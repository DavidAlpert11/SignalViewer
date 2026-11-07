"""
Screenshots and short videos for the README (docs/images, docs/media), made from the app itself:
it starts Signal Viewer on the example files with an empty home folder, drives it with Playwright
and records. Run it before a release so the pictures show the current interface.

    python tools/make_readme_media.py                 # everything
    python tools/make_readme_media.py --only 01 14    # names starting with these
    SV_CHROMIUM=/path/to/chrome python tools/make_readme_media.py

Needs: playwright (+ a Chromium), ffmpeg on PATH for the videos (MP4 + GIF).
Not made here (kept from a real screen): 06_3d_terrain.png and the 02_flight_map_3d video - a
headless browser draws the 3D view on software WebGL, where its camera and its playback cannot
be recorded well.
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
MEDIA = os.path.join(ROOT, "docs", "media")
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
    runs = json.loads(urllib.request.urlopen(app.url + "/api/runs").read())
    for r in runs:
        if r.get("format") != "derived":
            urllib.request.urlopen(urllib.request.Request(f"{app.url}/api/runs/{r['id']}", method="DELETE"))
    for name in ("autosave.json", "ui_settings.json", "sweep_autosave.json"):    # settings too (1.8: kept in the app folder) -
        try:                                             # the Hebrew scene must not leave the next ones in Hebrew
            os.remove(os.path.join(app.home, ".signalviewer", name))
        except OSError:
            pass


def page(browser, app, dark=False, video=None):
    reset(app)
    t0 = time.time()
    ctx = browser.new_context(viewport={"width": W, "height": H}, color_scheme="dark" if dark else "light",
                              **({"record_video_dir": video, "record_video_size": {"width": W, "height": H}} if video else {}))
    pg = ctx.new_page()
    pg._t0 = t0                                                # recording start, for trimming the video
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
    pg.wait_for_selector(".sig")
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


def shot(pg, name):
    no_toasts(pg)
    pg.mouse.move(W - 5, H - 5)
    pg.wait_for_timeout(300)
    path = os.path.join(IMAGES, name + ".png")
    pg.screenshot(path=path)
    print("image", os.path.relpath(path, ROOT))


def mark(pg) -> float:
    """Seconds since the recording started: where a video should begin (the loading is cut)."""
    return time.time() - pg._t0


def finish_video(ctx, pg, name, since=None):
    """The context's WebM -> MP4 (H.264) and a GIF (8 fps, 900 px wide, own palette). since: a
    mark() - only what was recorded after it is kept (loading the app and the files is cut; the
    recording's clock lags while loading, so the cut is measured from the end)."""
    keep = (mark(pg) - since) if since is not None else None
    vid = pg.video.path() if pg.video else None
    ctx.close()
    if not vid or not shutil.which("ffmpeg"):
        print("video skipped (no ffmpeg):", name)
        return
    skip = 0.0
    if keep:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vid],
                                   capture_output=True, text=True).stdout.strip() or 0)
        skip = max(0.0, dur - keep)
    mp4 = os.path.join(MEDIA, name + ".mp4")
    gif = os.path.join(MEDIA, name + ".gif")
    q = ["-hide_banner", "-loglevel", "error", "-y", *(["-ss", f"{max(0.0, skip):.2f}"] if skip > 0 else [])]
    subprocess.run(["ffmpeg", *q, "-i", vid, "-vf", "fps=25", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "28",
                    "-movflags", "+faststart", mp4], check=True)
    pal = vid + ".png"
    subprocess.run(["ffmpeg", *q, "-i", vid, "-vf", "fps=8,scale=900:-1:flags=lanczos,palettegen=stats_mode=diff", pal], check=True)
    subprocess.run(["ffmpeg", *q, "-i", vid, "-i", pal, "-lavfi",
                    "fps=8,scale=900:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle", gif], check=True)
    print("video", os.path.relpath(mp4, ROOT), f"{os.path.getsize(mp4) // 1024} kB,", os.path.relpath(gif, ROOT), f"{os.path.getsize(gif) // 1024} kB")

