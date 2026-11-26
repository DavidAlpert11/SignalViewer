"""Measure the map / 3D view over repeated opening and closing (2026-11-16: Out of Memory on the owner's PC).

Opens the examples that have a map (flight, ardupilot, twoFlights, simVsFlight) one after another, switches the
map's cameras and the tabs, closes the files and opens the next - CYCLES times - and after each opening records:

    heap      the page's JS heap after a forced garbage collection (MB, CDP Performance.getMetrics)
    gl        WebGL contexts alive in the page (made and not lost; counted after the GC)
    widgets   Cesium widgets alive (made and not destroyed)
    post      listeners on the 3D view's postRender event (a listener added per rebuild and never removed grows)
    terrain   terrain providers made in the page so far
    browser   the browser's memory, every process (MB; psutil, else /proc; '-' where neither works)
    server    the backend's memory (MB, same way)
    draw      seconds from the click on the example card to a drawn map (Cesium's tilesLoaded)

    python tools/measure_maps.py                       # this checkout, 20 cycles, light mode (software WebGL)
    python tools/measure_maps.py --full                # report a hardware renderer: the full mode (sky, shadows, MSAA 4)
    python tools/measure_maps.py --gpu                 # a real graphics card (Windows): the browser's own GPU, no flags
    python tools/measure_maps.py --root ../sv-1.26.0   # another checkout (a git worktree of an older tag)
    python tools/measure_maps.py --cycles 5 --csv out.csv

On Windows set SV_CHROMIUM to Chrome / Edge (e.g. "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe") or
run `python -m playwright install chromium` once. The console of the page (errors, Cesium's render error) is
printed at the end.
"""
import argparse
import csv
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = ["flight", "ardupilot", "twoFlights", "simVsFlight"]
# the cards' English titles (before 1.28 a card had no data-example)
TITLES = {"flight": "a drone flight", "ardupilot": "an ArduPilot flight log", "twoFlights": "the same mission flown twice",
          "simVsFlight": "a simulation against its flight"}
SOFT_GL = ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]

# reported as a graphics card: the app picks its full 3D mode (as tools/make_training_video.py)
HARDWARE_GL = """(() => { const f = (P) => { const g = P.getParameter; P.getParameter = function (p) {
  if (p === 0x9246) return 'ANGLE (Hardware renderer for the measurement)'; return g.call(this, p); }; };
  f(WebGLRenderingContext.prototype); if (window.WebGL2RenderingContext) f(WebGL2RenderingContext.prototype); })();"""

# counters in the page: WebGL contexts (weak refs - a context the page let go is not counted after a GC),
# Cesium widgets (window.__svGlobe is set for each new one), terrain providers made
PROBE = """(() => {
  const ctxs = []; let made = 0;
  const orig = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (kind, ...a) {
    const c = orig.call(this, kind, ...a);
    if (c && /webgl/.test(String(kind)) && !c.__svCounted) { c.__svCounted = true; made++; ctxs.push(new WeakRef(c)); }
    return c;
  };
  const widgets = []; let g = undefined;
  Object.defineProperty(window, '__svGlobe', { configurable: true, get: () => g,
    set: (v) => { g = v; if (v && v.widget) { widgets.push(new WeakRef(v.widget)); window.__svCesium = v.Cesium; } } });
  window.__svProbe = () => {
    let gl = 0, glHeld = 0, alive = 0, post = 0;
    for (const r of ctxs) { const c = r.deref(); if (c) { glHeld++; if (!c.isContextLost()) gl++; } }
    for (const r of widgets) { const w = r.deref(); if (w && !w.isDestroyed()) { alive++; post += w.scene.postRender.numberOfListeners; } }
    return { gl, glHeld, glMade: made, widgets: alive, widgetsMade: widgets.length, post,
             terrain: window.__svTerrainMade || 0 };
  };
})();"""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def rss_mb(pids) -> float | None:
    """Resident memory of these processes together (MB); None where it cannot be read."""
    total = 0
    try:
        import psutil
        for p in pids:
            try:
                total += psutil.Process(p).memory_info().rss
            except psutil.Error:
                pass
        return total / 2**20
    except ImportError:
        pass
    if os.path.isdir("/proc"):
        for p in pids:
            try:
                with open(f"/proc/{p}/statm") as f:
                    total += int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
            except OSError:
                pass
        return total / 2**20
    return None


