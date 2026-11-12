"""L1-L6 (round of 2026-11-10): objects whose position is in metres - NED, ENU, ECEF - are found by their
names and added like latitude / longitude ones: every ArduPilot EKF lane through the EKF origin (ORGN),
generic ned / enu / ecef names through an origin group; once added they are not offered again; a local
position without an origin gets one suggested in Advanced….

    python -m pytest tests/e2e/test_local_objects.py -q
"""
import base64
import os
import shutil
import struct

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import flat_maps, env, open_files, pg, S  # noqa: E402,F401

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _copy(pg, name):
    shutil.copy(os.path.join(ROOT, "examples", name), pg.env["data"])


def _geo(pg):
    return S(pg, "s.ws.tabs[0].plots.find((p) => (p.mode === 'geo' || p.mode === '3d'))")


def _lats(pg, o):
    tr = pg.evaluate("""o => fetch('/api/object_track', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lat: o.lat, lon: o.lon }) }).then(r => r.json())""", o)
    return struct.unpack(f"<{tr['n']}d", base64.b64decode(tr["lat"]))


def test_ekf_lanes_found_added_once_and_placed_through_orgn(pg):
    """F1, F7, F8, L3, L6: POS, both EKF3 lanes and the GPS are offered (not ORGN); Add all puts them on a map;
    lane 1 lies 1.5 m north of lane 0; the bar then has nothing to offer and the found list shows every row added."""
    _copy(pg, "ardupilot_lanes.csv")
    open_files(pg, "ardupilot_lanes.csv")
    bar = pg.locator(".obj-suggest")
    bar.wait_for()
    assert "4 objects found: POS, XKF1[0], XKF1[1], GPS[0]" in bar.inner_text()
    bar.locator(".obj-suggest-add").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.some((p) => (p.mode === 'geo' || p.mode === '3d') && (p.objects ?? []).length === 4)")
    objs = {o["name"]: o for o in _geo(pg)["objects"]}
    assert set(objs) == {"POS", "XKF1[0]", "XKF1[1]", "GPS[0]"}
    lane0, lane1 = objs["XKF1[0]"], objs["XKF1[1]"]
    assert lane0["lat"].startswith("derived/") and lane0["roll"].endswith("XKF1[0].Roll [deg]")      # its own angles
    a, b = _lats(pg, lane0), _lats(pg, lane1)
    north = [(y - x) * 110_900 for x, y in zip(a, b)]                                               # ~m per degree at 32.8°
    assert all(abs(d - 1.5) < 0.1 for d in north[10:-10])
    pos = _lats(pg, objs["POS"])
    assert all(abs((x - p) * 110_900) < 0.05 for x, p in zip(a[10:-10], pos[10:-10]))               # lane 0 on POS
    pg.wait_for_selector(".obj-suggest:not(.obj-compare-offer)", state="detached")                  # F8: not offered again
    pg.locator(".obj-add").first.click()
    pg.wait_for_selector(".obj-found")
    assert pg.locator(".obj-found-row.added").count() == 4 and pg.locator(".obj-add-all").count() == 0
    lane_row = pg.locator(".obj-found-row", has=pg.locator(".obj-found-name[value='XKF1[1]']"))
    lane_row.locator(".obj-why").click()
    why = lane_row.locator(".obj-why-lines").inner_text()
    assert "ORGN[0]" in why and "EKF origin" in why and "EKF3 lane 1" in why


def test_generic_local_names_with_their_origin(pg):
    """L1 / L3: tgt.ned.x, ship.ecef_x, boat.pos.north/east/up (ENU), rov.pos.n/e/d - each found with its frame;
    origin.* is the origin of the local ones, not an object; Add all adds the four, once."""
    _copy(pg, "local_frames.csv")
    open_files(pg, "local_frames.csv")
    bar = pg.locator(".obj-suggest")
    bar.wait_for()
    assert "4 objects found" in bar.inner_text() and "origin" not in bar.inner_text()
    bar.locator(".obj-suggest-choose").click()
    pg.wait_for_selector(".obj-found")
    labels = dict(zip(pg.locator(".obj-found-name").evaluate_all("els => els.map((e) => e.value)"),
                      pg.locator(".obj-found-frame").all_inner_texts()))
    assert labels == {"tgt": "NED · origin origin", "ship": "ECEF", "boat": "ENU · origin origin", "rov": "NED · origin origin"}
    pg.locator(".obj-add-all", has_text="Add all (4)").click()
    pg.wait_for_selector(".obj-found", state="detached")
    assert len(_geo(pg)["objects"]) == 4
    pg.wait_for_selector(".obj-suggest:not(.obj-compare-offer)", state="detached")


