"""The 3D view: loads without the internet, puts the objects' 3D models where they are at the
timeline's time with the right heading / pitch / roll, shows height above ground.

    python -m pytest tests/e2e/test_globe3d.py -q
(WebGL in headless Chromium is software-rendered here: slow, hence the long waits.)
"""
import json
import os
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env  # noqa: E402,F401

GL = ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]


@pytest.fixture
def g3(env):
    from playwright.sync_api import sync_playwright
    d = env["data"]
    with open(os.path.join(d, "att_case.csv"), "w") as f:
        f.write("Time,GPS.Lat,GPS.Lng,GPS.Alt,ATT.Yaw,ATT.Pitch,ATT.Roll\n")
        for i in range(120):                                   # still, at 300 m over the sea; yaw 90, pitch 20, roll 30 (degrees)
            f.write(f"{i * 0.5},32.5,34.5,300,90,20,30\n")
    for r in json.loads(urllib.request.urlopen(env["url"] + "/api/runs").read()):
        urllib.request.urlopen(urllib.request.Request(env["url"] + f"/api/runs/{r['id']}", method="DELETE"))
    urllib.request.urlopen(urllib.request.Request(env["url"] + "/api/files/open", json.dumps({"paths": [os.path.join(d, "att_case.csv")]}).encode(),
                                                  {"Content-Type": "application/json"}))
    auto = os.path.join(env["home"], ".signalviewer", "autosave.json")
    if os.path.exists(auto):
        os.remove(auto)
    with sync_playwright() as p:
        b = p.chromium.launch(args=GL)
        pg = b.new_context(viewport={"width": 1100, "height": 800}, locale="en-US").new_page()
        external = []
        pg.on("request", lambda r: external.append(r.url) if not r.url.startswith(env["url"]) and not r.url.startswith(("data:", "blob:")) else None)
        pg.goto(env["url"])
        pg.wait_for_selector(".app")
        pg.evaluate("fetch('/api/runs').then(r => r.json()).then(runs => window.__sv.setState({ runs }))")
        pg.wait_for_selector(".sig")
        rid = pg.evaluate("window.__sv.state().runs[0].id")
        pg.evaluate(f"""window.__sv.setState({{ geoBase: 'offline', ws: (() => {{ const ws = structuredClone(window.__sv.state().ws); const p = ws.tabs[0].plots[0];
            p.mode = '3d'; p.objects = [{{ id: 'a', name: 'Test', kind: 'aircraft', color: '#ff3030', lat: '{rid}/GPS.Lat', lon: '{rid}/GPS.Lng',
              alt: '{rid}/GPS.Alt', yaw: '{rid}/ATT.Yaw', pitch: '{rid}/ATT.Pitch', roll: '{rid}/ATT.Roll' }}]; return ws; }})() }})""")
        pg.wait_for_function("!!window.__svGlobe", timeout=90000)
        pg.wait_for_selector(".globe3d-readout", timeout=60000)
        pg.wait_for_function("document.querySelector('.globe3d-readout').textContent.includes('Roll')", timeout=60000)
        yield pg, external
        b.close()


MODEL_AXES = """(() => { const { widget: w, Cesium: C } = window.__svGlobe; let m = null;
  for (let i = 0; i < w.scene.primitives.length; i++) { const p = w.scene.primitives.get(i); if (p instanceof C.Model) m = p; }
  const pos = C.Matrix4.getTranslation(m.modelMatrix, new C.Cartesian3());
  const carto = C.Cartographic.fromCartesian(pos);
  const inv = C.Matrix4.getMatrix3(C.Matrix4.inverse(C.Transforms.eastNorthUpToFixedFrame(pos), new C.Matrix4()), new C.Matrix3());
  const axis = (v) => { const r = C.Matrix3.multiplyByVector(C.Matrix4.getMatrix3(m.modelMatrix, new C.Matrix3()), v, new C.Cartesian3());
    const e = C.Matrix3.multiplyByVector(inv, r, new C.Cartesian3()); return [e.x, e.y, e.z]; };
  return { nose: axis(new C.Cartesian3(1, 0, 0)), right: axis(new C.Cartesian3(0, -1, 0)),
           lat: C.Math.toDegrees(carto.latitude), lon: C.Math.toDegrees(carto.longitude), h: carto.height }; })()"""


