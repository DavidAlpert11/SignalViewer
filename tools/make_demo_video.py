"""
A short demo for engineers: Signal Viewer with simulation data (docs/media/demo_simulation.mp4).

    python tools/make_demo_video.py            # needs Playwright (+ a Chromium: SV_CHROMIUM) and ffmpeg

The story, recorded from the app itself on the shipped examples (no network): a MATLAB model and the flight it
should match open on two clocks -> the app finds the time offset by itself -> the flight is judged against the
model within the tolerances file the CI reads -> the worst moment, one click away -> a parameter study runs the
user's own simulation round after round until the best stops changing -> one gain set for three drones.
Captions are drawn in the page; waiting (a simulation round) is cut out of the film.
"""
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_readme_media import MEDIA, App, H, W, no_toasts, reset  # noqa: E402

OUT = os.path.join(MEDIA, "demo_simulation.mp4")

OVERLAY = r"""
(() => {
  const st = document.createElement('style');
  st.textContent = `
  #demo-cap { position: fixed; left: 50%; bottom: 46px; transform: translateX(-50%); z-index: 99999; max-width: 1180px;
    padding: 14px 26px; border-radius: 14px; background: rgba(10,14,20,.86); color: #fff; text-align: center;
    font: 600 26px/1.3 'IBM Plex Sans', system-ui, sans-serif; box-shadow: 0 10px 40px rgba(0,0,0,.45);
    transition: opacity .35s ease; pointer-events: none; }
  #demo-cap small { display: block; margin-top: 6px; font-weight: 400; font-size: 18px; color: #b8c4d4; }
  #demo-title { position: fixed; inset: 0; z-index: 100000; display: flex; flex-direction: column; align-items: center;
    justify-content: center; background: radial-gradient(circle at 50% 40%, #16202c, #07090d 70%); color: #fff;
    font-family: 'IBM Plex Sans', system-ui, sans-serif; transition: opacity .6s ease; pointer-events: none; }
  #demo-title h1 { font-size: 64px; margin: 0 0 14px; letter-spacing: -.5px; }
  #demo-title p { font-size: 26px; margin: 0; color: #b8c4d4; max-width: 1100px; text-align: center; line-height: 1.4; }
  #demo-title .tag { margin-top: 34px; font-size: 18px; color: #f2a33a; letter-spacing: 2px; text-transform: uppercase; }`;
  document.head.appendChild(st);
  window.__cap = (text, sub) => {
    let c = document.getElementById('demo-cap');
    if (!text) { if (c) c.style.opacity = 0; return; }
    if (!c) { c = document.createElement('div'); c.id = 'demo-cap'; document.body.appendChild(c); }
    c.innerHTML = text + (sub ? `<small>${sub}</small>` : ''); c.style.opacity = 1;
  };
  window.__title = (h, p, tag) => {
    let d = document.getElementById('demo-title');
    if (!h) { if (d) { d.style.opacity = 0; setTimeout(() => d.remove(), 700); } return; }
    if (!d) { d = document.createElement('div'); d.id = 'demo-title'; document.body.appendChild(d); }
    d.innerHTML = `<h1>${h}</h1><p>${p || ''}</p>${tag ? `<div class="tag">${tag}</div>` : ''}`; d.style.opacity = 1;
  };
})()
"""


class Film:
    """The recording's clock, and the stretches to cut (waiting) - in recorded seconds."""

    def __init__(self, pg):
        self.pg, self.t0, self.cuts = pg, time.time(), []

    def now(self) -> float:
        return time.time() - self.t0

    def overlay(self):
        self.pg.evaluate(OVERLAY)

    def cap(self, text="", sub="", hold=0.0):
        self.pg.evaluate("([a, b]) => window.__cap(a, b)", [text, sub])
        if hold:
            self.pg.wait_for_timeout(int(hold * 1000))

    def title(self, h="", p="", tag="", hold=0.0):
        self.pg.evaluate("([a, b, c]) => window.__title(a, b, c)", [h, p, tag])
        if hold:
            self.pg.wait_for_timeout(int(hold * 1000))

    def glide(self, locator, click=True, button="left"):
        """The pointer moves to the control as a person's would, then clicks."""
        locator.scroll_into_view_if_needed()
        self.pg.wait_for_timeout(300)
        box = locator.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.pg.mouse.move(x, y, steps=28)
        self.pg.wait_for_timeout(250)
        if click:
            self.pg.mouse.click(x, y, button=button)

    def wait_cut(self, fn, keep=1.2):
        """Run a slow step (a simulation round); keep its first `keep` seconds and its end, cut the rest."""
        a = self.now()
        fn()
        b = self.now()
        if b - a > keep + 1.5:
            self.cuts.append((a + keep, b - 0.8))


