"""
The training film: Signal Viewer taught like a presentation, as a video (docs/media/training.mp4).

    python tools/make_training_video.py          # needs Playwright (+ a Chromium: SV_CHROMIUM) and ffmpeg

Each chapter opens with a slide (what you will learn, in a few lines), then shows it live in the app on the
shipped examples, with captions and a ring where the pointer clicks - and a voice that says what is done and why
(tools/narration.py: Piper, on this machine; --silent for none). Recorded from the app itself, offline (the voice
model is fetched once).
A chapter that cannot be shown (an example missing) is left out with a note in the log - the film goes on.
"""
import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_demo_video import Film, cut_and_encode, fresh  # noqa: E402
from make_readme_media import MEDIA, MENU_LABEL, App, H, W, _wide_panel, no_toasts, reset  # noqa: E402
import make_demo_video  # noqa: E402
from narration import Narrator  # noqa: E402

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
    """The demo film's tools, plus slides, a ring where the pointer clicks, and the voice: each line spoken at the
    film's moment (the recording's clock less the waits cut), the next line or step only once it is said."""

    def __init__(self, pg, narrator=None):
        super().__init__(pg)
        self.nar, self.voice, self.voice_end, self.start = narrator, [], 0.0, 0.0

    def final(self, t: float) -> float:
        """A moment of the recording in the finished film: from its start, the cut waits taken out."""
        return t - self.start - sum(max(0.0, min(b, t) - a) for a, b in self.cuts if a < t)

    def wait_voice(self, pad=0.35):
        rem = self.voice_end - self.final(self.now())
        if rem > -pad:
            self.pg.wait_for_timeout(int((rem + pad) * 1000))

    def say(self, text, wait=True):
        if not self.nar:
            return
        self.wait_voice()
        a = self.nar.speak(text)
        t = self.now()
        self.voice.append((t, a))
        self.voice_end = self.final(t) + len(a) / self.nar.rate
        if wait:
            self.wait_voice()

    def cap(self, text="", sub="", hold=0.0, say=None, wait=True):
        super().cap(text, sub)
        if say:
            self.say(say, wait)
        if hold and not (say and self.nar):
            self.pg.wait_for_timeout(int(hold * 1000))

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


def chapter(film, app, no, title, items, show, foot="", keep=False, prepare=None, voice=""):
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
        film.slide(no, title, items, foot, hold=0.0 if (voice and film.nar) else 5.0)
        if voice:
            film.say(voice)
            film.pg.wait_for_timeout(500)
        film.slide()
        film.pg.wait_for_timeout(700)
        show(film, app)
    except Exception:
        print(f"chapter {no} '{title}' left out:\n{traceback.format_exc()[-600:]}")
        film.slide(no, title, items, foot)
        fresh(film, app)
        film.slide()


def help_example(film, label, glide=True):
    """Help -> Examples -> label, as a hand does it: sideways into the submenu first, then down to the item (a
    diagonal path crosses the next item of the menu, which closes the submenu)."""
    pg = film.pg
    if not glide:
        pg.locator(".topbar .menubar-btn", has_text="Help").first.click()
        pg.locator(".menu.ctx button", has_text="Examples").first.click()
        pg.locator(".menu.ctx.sub button", has_text=label).first.click()
        return
    film.glide(pg.locator(".topbar .menubar-btn", has_text="Help").first)
    ex = pg.locator(".menu.ctx button", has_text="Examples").first
    film.glide(ex)
    item = pg.locator(".menu.ctx.sub button", has_text=label).first
    item.wait_for()
    eb, ib = ex.bounding_box(), item.bounding_box()
    pg.mouse.move(ib["x"] + ib["width"] / 2, eb["y"] + eb["height"] / 2, steps=12)
    film.glide(item)


def open_example(film, ex, ready, glide=True):
    """A welcome card - or, for the examples without one (FR11: six cards), Help -> Examples."""
    pg = film.pg
    card = pg.locator(f".ex-card[data-example='{ex}']").first
    if card.count():
        film.glide(card) if glide else card.click()
    else:
        help_example(film, MENU_LABEL[ex], glide)
    film.pg.wait_for_selector(ready, timeout=90000)
    film.pg.wait_for_function("window.__sv.state().busy === 0 && !document.querySelector('.job')", timeout=90000)
    film.pg.wait_for_timeout(1200)
    no_toasts(film.pg)