def test_model_heading_pitch_roll_and_place(g3):
    pg, _ = g3
    a = pg.evaluate(MODEL_AXES)
    (e, n, u), (re_, rn, ru) = a["nose"], a["right"]
    # heading 90 = east, pitch +20 = nose up
    assert e > 0.9 and abs(n) < 0.05 and abs(u - __import__("math").sin(__import__("math").radians(20))) < 0.02, a
    # roll +30 = right wing down (the right wing points south when heading east)
    assert rn < -0.5 and ru < -0.3, a
    assert abs(a["lat"] - 32.5) < 1e-6 and abs(a["lon"] - 34.5) < 1e-6 and abs(a["h"] - 300) < 0.5


def test_readout_and_nothing_from_the_internet(g3):
    pg, external = g3
    txt = pg.locator(".globe3d-readout").inner_text()
    assert "Alt 300" in txt and "AGL 300" in txt                   # over the sea: ground 0
    assert "Hdg 90°" in txt and "Pitch 20°" in txt and "Roll 30°" in txt
    pg.wait_for_timeout(1500)
    assert external == []


def test_follow_centres_the_camera_on_the_object(g3):
    pg, _ = g3
    pid = pg.evaluate("window.__sv.state().ws.tabs[0].plots[0].id")
    pg.evaluate(f"""window.__sv.setState({{ ws: (() => {{ const ws = structuredClone(window.__sv.state().ws);
        ws.tabs[0].plots[0].followObject = 'a'; return ws; }})() }})""")
    pg.wait_for_timeout(2500)
    # the point in the middle of the view is the object (the camera looks straight at it)
    r = pg.evaluate("""(() => { const { widget: w, Cesium: C } = window.__svGlobe; let m = null;
      for (let i = 0; i < w.scene.primitives.length; i++) { const p = w.scene.primitives.get(i); if (p instanceof C.Model) m = p; }
      const pos = C.Matrix4.getTranslation(m.modelMatrix, new C.Cartesian3());
      const dir = C.Cartesian3.normalize(C.Cartesian3.subtract(pos, w.camera.positionWC, new C.Cartesian3()), new C.Cartesian3());
      return C.Cartesian3.dot(dir, w.camera.directionWC); })()""")
    assert r > 0.999                                                # within ~2.5 degrees of the view's centre


def test_light_settings_without_graphics_acceleration(g3):
    pg, _ = g3
    soft = pg.evaluate("""(() => { const gl = document.createElement('canvas').getContext('webgl'); const e = gl.getExtension('WEBGL_debug_renderer_info');
      return /swiftshader|llvmpipe|softpipe|basic render|software/i.test(String(gl.getParameter(e ? e.UNMASKED_RENDERER_WEBGL : gl.RENDERER))); })()""")
    shown = pg.locator(".globe3d-light").count() == 1
    assert shown == soft                                            # the badge exactly when drawing is in software
    if soft:
        assert pg.evaluate("window.__svGlobe.widget.scene.msaaSamples") == 1
        assert pg.evaluate("window.__svGlobe.widget.scene.globe.maximumScreenSpaceError") == 4


