"""
Screenshots for the README and the docs (docs/images), made from the app itself:
it starts Signal Viewer on the example files with an empty home folder, drives it with Playwright
and takes the shots. Run it before a release so the pictures show the current interface.

    python tools/make_readme_media.py                 # everything
    python tools/make_readme_media.py --only 01 14    # names starting with these
    python tools/make_readme_media.py --only examples # W1 / W2: the welcome screen's card pictures
    SV_CHROMIUM=/path/to/chrome python tools/make_readme_media.py

Needs: playwright (+ a Chromium). The README's short films (45, 46: GIF, made frame by frame) need ffmpeg too;
the long films are made by make_demo_video.py / make_training_video.py.
Not made here (kept from a real screen): 06_3d_terrain.png - a headless browser draws the 3D view
on software WebGL. The map scenes (05, 28, 31) use OpenStreetMap's tiles and 44 Esri's satellite photos with the
terrain: run them on a computer with the internet (`--only 05 28 31 44`, then tools/make_social_preview.py),
else the map is empty.
Every picture is in the dark theme (owner, 1.22.0).
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMAGES = os.path.join(ROOT, "docs", "images")
MEDIA = os.path.join(ROOT, "docs", "media")          # the films (make_demo_video.py)
W, H = 1600, 900


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class App:
    """The app on a free port, with its own empty home (no autosave, no recent files)."""

    def __init__(self):
        self.home = tempfile.mkdtemp(prefix="sv-media-home-")
        self.data = tempfile.mkdtemp(prefix="sv-media-data-")
        for f in os.listdir(os.path.join(ROOT, "examples")):          # the examples' folders too (investigate/, sweeps/...)
            src = os.path.join(ROOT, "examples", f)
            (shutil.copytree(src, os.path.join(self.data, f)) if os.path.isdir(src) else shutil.copy(src, self.data))
        # a flight log with findings for the health check (vibration, EKF, errors)
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_test_bin.py"), os.path.join(self.data, "flight.bin"),
                        "--seconds", "120"], check=True, capture_output=True)
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        env = {**os.environ, "HOME": self.home, "USERPROFILE": self.home, "SV_EXAMPLES": self.data}
        self.proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "run.py"), "--port", str(self.port), "--no-open"],
                                     cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(240):
            try:
                urllib.request.urlopen(self.url, timeout=1)
                return
            except Exception:
                time.sleep(0.5)
        raise RuntimeError("the app did not start")

    def path(self, name):
        return os.path.join(self.data, name)

    def close(self):
        self.proc.terminate()
        shutil.rmtree(self.home, ignore_errors=True)
        shutil.rmtree(self.data, ignore_errors=True)


# ----------------------------------------------------------------------------- helpers
def reset(app):
    """Every scene starts clean: close the files earlier scenes opened (one server for all)."""
    try:                                           # a MAVLink link an earlier scene left running
        urllib.request.urlopen(urllib.request.Request(app.url + "/api/mavlink/stop", data=b"{}", method="POST",
                                                      headers={"Content-Type": "application/json"}))
    except Exception:
        pass
    runs = json.loads(urllib.request.urlopen(app.url + "/api/runs").read())
    for r in runs:
        if r.get("format") != "derived":
            urllib.request.urlopen(urllib.request.Request(f"{app.url}/api/runs/{r['id']}", method="DELETE"))
    for name in ("autosave.json", "ui_settings.json", "sweep_autosave.json", "recent.json"):   # settings too (1.8: kept in the app folder) -
        try:                                             # the Hebrew scene must not leave the next ones in Hebrew
            os.remove(os.path.join(app.home, ".signalviewer", name))
        except OSError:                                  # (recent files: a picture shows the welcome as a new user sees it)
            pass


def page(browser, app, dark=True, scale=1):   # owner (1.22.0): every picture in the dark theme
    reset(app)
    ctx = browser.new_context(viewport={"width": W, "height": H}, color_scheme="dark" if dark else "light", device_scale_factor=scale)
    pg = ctx.new_page()
    pg.goto(app.url)
    pg.wait_for_selector(".app")
    pg.wait_for_timeout(400)
    return ctx, pg


def S(pg, expr):
    return pg.evaluate(f"(() => {{ const s = window.__sv.state(); return {expr}; }})()")


def open_api(pg, app, *names):
    """Open files the quick way (no dialog): the open endpoint, then the run list into the UI."""
    paths = [app.path(n) for n in names]
    pg.evaluate("""async (paths) => {
      await fetch('/api/files/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({paths})});
      const runs = await (await fetch('/api/runs')).json();
      window.__sv.setState({ runs });
    }""", paths)
    pg.wait_for_selector(".run-head")              # (a log's groups start closed: no signal row may show)
    pg.wait_for_timeout(300)


def open_dialog(pg, app, *names, slow=False):
    """Open files the way a user does: Ctrl+O, the folder, the files, Open."""
    pg.keyboard.press("Control+o")
    pg.wait_for_function("document.querySelector('.crumbs input') && document.querySelector('.crumbs input').value !== ''")
    pg.fill(".crumbs input", app.data)
    pg.press(".crumbs input", "Enter")
    pg.wait_for_timeout(500 if slow else 200)
    for i, n in enumerate(names):
        pg.locator(".dialog .dialog-body .fs-row", has_text=n).first.click(modifiers=["Control"] if i else [])
        pg.wait_for_timeout(300 if slow else 50)
    pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function(f"window.__sv.state().runs.filter(r => r.format !== 'derived').length >= {len(names)}")
    pg.wait_for_timeout(600)


def sig(pg, name, nth=0):
    return pg.locator(".sig", has_text=name).nth(nth)


def layout(pg, r, c):
    pg.click(".stage-bar .layout-btn")
    pg.click(f"[aria-label='Layout {r} × {c}']")
    pg.wait_for_timeout(200)


def select_plot(pg, k):
    pg.keyboard.press(str(k))
    pg.wait_for_timeout(80)


def apply_template(pg, tid):
    pg.evaluate(f"window.__sv.setState({{ templatesOpen: true, templatesSelect: {json.dumps(tid)} }})")
    btn = pg.locator(".tpl-actions .btn.primary")
    btn.wait_for()
    pg.wait_for_function("!document.querySelector('.tpl-actions .btn.primary').disabled")
    btn.click()
    pg.wait_for_function("!document.querySelector('.tpl-details')")
    pg.wait_for_timeout(1500)


def cursors(pg, t1, t2):
    pg.evaluate(f"window.__sv.setState({{ cursor: {{ on: true, dual: true, t1: {t1}, t2: {t2}, active: 1 }} }})")
    pg.wait_for_timeout(500)


def no_toasts(pg):
    pg.evaluate("document.querySelectorAll('.toast button[aria-label]').forEach(b => b.click())")
    pg.wait_for_timeout(200)


# a headless browser draws 3D on software WebGL: its "reduced quality" badge and the camera's one-line help
# are true on screen but not what the pictures are about
SHOT_HIDE = ".globe3d-light, .g3-cam-hint { display: none !important; }"


def shot(pg, name):
    no_toasts(pg)
    pg.add_style_tag(content=SHOT_HIDE)
    pg.mouse.move(W - 5, H - 5)
    pg.wait_for_timeout(300)
    path = os.path.join(IMAGES, name + ".png")
    pg.screenshot(path=path)
    print("image", os.path.relpath(path, ROOT))




def sweeps_fresh(pg):
    """The Sweeps area with no study open (the studies are kept from the last scene)."""
    pg.locator(".areas .area-btn", has_text="Sweeps").click()
    pg.wait_for_selector(".sw-welcome, .sw-study-wrap")
    if pg.locator(".sw-pills .sw-tbl-pill .x").count():                  # Clear > Everything (1.20)
        pg.locator(".sw-clear-btn").click()
        pg.locator(".menu.ctx button", has_text="Everything").click()
        pg.locator(".dialog-foot .btn").last.click()
    pg.wait_for_selector(".sw-welcome")
    no_toasts(pg)


def img_25_sweeps_data(b, app):
    """Sweeps / Data: the example's two sweeps as two tables and a third, merged with a source column;
    the merge box and Continue with in the side panel, the merged table's parallel plot."""
    ctx, pg = page(b, app)
    sweeps_fresh(pg)
    pg.locator(".sw-welcome .btn", has_text="two sweeps, merged").click()
    pg.wait_for_function("document.querySelectorAll('.sw-table-item').length === 3")
    for box in pg.locator(".sw-table-item input[type=checkbox]").all()[:2]:
        box.check()
    pg.locator(".sw-center-tabs button", has_text="Parallel plot").click()
    pg.wait_for_selector(".pp canvas"); pg.locator(".pp-axis-name", has_text="_source").first.click()
    pg.wait_for_selector(".sw-merge-preview"); pg.wait_for_timeout(600)
    shot(pg, "25_sweeps_data"); ctx.close()


def img_26_sweeps_split(b, app):
    """Sweeps / Results split by payload: one value of the condition, the best set per value."""
    ctx, pg = page(b, app)
    sweeps_fresh(pg)
    pg.locator(".sw-welcome .btn", has_text="Try an example").click()
    pg.wait_for_selector(".sw-steps")
    pg.locator(".sw-step-btn[data-step='roles']").click()
    card = pg.locator(".sw-cond-card", has_text="scenario_payload_kg")
    card.locator("summary").click(); card.locator(".sw-split-toggle input").check()
    pg.locator(".sw-step-btn[data-step='goals']").click()
    for col, v in (("roll_error_deg", 5), ("overshoot_pct", 15)):
        box = pg.locator(f"input[aria-label='{col} at most']"); box.fill(str(v)); box.press("Enter")
        pg.locator(f".sw-goal-table tr[data-col='{col}'] .sw-limit-met").first.wait_for()
    pg.locator("select[aria-label='Optimize energy_wh']").select_option("min")
    pg.locator(".sw-step-btn[data-step='results']").click()
    bar = pg.locator(".sw-split-bar"); bar.wait_for()
    bar.locator(".sw-pill").nth(2).click()
    bar.locator(".linklike", has_text="Best set per value").click()
    pg.wait_for_selector(".sw-split-table tbody tr"); pg.wait_for_timeout(800)
    shot(pg, "26_sweeps_split"); ctx.close()


# ----------------------------------------------------------------------------- scenes
def overview(pg, app):
    open_api(pg, app, "run_012.csv")
    layout(pg, 2, 2)
    for k, n in ((1, "Speed"), (2, "RPM"), (3, "Throttle"), (4, "EngineTemp")):
        select_plot(pg, k); sig(pg, n).click(); pg.wait_for_timeout(150)
    sig(pg, "DriveMode").click()                              # a text signal into plot 4: a state lane
    cursors(pg, 18, 34)
    pg.evaluate("window.__sv.setState({ inspectorOpen: true })")
    pg.wait_for_timeout(600)


def img_01_overview(b, app):
    ctx, pg = page(b, app); overview(pg, app); shot(pg, "01_overview"); ctx.close()


def img_02_dark_theme(b, app):
    ctx, pg = page(b, app, dark=True); overview(pg, app); shot(pg, "02_dark_theme"); ctx.close()


def compare_view(pg, app):
    open_api(pg, app, "run_012.csv", "run_013.csv", "run_014.csv")
    pg.click("[aria-label='Compare runs']")
    pg.wait_for_selector(".sim-row", timeout=30000)
    pg.wait_for_timeout(500)
    pg.locator(".sim-row").first.click()
    pg.wait_for_timeout(1200)


def img_03_compare_runs(b, app):
    ctx, pg = page(b, app); compare_view(pg, app); shot(pg, "03_compare_runs"); ctx.close()


def img_04_comparison_table(b, app):
    ctx, pg = page(b, app); compare_view(pg, app)
    pg.locator(".cmp-panel button", has_text="Table of all signals").first.click()
    pg.wait_for_selector(".cmp-dialog"); pg.wait_for_timeout(800)
    shot(pg, "04_comparison_table"); ctx.close()


def img_05_map_and_3d(b, app):
    ctx, pg = page(b, app); open_api(pg, app, "uav_flight.csv")
    apply_template(pg, "bi-position")
    pg.evaluate("window.__sv.setState({ geoBase: 'osm' })")      # OpenStreetMap's colours (needs the internet)
    cursors(pg, 160, 160); pg.wait_for_timeout(8000)               # the terrain and the map tiles load
    for _ in range(2):              # until the 3D's tiles are refined (a fixed wait left them blurred on software WebGL)
        pg.wait_for_function("!!window.__svGlobe && window.__svGlobe.widget.scene.globe.tilesLoaded", timeout=60000)
        pg.wait_for_timeout(1500)
    shot(pg, "05_map_and_3d"); ctx.close()


# 06_3d_terrain.png is not made here: in a headless browser the 3D view runs on software WebGL and
# its camera cannot be placed reliably; that picture is kept from a real screen.


def img_07_ardupilot_attitude(b, app):
    ctx, pg = page(b, app); open_api(pg, app, "flight.bin")
    apply_template(pg, "bi-ap-attitude"); cursors(pg, 30, 30)
    shot(pg, "07_ardupilot_attitude"); ctx.close()


def img_08_vibration_spectrogram(b, app):
    ctx, pg = page(b, app); open_api(pg, app, "flight.bin")
    apply_template(pg, "bi-ap-vibration"); pg.wait_for_timeout(1500)
    shot(pg, "08_vibration_spectrogram"); ctx.close()


def log_panel(pg, app, tab):
    open_api(pg, app, "flight.bin")
    apply_template(pg, "bi-ap-vibration")
    pg.evaluate("window.__sv.setState({ panel: 'log', startCard: null })")
    pg.wait_for_selector(".log-panel, .health, [role='tab']")
    ids = {"Health": "health", "Events": "events", "Parameters": "params", "File": "file"}       # D7: the Checks view's tabs
    pg.locator(f"[role='tab'][data-tab='{ids.get(tab, tab)}']").first.click()
    pg.wait_for_timeout(1200)


def img_09_health_check(b, app):
    ctx, pg = page(b, app); log_panel(pg, app, "Health"); shot(pg, "09_health_check"); ctx.close()


def img_10_log_events(b, app):
    ctx, pg = page(b, app); log_panel(pg, app, "Events"); shot(pg, "10_log_events"); ctx.close()


def img_11_formula_editor(b, app):
    ctx, pg = page(b, app); open_api(pg, app, "run_012.csv")
    sig(pg, "Speed").click(); sig(pg, "RPM").click()
    pg.click("[aria-label='Create signals']")
    pg.locator(".analysis .seg.wide button", has_text="Formula").click()
    box = pg.locator(".analysis .fx-input textarea, .analysis .fx-input input, .analysis textarea").first
    box.click(); box.type("2*Speed - RP", delay=40)
    pg.wait_for_timeout(900)
    shot(pg, "11_formula_editor"); ctx.close()


def img_12_hebrew_rtl(b, app):
    ctx, pg = page(b, app); overview(pg, app)
    pg.locator("header.topbar .btn", has_text="עברית").click(); pg.wait_for_timeout(800)
    shot(pg, "12_hebrew_rtl"); ctx.close()


def img_13_template_library(b, app):
    ctx, pg = page(b, app); open_api(pg, app, "flight.bin")
    pg.evaluate("window.__sv.setState({ startCard: null, templatesOpen: true, templatesSelect: 'bi-ap-review' })")
    pg.wait_for_selector(".tpl-details"); pg.wait_for_function("!document.querySelector('.tpl-actions .btn.primary').disabled")
    pg.wait_for_timeout(600)
    shot(pg, "13_template_library"); ctx.close()


def img_14_smart_start(b, app):
    ctx, pg = page(b, app); open_dialog(pg, app, "flight.bin")
    pg.wait_for_selector(".start-card", timeout=20000); pg.wait_for_timeout(600)
    shot(pg, "14_smart_start"); ctx.close()


def img_15_segment_compare(b, app):
    ctx, pg = page(b, app); open_api(pg, app, "run_012.csv", "run_013.csv", "run_014.csv")
    pg.click("[aria-label='Compare runs']")
    pg.locator(".cmp-panel .seg.wide button", has_text="A segment").click()
    pg.locator(".seg-pick label:has-text('State signal') select").select_option("Gear")
    pg.wait_for_timeout(500)
    vals = pg.locator(".seg-pick label:has-text('Value') select option").all_inner_texts()
    pg.locator(".seg-pick label:has-text('Value') select").select_option(label=vals[min(3, len(vals) - 1)])
    pg.wait_for_selector(".sim-row", timeout=30000); pg.wait_for_timeout(600)
    pg.locator(".sim-row", has_text="Speed").first.click(); pg.wait_for_timeout(1500)
    shot(pg, "15_segment_compare"); ctx.close()


def fake_vehicle(port, stop):
    """An ArduCopter on UDP that circles and climbs: HEARTBEAT, ATTITUDE, GLOBAL_POSITION_INT, VFR_HUD."""
    import math
    from pymavlink.dialects.v20 import ardupilotmega as mavlink
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    mav = mavlink.MAVLink(None, srcSystem=1, srcComponent=1)
    t0, k = time.time(), 0
    while not stop.is_set():
        a = time.time() - t0
        ms = int(a * 1000)
        if k % 10 == 0:
            s.sendto(mav.heartbeat_encode(2, 3, 81 | 128, 4, 4).pack(mav), ("127.0.0.1", port))
        s.sendto(mav.attitude_encode(ms, 0.25 * math.sin(a * 0.9), 0.12 * math.cos(a * 1.3), (a * 0.4) % 6.28, 0, 0, 0).pack(mav), ("127.0.0.1", port))
        s.sendto(mav.global_position_int_encode(ms, int((32.8 + 0.0008 * math.sin(a * 0.2)) * 1e7), int((35.6 + 0.0008 * math.cos(a * 0.2)) * 1e7),
                                                int((60 + 2 * a) * 1000), int((20 + 2 * a) * 1000), 0, 0, 0, 0).pack(mav), ("127.0.0.1", port))
        s.sendto(mav.vfr_hud_encode(8 + math.sin(a), 8 + math.sin(a), int(a * 23) % 360, 55, 20 + 2 * a, 1.5).pack(mav), ("127.0.0.1", port))
        k += 1
        time.sleep(0.05)
    s.close()


def live_mavlink(pg, app, seconds=8.0):
    port = free_port()
    pg.click(".live-more"); pg.wait_for_timeout(300)
    pg.locator(".mav-section:not(.link-section) input[list]").fill(f"udpin:127.0.0.1:{port}")
    pg.get_by_role("button", name="Connect and record").click()
    stop = threading.Event()
    th = threading.Thread(target=fake_vehicle, args=(port, stop), daemon=True); th.start()
    pg.wait_for_function("window.__sv.state().runs.some(r => r.format === 'tlog')", timeout=20000)
    pg.keyboard.press("Escape"); pg.mouse.click(W // 2, H - 30)
    layout(pg, 2, 1)
    select_plot(pg, 1); sig(pg, "ATTITUDE.roll").click(); sig(pg, "ATTITUDE.pitch").click()
    select_plot(pg, 2); sig(pg, "VFR_HUD.alt").click()
    pg.evaluate("window.__sv.setState({ follow: 30 })")
    pg.wait_for_timeout(int(seconds * 1000))
    return stop


def img_16_live_mavlink(b, app):
    ctx, pg = page(b, app); stop = live_mavlink(pg, app)
    pg.click(".mav-pill"); pg.wait_for_timeout(600)
    shot(pg, "16_live_mavlink"); stop.set(); ctx.close()


def img_17_fft_motor_orders(b, app):
    import numpy as np
    t = np.arange(0, 6, 0.001)
    acc = (np.sin(2 * np.pi * 95 * t) + 0.45 * np.sin(2 * np.pi * 190 * t) + 0.2 * np.sin(2 * np.pi * 285 * t)
           + 0.3 * np.random.default_rng(1).standard_normal(len(t)))
    np.savetxt(app.path("motor.csv"), np.column_stack([t, 5700 + 30 * np.sin(t), acc]), delimiter=",",
               header="Time,ESC.RPM,IMU.AccZ [m/s/s]", comments="", fmt="%.6g")
    ctx, pg = page(b, app); open_api(pg, app, "motor.csv")
    sig(pg, "IMU.AccZ").click()
    pg.wait_for_selector(".plot .u-over")
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="FFT").first.click()
    pg.wait_for_selector(".plot select[aria-label='Motor orders']")
    pg.locator(".plot select[aria-label='Motor orders']").select_option(label="ESC.RPM")
    pg.locator(".plot select[aria-label='Propeller blades']").select_option("2")
    pg.wait_for_timeout(1200)
    shot(pg, "17_fft_motor_orders"); ctx.close()


def img_23_sweeps_goal(b, app):
    """Sweeps: the example's goal as one table (roll error <= 5 and overshoot <= 15 in every scenario,
    kp_roll at most 0.25, the least energy) - the count and the best set beside it."""
    ctx, pg = page(b, app)
    pg.locator(".areas .area-btn", has_text="Sweeps").click()
    pg.locator(".sw-welcome .btn", has_text="Try an example").click()
    pg.wait_for_selector(".sw-steps")
    pg.locator(".sw-step-btn[data-step='goals']").click()
    for col, v in (("roll_error_deg", 5), ("overshoot_pct", 15), ("kp_roll", 0.25)):
        box = pg.locator(f"input[aria-label='{col} at most']"); box.fill(str(v)); box.press("Enter")
        pg.locator(f".sw-goal-table tr[data-col='{col}'] .sw-limit-met").first.wait_for()
    pg.locator("select[aria-label='Optimize energy_wh']").select_option("min")
    pg.wait_for_selector(".sw-side-step .sw-best:has-text('kp_roll = ')"); pg.wait_for_timeout(600)
    shot(pg, "23_sweeps_goal"); ctx.close()


def img_18_frames(b, app):
    ctx, pg = page(b, app); open_api(pg, app, "uav_flight.csv")
    pg.get_by_placeholder("Search signals").fill("GPS.Alt")          # D2: the list groups by prefix
    sig(pg, "Alt").click()
    pg.click("[aria-label='Create signals']")
    pg.locator(".analysis .seg.wide button", has_text="Frames").click(); pg.wait_for_timeout(400)
    pg.locator(".seg.wide button", has_text="A plot per axis").click()
    pg.get_by_role("button", name="Preview", exact=True).click()
    pg.wait_for_selector(".pv-plot canvas", timeout=20000); pg.wait_for_timeout(1200)
    shot(pg, "18_frames"); ctx.close()






# ----------------------------------------------------------------------------- 1.20 (the owner's notes)
def _many_signals(pg, app, n=30):
    """copter_flight.bin with n of its signals in one plot (an investigation)."""
    open_api(pg, app, "copter_flight.bin")
    pg.evaluate("""(n) => { const st = window.__sv.state(); const r = st.runs[0];
      const ids = r.signals.map((x) => x.id).filter((id) => /[/](ATT|RATE|IMU|VIBE|CTUN|RCOU)/.test(id)).slice(0, n);
      const pal = ['#3D8BFD','#F07B3F','#2FBF9F','#E5677A','#9B7BFF','#B8A33A','#4FC3E8','#D08CE8','#7CC35A','#FF8FB1'];
      st.commit((ws) => { ws.tabs[0].plots[0].signals = ids.map((id, i) => ({ sig: id, color: pal[i % 10], width: 1.5, scale: 1, offset: 0 })); return ws; }); }""", n)
    pg.wait_for_selector(".legend-side .lrow"); pg.wait_for_timeout(1200)


def img_27_legend_side(b, app):
    """30 signals in one plot: the legend in a column beside it, the values aligned, one line in front."""
    ctx, pg = page(b, app)
    _many_signals(pg, app)
    pg.evaluate("window.__sv.setState({ cursor: { on: true, dual: false, t1: 150, t2: null } })"); pg.wait_for_timeout(800)
    pg.locator(".legend-side .lrow").nth(1).hover(); pg.wait_for_timeout(400)
    no_toasts(pg)
    path = os.path.join(IMAGES, "27_legend_side.png"); pg.screenshot(path=path); print("image", os.path.relpath(path, ROOT))
    ctx.close()


def img_28_map_by_mode(b, app):
    """The copter's track on the map coloured by its flight mode, with the key."""
    ctx, pg = page(b, app)
    open_api(pg, app, "copter_flight.bin")
    rid = S(pg, "s.runs[0].id")
    obj = {"id": "o1", "name": "Copter", "kind": "drone", "color": "#E5677A", "lat": f"{rid}/GPS[0].Lat [deg]",
           "lon": f"{rid}/GPS[0].Lng [deg]", "alt": f"{rid}/GPS[0].Alt [m]", "trail": True, "trackColor": "state", "colorSig": f"{rid}/MODE.Mode"}
    pg.evaluate("""(o) => window.__sv.state().commit((ws) => { const p = ws.tabs[0].plots[0];
        p.mode = 'geo'; p.xSignal = o.lon; p.signals = [{sig: o.lat, color: '#3D8BFD', width: 1.5, scale: 1, offset: 0}]; p.objects = [o]; return ws; })""", obj)
    pg.evaluate("window.__sv.setState({ geoBase: 'osm' })")      # OpenStreetMap's colours (needs the internet)
    pg.wait_for_selector(".track-key", timeout=30000); pg.wait_for_timeout(2500)
    pg.locator(".plot").first.hover()                         # the map's bar shows on the map in use
    pg.locator(".geo-fit").first.click()                      # framed on the whole track (a short copter flight)
    pg.wait_for_timeout(1500)
    if pg.evaluate("!!window.__svGlobe"):
        pg.wait_for_function("window.__svGlobe.widget.scene.globe.tilesLoaded", timeout=60000)
    pg.mouse.move(5, H - 5); pg.wait_for_timeout(2500)
    shot(pg, "28_map_by_mode"); ctx.close()


def img_00_hero(b, app):
    """1.23: the README's first picture - judging a flight against its simulation (the release's main
    flow), dark, at 2x: the model (the golden run, ★) and the flight overlaid in four plots, Compare's
    verdict (2 of 7 signals outside the tolerances file the command line reads) and the worst failure's
    difference over time with its band. Offline (no map tiles). The flight / map / 3D picture of
    1.22 is 31_flight_map_3d (img_31_flight_map_3d, needs the internet for its map)."""
    reset(app)
    ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=2, color_scheme="dark")
    pg = ctx.new_page()
    pg.goto(app.url); pg.wait_for_selector(".app"); pg.wait_for_timeout(400)
    pg.evaluate("window.__sv.setState({ theme: 'dark' })")
    sim, flight = app.path("sim_vs_flight/sim_attitude_doublets.mat"), app.path("sim_vs_flight/flight_attitude_doublets.bin")
    open_api(pg, app, "sim_vs_flight/sim_attitude_doublets.mat", "sim_vs_flight/flight_attitude_doublets.bin")
    ids = pg.evaluate("""async ([sim, flight, tol]) => {
      const runs = await (await fetch('/api/runs')).json();
      const s = runs.find((r) => r.path === sim), f = runs.find((r) => r.path === flight);
      await fetch('/api/runs/' + f.id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ timeOffset: -104.369 }) });
      const t = await (await fetch('/api/compare/tolerances/load', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: tol }) })).json();
      window.__sv.setState({ runs: await (await fetch('/api/runs')).json(), compareTol: t.tolerances, startCard: null });
      return [s.id, f.id]; }""", [sim, flight, app.path("sim_vs_flight/tolerances.json")])
    # the differences (flight - model), with the tolerance (3 deg) as their limits: where it fails shows
    ids += pg.evaluate("""async ([s, f]) => { const made = [];
      for (const [a, b, n] of [['ATT.Roll [deg]', 'ATT.Roll', 'Δ Roll'], ['ATT.Pitch [deg]', 'ATT.Pitch', 'Δ Pitch']]) {
        const r = await (await fetch('/api/derived', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ op: 'sub', sources: [`${f}/${a}`, `${s}/${b}`], params: { alignment: 'linear', pinned: [1] }, name: n }) })).json();
        window.__sv.setState({ runs: r.runs }); made.push(r.id); }
      return made; }""", ids)
    pg.evaluate("""([s, f, dr, dp]) => window.__sv.state().commit((ws) => {
      const tab = ws.tabs[0];
      const pair = (id, title, a, b) => ({ id, title, signals: [
        { sig: `${s}/${a}`, color: '#58A6FF', width: 4, scale: 1, offset: 0, dash: false, label: 'Model ★' },
        { sig: `${f}/${b}`, color: '#F2A33A', width: 1.5, scale: 1, offset: 0, label: 'Flight' }] });
      const diff = (id, title, sig, color) => ({ id, title, signals: [{ sig, color, width: 1.25, scale: 1, offset: 0, limits: { lo: -3, hi: 3 } }] });
      tab.name = 'Model vs flight';
      tab.plots = [pair('h-roll', 'Roll (deg)', 'ATT.Roll', 'ATT.Roll [deg]'), pair('h-pitch', 'Pitch (deg)', 'ATT.Pitch', 'ATT.Pitch [deg]'),
                   diff('h-droll', 'Roll: flight − model, tolerance ±3', dr, '#FF7B72'), diff('h-dpitch', 'Pitch: flight − model, tolerance ±3', dp, '#56D364')];
      tab.rows = 2; tab.cols = 2; tab.linkX = true; tab.active = 2;
      return ws; })""", ids)
    pg.evaluate("() => { const t = window.__sv.state().ws.tabs[0]; window.__sv.setState({ ranges: { [t.id]: [0, 95] } }); }")
    if pg.locator(".ov-head .ov-hide").count():                     # the overview strip: room for the plots
        pg.locator(".ov-head .ov-hide").first.click(force=True)
    pg.click("[aria-label='Compare runs']")
    pg.wait_for_selector(".judge-verdict li", timeout=60000)
    pg.locator(".golden-mark input").check()                        # the model is the golden run
    pg.locator(".cmp-panel").evaluate("e => e.scrollTop = 0")
    # the cursor on the worst place: the flight's roll 6.1 deg from the model's at 31.17 s (outside +-3)
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: false, t1: 31.171, t2: null, active: 1 } })")
    pg.wait_for_timeout(2500)
    shot(pg, "00_hero"); ctx.close()


