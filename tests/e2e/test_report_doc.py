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


def test_clear_and_the_report(pg):
    """CLR1: Clear > All tabs says when the written report pointed at them (and clears it too on request); Clear >
    The report empties only the report (one Undo); the Report screen's reset menu has Empty."""
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    pg.evaluate("() => window.__sv.state().commit(ws => { ws.tabs[0].name = 'Drive'; ws.tabs[0].plots[0].title = 'Speed'; "
                "ws.report = { title: 'T', intro: '', summary: '', lang: 'en', theme: 'light', scope: 'tab', "
                "doc: { v: 1, text: '# Drive test\\n\\n[[Drive]]\\n\\n[[Drive.Speed]]\\n\\n[[toc]]' } }; return ws; })")

    def pick(text):
        pg.click(".area-tools [aria-label='Clear']")
        pg.locator(".menu.ctx button", has_text=text).click()

    # all tabs: the toast says the report's 2 references are gone, and offers to clear the report too
    pick("All tabs (1)")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 0")
    toast = pg.locator(".toast", has_text="refers to 2 plots or tabs")
    toast.wait_for()
    toast.locator("button", has_text="Clear the report too").click()
    pg.wait_for_function("window.__sv.state().ws.report.doc.text === ''")
    assert S(pg, "s.ws.report.title") == "T"                                 # its settings stay
    pg.evaluate("() => window.__sv.state().undo()")
    pg.wait_for_function("window.__sv.state().ws.report.doc.text.includes('[[Drive]]')")

    # the Clear menu's "The report": asks (it has text), empties, one Undo brings it back; the tabs are untouched
    pg.evaluate("() => window.__sv.state().undo()")                          # the tabs back too
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    pick("The report")
    pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function("window.__sv.state().ws.report.doc.text === ''")
    assert S(pg, "s.ws.tabs[0].plots[0].signals.length") == 1
    pg.locator(".toast button", has_text="Undo").click()
    pg.wait_for_function("window.__sv.state().ws.report.doc.text.includes('[[Drive]]')")

    # the Report screen: ↺ > Empty
    pg.locator(".rail button[aria-label='Report']").click()
    pg.wait_for_selector(".rd .rd-text")
    pg.locator(".rd-reset").click()
    pg.locator(".menu.ctx button", has_text="Empty").click()
    pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function("window.__sv.state().ws.report.doc.text === '' && document.querySelector('.rd-text').value === ''")
    # ↺ > Back to the report made from the open tabs
    pg.locator(".rd-reset").click()
    pg.locator(".menu.ctx button", has_text="Back to the report").click()
    pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function("document.querySelector('.rd-text').value.includes('[[Drive]]')")


