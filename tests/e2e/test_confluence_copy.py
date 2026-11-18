"""CP1 (owner, 2026-11-18): Copy for Confluence. The plot's menu puts two flavours on the clipboard: text/plain is
the interactive page for Confluence's HTML macro, text/html the picture + statistics + notes for a straight paste.
Here the macro is stood in for by a page that holds the copied HTML as it is (what the macro renders): the plot is
drawn in its frame, zooms, its lines go on and off - twice on one page without the two meeting. A straight paste
into an editor (contenteditable) gets the picture and the table, no script."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, open_files, pg, sig  # noqa: E402,F401


def _copy(pg, label="Copy for Confluence"):
    pg.locator(".plot-more").first.click()
    pg.locator(".menu.ctx button", has_text=label).first.click()
    pg.wait_for_selector(".toast:has-text('Copied (')", timeout=20000)


def test_copy_for_confluence_is_interactive_in_the_macro_and_static_when_pasted(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.evaluate("window.__sv.setState(s => ({ ws: { ...s.ws, notes: [{ id: 'n1', t: 5, text: 'gear change' }] } }))")
    _copy(pg)
    toast = pg.locator(".toast").last.inner_text()
    kb = float(toast.split("Copied (")[1].split(" ")[0])
    assert kb < 400, toast                                       # small: a 4 MB page brought his editor down
    text = pg.evaluate("navigator.clipboard.readText()")
    rich = pg.evaluate("""async () => { const it = (await navigator.clipboard.read())[0];
        return await (await it.getType('text/html')).text(); }""")
    assert text.startswith('<div class="sv-clip"><iframe') and "<script>" in text
    assert "<script" not in rich and "data:image/png;base64," in rich and "gear change" in rich and "Speed" in rich

    # the HTML macro: the copied HTML as it is, twice on one page among the page's own content
    ctx = pg.context
    page = ctx.new_page()
    page.set_content('<html><body><h1 id="own">Confluence page</h1><div class="m1">%s</div><p>between</p><div class="m2">%s</div></body></html>' % (text, text))
    frames = page.locator("iframe")
    assert frames.count() == 2
    page.wait_for_function("""() => [...document.querySelectorAll('iframe')].every(f => f.contentDocument
        && f.contentDocument.querySelector('.canvas canvas') && f.getBoundingClientRect().height > 300)""", timeout=15000)
    assert page.evaluate("getComputedStyle(document.getElementById('own')).fontSize") == "32px"   # the page's own styles untouched
    f1 = page.frame_locator(".m1 iframe")
    assert "gear change" in f1.locator("body").inner_text() and "Max" in f1.locator("table").inner_text()
    # lines on and off: the legend chip in the first copy only
    chip = f1.locator(".legend .chip").first
    chip.click()
    assert "off" in (chip.get_attribute("class") or "")
    assert "off" not in (page.frame_locator(".m2 iframe").locator(".legend .chip").first.get_attribute("class") or "")
    # zoom: a drag across the plot redraws it on the narrower range; a double-click leaves the zoom
    canvas = f1.locator(".canvas canvas").first
    page.mouse.move(0, 0)
    whole = canvas.screenshot()
    box = f1.locator(".canvas .u-over").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] / 2)
    page.mouse.down(); page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2, steps=8); page.mouse.up()
    page.mouse.move(0, 0)
    page.wait_for_timeout(400)
    zoomed = canvas.screenshot()
    assert zoomed != whole
    page.mouse.dblclick(box["x"] + box["width"] * 0.4, box["y"] + box["height"] / 2)
    page.mouse.move(0, 0)
    page.wait_for_timeout(400)
    assert canvas.screenshot() != zoomed                          # (a click also places the cursor: not == whole)
    # cursor: the value under the pointer shows in the legend
    page.mouse.move(box["x"] + box["width"] * 0.4, box["y"] + box["height"] / 2)
    page.wait_for_timeout(200)
    assert f1.locator(".legend .chip .val").first.inner_text().strip() != ""

    # a straight paste (Ctrl+V into an editor): the static flavour - picture and table, no script
    page.set_content('<div id="ed" contenteditable="true" style="min-height:50px"></div>')
    page.click("#ed")
    page.keyboard.press("Control+v")
    page.wait_for_selector("#ed img")
    assert page.locator("#ed table").count() >= 1 and page.locator("#ed script").count() == 0
    page.close()