def img_31_flight_map_3d(b, app):
    """M1 (1.22's first picture): one window, 2 x 2, dark, at 2x: the map (drawn in 3D since 1.28) with the track
    coloured by the flight mode and the vehicle at the cursor; altitude and Roll desired vs actual with
    the mode lane; the vibration behind the health check's finding - the cursor at the vibration
    (~140 s of the ArduPilot example), the findings docked beside the timeline. No signal list, no
    popups. tools/make_social_preview.py crops docs/images/social-preview.png from it."""
    reset(app)
    ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=2, color_scheme="dark")
    pg = ctx.new_page()
    pg.goto(app.url); pg.wait_for_selector(".app"); pg.wait_for_timeout(400)
    pg.evaluate("window.__sv.setState({ theme: 'dark' })")
    pg.locator(".ex-card[data-example='ardupilot']").click()                  # as a user starts: the example
    pg.wait_for_selector(".findings-dock", timeout=60000)
    pg.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.name === 'Flight')")
    rid = S(pg, "s.runs.find((r) => r.format === 'bin').id")
    pg.evaluate("""(rid) => window.__sv.state().commit((ws) => {
      const tab = ws.tabs.find((t) => t.name === 'Flight');
      const sig = (n) => `${rid}/${n}`;
      const line = (n, color, width = 1.5) => ({ sig: sig(n), color, width, scale: 1, offset: 0 });
      for (const p of tab.plots) {
        for (const o of p.objects || []) { o.trackColor = 'state'; o.colorSig = sig('MODE.Mode'); o.trail = true; }
        if (p.mode === '3d') { p.showReadout = false; p.showEvents = false; p.followObject = null; }   // General camera: the whole track
      }
      tab.rows = 2; tab.cols = 2; tab.rowSizes = [1.15, 1]; tab.linkX = true;
      tab.sharedStates = [sig('MODE.Mode')];
      tab.plots.push(                                   // 1.28: the tab has one map (its cameras cover 3D)
        { id: 'hero-alt', title: 'Altitude', signals: [line('CTUN.DAlt [m]', '#8FA3B8', 1.25), line('CTUN.Alt [m]', '#58A6FF', 1.75)] },
        { id: 'hero-roll', title: 'Roll', signals: [line('ATT.DesRoll [deg]', '#8FA3B8', 1.25), line('ATT.Roll [deg]', '#F2A33A', 1.75)] },
        { id: 'hero-vibe', title: 'Vibration', signals: [line('VIBE[0].VibeX [m/s/s]', '#4C9AFF'), line('VIBE[0].VibeY [m/s/s]', '#3FB950'),
          line('VIBE[0].VibeZ [m/s/s]', '#E5534B')] });
      ws.activeTab = tab.id; tab.active = 2;
      tab.plots = [tab.plots[0], tab.plots[tab.plots.length - 3], tab.plots[tab.plots.length - 2], tab.plots[tab.plots.length - 1]];
      return ws; })""", rid)
    # the map in OpenStreetMap's colours (owner: more inviting than the dark automatic one)
    # (1.23: SV_HERO_MAP=auto - the offline map, on a computer without the internet)
    pg.evaluate("b => window.__sv.setState({ panel: null, startCard: { ...window.__sv.state().startCard }, findingsOpen: false, geoBase: b })",
                os.environ.get("SV_HERO_MAP", "osm"))
    cursors(pg, 140.4, 140.4)
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, dual: false, t2: null } })")
    pg.wait_for_selector(".track-key", timeout=30000); pg.wait_for_timeout(4000)
    # the 3D as the owner's example (2026-11-07): General camera, the whole track at an angle (the
    # default view looks down ~35 deg), brought closer with the wheel so the track fills the plot. The
    # wheel zooms toward the mouse, so it points at the middle of the track (projected from the scene's
    # track lines), not at the plot's middle - else the track drifts out of the view (and 3 steps
    # at the plot's middle went down into the ground). The tiles are loaded first.
    pg.wait_for_function("!!window.__svGlobe && window.__svGlobe.widget.scene.globe.tilesLoaded", timeout=60000)
    xy = pg.evaluate("""() => { const { widget: w, Cesium: C } = window.__svGlobe; const pts = [];
      const walk = (c) => { for (let i = 0; i < c.length; i++) { const p = c.get(i);
        if (p instanceof C.PolylineCollection) for (let j = 0; j < p.length; j++) pts.push(...p.get(j).positions);
        else if (p instanceof C.PrimitiveCollection) walk(p); } };
      walk(w.scene.primitives);
      if (!pts.length) return null;
      const s = C.SceneTransforms.worldToWindowCoordinates(w.scene, C.BoundingSphere.fromPoints(pts).center);
      const r = w.canvas.getBoundingClientRect();
      return s ? { x: r.left + s.x, y: r.top + s.y } : null; }""")
    g = pg.locator(".plot:has(.globe3d)").locator("canvas").first.bounding_box()
    pg.mouse.move(*((xy["x"], xy["y"]) if xy else (g["x"] + g["width"] / 2, g["y"] + g["height"] * 0.55)))
    for _ in range(2):
        pg.mouse.wheel(0, -240); pg.wait_for_timeout(200)
    pg.mouse.move(5, H - 5)
    pg.add_style_tag(content=".globe3d-bar { display: none !important }")      # a clean picture (the 3D's bar is in 28)
    pg.wait_for_timeout(8000)                                                   # the terrain, the map tiles, the 3D model
    shot(pg, "31_flight_map_3d"); ctx.close()


