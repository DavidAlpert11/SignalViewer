"""1.26: one Map - P4: it is the 3D view, "2D" is its From above camera (no 2D | 3D switch; "3D" alone is XYZ); the 3D view is in reports (it was left out without a
word); an HTML report is one live page - its bar moves the time plots and the 3D view (which falls back to its
picture where the browser has no WebGL).

    python -m pytest tests/e2e/test_live_report.py -q
"""
import os
import sys

import numpy as np
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
    geo.hover()                                       # review R3: a map plot's bar shows on the plot being used (selector change)
    geo.locator(".rel-toggle").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[1].relHidden === true")
    assert pg.locator(".plot .rel-panel").count() == 0
    geo.locator(".mode-btn").click()
    items = pg.locator(".menu.ctx button").all_inner_texts()
    assert any("Map" in i for i in items) and any(i.strip().startswith("3D (XYZ)") for i in items)
    assert not any(i.strip() == "3D" for i in items)                                 # no second "3D" kind
    pg.keyboard.press("Escape")
    geo.hover()
    geo.locator(".rel-toggle").click()
    pg.wait_for_selector(".plot .rel-panel")


def test_one_bar(pg):
    """P4 (adapted from test_one_bar_for_2d_and_3d): the Map's bar - camera Free / On the object (owner,
    2026-11-16: only these two) on the chosen object, + − fit, Relation; drawn flat, On the object can turn
    the map with the object (track up)."""
    map_and_line(pg)
    geo = pg.locator(".plot").nth(1)
    geo.hover()                                       # review R3: the pointer on the Map - its whole bar shows
    def bar():
        b = geo.locator(".map-bar")
        b.locator(".g3-seg").first.locator("button").first.wait_for()
        return [b.locator(".g3-seg").first.locator("button").all_inner_texts(), b.locator(".geo-zoom-in, .geo-zoom-out, .geo-fit, .rel-toggle").count(),
                b.locator("select.geo-follow option").all_inner_texts()]
    two = bar()
    # the object picker shows with the camera on an object
    assert two == [["Free", "On the object"], 4, []], two
    assert "on" in (geo.locator(".map-bar .g3-cam-free").get_attribute("class") or "")
    geo.locator(".map-bar .g3-cam-object").click()
    pg.wait_for_function("(() => { const p = window.__sv.state().ws.tabs[0].plots[1]; return !p.camera && p.followObject === 'o1'; })()")
    assert geo.locator(".map-bar select.geo-follow option").all_inner_texts() == ["Plane", "Chase"]
    if geo.locator(".geo-up").count():                                              # drawn flat: the map can turn with it
        geo.locator(".geo-up").click()
        pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[1].mapUp === 'track'")
    geo.locator(".map-bar .g3-cam-free").click()
    pg.wait_for_function("(() => { const p = window.__sv.state().ws.tabs[0].plots[1]; return p.followObject === null && p.camera === 'free'; })()")


def test_live_html_report_with_the_3d_view(pg):
    map_and_line(pg)                                                                  # P4: the Map goes out as the 3D page
    pg.click(".rail [aria-label='Report'], .rail button:has-text('Report')")
    assert pg.locator(".rplot").count() == 2                                         # the 3D view is listed
    pg.locator(".replay-make").click()                                          # RV8: the one offline page
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
            fr.locator('#cam [data-cam="centre"]').click()
            fr.wait_for_function("window.__scene.state.cam === 'centre' && window.__scene.state.camDist <= 1500")
        # the trail: the last 20 s only
        fr.locator("#trail").select_option("20")
        assert fr.evaluate("window.__page.trail()") == 20
        # the same toolbar in the 3D page as in the 2D map's page, with the app's words
        assert fr.locator("#cam button").all_inner_texts() == ["Free", "On the object"]   # the app's two cameras
        if gl:
            fr.locator('#cam [data-cam="free"]').click()
            fr.wait_for_function("window.__scene.state.cam === 'free'")
            assert fr.locator('#cam [data-cam="free"]').get_attribute("aria-checked") == "true"
    finally:
        page.close()


# ----------------------------------------------------------------------------- F4: live instruments
def _ins_csv(path, t):
    """a rig with a position and an attitude (radians: the Automatic rule), a temperature and a step state"""
    cols = np.column_stack([t, 20 + t, np.full_like(t, np.radians(10)), np.zeros_like(t), np.full_like(t, -1.5708),
                            32 + t * 2 / 111195.0, np.full_like(t, 35.0), 100 + t, (t > 5).astype(int)])
    np.savetxt(path, cols, delimiter=",", header="Time,Engine.Temp [degC],roll,pitch,yaw,lat,lon,alt,Step", comments="", fmt="%.9g")


