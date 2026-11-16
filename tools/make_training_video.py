"""
The training film: Signal Viewer taught like a presentation, as a video (docs/media/training.mp4).

    python tools/make_training_video.py          # needs Playwright (+ a Chromium: SV_CHROMIUM) and ffmpeg

Each chapter opens with a slide (what you will learn, in a few lines), then shows it live in the app on the
shipped examples, with captions and a ring where the pointer clicks. Recorded from the app itself, offline.
A chapter that cannot be shown (an example missing) is left out with a note in the log - the film goes on.
"""
import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_demo_video import Film, cut_and_encode, fresh  # noqa: E402
from make_readme_media import MEDIA, App, H, W, no_toasts, reset  # noqa: E402
import make_demo_video  # noqa: E402

OUT = os.path.join(MEDIA, "training.mp4")

SLIDES = r"""
(() => {
  const st = document.createElement('style');
  st.textContent = `
  #tr-slide { position: fixed; inset: 0; z-index: 100001; display: flex; align-items: center; justify-content: center;
    background: radial-gradient(circle at 30% 30%, #17222f, #07090d 75%); color: #fff; transition: opacity .5s ease;
    font-family: 'IBM Plex Sans', system-ui, sans-serif; pointer-events: none; }
  #tr-slide .box { width: 1180px; }
  #tr-slide .no { font: 600 20px 'IBM Plex Mono', monospace; color: #f2a33a; letter-spacing: 2px; }
  #tr-slide h1 { font-size: 56px; margin: 10px 0 30px; letter-spacing: -.5px; }
  #tr-slide ul { margin: 0; padding: 0; list-style: none; }
  #tr-slide li { font-size: 27px; line-height: 1.45; color: #d6dee9; margin: 0 0 14px; padding-left: 38px; position: relative; }
  #tr-slide li::before { content: ''; position: absolute; left: 6px; top: 15px; width: 12px; height: 12px; border-radius: 3px; background: #58a6ff; }
  #tr-slide .foot { margin-top: 38px; font-size: 18px; color: #8b98a9; }
  #tr-ring { position: fixed; z-index: 99998; width: 46px; height: 46px; margin: -23px 0 0 -23px; border-radius: 50%;
    border: 3px solid #f2a33a; pointer-events: none; opacity: 0; transform: scale(.4); transition: opacity .2s, transform .35s ease; }
  #tr-ring.on { opacity: 1; transform: scale(1); }
  /* recorded without a graphics card: the 3D view's "reduced quality" badge is true here, not for the viewer */
  .globe3d-light { display: none !important; }`;
  document.head.appendChild(st);
  window.__slide = (no, h, items, foot) => {
    let d = document.getElementById('tr-slide');
    if (!h) { if (d) { d.style.opacity = 0; setTimeout(() => d.remove(), 600); } return; }
    if (!d) { d = document.createElement('div'); d.id = 'tr-slide'; document.body.appendChild(d); }
    d.innerHTML = `<div class="box">${no ? `<div class="no">${no}</div>` : ''}<h1>${h}</h1><ul>${(items || []).map((x) => `<li>${x}</li>`).join('')}</ul>${foot ? `<div class="foot">${foot}</div>` : ''}</div>`;
    d.style.opacity = 1;
  };
  window.__ring = (x, y) => {
    let r = document.getElementById('tr-ring');
    if (!r) { r = document.createElement('div'); r.id = 'tr-ring'; document.body.appendChild(r); }
    r.style.left = x + 'px'; r.style.top = y + 'px'; r.classList.remove('on'); void r.offsetWidth; r.classList.add('on');
    setTimeout(() => r.classList.remove('on'), 700);
  };
})()
"""


# The recording machine has no graphics card: the app would see a software renderer and draw its 3D view in its
# light mode (no sky, no sunlight, flat far ground). The film shows what a viewer with a graphics card sees,
# so the page is told a hardware renderer's name; the frames are still drawn (slowly) by the same software.
HARDWARE_GL = """(() => { const f = (P) => { const g = P.getParameter; P.getParameter = function (p) {
  if (p === 0x9246) return 'ANGLE (Hardware renderer for the recording)'; return g.call(this, p); }; };
  f(WebGLRenderingContext.prototype); if (window.WebGL2RenderingContext) f(WebGL2RenderingContext.prototype); })();"""


