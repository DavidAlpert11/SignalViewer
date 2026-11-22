"""CP1 (owner, 2026-11-18): Copy for Confluence. The plot's menu saves the page with every sample (attached to the
Confluence page) and puts two flavours on the clipboard: text/plain is the HTML macro's few lines that show that
attachment, text/html the picture + statistics + notes for a straight paste. Confluence is stood in for by a page
(its <meta name="ajs-page-id">) that holds the copied lines as the macro renders them, its attachment served at
/download/attachments/<page>/<name>: the plot is drawn in its frame, zooms, its lines go on and off - twice on one
page without the two meeting; not yet attached, the macro says what to do. A straight paste into an editor
(contenteditable) gets the picture and the table, no script."""
import json
import os
import re

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, open_files, pg, save_as, sig  # noqa: E402,F401

CONF = "http://confluence.test"


def _copy(pg, name, label="Copy for Confluence"):
    pg.locator(".plot-more").first.click()
    pg.locator(".menu.ctx button", has_text=label).first.click()
    save_as(pg, name)
    pg.wait_for_selector(f".toast:has-text('Saved {name}')", timeout=30000)


def _confluence(ctx, body, attachment=None):
    """A Confluence page (id 4711) with `body` in it; its attachment plot.html is `attachment` (else 404)."""
    page = ctx.new_page()
    page.route(CONF + "/download/attachments/4711/plot.html", lambda r: r.fulfill(status=200, body=attachment, content_type="text/html; charset=utf-8")
               if attachment else r.fulfill(status=404, body="no"))
    page.route(CONF + "/pages/viewpage.action", lambda r: r.fulfill(status=200, content_type="text/html; charset=utf-8",
               body='<html><head><meta name="ajs-page-id" content="4711"><meta name="ajs-context-path" content=""></head>'
                    '<body><h1 id="own">Confluence page</h1>%s</body></html>' % body))
    page.goto(CONF + "/pages/viewpage.action")
    return page


def test_copy_for_confluence_is_interactive_in_the_macro_and_static_when_pasted(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.evaluate("window.__sv.setState(s => ({ ws: { ...s.ws, notes: [{ id: 'n1', t: 5, text: 'gear change' }] } }))")
    _copy(pg, "plot.html")
    saved = open(os.path.join(pg.env["out"], "plot.html"), encoding="utf-8").read()
    data = json.loads(re.search(r'id="sv-data">(.*?)</script>', saved, re.S).group(1).replace("<\\/", "</"))
    assert data["tabs"][0]["plots"][0]["signals"][0]["levels"][-1]["n"] == 3000      # every sample of the recording
    text = pg.evaluate("navigator.clipboard.readText()")
    rich = pg.evaluate("""async () => { const it = (await navigator.clipboard.read())[0];
        return await (await it.getType('text/html')).text(); }""")
    assert len(text) < 4000 and "<iframe" in text and "plot.html" in text      # the macro: a few lines, never the data
    assert "<script" not in rich and "data:image/png;base64," in rich and "gear change" in rich and "Speed" in rich

    # not attached yet: the macro says so
    ctx = pg.context
    page = _confluence(ctx, text)
    page.wait_for_selector("text=is not attached to this page")
    page.close()
    # attached: the HTML macro's lines twice on one page among the page's own content
    page = _confluence(ctx, '<div class="m1">%s</div><p>between</p><div class="m2">%s</div>' % (text, text), saved)
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


def _render_user_macro(template, markup):
    """Confluence's part, stood in for: the user macro's Velocity with the parameters of `markup` and page 4711."""
    m = re.fullmatch(r"\{signalviewer:file=([^|}]+)\|height=(\d+)\}", markup)
    assert m, markup
    import html as H
    body = "\n".join(ln for ln in template.splitlines() if not ln.startswith("##"))
    return (body.replace("$!generalUtil.htmlEncode($!paramfile)", H.escape(m.group(1)))
            .replace("$!generalUtil.htmlEncode($!paramheight)", m.group(2))
            .replace("$!content.id", "4711").replace("$!req.contextPath", ""))


def test_copy_for_confluence_with_the_signal_viewer_user_macro(pg):
    """CP3 (owner, 2026-11-22): Settings -> Copy for Confluence: Signal Viewer macro. The copy is the macro's markup;
    the template (saved from Settings for the administrator) renders the plot live in a page - one without the
    meta tags too: Confluence gives the user macro the page itself."""
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.evaluate("window.__sv.setState({ confluenceMacro: 'user' })")
    _copy(pg, "plot.html")
    pg.wait_for_selector(".toast:has-text('Insert > Markup')")
    text = pg.evaluate("navigator.clipboard.readText()")
    assert text.startswith("{signalviewer:file=plot.html|height=")
    saved = open(os.path.join(pg.env["out"], "plot.html"), encoding="utf-8").read()
    # the template, as the Settings button saves it
    pg.evaluate("window.__sv.setState({ settingsOpen: true })")
    pg.locator(".set-confluence .seg button", has_text="Signal Viewer macro").wait_for()
    assert pg.locator(".set-confluence .seg button.on").inner_text() == "Signal Viewer macro"
    pg.locator(".set-confluence-save").click()
    save_as(pg, "macro.txt")
    pg.wait_for_selector(".toast:has-text('User Macros')", timeout=15000)
    tpl = open(os.path.join(pg.env["out"], "macro.txt"), encoding="utf-8").read()
    page = pg.context.new_page()
    page.route(CONF + "/download/attachments/4711/plot.html", lambda r: r.fulfill(status=200, body=saved, content_type="text/html; charset=utf-8"))
    page.route(CONF + "/display/X", lambda r: r.fulfill(status=200, content_type="text/html; charset=utf-8",
               body="<html><body><h1>Page</h1>%s</body></html>" % _render_user_macro(tpl, text)))
    page.goto(CONF + "/display/X")
    page.wait_for_function("""() => { const f = document.querySelector('.sv-clip iframe');
        return f && f.contentDocument && f.contentDocument.querySelector('.canvas canvas') && f.getBoundingClientRect().height > 300; }""", timeout=15000)
    page.close()