def img_44_satellite_flight(b, app):
    """RD2: the still (see _satellite)."""
    ctx, pg = _satellite(b, app, 2)
    shot(pg, "44_satellite_flight"); ctx.close()


def _satellite(b, app, scale, zoom=None):
    """RD2 (owner, 2026-11-17): the README's map picture - the ArduPilot example over the satellite photos in 3D,
    on the real terrain, the tiles all loaded; the cursor in the middle of the track (the vehicle there) and,
    under the map on the same time, altitude and roll (desired vs actual) with the flight modes. Needs the
    internet (Esri's photos, the AWS terrain); without it the map is empty."""
    reset(app)
    ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=scale, color_scheme="dark")
    pg = ctx.new_page()
    pg.goto(app.url); pg.wait_for_selector(".app"); pg.wait_for_timeout(400)
    pg.evaluate("window.__sv.setState({ theme: 'dark' })")
    pg.locator(".ex-card[data-example='ardupilot']").click()
    pg.wait_for_selector(".findings-dock", timeout=60000)
    pg.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.name === 'Flight')")
    rid = S(pg, "s.runs.find((r) => r.format === 'bin').id")
    pg.evaluate("""(rid) => window.__sv.state().commit((ws) => {
      const tab = ws.tabs.find((t) => t.name === 'Flight');
      const sig = (n) => `${rid}/${n}`;
      const line = (n, color, width = 1.5) => ({ sig: sig(n), color, width, scale: 1, offset: 0 });
      const map = tab.plots[0];
      for (const o of map.objects || []) { o.trackColor = 'state'; o.colorSig = sig('MODE.Mode'); o.trail = true; }
      if (map.mode === '3d') { map.showReadout = false; map.showEvents = false; map.followObject = null; }
      tab.plots = [map,
        { id: 'sat-alt', title: 'Altitude', signals: [line('CTUN.DAlt [m]', '#8FA3B8', 1.25), line('CTUN.Alt [m]', '#58A6FF', 1.75)] },
        { id: 'sat-roll', title: 'Roll', signals: [line('ATT.DesRoll [deg]', '#8FA3B8', 1.25), line('ATT.Roll [deg]', '#F2A33A', 1.75)] }];
      tab.rows = 3; tab.cols = 1; tab.rowSizes = [2.8, 1, 1]; tab.linkX = true;
      tab.sharedStates = [sig('MODE.Mode')];
      ws.activeTab = tab.id; tab.active = 1;
      return ws; })""", rid)
    pg.evaluate("() => window.__sv.setState({ panel: null, startCard: null, findingsOpen: false, geoBase: 'satellite' })")
    cursors(pg, 140.4, 140.4)
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, dual: false, t2: null } })")
    no_toasts(pg)
    pg.wait_for_function("!!window.__svGlobe && window.__svGlobe.widget.scene.globe.tilesLoaded", timeout=120000)
    xy = pg.evaluate("""() => { const { widget: w, Cesium: C } = window.__svGlobe; const pts = [];
      const walk = (c) => { for (let i = 0; i < c.length; i++) { const p = c.get(i);
        if (p instanceof C.PolylineCollection) for (let j = 0; j < p.length; j++) pts.push(...p.get(j).positions);
        else if (p instanceof C.PrimitiveCollection) walk(p); } };
      walk(w.scene.primitives);
      if (!pts.length) return null;
      const s = C.SceneTransforms.worldToWindowCoordinates(w.scene, C.BoundingSphere.fromPoints(pts).center);
      const r = w.canvas.getBoundingClientRect();
      return s ? { x: r.left + s.x, y: r.top + s.y } : null; }""")
    g = pg.locator(".plot:has(.globe3d)").locator("canvas").first.bounding_box()
    pg.mouse.move(*((xy["x"], xy["y"]) if xy else (g["x"] + g["width"] / 2, g["y"] + g["height"] * 0.55)))
    for _ in range(zoom if zoom is not None else int(os.environ.get("SV_SAT_ZOOM", "1"))):
        pg.mouse.wheel(0, -240 if zoom is None else -140); pg.wait_for_timeout(200)
    pg.mouse.move(5, H - 5)
    # a clean picture: the photo uncovered (the 3D bar, the vehicle's numbers box and the demo's line hidden)
    pg.add_style_tag(content=".globe3d-bar, .globe3d-readout, .demo-guide { display: none !important }")
    # the photos at full detail: wait until the globe has every tile, then a little longer
    pg.wait_for_timeout(3000)
    pg.wait_for_function("window.__svGlobe.widget.scene.globe.tilesLoaded", timeout=180000)
    pg.wait_for_timeout(int(os.environ.get("SV_SAT_WAIT", "15000")))
    return ctx, pg


