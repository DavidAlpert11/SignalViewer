"""Round of 2026-11-12: the map's "Export the flight" submenu writes each of its three outputs
(Tacview .acmi, Tacview CSV files in a folder, Google Earth .kml), and an object with no position
(0, 0 for the whole file) is not added by *Add all*.

    python -m pytest tests/e2e/test_round_1112.py -q
"""
import os
import shutil
import xml.etree.ElementTree as ET

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, flat_maps, goto_folder, menu_item, open_files, pg, S, save_as  # noqa: E402,F401

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _map(pg):
    shutil.copy(os.path.join(ROOT, "examples", "three_objects.csv"), pg.env["data"])
    open_files(pg, "three_objects.csv")
    pg.locator(".obj-suggest .obj-suggest-add").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.some((p) => (p.mode === 'geo' || p.mode === '3d') && (p.objects ?? []).length === 3)")
    return S(pg, "s.ws.tabs[0].plots.findIndex((p) => (p.mode === 'geo' || p.mode === '3d'))")


def _submenu(pg, i, label):
    pg.locator(".plot-more").nth(i).click()
    pg.locator(".menu.ctx button", has_text="Export the flight").hover()
    menu_item(pg, label)
    pg.wait_for_selector(".dialog .crumbs input")                                     # the picker has loaded its folder


def test_export_the_flight_three_ways(pg):
    i = _map(pg)
    _submenu(pg, i, "Tacview (.acmi)…")
    save_as(pg, "flight")
    pg.wait_for_selector(".toast:has-text('3 object(s) saved for Tacview')")
    assert os.path.exists(os.path.join(pg.env["out"], "flight.acmi"))

    folder = os.path.join(pg.env["out"], "tacview")
    os.makedirs(folder, exist_ok=True)
    _submenu(pg, i, "Tacview CSV files (a folder)…")
    for _ in range(4):                                                                # as save_as: the picker may load late
        goto_folder(pg, folder)
        pg.wait_for_timeout(300)
        if pg.evaluate("document.querySelector('.crumbs input').value") == folder:
            break
    pg.click(".dialog button:has-text('Use this folder')")
    pg.wait_for_selector(".toast:has-text('CSV file(s) for Tacview saved')")
    assert pg.locator(".toast:has-text('File → Merge')").count() >= 1
    names = sorted(os.listdir(folder))
    assert len(names) == 3 and all(n.startswith("C172 (") and n.endswith("].csv") for n in names)

    _submenu(pg, i, "Google Earth (.kml)…")
    save_as(pg, "flight")
    pg.wait_for_selector(".toast:has-text('saved for Google Earth')")
    root = ET.parse(os.path.join(pg.env["out"], "flight.kml")).getroot()
    assert len(list(root.iter("{http://www.opengis.net/kml/2.2}Placemark"))) == 3


DRAWN = "(() => { const p = window.__sv.state().ws.tabs[0].plots.find((x) => (x.mode === 'geo' || x.mode === '3d')); return ((window.__svMapDrawn ?? {})[p.id] ?? []).map((id) => p.objects.find((o) => o.id === id).name).sort().join(','); })()"


def test_hide_an_object_on_the_map(pg):
    """P6: the eye on a chip hides an object (not drawn, not fitted, its chip struck through); Alt+click
    leaves only that one (again: all); a session saved and opened again keeps it hidden."""
    flat_maps(pg)                                                                 # the drawn-objects hook is the flat drawing's
    _map(pg)
    pg.wait_for_function(f"{DRAWN} === 'gps,nav,phys'")
    chip = lambda n: pg.locator(".obj-chip", has=pg.locator(".obj-chip-main", has_text=n))
    chip("gps").locator(".obj-eye").click()
    pg.wait_for_function(f"{DRAWN} === 'nav,phys'")
    assert "hidden" in chip("gps").get_attribute("class")
    chip("phys").locator(".obj-eye").click(modifiers=["Alt"])
    pg.wait_for_function(f"{DRAWN} === 'phys'")
    chip("phys").locator(".obj-eye").click(modifiers=["Alt"])
    pg.wait_for_function(f"{DRAWN} === 'gps,nav,phys'")
    chip("nav").locator(".obj-eye").click()
    pg.wait_for_function(f"{DRAWN} === 'gps,phys'")
    pg.keyboard.press("Control+s"); save_as(pg, "hidden_obj")
    pg.wait_for_selector(".toast:has-text('Saved')")
    with open(os.path.join(pg.env["out"], "hidden_obj.svsession"), encoding="utf-8") as f:
        assert '"hidden": true' in f.read().replace('"hidden":true', '"hidden": true')
    pg.keyboard.press("Control+Shift+O")
    goto_folder(pg, pg.env["out"])
    pg.locator(".dialog .dialog-body .fs-row", has_text="hidden_obj.svsession").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function(f"{DRAWN} === 'gps,phys'", timeout=15000)


