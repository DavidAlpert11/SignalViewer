"""D7: one Checks view for any file (limits, data quality, a log's health check as tinted cards under one
verdict), F1 The file (the structure, values at the cursor, click to plot) and F3 a run's parameters with
two runs compared - on CSV files, no flight log needed."""
import os

import numpy as np
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_example, open_files, pg  # noqa: E402,F401


def _write(d, name, gain, gap=False):
    t = np.arange(0, 20, 0.05)
    if gap:
        t = t[(t < 8) | (t > 11)]
    cols = np.column_stack([t, np.full_like(t, gain), np.sin(t) * 10, np.cos(t)])
    np.savetxt(os.path.join(d, name), cols, delimiter=",", header="Time,Gain,Engine_rpm [1/min],Engine_temp", comments="", fmt="%.6g")


def test_checks_file_and_parameters_for_csv_runs(pg):
    _write(pg.env["data"], "bench_run_1.csv", 0.5, gap=True)
    _write(pg.env["data"], "bench_run_2.csv", 0.8)
    open_files(pg, "bench_run_1.csv", "bench_run_2.csv")
    rid = S(pg, "s.runs.find(r => r.name.includes('bench_run_1')).id")
    # a limit on a plotted signal of run 1: it fails (sin * 10 leaves -5 … 5)
    pg.evaluate(f"""window.__sv.state().commit((ws) => {{ const t = ws.tabs.find(x => x.id === ws.activeTab);
        t.plots[0].signals = [{{ sig: '{rid}/Engine_rpm [1/min]', color: '#888', width: 1.5, scale: 1, offset: 0, limits: {{ lo: -5, hi: 5 }} }}];
        return ws; }})""")
    pg.locator(".rail button[aria-label='Checks']").click()
    panel = pg.locator("aside.log-panel")
    panel.locator("select").first.select_option(rid)
    pg.wait_for_selector("aside.log-panel .checks[data-checks-ready='1']", timeout=20000)
    # the verdict first; a failed limit is a red card, the gap a data-quality card
    assert panel.locator("[data-testid=checks-verdict]").inner_text().startswith("1 failed")
    lim = panel.locator(".card.bad[data-limit='Engine_rpm [1/min]']")
    assert "outside -5 … 5" in lim.inner_text()
    assert panel.locator(".card.warn[data-quality]").count() >= 1
    lim.locator(".pchange.span").first.click()                                  # a span: shown whole
    pg.wait_for_function("window.__sv.state().cursor.on")
    # The file: the Engine group (a column prefix), its gap, its columns with units; a click plots one
    panel.locator(".log-tabs [data-tab=file]").click()
    eng = panel.locator("tr.fv-group[data-group='Engine']")
    eng.wait_for()
    assert "⚠" in eng.inner_text()                                             # the 3 s hole
    eng.locator("button").click()
    col = panel.locator("tr.fv-col[data-column='Engine_temp']")
    assert col.count() == 1
    n0 = S(pg, "s.ws.tabs.find(x => x.id === s.ws.activeTab).plots.flatMap(p => p.signals).length")
    col.locator("button").click()
    pg.wait_for_function(f"window.__sv.state().ws.tabs.find(x => x.id === window.__sv.state().ws.activeTab).plots.flatMap(p => p.signals).length > {n0}")
    # values at the cursor
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, t1: 1.0 } })")
    pg.wait_for_function("document.querySelector(\"tr.fv-col[data-column='Engine_temp'] td:last-child\").textContent.trim() !== ''")
    # Parameters: Gain is constant (0.5), run is a file-name number; compared with run 2 only they differ
    panel.locator(".log-tabs [data-tab=params]").click()
    pg.wait_for_selector("aside.log-panel tr[data-param='Gain']")
    assert "0.5" in panel.locator("tr[data-param='Gain']").inner_text()
    panel.locator(".runparams select").select_option(index=1)
    pg.wait_for_selector("aside.log-panel tr[data-diff='Gain']")
    assert panel.locator("tr[data-diff]").count() == 2                          # Gain and run - nothing equal listed
    assert "0.8" in panel.locator("tr[data-diff='Gain']").inner_text()


def test_the_checks_file_beside_a_recording_gives_the_verdict(pg):
    """RV2 (review 2026-11-16): the pump read "Checks: 0 failed" while its checks.json fails 2 of 4 in CI. The
    checks file beside a recording now runs in the window; with nothing checked the pill says so."""
    import json, shutil
    d = pg.env["data"]
    shutil.copy(os.path.join(os.path.dirname(__file__), "..", "..", "examples", "bench", "pump_run_07.parquet"), os.path.join(d, "pump.parquet"))
    with open(os.path.join(d, "pump.checks.json"), "w") as fh:
        json.dump({"checks": [{"name": "Temp below 85", "signal": "MotorTemp", "hi": 85}, {"signal": "Vibration", "hi": 0.5}]}, fh)
    _write(d, "plain_run.csv", 0.5, gap=True)
    open_files(pg, "plain_run.csv")
    pg.wait_for_selector(".ov-head .ov-checks")
    assert pg.locator(".ov-head .ov-checks").inner_text().startswith("Checks: no limits set")   # not "0 failed"
    open_files(pg, "pump.parquet")
    rid = S(pg, "s.runs.find(r => r.name === 'pump.parquet').id")
    pg.locator(".rail button[aria-label='Checks']").click()
    panel = pg.locator("aside.log-panel")
    panel.locator("select").first.select_option(rid)
    pg.wait_for_selector("aside.log-panel .checks[data-checks-ready='1']", timeout=20000)
    assert panel.locator("[data-testid=checks-verdict]").inner_text().startswith("1 failed")
    sec = panel.locator("[data-checks-file='pump.checks.json']")
    assert sec.locator(".card.bad[data-check='Temp below 85']").count() == 1
    assert sec.locator(".card.ok[data-status=pass]").count() == 1
    sec.locator(".card.bad .pchange.span").click()                                # to the worst moment
    pg.wait_for_function("Math.abs(window.__sv.state().cursor.t1 - 559.74) < 0.5")


