"""D7: one Checks view for any file (limits, data quality, a log's health check as tinted cards under one
verdict), F1 The file (the structure, values at the cursor, click to plot) and F3 a run's parameters with
two runs compared - on CSV files, no flight log needed."""
import os

import numpy as np
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg  # noqa: E402,F401


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