class Lesson(Film):
    """The demo film's tools, plus slides and a ring where the pointer clicks."""

    def overlay(self):
        super().overlay()
        self.pg.evaluate(SLIDES)

    def slide(self, no="", h="", items=(), foot="", hold=0.0):
        self.pg.evaluate("([a, b, c, d]) => window.__slide(a, b, c, d)", [no, h, list(items), foot])
        if hold:
            self.pg.wait_for_timeout(int(hold * 1000))

    def glide(self, locator, click=True, button="left"):
        locator.scroll_into_view_if_needed()
        self.pg.wait_for_timeout(250)
        box = locator.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.pg.mouse.move(x, y, steps=26)
        self.pg.wait_for_timeout(220)
        if click:
            self.pg.evaluate("([x, y]) => window.__ring(x, y)", [x, y])
            self.pg.mouse.click(x, y, button=button)

    def rail(self, name):
        self.glide(self.pg.locator(f"button:has(.rail-label:text-is('{name}'))").first)


def chapter(film, app, no, title, items, show, foot="", keep=False, prepare=None):
    """A slide, then the live part. keep: go on with what the last chapter opened (one example serves several
    chapters - no reopening); else a fresh workspace behind the slide. prepare: work done behind the slide
    (a map loading its tiles) - its wait is cut from the film. A failure is logged and the chapter skipped."""
    film.cap()
    film.slide(no, title, items, foot)
    try:
        if not keep:
            fresh(film, app)
            film.slide(no, title, items, foot)          # the reload took the slide away: back before anything shows
        if prepare:
            film.wait_cut(lambda: prepare(film, app))
        film.slide(no, title, items, foot, hold=5.0)
        film.slide()
        film.pg.wait_for_timeout(700)
        show(film, app)
    except Exception:
        print(f"chapter {no} '{title}' left out:\n{traceback.format_exc()[-600:]}")
        film.slide(no, title, items, foot)
        fresh(film, app)
        film.slide()


def open_example(film, ex, ready, glide=True):
    card = film.pg.locator(f".ex-card[data-example='{ex}']").first
    film.glide(card) if glide else card.click()
    film.pg.wait_for_selector(ready, timeout=90000)
    film.pg.wait_for_function("window.__sv.state().busy === 0 && !document.querySelector('.job')", timeout=90000)
    film.pg.wait_for_timeout(1200)
    no_toasts(film.pg)


# ----------------------------------------------------------------------------- the chapters
def ch_workspace(f, app):
    pg = f.pg
    f.cap("The welcome screen: a demo with a known answer for every area", "Recordings · Sweeps – pick one to start", hold=3.2)
    pg.mouse.wheel(0, 500); pg.wait_for_timeout(1400); pg.mouse.wheel(0, -500); pg.wait_for_timeout(800)
    f.cap("Open a file – or drop it on the window", "Here: three test runs of a car, as CSV")
    open_example(f, "car", ".grid canvas")
    f.cap("Left: the files and their signals, grouped and searchable", "Units, rates and a sparkline for each signal", hold=3.4)
    f.cap("Top: the three areas, files, templates, Undo", "Every change to the workspace can be undone (Ctrl+Z)", hold=3.2)


