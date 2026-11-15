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
  #tr-ring.on { opacity: 1; transform: scale(1); }`;
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


def chapter(film, app, no, title, items, show, foot=""):
    """A slide, then the live part (on a fresh workspace, behind the slide); a failure is logged and skipped."""
    film.cap()
    film.slide(no, title, items, foot)
    try:
        fresh(film, app)
        film.slide(no, title, items, foot, hold=5.5)
        film.slide()
        film.pg.wait_for_timeout(700)
        show(film, app)
    except Exception:
        print(f"chapter {no} '{title}' left out:\n{traceback.format_exc()[-600:]}")
        film.slide(no, title, items, foot)
        fresh(film, app)
        film.slide()


def open_example(film, ex, ready):
    film.glide(film.pg.locator(f".ex-card[data-example='{ex}']").first)
    film.pg.wait_for_selector(ready, timeout=90000)
    film.pg.wait_for_timeout(1800)
    no_toasts(film.pg)


# ----------------------------------------------------------------------------- the chapters
def ch_workspace(f, app):
    pg = f.pg
    f.cap("The welcome screen: a demo with a known answer for every area", "Recordings · Sweeps · Fleet – pick one to start", hold=3.2)
    pg.mouse.wheel(0, 500); pg.wait_for_timeout(1400); pg.mouse.wheel(0, -500); pg.wait_for_timeout(800)
    f.cap("Open a file – or drop it on the window", "Here: three test runs of a car, as CSV")
    open_example(f, "car", ".grid canvas")
    f.cap("Left: the files and their signals, grouped and searchable", "Units, rates and a sparkline for each signal", hold=3.6)
    f.cap("Top: the three areas, files, templates, Undo", "Every change to the workspace can be undone (Ctrl+Z)", hold=3.4)


def ch_plots(f, app):
    pg = f.pg
    open_example(f, "car", ".grid canvas")
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
    f.cap("Drag to zoom, double-click to fit – all plots share the time axis", "The plot shows every spike, even zoomed out", hold=3.4)


def ch_compare(f, app):
    pg = f.pg
    open_example(f, "car", ".grid canvas")
    f.cap("Compare: every shared signal ranked by how different it is")
    f.rail("Compare")
    pg.wait_for_selector(".sim-row", timeout=30000)
    pg.wait_for_timeout(2200)
    f.cap("Click a row: its signal from every run, overlaid")
    f.glide(pg.locator(".sim-row").first)
    pg.wait_for_timeout(2600)
    f.cap("Mark one run as golden, set tolerances – the verdict is pass / fail", "The same check runs from the command line, in CI", hold=3.6)


def ch_checks(f, app):
    pg = f.pg
    f.cap("Any file: here a pump on a test bench, as Parquet")
    open_example(f, "bench", ".grid canvas")
    f.cap("Checks: one verdict for the file")
    f.rail("Checks")
    pg.wait_for_timeout(2600)
    f.cap("Your limits, the data's own quality, a log's health check", "Gaps, stuck values, spikes – each a click from its moment", hold=4.0)
    f.cap("The file: the structure of any recording")
    f.glide(pg.locator("[role='tab'][data-tab='file']").first)
    pg.wait_for_timeout(3000)


def ch_investigate(f, app):
    pg = f.pg
    f.cap("A known fault: two runs, one went wrong")
    open_example(f, "investigate", ".grid canvas")
    f.cap("Investigate: name an event, find every time it happened")
    f.rail("Investigate")
    pg.wait_for_timeout(2800)
    f.cap("What changed? – put two cursors around the moment", "Signals that left their usual range, in time order, the likeliest cause first", hold=4.2)


def ch_map(f, app):
    pg = f.pg
    f.cap("Positions in the file: the run on a map")
    open_example(f, "flight", ".grid canvas, .geo canvas")
    pg.wait_for_timeout(1500)
    for name, say in (("From above", "From above: the whole track, north up"), ("Behind it", "Behind it: follow the object, the way it moves"),
                      ("Around it", "Around it: orbit the object at the cursor's time")):
        btn = pg.get_by_role("button", name=name).first
        if btn.count():
            f.cap(say)
            f.glide(btn)
            pg.wait_for_timeout(2400)
    f.cap("Map background: offline by default; online maps and your own are opt-in")
    f.glide(pg.locator(".map-layers-btn").first)
    pg.wait_for_timeout(2600)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(600)
    f.cap("Play: every plot, the map and the 3D view follow one time bar", hold=2.6)


def ch_sweeps(f, app):
    pg = f.pg
    f.cap("A table of runs: 810 runs of a controller sweep")
    open_example(f, "sweepTable", ".pp canvas")
    f.cap("Which parameter sets hold in every scenario – and the best one", "Data · Columns · Goal · Results: four steps", hold=4.0)
    f.cap("A study can also start from nothing", "Set up the parameters and ranges; the app runs your simulation round after round", hold=3.8)