# ----------------------------------------------------------------------------- the chapters
def ch_workspace(f, app):
    pg = f.pg
    f.cap("The welcome screen: a demo with a known answer for every area", "Recordings · Sweeps – pick one to start",
          say="This is the welcome screen. Each card opens a demo with a known answer, so you can learn every area on real data before you open your own files.", hold=3.2)
    pg.mouse.wheel(0, 500); pg.wait_for_timeout(1400); pg.mouse.wheel(0, -500); pg.wait_for_timeout(800)
    f.cap("Open a file – or drop it on the window", "Here: three test runs of a car, as CSV",
          say="To open a file, use the Open button, or simply drop it on the window. Here we open three test runs of a car.", wait=False)
    open_example(f, "car", ".grid canvas")
    f.cap("Left: the files and their signals, grouped and searchable", "Units, rates and a sparkline for each signal",
          say="On the left are the files and their signals. Each signal shows its unit, its sample rate and a small picture of its shape. Type in the search box to find one by name.", hold=3.4)
    f.cap("Top: the three areas, files, templates, Undo", "Every change to the workspace can be undone (Ctrl+Z)",
          say="The top bar holds the areas, the file actions, templates and undo. Every change to the workspace can be undone with control Z.", hold=3.2)


def ch_plots(f, app):
    pg = f.pg
    f.cap("Click a signal to plot it – Ctrl+click adds it to the same plot",
          say="Click a signal to plot it. Control click adds it to the same plot.", wait=False)
    f.glide(pg.locator(".sig", has_text="RPM").first)
    pg.wait_for_timeout(1500)
    f.cap("The cursor: values of every line at one moment", "Space turns it on and off",
          say="Turn on the cursor to read the value of every line at one moment. The space bar turns it on and off.", wait=False)
    f.glide(pg.locator(".stage-bar .cursor-btn").first)
    box = pg.locator(".grid canvas").first.bounding_box()
    for k in range(9):
        pg.mouse.move(box["x"] + box["width"] * (0.2 + 0.07 * k), box["y"] + box["height"] * 0.5, steps=6)
        pg.wait_for_timeout(160)
    pg.mouse.click(box["x"] + box["width"] * 0.45, box["y"] + box["height"] * 0.5)
    pg.wait_for_timeout(1200)
    f.cap("Two cursors: the change between them, Δ, in the legend", "D toggles them",
          say="Two cursors show the change between two moments, delta, right in the legend.", wait=False)
    f.glide(pg.locator(".stage-bar .cursor-btn").nth(1))
    pg.wait_for_timeout(2600)
    f.cap("Drag to zoom, double-click to fit – all plots share the time axis", "The plot shows every spike, even zoomed out",
          say="Drag across a plot to zoom, and double click to see everything again. Even zoomed out, every spike is drawn: nothing is hidden by thinning.", wait=False)
    pg.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] * 0.5)
    pg.mouse.down(); pg.mouse.move(box["x"] + box["width"] * 0.55, box["y"] + box["height"] * 0.5, steps=20); pg.mouse.up()
    pg.wait_for_timeout(1800)
    pg.mouse.dblclick(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
    pg.wait_for_timeout(1400)


def ch_compare(f, app):
    pg = f.pg
    f.cap("Compare: the same three runs – every shared signal ranked by how different it is",
          say="Compare puts the three runs side by side. Every signal they share is ranked by how different it is between the runs.", wait=False)
    f.rail("Compare")
    pg.wait_for_selector(".sim-row", timeout=30000)
    pg.wait_for_timeout(2200)
    f.cap("Click a row: its signal from every run, overlaid", say="Click a row to see that signal from every run, overlaid.", wait=False)
    f.glide(pg.locator(".sim-row").first)
    pg.wait_for_timeout(2600)
    f.cap("Mark one run as golden, set tolerances – the verdict is pass / fail", "The same check runs from the command line, in CI",
          say="Mark one run as the golden reference and set tolerances, and the answer becomes pass or fail. The same check runs from the command line, so it can guard your continuous integration.", hold=3.4)


def ch_checks(f, app):
    pg = f.pg
    f.cap("Any file: here a pump on a test bench, as Parquet", say="Checks work on any file. Here, a pump on a test bench.", wait=False)
    open_example(f, "bench", ".grid canvas")
    f.cap("Checks: one verdict for the file", say="Open Checks for one verdict on the whole file.", wait=False)
    f.rail("Checks")
    pg.wait_for_timeout(2600)
    f.cap("Your limits, the data's own quality, a log's health check", "Gaps, stuck values, spikes – each a click from its moment",
          say="It combines your own limits with the quality of the data itself: gaps, stuck values and spikes. Each finding is one click away from its moment in the plots.", hold=3.6)
    f.cap("The file: the structure of any recording", say="The File tab shows the structure of the recording.", wait=False)
    f.glide(pg.locator("[role='tab'][data-tab='file']").first)
    pg.wait_for_timeout(2800)


def ch_investigate(f, app):
    pg = f.pg
    f.cap("A known fault: a drone in three gusts – the heavy run loses its roll",
          say="Now a known fault. A drone flies through three gusts, and the heavy run loses its roll.", wait=False)
    open_example(f, "investigate", ".grid canvas")
    roll = pg.locator(".sig").filter(has=pg.get_by_text("Roll", exact=True)).first
    if roll.count():
        f.glide(roll)
        pg.wait_for_timeout(1400)
    f.cap("What changed? – two cursors around the moment it went wrong",
          say="Put two cursors around the moment it went wrong, right-click, and ask: what changed?", wait=False)
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 38.46, t2: 39.24, active: 1 } })")
    pg.wait_for_timeout(1200)
    f.glide(pg.locator(".plot.active .plot-body").first, button="right")     # CC4: the span's actions, a right-click
    pg.wait_for_timeout(600)
    f.glide(pg.locator(".menu.ctx button", has_text="What changed?").first)
    pg.wait_for_selector(".wc-section", timeout=30000)
    pg.wait_for_timeout(1800)
    f.cap("The signals that left their usual range, in time order", "Wind first, then the vibration, motor 3 – and only then the roll",
          say="The app lists the signals that left their usual range, in the order they did. The wind first, then the vibration and motor three, and only then the roll. The first to move is the likeliest cause: a lead to check, not a proof.", hold=4.4)