def test_latex_report_written_in_latex_typeset_offline(pg):
    """RE3: Written in -> LaTeX converts the report (its [[plots]] and {{values}} kept); the preview is the PDF this
    computer's LaTeX made; an error points to the line of the text; the LaTeX project (.zip) and the PDF (LaTeX)."""
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    pg.evaluate("() => window.__sv.state().commit(ws => { ws.tabs[0].name = 'Drive'; ws.tabs[0].plots[0].title = 'Speed'; return ws; })")
    pg.locator(".rail button[aria-label='Report']").click()
    pg.wait_for_selector(".rd .rd-text")
    write(pg, "# Drive test\n\nTop speed **{{ max(Speed) }}**.\n\n[[Drive.Speed]]\n\n```latex\n\\begin{align} v &= d/t \\end{align}\n```\n")
    from svcore import latex as TX
    if TX.status()["snippets"]:                     # a ```latex block drawn by TeX in the page (the computer's TeX only:
        preview_has(pg, 'class="math tex')          # the built-in Tectonic typesets documents, not snippets - RE4)
    pg.locator(".rd-format").select_option("tex")
    pg.wait_for_function("(window.__sv.state().ws.report?.doc?.text || '').startsWith('% Made by Signal Viewer')", timeout=15000)
    text = S(pg, "s.ws.report.doc.text")
    assert "\\begin{document}" in text and "{{ max(Speed) }}" in text and "[[Drive.Speed]]" in text and "\\begin{align}" in text
    try:
        pg.wait_for_selector(".rd-pdf-frame", timeout=60000)
    except Exception:
        print("DBG", pg.locator(".rd-preview").inner_text()[:800])
        raise
    assert "/api/report/tex/pdf/" in pg.locator(".rd-pdf-frame").get_attribute("src")
    if SHOT:
        pg.screenshot(path=os.path.join(SHOT, "report_latex.png"))
    # an error: said at its line, a click selects it in the text
    write(pg, text.replace("\\end{document}", "\\textbf{oops\n\\end{document}"))
    pg.wait_for_selector(".rd-tex-err", timeout=60000)
    assert "Line" in pg.locator(".rd-tex-err").inner_text()
    pg.locator(".rd-tex-err .linklike").click()
    assert "oops" in pg.evaluate("() => { const e = document.querySelector('.rd-text'); return e.value.slice(e.selectionStart, e.selectionEnd); }")
    write(pg, text)
    pg.wait_for_function("!document.querySelector('.rd-tex-err')", timeout=60000)
    # the project for Overleaf, and the PDF typeset here
    pg.locator(".rd-texzip").click()
    save_as(pg, "drive.zip")
    pg.locator(".rd-texpdf").click()
    save_as(pg, "drive.pdf")
    import zipfile
    for name in ("drive.zip", "drive.pdf"):
        path = os.path.join(pg.env["out"], name)
        for _ in range(300):
            if os.path.exists(path) and os.path.getsize(path) > 0:
                break
            pg.wait_for_timeout(200)
    with zipfile.ZipFile(os.path.join(pg.env["out"], "drive.zip")) as z:
        assert "main.tex" in z.namelist() and any(n.startswith("figures/plot-") for n in z.namelist())
        assert "\\includegraphics" in z.read("main.tex").decode("utf-8")
    assert open(os.path.join(pg.env["out"], "drive.pdf"), "rb").read(5) == b"%PDF-"


def test_editor_undo_a_comment_and_line_keys(pg):
    """RE4 (owner, 2026-11-23): Ctrl+Z in the report undoes a run of typing at once (not letter by letter) and what the
    app put in (bold); Ctrl+Y brings it back; Ctrl+/ makes the lines a comment, left out of the report, and back."""
    open_files(pg, "run_a.csv")
    pg.locator(".rail button[aria-label='Report']").click()
    ta = pg.locator(".rd-text")
    ta.wait_for()
    write(pg, "# Title\n\nfirst line\nsecond line")
    ta.click()
    pg.keyboard.press("Control+End")
    pg.keyboard.type(" and more words")
    pg.keyboard.press("Control+z")
    assert ta.input_value() == "# Title\n\nfirst line\nsecond line"            # the whole run of typing at once
    pg.keyboard.press("Control+y")
    assert ta.input_value().endswith("second line and more words")
    pg.keyboard.press("Control+b")
    assert ta.input_value().endswith("words****")
    pg.keyboard.press("Control+z")
    assert ta.input_value().endswith("words")
    # Ctrl+/ on the line with the caret: a comment, not in the preview; again: text
    pg.keyboard.press("Control+z")
    pg.keyboard.press("Control+/")
    pg.wait_for_function("(window.__sv.state().ws.report?.doc?.text || '').includes('<!-- second line -->')", timeout=10000)
    preview_has(pg, "first line")
    assert "second line" not in (S(pg, "s.reportPreviewHtml") or "")
    pg.keyboard.press("Control+/")
    assert ta.input_value() == "# Title\n\nfirst line\nsecond line"
    pg.keyboard.press("Alt+ArrowUp")                                         # the line moves up
    assert ta.input_value() == "# Title\n\nsecond line\nfirst line"