# ----------------------------------------------------------------------------- RD3: short films for the README
def film(frames, name, fps=10, width=1200):
    """Frames (PNG files, in order) -> docs/images/<name>.gif: one palette for the whole film (no flicker),
    a pause on the last frame. ffmpeg needed."""
    d = os.path.dirname(frames[0])
    for i, f in enumerate(frames):
        os.replace(f, os.path.join(d, f"f{i:04d}.png"))
    for k in range(fps * 2):                                    # hold the end two seconds
        shutil.copy(os.path.join(d, f"f{len(frames) - 1:04d}.png"), os.path.join(d, f"f{len(frames) + k:04d}.png"))
    out = os.path.join(IMAGES, name + ".gif")
    vf = (f"scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=256:stats_mode=full[p];"
          f"[b][p]paletteuse=dither=sierra2_4a")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(d, "f%04d.png"),
                    "-vf", vf, "-loop", "0", out], check=True)
    shutil.rmtree(d, ignore_errors=True)
    print("film", os.path.relpath(out, ROOT), f"{os.path.getsize(out) // 1024} KB")


def frame(pg, d, frames):
    path = os.path.join(d, f"raw{len(frames):04d}.png")
    pg.screenshot(path=path); frames.append(path)


def img_46_satellite_replay(b, app):
    """RD3: the satellite picture as a film - the cursor runs through the flight: the vehicle moves along its
    track on the photos while the cursor moves in altitude and roll."""
    ctx, pg = _satellite(b, app, 1, zoom=1)        # at 1x a full wheel step comes closer than at 2x: a smaller one
    pg.add_style_tag(content=SHOT_HIDE)
    d, frames = tempfile.mkdtemp(prefix="sv-film-"), []
    t = 30.0
    while t <= 232:
        pg.evaluate("t => window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: false, t1: t, t2: null } })", t)
        pg.wait_for_timeout(180)
        frame(pg, d, frames); t += 2.5
    film(frames, "46_satellite_replay")
    ctx.close()