@pytest.fixture
def g3multi(env):
    """Three still objects: A at 32.5, 34.5, 300 m; B 0.01 deg east at 500 m; C 0.01 deg north at 300 m."""
    from playwright.sync_api import sync_playwright
    d = env["data"]
    for name, lat, lon, alt in (("obj_A.csv", 32.5, 34.5, 300), ("obj_B.csv", 32.5, 34.51, 500), ("obj_C.csv", 32.51, 34.5, 300)):
        with open(os.path.join(d, name), "w") as f:
            f.write("Time,Lat,Lon,Alt\n" + "".join(f"{i * 0.5},{lat},{lon},{alt}\n" for i in range(120)))
    for r in json.loads(urllib.request.urlopen(env["url"] + "/api/runs").read()):
        urllib.request.urlopen(urllib.request.Request(env["url"] + f"/api/runs/{r['id']}", method="DELETE"))
    urllib.request.urlopen(urllib.request.Request(env["url"] + "/api/files/open", json.dumps(
        {"paths": [os.path.join(d, n) for n in ("obj_A.csv", "obj_B.csv", "obj_C.csv")]}).encode(), {"Content-Type": "application/json"}))
    auto = os.path.join(env["home"], ".signalviewer", "autosave.json")
    if os.path.exists(auto):
        os.remove(auto)
    with sync_playwright() as p:
        b = p.chromium.launch(args=GL)
        pg = b.new_context(viewport={"width": 1200, "height": 800}, locale="en-US").new_page()
        pg.goto(env["url"])
        pg.wait_for_selector(".app")
        pg.evaluate("fetch('/api/runs').then(r => r.json()).then(runs => window.__sv.setState({ runs }))")
        pg.wait_for_selector(".sig")
        ids = pg.evaluate("Object.fromEntries(window.__sv.state().runs.map(r => [r.name, r.id]))")
        objs = ",".join(f"{{ id: '{k}', name: '{k}', kind: 'aircraft', color: '{c}', lat: '{ids[f'obj_{k}.csv']}/Lat', lon: '{ids[f'obj_{k}.csv']}/Lon', alt: '{ids[f'obj_{k}.csv']}/Alt' }}"
                        for k, c in (("A", "#ff3030"), ("B", "#30a0ff"), ("C", "#30d070")))
        pg.evaluate(f"""window.__sv.setState({{ geoBase: 'offline', ws: (() => {{ const ws = structuredClone(window.__sv.state().ws); const p = ws.tabs[0].plots[0];
            p.mode = '3d'; p.objects = [{objs}]; return ws; }})() }})""")
        pg.wait_for_function("!!window.__svGlobe", timeout=90000)
        pg.wait_for_selector(".globe3d-readout", timeout=60000)
        yield pg
        b.close()


def test_related_objects_distance_line_and_box(g3multi):
    pg = g3multi
    assert pg.locator(".globe3d-readout b").inner_text() == "A"                # the first object is the primary
    pg.locator(".globe3d-bar select[aria-label='Second']").select_option("B")
    pg.locator(".globe3d-bar select[aria-label='Third']").select_option("C")
    pg.wait_for_function("document.querySelectorAll('.globe3d-readout .g3-rel').length === 2")
    rel = pg.locator(".globe3d-readout .g3-rel").all_inner_texts()
    # A -> B on the WGS84 ellipsoid: 0.01 deg of longitude at 32.5 N = N cos(lat) dlon = 940 m; 200 m higher;
    # slant sqrt(940^2 + 200^2) = 961 m; bearing east
    assert rel[0].startswith("B: 940 m") and "Δh +200 m" in rel[0] and "slant 961 m" in rel[0] and "90°" in rel[0], rel[0]
    # A -> C: 0.01 deg of latitude at 32.5 N = 1.109 km, same height, north
    assert rel[1].startswith("C: 1.11 km") and "Δh +0 m" in rel[1] and " 0°" in rel[1], rel[1]
    lines = pg.evaluate("""(() => { const { widget: w, Cesium: C } = window.__svGlobe; let n = 0;
      for (let i = 0; i < w.scene.primitives.length; i++) { const p = w.scene.primitives.get(i);
        if (p instanceof C.PolylineCollection) for (let k = 0; k < p.length; k++) if (p.get(k).material.type === 'PolylineDash') n++; } return n; })()""")
    assert lines == 2                                                           # a dashed line to each
    pg.locator(".globe3d-bar button", has_text="Data").click()                 # the box can be hidden
    pg.wait_for_selector(".globe3d-readout", state="detached")
    assert pg.evaluate("window.__sv.state().ws.tabs[0].plots[0].showReadout") is False