def ch_messages(f, app):
    pg = f.pg
    f.cap("A serial link recorded byte by byte – both directions", say="Many test setups record a serial link or a radio byte by byte. This demo has both directions of one link.", wait=False)
    help_example(f, "a serial link")
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name.includes('link'))", timeout=60000)
    pg.wait_for_timeout(2500)
    no_toasts(pg)
    f.cap("Messages: every byte stream, MAVLink log and link in one place",
          say="Open the Messages panel. It is the one place for everything about messages: the byte streams in your files, the message types of logs such as MAVLink, the links running now, and a library of message structures.", wait=False)
    no_toasts(pg)
    f.rail("Messages")
    pg.wait_for_selector(".msgp-stream .msgp-types .chip-s", timeout=60000)
    _wide_panel(pg, 600)                            # the structure's fields table wants room
    no_toasts(pg)
    pg.wait_for_timeout(1500)
    f.cap("Found by themselves: the header, the checksum, each type and its rate", hold=3.0,
          say="The messages were found by themselves: the header, the length and type bytes, the checksum with its errors, and every message type with its rate.")
    f.cap("Open a stream: what it carries, then Propose a structure", say="Open a stream, and let the app propose what each message holds.", wait=False)
    f.glide(pg.locator(".msgp-stream[data-key$='/rx_byte'] .msgp-stream-head").first)
    pg.wait_for_timeout(900)
    f.glide(pg.locator(".msgp-stream.open .msg-propose").first)
    pg.wait_for_selector(".msgp-stream.open .msg-struct .msg-msg", timeout=30000)
    pg.evaluate("() => document.querySelector('.msgp-stream.open .msg-structure').scrollIntoView({ block: 'start', behavior: 'smooth' })")
    pg.wait_for_timeout(1500)
    f.cap("Each field guessed: 16-bit LSB or MSB first, signed, 32-bit, float", "Rename the fields, give the scale and the unit",
          say="Each field is guessed from how it moves: sixteen bit values with the low or the high byte first, signed values, thirty two bit numbers and floats. Rename the fields, give a scale and a unit, and save the structure to the library for next time.", hold=3.4)
    f.cap("Make the recording: every value becomes a signal", say="Make the recording, and every value becomes a signal, ready for plots, the map and the report.", wait=False)
    f.glide(pg.locator(".msgp-stream.open .msg-make").first)
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name === 'rx_byte - messages')", timeout=60000)
    pg.wait_for_timeout(2600)
    no_toasts(pg)
    f.cap("Live too: Live ▾ → Listen to a link – serial, UDP or TCP", hold=3.0,
          say="The same works live. In the Live menu, listen to a serial port, U D P or T C P: the bytes are recorded to a file and decoded as they arrive.")