def img_45_sweeps_filter(b, app):
    """RD3: Sweeps as a film - All runs with every run shown (Show: All), then a filter narrows energy, then roll
    error: the lines kept, the count above the plot (810 -> about 60) and the table follow every step."""
    ctx, pg = page(b, app)
    _example(pg, "sweepTable", ".pp canvas", 1500)
    tab = pg.get_by_role("tab", name="All runs")
    if not tab.count():
        tab = pg.locator("button", has_text="All runs")
    tab.first.click(); pg.wait_for_timeout(2500)
    show = pg.locator("select:has(option:text-matches('^Holds'))").first           # Show: every run, not only the holding sets
    show.select_option(label=next(o for o in show.locator("option").all_inner_texts() if o.startswith("All")))
    pg.wait_for_function("window.__svSweeps.idle()", timeout=30000); pg.wait_for_timeout(800)
    pg.add_style_tag(content=SHOT_HIDE); pg.mouse.move(W - 5, H - 5)
    d, frames = tempfile.mkdtemp(prefix="sv-film-"), []

    def step(col, hi):
        pg.evaluate("([c, hi]) => window.__svSweeps.filter(c, { kind: 'ranges', ranges: [[0, hi]] })", [col, hi])
        pg.wait_for_function("window.__svSweeps.idle()", timeout=30000); pg.wait_for_timeout(250)
        frame(pg, d, frames)
    for _ in range(4):
        frame(pg, d, frames)                                     # the whole table first
    for hi in (110, 85, 65, 55, 50, 47, 45, 43):
        step("energy_wh", hi)
    frame(pg, d, frames)
    for hi in (4.5, 4, 3.5, 3.2, 3, 2.8, 2.6):
        step("roll_error_deg", hi)
    film(frames, "45_sweeps_filter", fps=3)
    ctx.close()


def _pareto(pg):
    pg.locator(".areas .area-btn", has_text="Sweeps").click()
    pg.locator(".sw-welcome .btn", has_text="Try an example").click()
    pg.wait_for_selector(".sw-steps")
    pg.locator(".sw-step-btn[data-step='goals']").click(); pg.wait_for_timeout(500)
    pg.locator("select[aria-label='Optimize energy_wh']").select_option("min"); pg.wait_for_timeout(700)
    pg.locator("select[aria-label='Optimize roll_error_deg']").select_option("min"); pg.wait_for_timeout(700)
    pg.locator(".sw-rankby select").select_option("pareto"); pg.wait_for_timeout(900)


def img_30_sweeps_pareto(b, app):
    """Sweeps: two objectives - the Pareto front, the balanced set starred."""
    ctx, pg = page(b, app)
    _pareto(pg)
    pg.locator(".sw-rankby .btn").click(); pg.wait_for_timeout(1500)
    shot(pg, "30_sweeps_pareto"); ctx.close()





