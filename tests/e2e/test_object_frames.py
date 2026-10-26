"""Q101 / Q102: a map object's position from ECEF / NED / ENU (with a reference point), smoothed
over a window in seconds; and vector smoothing in Create signals.

    python -m pytest tests/e2e/test_object_frames.py -q
"""
import math
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401


def _ecef(lat, lon, alt):
    a, f = 6378137.0, 1 / 298.257223563
    e2 = f * (2 - f)
    la, lo = math.radians(lat), math.radians(lon)
    n = a / math.sqrt(1 - e2 * math.sin(la) ** 2)
    return ((n + alt) * math.cos(la) * math.cos(lo), (n + alt) * math.cos(la) * math.sin(lo), (n * (1 - e2) + alt) * math.sin(la))


@pytest.fixture(autouse=True)
def _files(pg):
    d = pg.env["data"]
    if not os.path.exists(os.path.join(d, "obj_ned.csv")):
        with open(os.path.join(d, "obj_ned.csv"), "w") as f:
            f.write("Time,N,E,D\n")
            for i in range(200):                       # 10 m/s north, a little noise on east
                f.write(f"{i * 0.1:.1f},{i * 1.0:.3f},{(1 if i % 2 else -1) * 0.5:.3f},-50\n")
        with open(os.path.join(d, "obj_ecef.csv"), "w") as f:
            f.write("Time,X,Y,Z\n")
            for i in range(200):
                x, y, z = _ecef(32.0 + i * 1e-5, 35.0, 100.0)
                f.write(f"{i * 0.1:.1f},{x:.3f},{y:.3f},{z:.3f}\n")
    yield


def _map(pg, name):
    open_files(pg, name)
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="Map").first.click()
    pg.locator(".obj-add").click()
    pg.wait_for_selector(".obj-dialog")


def _pick(pg, k, name):
    pg.locator(".obj-dialog .obj-role").nth(k).locator(".picker-btn").click()
    pg.keyboard.type(name); pg.keyboard.press("Enter")


def _derived(pg):
    return S(pg, "(s.runs.find(r => r.format === 'derived')?.signals ?? []).map(x => ({ id: x.id, op: x.op, params: x.params, sources: x.sources }))")


def test_object_from_ned_with_a_typed_origin_and_edit_keeps_it(pg):
    _map(pg, "obj_ned.csv")
    pg.select_option(".obj-pos-frame", "ned")
    for k, n in enumerate(("N", "E", "D")):
        _pick(pg, k, n)
    pg.select_option(".obj-ref", "manual")
    for k, v in enumerate(("32", "35", "0")):
        pg.fill(f".obj-ref-{k}", v)
    pg.click(".obj-save")
    pg.wait_for_function("(window.__sv.state().ws.tabs[0].plots[0].objects ?? []).length === 1")
    obj = S(pg, "s.ws.tabs[0].plots[0].objects[0]")
    d = {x["id"]: x for x in _derived(pg)}
    assert d[obj["lat"]]["op"] == "frame" and d[obj["lat"]]["params"]["src"] == "ned"
    assert d[obj["lat"]]["params"]["ref_lat"] == 32 and obj["alt"] in d
    # edit: the dialog reads the chain back, and saving it unchanged makes nothing new
    pg.evaluate("(() => { const p = window.__sv.state().ws.tabs[0].plots[0]; window.__sv.setState({ objectDialog: { plotId: p.id, objectId: p.objects[0].id } }); })()")
    pg.wait_for_selector(".obj-dialog")
    assert pg.input_value(".obj-pos-frame") == "ned" and pg.input_value(".obj-ref") == "manual"
    assert pg.input_value(".obj-ref-0") == "32"
    pg.click(".obj-save")
    pg.wait_for_selector(".obj-dialog", state="detached")
    assert len(_derived(pg)) == 3


def test_object_from_ecef_smoothed(pg):
    _map(pg, "obj_ecef.csv")
    pg.select_option(".obj-pos-frame", "ecef")
    assert pg.locator(".obj-ref").count() == 0                     # ECEF is a place by itself
    for k, n in enumerate(("X", "Y", "Z")):
        _pick(pg, k, n)
    pg.fill(".obj-smooth", "2")
    pg.click(".obj-save")
    pg.wait_for_function("(window.__sv.state().ws.tabs[0].plots[0].objects ?? []).length === 1")
    obj = S(pg, "s.ws.tabs[0].plots[0].objects[0]")
    d = {x["id"]: x for x in _derived(pg)}
    sm = d[obj["lat"]]
    assert sm["op"] == "vecsmooth" and sm["params"]["window"] == 2 and sm["params"]["kind"] == "lla"
    assert d[sm["sources"][0]]["op"] == "frame" and d[sm["sources"][0]]["params"]["src"] == "ecef"
    assert len(d) == 6
    pg.evaluate("(() => { const p = window.__sv.state().ws.tabs[0].plots[0]; window.__sv.setState({ objectDialog: { plotId: p.id, objectId: p.objects[0].id } }); })()")
    pg.wait_for_selector(".obj-dialog")
    assert pg.input_value(".obj-pos-frame") == "ecef" and pg.input_value(".obj-smooth") == "2"


def test_vector_smoothing_in_create_signals(pg):
    open_files(pg, "obj_ned.csv")
    for n in ("N", "E", "D"):
        sig(pg, n).click()
    pg.click("[aria-label='Create signals']")
    pg.click(".seg.wide button:has-text('Several')")
    pg.locator(".analysis .afield select").first.select_option("vecsmooth")
    pg.click(".msp-top .linklike:has-text('From the active plot')")
    pg.fill(".vs-window", "1")
    pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("(window.__sv.state().runs.find(r => r.format === 'derived')?.signals ?? []).length === 3")
    names = S(pg, "s.runs.find(r => r.format === 'derived').signals.map(x => x.name)")
    assert names == ["smooth_1s.N", "smooth_1s.E", "smooth_1s.D"]