def ch_report(f, app):
    pg = f.pg
    f.cap("A report from ready-made parts – one click", say="Reports. This demo opens two test missions; one click and the app writes the report by itself.", wait=False)
    help_example(f, "a test report, step by step")
    pg.wait_for_selector(".demo-guide .demo-next", timeout=60000)
    pg.locator(".demo-guide .demo-next").click()
    pg.wait_for_function("(window.__sv.state().reportPreviewHtml || '').includes('class=\"plot')", timeout=120000)
    pg.wait_for_timeout(2500)
    no_toasts(pg)
    f.cap("Write on the left, the page on the right – updated as you type",
          say="On the left is the text: you write it like a document. On the right is the page it makes, updated as you type.", hold=3.2)
    f.cap("Ready-made parts: commanded vs actual, navigation errors, differences",
          say="The automatic report is made of ready-made parts: commanded against actual, navigation errors, the scenario and its special moments, and the main differences between the files. Every number is computed on every sample.", hold=3.4)
    fr = next((x for x in pg.frames if x != pg.main_frame), None)
    if fr:
        for _ in range(4):
            fr.evaluate("window.scrollBy({ top: 420, behavior: 'smooth' })")
            pg.wait_for_timeout(900)
    f.cap("One HTML file – any browser, offline – or PDF and Word", hold=3.0,
          say="Save it as one H T M L file that opens in any browser, offline, with live plots. Or as P D F and Word.")


def ch_keys(f, app):
    pg = f.pg
    f.cap("Ctrl+K: every command and every signal, by name", say="Control K finds any command or any signal by its name.", wait=False)
    pg.keyboard.press("Control+k"); pg.wait_for_timeout(700)
    pg.keyboard.type("motor", delay=80); pg.wait_for_timeout(1800)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
    f.cap("Ctrl+Z undoes any change to the workspace", "Templates: save this view, apply it to the next run",
          say="Control Z undoes any change. And a template saves the view you built, to apply it to the next run with one click.", hold=3.4)


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
    open_example(f, "flight", ".grid", glide=False)
    globe_ready(pg)
    no_toasts(pg)


def ch_map(f, app):
    """From above, then tilted the way a user does (Ctrl+drag): the ground's relief with the track over it. The
    tiles of the tilted view take long to draw without a graphics card: that wait is cut, and the camera holds
    still there (playing in it would crawl in the recording)."""
    pg = f.pg
    f.cap("Positions in the file: the run on a map", "Here the satellite map with its roads – the offline map is the default", hold=3.4,
          say="When a file has positions, the run appears on a map. Here, satellite photos with roads. The offline map is the default, so nothing leaves your machine unless you choose an online map.")
    box = pg.locator(".plot:has(.globe3d)").first.bounding_box()
    cx, cy = box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.6
    f.cap("Tilt it – Ctrl+drag or the middle button – and the ground has its heights",
          say="Tilt the view with control drag, and the ground shows its heights.", wait=False)
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
          "Cameras named by what they do: From above · Around it · Behind it · Cockpit", hold=5.0,
          say="Play moves the vehicle along its track, and every plot follows on the same time bar. The cameras are named by what they do: from above, around it, behind it, and the cockpit.")


