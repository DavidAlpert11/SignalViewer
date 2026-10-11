"""Objects on the map: added through the dialog (signals filled in from their names, from any
file), drawn at the timeline's time pointing where they head, followed, removed with their file.

    python -m pytest tests/e2e/test_map_objects.py -q
"""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, menu_item, open_files, pg  # noqa: E402,F401


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
    pg.locator(".plot .mode-seg button", has_text="Map").click()
    pg.locator(".obj-add").click()
    pg.wait_for_selector(".obj-dialog")
    filled = pg.evaluate("[...document.querySelectorAll('.obj-role select')].filter(s => !s.getAttribute('aria-label').includes('–')).map(s => s.value.split('/')[1] || '')")
    assert filled == ["GPS.Lat", "GPS.Lng", "GPS.Alt", "ATT.Yaw", "ATT.Pitch", "ATT.Roll"]
    pg.locator(".obj-dialog .btn.primary").click()
    pg.locator(".obj-add").click()
    pg.locator(".obj-kind", has_text="Ship").click()
    pg.select_option(".obj-main select", label="obj_ship.csv")
    assert pg.locator(".obj-dialog .obj-name input").input_value().startswith("Ship")   # the name follows the kind
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
    pg.wait_for_timeout(400)
    a = pg.locator(".plot .geo canvas").screenshot()
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, t1: 250 } })")
    pg.wait_for_timeout(400)
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