def sweeps_fresh(pg):
    """The Sweeps area with no study open (the studies are kept from the last scene)."""
    pg.locator(".areas .area-btn", has_text="Sweeps").click()
    pg.wait_for_selector(".sw-welcome, .sw-study-wrap")
    if pg.locator(".areabar .tab .x").count():                  # Clear > Everything (1.20)
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
    cursors(pg, 160, 160); pg.wait_for_timeout(8000)               # the terrain and the map tiles load
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
    pg.locator("[role='tab']", has_text=tab).first.click()
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
    pg.locator(".mav-section input[list]").fill(f"udpin:127.0.0.1:{port}")
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
    sig(pg, "GPS.Alt").click()
    pg.click("[aria-label='Create signals']")
    pg.locator(".analysis .seg.wide button", has_text="Frames").click(); pg.wait_for_timeout(400)
    pg.locator(".seg.wide button", has_text="A plot per axis").click()
    pg.get_by_role("button", name="Preview", exact=True).click()
    pg.wait_for_selector(".pv-plot canvas", timeout=20000); pg.wait_for_timeout(1200)
    shot(pg, "18_frames"); ctx.close()


# ----------------------------------------------------------------------------- videos
def vid_01_quickstart(b, app, tmp):
    ctx, pg = page(b, app, video=tmp)
    open_dialog(pg, app, "run_012.csv", slow=True)
    layout(pg, 2, 2); pg.wait_for_timeout(400)
    for k, n in ((1, "Speed"), (2, "RPM"), (3, "Throttle"), (4, "EngineTemp")):
        select_plot(pg, k); sig(pg, n).click(); pg.wait_for_timeout(500)
    box = pg.locator(".plot .u-over").first.bounding_box()
    pg.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] / 2)
    pg.mouse.down(); pg.mouse.move(box["x"] + box["width"] * 0.6, box["y"] + box["height"] / 2, steps=15); pg.mouse.up()
    pg.wait_for_timeout(700)
    pg.keyboard.press("Space"); pg.wait_for_timeout(300)
    pg.mouse.click(box["x"] + box["width"] * 0.4, box["y"] + box["height"] / 2); pg.wait_for_timeout(500)
    pg.keyboard.down("Shift"); pg.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2); pg.keyboard.up("Shift")
    pg.wait_for_timeout(1500)
    pg.keyboard.press("r"); pg.wait_for_timeout(1200)
    finish_video(ctx, pg, "01_quickstart")


# 02_flight_map_3d (video) is not made here, for the same reason as 06_3d_terrain: headless, the 3D
# view draws on software WebGL and the recorder catches only a few frames of the playback.


def vid_03_compare_runs(b, app, tmp):
    ctx, pg = page(b, app, video=tmp)
    open_api(pg, app, "run_012.csv", "run_013.csv", "run_014.csv")
    pg.click("[aria-label='Compare runs']")
    pg.wait_for_selector(".sim-row", timeout=30000); pg.wait_for_timeout(900)
    for k in range(3):
        pg.locator(".sim-row").nth(k).click(); pg.wait_for_timeout(1300)
    pg.locator(".cmp-panel .seg.wide button", has_text="A segment").click(); pg.wait_for_timeout(500)
    pg.locator(".seg-pick label:has-text('State signal') select").select_option("Gear"); pg.wait_for_timeout(900)
    pg.wait_for_selector(".sim-row", timeout=30000)
    pg.locator(".sim-row", has_text="Speed").first.click(); pg.wait_for_timeout(1800)
    pg.locator(".cmp-panel button", has_text="Table of all signals").first.click()
    pg.wait_for_selector(".cmp-dialog"); pg.wait_for_timeout(2200)
    finish_video(ctx, pg, "03_compare_runs")