def ch_plots(f, app):
    pg = f.pg
    f.cap("Click a signal to plot it – Ctrl+click adds it to the same plot")
    f.glide(pg.locator(".sig", has_text="RPM").first)
    pg.wait_for_timeout(1500)
    f.cap("The cursor: values of every line at one moment", "Space turns it on and off")
    f.glide(pg.locator(".stage-bar .cursor-btn").first)
    box = pg.locator(".grid canvas").first.bounding_box()
    for k in range(9):
        pg.mouse.move(box["x"] + box["width"] * (0.2 + 0.07 * k), box["y"] + box["height"] * 0.5, steps=6)
        pg.wait_for_timeout(160)
    pg.mouse.click(box["x"] + box["width"] * 0.45, box["y"] + box["height"] * 0.5)
    pg.wait_for_timeout(1200)
    f.cap("Two cursors: the change between them, Δ, in the legend", "D toggles them")
    f.glide(pg.locator(".stage-bar .cursor-btn").nth(1))
    pg.wait_for_timeout(2600)
    f.cap("Drag to zoom, double-click to fit – all plots share the time axis", "The plot shows every spike, even zoomed out")
    pg.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] * 0.5)
    pg.mouse.down(); pg.mouse.move(box["x"] + box["width"] * 0.55, box["y"] + box["height"] * 0.5, steps=20); pg.mouse.up()
    pg.wait_for_timeout(1800)
    pg.mouse.dblclick(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
    pg.wait_for_timeout(1400)


def ch_compare(f, app):
    pg = f.pg
    f.cap("Compare: the same three runs – every shared signal ranked by how different it is")
    f.rail("Compare")
    pg.wait_for_selector(".sim-row", timeout=30000)
    pg.wait_for_timeout(2200)
    f.cap("Click a row: its signal from every run, overlaid")
    f.glide(pg.locator(".sim-row").first)
    pg.wait_for_timeout(2600)
    f.cap("Mark one run as golden, set tolerances – the verdict is pass / fail", "The same check runs from the command line, in CI", hold=3.4)


def ch_checks(f, app):
    pg = f.pg
    f.cap("Any file: here a pump on a test bench, as Parquet")
    open_example(f, "bench", ".grid canvas")
    f.cap("Checks: one verdict for the file")
    f.rail("Checks")
    pg.wait_for_timeout(2600)
    f.cap("Your limits, the data's own quality, a log's health check", "Gaps, stuck values, spikes – each a click from its moment", hold=3.6)
    f.cap("The file: the structure of any recording")
    f.glide(pg.locator("[role='tab'][data-tab='file']").first)
    pg.wait_for_timeout(2800)


def ch_investigate(f, app):
    pg = f.pg
    f.cap("A known fault: a drone in three gusts – the heavy run loses its roll")
    open_example(f, "investigate", ".grid canvas")
    roll = pg.locator(".sig").filter(has=pg.get_by_text("Roll", exact=True)).first
    if roll.count():
        f.glide(roll)
        pg.wait_for_timeout(1400)
    f.cap("What changed? – two cursors around the moment it went wrong")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 38.46, t2: 39.24, active: 1 } })")
    pg.wait_for_selector(".sel-bar:not([hidden])", timeout=20000)
    pg.wait_for_timeout(1200)
    f.glide(pg.locator(".sel-changed").first)
    pg.wait_for_selector(".wc-section", timeout=30000)
    pg.wait_for_timeout(1800)
    f.cap("The signals that left their usual range, in time order", "Wind first, then the vibration, motor 3 – and only then the roll", hold=4.4)


def ch_report(f, app):
    pg = f.pg
    f.cap("Report: what is on screen becomes one offline HTML page")
    f.rail("Report")
    pg.wait_for_timeout(1800)
    prev = pg.locator(".side .btn", has_text="Preview").first
    if prev.count():
        f.glide(prev)
        pg.wait_for_function("(window.__sv.state().reportPreviewHtml || '').length > 1000", timeout=60000)
        pg.wait_for_timeout(1500)
        f.cap("It opens with the process in brief: the data, what was checked, the conclusion", "Any browser, no install – PDF and Word too", hold=3.0)
        pg.mouse.wheel(0, 700); pg.wait_for_timeout(1800)
        pg.evaluate("window.__sv.setState({ reportPreviewHtml: null })")
        pg.wait_for_timeout(600)
    else:
        f.cap("It opens with the process in brief: the data, what was checked, the conclusion", "Any browser, no install – PDF and Word too", hold=3.6)