def fresh(film, app) -> None:
    """Behind a chapter card: close everything (server side) and reload to the welcome screen."""
    reset(app)
    film.pg.reload()
    film.pg.wait_for_selector(".ex-card", timeout=30000)
    film.pg.evaluate("window.__sv.setState({ theme: 'dark' })")
    film.overlay()


def record(b, app, tmp) -> tuple:
    reset(app)
    ctx = b.new_context(viewport={"width": W, "height": H}, color_scheme="dark",
                        record_video_dir=tmp, record_video_size={"width": W, "height": H})
    pg = ctx.new_page()
    film = Film(pg)
    pg.goto(app.url)
    pg.wait_for_selector(".ex-card[data-example='simVsFlight']")
    pg.evaluate("window.__sv.setState({ theme: 'dark' })")
    film.overlay()
    start = film.now()                                   # the loading before this is cut

    # 1 - the title
    film.title("Simulation vs. reality", "Does the flight do what the model says it will? Answered in a minute –<br>"
               "on your own machine, with your own files.", "Signal Viewer · engineering data workbench", hold=4.2)
    film.title()
    pg.wait_for_timeout(700)

    # 2 - two files, two clocks
    film.cap("A Simulink model (.mat) and the real flight (.bin)", "Opened together – every signal on one time axis")
    film.glide(pg.locator(".ex-card[data-example='simVsFlight']"))
    pg.wait_for_function("window.__sv.state().runs.filter((r) => r.format !== 'derived').length === 2", timeout=30000)
    pg.wait_for_selector(".grid canvas", timeout=30000)
    pg.wait_for_timeout(2400)
    no_toasts(pg)
    film.cap("But they were recorded on two different clocks", "The model starts at 0 s; the flight's doublets come 100 s later", hold=3.6)

    # 3 - the app finds the offset itself
    film.cap("Align time: the app finds the offset by itself", "Matching signals in both files, correlated")
    film.glide(pg.locator(".run-head").filter(has_text="flight_attitude").first, button="right")
    pg.wait_for_timeout(700)
    film.glide(pg.get_by_text("Align time with another file").first)
    pg.wait_for_selector("text=Signal correlation", timeout=30000)
    pg.wait_for_timeout(2600)
    film.cap("−104.369 s · correlation 0.998 – confirmed on a second signal", "No manual sliding, no guessing", hold=2.6)
    film.glide(pg.get_by_role("button", name="Apply", exact=True).first)
    pg.wait_for_timeout(1800)
    no_toasts(pg)
    film.cap("Aligned. Model and flight, sample by sample", "The raw data is untouched – the offset is recorded and undoable", hold=3.6)

    # 4 - judged against the model
    film.cap("Compare: the flight judged against the model", "Per-signal tolerances – the same file the CI reads")
    pg.evaluate("""async (tol) => {
      const t = await (await fetch('/api/compare/tolerances/load', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: tol }) })).json();
      window.__sv.setState({ compareTol: t.tolerances }); }""", app.path("sim_vs_flight/tolerances.json"))
    film.glide(pg.locator("[aria-label='Compare runs']").first)
    pg.wait_for_selector(".sim-row", timeout=30000)
    pg.wait_for_timeout(2600)
    film.cap("Verdict: 2 of 7 signals outside their tolerance", "Every signal ranked by how far the flight is from the model", hold=3.4)
    worst = pg.get_by_role("button", name="Show the worst failure")
    if worst.count():
        film.cap("One click to the worst moment", "The cursor lands on it, in every plot")
        film.glide(worst.first)
        pg.wait_for_timeout(3200)
    film.cap("Pass / fail you can defend", "signalviewer-cli compare model.mat flights/*.bin --tolerances tol.json  →  exit 1", hold=3.6)

    # 5 - a parameter study that runs your simulation (a chapter card covers the switch to a fresh workspace)
    film.cap()
    film.title("Now tune it", "A parameter study that runs your own simulation –<br>round after round, until the best stops changing.",
               "Sweeps")
    fresh(film, app)
    film.title("Now tune it", "A parameter study that runs your own simulation –<br>round after round, until the best stops changing.",
               "Sweeps", hold=3.0)
    film.title()
    pg.wait_for_timeout(600)
    film.cap("The smart-sweep demo: a drone model in Python", "Sweeps proposes the next runs, starts your program, reads the results")
    film.glide(pg.locator(".ex-card[data-example='smartSweepDemo']").first)
    pg.wait_for_selector(".dm-strip", timeout=60000)
    if pg.locator(".dm-reset").is_enabled():
        pg.locator(".dm-reset").click()
        pg.wait_for_function("document.querySelector('.dm-strip').dataset.round === '0'")
    pg.wait_for_timeout(1600)
    for k in (1, 2, 3):
        film.cap(f"Round {k}: your simulation runs on your PC", "Only the runs that can still change the answer")
        film.glide(pg.locator(".dm-next").first)
        film.wait_cut(lambda k=k: pg.wait_for_function(
            f"document.querySelector('.dm-chart')?.dataset.points === '{k}' && "
            "document.querySelector('[data-shot=demo]').dataset.settled === '1'", timeout=300000))
        pg.wait_for_timeout(1800)
    film.cap("It converges on the full grid's optimum", "With a fraction of the runs – each round's table kept, continue tomorrow", hold=4.0)

    # 6 - one set for several systems
    film.cap()
    film.title("One set for every system", "Three different drones – which gains hold for all of them?", "Sweeps · common parameters")
    fresh(film, app)
    film.title("One set for every system", "Three different drones – which gains hold for all of them?", "Sweeps · common parameters", hold=2.6)
    film.title()
    # FR11: the three drones are in Help -> Examples (six cards on the welcome screen)
    film.glide(pg.locator(".topbar .menubar-btn", has_text="Help"))
    film.glide(pg.locator(".menu.ctx button", has_text="Examples"))
    film.glide(pg.locator(".menu.ctx.sub button", has_text="one gain set, three drones"))
    pg.wait_for_selector("[data-shot][data-settled='1']", timeout=120000)
    pg.wait_for_timeout(1500)
    film.cap("The sets that hold for all three, ranked together", "And why the others fail – per drone, per scenario", hold=4.2)

    # 7 - the end
    film.cap()
    film.title("Signal Viewer", "Align · compare · judge · tune – simulation and test data, side by side.<br>"
               "Offline, free (MIT), English and Hebrew.", "github.com/DavidAlpert11/SignalViewer", hold=4.5)
    end = film.now()
    vid = str(pg.video.path())
    ctx.close()
    return vid, start, end, film.cuts