def ch_sweeps(f, app):
    pg = f.pg
    f.cap("A table of runs: 810 runs of a controller sweep", "Opened with its question: which settings hold in every scenario",
          say="Sweeps works on tables of runs. Here, eight hundred and ten runs of a controller sweep, opened with its question: which settings hold in every scenario?", wait=False)
    open_example(f, "sweepTable", ".pp canvas")
    pg.wait_for_timeout(1500)
    f.cap("Each line is one run – the ones that hold every limit stand out, the best is marked", hold=3.6,
          say="Each line is one run. The runs that hold every limit stand out, and the best one is marked.")
    goals = pg.locator(".sw-step-btn[data-step='goals']").first
    if goals.count():
        f.cap("The question is plain: limits on the outputs, then what is best",
              say="The question is written plainly: limits on the outputs, then what counts as best.", wait=False)
        f.glide(goals)
        pg.wait_for_timeout(2600)
        f.glide(pg.locator(".sw-step-btn[data-step='results']").first)
        pg.wait_for_timeout(1800)
    f.cap("A study can also start from nothing", "Set the parameters and ranges; Sweeps runs your simulation round after round", hold=3.6,
          say="A study can also start from nothing. Set the parameters and their ranges, and Sweeps runs your own simulation round after round, until the best answer stops changing.")


def record(b, app, tmp, narrator=None):
    reset(app)
    ctx = b.new_context(viewport={"width": W, "height": H}, color_scheme="dark",
                        record_video_dir=tmp, record_video_size={"width": W, "height": H})
    ctx.add_init_script(HARDWARE_GL)
    pg = ctx.new_page()
    f = Lesson(pg, narrator)
    pg.goto(app.url)
    pg.wait_for_selector(".ex-card")
    pg.evaluate("window.__sv.setState({ theme: 'dark' })")
    f.overlay()
    start = f.start = f.now()

    f.slide("TRAINING", "Signal Viewer, step by step",
            ["From raw measurements to an engineering answer you can defend",
             "Any time-series data: test runs, logs, simulations, ROS 2, CAN",
             "Everything on your own machine – no account, no internet"],
            "Ten short chapters on the built-in demos · English and Hebrew · free and open source (MIT)", hold=0 if narrator else 5.5)
    f.say("Welcome to Signal Viewer. It takes you from raw measurements to an engineering answer you can defend. "
          "Test runs, flight logs, simulations, CAN and byte streams: everything runs on your own machine, with no account and no internet.")
    f.slide("AGENDA", "What you will learn",
            ["1 · The workspace   2 · Plots and cursors   3 · Comparing runs",
             "4 · Checks   5 · What changed first   6 · Messages",
             "7 · Reports   8 · Working fast   9 · Map and 3D   10 · Sweeps"], hold=0 if narrator else 5.0)
    f.say("In ten short chapters, on the demos that come with the app, you will learn the workspace, plots and cursors, comparing runs, "
          "checks, finding what changed first, messages, reports, working fast, the map and 3D, and Sweeps.")

    chapter(f, app, "CHAPTER 1", "The workspace", ["The welcome screen and its demos", "Opening files: any supported format, or drag and drop",
                                                    "Files, signals and the three areas"], ch_workspace,
            voice="Chapter one: the workspace. Where things are, and how to open your files.")
    chapter(f, app, "CHAPTER 2", "Plots and cursors", ["Click a signal to plot it; Ctrl+click to add it to the same plot",
                                                        "One cursor for values, two cursors for the change between them",
                                                        "Zoom, pan, and every spike kept on screen"], ch_plots, keep=True,
            voice="Chapter two: plots and cursors.")
    chapter(f, app, "CHAPTER 3", "Comparing runs", ["Every shared signal ranked by how different it is",
                                                     "A golden run and tolerances give a pass / fail verdict",
                                                     "Runs on different clocks are aligned first (Align time)"], ch_compare, keep=True,
            voice="Chapter three: comparing runs. Which signals differ, and by how much.")
    chapter(f, app, "CHAPTER 4", "Checks", ["One verdict per file, for any format",
                                             "Limits per phase or mode, data quality, a log's health check",
                                             "The same checks in CI: signalviewer-cli check"], ch_checks,
            voice="Chapter four: checks. One verdict for a file.")
    chapter(f, app, "CHAPTER 5", "What changed first", ["Two cursors around the moment it went wrong",
                                                         "The signals that left their usual range, in time order",
                                                         "The likeliest cause first – a lead, not a proof"], ch_investigate,
            voice="Chapter five: what changed first. Finding the cause of a fault.")
    chapter(f, app, "CHAPTER 6", "Messages", ["Byte streams found by themselves: header, length, type, checksum",
                                               "A structure proposed – fields LSB / MSB, signed, 32-bit – becomes a recording",
                                               "MAVLink logs, live links and the structure library in one panel"], ch_messages,
            voice="Chapter six: messages. From raw bytes on a link to signals you can plot.")
    chapter(f, app, "CHAPTER 7", "Reports", ["Write it like a document; the page beside it, live",
                                              "Ready reports made of ready-made parts – one click",
                                              "One HTML page, any browser, offline – PDF and Word too"], ch_report,
            voice="Chapter seven: reports. From what you found to a page you can send.")
    chapter(f, app, "CHAPTER 8", "Working fast", ["Ctrl+K – any command or signal by name", "Ctrl+Z – undo anything in the workspace",
                                                   "Templates and profiles – the same view on the next run"], ch_keys, keep=True,
            voice="Chapter eight: working fast.")
    chapter(f, app, "CHAPTER 9", "Map and 3D", ["Any recording with positions, on a map – offline by default",
                                                 "Cameras named by what they do: From above, Around it, Behind it, Cockpit",
                                                 "Height profile, arrows along the path, your own maps"], ch_map, prepare=prep_map,
            voice="Chapter nine: the map and 3D.")
    chapter(f, app, "CHAPTER 10", "Sweeps", ["A table of results – or start from nothing",
                                             "The parameter sets that hold in every scenario, and the best one",
                                             "A loop that runs your simulation until the best stops changing"], ch_sweeps,
            voice="Chapter ten: Sweeps. Which parameter sets hold, and which is best.")

    f.cap()
    f.slide("", "You are ready", ["Start from a demo on the welcome screen, then open your own files",
                                  "The user guide: davidalpert11.github.io/SignalViewer",
                                  "Questions and ideas: github.com/DavidAlpert11/SignalViewer"], "Signal Viewer · engineering data workbench", hold=0 if narrator else 5.5)
    f.say("You are ready. Start from a demo on the welcome screen, then open your own files. The user guide and the source are on GitHub. Thank you for watching.")
    f.pg.wait_for_timeout(1500)
    end = f.now()
    vid = str(pg.video.path())
    ctx.close()
    return vid, start, end, f.cuts, [(f.final(t), a) for t, a in f.voice]


