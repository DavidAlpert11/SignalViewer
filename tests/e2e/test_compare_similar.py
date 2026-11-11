"""L9: Compare with similar… - signals of one file whose names differ in one segment (phys / nav, XKF1[0] /
XKF1[1]) found by name, compared in one tab (values left, member − reference right) with angle differences
wrapped, from the signal list's group menu, a signal's menu and Ctrl+K.

    python -m pytest tests/e2e/test_compare_similar.py -q
"""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, menu_item, open_files, pg, S  # noqa: E402,F401

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _copy(pg, name):
    shutil.copy(os.path.join(ROOT, "examples", name), pg.env["data"])


def _value_at(pg, sid, t):
    return pg.evaluate("""([sid, t]) => fetch('/api/cursor', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signals: [sid], t }) }).then(r => r.json()).then(r => r.values[sid])""", [sid, t])


def _derived(pg):
    return pg.evaluate("(window.__sv.state().runs.find((r) => r.format === 'derived')?.signals ?? []).map((s) => ({ id: s.id, op: s.op, params: s.params, sources: s.sources }))")


def test_group_menu_makes_the_tab(pg):
    """nav.att's group menu: roll / pitch / yaw, each with phys (the truth: the reference) and nav; Both:
    one tab, values left and nav − phys right; the yaw difference made with wrap (the values: no unit, so
    the backend's angle guess decides 360 or 2pi)."""
    _copy(pg, "three_objects.csv")
    open_files(pg, "three_objects.csv")
    pg.locator(".grp-head", has=pg.locator(".nm", has_text="att")).nth(1).click(button="right")      # nav.att
    menu_item(pg, "Compare with similar…")
    dlg = pg.locator(".simdlg")
    dlg.wait_for()
    assert [x for x in dlg.locator(".sim-leaf").all_inner_texts()] == ["*.att.roll", "*.att.pitch", "*.att.yaw"]
    assert dlg.locator(".sim-ref option:checked").inner_text() == "phys"
    assert "truth / navigation / receiver" in dlg.locator(".sim-how").first.inner_text()
    n0 = len(S(pg, "s.ws.tabs"))
    dlg.locator(".sim-make").click()
    dlg.locator(".cmpobj-stats").wait_for()
    tab = S(pg, "s.ws.tabs")[n0]
    assert tab["cols"] == 2 and [p["title"] for p in tab["plots"]] == ["*.att.roll", "*.att.roll: − phys", "*.att.pitch", "*.att.pitch: − phys", "*.att.yaw", "*.att.yaw: − phys"]
    assert [len(p["signals"]) for p in tab["plots"]] == [2, 1, 2, 1, 2, 1]
    subs = [d for d in _derived(pg) if d["op"] == "sub"]
    yaw = [d for d in subs if d["sources"][0].endswith("nav.att.yaw")][0]
    assert yaw["params"].get("wrap") in ("2pi", 360) and all("wrap" in d["params"] for d in subs)
    # again: the same signals are reused
    n = len(_derived(pg))
    dlg.locator(".sim-make").click()
    pg.wait_for_function(f"window.__sv.state().ws.tabs.length === {n0 + 2}")
    assert len(_derived(pg)) == n


def test_ekf_lane_yaw_across_north_is_small(pg):
    """XKF1[0].Yaw / XKF1[1].Yaw [deg] (an instance family): the heading passes 359 -> 0, and lane 1 - lane 0
    stays +0.5°, never ~360 - the backend's sub with wrap 360; Ctrl+K opens the dialog for the file too."""
    _copy(pg, "ardupilot_lanes.csv")
    open_files(pg, "ardupilot_lanes.csv")
    rid = pg.evaluate("window.__sv.state().runs.find((r) => r.format !== 'derived').id")
    pg.evaluate(f"window.__sv.setState({{ similarDialog: {{ runId: {rid!r}, ids: [{rid + '/XKF1[1].Yaw [deg]'!r}] }} }})")
    dlg = pg.locator(".simdlg")
    dlg.wait_for()
    assert dlg.locator(".sim-leaf").all_inner_texts() == ["XKF1[*].Yaw"] and "instances" in dlg.inner_text()
    dlg.locator(".sim-ref").select_option("XKF1[0]")
    dlg.locator(".cmpobj-show button", has_text="Errors vs the reference").click()
    dlg.locator(".sim-make").click()
    dlg.locator(".cmpobj-stats").wait_for()
    row = dlg.locator(".cmpobj-stats tbody tr").first.inner_text().split("\t")
    assert abs(float(row[2]) - 0.5) < 0.01 and float(row[4]) < 0.51                 # RMS 0.5, max |error| 0.5
    sub = [d for d in _derived(pg) if d["op"] == "sub"][0]
    assert sub["params"]["wrap"] == 360
    # 155 s into the circle the heading crosses north (0 / 360): still +0.5
    for t in (150.0, 157.0, 157.1, 160.0):
        assert abs(_value_at(pg, sub["id"], t) - 0.5) < 0.01, t
    dlg.locator("button", has_text="Close").click()
    pg.keyboard.press("Control+k"); pg.keyboard.type("similar signals"); pg.keyboard.press("Enter")
    pg.wait_for_selector(".simdlg")
    assert "XKF1[*].Roll" in pg.locator(".simdlg .sim-list").inner_text()