def cut_and_encode(vid: str, start: float, end: float, cuts: list) -> None:
    """Keep [start, end] minus the cuts (the recording's clock lags the wall clock while loading: measured
    from the end, as finish_video does), then H.264 for any player."""
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vid],
                               capture_output=True, text=True).stdout.strip())
    lag = max(0.0, (end - dur))                          # wall time the recording did not see (at its start)
    keep, t = [], start
    for a, b in sorted(cuts):
        keep.append((t, a)); t = b
    keep.append((t, end))
    parts = [(max(0.0, a - lag), max(0.0, b - lag)) for a, b in keep if b - a > 0.2]
    sel = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in parts)
    os.makedirs(MEDIA, exist_ok=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", vid,
                    "-vf", f"select='{sel}',setpts=N/FRAME_RATE/TB,fps=30", "-an",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", "-preset", "slow", "-movflags", "+faststart", OUT],
                   check=True)
    out = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", OUT],
                               capture_output=True, text=True).stdout.strip())
    print(f"video {os.path.relpath(OUT)}  {out:.0f} s, {os.path.getsize(OUT) // 1024} kB  (cut {len(cuts)} waits)")


def main() -> None:
    from playwright.sync_api import sync_playwright
    app = App()
    tmp = tempfile.mkdtemp(prefix="sv-demo-")
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
