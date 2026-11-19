"""RE2: the report's ready-made parts - the library beside the text shows what the open files have (commanded /
measured pairs, objects with the guessed reference, states, files to compare), a ready report is one click and is
made of parts, each part one click; a table pasted from Word and a picture go into the text and stay in the
session; a report kept as the user's own template comes back. On the demo recordings (examples/report_demo).

    python -m pytest tests/e2e/test_report_parts.py -q
"""
import base64
import os
import shutil

import pytest

pw = pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg  # noqa: E402,F401
from test_report_doc import preview_has  # noqa: E402

DEMO = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "report_demo")
SHOT = os.environ.get("SV_SHOTS")             # a folder: pictures of the screen for the owner (not needed by the test)
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP4z8DAwMDAwMDAwMDAAAANBAEAv0WzLwAAAABJRU5ErkJggg==")


def shot(pg, name):
    if SHOT:
        os.makedirs(SHOT, exist_ok=True)
        pg.screenshot(path=os.path.join(SHOT, name))


def committed(pg, *parts, timeout=15000):
    pg.wait_for_function("ps => ps.every(p => (window.__sv.state().ws.report?.doc?.text || '').includes(p))", arg=list(parts), timeout=timeout)


@pytest.fixture()
def demo(pg):
    for f in ("mission_ref.csv", "mission_gust.csv"):
        shutil.copy(os.path.join(DEMO, f), os.path.join(pg.env["data"], f))
    open_files(pg, "mission_ref.csv", "mission_gust.csv")
    pg.locator(".rail button[aria-label='Report']").click()
    pg.wait_for_selector(".rd-parts .rd-cat-tracking")
    return pg


def test_a_ready_report_made_of_parts(demo):
    pg = demo
    lib = pg.locator(".rd-parts")
    assert "8 pairs found" in lib.locator(".rd-cat-tracking summary").inner_text()
    assert "6 objects" in lib.locator(".rd-cat-navigation summary").inner_text()
    assert "2 files open" in lib.locator(".rd-cat-compare summary").inner_text()
    ref = lib.locator(".rd-cat-navigation select")
    assert "guessed" in ref.locator("option:checked").inner_text()          # the truth guessed as the reference
    lib.locator(".rd-ready .rd-lib-item", has_text="Automatic report").click()
    committed(pg, "[[summary]]", "[[tracking]]", "[[navigation]]", "[[states]]", "[[moments]]", "[[differences]]")
    preview_has(pg, "What to look at", "commanded / measured pairs", "Navigation errors against", "mission.phase",
                "The central region of the change: 141.0", "First to diverge", 'class="plot')
    shot(pg, "re2_ready_report.png")
    # a part at the caret: one pair's tracking, after the title
    ed = pg.locator(".rd-text")
    ed.click()
    pg.evaluate("() => { const e = document.querySelector('.rd-text'); const i = e.value.indexOf('\\n') + 1; e.setSelectionRange(i, i); }")
    lib.locator(".rd-cat-tracking .rd-lib-item", has_text="ctrl.roll [deg] ← ").click()
    committed(pg, "[[tracking ctrl.roll | top 1]]")
    # the baseline changed: the part is written with it
    lib.locator(".rd-cat-compare select").select_option("mission_gust.csv")
    lib.locator(".rd-cat-compare .rd-lib-item", has_text="tables only").click()
    committed(pg, "[[differences | base mission_gust.csv, table]]")


def test_paste_a_word_table_and_a_picture_and_keep_a_report_template(demo):
    pg = demo
    pg.locator(".rd-text").fill("# Bench\n\n")
    pg.locator(".rd-text").click()
    pg.keyboard.press("Control+End")
    # what Word puts on the clipboard: a table with a merged cell and Hebrew
    html = ("<html><body><p class=MsoNormal><b>Results</b></p><table><tr><td><b>Run</b></td><td>תוצאה</td><td>Max</td></tr>"
            "<tr><td rowspan=2>A</td><td>עבר</td><td>12.5</td></tr><tr><td>נכשל</td><td>9</td></tr></table></body></html>")
    pg.evaluate("""h => { const dt = new DataTransfer(); dt.setData('text/html', h); dt.setData('text/plain', 'Run תוצאה Max');
        document.querySelector('.rd-text').dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })); }""", html)
    committed(pg, "**Results**", "| **Run** | תוצאה | Max |", "| A | עבר | 12.5 |", "| A | נכשל | 9 |")
    # a picture from a file: kept in the session, written asset:<id>, drawn in the page
    pg.locator(".rd-editor input[type=file]").set_input_files({"name": "rig.png", "mimeType": "image/png", "buffer": PNG})
    pg.wait_for_function("() => Object.keys(window.__sv.state().ws.report?.assets || {}).length === 1", timeout=10000)
    committed(pg, "![rig](asset:")
    preview_has(pg, "data:image/png;base64,", "<table")
    shot(pg, "re2_paste.png")
    # the user's own report template, offered again
    pg.locator(".rd-save-mine").click()
    pg.locator(".dialog input").fill("Bench report")
    pg.locator(".dialog .btn.primary").click()
    pg.wait_for_selector(".rd-mine .rd-lib-item:has-text('Bench report')")
    assert S(pg, "s.ws.report.assets") and len(S(pg, "Object.keys(s.ws.report.assets)")) == 1
