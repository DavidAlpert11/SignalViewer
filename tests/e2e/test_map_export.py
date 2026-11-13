"""L11: a map saved as a standalone HTML page opens with no network at all (tiles and code embedded): the
slider moves the markers, the theme switches; the ⋯ menu offers the map's picture and page.

    python -m pytest tests/e2e/test_map_export.py -q
"""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, flat_maps, open_files, pg  # noqa: E402,F401

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_html_map_works_offline(pg, tmp_path):
    shutil.copy(os.path.join(ROOT, "examples", "ardupilot_lanes.csv"), pg.env["data"])
    open_files(pg, "ardupilot_lanes.csv")
    flat_maps(pg)                                                                 # P4: the flat map's own menu and page
    pg.locator(".obj-suggest-add").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.some((p) => (p.mode === 'geo' || p.mode === '3d') && (p.objects ?? []).length === 4)")
    # the map's ⋯ menu has the map's own picture and page
    geo = pg.locator(".plot", has=pg.locator(".plot-canvas.geo")).first
    geo.locator(".plot-more").click()
    pg.locator(".menu.ctx button", has_text="Save / export").hover()              # review: one submenu for saving / exporting
    pg.wait_for_selector(".menu.ctx button:has-text('this view')")
    items = pg.locator(".menu.ctx button").all_inner_texts()
    assert any("this view" in x for x in items) and any("fit all tracks" in x for x in items) and any("Save as HTML" in x for x in items)
    pg.keyboard.press("Escape")
    # the page as the menu saves it (the same request: the plot's objects, the layer, the cursor)
    path = str(tmp_path / "lanes_map.html")
    r = pg.evaluate("""(path) => { const p = window.__sv.state().ws.tabs[0].plots.find((x) => (x.mode === 'geo' || x.mode === '3d'));
        const geo = { objects: p.objects.map((o) => ({ name: o.name, color: o.color, lat: o.lat, lon: o.lon, alt: o.alt ?? null })), base: 'offline', cursor: null, bounds: null };
        return fetch('/api/export/image', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path, format: 'html', theme: 'light', plot: { mode: 'geo', title: 'Lanes', signals: [], geo } }) }).then((r) => r.json()); }""", path)
    assert r["path"] and r["size"] < 16 * 1024 * 1024
    # open it in a context with every request blocked
    ctx = pg.context.browser.new_context()
    blocked = []
    ctx.route("**/*", lambda route: (blocked.append(route.request.url), route.abort()) if not route.request.url.startswith(("file:", "data:")) else route.continue_())
    page = ctx.new_page()
    page.goto("file://" + path)
    page.wait_for_function("Array.isArray(window.__markers) && window.__markers.length === 4")
    end = page.evaluate("window.__markers.map((m) => m.join(','))")
    page.evaluate("() => { const s = document.getElementById('slider'); s.value = s.min; s.dispatchEvent(new Event('input')); }")
    start = page.evaluate("window.__markers.map((m) => m.join(','))")
    assert start != end                                                         # the markers moved with the slider
    assert page.locator("#legend").inner_text().count("\n") >= 3
    page.locator("#theme").click()
    assert "dark" in page.evaluate("document.documentElement.className")
    assert blocked == []                                                        # nothing was asked from outside
    ctx.close()
