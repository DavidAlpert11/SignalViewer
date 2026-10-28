"""Investigation step 6: findings (a status and the view they were found in), the journal of steps,
and the report's investigation sections.

    python -m pytest tests/e2e/test_findings_report.py -q
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_conditions import _new, _panel  # noqa: E402
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401


def _note(pg, text, t1, t2):
    pg.evaluate(f"window.__sv.setState({{ cursor: {{ on: true, dual: true, t1: {t1}, t2: {t2}, active: 1 }} }})")
    pg.keyboard.press("n")
    pg.locator(".dialog textarea, .dialog input").first.fill(text)
    pg.locator(".dialog .btn.primary").click()
    pg.wait_for_function(f"(window.__sv.state().ws.notes || []).some(n => n.text === '{text}')")


def test_a_finding_keeps_its_view_and_goes_back_to_it(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")
    _note(pg, "speed holds", 8, 16)
    pg.evaluate("window.__sv.setState({ inspectorOpen: true })")
    pg.locator(".notes-list li", has_text="speed holds").locator(".note-status").select_option("fault")
    pg.wait_for_function("window.__sv.state().ws.notes[0].status === 'fault' && !!window.__sv.state().ws.notes[0].view")
    v = S(pg, "s.ws.notes[0].view")
    assert v["t1"] == 8 and v["t2"] == 16
    assert S(pg, "s.journal.length") == 1 and "speed holds" in S(pg, "s.journal[0].text")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: false } })")
    pg.locator(".notes-list li", has_text="speed holds").locator(".note-view").click()
    pg.wait_for_function("window.__sv.state().cursor.on && window.__sv.state().cursor.t2 === 16")


def test_journal_and_report_sections(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")
    _panel(pg)
    _new(pg, "Fast", "Speed > 30")
    pg.click(".cond-save")
    pg.wait_for_function("window.__sv.state().journal.some(j => j.text.includes('Fast') && j.text.includes('1 stretch'))")
    pg.locator(".jr-toggle").click()
    assert "Fast" in pg.inner_text(".jr-list")
    _note(pg, "an idea", 2, 4)
    pg.evaluate("window.__sv.setState({ inspectorOpen: true })")
    pg.locator(".notes-list li", has_text="an idea").locator(".note-status").select_option("rejected")
    _note(pg, "the cause", 6, 20)
    pg.locator(".notes-list li", has_text="the cause").locator(".note-status").select_option("open")
    pg.click("nav.rail button[aria-label='Report']")
    pg.wait_for_selector(".report-investigation")
    assert pg.is_checked(".report-investigation")
    pg.click(".side .btn:has-text('Preview')")
    pg.wait_for_function("(window.__sv.state().reportPreviewHtml || '').length > 1000")
    html = S(pg, "s.reportPreviewHtml")
    for part in ("Findings", "the cause", "Hypotheses checked and rejected", "an idea", "Analysis steps", "How to reproduce", "Speed &gt; 30"):
        assert part in html, part
    pg.evaluate("window.__sv.setState({ reportPreviewHtml: null })")          # the preview covers the panel
    pg.locator(".report-investigation").uncheck()
    pg.click(".side .btn:has-text('Preview')")
    pg.wait_for_function("(window.__sv.state().reportPreviewHtml || '').length > 1000 && !window.__sv.state().reportPreviewHtml.includes('How to reproduce')")