def vid_04_flight_log_health(b, app, tmp):
    ctx, pg = page(b, app, video=tmp)
    open_dialog(pg, app, "flight.bin", slow=True)
    pg.wait_for_selector(".start-card", timeout=20000); pg.wait_for_timeout(1800)
    pg.locator(".start-card .hrow .pchange.span").first.click(); pg.wait_for_timeout(1300)
    pg.locator(".start-card").get_by_role("button", name="Open it").click(); pg.wait_for_timeout(2200)
    pg.evaluate("window.__sv.setState({ panel: 'log' })"); pg.wait_for_timeout(1200)
    pg.locator("[role='tab']", has_text="Events").first.click(); pg.wait_for_timeout(1200)
    pg.locator("[role='tab']", has_text="Parameters").first.click(); pg.wait_for_timeout(1500)
    finish_video(ctx, pg, "04_flight_log_health")


def vid_05_live_mavlink(b, app, tmp):
    ctx, pg = page(b, app, video=tmp)
    stop = live_mavlink(pg, app, seconds=7)
    stop.set(); pg.wait_for_timeout(300)
    finish_video(ctx, pg, "05_live_mavlink")


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
    pg.wait_for_selector(".track-key", timeout=30000); pg.wait_for_timeout(2500)
    shot(pg, "28_map_by_mode"); ctx.close()


def img_00_hero(b, app):
    """M1: the README's first picture - one window, 2 x 2, dark, at 2x: the map with the track coloured
    by the flight mode and the vehicle at the cursor; the 3D attitude; Roll desired vs actual with
    the mode lane; the vibration behind the health check's finding - the cursor at the vibration
    (~140 s of the ArduPilot example), the findings docked beside the timeline. No signal list, no
    popups. tools/make_social_preview.py crops docs/images/social-preview.png from it."""
    reset(app)
    ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=2, color_scheme="dark")
    pg = ctx.new_page()
    pg.goto(app.url); pg.wait_for_selector(".app"); pg.wait_for_timeout(400)
    pg.evaluate("window.__sv.setState({ theme: 'dark' })")
    pg.locator(".examples-line button", has_text="ArduPilot").click()          # as a user starts: the example
    pg.wait_for_selector(".findings-dock", timeout=60000)
    pg.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.name === 'Flight')")
    rid = S(pg, "s.runs.find((r) => r.format === 'bin').id")
    pg.evaluate("""(rid) => window.__sv.state().commit((ws) => {
      const tab = ws.tabs.find((t) => t.name === 'Flight');
      const sig = (n) => `${rid}/${n}`;
      const line = (n, color, width = 1.5) => ({ sig: sig(n), color, width, scale: 1, offset: 0 });
      for (const p of tab.plots) {
        for (const o of p.objects || []) { o.trackColor = 'state'; o.colorSig = sig('MODE.Mode'); o.trail = true; }
        if (p.mode === '3d') { p.showReadout = false; p.showEvents = false; p.followObject = p.objects?.[0]?.id ?? null; }   // the attitude, close
      }
      tab.rows = 2; tab.cols = 2; tab.rowSizes = [1.15, 1]; tab.linkX = true;
      tab.sharedStates = [sig('MODE.Mode')];
      tab.plots.push(
        { id: 'hero-roll', title: 'Roll', signals: [line('ATT.DesRoll [deg]', '#8FA3B8', 1.25), line('ATT.Roll [deg]', '#F2A33A', 1.75)] },
        { id: 'hero-vibe', title: 'Vibration', signals: [line('VIBE[0].VibeX [m/s/s]', '#4C9AFF'), line('VIBE[0].VibeY [m/s/s]', '#3FB950'),
          line('VIBE[0].VibeZ [m/s/s]', '#E5534B')] });
      ws.activeTab = tab.id; tab.active = 2;
      return ws; })""", rid)
    pg.evaluate("window.__sv.setState({ panel: null, startCard: { ...window.__sv.state().startCard }, findingsOpen: false })")
    cursors(pg, 140.4, 140.4)
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, dual: false, t2: null } })")
    pg.wait_for_selector(".track-key", timeout=30000); pg.wait_for_timeout(4000)
    cam = pg.locator("button", has_text="On the object")                        # the camera behind the vehicle
    if cam.count():
        cam.first.click()
    pg.wait_for_timeout(8000)                                                   # the terrain, the map tiles, the 3D model
    shot(pg, "00_hero"); ctx.close()


