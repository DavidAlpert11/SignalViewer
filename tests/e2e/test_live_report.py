"""1.26: one Map with a 2D | 3D switch ("3D" alone is XYZ); the 3D view is in reports (it was left out without a
word); an HTML report is one live page - its bar moves the time plots and the 3D view (which falls back to its
picture where the browser has no WebGL).

    python -m pytest tests/e2e/test_live_report.py -q
"""
import os

import pytest

pw = pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, save_as, set_layout, sig  # noqa: E402,F401


def map_and_line(pg):
    open_files(pg, "geo.csv")
    set_layout(pg, 2, 1)
    sig(pg, "Gear").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    pg.evaluate("""() => { const s = window.__sv.state(), run = s.runs.find(r => r.name === 'geo.csv');
      s.commit((ws) => { const p = ws.tabs[0].plots[1]; p.mode = 'geo';
        p.objects = [{ id: 'o1', name: 'Plane', kind: 'aircraft', color: '#e5677a', lat: run.id + '/Lat', lon: run.id + '/Lon' }]; return ws; }); }""")
    pg.wait_for_selector(".plot .map-view")


def test_one_map_two_views(pg):
    map_and_line(pg)
    geo = pg.locator(".plot").nth(1)
    assert geo.locator(".mode-btn").inner_text().strip() == "Map"
    geo.locator(".map-view button", has_text="3D").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[1].mode === '3d'")
    assert geo.locator(".mode-btn").inner_text().strip() == "Map"                  # still the Map, seen in 3D
    assert S(pg, "s.ws.tabs[0].plots[1].objects.length") == 1                       # the objects stay
    geo.locator(".mode-btn").click()
    items = pg.locator(".menu.ctx button").all_inner_texts()
    assert any("Map" in i for i in items) and any(i.strip().startswith("3D (XYZ)") for i in items)
    assert not any(i.strip() == "3D" for i in items)                                 # no second "3D" kind
    pg.keyboard.press("Escape")
    geo.locator(".map-view button", has_text="2D").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[1].mode === 'geo'")


def test_live_html_report_with_the_3d_view(pg):
    map_and_line(pg)
    pg.locator(".plot").nth(1).locator(".map-view button", has_text="3D").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[1].mode === '3d'")
    pg.click(".rail [aria-label='Report'], .rail button:has-text('Report')")
    assert pg.locator(".rplot").count() == 2                                         # the 3D view is listed
    pg.locator(".btn.primary", has_text="Create interactive HTML").click()
    save_as(pg, "live.html")
    pg.locator(".toast", has_text="live.html").wait_for(timeout=60000)
    page = pg.context.new_page()
    try:
        page.goto("file://" + os.path.join(pg.env["out"], "live.html"))
        page.wait_for_function("window.__replay && document.querySelectorAll('iframe.mapframe').length === 1")
        assert page.evaluate("document.body.className") == "live"                   # the report's layout, one time
        assert page.locator(".plot table").count() >= 1                              # its statistics kept
        fr = next(f for f in page.frames if f != page.main_frame)
        fr.wait_for_function("window.__scene")
        b = page.locator("#rp-track").bounding_box()
        page.mouse.click(b["x"] + b["width"] * 0.7, b["y"] + b["height"] / 2)
        page.wait_for_function("window.__replay.t > window.__replay.lo + 0.5 * (window.__replay.hi - window.__replay.lo)")
        t = page.evaluate("window.__replay.t")
        fr.wait_for_function(f"Math.abs(window.__scene.t - {t}) < 0.05")             # the 3D view follows the page
        gl = fr.evaluate("window.__scene.state.gl")
        if not gl:                                                                   # no WebGL here: its picture
            assert fr.locator("#fallback").is_visible()
    finally:
        page.close()