def ch_report(f, app):
    pg = f.pg
    open_example(f, "car", ".grid canvas")
    f.cap("Report: what is on screen becomes one offline HTML page")
    f.rail("Report")
    pg.wait_for_timeout(2800)
    f.cap("It opens with the process in brief: the data, what was checked, the conclusion", "Any browser, no install – PDF and Word too", hold=4.0)


def ch_keys(f, app):
    pg = f.pg
    open_example(f, "car", ".grid canvas")
    f.cap("Ctrl+K: every command and every signal, by name")
    pg.keyboard.press("Control+k"); pg.wait_for_timeout(700)
    pg.keyboard.type("two cursors", delay=70); pg.wait_for_timeout(1800)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
    f.cap("Templates: save this view, apply it to the next run", "Profiles add their numbers to the run at a glance", hold=3.6)


def record(b, app, tmp):
    make_demo_video.OVERLAY  # the captions' and titles' styles
    reset(app)
    ctx = b.new_context(viewport={"width": W, "height": H}, color_scheme="dark",
                        record_video_dir=tmp, record_video_size={"width": W, "height": H})
    pg = ctx.new_page()
    f = Lesson(pg)
    pg.goto(app.url)
    pg.wait_for_selector(".ex-card[data-example='car']")
    pg.evaluate("window.__sv.setState({ theme: 'dark' })")
    f.overlay()
    start = f.now()

    f.slide("TRAINING", "Signal Viewer in ten minutes",
            ["From raw measurements to an engineering answer you can defend",
             "Any time-series data: test runs, logs, simulations, ROS 2, CAN",
             "Everything on your own machine – no account, no internet"],
            "English and Hebrew · free and open source (MIT)", hold=6.0)
    f.slide("AGENDA", "What you will learn",
            ["1 · The workspace   2 · Plots and cursors   3 · Comparing runs",
             "4 · Checks and limits   5 · Investigating a fault   6 · Map and 3D",
             "7 · Sweeps   8 · Reports   9 · Working fast"], hold=6.0)

    chapter(f, app, "CHAPTER 1", "The workspace", ["The welcome screen and its demos", "Opening files: any supported format, or drag and drop",
                                                    "Files, signals and the three areas"], ch_workspace)
    chapter(f, app, "CHAPTER 2", "Plots and cursors", ["Click a signal to plot it; Ctrl+click to add it to the same plot",
                                                        "One cursor for values, two cursors for the change between them",
                                                        "Zoom, pan, and every spike kept on screen"], ch_plots)
    chapter(f, app, "CHAPTER 3", "Comparing runs", ["Every shared signal ranked by how different it is",
                                                     "A golden run and tolerances give a pass / fail verdict",
                                                     "Runs on different clocks are aligned first (Align time)"], ch_compare)
    chapter(f, app, "CHAPTER 4", "Checks and limits", ["One verdict per file, for any format",
                                                        "Limits per phase or mode, data quality, a log's health check",
                                                        "The same checks in CI: signalviewer-cli check"], ch_checks)
    chapter(f, app, "CHAPTER 5", "Investigating a fault", ["Name an event and find every time it happened",
                                                            "What changed? – the first signal to move, and what led what",
                                                            "Findings and notes, kept with the session"], ch_investigate)
    chapter(f, app, "CHAPTER 6", "Map and 3D", ["Any recording with positions, on an offline map",
                                                 "Cameras named by what they do: From above, Behind it, Around it, Cockpit",
                                                 "Height profile, arrows along the path, your own maps"], ch_map)
    chapter(f, app, "CHAPTER 7", "Sweeps", ["A table of results – or start from nothing",
                                             "The parameter sets that hold in every scenario, one set for several systems",
                                             "A loop that runs your simulation until the best stops changing"], ch_sweeps)
    chapter(f, app, "CHAPTER 8", "Reports", ["One HTML page that opens with the process in brief",
                                              "Plots, map and 3D on one time bar – any browser, offline",
                                              "PDF and Word as well"], ch_report)
    chapter(f, app, "CHAPTER 9", "Working fast", ["Ctrl+K – any command or signal by name", "Ctrl+Z – undo anything in the workspace",
                                                   "Templates and profiles – the same view on the next run"], ch_keys)

    f.cap()
    f.slide("", "You are ready", ["Start from a demo on the welcome screen, then open your own files",
                                  "The user guide: davidalpert11.github.io/SignalViewer",
                                  "Questions and ideas: github.com/DavidAlpert11/SignalViewer"], "Signal Viewer · engineering data workbench", hold=6.0)
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
            b = p.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--no-sandbox"])
            vid, start, end, cuts = record(b, app, tmp)
            b.close()
        cut_and_encode(vid, start, end, cuts)
    finally:
        app.close()


if __name__ == "__main__":
    main()