def _fleet(pg):
    pg.click("[aria-label='Fleet']")
    pg.locator(".fleet-example .btn").click()
    pg.wait_for_selector(".fleet-trend circle", timeout=60000)
    pg.wait_for_function("document.querySelectorAll('.fleet-log').length === 1"); pg.wait_for_timeout(500)


def img_29_fleet_trend(b, app):
    """The example fleet: one copter's vibration growing flight after flight, the flight over the limit."""
    ctx, pg = page(b, app)
    _fleet(pg)
    pg.fill(".fleet-search input[type=search]", "X8-A")
    pg.wait_for_function("document.querySelectorAll('.fleet-trend circle').length === 6")
    pg.locator(".fleet-line").first.click(); pg.wait_for_timeout(500)
    pg.locator(".fleet-findings button").first.click()          # Open here: the flight at the finding
    pg.wait_for_function("window.__sv.state().runs.length > 0", timeout=30000); pg.wait_for_timeout(1500)
    pg.evaluate("window.__sv.setState({ panel: 'fleet' })"); pg.wait_for_timeout(600)
    shot(pg, "29_fleet_trend"); ctx.close()


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


def vid_06_many_signals(b, app, tmp):
    ctx, pg = page(b, app, video=tmp)
    since = mark(pg)
    _many_signals(pg, app)
    box = pg.locator(".plot-canvas").first.bounding_box()
    for i in range(24):
        pg.mouse.move(box["x"] + 40 + i * (box["width"] - 80) / 24, box["y"] + box["height"] * 0.5); pg.wait_for_timeout(70)
    for k in (0, 3, 8):
        pg.locator(".legend-side .lrow").nth(k).hover(); pg.wait_for_timeout(900)
    pg.fill(".legend-filter", "Vibe"); pg.wait_for_timeout(1200)
    pg.fill(".legend-filter", ""); pg.wait_for_timeout(600)
    finish_video(ctx, pg, "06_many_signals", since)


def vid_07_fleet(b, app, tmp):
    ctx, pg = page(b, app, video=tmp)
    since = mark(pg)
    _fleet(pg); pg.wait_for_timeout(1200)
    pg.locator(".fleet-search input[type=search]").type("X8-A", delay=120); pg.wait_for_timeout(1500)
    pg.locator(".fleet-line").first.click(); pg.wait_for_timeout(1500)
    pg.locator(".fleet-findings button").first.click(); pg.wait_for_timeout(2500)
    finish_video(ctx, pg, "07_fleet", since)


def vid_08_sweeps_pareto(b, app, tmp):
    ctx, pg = page(b, app, video=tmp)
    since = mark(pg)
    _pareto(pg); pg.wait_for_timeout(800)
    pg.locator(".sw-rankby .btn").click(); pg.wait_for_timeout(2500)
    finish_video(ctx, pg, "08_sweeps_pareto", since)


SCENES = [(n, f) for n, f in sorted(globals().items()) if n.startswith(("img_", "vid_"))]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", nargs="*", help="scene names (or their number) to make, e.g. 01 vid_03")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    os.makedirs(IMAGES, exist_ok=True); os.makedirs(MEDIA, exist_ok=True)
    app = App()
    tmp = tempfile.mkdtemp(prefix="sv-media-vid-")
    try:
        with sync_playwright() as p:
            exe = os.environ.get("SV_CHROMIUM")
            b = p.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            for name, fn in SCENES:
                short = name.split("_", 1)[1]
                if a.only and not any(short.startswith(o) or name.startswith(o) for o in a.only):
                    continue
                try:
                    fn(b, app, tmp) if name.startswith("vid_") else fn(b, app)
                except Exception as e:                          # one scene failing must not stop the others
                    print("FAILED", name, "-", str(e)[:600])
            b.close()
    finally:
        app.close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
