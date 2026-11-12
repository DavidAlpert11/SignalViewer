"""1.26: one Map - P4: it is the 3D view, "2D" is its From above camera (no 2D | 3D switch; "3D" alone is XYZ); the 3D view is in reports (it was left out without a
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
        p.objects = [{ id: 'o1', name: 'Plane', kind: 'aircraft', color: '#e5677a', lat: run.id + '/Lat', lon: run.id + '/Lon' },
                     { id: 'o2', name: 'Chase', kind: 'aircraft', color: '#3d8bfd', track: 'dash', lat: run.id + '/Lat', lon: run.id + '/Lon' }]; return ws; }); }""")
    pg.wait_for_selector(".plot .map-bar")


def test_one_map(pg):
    """P4 (adapted from test_one_map_two_views): no 2D | 3D switch - a map with objects is the Map (the 3D
    view; here, without WebGL, its flat drawing with its quiet line)."""
    map_and_line(pg)
    geo = pg.locator(".plot").nth(1)
    assert geo.locator(".mode-btn").inner_text().strip() == "Map"
    assert geo.locator(".map-view").count() == 0
    assert S(pg, "s.ws.tabs[0].plots[1].objects.length") == 2                       # the objects stay
    # 1.26: the relation box in 3D as on the 2D map; the same Relation button hides / shows it in both
    pg.wait_for_selector(".plot .rel-panel")
    geo.locator(".rel-toggle").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[1].relHidden === true")
    assert pg.locator(".plot .rel-panel").count() == 0
    geo.locator(".mode-btn").click()
    items = pg.locator(".menu.ctx button").all_inner_texts()
    assert any("Map" in i for i in items) and any(i.strip().startswith("3D (XYZ)") for i in items)
    assert not any(i.strip() == "3D" for i in items)                                 # no second "3D" kind
    pg.keyboard.press("Escape")
    geo.locator(".rel-toggle").click()
    pg.wait_for_selector(".plot .rel-panel")


def test_one_bar(pg):
    """P4 (adapted from test_one_bar_for_2d_and_3d): the Map's bar - camera General / From above / On the
    object / Chase on the chosen object, + − fit, Relation; a 2D-era map opens From above; Chase in the flat
    drawing is close and track up."""
    map_and_line(pg)
    geo = pg.locator(".plot").nth(1)
    def bar():
        b = geo.locator(".map-bar")
        b.locator(".g3-seg").first.locator("button").first.wait_for()
        return [b.locator(".g3-seg").first.locator("button").all_inner_texts(), b.locator(".geo-zoom-in, .geo-zoom-out, .geo-fit, .rel-toggle").count(),
                b.locator("select.geo-follow option").all_inner_texts()]
    two = bar()
    assert two == [["General", "From above", "On the object", "Chase", "Cockpit"], 4, ["Plane", "Chase"]], two   # P9: Cockpit
    assert "on" in (geo.locator(".map-bar .g3-cam-top").get_attribute("class") or "")   # a 2D-era map: From above
    geo.locator(".map-bar .g3-cam-chase").click()
    pg.wait_for_function("(() => { const p = window.__sv.state().ws.tabs[0].plots[1]; return p.camera === 'chase' && p.followObject === 'o1'; })()")
    if geo.locator(".geo-up").count():
        assert "on" in (geo.locator(".geo-up").get_attribute("class") or "")         # Chase, drawn flat: track up
    geo.locator(".map-bar button", has_text="General").click()
    pg.wait_for_function("(() => { const p = window.__sv.state().ws.tabs[0].plots[1]; return p.followObject === null && p.camera === 'free'; })()")
    geo.locator(".map-bar .g3-cam-top").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[1].camera === 'top'")


def test_live_html_report_with_the_3d_view(pg):
    map_and_line(pg)                                                                  # P4: the Map goes out as the 3D page
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
        # 1.26: the page's relation box - shown, hidden by its button; the camera close to the reference
        assert fr.evaluate("window.__page.rel().shown") is True and fr.locator(".svrel").is_visible()
        assert fr.evaluate("window.__page.rel().pair") == {"p": 0, "s": 1}
        fr.locator("#rel").click()
        assert fr.evaluate("window.__page.rel().shown") is False and fr.locator("#rel").get_attribute("aria-pressed") == "false"
        if gl:
            fr.locator('#cam [data-cam="close"]').click()
            fr.wait_for_function("window.__scene.state.cam === 'close' && window.__scene.state.camDist < 100")
        # the trail: the last 20 s only
        fr.locator("#trail").select_option("20")
        assert fr.evaluate("window.__page.trail()") == 20
        # the same toolbar in the 3D page as in the 2D map's page, with the app's words
        assert fr.locator("#cam button").all_inner_texts()[:3] == ["General", "On the object", "Chase"]   # (+ Cockpit in 3D, P9)
    finally:
        page.close()
