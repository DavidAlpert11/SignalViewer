"""Map objects in templates: saved by signal names, re-created from another file; the automatic
"position on the map" template; flight-log templates; a quaternion attitude found by its names.

    python -m pytest tests/e2e/test_object_templates.py -q
"""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, menu_item, open_files, pg  # noqa: E402,F401

FLIGHT = "Time,GPS.Lat,GPS.Lng,GPS.Alt,ATT.Yaw,ATT.Pitch,ATT.Roll\n"


@pytest.fixture(autouse=True)
def _files(pg):
    d = pg.env["data"]
    for name, lat0 in (("tpl_flight_a.csv", 32.0), ("tpl_flight_b.csv", 31.5)):
        p = os.path.join(d, name)
        if not os.path.exists(p):
            with open(p, "w") as f:
                f.write(FLIGHT + "".join(f"{i * 0.5},{lat0 + i * 1e-4:.6f},34.8,{500 + i},{i % 360 - 180},{i % 7},{i % 9}\n" for i in range(300)))
    p = os.path.join(d, "tpl_track.csv")                      # a plain file: no template made for it
    if not os.path.exists(p):
        with open(p, "w") as f:
            f.write("Time,latitude,longitude,altitude,heading\n" + "".join(f"{i},{31.7 + i * 1e-4:.6f},35.0,{200 + i},{i % 360}\n" for i in range(200)))
    p = os.path.join(d, "tpl_px4.csv")
    if not os.path.exists(p):
        with open(p, "w") as f:
            f.write("Time,vehicle_global_position.lat,vehicle_global_position.lon,vehicle_global_position.alt,"
                    "vehicle_attitude.q[0],vehicle_attitude.q[1],vehicle_attitude.q[2],vehicle_attitude.q[3]\n")
            f.write("".join(f"{i * 0.5},{31.9 + i * 1e-4:.6f},34.9,300,1,0,0,0\n" for i in range(200)))
    yield


def _objects(pg):
    return [o for t in S(pg, "s.ws.tabs") for p in t["plots"] for o in (p.get("objects") or [])]


def test_template_keeps_objects_by_name_and_recreates_them_from_another_file(pg):
    open_files(pg, "tpl_flight_a.csv")
    pg.locator(".plot .mode-seg button", has_text="Map").click()
    pg.locator(".obj-add").click()
    pg.locator(".obj-kind", has_text="UAV").click()
    pg.locator(".obj-dialog .obj-name input").fill("Heron")
    pg.locator(".obj-dialog .btn.primary").click()
    pg.wait_for_selector(".obj-chip")
    pg.locator(".tpl-strip-save").click()
    pg.wait_for_selector(".tpl-editor")
    pg.locator(".tpl-editor input").first.fill("Heron on the map")
    pg.locator(".tpl-editor .btn.primary").click()
    pg.wait_for_selector(".tpl-details h3:has-text('Heron on the map')")
    pg.keyboard.press("Escape")
    # another file with the same signal names: the template re-creates the object from it
    rid_a = S(pg, "s.runs.find(r => r.name === 'tpl_flight_a.csv').id")
    pg.locator(".run-head", has_text="tpl_flight_a.csv").click(button="right"); menu_item(pg, "Remove")
    open_files(pg, "tpl_flight_b.csv", clear=False)
    rid_b = S(pg, "s.runs.find(r => r.name === 'tpl_flight_b.csv').id")
    pg.click(".topbar [aria-label='Templates']"); menu_item(pg, "Open a template")
    pg.locator(".tpl-item", has_text="Heron on the map").click()
    pg.locator(".tpl-actions .btn.primary").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.plots.some(p => (p.objects || []).length))")
    o = _objects(pg)[-1]
    assert o["name"] == "Heron" and o["kind"] == "uav"
    assert o["lat"] == f"{rid_b}/GPS.Lat" and o["yaw"] == f"{rid_b}/ATT.Yaw" and o["roll"] == f"{rid_b}/ATT.Roll"
    assert rid_a != rid_b


def test_position_template_only_for_a_file_with_a_position(pg):
    open_files(pg, "run_a.csv")
    pg.wait_for_selector(".tpl-strip")
    assert pg.locator(".tpl-strip .chipbtn", has_text="Position on the map").count() == 0
    # an ArduPilot-like file is offered the ArduPilot flight template (the more exact one)
    open_files(pg, "tpl_flight_a.csv")
    pg.locator(".tpl-strip .chipbtn", has_text="ArduPilot · Flight on the map").wait_for()
    # a plain file with a position (alone): the automatic one
    for name in ("run_a.csv", "tpl_flight_a.csv"):
        pg.locator(".run-head", has_text=name).click(button="right"); menu_item(pg, "Remove")
    pg.wait_for_function("window.__sv.state().runs.filter(r => r.format !== 'derived').length === 0")
    open_files(pg, "tpl_track.csv", clear=False)
    chip = pg.locator(".tpl-strip .chipbtn", has_text="Position on the map")
    chip.wait_for()
    chip.click()                                           # T48: one file, nothing to choose - opens at once
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.plots.some(p => p.mode === '3d' && (p.objects || []).length))")
    tab = [t for t in S(pg, "s.ws.tabs") if any(p.get("objects") for p in t["plots"])][-1]
    assert [p["mode"] for p in tab["plots"]] == ["geo", "3d"]
    o = tab["plots"][0]["objects"][0]
    assert o["lat"].endswith("/latitude") and o["lon"].endswith("/longitude") and o["alt"].endswith("/altitude") and o["yaw"].endswith("/heading")


def test_quaternion_found_by_name(pg):
    open_files(pg, "tpl_px4.csv")
    pg.locator(".plot .mode-seg button", has_text="Map").click()
    pg.locator(".obj-add").click()
    pg.wait_for_selector(".obj-dialog")
    assert pg.locator(".obj-dialog select", has_text="a quaternion").evaluate("e => e.value") == "quat"
    pg.locator(".obj-dialog .btn.primary").click()
    o = _objects(pg)[-1]
    assert o["qw"].endswith("/vehicle_attitude.q[0]") and o["qz"].endswith("/vehicle_attitude.q[3]") and o.get("yaw") is None


def test_ardupilot_flight_template(pg):
    open_files(pg, "tpl_flight_a.csv")
    pg.click(".topbar [aria-label='Templates']"); menu_item(pg, "Open a template")
    pg.locator(".tpl-item", has_text="ArduPilot · Flight on the map & 3D").click()
    pg.locator(".tpl-actions .btn.primary").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.plots.some(p => (p.objects || []).length))")
    o = _objects(pg)[-1]
    for role, name in (("lat", "GPS.Lat"), ("lon", "GPS.Lng"), ("alt", "GPS.Alt"), ("yaw", "ATT.Yaw"), ("pitch", "ATT.Pitch"), ("roll", "ATT.Roll")):
        assert o[role].endswith("/" + name), (role, o[role])
