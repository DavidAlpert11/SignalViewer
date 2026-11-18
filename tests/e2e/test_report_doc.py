"""RE1: the report written as a document - the Report button shows the editor in place of the plots; an old
session's report opens as the document its form made; [[tab.plot]] puts a plot in, {{ max(Speed) }} a value
computed on every sample; the preview, undo, a broken reference said, Add to report from a plot, the .html file.

    python -m pytest tests/e2e/test_report_doc.py -q
"""
import os
import sys

import numpy as np
import pytest

pw = pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, save_as, sig  # noqa: E402,F401

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
from svcore.docfields import format_value  # noqa: E402

SHOT = os.environ.get("SV_SHOTS")             # a folder: pictures of the screen for the owner (not needed by the test)


def speed_max():
    t = np.arange(0, 30, 0.01)
    f = 20 + 10 * np.tanh(t - 5) - 8 * np.tanh(t - 20)
    return float(np.max(np.array([float("%.6g" % v) for v in f])))   # as the CSV holds it


def write(pg, text):
    pg.locator(".rd-text").fill(text)
    pg.wait_for_function("t => (window.__sv.state().ws.report?.doc?.text || '') === t", arg=text, timeout=10000)   # committed after the pause


def preview_has(pg, *parts):
    try:
        pg.wait_for_function("ps => ps.every(p => (window.__sv.state().reportPreviewHtml || '').includes(p))", arg=list(parts), timeout=30000)
    except Exception:
        import re
        h = S(pg, "s.reportPreviewHtml") or ""
        print("DBG missing", [p for p in parts if p not in h], re.findall(r'<span class="(?:val|field-err)"[^<]*<', h)[:5], h.count('class="plot"'))
        raise


def test_write_a_report_with_a_plot_and_a_value(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    pg.evaluate("() => window.__sv.state().commit(ws => { ws.tabs[0].name = 'Drive'; ws.tabs[0].plots[0].title = 'Speed'; "
                "ws.report = { title: 'Old title', intro: 'Written before 1.31', summary: '', lang: 'en', theme: 'light', scope: 'tab' }; return ws; })")
    pg.locator(".rail button[aria-label='Report']").click()
    pg.wait_for_selector(".rd .rd-text")
    assert pg.locator(".plot").count() == 0                               # the report takes the stage
    text = pg.locator(".rd-text").input_value()
    assert text.startswith("# Old title\n\nWritten before 1.31\n\n[[process]]") and "[[Drive]]" in text
    assert S(pg, "s.ws.report.doc") is None                               # an old session is not changed by opening it
    preview_has(pg, "Old title", "Written before 1.31", 'class="plot"')

    want = format_value(speed_max())
    write(pg, "# Drive test\n\nTop speed **{{ max(Speed) }}** at {{ tmax(Speed) :.1f }} s.\n\n[[Drive.Speed | 0..30]]\n\n- one\n- two\n\n$v = \\frac{d}{t}$")
    preview_has(pg, f">{want}<", "<strong>", "<li", '<svg class="math"', 'class="plot"')
    if SHOT:
        pg.screenshot(path=os.path.join(SHOT, "report_screen.png"))

    # undo: one step back to the document before
    pg.locator(".rd-text").press("Tab")                                   # leave the editor (the editor's own undo stays the browser's)
    pg.evaluate("() => window.__sv.state().undo()")
    pg.wait_for_function("!window.__sv.state().ws.report.doc")               # back to the report its old form made
    pg.wait_for_function("document.querySelector('.rd-text').value.includes('[[process]]')")
    pg.evaluate("() => window.__sv.state().redo()")
    pg.wait_for_function("document.querySelector('.rd-text').value.includes('max(Speed)')")

    # a reference that cannot be filled is said - in the preview and in the head
    write(pg, "# Drive test\n\n[[Nope]] and {{ max(Nothing) }}")
    preview_has(pg, "field-err", "Nope")
    pg.wait_for_selector(".rd-problems")

    # the .html file is the page the preview showed
    write(pg, "# Drive test\n\nTop speed {{ max(Speed) }}.\n\n[[Drive.Speed]]")
    pg.locator(".replay-make").click()
    save_as(pg, "drive.html")
    path = os.path.join(pg.env["out"], "drive.html")
    for _ in range(100):
        if os.path.exists(path):
            break
        pg.wait_for_timeout(200)
    page = open(path, encoding="utf-8").read()
    assert f">{want}<" in page and "<title>Drive test</title>" in page and 'class="plot"' in page


def test_add_to_report_from_a_plot_and_back(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "RPM").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    pg.evaluate("() => window.__sv.state().commit(ws => { ws.tabs[0].plots[0].title = 'Engine'; return ws; })")
    pg.locator(".plot-more").first.click()
    pg.locator(".menu.ctx button", has_text="Add to report").click()
    pg.wait_for_function("(window.__sv.state().ws.report?.doc?.text || '').trimEnd().endsWith('.Engine]]')")
    pg.locator(".toast button", has_text="Report").click()                 # the toast's way to the report
    pg.wait_for_selector(".rd .rd-text")
    assert pg.locator(".rd-text").input_value().rstrip().endswith(".Engine]]")
    # the value form writes a value by name
    pg.locator(".rd-value-sig").fill("RPM")
    pg.locator(".rd-value-stat").select_option("mean")
    pg.locator(".rd-text").click()
    pg.locator(".rd-text").press("Control+End")
    pg.locator(".rd-value-insert").click()
    pg.wait_for_function("document.querySelector('.rd-text').value.includes('{{ mean(RPM) }}')")
    pg.locator(".rail button[aria-label='Report']").click()                # the same button goes back to the plots
    pg.wait_for_selector(".plot")
