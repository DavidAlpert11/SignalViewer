"""Objects on the map: added through the dialog (signals filled in from their names, from any
file), drawn at the timeline's time pointing where they head, followed, removed with their file.

    python -m pytest tests/e2e/test_map_objects.py -q
"""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, frames, menu_item, open_files, pg, S, object_form, save_as  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _files(pg):
    d = pg.env["data"]
    path = os.path.join(d, "obj_aircraft.csv")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write("Time,GPS.Lat,GPS.Lng,GPS.Alt,ATT.Yaw,ATT.Pitch,ATT.Roll\n")
            for i in range(600):
                t = i * 0.5
                f.write(f"{t},{32.0 + i * 1e-4:.6f},{34.8:.6f},{1000 + i},{90.0:.1f},0,0\n")   # moving north, nose east
        with open(os.path.join(d, "obj_ship.csv"), "w") as f:
            f.write("Time,lat,lon\n")
            for i in range(300):
                f.write(f"{i * 1.0},{32.05:.6f},{34.70 + i * 1e-4:.6f}\n")                     # moving east
    yield


def _map_with_objects(pg):
    open_files(pg, "obj_aircraft.csv", "obj_ship.csv")
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="Map").first.click()
    pg.locator(".obj-add").click(); object_form(pg)
    # each role: a signal typed by name (SignalField) - the one guessed from the names is shown in it
    filled = pg.evaluate("[...document.querySelectorAll('.obj-role .picker-val')].map(e => e.querySelector('.ph') ? '' : e.textContent.trim())")
    assert filled == ["GPS.Lat", "GPS.Lng", "GPS.Alt", "ATT.Yaw", "ATT.Pitch", "ATT.Roll"]
    pg.locator(".obj-dialog .btn.primary").click()
    pg.locator(".obj-add").click(); object_form(pg)                              # the ship: the found row not added yet
    pg.locator(".obj-kind", has_text="Ship").click()
    pg.select_option(".obj-main select", label="obj_ship.csv")
    assert pg.locator(".obj-dialog .obj-name input").input_value() == "obj_ship"     # N5: the found name (no prefix: the file's) stays
    pg.locator(".obj-dialog .btn.primary").click()
    pg.wait_for_selector(".obj-chip >> nth=1")
    return S(pg, "s.ws.tabs[0].plots[0].objects")


def test_add_objects_from_two_files(pg):
    objs = _map_with_objects(pg)
    assert [o["kind"] for o in objs] == ["aircraft", "ship"]
    assert objs[1]["lat"].endswith("/lat") and objs[1]["yaw"] is None          # heading from motion
    assert pg.locator(".obj-chip").count() == 2


def test_object_position_and_heading_at_the_time(pg):
    objs = _map_with_objects(pg)
    # the server's track: aircraft heading from its yaw (90 = east), ship from its motion (east)
    tr = pg.evaluate(f"""fetch('/api/object_track', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ lat: '{objs[1]['lat']}', lon: '{objs[1]['lon']}' }}) }}).then(r => r.json())""")
    import base64
    import struct
    course = struct.unpack(f"<{tr['n']}f", base64.b64decode(tr["course"]))
    assert all(abs(c - 90) < 1 for c in course[5:-5])
    # icons are drawn where the objects are at the timeline's time: something at the ship's place changes as time moves
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, t1: 10 } })")
    frames(pg, 3)
    a = pg.locator(".plot .geo canvas").screenshot()
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, t1: 250 } })")
    frames(pg, 3)
    b = pg.locator(".plot .geo canvas").screenshot()
    assert a != b                                                               # the icons moved


def test_follow_and_remove_with_its_file(pg):
    _map_with_objects(pg)
    pg.locator(".obj-chip").first.locator("[aria-pressed]").click()
    assert S(pg, "s.ws.tabs[0].plots[0].followObject") is not None
    pg.locator(".obj-chip").first.locator("[aria-pressed]").click()
    assert S(pg, "s.ws.tabs[0].plots[0].followObject") is None
    # closing the ship's file (the file panel's menu) removes the ship - its position is gone - and
    # keeps the aircraft
    pg.locator(".run-head", has_text="obj_ship.csv").click(button="right")
    menu_item(pg, "Remove")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].objects.length === 1")
    assert [o["kind"] for o in S(pg, "s.ws.tabs[0].plots[0].objects")] == ["aircraft"]