def test_local_position_without_origin_gets_one_suggested(pg):
    """L5: with no origin in the file the NED row says it needs one; Advanced… fills in the file's GPS
    (its first fix becomes the origin) and says so; Save puts the object on the map."""
    src = open(os.path.join(ROOT, "examples", "local_frames.csv")).read().splitlines()
    head = src[0].replace("origin.lat", "gps.lat").replace("origin.lon", "gps.lon").replace("origin.alt", "gps.alt")
    with open(os.path.join(pg.env["data"], "no_origin.csv"), "w") as fh:
        fh.write("\n".join([head] + src[1:200]) + "\n")
    open_files(pg, "no_origin.csv")
    pg.locator(".obj-suggest").wait_for()
    pg.locator(".obj-suggest-choose").click()
    pg.wait_for_selector(".obj-found")
    row = pg.locator(".obj-found-row", has=pg.locator(".obj-found-name[value='tgt']"))
    assert row.locator(".obj-found-frame").inner_text() == "NED · needs an origin - Advanced…"
    assert row.locator(".obj-found-check").is_disabled()
    row.locator(".obj-adv").click()
    pg.wait_for_selector(".obj-dialog")
    assert pg.locator(".obj-dialog .obj-ref").input_value() == "signals"
    assert "first valid sample of gps" in pg.locator(".obj-origin-why").inner_text()
    pg.locator(".obj-dialog .obj-save").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.some((p) => (p.objects ?? []).some((o) => o.name === 'tgt'))")


def _value_at(pg, sid, t):
    return pg.evaluate("""([sid, t]) => fetch('/api/cursor', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ signals: [sid], t }) }).then(r => r.json()).then(r => r.values[sid])""", [sid, t])


def _derived_count(pg):
    return pg.evaluate("(window.__sv.state().runs.find((r) => r.format === 'derived')?.signals ?? []).length")


def test_compare_objects_dialog_on_ekf_lanes(pg):
    """L8: Compare… with POS as the reference: Position + Attitude, Both - one tab each, values left and errors
    right; lane 1's north error +1.5 m and its yaw error +0.5°, lane 0's ~0; the statistics table; velocity off
    with its reason (POS has none); the same choice made again reuses the signals; Velocity from lane 0."""
    _copy(pg, "ardupilot_lanes.csv")
    open_files(pg, "ardupilot_lanes.csv")
    flat_maps(pg)                    # P4: the light drawing - the software-rendered 3D view slowed the job past the waits here
    pg.locator(".obj-suggest-add").click()
    pg.wait_for_selector(".rel-panel")
    pg.locator(".rel-panel .rel-compare-open").click()
    dlg = pg.locator(".cmpobj")
    dlg.wait_for()
    assert dlg.locator(".cmpobj-ref option:checked").inner_text() == "POS"
    vel = dlg.locator(".cmpobj-q-velocity")
    assert vel.is_disabled() and "POS has no velocity" in dlg.inner_text()
    dlg.locator(".cmpobj-objs label", has_text="GPS[0]").locator("input").uncheck()
    tabs0 = len(S(pg, "s.ws.tabs"))
    dlg.locator(".cmpobj-make").click()
    dlg.locator(".cmpobj-stats").wait_for()
    tabs = S(pg, "s.ws.tabs")[tabs0:]
    assert [t["name"] for t in tabs] == ["Position (NED) vs POS", "Attitude vs POS"]
    pos = tabs[0]
    assert pos["cols"] == 2 and len(pos["plots"]) == 8
    assert pos["plots"][0]["title"].startswith("north (NED)") and pos["plots"][1]["title"].startswith("Δnorth (NED")
    assert len(pos["plots"][0]["signals"]) == 3 and len(pos["plots"][1]["signals"]) == 2          # POS + 2 lanes; 2 errors
    e0, e1 = (p["sig"] for p in pos["plots"][1]["signals"])
    assert abs(_value_at(pg, e0, 100)) < 0.05 and abs(_value_at(pg, e1, 100) - 1.5) < 0.05
    yaw = [p["sig"] for p in tabs[1]["plots"][5]["signals"]]                                         # Δyaw column
    assert abs(_value_at(pg, yaw[1], 100) - 0.5) < 0.01
    rows = dlg.locator(".cmpobj-stats tbody tr").all_inner_texts()
    north1 = [r for r in rows if r.startswith("XKF1[1]") and "Δnorth" in r][0]
    assert "1.5" in north1.split("\t")[2]                                                          # RMS
    n = _derived_count(pg)
    dlg.locator(".cmpobj-make").click()                                                             # the same again: reused
    pg.wait_for_function(f"window.__sv.state().ws.tabs.length === {tabs0 + 4}")
    assert _derived_count(pg) == n
    # velocity: lane 0 as the reference, lane 1 compared - the speed error is zero (same velocities)
    dlg.locator(".cmpobj-ref").select_option(label="XKF1[0]")
    assert not dlg.locator(".cmpobj-q-velocity").is_disabled()
    for q in ("position", "attitude"):
        dlg.locator(f".cmpobj-q-{q}").uncheck()
    dlg.locator(".cmpobj-make").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.name === 'Velocity (NED) vs XKF1[0]')")
    vt = [t for t in S(pg, "s.ws.tabs") if t["name"] == "Velocity (NED) vs XKF1[0]"][0]
    sp = [p for p in vt["plots"] if p["title"].startswith("speed error")][0]["signals"]
    assert all(abs(_value_at(pg, x["sig"], 100)) < 1e-6 for x in sp)