def _open_instruments(pg):
    pg.locator(".rail button[aria-label='Checks']").click()
    pg.locator("aside.log-panel .log-tabs [data-tab=instruments]").click()
    pg.wait_for_selector("aside.log-panel .instruments")


def _tile(pg, name):
    return pg.locator(f"aside.log-panel .ins-tile[data-name='{name}']")


def test_instruments_on_a_recording(pg):
    _ins_csv(os.path.join(pg.env["data"], "rig.csv"), np.arange(0, 10, 0.5))
    open_files(pg, "rig.csv")
    _open_instruments(pg)
    panel = pg.locator("aside.log-panel .instruments")
    assert panel.locator(".empty-state").count() == 1                       # no profile: says what to do
    # the attitude of the object the map would draw (detected), in degrees, heading 0-360
    att = panel.locator(".ins-att")
    att.wait_for()
    assert abs(float(att.get_attribute("data-roll")) - 10) < 1e-3 and abs(float(att.get_attribute("data-yaw")) - 270) < 1e-2
    panel.locator(".ins-add select").select_option("Engine.Temp [degC]")
    panel.locator(".ins-add select").select_option("Step")
    pg.wait_for_function("(window.__sv.state().ws.instruments || []).length === 2")
    # the value in force at the time (never interpolated): at 3.2 s the 3.0 s sample
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, t1: 3.2 } })")
    pg.wait_for_function("document.querySelector(\".ins-tile[data-name='Engine.Temp [degC]']\").dataset.value === '23'")
    assert "degC" in _tile(pg, "Engine.Temp [degC]").inner_text()
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, t1: 7 } })")
    pg.wait_for_function("document.querySelector(\".ins-tile[data-name='Step']\").dataset.value === '1'")
    # remove = one Undo step
    _tile(pg, "Step").hover()
    _tile(pg, "Step").locator(".ins-x").click()
    pg.wait_for_function("window.__sv.state().ws.instruments.length === 1")
    pg.keyboard.press("Control+z")
    pg.wait_for_function("window.__sv.state().ws.instruments.length === 2")


def test_instruments_follow_a_live_file(pg):
    src = os.path.join(pg.env["data"], "growing.csv")
    _ins_csv(src, np.arange(0, 3, 0.5))
    open_files(pg, "growing.csv")
    pg.evaluate("window.__sv.state().commit((ws) => { ws.instruments = ['Oil.Temp|Engine.Temp', 'Nope']; return ws; })")
    _open_instruments(pg)
    pg.wait_for_function("(document.querySelector(\"aside.log-panel .ins-tile[data-name='Nope']\") || {}).innerText?.includes('Not in this file')")   # said, not hidden (once its answer is in)
    pg.click(".live-btn")
    pg.wait_for_function("window.__sv.state().streaming === true")
    assert pg.locator("aside.log-panel .instruments[data-live='1']").count() == 1
    with open(src, "a") as fh:
        for t in (3.0, 3.5, 4.0):
            fh.write(f"{t},{20 + t},0.1745,0,-1.5708,32,35,{100 + t},0\n")
    # the time stays at the newest data: the tile shows the last row's value
    pg.wait_for_function("document.querySelector(\".ins-tile[data-name='Oil.Temp|Engine.Temp']\").dataset.value === '24'", timeout=15000)
    pg.click(".live-btn")
    pg.wait_for_function("window.__sv.state().streaming === false")


def test_instruments_for_data_sent_from_python(pg):
    import time
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
    from signalviewer import push_client
    home = pg.env["home"]
    for _ in range(50):                                       # run.py writes push.json after start
        if os.path.isfile(os.path.join(home, ".signalviewer", "push.json")):
            break
        time.sleep(0.1)
    t = np.linspace(0, 20, 401)
    push_client.show(t, {"altitude": 100 + 5 * t}, name="sim run", home=home)
    pg.wait_for_function("window.__sv.state().runs.length === 1")
    pg.evaluate("window.__sv.state().commit((ws) => { ws.instruments = ['altitude']; return ws; })")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: false } })")
    _open_instruments(pg)
    pg.wait_for_function("document.querySelector(\".ins-tile[data-name='altitude']\")?.dataset.value === '200'")   # the newest
    push_client.show(t * 2, {"altitude": 300 + 5 * t}, name="sim run", home=home)       # sent again, longer
    pg.wait_for_function("document.querySelector(\".ins-tile[data-name='altitude']\")?.dataset.value === '400'", timeout=15000)