# ----------------------------------------------------------------------------- 1.28: the tutorials' pictures
# the examples off the welcome screen (FR11), by their label in Help -> Examples
MENU_LABEL = {"flight": "a drone flight", "car": "three car runs", "bench": "a pump on a test bench",
              "sweepTable": "a sweep: which settings hold", "commonGains": "one gain set, three drones"}


def _example(pg, ex, ready, settle=1200):
    """Open a welcome-screen example as a new user does, and wait until it is drawn."""
    pg.wait_for_selector(".ex-card")                                    # the cards come with the list of examples
    if ex not in MENU_LABEL:
        pg.locator(f".ex-card[data-example='{ex}']").first.click()
    else:                                         # FR11: not one of the six cards - Help -> Examples
        pg.locator(".topbar .menubar-btn", has_text="Help").click()
        pg.locator(".menu.ctx button", has_text="Examples").click()
        pg.locator(".menu.ctx.sub button", has_text=MENU_LABEL[ex]).click()
    pg.wait_for_selector(ready, timeout=120000)
    pg.wait_for_function("window.__sv.state().busy === 0 && !document.querySelector('.job')", timeout=120000)
    pg.wait_for_timeout(settle)
    no_toasts(pg)


def img_20_sim_vs_flight(b, app):
    """docs/sim-vs-flight.md, steps 1-4 on the example (20 before, 21 Align time, 22 aligned, 23 the roll
    doublet up close, 24 Compare's ranking) - one session, as the tutorial goes."""
    ctx, pg = page(b, app)
    _example(pg, "simVsFlight", ".grid canvas", 2500)
    shot(pg, "20_sim_vs_flight_before")
    pg.locator(".run-head").filter(has_text="flight_attitude").first.click(button="right")
    pg.get_by_text("Align time with another file").first.click()
    pg.wait_for_selector("text=Signal correlation", timeout=60000); pg.wait_for_timeout(2500)
    shot(pg, "21_sim_vs_flight_align")
    pg.get_by_role("button", name="Apply", exact=True).first.click()
    pg.wait_for_function("window.__sv.state().runs.some((r) => Math.abs((r.timeOffset || 0) + 104.369) < 0.05)", timeout=30000)
    pg.wait_for_timeout(2000); no_toasts(pg)
    shot(pg, "22_sim_vs_flight_aligned")
    pg.evaluate("() => { const t = window.__sv.state().ws.tabs.find((x) => x.id === window.__sv.state().ws.activeTab); window.__sv.setState({ ranges: { [t.id]: [24, 40] } }); }")
    pg.wait_for_timeout(2000)
    shot(pg, "23_sim_vs_flight_overshoot")
    pg.evaluate("() => { const t = window.__sv.state().ws.tabs.find((x) => x.id === window.__sv.state().ws.activeTab); window.__sv.setState({ ranges: {} }); }")
    pg.click("[aria-label='Compare runs']")
    pg.wait_for_selector(".sim-row", timeout=60000); pg.wait_for_timeout(2000)
    shot(pg, "24_sim_vs_flight_compare"); ctx.close()


def img_32_replay(b, app):
    """32: a replay page in the browser (Report > Send it as one page); 33: the app as it was sent - two cursors
    with Δ in every chip, the plots' window on the timeline (RE1: then the report screen's HTML makes the page)."""
    ctx, pg = page(b, app)
    _example(pg, "car", ".grid canvas", 1500)
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 18, t2: 31, active: 2 } })")
    shot(pg, "33_send_replay_delta")
    pg.click("nav.rail button[aria-label='Report']")
    pg.wait_for_selector(".rd .replay-make", timeout=30000); pg.wait_for_timeout(1500)
    pg.locator(".replay-make").click()
    pg.wait_for_function("document.querySelector('.crumbs input') && document.querySelector('.crumbs input').value !== ''")
    pg.fill(".crumbs input", app.data); pg.press(".crumbs input", "Enter")
    pg.wait_for_function(f"document.querySelector('.crumbs input').value === {json.dumps(app.data)}")
    pg.fill(".savename input", "car-replay.html"); pg.click(".dialog-foot .btn.primary")
    path = app.path("car-replay.html")
    for _ in range(120):
        if os.path.exists(path) and os.path.getsize(path) > 10000:
            break
        pg.wait_for_timeout(500)
    rp = ctx.new_page()
    rp.goto("file://" + path, wait_until="domcontentloaded")
    rp.wait_for_function("window.__replay && document.querySelectorAll('.plot .u-over').length > 0", timeout=60000)
    rp.wait_for_timeout(1500)
    rp.screenshot(path=os.path.join(IMAGES, "32_replay_page.png")); print("image docs/images/32_replay_page.png")
    ctx.close()


def img_39_smart_sweep_demo(b, app):
    """The smart-sweep demo after three rounds: the next runs converge on the full grid's optimum."""
    ctx, pg = page(b, app)
    pg.locator(".ex-card[data-example='smartSweepDemo']").first.click()
    pg.wait_for_selector(".dm-strip", timeout=60000)
    if pg.locator(".dm-reset").is_enabled():
        pg.locator(".dm-reset").click()
        pg.wait_for_function("document.querySelector('.dm-strip').dataset.round === '0'")
    for k in (1, 2, 3):
        pg.locator(".dm-next").click()
        pg.wait_for_function(f"document.querySelector('.dm-chart')?.dataset.points === '{k}' && "
                             "document.querySelector('[data-shot=demo]').dataset.settled === '1'", timeout=300000)
    pg.wait_for_timeout(1500)
    shot(pg, "39_smart_sweep_demo"); ctx.close()


def img_40_common_gains(b, app):
    """One set of gains for three drones: the shared answer, why the others fail."""
    ctx, pg = page(b, app)
    _example(pg, "commonGains", "[data-shot][data-settled='1']", 2000)
    shot(pg, "40_common_gains"); ctx.close()


def img_41_sweeps_all_runs(b, app):
    """The sweep table's results: All runs - a line per run across the parameters, each scenario and the outputs."""
    ctx, pg = page(b, app)
    _example(pg, "sweepTable", ".pp canvas", 1500)
    tab = pg.get_by_role("tab", name="All runs")
    if not tab.count():
        tab = pg.locator("button", has_text="All runs")
    tab.first.click(); pg.wait_for_timeout(2500)
    shot(pg, "41_sweeps_all_runs"); ctx.close()


def _what_changed(pg):
    _example(pg, "investigate", ".grid canvas", 1500)
    pg.locator(".sig").filter(has=pg.get_by_text("Roll", exact=True)).first.click()
    pg.wait_for_timeout(800)
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 38.46, t2: 39.24, active: 1 } })")
    pg.wait_for_selector(".sel-bar:not([hidden])", timeout=20000)
    pg.click(".sel-changed")
    pg.wait_for_selector(".wc-section", timeout=60000); pg.wait_for_timeout(2000)


def img_42_report_process(b, app):
    """RE1: the report written beside its live page - it opens with The process in brief, a value of every sample
    in the text, the roll plot."""
    ctx, pg = page(b, app)
    _what_changed(pg)
    pg.click("nav.rail button[aria-label='Report']")
    pg.wait_for_selector(".rd .rd-text", timeout=30000)
    pg.locator(".rd-text").fill("# Heavy payload: the roll in gusts\n\nThe roll peaked at **{{ max({heavy_payload.csv:Roll}) :.1f }}°** at "
                                "{{ tmax({heavy_payload.csv:Roll}) :.1f }} s; motor 3 reached {{ max({heavy_payload.csv:Motor3}) :.0f }}.\n\n[[process]]\n\n[[tab1]]\n")
    pg.wait_for_function("(window.__sv.state().reportPreviewHtml || '').includes('Heavy payload')", timeout=60000)
    pg.wait_for_timeout(2500)
    shot(pg, "42_report_process"); ctx.close()


def img_43_what_changed(b, app):
    """What changed first around the roll error: every signal that left its usual range, in time order."""
    ctx, pg = page(b, app)
    _what_changed(pg)
    shot(pg, "43_what_changed"); ctx.close()


def img_47_what_changed_film(b, app):
    """RD4: What changed? as a film - the Investigate example, two cursors put around the roll's first jump, the
    question asked, and the answer: the signals that left their usual range in time order, who led whom."""
    ctx, pg = page(b, app)
    _example(pg, "investigate", ".grid canvas", 1500)
    pg.locator(".sig").filter(has=pg.get_by_text("Roll", exact=True)).first.click()
    pg.wait_for_timeout(800)
    # time 25-55 s: the roll's first jump wide enough to see the cursors pulled across it
    pg.evaluate("() => { const t = window.__sv.state().ws.tabs[0]; window.__sv.setState({ ranges: { [t.id]: [25, 55] } }); }")
    pg.wait_for_timeout(800)
    pg.add_style_tag(content=SHOT_HIDE); pg.mouse.move(W - 5, H - 5)
    d, frames = tempfile.mkdtemp(prefix="sv-film-"), []
    for _ in range(4):
        frame(pg, d, frames)                                      # the two runs, the roll's jump
    for t2 in (38.46, 38.62, 38.78, 38.94, 39.1, 39.24):          # the second cursor pulled across the jump
        pg.evaluate("t2 => window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 38.46, t2, active: 2 } })", t2)
        pg.wait_for_timeout(250); frame(pg, d, frames)
    pg.wait_for_selector(".sel-bar:not([hidden])", timeout=20000)
    btn = pg.locator(".sel-changed").first.bounding_box()
    pg.mouse.move(btn["x"] + btn["width"] / 2, btn["y"] + btn["height"] / 2); pg.wait_for_timeout(300)
    frame(pg, d, frames); frame(pg, d, frames)                    # the question, under the pointer
    pg.click(".sel-changed")
    pg.wait_for_selector(".wc-section", timeout=60000); pg.wait_for_timeout(2000)
    pg.mouse.move(W - 5, H - 5); pg.wait_for_timeout(300)
    frame(pg, d, frames)
    film(frames, "47_what_changed", fps=3)
    ctx.close()