def test_the_pages_legend_hides_objects(pg, tmp_path):
    """P6: in the offline map page each legend row is a button - a click hides, Alt+click leaves one."""
    _map(pg)
    path = str(tmp_path / "objs_map.html")
    pg.evaluate("""(path) => { const p = window.__sv.state().ws.tabs[0].plots.find((x) => (x.mode === 'geo' || x.mode === '3d'));
        const geo = { objects: p.objects.map((o) => ({ name: o.name, color: o.color, lat: o.lat, lon: o.lon, alt: o.alt ?? null })), base: 'offline', cursor: null, bounds: null };
        return fetch('/api/export/image', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path, format: 'html', theme: 'light', plot: { mode: 'geo', title: 'Objs', signals: [], geo } }) }).then((r) => r.json()); }""", path)
    page = pg.context.new_page()
    page.goto("file://" + path)
    page.wait_for_function("Array.isArray(window.__markers) && window.__markers.length === 3")
    page.locator("#legend .lg", has_text="gps").click()
    assert page.evaluate("window.__page.hidden()") == ["gps"]
    page.locator("#legend .lg", has_text="phys").click(modifiers=["Alt"])
    assert sorted(page.evaluate("window.__page.hidden()")) == ["gps", "nav"]
    page.locator("#legend .lg", has_text="phys").click(modifiers=["Alt"])
    assert page.evaluate("window.__page.hidden()") == []
    page.close()


NO_WEBGL = """(() => { const g = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (k, ...a) { return /webgl/i.test(k) ? null : g.call(this, k, ...a); }; })()"""


def test_without_webgl_the_map_is_flat_with_its_line(pg):
    """P4: where 3D cannot draw (no WebGL) the Map is the flat drawing with one quiet line, the same bar."""
    page = pg.context.new_page()
    try:
        page.add_init_script(NO_WEBGL)
        page.goto(pg.env["url"])
        page.wait_for_selector(".app")
        shutil.copy(os.path.join(ROOT, "examples", "three_objects.csv"), pg.env["data"])
        page.evaluate("(p) => fetch('/api/files/open', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paths: [p] }) })"
                      ".then(() => fetch('/api/runs')).then((r) => r.json()).then((runs) => window.__sv.setState({ runs }))",
                      os.path.join(pg.env["data"], "three_objects.csv"))
        page.wait_for_function("window.__sv.state().runs.length > 0")
        page.evaluate("""() => { const s = window.__sv.state(), run = s.runs.find((r) => r.name === 'three_objects.csv');
          s.commit((ws) => { const p = ws.tabs[0].plots[0]; p.mode = '3d';
            p.objects = [{ id: 'o1', name: 'phys', kind: 'aircraft', color: '#e5677a', lat: run.id + '/phys.lat', lon: run.id + '/phys.lon' }]; return ws; }); }""")
        page.wait_for_selector(".map-flat-note:has-text('Shown flat')")
        page.wait_for_selector(".plot .map-bar .g3-cam-top")
    finally:
        page.close()


VIEW_CENTRE = """(() => { const v = document.querySelector('.plot-canvas.geo').dataset.view.split(',').map(Number);
  return [Math.atan(Math.sinh(Math.PI * (1 - 2 * v[2]))) * 180 / Math.PI, v[1] * 360 - 180]; })()"""