def test_camera_on_the_object_zooms_towards_it(g3multi):
    pg = g3multi
    pg.locator(".globe3d-bar select[aria-label='Object']").select_option("B")
    pg.locator(".globe3d-bar button", has_text="On the object").click()
    pg.wait_for_timeout(1500)
    probe = """(() => { const { widget: w, Cesium: C } = window.__svGlobe;
      const pos = C.Cartesian3.fromDegrees(34.51, 32.5, 500);
      const dir = C.Cartesian3.normalize(C.Cartesian3.subtract(pos, w.camera.positionWC, new C.Cartesian3()), new C.Cartesian3());
      return { d: C.Cartesian3.distance(w.camera.positionWC, pos), centre: C.Cartesian3.dot(dir, w.camera.directionWC) }; })()"""
    a = pg.evaluate(probe)
    assert a["centre"] > 0.999, a                                              # B in the middle
    # zoom in with the wheel away from the middle: the camera still goes towards B
    box = pg.locator(".globe3d-host").bounding_box()
    pg.mouse.move(box["x"] + box["width"] * 0.85, box["y"] + box["height"] * 0.8)
    for _ in range(4):
        pg.mouse.wheel(0, -400)
        pg.wait_for_timeout(300)
    pg.wait_for_timeout(1500)
    b = pg.evaluate(probe)
    assert b["d"] < a["d"] * 0.8 and b["centre"] > 0.999, (a, b)
    # another primary while centred: the camera moves to it
    pg.locator(".globe3d-bar select[aria-label='Object']").select_option("C")
    assert pg.evaluate("window.__sv.state().ws.tabs[0].plots[0].followObject") == "C"


@pytest.fixture
def g3move(env):
    """One object moving north: latitude 32.0 + t * 1e-4 (t = 0..100 s), at 300 m."""
    from playwright.sync_api import sync_playwright
    d = env["data"]
    with open(os.path.join(d, "obj_move.csv"), "w") as f:
        f.write("Time,Lat,Lon,Alt\n" + "".join(f"{i * 0.5},{32.0 + i * 0.5e-4:.6f},34.5,300\n" for i in range(201)))
    for r in json.loads(urllib.request.urlopen(env["url"] + "/api/runs").read()):
        urllib.request.urlopen(urllib.request.Request(env["url"] + f"/api/runs/{r['id']}", method="DELETE"))
    urllib.request.urlopen(urllib.request.Request(env["url"] + "/api/files/open", json.dumps({"paths": [os.path.join(d, "obj_move.csv")]}).encode(),
                                                  {"Content-Type": "application/json"}))
    auto = os.path.join(env["home"], ".signalviewer", "autosave.json")
    if os.path.exists(auto):
        os.remove(auto)
    with sync_playwright() as p:
        b = p.chromium.launch(args=GL)
        pg = b.new_context(viewport={"width": 1200, "height": 800}, locale="en-US").new_page()
        pg.goto(env["url"])
        pg.wait_for_selector(".app")
        pg.evaluate("fetch('/api/runs').then(r => r.json()).then(runs => window.__sv.setState({ runs }))")
        pg.wait_for_selector(".sig")
        rid = pg.evaluate("window.__sv.state().runs[0].id")
        pg.evaluate(f"""window.__sv.setState({{ geoBase: 'offline', cursor: {{ ...window.__sv.state().cursor, on: true, t1: 20 }},
            ws: (() => {{ const ws = structuredClone(window.__sv.state().ws); const p = ws.tabs[0].plots[0];
            p.mode = '3d'; p.objects = [{{ id: 'm', name: 'M', kind: 'drone', color: '#ff3030', lat: '{rid}/Lat', lon: '{rid}/Lon', alt: '{rid}/Alt' }}]; return ws; }})() }})""")
        pg.wait_for_function("!!window.__svGlobe", timeout=90000)
        pg.wait_for_selector(".globe3d-readout", timeout=60000)
        yield pg
        b.close()