def test_edit_and_remove_object(pg):
    _map_with_objects(pg)
    pg.locator(".obj-chip-main").first.click()
    pg.wait_for_selector(".obj-dialog")
    pg.locator(".obj-dialog .obj-name input").fill("Heron 7")
    pg.locator(".obj-kind", has_text="UAV").click()
    pg.locator(".obj-dialog .btn.primary").click()
    o = S(pg, "s.ws.tabs[0].plots[0].objects[0]")
    assert o["name"] == "Heron 7" and o["kind"] == "uav"
    pg.locator(".obj-chip").first.locator("button[aria-label^='Remove']").click()
    assert len(S(pg, "s.ws.tabs[0].plots[0].objects")) == 1
    pg.keyboard.press("Control+z")                                              # undo brings it back
    assert len(S(pg, "s.ws.tabs[0].plots[0].objects")) == 2


def _three(pg):
    import shutil
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    shutil.copy(os.path.join(root, "examples", "three_objects.csv"), pg.env["data"])
    open_files(pg, "three_objects.csv")
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="Map").first.click()


def test_found_objects_add_all_in_one_undo(pg):
    """N5: the three objects of the fixture are found, classified, from their own prefixes, and added in
    one click and one Undo; *Why?* says why in plain words."""
    _three(pg)
    pg.locator(".obj-add").click()
    pg.wait_for_selector(".obj-found")
    rows = pg.locator(".obj-found-row")
    assert [rows.nth(i).locator(".obj-found-name").input_value() for i in range(3)] == ["phys", "nav", "gps"]
    assert pg.locator(".obj-found .obj-cls").all_inner_texts() == ["truth", "navigation", "receiver"]
    assert rows.nth(1).locator(".obj-chip-sig").all_inner_texts() == ["nav.lat", "nav.lon", "nav.alt", "nav.att.roll", "nav.att.pitch", "nav.att.yaw"]
    rows.nth(1).locator(".obj-why").click()
    why = rows.nth(1).locator(".obj-why-lines").inner_text()
    assert "names under the prefix nav" in why and "sub-group att of nav" in why and "the word 'nav'" in why
    rows.nth(2).locator(".obj-why").click()
    assert "course over ground" in rows.nth(2).locator(".obj-why-lines").inner_text()     # gps: position only
    assert "How to name your signals" in pg.locator(".obj-naming").inner_text()
    n0 = len(S(pg, "window.__sv.state().ws.tabs[0].plots[0].objects ?? []"))
    pg.locator(".obj-add-all", has_text="Add all (3)").click()
    pg.wait_for_selector(".obj-found", state="detached")
    objs = S(pg, "s.ws.tabs[0].plots[0].objects")
    assert [o["name"] for o in objs] == ["phys", "nav", "gps"] and n0 == 0
    assert objs[0]["roll"].endswith("/phys.att.roll") and objs[2]["yaw"] is None   # no mixed sources
    assert len({o["color"] for o in objs}) == 3
    pg.keyboard.press("Control+z")                                              # one Undo takes all three
    pg.wait_for_function("(window.__sv.state().ws.tabs[0].plots[0].objects ?? []).length === 0")


def test_found_objects_add_selected_and_shown_as_added(pg):
    _three(pg)
    pg.locator(".obj-add").click()
    pg.wait_for_selector(".obj-found")
    pg.locator(".obj-found-row").nth(2).locator(".obj-found-check").uncheck()
    pg.locator(".obj-found-row").nth(0).locator(".obj-found-name").fill("Truth")
    pg.locator(".obj-add-sel").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].objects.length === 2")
    assert [o["name"] for o in S(pg, "s.ws.tabs[0].plots[0].objects")] == ["Truth", "nav"]
    pg.locator(".obj-add").click()
    pg.wait_for_selector(".obj-found")
    assert pg.locator(".obj-found-row.added").count() == 2 and pg.locator(".obj-add-all").inner_text() == "Add"