# ----------------------------------------------------------------------------- W2: the example cards' pictures
EX_PICS = os.path.join(ROOT, "frontend", "public", "examples")
EX_W, EX_H, EX_MAX_BYTES = 480, 270, 40_000
# what is hidden while the picture is taken: every text of the interface, so a picture serves both languages
EX_NO_TEXT = """.plot-head, .legend, .plot-title, .mode-bar, .plot-mode, .stage-bar, .toasts, .start-card, .tpl-strip, .plot-empty,
  .u-legend, .readout, .cursor-bar, .tl, .map-bar, .relation, .sw-shot-text, .geo-hint, .geo-readout, .globe3d-readout,
  .g3-readout, .g3-cam-hint, .g3-seg-label, .globe3d-light, .map-layers, .map-cam-line { visibility: hidden !important; }"""


def _ex_ready(pg, ex):
    """The example's view has settled: nothing loading, the plots (or the study's view) drawn."""
    pg.wait_for_function("window.__sv.state().busy === 0 && !document.querySelector('.job')", timeout=60000)
    if ex.get("open") == "study":                      # the Sweeps panel marks its picture area when its answer is in
        pg.wait_for_selector("[data-shot][data-settled='1']", timeout=120000)
    elif ex.get("open") == "sweep":                    # the table and its question: the results' parallel plot
        pg.wait_for_selector(".pp canvas", timeout=60000); pg.wait_for_function("window.__svSweeps.idle()", timeout=60000)
    elif ex.get("open") == "summary":                  # FL1: the folder summed up, a row per recording in Sweeps
        pg.wait_for_selector(".sw-raw tbody tr:nth-child(10)", timeout=120000)
        pg.locator(".sw-center-tabs [role=tab]").nth(1).click()                     # its parallel plot: a line per recording
        pg.wait_for_selector(".pp canvas", timeout=60000); pg.wait_for_function("window.__svSweeps.idle()", timeout=60000)
    else:
        pg.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.length || (p.objects || []).length))", timeout=60000)
        pg.wait_for_selector(".grid canvas, .grid svg", timeout=30000)
    pg.evaluate("n => new Promise((r) => { const f = (k) => (k ? requestAnimationFrame(() => f(k - 1)) : r(true)); f(n); })", 6)
    pg.wait_for_timeout(600)                               # the first draw-in (W13.2) is done


def _ex_save(png: bytes, path: str) -> int:
    """The shot cropped to 16:9 around its centre, 480 x 270, WebP within 40 kB (lower quality if needed)."""
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    w, h = im.size
    if w / h > 16 / 9:
        nw = int(h * 16 / 9)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w * 9 / 16)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    im = im.resize((EX_W, EX_H), Image.LANCZOS)
    for q in (80, 72, 64, 56, 48, 40):
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=q, method=6)
        if buf.tell() <= EX_MAX_BYTES:
            break
    with open(path, "wb") as f:
        f.write(buf.getvalue())
    return buf.tell()


def img_38_welcome_cards(b, app):
    """The welcome screen a new user sees: the demos grouped by area, each card with its picture."""
    ctx, pg = page(b, app)
    pg.wait_for_selector(".ex-card img", timeout=30000)
    pg.evaluate("Promise.all([...document.querySelectorAll('.ex-card img')].map((i) => i.complete ? 1 : new Promise((r) => { i.onload = i.onerror = r; })))")
    pg.wait_for_timeout(600)
    shot(pg, "38_welcome_cards"); ctx.close()


def img_examples(browser, app):
    """W2: the welcome screen's card pictures (frontend/public/examples/<id>.<theme>.webp), made by opening each
    example as a new user would, in both themes - the plot or map area (a study: its panel's picture area)
    only, no interface text. Run it before a release, with the README pictures (Releasing step 1)."""
    os.makedirs(EX_PICS, exist_ok=True)
    sets = json.loads(urllib.request.urlopen(app.url + "/api/examples").read())
    only = [x for x in os.environ.get("SV_EX_ONLY", "").split(",") if x]          # e.g. SV_EX_ONLY=car,sweepTable
    # FR11: only the six cards on the welcome screen have a picture (the others are in Help -> Examples)
    for ex in [x for x in sets if x["id"] not in MENU_LABEL and (not only or x["id"] in only)]:
        for theme in ("dark", "light"):
            ctx, pg = page(browser, app, dark=theme == "dark", scale=2)
            try:
                pg.evaluate(f"window.__sv.setState({{ theme: '{theme}', geoBase: 'offline' }})")   # maps: the built-in basemap
                pg.wait_for_selector(".ex-card")
                if not pg.locator(f".ex-card[data-example='{ex['id']}']").count():      # a Help -> Examples one: no card
                    continue
                pg.locator(f".ex-card[data-example='{ex['id']}']").click()
                if ex["id"] == "smartSweepDemo":                # the demo's picture: after two rounds, its chart drawn
                    pg.wait_for_selector(".dm-strip", timeout=60000)
                    if pg.locator(".dm-reset").is_enabled():
                        pg.locator(".dm-reset").click()
                        pg.wait_for_function("document.querySelector('.dm-strip').dataset.round === '0'")
                    for k in (1, 2):
                        pg.locator(".dm-next").click()
                        pg.wait_for_function(f"document.querySelector('.dm-chart')?.dataset.points === '{k}' && "
                                             "document.querySelector('[data-shot=demo]').dataset.settled === '1'", timeout=180000)
                _ex_ready(pg, ex)
                # texts drawn inside the plots and the map (the log's event names, object names): off for the picture
                pg.evaluate("(() => { const s = window.__sv.state(); window.__sv.setState({ logMarkers: 'off', mapPrefs: { ...s.mapPrefs, names: 'hidden' } }); })()")
                pg.evaluate("n => new Promise((r) => { const f = (k) => (k ? requestAnimationFrame(() => f(k - 1)) : r(true)); f(n); })", 6)
                pg.wait_for_timeout(400)
                pg.add_style_tag(content=EX_NO_TEXT)
                no_toasts(pg)
                pg.mouse.move(W - 5, 5)
                # a study: its shared-values chart (the values tried, which hold, the best) - no table, no words
                area = {"study": "[data-shot] .cp-space-svg", "sweep": ".pp", "summary": ".pp"}.get(ex.get("open", ""), ".grid")
                area = pg.locator(area).first
                size = _ex_save(area.screenshot(), os.path.join(EX_PICS, f"{ex['id']}.{theme}.webp"))
                print("example picture", ex["id"], theme, f"{size / 1000:.1f} kB")
            except Exception as e:                          # one card failing must not stop the others
                print("FAILED example", ex["id"], theme, "-", str(e)[:300])
            finally:
                ctx.close()


def _report_parts(pg, app, he=False):
    """RE2: the two demo recordings open, the Report screen, the automatic report made of ready-made parts."""
    if he:
        pg.evaluate("() => window.__sv.setState({ lang: 'he' })")
    open_api(pg, app, "report_demo/mission_ref.csv", "report_demo/mission_gust.csv")
    pg.click("nav.rail button[aria-label='%s']" % ("דוח" if he else "Report"))
    pg.wait_for_selector(".rd-parts .rd-cat-tracking", timeout=30000)
    pg.locator(".rd-ready .rd-lib-item").first.click()
    pg.wait_for_function("(window.__sv.state().ws.report?.doc?.text || '').includes('[[differences]]')", timeout=20000)
    pg.wait_for_function("(window.__sv.state().reportPreviewHtml || '').includes('class=\"plot')", timeout=90000)
    pg.wait_for_timeout(3000)


def _preview_to(pg, text):
    """Scroll the live preview to the first heading / paragraph that has this text."""
    fr = next(f for f in pg.frames if f != pg.main_frame)
    fr.evaluate("""t => { const el = [...document.querySelectorAll('h1,h2,h3,p,strong')].find(e => e.textContent.includes(t));
      if (el) el.scrollIntoView({ block: 'start' }); }""", text)
    pg.wait_for_timeout(1500)


def img_48_report_parts(b, app):
    """RE2: the ready-made parts beside the text - ready reports, parts by category (commanded vs actual, navigation
    with the guessed reference, the scenario, comparing files) - and the automatic report's What to look at."""
    ctx, pg = page(b, app)
    _report_parts(pg, app)
    _preview_to(pg, "What to look at")
    shot(pg, "48_report_parts"); ctx.close()