MODEL_LAT = """(() => { const { widget: w, Cesium: C } = window.__svGlobe; let m = null;
  for (let i = 0; i < w.scene.primitives.length; i++) { const p = w.scene.primitives.get(i); if (p instanceof C.Model) m = p; }
  return C.Math.toDegrees(C.Cartographic.fromCartesian(C.Matrix4.getTranslation(m.modelMatrix, new C.Cartesian3())).latitude); })()"""


def test_own_time_is_independent_of_the_timeline(g3move):
    pg = g3move
    pg.wait_for_timeout(500)
    assert abs(pg.evaluate(MODEL_LAT) - (32.0 + 20 * 1e-4)) < 2e-6                # shared: at the timeline's t = 20
    pg.locator(".globe3d-bar button", has_text="Own time").click()
    pg.wait_for_selector(".g3-own")
    assert pg.evaluate("window.__sv.state().ws.tabs[0].plots[0].ownTime") == 20     # starts where the timeline was
    # the timeline moves: this view does not
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, t1: 80 } })")
    pg.wait_for_timeout(500)
    assert abs(pg.evaluate(MODEL_LAT) - (32.0 + 20 * 1e-4)) < 2e-6
    # its own playback moves it; the timeline's time stays
    pg.locator(".g3-own select").select_option("10")
    pg.locator(".g3-own .iconbtn").click()
    pg.wait_for_timeout(2000)
    pg.locator(".g3-own .iconbtn").click()
    lat = pg.evaluate(MODEL_LAT)
    assert lat > 32.0 + 25 * 1e-4, lat
    assert pg.evaluate("window.__sv.state().cursor.t1") == 80
    own = pg.evaluate("window.__sv.state().ws.tabs[0].plots[0].ownTime")
    assert own > 25                                                                 # kept when paused
    # dragging its own bar to the start
    pg.locator(".g3-own input[type=range]").fill("0")
    pg.wait_for_timeout(500)
    assert abs(pg.evaluate(MODEL_LAT) - 32.0) < 2e-6
    # shared again: back on the timeline's time
    pg.locator(".globe3d-bar button", has_text="Shared").click()
    pg.wait_for_selector(".g3-own", state="detached")
    pg.wait_for_timeout(500)
    assert abs(pg.evaluate(MODEL_LAT) - (32.0 + 80 * 1e-4)) < 2e-6
    assert pg.evaluate("window.__sv.state().ws.tabs[0].plots[0].ownTime") is None


def test_measure_two_points_on_the_ground(g3multi):
    pg = g3multi
    # the ground's detail first: while only the coarse terrain is in, heights there are smeared from far
    # mountains and a click lands on that (a globe measures what it shows)
    pg.wait_for_function("(() => { const w = window.__svGlobe.widget; w.scene.requestRender(); return w.scene.globe.tilesLoaded; })()",
                         timeout=90000, polling=500)
    pg.locator(".globe3d-bar button", has_text="Measure").click()
    pg.wait_for_selector(".g3-measure:has-text('first point')")
    # where two known places are on the screen: 32.5 N and 32.51 N at 34.5 E (sea: height 0)
    pts = pg.evaluate("""(() => { const { widget: w, Cesium: C } = window.__svGlobe; const r = w.scene.canvas.getBoundingClientRect();
      const T = C.SceneTransforms.worldToWindowCoordinates || C.SceneTransforms.wgs84ToWindowCoordinates;
      return [[34.5, 32.5], [34.5, 32.51]].map(([lo, la]) => { const p = T(w.scene, C.Cartesian3.fromDegrees(lo, la, 0)); return [r.left + p.x, r.top + p.y]; }); })()""")
    for x, y in pts:
        pg.mouse.click(x, y)
        pg.wait_for_timeout(400)
    txt = pg.locator(".g3-measure").inner_text()
    import re
    ground = re.search(r"Ground ([\d.,]+) (k?m)", txt)
    metres = float(ground.group(1).replace(",", "")) * (1000 if ground.group(2) == "km" else 1)
    assert abs(metres - 1109) < 25, txt                          # 0.01 deg of latitude at 32.5 N on WGS84
    assert pg.evaluate("""(() => { const { widget: w, Cesium: C } = window.__svGlobe; let n = 0;
      for (let i = 0; i < w.scene.primitives.length; i++) { const p = w.scene.primitives.get(i); if (p instanceof C.PointPrimitiveCollection) n += p.length; } return n; })()""") >= 2
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".g3-measure", state="detached")