def test_places_add_fly_and_page(pg, tmp_path):
    """P7: right-click on the Map -> Add a place here… -> it is in the Places panel and on the Map; a click in
    the panel flies there (the view's centre within 100 m); the offline page draws it."""
    flat_maps(pg)
    _map(pg)
    pg.wait_for_function("(window.__svMapDrawn ?? {}) && document.querySelector('.plot-canvas.geo')?.dataset.view")
    pg.wait_for_timeout(300)
    canvas = pg.locator(".plot-canvas.geo canvas").first
    box = canvas.bounding_box()
    canvas.click(button="right", position={"x": box["width"] * 0.3, "y": box["height"] * 0.4})
    menu_item(pg, "Add a place here…")
    pg.fill(".place-dialog .place-name", "Ground station")
    pg.wait_for_function("!document.querySelector('.place-dialog .place-save').disabled")
    pg.click(".place-dialog .place-save")
    pg.wait_for_selector(".places-panel .pl-session .pl-name:has-text('Ground station')")
    pg.wait_for_function("(window.__svMapPlaces ?? []).includes('Ground station')")
    place = pg.evaluate("window.__sv.state().ws.places[0]")
    # move away, then fly back from the panel
    pg.locator(".plot .geo-zoom-out").first.click()
    pg.locator(".plot .geo-zoom-out").first.click()
    pg.wait_for_timeout(400)
    pg.locator(".places-panel .pl-go", has_text="Ground station").click()
    pg.wait_for_timeout(1600)                                                      # the flight takes 1.2 s
    lat, lon = pg.evaluate(VIEW_CENTRE)
    d = ((lat - place["lat"]) * 111_000) ** 2 + ((lon - place["lon"]) * 111_000 * 0.84) ** 2
    assert d ** 0.5 < 100, (lat, lon, place)
    # a typed position in the search box flies there too
    pg.fill(".places-panel .pl-search", "32°41'13\"N 35°23'24\"E")
    pg.wait_for_selector(".places-panel .pl-goto")
    # the offline page draws it
    path = str(tmp_path / "places_map.html")
    pg.evaluate("""(path) => {
        const s = window.__sv.state(), p = s.ws.tabs[0].plots.find((x) => (x.mode === 'geo' || x.mode === '3d'));
        const geo = { objects: p.objects.map((o) => ({ name: o.name, color: o.color, lat: o.lat, lon: o.lon, alt: o.alt ?? null })), base: 'offline', cursor: null, bounds: null,
          places: s.ws.places };
        return fetch('/api/export/image', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path, format: 'html', theme: 'light', plot: { mode: 'geo', title: 'Objs', signals: [], geo } }) }).then((r) => r.json()); }""", path)
    page = pg.context.new_page()
    page.goto("file://" + path)
    page.wait_for_function("window.__page && window.__page.places().length === 1")
    assert page.locator("#labels .place-tag", has_text="Ground station").count() == 1
    page.close()


def test_settings_icon_of_a_new_object(pg):
    """P8: Settings > Map and objects - "navigation -> drone": objects added after it are drones; the ones
    already there (as in a session saved before) stay aircraft."""
    shutil.copy(os.path.join(ROOT, "examples", "ardupilot_lanes.csv"), pg.env["data"])
    open_files(pg, "ardupilot_lanes.csv")
    pg.locator(".obj-suggest .obj-suggest-add").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.some((p) => (p.objects ?? []).length > 1)")
    before = pg.evaluate("window.__sv.state().ws.tabs[0].plots.find((p) => (p.objects ?? []).length).objects.map((o) => [o.cls, o.kind])")
    assert all(k == "aircraft" for _c, k in before) and any(c == "navigation" for c, _k in before)
    pg.keyboard.press("Control+,")
    pg.wait_for_selector(".dialog.settings .set-map")
    assert pg.locator(".set-map .hint", has_text="new things only").count() == 1
    pg.select_option(".set-map .set-icon-navigation", "drone")
    pg.keyboard.press("Escape")
    assert pg.evaluate("window.__sv.state().ws.tabs[0].plots.find((p) => (p.objects ?? []).length).objects.every((o) => o.kind === 'aircraft')")
    # a new tab, the objects again: the navigation lanes are drones now
    pg.evaluate("window.__sv.state().commit((ws) => { ws.tabs[0].plots = ws.tabs[0].plots.map((p) => ({ ...p, objects: [] , mode: 'time' })); return ws; })")
    pg.evaluate("window.__sv.setState({ objSuggestHidden: [] })")
    pg.locator(".obj-suggest .obj-suggest-add").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.some((p) => (p.objects ?? []).length > 1)")
    after = pg.evaluate("window.__sv.state().ws.tabs[0].plots.find((p) => (p.objects ?? []).length).objects.map((o) => [o.cls, o.kind])")
    assert all((k == "drone") == (c == "navigation") for c, k in after), after
    # back to the default for the next tests (settings are kept by the app)
    pg.keyboard.press("Control+,")
    pg.click(".set-map .set-map-reset")
    pg.keyboard.press("Escape")