def img_49_report_differences(b, app):
    """RE2: two runs of the same mission compared - the central region of the change, the first to diverge, the
    signals ranked, each zoomed on its own region."""
    ctx, pg = page(b, app)
    _report_parts(pg, app)
    pg.click(".rd-head .seg button:nth-child(3)")          # Preview: the page at the screen's width
    pg.wait_for_timeout(2500)
    _preview_to(pg, "The central region of the change")
    shot(pg, "49_report_differences"); ctx.close()


def img_51_report_map(b, app):
    """RE2: the trajectory part - both runs' tracks on the map; then navigation errors one plot per axis."""
    ctx, pg = page(b, app)
    _report_parts(pg, app)
    pg.click(".rd-head .seg button:nth-child(3)")
    pg.wait_for_timeout(2500)
    _preview_to(pg, "The tracks on the map")
    pg.wait_for_timeout(3000)
    shot(pg, "51_report_map"); ctx.close()


def img_57_report_latex(b, app):
    """RE3: the automatic report turned into a LaTeX document (Written in -> LaTeX): the source beside the PDF this
    computer's TeX made - the plots as figures, the parts as sections and tables. Needs a LaTeX installed."""
    ctx, pg = page(b, app)
    _report_parts(pg, app)
    pg.locator(".rd-format").select_option("tex")
    pg.wait_for_function("(window.__sv.state().ws.report?.doc?.text || '').includes('\\\\documentclass')", timeout=30000)
    pg.wait_for_selector(".rd-pdf-frame", timeout=180000)
    # the text from \\begin{document} (the parts as references), beside the PDF (a Chromium with its PDF view: SV_CHROMIUM)
    pg.evaluate("() => { const e = document.querySelector('.rd-text'); const i = e.value.indexOf('\\\\begin{document}'); e.scrollTop = e.scrollHeight * i / e.value.length - 20; }")
    pg.evaluate("() => { for (const t of [...document.querySelectorAll('.toast button[aria-label]')]) t.click(); }")
    pg.wait_for_timeout(4000)
    shot(pg, "57_report_latex"); ctx.close()


def img_50_report_parts_hebrew(b, app):
    """RE2: the same automatic report in Hebrew (the report's language follows the app's)."""
    ctx, pg = page(b, app)
    _report_parts(pg, app, he=True)
    _preview_to(pg, "פקודה / ביצוע")
    shot(pg, "50_report_parts_hebrew"); ctx.close()


def _help_example(pg, text):
    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="Examples").click()
    pg.locator(".menu.ctx.sub button", has_text=text).click()


def _finish_demo(pg):
    """A step-by-step example (demoGuide.ts) taken to its end at once: its line's *Show the result*."""
    pg.wait_for_selector(".demo-guide .demo-finish", timeout=60000)
    pg.locator(".demo-guide .demo-finish").click()


def img_52_messages_recording(b, app):
    """MSG2: Help -> Examples -> messages to signals - the serial link's two directions decoded by their structures
    (MSB / LSB first, 32-bit, float, bits, scales) into recordings of their own, plotted one plot per message."""
    ctx, pg = page(b, app)
    _help_example(pg, "messages to signals")
    _finish_demo(pg)
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name === 'rx_byte - messages')", timeout=60000)
    pg.wait_for_timeout(1500)
    pg.evaluate("() => { for (const t of [...document.querySelectorAll('.toast button[aria-label]')]) t.click(); }")
    pg.wait_for_timeout(2500)
    shot(pg, "52_messages_recording"); ctx.close()


def _wide_panel(pg, w=640):
    """The side panel dragged wider by its edge (the structure's fields table wants room). Messages opens as a page on the
    whole stage (components/rail.ts) - nothing to drag then."""
    if not pg.locator(".main > .resizer").count():
        return
    r = pg.locator(".main > .resizer").first.bounding_box()
    pg.mouse.move(r["x"] + r["width"] / 2, r["y"] + 200)
    pg.mouse.down()
    pg.mouse.move(64 + w, r["y"] + 200, steps=8)
    pg.mouse.up()
    pg.wait_for_timeout(300)


def img_53_messages_structure(b, app):
    """MSG2 / MSG3: the Messages panel on a sensor board's bytes -> Propose a structure: the header, length, type,
    checksum and footer found, each message's fields guessed (16-bit LSB / MSB first, signed, 32-bit) - a form to
    correct, or JSON."""
    ctx, pg = page(b, app)
    open_api(pg, app, "serial_link/sensor_uart.csv")
    pg.locator(".sig", has_text="sensor_byte").first.click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    pg.wait_for_selector(".msgp-stream.open .msgp-edit")
    _wide_panel(pg)
    pg.locator(".msgp-stream.open .msg-propose").click()
    pg.wait_for_selector(".msgp-stream.open .msg-struct .msg-msg")
    pg.evaluate("() => document.querySelector('.msgp-stream.open .msg-structure').scrollIntoView({ block: 'start' })")
    pg.wait_for_timeout(1200)
    shot(pg, "53_messages_structure"); ctx.close()


def img_55_messages_panel(b, app):
    """MSG3: the Messages panel - the byte streams of a serial link with their types and rates, a flight log's
    message types (fields, count, rate), the structure library."""
    ctx, pg = page(b, app)
    open_api(pg, app, "serial_link/link_tx_rx.csv", "copter_flight.bin")
    pg.locator(".rail button[aria-label='Messages']").click()
    pg.wait_for_selector(".msgp-stream .msgp-types .chip-s", timeout=60000)
    _wide_panel(pg, 520)
    pg.wait_for_selector(".msgp-log")
    if not pg.locator(".msgp-log[open]").count():
        pg.locator(".msgp-log summary").first.click()
    pg.locator(".msgp-log tbody tr", has=pg.locator("td", has_text="ATT")).first.click()
    pg.wait_for_timeout(2500)
    pg.evaluate("() => { for (const t of [...document.querySelectorAll('.toast button[aria-label]')]) t.click(); }")
    pg.wait_for_timeout(800)
    shot(pg, "55_messages_panel"); ctx.close()


def img_56_messages_steps(b, app):
    """MSG4: the Messages panel's steps on a raw byte signal - the repeating patterns (the header first), the first
    messages byte by byte coloured by role, the values of each message in step 3."""
    ctx, pg = page(b, app)
    open_api(pg, app, "serial_link/link_tx_rx.csv")
    pg.locator(".rail button[aria-label='Messages']").click()
    pg.wait_for_selector(".msgp-stream[data-key$='/rx_byte'] .msgp-stream-head", timeout=60000)
    _wide_panel(pg, 720)
    pg.locator(".msgp-stream[data-key$='/rx_byte'] .msgp-stream-head").click()
    pg.wait_for_selector(".msgp-stream.open .bv-frame .bv-b.role-header", timeout=60000)
    pg.wait_for_selector(".msgp-stream.open .msg-values-t", timeout=60000)
    pg.evaluate("() => { for (const t of [...document.querySelectorAll('.toast button[aria-label]')]) t.click(); }")
    pg.locator(".msgp-stream.open .msg-step-2").scroll_into_view_if_needed()
    pg.evaluate("() => document.querySelector('.msgp-stream.open .msg-step-2').scrollIntoView({block: 'start'})")
    pg.wait_for_timeout(800)
    shot(pg, "56_messages_steps"); ctx.close()


def img_54_gps_nmea(b, app):
    """MSG2: a GPS receiver's raw NMEA opened as a recording: the track on the map, the fix status as a lane."""
    ctx, pg = page(b, app)
    _help_example(pg, "raw NMEA")
    _finish_demo(pg)
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.plots.some(p => (p.mode === 'geo' || p.mode === '3d') && (p.objects || []).length))", timeout=60000)
    pg.evaluate("() => { const st = window.__sv.state(); const tb = st.ws.tabs.find(t => t.plots.some(p => p.mode === 'geo' || p.mode === '3d')); window.__sv.setState({ ws: { ...st.ws, activeTab: tb.id } }); }")
    pg.wait_for_timeout(1500)
    pg.evaluate("() => { for (const t of [...document.querySelectorAll('.toast button[aria-label]')]) t.click(); }")
    pg.wait_for_timeout(3500)
    shot(pg, "54_gps_nmea"); ctx.close()


SCENES = [(n, f) for n, f in sorted(globals().items()) if n.startswith("img_")]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", nargs="*", help="scene names (or their number) to make, e.g. 01 14")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    os.makedirs(IMAGES, exist_ok=True)
    app = App()
    try:
        with sync_playwright() as p:
            exe = os.environ.get("SV_CHROMIUM")
            b = p.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            for name, fn in SCENES:
                short = name.split("_", 1)[1]
                if a.only and not any(short.startswith(o) or name.startswith(o) for o in a.only):
                    continue
                try:
                    fn(b, app)
                except Exception as e:                          # one scene failing must not stop the others
                    print("FAILED", name, "-", str(e)[:600])
            b.close()
    finally:
        app.close()


if __name__ == "__main__":
    main()
