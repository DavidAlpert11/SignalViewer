"""
26.U4: "judge a run" as the main flow - a golden run marked in Compare (with its tolerance), a
recording opened later is offered to be judged against it; Compare says pass / fail per file and
shows the worst failure; "Report…" makes a tab of the failing signals and a report with the verdict.
"""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_template_tabs import pg  # noqa: E402,F401
from test_features import clear_everything, goto_folder  # noqa: E402


def test_golden_run_proposed_judged_and_reported(pg):
    pg.locator(".examples-line button", has_text="three car runs").click()
    pg.wait_for_function("document.querySelectorAll('.run-head').length === 3")
    pg.click("[aria-label='Compare runs']")
    pg.wait_for_selector(".sim-row", timeout=30000)
    verdict = pg.locator(".judge-verdict")
    assert "Set a tolerance" in verdict.inner_text()                    # a baseline file, no tolerance yet
    verdict.locator("button", has_text="Set a tolerance").click()
    pg.locator(".cmp-panel > .tol-fields .afield", has_text="Tolerance (±)").locator("input").fill("2")
    pg.wait_for_selector(".judge-verdict li", timeout=30000)
    assert verdict.locator("li").count() == 2 and "run_012.csv" in verdict.locator("h3").inner_text()
    assert verdict.locator("li.fail").count() >= 1 and "outside the tolerance" in verdict.inner_text()
    # the worst failure: its comparison with the difference over time
    verdict.locator("button", has_text="Show the worst failure").click()
    pg.wait_for_selector(".diff-chart", timeout=20000)
    # mark the baseline as a golden run (with this tolerance)
    pg.locator(".golden-mark input").check()
    pg.wait_for_function("(window.__sv.state().toasts || []).some(t => t.text.includes('golden run'))")
    # Report…: a tab of the failing signals, the report panel with the verdict
    verdict.locator("button", has_text="Report…").click()
    pg.wait_for_selector(".rverdict input:checked")
    tab = pg.evaluate("(() => { const ws = window.__sv.state().ws; return ws.tabs.find(t => t.id === ws.activeTab); })()")
    assert tab["name"].startswith("Verdict") and len(tab["plots"]) >= 1 and all(len(p["signals"]) == 3 for p in tab["plots"])
    v = pg.evaluate("window.__sv.state().ws.report.verdict")
    assert v["title"] == "Against run_012.csv" and len(v["head"]) == 4 and any(c.startswith("✗") for r in v["rows"] for c in r[2:])
    pg.locator(".side button", has_text="Preview").click()
    pg.wait_for_function("(window.__sv.state().reportPreviewHtml || '').includes('Against run_012.csv')", timeout=30000)
    pg.evaluate("window.__sv.setState({ reportPreviewHtml: null })")

    # later: only a new recording is open - the app offers its golden run
    folder = os.path.dirname(pg.evaluate("window.__sv.state().runs.find(r => r.name === 'run_014.csv').path"))
    clear_everything(pg)
    pg.wait_for_function("window.__sv.state().runs.filter(r => r.format !== 'derived').length === 0")
    pg.keyboard.press("Control+o")
    goto_folder(pg, folder)
    pg.locator(".dialog .dialog-body .fs-row", has_text="run_014.csv").first.click()
    pg.click(".dialog-foot .btn.primary")
    card = pg.locator(".start-judge")
    card.wait_for(timeout=30000)
    assert "Judge it against run_012.csv" in card.inner_text()
    card.locator("button", has_text="Judge it").click()
    pg.wait_for_selector(".judge-verdict li", timeout=30000)
    assert pg.evaluate("window.__sv.state().compareTol.default.abs") == 2            # its tolerance came with it
    li = pg.locator(".judge-verdict li")
    assert li.count() == 1 and "run_014.csv" in li.inner_text()
    assert "★" in pg.locator(".cmp-panel select").first.inner_text()                 # the golden run, marked
