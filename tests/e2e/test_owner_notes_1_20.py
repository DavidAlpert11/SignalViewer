"""The owner's notes of 2026-11-03 (1.20): a legend that neither jumps nor fills the plot, made
signals managed in the signal list, named nested groups, a map track coloured by the flight mode,
the Fleet's example, and in Sweeps the runs' tab, several objectives (Pareto) and Clear.

    python -m pytest tests/e2e/test_owner_notes_1_20.py -q
"""
import os
import shutil

import numpy as np
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, _csv, open_files, pg, env, sig, menu_item  # noqa: E402,F401

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def _many(pg, n):
    p = os.path.join(pg.env["data"], f"many{n}.csv")
    if not os.path.exists(p):
        t = np.arange(0, 20, 0.02)
        # values whose printed length changes as the cursor moves (1.5, -0.25, 123.456...)
        _csv(p, ["Time"] + [f"Channel_{i:02d}_measured" for i in range(n)],
             [t] + [np.sin(t * (1 + i / 7)) * 10 ** (i % 4) for i in range(n)])
    return os.path.basename(p)


def _plot_all(pg, prefix, n):
    pg.evaluate("""([prefix, n]) => { const st = window.__sv.state(); const r = st.runs.find((x) => x.signals.some((y) => y.name.startsWith(prefix)));
        const sigs = r.signals.filter((y) => y.name.startsWith(prefix)).slice(0, n)
          .map((y, i) => ({ sig: y.id, color: ['#3D8BFD', '#F07B3F', '#2FBF9F'][i % 3], width: 1.5, scale: 1, offset: 0 }));
        st.commit((ws) => { ws.tabs[0].plots[0].signals = sigs; return ws; }); }""", [prefix, n])
    pg.wait_for_function(f"window.__sv.state().ws.tabs[0].plots[0].signals.length === {n}")


def test_legend_beside_when_many_and_still_while_hovering(pg):
    open_files(pg, _many(pg, 30))
    _plot_all(pg, "Channel_", 30)
    # many: a column beside the plot, the header one line
    pg.wait_for_selector(".legend-side .lrow")
    assert pg.locator(".legend-side .lrow").count() == 30
    assert pg.locator(".plot-head").first.bounding_box()["height"] < 40
    # the filter, and the line under the pointer in front
    pg.fill(".legend-filter", "Channel_07")
    assert pg.locator(".legend-side .lrow").count() == 1
    pg.locator(".legend-side .lrow").first.hover()
    assert S(pg, "s.legendFocus && s.legendFocus.sig.endsWith('Channel_07_measured')")
    pg.fill(".legend-filter", "")
    # above the plot (the menu), a few signals: the header never gets lower while the pointer moves
    pg.locator(".plot-more").first.click()
    pg.locator(".menu.ctx button", has_text="Legend").first.hover()
    menu_item(pg, "Above the plot")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].legend === 'top'")
    pg.evaluate("""() => { const st = window.__sv.state(); st.commit((ws) => { ws.tabs[0].plots[0].signals = ws.tabs[0].plots[0].signals.slice(0, 6); return ws; }); }""")
    box = pg.locator(".plot-body").first.bounding_box()
    hs = []
    for i in range(40):
        pg.mouse.move(box["x"] + 20 + i * (box["width"] - 40) / 40, box["y"] + box["height"] / 2)
        hs.append(round(pg.locator(".plot-head").first.bounding_box()["height"]))
    assert all(b >= a for a, b in zip(hs, hs[1:])), hs           # grows at most, never jumps back
    assert pg.locator(".plot-body .hover-t").count() == 1           # the time in the plot's corner
    # hidden: a button says how many and shows it again
    pg.evaluate("() => window.__sv.state().commit((ws) => { ws.tabs[0].plots[0].legend = 'off'; return ws; })")
    pg.locator(".legend-hidden").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].legend === undefined")