def ch_keys(f, app):
    pg = f.pg
    f.cap("Ctrl+K: every command and every signal, by name")
    pg.keyboard.press("Control+k"); pg.wait_for_timeout(700)
    pg.keyboard.type("motor", delay=80); pg.wait_for_timeout(1800)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
    f.cap("Ctrl+Z undoes any change to the workspace", "Templates: save this view, apply it to the next run", hold=3.4)


def globe_ready(pg, timeout=300000):
    """The 3D map has drawn every tile it needs for the view on screen (Cesium's own flag), and stays so for 3 s -
    the flag is true for a moment before the next level of tiles is asked for."""
    pg.wait_for_function("""() => { const g = window.__svGlobe; const ok = !!g && g.widget.scene.globe.tilesLoaded;
      const now = performance.now(); if (!ok) { window.__readySince = null; return false; }
      window.__readySince = window.__readySince || now; return now - window.__readySince > 3000; }""", timeout=timeout, polling=250)


def prep_map(f, app):
    """Behind the slide: the flight opened on Satellite + roads and every tile drawn - the map is there when the
    slide goes."""
    pg = f.pg
    pg.evaluate("window.__sv.setState({ geoBase: 'satroads' })")
    pg.locator(".ex-card[data-example='flight']").first.click()
    pg.wait_for_function("window.__sv.state().busy === 0", timeout=90000)
    globe_ready(pg)
    no_toasts(pg)


def ch_map(f, app):
    """From above, then tilted the way a user does (Ctrl+drag): the ground's relief with the track over it. The
    tiles of the tilted view take long to draw without a graphics card: that wait is cut, and the camera holds
    still there (playing in it would crawl in the recording)."""
    pg = f.pg
    f.cap("Positions in the file: the run on a map", "Here the satellite map with its roads – the offline map is the default", hold=3.4)
    box = pg.locator(".plot:has(.globe3d)").first.bounding_box()
    cx, cy = box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.6
    f.cap("Tilt it – Ctrl+drag or the middle button – and the ground has its heights")
    pg.mouse.move(cx, cy, steps=20); pg.wait_for_timeout(300)

    def tilt():
        pg.keyboard.down("Control"); pg.mouse.down()
        pg.mouse.move(cx, cy - 160, steps=12)
        pg.mouse.up(); pg.keyboard.up("Control")
        pg.mouse.move(box["x"] + box["width"] - 8, box["y"] + 8)    # off the ground: no pointer readout
        globe_ready(pg)
    f.wait_cut(tilt, keep=1.5)                                      # the gesture's start, then the relief drawn
    pg.wait_for_timeout(4500)
    f.cap("Play moves the object along its track – every plot and the map on one time bar",
          "Cameras named by what they do: From above · Around it · Behind it · Cockpit", hold=5.0)


def ch_sweeps(f, app):
    pg = f.pg
    f.cap("A table of runs: 810 runs of a controller sweep", "Opened with its question: which settings hold in every scenario")
    open_example(f, "sweepTable", ".pp canvas")
    pg.wait_for_timeout(1500)
    f.cap("Each line is one run – the ones that hold every limit stand out, the best is marked", hold=3.6)
    goals = pg.locator(".sw-step-btn[data-step='goals']").first
    if goals.count():
        f.cap("The question is plain: limits on the outputs, then what is best")
        f.glide(goals)
        pg.wait_for_timeout(2600)
        f.glide(pg.locator(".sw-step-btn[data-step='results']").first)
        pg.wait_for_timeout(1800)
    f.cap("A study can also start from nothing", "Set the parameters and ranges; Sweeps runs your simulation round after round", hold=3.6)