def children(pid) -> list:
    """Every process under pid (the browser's renderer, GPU and utility processes)."""
    try:
        import psutil
        return [c.pid for c in psutil.Process(pid).children(recursive=True)]
    except ImportError:
        pass
    if not os.path.isdir("/proc"):
        return []
    kids, parent = [], {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open(f"/proc/{d}/stat") as f:
                    parent[int(d)] = int(f.read().rsplit(")", 1)[1].split()[1])
            except (OSError, IndexError, ValueError):
                pass
    todo = [pid]
    while todo:
        p = todo.pop()
        for c, pp in parent.items():
            if pp == p:
                kids.append(c)
                todo.append(c)
    return kids


def browser_root(me):
    """The browser's main process (its first process named chrome / msedge / headless_shell under this one)."""
    names = {}
    try:
        import psutil
        names = {c.pid: c.name() for c in psutil.Process(me).children(recursive=True)}
    except ImportError:
        for c in children(me):
            try:
                with open(f"/proc/{c}/comm") as f:
                    names[c] = f.read().strip()
            except OSError:
                pass
    hit = [p for p, n in names.items() if re.search(r"chrom|msedge|headless", n, re.I)]
    return min(hit) if hit else None


class Server:
    """The app of a checkout on a free port, with an empty home (no autosave, no recent files)."""

    def __init__(self, root):
        self.home = tempfile.mkdtemp(prefix="sv-measure-home-")
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        env = {**os.environ, "HOME": self.home, "USERPROFILE": self.home}
        self.proc = subprocess.Popen([sys.executable, os.path.join(root, "run.py"), "--port", str(self.port), "--no-open"],
                                     cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(600):
            try:
                urllib.request.urlopen(self.url, timeout=1)
                return
            except Exception:
                if self.proc.poll() is not None:
                    raise RuntimeError(f"the app in {root} stopped while starting (exit {self.proc.returncode})")
                time.sleep(0.5)
        raise RuntimeError("the app did not start in 5 minutes")

    def rss(self):
        return rss_mb([self.proc.pid, *children(self.proc.pid)])

    def close_runs(self):
        import json
        for r in json.loads(urllib.request.urlopen(self.url + "/api/runs").read()):
            if r.get("format") != "derived":
                urllib.request.urlopen(urllib.request.Request(f"{self.url}/api/runs/{r['id']}", method="DELETE"))

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        shutil.rmtree(self.home, ignore_errors=True)


def map_ready(pg, timeout_s):
    """Seconds until a map is drawn (the 3D view's tiles loaded, or the flat map's canvas), None on time-out."""
    t0 = time.time()
    try:
        pg.wait_for_function("""() => { const g = window.__svGlobe;
          if (g && g.widget && !g.widget.isDestroyed() && document.querySelector('.globe3d-host canvas'))
            return g.widget.scene.globe.tilesLoaded;
          return !!document.querySelector('.geo-canvas, .plot canvas.geo') && window.__sv.state().busy === 0; }""",
                             timeout=timeout_s * 1000, polling=100)
        return time.time() - t0
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ROOT, help="the checkout to run (default: this one)")
    ap.add_argument("--url", help="an app already running (its server's memory is not measured)")
    ap.add_argument("--cycles", type=int, default=20)
    ap.add_argument("--examples", default=",".join(EXAMPLES))
    ap.add_argument("--full", action="store_true", help="report a hardware renderer (the 3D view's full mode) on software WebGL")
    ap.add_argument("--gpu", action="store_true", help="use the machine's graphics card (no software-WebGL flags)")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--timeout", type=float, default=120, help="seconds to wait for a drawn map")
    ap.add_argument("--csv", help="write the rows here too")
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright

    srv = None if a.url else Server(os.path.abspath(a.root))
    url = a.url or srv.url
    rows, console = [], []
    try:
        with sync_playwright() as p:
            exe = os.environ.get("SV_CHROMIUM")
            args = ["--no-sandbox", "--enable-precise-memory-info"] if a.gpu else SOFT_GL + ["--enable-precise-memory-info"]
            b = p.chromium.launch(headless=not a.headed, args=args, **({"executable_path": exe} if exe else {}))
            ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
            ctx.add_init_script(PROBE)
            if a.full:
                ctx.add_init_script(HARDWARE_GL)
            pg = ctx.new_page()
            pg.on("console", lambda m: console.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
            pg.on("pageerror", lambda e: console.append(f"pageerror: {e}"))
            pg.on("crash", lambda: console.append("PAGE CRASHED"))
            pg.on("response", lambda r: console.append(f"HTTP {r.status}: {r.url.split('?')[0]}") if r.status >= 400 else None)
            terrain_req = [0]
            pg.on("request", lambda r: terrain_req.__setitem__(0, terrain_req[0] + 1) if "/api/terrain/" in r.url and "version" not in r.url else None)
            cdp = ctx.new_cdp_session(pg)
            cdp.send("Performance.enable")
            pg.goto(url)
            pg.wait_for_selector(".ex-card", timeout=60000)
            browser_pid = browser_root(os.getpid())
            exs = a.examples.split(",")
            print(f"{'cycle':>5} {'example':<12} {'draw s':>7} {'heap MB':>8} {'gl':>3} {'widg':>4} {'post':>4} "
                  f"{'terr req':>8} {'browser MB':>10} {'server MB':>9}")
            for cyc in range(1, a.cycles + 1):
                for ex in exs:
                    t0 = time.time()
                    card = pg.locator(f".ex-card[data-example='{ex}']")
                    if card.count():
                        card.first.click()
                    else:                                    # not one of the welcome's six: Help -> Examples
                        pg.locator(".topbar .menubar-btn", has_text="Help").click()
                        pg.locator(".menu.ctx button", has_text="Examples").click()
                        pg.locator(".menu.ctx.sub button", has_text=TITLES.get(ex, ex)).first.click()
                    pg.wait_for_function("window.__sv.state().runs.length > 0", timeout=120000)
                    draw = map_ready(pg, a.timeout)
                    draw = None if draw is None else time.time() - t0
                    # use it: every camera, then every tab and back
                    for cam in pg.locator(".map-bar .g3-seg button[role=radio]").all():
                        try:
                            cam.click(timeout=3000)
                            pg.wait_for_timeout(400)
                        except Exception:
                            pass
                    tabs = pg.evaluate("window.__sv.state().ws.tabs.map((t) => t.id)")
                    for tid in tabs + tabs[:1]:
                        pg.evaluate("(id) => window.__sv.setState((s) => ({ ws: { ...s.ws, activeTab: id } }))", tid)
                        pg.wait_for_timeout(500)
                    pr = pg.evaluate("window.__svProbe()")
                    # close: the files closed (the server's and the page's) - the welcome screen, every plot unmounted
                    if srv:
                        srv.close_runs()
                    else:
                        pg.evaluate("""async () => { for (const r of await (await fetch('/api/runs')).json())
                          if (r.format !== 'derived') await fetch('/api/runs/' + r.id, { method: 'DELETE' }); }""")
                    pg.evaluate("window.__sv.setState({ runs: [] })")
                    pg.wait_for_selector(".ex-card", timeout=30000)
                    pg.wait_for_timeout(300)
                    cdp.send("HeapProfiler.collectGarbage")
                    heap = next(m["value"] for m in cdp.send("Performance.getMetrics")["metrics"] if m["name"] == "JSHeapUsedSize") / 2**20
                    after = pg.evaluate("window.__svProbe()")
                    bmem = rss_mb([browser_pid, *children(browser_pid)]) if browser_pid else None
                    smem = srv.rss() if srv else None
                    row = {"cycle": cyc, "example": ex, "draw_s": None if draw is None else round(draw, 2), "heap_mb": round(heap, 1),
                           "gl_open": pr["gl"], "widgets_open": pr["widgets"], "post_open": pr["post"],
                           "gl_after_close": after["gl"], "widgets_after_close": after["widgets"],
                           "terrain_requests": terrain_req[0],
                           "browser_mb": None if bmem is None else round(bmem), "server_mb": None if smem is None else round(smem)}
                    rows.append(row)
                    print(f"{cyc:>5} {ex:<12} {row['draw_s'] if row['draw_s'] is not None else 'TIMEOUT':>7} {row['heap_mb']:>8} "
                          f"{pr['gl']:>3} {pr['widgets']:>4} {pr['post']:>4} {terrain_req[0]:>8} "
                          f"{row['browser_mb'] if row['browser_mb'] is not None else '-':>10} {row['server_mb'] if row['server_mb'] is not None else '-':>9}",
                          flush=True)
                    terrain_req[0] = 0
            b.close()
    finally:
        if srv:
            srv.close()
    if a.csv and rows:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    if rows:
        first = [r for r in rows if r["cycle"] == 1]
        last = [r for r in rows if r["cycle"] == rows[-1]["cycle"]]
        draws = [r["draw_s"] for r in rows if r["draw_s"] is not None]
        print(f"\nheap after close: {first[-1]['heap_mb']} MB (cycle 1) -> {last[-1]['heap_mb']} MB (cycle {rows[-1]['cycle']}); "
              f"WebGL alive after close (last): {last[-1]['gl_after_close']}; widgets after close: {last[-1]['widgets_after_close']}; "
              f"draw median {sorted(draws)[len(draws) // 2] if draws else '-'} s, timeouts {sum(r['draw_s'] is None for r in rows)}")
    seen = set()                                     # one line per kind of message (not per WebGL context's address)
    msgs = [m for m in console if not ((k := re.sub(r"0x[0-9a-f]+", "0x", m)) in seen or seen.add(k))]
    if msgs:
        print(f"\nthe page's console ({len(console)} messages, {len(msgs)} different):")
        for m in msgs[:40]:
            print("  " + re.sub(r"\s+", " ", m)[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
