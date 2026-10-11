"""
Signal Viewer - browser-side performance benchmark (the server side is tools/benchmark.py).

Drives the real UI in headless Chromium and measures what the user feels: start-up, drawing,
zoom, cursor scrubbing, playback, a 3x3 grid, a 5000-signal file, a large template library and
memory over repeated work. Each group of scenarios runs against a fresh server; results are kept
in a JSON file so groups can run one at a time, then a Markdown report is written.

    python tools/browser_benchmark.py --data DIR --results results.json --group core
    python tools/browser_benchmark.py --data DIR --results results.json --group grid
    python tools/browser_benchmark.py --data DIR --results results.json --group wide
    python tools/browser_benchmark.py --data DIR --results results.json --group memory
    python tools/browser_benchmark.py --results results.json --report docs/benchmark_browser.md

DIR must hold big.csv (5M rows: Time + S0..S5 + Gear) and wide5k.csv (5000 signals); --make-data
creates them. Headless Chromium draws without a GPU, so frame rates are a conservative floor.
"""
import argparse
import json
import math
import os
import platform
import socket
import statistics
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ------------------------------------------------------------------ budgets
# (metric key, label, budget, "max" = lower is better / "min" = higher is better, unit)
BUDGETS = [
    ("startup_ms", "Start-up: page to ready app (median of 5)", 1500, "max", "ms"),
    ("startup_js_kb", "Start-up: JavaScript loaded", 800, "max", "KB"),
    ("startup_heap_mb", "Start-up: JS heap", 40, "max", "MB"),
    ("plot_add_ms", "Add a signal of a 5M-row file -> drawn (median of 4)", 300, "max", "ms"),
    ("zoom_p95_ms", "Zoom (wheel) -> redrawn, 4 signals, p95 of 10", 300, "max", "ms"),
    ("scrub_fps", "Cursor scrubbing, 4 signals: frames per second", 50, "min", "fps"),
    ("scrub_p95_frame_ms", "Cursor scrubbing: p95 frame time", 33, "max", "ms"),
    ("scrub_long_tasks", "Cursor scrubbing: long tasks (> 50 ms)", 0, "max", ""),
    ("play_draw_fps", "Playback (draw mode): frames per second", 50, "min", "fps"),
    ("play_cursor_fps", "Playback (cursor mode): frames per second", 50, "min", "fps"),
    ("timeline_drag_fps", "Dragging the timeline (draw mode), 4 signals: fps", 50, "min", "fps"),
    # draw mode redraws the series up to the time on every move: near the end that is nearly the
    # whole plot, ~52 ms on one CPU without a GPU - a few frames just over the 50 ms line
    ("timeline_drag_long_tasks", "Dragging the timeline (draw mode): long tasks (> 50 ms)", 5, "max", ""),
    ("grid_zoom_p95_ms", "3x3 grid, 36 series: zoom -> redrawn, p95", 500, "max", "ms"),
    ("grid_scrub_fps", "3x3 grid: cursor scrubbing fps", 30, "min", "fps"),
    ("wide_panel_ms", "5000-signal file: file panel shown", 300, "max", "ms"),
    ("wide_search_ms", "5000-signal file: search, last key -> results", 150, "max", "ms"),
    ("wide_scroll_fps", "5000-signal file: scrolling the file panel fps", 50, "min", "fps"),
    ("tpl_lib_open_ms", "200 templates: open the library", 300, "max", "ms"),
    ("tpl_runs_change_ms", "200 templates + 5000 signals: file opened -> panel updated", 200, "max", "ms"),
    ("map_first_view_ms", "Offline map, first view of an area (tiles drawn by the server, empty cache)", 8000, "max", "ms"),
    ("map_cached_view_ms", "Offline map, the same view again (cached tiles)", 1500, "max", "ms"),
    ("map_pan_fps", "Offline map: dragging (panning) fps", 30, "min", "fps"),
    ("map_object_play_fps", "Offline map with a moving object: playback fps", 30, "min", "fps"),
    # 3D: WebGL drawn in software here (no GPU) - a floor, far below a machine with a graphics card
    ("globe_first_view_ms", "3D view: shown with an object (CesiumJS loaded on first use), software WebGL", 20000, "max", "ms"),
    # here even a bare Cesium globe draws at ~1.2 fps (software WebGL on one CPU): a regression floor only
    ("globe_play_fps", "3D view: playback with an object, software WebGL on 1 CPU (floor)", 0.5, "min", "fps"),
    ("mem_per_cycle_kb", "Memory: heap growth per open/plot/close cycle, cycles 10-30", 30, "max", "KB"),
]