def record(b, app, tmp):
    reset(app)
    ctx = b.new_context(viewport={"width": W, "height": H}, color_scheme="dark",
                        record_video_dir=tmp, record_video_size={"width": W, "height": H})
    ctx.add_init_script(HARDWARE_GL)
    pg = ctx.new_page()
    f = Lesson(pg)
    pg.goto(app.url)
    pg.wait_for_selector(".ex-card[data-example='car']")
    pg.evaluate("window.__sv.setState({ theme: 'dark' })")
    f.overlay()
    start = f.now()

    f.slide("TRAINING", "Signal Viewer, step by step",
            ["From raw measurements to an engineering answer you can defend",
             "Any time-series data: test runs, logs, simulations, ROS 2, CAN",
             "Everything on your own machine – no account, no internet"],
            "Nine short chapters on the built-in demos · English and Hebrew · free and open source (MIT)", hold=5.5)
    f.slide("AGENDA", "What you will learn",
            ["1 · The workspace   2 · Plots and cursors   3 · Comparing runs",
             "4 · Checks   5 · What changed first   6 · Reports",
             "7 · Working fast   8 · Map and 3D   9 · Sweeps"], hold=5.0)

    chapter(f, app, "CHAPTER 1", "The workspace", ["The welcome screen and its demos", "Opening files: any supported format, or drag and drop",
                                                    "Files, signals and the three areas"], ch_workspace)
    chapter(f, app, "CHAPTER 2", "Plots and cursors", ["Click a signal to plot it; Ctrl+click to add it to the same plot",
                                                        "One cursor for values, two cursors for the change between them",
                                                        "Zoom, pan, and every spike kept on screen"], ch_plots, keep=True)
    chapter(f, app, "CHAPTER 3", "Comparing runs", ["Every shared signal ranked by how different it is",
                                                     "A golden run and tolerances give a pass / fail verdict",
                                                     "Runs on different clocks are aligned first (Align time)"], ch_compare, keep=True)
    chapter(f, app, "CHAPTER 4", "Checks", ["One verdict per file, for any format",
                                             "Limits per phase or mode, data quality, a log's health check",
                                             "The same checks in CI: signalviewer-cli check"], ch_checks)
    chapter(f, app, "CHAPTER 5", "What changed first", ["Two cursors around the moment it went wrong",
                                                         "The signals that left their usual range, in time order",
                                                         "The likeliest cause first – a lead, not a proof"], ch_investigate)
    chapter(f, app, "CHAPTER 6", "Reports", ["One HTML page that opens with the process in brief",
                                              "Plots, map and 3D on one time bar – any browser, offline",
                                              "PDF and Word as well"], ch_report, keep=True)
    chapter(f, app, "CHAPTER 7", "Working fast", ["Ctrl+K – any command or signal by name", "Ctrl+Z – undo anything in the workspace",
                                                   "Templates and profiles – the same view on the next run"], ch_keys, keep=True)
    chapter(f, app, "CHAPTER 8", "Map and 3D", ["Any recording with positions, on a map – offline by default",
                                                 "Cameras named by what they do: From above, Around it, Behind it, Cockpit",
                                                 "Height profile, arrows along the path, your own maps"], ch_map, prepare=prep_map)
    chapter(f, app, "CHAPTER 9", "Sweeps", ["A table of results – or start from nothing",
                                             "The parameter sets that hold in every scenario, and the best one",
                                             "A loop that runs your simulation until the best stops changing"], ch_sweeps)

    f.cap()
    f.slide("", "You are ready", ["Start from a demo on the welcome screen, then open your own files",
                                  "The user guide: davidalpert11.github.io/SignalViewer",
                                  "Questions and ideas: github.com/DavidAlpert11/SignalViewer"], "Signal Viewer · engineering data workbench", hold=5.5)
    end = f.now()
    vid = str(pg.video.path())
    ctx.close()
    return vid, start, end, f.cuts


def main() -> None:
    from playwright.sync_api import sync_playwright
    make_demo_video.OUT = OUT                       # the encoder writes here
    app = App()
    tmp = tempfile.mkdtemp(prefix="sv-training-")
    try:
        with sync_playwright() as p:
            exe = os.environ.get("SV_CHROMIUM")
            b = p.chromium.launch(**({"executable_path": exe} if exe else {}),
                                  args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
            vid, start, end, cuts = record(b, app, tmp)
            b.close()
        cut_and_encode(vid, start, end, cuts)
    finally:
        app.close()


if __name__ == "__main__":
    main()