def test_log_events_on_the_track_and_image(g3multi):
    pg = g3multi
    rid = pg.evaluate("window.__sv.state().runs.find(r => r.name === 'obj_A.csv').id")
    # events of A's file (as a flight log would give them): an error and a mode change
    pg.evaluate(f"""window.__sv.setState({{ logs: {{ ...window.__sv.state().logs, '{rid}': {{ timeOffset: 0, params: [], events: [
        {{ t: 10, kind: 'error', text: 'GPS glitch', level: 'error' }}, {{ t: 30, kind: 'mode', text: 'LOITER', level: 'info' }},
        {{ t: 40, kind: 'msg', text: 'just info', level: 'info' }}] }} }} }})""")
    pg.locator(".globe3d-bar button", has_text="Events").wait_for()
    count = """(() => { const { widget: w, Cesium: C } = window.__svGlobe; let n = 0;
      for (let i = 0; i < w.scene.primitives.length; i++) { const p = w.scene.primitives.get(i); if (p instanceof C.LabelCollection)
        for (let k = 0; k < p.length; k++) if (['GPS glitch', 'LOITER'].includes(p.get(k).text)) n++; } return n; })()"""
    pg.wait_for_function(count + " === 2")                        # the error and the mode change; not the plain message
    pg.locator(".globe3d-bar button", has_text="Events").click()
    pg.wait_for_function(count + " === 0")
    # the view as a PNG file
    out = os.path.join(pg.evaluate("'" + os.environ.get("TMPDIR", "/tmp") + "'"), "g3_view_test.png")
    if os.path.exists(out):
        os.remove(out)
    pg.locator(".globe3d-bar button", has_text="Image").click()
    pg.wait_for_selector(".dialog .crumbs input")
    pg.wait_for_function("document.querySelector('.dialog .crumbs input').value !== ''")
    pg.fill(".dialog .crumbs input", os.path.dirname(out))
    pg.keyboard.press("Enter")
    pg.wait_for_function(f"document.querySelector('.dialog .crumbs input').value === {json.dumps(os.path.dirname(out))}")
    pg.locator(".dialog-foot input").fill(os.path.basename(out))
    pg.locator(".dialog-foot .btn.primary").click()
    for _ in range(40):
        if os.path.exists(out):
            break
        pg.wait_for_timeout(250)
    data = open(out, "rb").read()
    assert data.startswith(b"\x89PNG")
    # a real picture, not an empty canvas: many colours, and object A's red model in it
    import numpy as np
    from PIL import Image
    im = np.asarray(Image.open(out).convert("RGB")).astype(int).reshape(-1, 3)
    assert len(np.unique(im, axis=0)) > 100
    assert ((im[:, 0] > 180) & (im[:, 1] < 90) & (im[:, 2] < 90)).sum() > 20


def test_remove_the_3d_view_and_undo(g3multi):
    pg = g3multi
    P = "window.__sv.state().ws.tabs[0].plots[0]"
    pg.locator(".globe3d-bar button[aria-label='Remove the 3D view']").click()
    pg.wait_for_selector(".globe3d", state="detached")
    assert pg.evaluate(f"[{P}.mode, {P}.objects.length]") == ["time", 0]
    pg.keyboard.press("Control+z")                                              # back, with its objects
    pg.wait_for_selector(".globe3d-bar", timeout=60000)
    assert pg.evaluate(f"[{P}.mode, {P}.objects.length]") == ["3d", 3]
    # "Clear plot" works on a plot that holds only objects (it was disabled for it)
    pg.locator(".plot .plot-more").first.click()
    item = pg.locator(".plot .menu[role=menu] button", has_text="Clear plot")
    assert item.is_enabled()
    item.click()
    assert pg.evaluate(f"[{P}.mode, {P}.objects.length]") == ["3d", 0]