INIT_JS = r"""
(() => {
  const P = window.__perf = { longtasks: [], data: [], cursor: 0 };
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) P.longtasks.push([e.startTime, e.duration]); })
        .observe({ type: "longtask", buffered: true }); } catch (e) {}
  const f0 = window.fetch;
  window.fetch = async (...a) => {
    const url = String(a[0] && a[0].url || a[0]);
    const r = await f0(...a);
    if (url.includes("/api/data")) { await r.clone().arrayBuffer(); P.data.push(performance.now()); }
    if (url.includes("/api/cursor")) P.cursor++;
    return r;
  };
  window.__raf2 = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(performance.now()))));
  // frames recorded until stopped (for gestures whose length is not known in advance)
  window.__rec = () => { const R = window.__recState = { ts: [], on: true };
    const f = (t) => { if (!R.on) return; R.ts.push(t); requestAnimationFrame(f); }; requestAnimationFrame(f); };
  window.__recStop = () => { const R = window.__recState; R.on = false; return R.ts; };
  window.__frames = (ms) => new Promise((res) => {
    const ts = []; const t0 = performance.now();
    const f = (t) => { ts.push(t); if (t - t0 < ms) requestAnimationFrame(f); else res(ts); };
    requestAnimationFrame(f);
  });
})();
"""


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def frame_stats(ts):
    d = [b - a for a, b in zip(ts, ts[1:])] or [0]
    d.sort()
    span = (ts[-1] - ts[0]) / 1000 if len(ts) > 1 else 1
    return {"fps": round((len(ts) - 1) / span, 1) if span else 0,
            "p95": round(d[min(len(d) - 1, int(len(d) * 0.95))], 1)}


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(len(xs) * 0.95)) - 1)] if xs else None