GL_ARGS = ["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]


def _post(env, path, body):
    import json
    import urllib.request
    req = urllib.request.Request(env["url"] + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())


def _tabor_page(env, tmp_path, camera=None, replay=None):
    """The Mount Tabor flight (tools/make_live_report_media.py: truth, nav drifting 6 m north, gps) as the 3D
    Map's own offline page (or, with `replay`, a live report holding it), made by the app."""
    import json
    import sys
    import urllib.request
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import make_live_report_media as media
    csv = os.path.join(env["data"], "tabor_flight.csv")
    media.flight_csv(csv)
    _post(env, "/api/files/open", {"paths": [csv]})
    r = next(x for x in json.loads(urllib.request.urlopen(env["url"] + "/api/runs").read()) if x["name"] == "tabor_flight.csv")["id"]
    o = lambda n, c, att: {"name": n, "kind": "aircraft", "color": c, "lat": f"{r}/{n}.lat", "lon": f"{r}/{n}.lon", "alt": f"{r}/{n}.alt",   # noqa: E731
                           **({"roll": f"{r}/{n}.att.roll", "pitch": f"{r}/{n}.att.pitch", "yaw": f"{r}/{n}.att.yaw"} if att else {})}
    objs = [o("truth", "#e5677a", True), o("nav", "#3d8bfd", True), o("gps", "#2da44e", False)]
    plot = {"mode": "3d", "title": "Tabor", "signals": [], "geo": {"objects": objs, "base": "offline", "cursor": 290, "primary": "truth", "secondary": "nav"},
            "scene": {"objects": objs, "follow": "truth" if camera else None, "camera": camera, "primary": "truth", "secondary": "nav"}}
    path = str(tmp_path / "tabor_3d.html")
    if replay is None:
        _post(env, "/api/export/image", {"path": path, "format": "html", "theme": "dark", "plot": plot})
        return path, r
    return plot, r


def test_the_wow_in_the_3d_page(env, tmp_path):
    """P9: the 3D page - the sun of the scene, drop lines and the last 10 s, flights, the cockpit (70°, its own
    model hidden), the flight display (off in General, on in Chase / Cockpit), the mini-map, the error surface
    between truth and nav (one vehicle: p95 near 6 m)."""
    from playwright.sync_api import sync_playwright
    path, _r = _tabor_page(env, tmp_path)
    with sync_playwright() as p:
        b = p.chromium.launch(args=GL_ARGS)
        page = b.new_page(viewport={"width": 1300, "height": 800})
        page.goto("file://" + path)
        page.wait_for_function("window.__scene && window.__scene.state.gl")
        w = lambda: page.evaluate("window.__scene.state.wow")                     # noqa: E731
        s = w()
        assert s["sun"]["el"] > 8 and not s["sun"]["dated"]
        assert s["drop"] and s["recent"] and not s["display"] and not s["mini"] and not s["cockpit"]
        assert s["errorSurface"]["shown"] and 4.5 < s["errorSurface"]["p95"] < 7.5 and s["errorSurface"]["median"] < 20
        page.click("#fit")
        assert page.evaluate("window.__scene.state.wow.gliding")                  # Fit flies there
        page.locator('#cam [data-cam="close"]').click()
        page.wait_for_timeout(1500)
        s = w()
        assert s["display"] and s["mini"]
        page.locator('#cam [data-cam="cockpit"]').click()
        page.wait_for_timeout(300)
        s = w()
        assert s["cockpit"] and s["fov"] == 70 and s["display"]
        page.click("#disp")
        page.wait_for_function("!window.__scene.state.wow.display")              # the next frame shows it (no sleep)
        page.click("#errs")
        page.wait_for_function("!window.__scene.state.wow.errorSurface.shown")
        b.close()


def test_story_in_the_live_page(env, tmp_path):
    """P10: the live page's ▶ Story - a card within 30 s, ◀ ▶ move the time, the 3D frame's camera goes to the
    moment's object, Esc ends it and the reader's camera comes back; the moments are diamonds on the timeline."""
    from playwright.sync_api import sync_playwright
    plot, _r = _tabor_page(env, tmp_path, replay=True)
    path = str(tmp_path / "tabor_live.html")
    events = [{"t": 62.0, "text": "GPS: 9 satellites", "level": "warning"}, {"t": 150.0, "text": "nav drifts north", "level": "note"},
              {"t": 231.0, "text": "EKF variance", "level": "error"}]
    _post(env, "/api/report", {"path": path, "format": "html", "title": "Tabor", "theme": "light",
                               "tabs": [{"name": "Flight", "plots": [plot]}],
                               "replay": {"t": 0.0, "extent": [0, 299.9], "compact": True, "events": events, "storyLength": 30}})
    with sync_playwright() as p:
        b = p.chromium.launch(args=GL_ARGS)
        page = b.new_page(viewport={"width": 1300, "height": 900})
        page.goto("file://" + path)
        page.wait_for_function("window.__replay && window.__replay.story.count > 0")
        count = page.evaluate("window.__replay.story.count")
        assert 4 <= count <= 12
        assert page.locator("#rp-marks i.story").count() == count
        fr = next(f for f in page.frames if f != page.main_frame)                 # the 3D view's page (a sandboxed frame)
        fr.wait_for_function("window.__scene && window.__scene.state.gl")
        cam0 = fr.evaluate("window.__scene.state.cam")
        assert not page.locator("#rp-story").is_visible()                       # 2026-11-13: it showed (as an empty box) before Story
        page.click("#rp-storybtn")
        page.wait_for_selector("#rp-story:not([hidden])", timeout=30000)
        st = page.evaluate("window.__replay.story")
        assert st["on"] and st["index"] >= 0
        page.wait_for_timeout(1500)
        inner = fr.evaluate("(() => { const s = window.__scene.state; return [s.cam, s.camObj]; })()")
        assert inner[0] in ("centre", "close") and inner[1] in ("truth", "nav", "gps")
        t1 = page.evaluate("window.__replay.t")
        page.click("#rp-story-next")
        assert page.evaluate("window.__replay.t") > t1 and page.evaluate("window.__replay.story.index") == st["index"] + 1
        page.click("#rp-story-prev")
        assert abs(page.evaluate("window.__replay.t") - t1) < 1e-6
        page.keyboard.press("Escape")
        assert not page.evaluate("window.__replay.story.on")
        page.wait_for_timeout(300)
        assert fr.evaluate("window.__scene.state.cam") == cam0
        b.close()


def test_story_in_the_app(pg):
    """P10: the Map's ▶ Story in the app - the cursor runs to the first moment, its card over the Map, ◀ ▶
    move between moments, Esc ends it; nothing goes into Undo."""
    flat_maps(pg)
    _map(pg)
    pg.wait_for_function("document.querySelector('.plot-canvas.geo')?.dataset.view")
    past = pg.evaluate("window.__sv.state().past.length")
    pg.locator(".map-bar .map-story").first.click()
    pg.wait_for_selector(".map-story-card", timeout=30000)
    st = pg.evaluate("window.__svStory")
    assert st["on"] and st["index"] >= 0 and st["count"] >= 1
    t1 = pg.evaluate("window.__sv.state().cursor.t1")
    if st["count"] > st["index"] + 1:
        pg.locator(".map-story-card .map-story-nav button").nth(1).click()
        assert pg.evaluate("window.__sv.state().cursor.t1") > t1
    pg.keyboard.press("Escape")
    pg.wait_for_function("!window.__svStory.on")
    assert pg.locator(".map-story-card").count() == 0
    # the camera flight sets the Map's camera free at most once (one Undo step), the cursor never
    assert pg.evaluate("window.__sv.state().past.length") - past <= 1


def test_story_keeps_a_chosen_camera(pg):
    """Owner (2026-11-13): the story moved to each moment by flying the camera, which set the Map's camera back
    to General - a chosen Chase / On the object stopped. Now the story only moves the time then."""
    flat_maps(pg)
    _map(pg)
    pg.wait_for_function("document.querySelector('.plot-canvas.geo')?.dataset.view")
    pg.evaluate("""(() => { const s = window.__sv.state(); s.commit((ws) => { for (const t of ws.tabs) for (const p of t.plots)
      if (p.objects && p.objects.length) { p.camera = 'chase'; p.followObject = p.objects[0].id; } return ws; }); })()""")
    cam = "(() => { for (const t of window.__sv.state().ws.tabs) for (const p of t.plots) if (p.objects && p.objects.length) return [p.camera, p.followObject]; })()"
    before = pg.evaluate(cam)
    pg.locator(".map-bar .map-story").first.click()
    pg.wait_for_selector(".map-story-card", timeout=30000)
    st = pg.evaluate("window.__svStory")
    if st["count"] > st["index"] + 1:
        pg.locator(".map-story-card .map-story-nav button").nth(1).click()
    pg.wait_for_timeout(400)
    assert pg.evaluate(cam) == before
    pg.keyboard.press("Escape")
    pg.wait_for_function("!window.__svStory.on")
    assert pg.evaluate(cam) == before