def main() -> None:
    import argparse
    import subprocess
    from playwright.sync_api import sync_playwright
    a = argparse.ArgumentParser(description="The training film")
    a.add_argument("--silent", action="store_true", help="no voice")
    silent = a.parse_args().silent
    make_demo_video.OUT = OUT                       # the encoder writes here
    narrator = None if silent else Narrator()
    app = App()
    tmp = tempfile.mkdtemp(prefix="sv-training-")
    try:
        with sync_playwright() as p:
            exe = os.environ.get("SV_CHROMIUM")
            b = p.chromium.launch(**({"executable_path": exe} if exe else {}),
                                  args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
            vid, start, end, cuts, clips = record(b, app, tmp, narrator)
            b.close()
        cut_and_encode(vid, start, end, cuts)
        if narrator and clips:                      # the voice laid on the film: AAC beside the picture as it is
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", OUT],
                                       capture_output=True, text=True).stdout.strip())
            wav, mixed = os.path.join(tmp, "voice.wav"), os.path.join(tmp, "training.mp4")
            narrator.track(clips, dur, wav)
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", OUT, "-i", wav, "-map", "0:v", "-map", "1:a",
                            "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-t", f"{dur:.2f}", "-movflags", "+faststart", mixed], check=True)
            os.replace(mixed, OUT)
            print(f"voice: {len(clips)} lines, {os.path.getsize(OUT) // 1024} kB")
    finally:
        app.close()


if __name__ == "__main__":
    main()