class Bench:
    def __init__(self, data_dir, home):
        self.data, self.home = data_dir, home
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        env = dict(os.environ, HOME=home, USERPROFILE=home, NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
        self.proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "run.py"), "--port", str(self.port), "--no-open"],
                                     env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(120):
            try:
                urllib.request.urlopen(self.url, timeout=1)
                break
            except Exception:
                time.sleep(0.25)
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(args=["--no-sandbox", "--enable-precise-memory-info"])

    def close(self):
        try:
            self.browser.close()
            self.pw.stop()
        finally:
            self.proc.terminate()

    # -------------------------------------------------------------- helpers
    def api(self, path, body=None, method=None):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"}, method=method)
        return json.loads(urllib.request.urlopen(req, timeout=120).read() or b"null")

    def clear_runs(self):
        for r in self.api("/api/runs"):
            if r["format"] != "derived":
                self.api(f"/api/runs/{r['id']}", method="DELETE")

    def page(self):
        # start from an empty workspace: the app restores its autosave on load, which would carry
        # plots over from the previous scenario and skew every number after it
        auto = os.path.join(self.home, ".signalviewer", "autosave.json")
        if os.path.exists(auto):
            os.remove(auto)
        ctx = self.browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
        ctx.add_init_script(INIT_JS)
        pg = ctx.new_page()
        pg.goto(self.url)
        pg.wait_for_selector(".app")
        return pg

    @staticmethod
    def sync_runs(pg):
        pg.evaluate("fetch('/api/runs').then(r => r.json()).then(runs => window.__sv.setState({ runs }))")
        pg.wait_for_function("window.__sv.state().runs.length > 0")

    @staticmethod
    def heap_mb(pg, gc=False):
        cdp = pg.context.new_cdp_session(pg)
        if gc:
            cdp.send("HeapProfiler.collectGarbage")
        return cdp.send("Runtime.getHeapUsage")["usedSize"] / 1048576

    @staticmethod
    def long_tasks_since(pg, t0):
        return pg.evaluate(f"window.__perf.longtasks.filter(([s]) => s >= {t0}).map(([, d]) => d)")

    def add_signal_timed(self, pg, name, nth=0):
        """Click a signal in the file panel; ms until its data arrived and was drawn."""
        n0 = pg.evaluate("window.__perf.data.length")
        t0 = pg.evaluate("performance.now()")
        pg.locator(".sig", has_text=name).nth(nth).click()
        pg.wait_for_function(f"window.__perf.data.length > {n0}", timeout=30000)
        t1 = pg.evaluate("window.__raf2()")
        return t1 - t0

    def zoom_timed(self, pg, plot_index=0, steps=10):
        box = pg.locator(".plot .u-over").nth(plot_index).bounding_box()
        pg.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
        out = []
        for i in range(steps):
            n0 = pg.evaluate("window.__perf.data.length")
            t0 = pg.evaluate("performance.now()")
            pg.mouse.wheel(0, -240 if i < steps // 2 else 240)
            try:
                pg.wait_for_function(f"window.__perf.data.length > {n0}", timeout=10000)
            except Exception:
                pass                                          # served from what the plot already had
            out.append(pg.evaluate("window.__raf2()") - t0)
            pg.wait_for_timeout(150)
        return out

    def scrub(self, pg, plot_index=0, ms=2500):
        box = pg.locator(".plot .u-over").nth(plot_index).bounding_box()
        y = box["y"] + box["height"] * 0.5
        x0, x1 = box["x"] + 20, box["x"] + box["width"] - 20
        # place the cursor with a click, then DRAG its line (moving the mouse alone only hovers)
        pg.mouse.click(x0, y)
        pg.wait_for_timeout(300)
        pg.mouse.move(x0, y)
        pg.mouse.down()
        t0 = pg.evaluate("performance.now()")
        c0 = pg.evaluate("window.__perf.cursor")
        pg.evaluate("window.__rec()")
        steps = int(ms / 16)
        for i in range(steps):
            f = i / steps
            pg.mouse.move(x0 + (x1 - x0) * (f * 2 if f < 0.5 else 2 - f * 2), y)
        pg.mouse.up()
        pg.evaluate("window.__raf2()")
        ts = pg.evaluate("window.__recStop()")
        st = frame_stats(ts)
        lt = self.long_tasks_since(pg, t0)
        return st, lt, pg.evaluate("window.__perf.cursor") - c0


# ------------------------------------------------------------------ scenario groups
def group_core(b):
    r = {}
    # start-up
    times, js, heap = [], [], []
    for _ in range(5):
        ctx = b.browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
        ctx.add_init_script(INIT_JS)
        pg = ctx.new_page()
        pg.goto(b.url)
        pg.wait_for_selector(".app")
        times.append(pg.evaluate("window.__raf2()"))
        js.append(pg.evaluate("""performance.getEntriesByType('resource').filter(e => e.initiatorType === 'script' || /\\.js$/.test(e.name))
            .reduce((a, e) => a + (e.encodedBodySize || e.transferSize || 0), 0) / 1024"""))
        heap.append(b.heap_mb(pg, gc=True))
        ctx.close()
    r["startup_ms"] = round(statistics.median(times))
    r["startup_js_kb"] = round(statistics.median(js))
    r["startup_heap_mb"] = round(statistics.median(heap), 1)

    # 5M rows: open (cache warm-up outside the timing), then add 4 signals
    b.clear_runs()
    b.api("/api/files/open", {"paths": [os.path.join(b.data, "big.csv")]})
    pg = b.page()
    b.sync_runs(pg)
    pg.wait_for_selector(".sig")
    adds = [b.add_signal_timed(pg, s) for s in ("S0", "S1", "S2", "S3")]
    r["plot_add_ms"] = round(statistics.median(adds))
    r["plot_add_all_ms"] = [round(x) for x in adds]
    z = b.zoom_timed(pg)
    r["zoom_p95_ms"] = round(p95(z))
    r["zoom_median_ms"] = round(statistics.median(z))
    pg.keyboard.press("Space")                                     # cursor on
    st, lt, ncur = b.scrub(pg)
    r["scrub_fps"], r["scrub_p95_frame_ms"], r["scrub_long_tasks"] = st["fps"], st["p95"], len(lt)
    r["scrub_cursor_requests"] = ncur
    for mode in ("draw", "cursor"):
        pg.evaluate(f"window.__sv.setState({{ playMode: '{mode}', playSpeed: 0.05 }})")
        pg.evaluate("window.__sv.setState({ playing: false })")
        pg.keyboard.press("p")
        ts = pg.evaluate("window.__frames(3000)")
        pg.keyboard.press("p")
        r[f"play_{mode}_fps"] = frame_stats(ts)["fps"]
    # the timeline: dragging its handle across the recording, in draw mode (the series redraw)
    pg.evaluate("window.__sv.setState({ playMode: 'draw', playing: false })")
    tb = pg.locator(".tl-track").bounding_box()
    y = tb["y"] + tb["height"] / 2
    pg.mouse.move(tb["x"] + 4, y)
    pg.mouse.down()
    t0 = pg.evaluate("performance.now()")
    pg.evaluate("window.__rec()")
    steps = 150
    for i in range(steps):
        f = i / steps
        pg.mouse.move(tb["x"] + 4 + (tb["width"] - 8) * (f * 2 if f < 0.5 else 2 - f * 2), y)
    pg.mouse.up()
    pg.evaluate("window.__raf2()")
    st = frame_stats(pg.evaluate("window.__recStop()"))
    r["timeline_drag_fps"] = st["fps"]
    r["timeline_drag_long_tasks"] = len(b.long_tasks_since(pg, t0))
    pg.context.close()
    return r


def group_grid(b):
    r = {}
    b.clear_runs()
    b.api("/api/files/open", {"paths": [os.path.join(b.data, "big.csv")]})
    pg = b.page()
    b.sync_runs(pg)
    pg.wait_for_selector(".sig")
    pg.click("[aria-label='Layout 3 × 3']")
    for i in range(1, 10):
        pg.keyboard.press(str(i))
        for s in ("S0", "S1", "S2", "S3"):
            n0 = pg.evaluate("window.__perf.data.length")
            pg.locator(".sig", has_text=s).first.click()
            try:
                pg.wait_for_function(f"window.__perf.data.length > {n0}", timeout=15000)
            except Exception:
                pass
    pg.wait_for_timeout(500)
    r["grid_series"] = pg.evaluate("window.__sv.state().ws.tabs[0].plots.reduce((a, p) => a + p.signals.length, 0)")
    z = b.zoom_timed(pg, 0, steps=6)
    r["grid_zoom_p95_ms"] = round(p95(z))
    pg.keyboard.press("Space")
    st, lt, _ = b.scrub(pg, 0, ms=2000)
    r["grid_scrub_fps"], r["grid_scrub_p95_frame_ms"], r["grid_scrub_long_tasks"] = st["fps"], st["p95"], len(lt)
    pg.context.close()
    return r


def group_wide(b):
    r = {}
    b.clear_runs()
    b.api("/api/files/open", {"paths": [os.path.join(b.data, "wide5k.csv")]})   # warm the cache
    pg = b.page()
    t0 = pg.evaluate("performance.now()")
    b.sync_runs(pg)
    pg.wait_for_selector(".grp-head")                              # 5000 signals: grouped by prefix
    r["wide_panel_ms"] = round(pg.evaluate("window.__raf2()") - t0)
    box = pg.locator(".side .filter input")
    box.click()
    for ch in "s0123":
        pg.keyboard.type(ch)
    t0 = pg.evaluate("performance.now()")
    pg.wait_for_function("document.querySelectorAll('.sig').length > 0 && [...document.querySelectorAll('.sig')].every(e => e.textContent.includes('s0123'))", timeout=10000)
    r["wide_search_ms"] = round(pg.evaluate("window.__raf2()") - t0)
    pg.fill(".side .filter input", ".s")                           # matches all 5000: a long list to scroll
    pg.wait_for_selector(".sig")
    pg.wait_for_timeout(500)
    tree = pg.locator(".tree").bounding_box()
    pg.mouse.move(tree["x"] + 50, tree["y"] + 100)
    pg.evaluate("window.__scrollFrames = window.__frames(2000)")
    for _ in range(100):
        pg.mouse.wheel(0, 120)
    r["wide_scroll_fps"] = frame_stats(pg.evaluate("window.__scrollFrames"))["fps"]
    pg.fill(".side .filter input", "")

    # 200 templates, each asking for a few of the wide file's signals
    for i in range(200):
        names = [f"g{(i + k) % 100}.s{((i * 7 + k * 13) % 5000):04d}" for k in range(4)]
        tpl = {"version": 2, "name": f"Bench template {i:03d}", "slots": [{"id": "main", "name": "wide5k.csv", "file": "wide5k.csv"}],
               "tabs": [{"name": "T", "rows": 2, "cols": 1, "plots": [{"title": "P", "signals": [{"name": n, "slot": "main"} for n in names]}] * 2}]}
        b.api("/api/templates", {"template": tpl, "replace": False})
    pg.reload()
    pg.wait_for_selector(".app")
    b.sync_runs(pg)
    pg.wait_for_selector(".tpl-strip")
    pg.wait_for_timeout(800)
    # timed inside the page, from the menu click to the list drawn (Playwright's own round trips
    # and actionability checks are not the app's time; the library's code loads on first open)
    pg.click(".topbar [aria-label='Templates']")
    pg.wait_for_selector(".menu.ctx button")
    r["tpl_lib_open_ms"] = round(pg.evaluate("""(async () => {
        const t0 = performance.now();
        document.querySelector('.menu.ctx button').click();
        while (!document.querySelector('.tpl-lib .tpl-item')) await new Promise((r) => setTimeout(r, 5));
        return (await window.__raf2()) - t0; })()"""))
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(500)
    # a file opened while 200 templates and 5000 signals are there: the panel (and the strip's fit) updates
    b.api("/api/files/open", {"paths": [os.path.join(b.data, "wide5k.csv")]})
    t0 = pg.evaluate("performance.now()")
    pg.evaluate("fetch('/api/runs').then(r => r.json()).then(runs => window.__sv.setState({ runs }))")
    pg.wait_for_function("window.__sv.state().runs.length >= 2")
    r["tpl_runs_change_ms"] = round(pg.evaluate("window.__raf2()") - t0)
    lt = b.long_tasks_since(pg, t0)
    r["tpl_runs_change_longest_task_ms"] = round(max(lt)) if lt else 0
    pg.context.close()
    for t in b.api("/api/templates")["templates"]:
        if t["name"].startswith("Bench template"):
            b.api(f"/api/templates/{t['id']}", method="DELETE")
    return r


CYCLE_JS = """async (path) => {
  const wait = async (f, ms = 15000) => { const t0 = performance.now(); while (!f()) { if (performance.now() - t0 > ms) throw new Error('timeout'); await new Promise(r => setTimeout(r, 20)); } };
  const post = (u, b) => fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json());
  const sig = (n) => [...document.querySelectorAll('.sig')].find(e => e.textContent.trim().startsWith(n));
  await post('/api/files/open', { paths: [path] });
  window.__sv.setState({ runs: await fetch('/api/runs').then(r => r.json()) });
  await wait(() => sig('A')); sig('A').click();
  await wait(() => document.querySelector('.plot .u-over'));
  document.querySelector("[aria-label='New tab']").click();
  await wait(() => document.querySelectorAll('.tab').length === 2 && sig('B')); sig('B').click();
  await new Promise(r => setTimeout(r, 200));
  [...document.querySelectorAll('.tab .x')].at(-1).click();
  for (const r of await fetch('/api/runs').then(r => r.json())) if (r.format !== 'derived') await fetch('/api/runs/' + r.id, { method: 'DELETE' });
  window.__sv.setState({ runs: [] });
  await new Promise(r => setTimeout(r, 150));
}"""


def group_memory(b):
    """Open a file, plot, add and close a tab, close the file - many times. Done from inside the page:
    elements Playwright touches stay referenced by its handles, which looked like a ~100 KB/cycle
    leak that is not the app's. The undo history (up to 100 workspaces, by design) is cleared before
    each reading. Reported: growth per cycle between cycles 10 and 30 (after warm-up)."""
    r = {}
    small = os.path.join(b.data, "small.csv")
    if not os.path.exists(small):
        with open(small, "w") as f:
            f.write("Time,A,B\n" + "".join(f"{i / 100},{i % 17},{i % 23}\n" for i in range(200000)))
    b.clear_runs()
    pg = b.page()

    def heap():
        pg.evaluate("window.__sv.setState({ past: [], future: [] })")
        return b.heap_mb(pg, gc=True)
    for _ in range(10):
        pg.evaluate(CYCLE_JS, small)
    h10 = heap()
    for _ in range(20):
        pg.evaluate(CYCLE_JS, small)
    h30 = heap()
    r["mem_heap_10_mb"], r["mem_heap_30_mb"] = round(h10, 2), round(h30, 2)
    r["mem_per_cycle_kb"] = round((h30 - h10) / 20 * 1024, 1)
    pg.context.close()
    return r


def group_map(b):
    """The offline map over Israel: first view with an empty tile cache (the server draws every tile),
    the same view again (cached), and dragging the map."""
    import glob
    import shutil
    r = {}
    track = os.path.join(b.data, "flight_tlv_jlm.csv")
    if not os.path.exists(track):
        import numpy as np
        t = np.arange(0, 600, 0.5)
        f = t / t[-1]
        np.savetxt(track, np.column_stack([t, 32.08 - 0.3 * f, 34.78 + 0.43 * f]), delimiter=",", header="Time,Lat,Lon", comments="", fmt="%.6f")
    for d in glob.glob(os.path.join(b.home, ".signalviewer", "tiles", "offline_topo*")):
        shutil.rmtree(d, ignore_errors=True)

    def view(pg):
        """ms from the map being shown until every offline tile it asked for has arrived and is drawn."""
        pending, done = set(), set()
        pg.on("request", lambda q: pending.add(q.url) if "/api/tiles/offline_topo" in q.url else None)
        pg.on("requestfinished", lambda q: done.add(q.url) if "/api/tiles/offline_topo" in q.url else None)
        t0 = time.time()
        pg.evaluate("window.__sv.setState({ geoBase: 'offline' })")
        pg.locator(".plot .mode-seg button", has_text="Map").click()
        pg.wait_for_selector(".plot .geo canvas")
        quiet = 0
        while quiet < 4 and time.time() - t0 < 60:
            pg.wait_for_timeout(200)            # (time.sleep would block Playwright's event delivery)
            quiet = quiet + 1 if pending and pending <= done else 0
        return round((time.time() - t0 - 0.6) * 1000), len(pending)

    b.clear_runs()
    b.api("/api/files/open", {"paths": [track]})
    for k, label in (("map_first_view_ms", "first"), ("map_cached_view_ms", "cached")):
        pg = b.page()
        b.sync_runs(pg)
        pg.wait_for_selector(".sig")
        pg.locator(".sig", has_text="Lat").first.click()
        pg.locator(".sig", has_text="Lon").first.click()
        ms, n = view(pg)
        r[k] = ms
        r[f"map_{label}_tiles"] = n
        if label == "cached":
            box = pg.locator(".plot .geo canvas").bounding_box()
            cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            pg.mouse.move(cx, cy)
            pg.mouse.down()
            pg.evaluate("window.__rec()")
            for i in range(60):
                pg.mouse.move(cx + 200 * math.sin(i / 60 * math.pi * 2), cy + 120 * math.sin(i / 30 * math.pi))
            pg.mouse.up()
            pg.evaluate("window.__raf2()")
            r["map_pan_fps"] = frame_stats(pg.evaluate("window.__recStop()"))["fps"]
            # an object on the track, played back: the map redraws with the icon every frame
            rid = pg.evaluate("window.__sv.state().runs[0].id")
            pg.evaluate(f"""window.__sv.setState({{ ws: (() => {{ const ws = structuredClone(window.__sv.state().ws);
                ws.tabs[0].plots[0].objects = [{{ id: 'b1', name: 'Bench', kind: 'aircraft', color: '#e5534b',
                  lat: '{rid}/Lat', lon: '{rid}/Lon', trail: true }}]; return ws; }})() }})""")
            pg.wait_for_timeout(1500)
            pg.evaluate("window.__sv.setState({ playSpeed: 10, playMode: 'draw' })")
            pg.keyboard.press("Home")
            pg.keyboard.press("p")
            ts = pg.evaluate("window.__frames(3000)")
            pg.keyboard.press("p")
            r["map_object_play_fps"] = frame_stats(ts)["fps"]
        pg.context.close()
    return r


def group_globe(b):
    """The 3D view with the flight track as an object: time until it is drawn (the CesiumJS code is
    loaded on first use), and playback frames per second."""
    r = {}
    track = os.path.join(b.data, "flight_tlv_jlm.csv")
    b.browser.close()
    b.browser = b.pw.chromium.launch(args=["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    b.clear_runs()
    b.api("/api/files/open", {"paths": [track]})
    pg = b.page()
    b.sync_runs(pg)
    pg.wait_for_selector(".sig")
    rid = pg.evaluate("window.__sv.state().runs[0].id")
    t0 = pg.evaluate("performance.now()")
    pg.evaluate(f"""window.__sv.setState({{ geoBase: 'offline', ws: (() => {{ const ws = structuredClone(window.__sv.state().ws); const p = ws.tabs[0].plots[0];
        p.mode = '3d'; p.objects = [{{ id: 'g', name: 'Bench', kind: 'aircraft', color: '#e5534b', lat: '{rid}/Lat', lon: '{rid}/Lon' }}]; return ws; }})() }})""")
    pg.wait_for_selector(".globe3d-readout", timeout=120000)
    r["globe_first_view_ms"] = round(pg.evaluate("window.__raf2()") - t0)
    pg.wait_for_timeout(8000)                                    # first tiles in
    pg.evaluate("window.__sv.setState({ playSpeed: 10, playMode: 'draw' })")
    pg.keyboard.press("Home")
    pg.keyboard.press("p")
    ts = pg.evaluate("window.__frames(4000)")
    pg.keyboard.press("p")
    r["globe_play_fps"] = frame_stats(ts)["fps"]
    pg.context.close()
    return r


GROUPS = {"core": group_core, "grid": group_grid, "wide": group_wide, "memory": group_memory, "map": group_map, "globe": group_globe}


# ------------------------------------------------------------------ data + report
def make_data(d):
    import numpy as np
    import pyarrow as pa
    import pyarrow.csv as pacsv
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(os.path.join(d, "big.csv")):
        n = 5_000_003
        t = np.arange(n) / 1000.0
        rng = np.random.default_rng(0)
        cols = {"Time": t, **{f"S{i}": np.sin(t * (i + 1) * 0.37) + 0.05 * rng.standard_normal(n) for i in range(6)}}
        cols["Gear"] = np.floor(t / 600)
        pacsv.write_csv(pa.table(cols), os.path.join(d, "big.csv"))
    if not os.path.exists(os.path.join(d, "wide5k.csv")):
        n, k = 5000, 5000
        t = np.arange(n) * 0.01
        rng = np.random.default_rng(1)
        cols = {"Time": t, **{f"g{i // 50}.s{i:04d}": np.sin(t * (i % 13 + 1)) + 0.01 * rng.standard_normal(n) for i in range(k)}}
        pacsv.write_csv(pa.table(cols), os.path.join(d, "wide5k.csv"))


def report(results, out):
    env = results.get("_env", {})
    lines = ["# Browser benchmark", "",
             f"{env.get('cpus', '?')} CPU · {env.get('ram_gb', '?')} GB RAM · headless Chromium (no GPU) · {env.get('python', '')}", "",
             "Measured in the real UI. Without a GPU, frame rates are a conservative floor.", "",
             "| Measurement | Budget | Result | |", "|---|---|---|---|"]
    for key, label, budget, kind, unit in BUDGETS:
        v = results.get(key)
        if v is None:
            lines.append(f"| {label} | {'≥' if kind == 'min' else '≤'} {budget} {unit} | – | not measured |")
            continue
        ok = v >= budget if kind == "min" else v <= budget
        lines.append(f"| {label} | {'≥' if kind == 'min' else '≤'} {budget} {unit} | {v} {unit} | {'pass' if ok else 'MISS'} |")
    extra = {k: v for k, v in results.items() if not k.startswith("_") and k not in {b[0] for b in BUDGETS}}
    if extra:
        lines += ["", "Details:", ""] + [f"- `{k}`: {v}" for k, v in sorted(extra.items())]
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--results", required=True)
    ap.add_argument("--group", choices=list(GROUPS))
    ap.add_argument("--report")
    ap.add_argument("--make-data", action="store_true")
    ap.add_argument("--home", default=None, help="HOME for the server (kept between groups: warm caches)")
    a = ap.parse_args()
    results = json.load(open(a.results)) if os.path.exists(a.results) else {}
    if a.make_data:
        make_data(a.data)
    if a.group:
        home = a.home or os.path.join(os.path.dirname(os.path.abspath(a.results)), "bench_home")
        os.makedirs(home, exist_ok=True)
        b = Bench(a.data, home)
        try:
            results.update(GROUPS[a.group](b))
        finally:
            b.close()
        try:
            ram = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30, 1)
        except (ValueError, OSError, AttributeError):
            ram = "?"
        results["_env"] = {"cpus": os.cpu_count(), "ram_gb": ram, "python": f"Python {platform.python_version()}"}
        with open(a.results, "w") as f:
            json.dump(results, f, indent=1)
        print(json.dumps({k: v for k, v in results.items() if not k.startswith("_")}, indent=1))
    if a.report:
        report(results, a.report)


if __name__ == "__main__":
    main()