def test_made_signal_renamed_deleted_and_grouped_from_the_list(pg):
    open_files(pg, "run_a.csv")
    rid = S(pg, "s.runs[0].id")
    r = pg.evaluate("""async (rid) => { const r = await fetch('/api/derived', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({op: 'expr', sources: [rid + '/Speed'], params: {expr: '2*v0', text: '2*{Speed}'}, name: 'twice'})}); return r.status; }""", rid)
    assert r == 200
    pg.evaluate("""async () => { const r = await fetch('/api/derived', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({op: 'expr', sources: ['derived/twice'], params: {expr: 'v0+1', text: '{twice}+1'}, name: 'plus'})}); }""")
    pg.reload(); pg.wait_for_selector(".app")
    pg.wait_for_function("window.__sv.state().runs.some((r) => r.format === 'derived') && !!window.__sv.state().ws.tabs[0].plots[0]")
    pg.wait_for_timeout(800)                                       # the session put back first
    pg.evaluate("() => window.__sv.state().commit((ws) => { ws.tabs[0].plots[0].signals = [{sig: 'derived/twice', color: '#3D8BFD', width: 1.5, scale: 1, offset: 0}]; return ws; })")
    # rename: the plot follows
    sig(pg, "twice").click(button="right")
    menu_item(pg, "Rename")
    pg.locator(".dialog input").first.fill("doubled"); pg.keyboard.press("Enter")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals[0].sig === 'derived/doubled'")
    # a group, nested by its name
    sig(pg, "doubled").click(button="right")
    pg.locator(".menu.ctx button", has_text="Add to a group").first.hover()
    menu_item(pg, "New group")
    pg.locator(".dialog input").first.fill("Speeds/Made"); pg.keyboard.press("Enter")
    pg.wait_for_selector(".ugroups-head")
    assert [x.split("\n")[0] for x in pg.locator(".grp-head.ugroup").all_inner_texts()] == ["Speeds", "Made"]
    # delete with Del: what was made from it is asked about, both go, one Undo puts them back
    sig(pg, "doubled").focus(); pg.keyboard.press("Delete")
    pg.wait_for_selector(".dialog:has-text('plus')")
    pg.locator(".dialog-foot .btn").last.click()
    pg.wait_for_function("!window.__sv.state().runs.some((r) => r.format === 'derived' && r.signals.length)")
    assert S(pg, "s.ws.tabs[0].plots[0].signals.length") == 0
    pg.locator(".toast button:has-text('Undo')").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    assert S(pg, "s.runs.find((r) => r.format === 'derived').signals.map((x) => x.name).join()") == "doubled,plus"


def test_map_track_coloured_by_the_flight_mode(pg):
    src = os.path.join(ROOT, "examples", "copter_flight.bin")
    shutil.copy(src, os.path.join(pg.env["data"], "copter_flight.bin"))
    open_files(pg, "copter_flight.bin")
    rid = S(pg, "s.runs[0].id")
    obj = {"id": "o1", "name": "Copter", "kind": "drone", "color": "#E5677A", "lat": f"{rid}/GPS[0].Lat [deg]",
           "lon": f"{rid}/GPS[0].Lng [deg]", "trail": True, "trackColor": "state", "colorSig": f"{rid}/MODE.Mode"}
    pg.evaluate("""(o) => window.__sv.state().commit((ws) => { const p = ws.tabs[0].plots[0];
        p.mode = 'geo'; p.xSignal = o.lon; p.signals = [{sig: o.lat, color: '#3D8BFD', width: 1.5, scale: 1, offset: 0}]; p.objects = [o]; return ws; })""", obj)
    pg.wait_for_selector(".track-key", timeout=30000)
    txt = pg.locator(".track-key").inner_text()
    assert "MODE.Mode" in txt and "AUTO" in txt and "LOITER" in txt
    # the object's dialog: the choice and its signal
    pg.locator(".obj-chip-main").first.click()
    assert pg.locator(".obj-trackcolor select").input_value() == "state"


def test_fleet_example(pg):
    pg.click("[aria-label='Fleet']")
    pg.locator(".fleet-example .btn").click()
    pg.wait_for_selector(".fleet-trend circle", timeout=60000)
    pg.wait_for_function("document.querySelectorAll('.fleet-log').length === 1")   # vibration above 30: one flight
    assert "X8-A_2026-10-07" in pg.locator(".fleet-log").inner_text()
    assert pg.locator(".fleet-trend circle").count() == 10
    pg.fill(".fleet-search input[type=search]", "X8-A")
    pg.wait_for_function("document.querySelectorAll('.fleet-trend circle').length === 6")


def test_sweeps_runs_tab_pareto_and_clear(pg):
    pg.locator(".areas .area-btn", has_text="Sweeps").click()
    pg.locator(".sw-welcome .btn", has_text="Try an example").click()
    pg.wait_for_selector(".sw-steps")
    pg.locator(".sw-step-btn[data-step='goals']").click()
    pg.locator("select[aria-label='Optimize energy_wh']").select_option("min")
    pg.wait_for_selector("text=More than one to optimize?")
    pg.locator("select[aria-label='Optimize roll_error_deg']").select_option("min")
    pg.locator(".sw-rankby select").select_option("pareto")
    pg.wait_for_selector(".sw-optimize-now:has-text('Pareto front of')")
    pg.locator(".sw-rankby .btn").click()
    pg.wait_for_selector(".sw-pane select >> nth=0")
    assert pg.locator(".sw-pane").first.locator("select").first.input_value() == "pareto"
    tabs = pg.locator(".sw-center-tabs button").all_inner_texts()
    assert tabs[0] == "Parameter sets · 45" and tabs[1] == "All runs · 810"
    # Clear > everything: closed, the notice's Undo opens it again
    pg.locator(".sw-clear-btn").click()
    menu_item(pg, "Everything")
    pg.locator(".dialog-foot .btn").last.click()
    pg.wait_for_selector(".sw-welcome")
    pg.locator(".toast button:has-text('Undo')").click()
    pg.wait_for_selector(".sw-steps")