def test_suggestion_bar_adds_every_object_with_its_look(pg):
    """N5: opening a file with objects shows "3 objects found: phys, nav, gps"; Add all puts them on a new
    map (the tab has none), each with its class's look - navigation dashed, the receiver as points and
    drawn by its motion; one Undo takes them back; × hides the bar for the file."""
    import shutil
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    shutil.copy(os.path.join(root, "examples", "three_objects.csv"), pg.env["data"])
    open_files(pg, "three_objects.csv")
    bar = pg.locator(".obj-suggest")
    bar.wait_for()
    assert "3 objects found: phys, nav, gps" in bar.inner_text()
    bar.locator(".obj-suggest-add").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.some((p) => p.mode === 'geo' && (p.objects ?? []).length === 3)")
    objs = S(pg, "s.ws.tabs[0].plots.find((p) => p.mode === 'geo').objects")
    look = {o["name"]: (o.get("cls"), o.get("track"), o.get("attitudeSource")) for o in objs}
    assert look == {"phys": ("truth", None, None), "nav": ("navigation", "dash", None), "gps": ("receiver", "points", "motion")}
    pg.wait_for_selector(".obj-suggest:not(.obj-compare-offer)", state="detached")   # nothing new to suggest
    assert "Compare the objects with phys" in pg.locator(".obj-compare-offer").inner_text()   # N7: but their comparison
    gps_chip = pg.locator(".obj-chip", has_text="gps")
    assert gps_chip.locator(".obj-att-badge").count() == 1                      # ≈: its attitude is from motion
    assert pg.locator(".obj-chip", has_text="nav").locator(".obj-att-badge").count() == 0
    pg.locator(".toast button", has_text="Undo").click()
    pg.wait_for_function("!window.__sv.state().ws.tabs[0].plots.some((p) => (p.objects ?? []).length)")
    bar.wait_for()
    bar.locator(".obj-suggest-hide").click()
    pg.wait_for_selector(".obj-suggest", state="detached")


def test_found_list_borrows_an_attitude(pg):
    """N5: a position-only row may borrow the angles of another row; the object then points as that one
    does (its chip shows ≈), and editing it offers the source again (one commit)."""
    _three(pg)
    pg.locator(".obj-add").click()
    pg.wait_for_selector(".obj-found")
    gps = pg.locator(".obj-found-row").nth(2)
    gps.locator(".obj-found-att select").select_option(label="from nav")
    gps.locator(".obj-why").click()
    assert "borrowed from nav" in gps.locator(".obj-why-lines").inner_text()
    pg.locator(".obj-add-all").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].objects.length === 3")
    objs = {o["name"]: o for o in S(pg, "s.ws.tabs[0].plots[0].objects")}
    assert objs["gps"]["attitudeSource"] == {"object": objs["nav"]["id"]}
    chip = pg.locator(".obj-chip", has_text="gps")
    assert "borrowed from nav" in chip.locator(".obj-att-badge").get_attribute("aria-label")
    chip.locator(".obj-chip-main").click()
    pg.wait_for_selector(".obj-dialog")
    sel = pg.locator(".obj-att-source")
    assert sel.evaluate("e => e.options[e.selectedIndex].text") == "from nav"
    sel.select_option("motion")
    pg.locator(".obj-min-speed").fill("2.5")
    pg.locator(".obj-save").click()
    o = [x for x in S(pg, "s.ws.tabs[0].plots[0].objects") if x["name"] == "gps"][0]
    assert o["attitudeSource"] == "motion" and o["minSpeed"] == 2.5


def test_suggestion_bar_choose_opens_the_list_on_a_new_map(pg):
    """The bar's Choose… on a tab without a map makes one and opens the found list on it (it took the
    new plot's id while placePlot kept the empty plot's, so nothing opened)."""
    import shutil
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    shutil.copy(os.path.join(root, "examples", "three_objects.csv"), pg.env["data"])
    open_files(pg, "three_objects.csv")
    pg.locator(".obj-suggest-choose").click()
    pg.wait_for_selector(".obj-found")
    assert S(pg, "s.ws.tabs[0].plots.some((p) => p.mode === 'geo')")


def test_export_the_objects_for_tacview(pg):
    """N8: a map's objects saved as Tacview's ACMI 2.2 from the plot's menu - each object with its
    position and attitude (the receiver's from its motion)."""
    import shutil
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    shutil.copy(os.path.join(root, "examples", "three_objects.csv"), pg.env["data"])
    open_files(pg, "three_objects.csv")
    pg.locator(".obj-suggest .obj-suggest-add").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.some((p) => p.mode === 'geo' && (p.objects ?? []).length === 3)")
    i = S(pg, "s.ws.tabs[0].plots.findIndex((p) => p.mode === 'geo')")
    pg.locator(".plot-more").nth(i).click()
    menu_item(pg, "Export for Tacview (.acmi)…")
    save_as(pg, "flight")
    pg.wait_for_selector(".toast:has-text('3 object(s) saved for Tacview')")
    with open(os.path.join(pg.env["out"], "flight.acmi"), encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    assert lines[:2] == ["FileType=text/acmi/tacview", "FileVersion=2.2"]
    named = [x for x in lines if ",Name=" in x]
    assert [x.split(",Name=")[1].split(",")[0] for x in named] == ["phys", "nav", "gps"]
    assert all(len(x.split(",")[1][2:].split("|")) == 6 for x in named)       # position and attitude each