def test_checks_as_a_page_and_back_beside_the_plots(pg):
    """UX5.2: Checks in the one frame - beside the plots by default; its ⤢ makes it a page (the file and its sections in
    the index column, the section in the main one), remembered; a click on an event brings the plots back beside it."""
    _write(pg.env["data"], "bench_run_1.csv", 0.5, gap=True)
    open_files(pg, "bench_run_1.csv")
    pg.locator(".rail button[aria-label='Checks']").click()
    pg.wait_for_selector("aside.log-panel .log-tabs")
    pg.locator("aside.log-panel .panel-fill").click()
    pg.wait_for_selector(".page.log-panel .page-index .log-tabs.vertical")
    pg.wait_for_selector(".page.log-panel .page-main .checks[data-checks-ready='1']", timeout=20000)
    assert pg.locator(".stage .plot").count() == 0                          # the page is in the plots' place
    pg.locator(".page.log-panel .log-tabs button[data-tab='file']").click()
    pg.wait_for_selector(".page.log-panel .page-main .checks[data-checks-ready='1']", state="detached")
    assert S(pg, "s.panelFull.log") is True
    pg.locator(".page-head .panel-fill").click()                            # beside the plots again
    pg.wait_for_selector("aside.log-panel")


def test_no_green_verdict_when_nothing_was_judged(pg):
    """Review 2026-11-25 (C1): with no limits, no checks file and no health check the verdict was the green "Nothing
    outside its limits" - above a motor the app itself flagged flat at its limit. Now: grey "nothing judged" for a
    clean file; the automatic flags counted and listed when there are some."""
    import shutil
    d = pg.env["data"]
    _write(d, "clean_run.csv", 0.5)
    shutil.copy(os.path.join(os.path.dirname(__file__), "..", "..", "examples", "investigate", "heavy_payload.csv"), os.path.join(d, "heavy.csv"))
    open_files(pg, "clean_run.csv", "heavy.csv")
    pg.locator(".rail button[aria-label='Checks']").click()
    panel = pg.locator("aside.log-panel")
    for name, tone in (("clean_run.csv", "none"), ("heavy.csv", "warning")):
        rid = S(pg, f"s.runs.find(r => r.name === '{name}').id")
        panel.locator("select").first.select_option(rid)
        pg.wait_for_function(f"(() => {{ const c = document.querySelector('aside.log-panel .checks[data-checks-ready=\"1\"]'); "
                             f"return c && document.querySelector('aside.log-panel [data-testid=checks-verdict]')?.dataset.tone === '{tone}'; }})()",
                             timeout=20000)
        verdict = panel.locator("[data-testid=checks-verdict]").inner_text()
        assert "Nothing outside its limits" not in verdict
    # CC12: heavy.csv's DesRoll / Roll pair is judged by the "any data" profile (its tracking, 30 % of the range)
    assert "automatic flag" in verdict and "to look at" in verdict
    assert "any" in panel.locator("[data-profiles]").get_attribute("data-profiles")
    assert panel.locator(".health-list .hrow.warning", has_text="Roll stays away from DesRoll").count() == 1
    flag = panel.locator(".card.warn[data-flag=saturated][data-flag-signal^='Motor3']")
    assert flag.count() >= 1 and "flat at its limit" in flag.first.inner_text()
    flag.first.locator(".pchange.span").click()                                   # to its moment
    pg.wait_for_function("window.__sv.state().cursor.on && window.__sv.state().cursor.t1 > 1")


def test_a_logs_own_findings_come_before_the_automatic_flags(pg):
    """Review 2026-11-25 (R1, round 2): on the ArduPilot example 19 automatic-flag cards ("a glitch?") came before the
    health check's 3 findings. With a health check (or a checks file) the flags come after it, three shown and "+N
    more"; the strip's chip counts the same parts as the panel."""
    open_example(pg, "ardupilot")
    pg.wait_for_function("window.__sv.state().runs.some(r => r.log)", timeout=60000)
    pg.locator(".rail button[aria-label='Checks']").click()
    pg.wait_for_selector("aside.log-panel .checks[data-checks-ready='1'], .page.log-panel .checks[data-checks-ready='1']", timeout=60000)
    checks = pg.locator(".checks[data-checks-ready='1']").first
    assert checks.get_attribute("data-flags-last") == "1"
    n = int(checks.get_attribute("data-flags"))
    order = checks.locator("section.checks-sec").evaluate_all("xs => xs.map(x => x.getAttribute('aria-label'))")
    assert order.index("Health check") < order.index("Automatic flags"), order
    assert checks.locator(".card[data-flag]").count() == min(3, n)
    if n > 3:
        assert f"+{n - 3} more" in checks.inner_text()
    verdict = pg.inner_text("[data-testid=checks-verdict]")
    pg.evaluate("window.__sv.setState({ demoGuide: null, panel: 'data' })")      # the strip's head, not the demo's line
    chip = pg.locator(".ov-head .ov-checks")
    chip.wait_for()
    assert f"{n} automatic flags" in chip.inner_text() and f"{n} automatic flags" in verdict
