"""Measure the Sweeps parallel plot on a big table, in the real app (1.29, ROADMAP M35 FT2).

Makes a table of N parameter sets (one run each, 5 parameters + 7 outputs = 12 axes), opens it in Sweeps,
goes to Results (Parameter sets: a line per set - every line drawn, no sample) and measures, from the
page's animation frames:

    open      the results step shown: seconds to the first picture / to the full picture
    filter    a filter set on an axis (half the lines kept): first picture / full picture
    brush     a drag on an axis (20 moves): the longest frame while dragging; after the release, the full picture
    hover     the pointer moved over the lines (30 moves): the longest frame
    longest   the longest frame (ms) of each step - the page does not answer the pointer during it

"first" is the first frame painted with lines of the new picture (the canvas's data-drawing turns 1);
"full" when every line is drawn (it turns 0). A checkout without the progressive drawing has no
data-drawing: then both are the end of the frame that drew everything.

    python tools/measure_sweeps_plot.py                        # 200,000 lines, DPR 1 and 2
    python tools/measure_sweeps_plot.py --rows 50000 --dpr 1
    python tools/measure_sweeps_plot.py --root ../sv-main      # another checkout (a git worktree), to compare

On Windows set SV_CHROMIUM to Chrome / Edge, or run `python -m playwright install chromium` once.
"""
import argparse
import json
import os
import sys
import tempfile
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_maps import ROOT, Server  # noqa: E402

# the page's frames: each painted frame's time and whether the plot was still drawing
FRAMES = """(() => {
  const F = window.__svFrames = { t: [], d: [], on: false };
  F.start = () => { F.t = []; F.d = []; F.on = true; const loop = (ts) => {
    const cv = document.querySelector('.pp canvas'); F.t.push(ts); F.d.push(cv ? cv.dataset.drawing ?? '' : '');
    if (F.on) requestAnimationFrame(loop); }; requestAnimationFrame(loop); };
  F.stop = () => { F.on = false; return { t: F.t, d: F.d }; };
})();"""


def table(path, n):
    rng = np.random.default_rng(3)
    r = np.arange(n)
    df = pd.DataFrame({f"p{j}": (r // 20 ** j) % 20 * 0.5 for j in range(5)})     # a grid: 20 values each
    for i in range(7):
        df[f"out_{i}"] = rng.normal(i, 1 + i * 0.1, n).round(5)
    df.to_csv(path, index=False)


def frames_after(pg, t0, settle_ms=600, timeout_s=120):
    """Frames from t0 until the plot is drawn and has stayed quiet for settle_ms."""
    end = time.time() + timeout_s
    while time.time() < end:
        f = pg.evaluate("({t: window.__svFrames.t, d: window.__svFrames.d})")
        t, d = f["t"], f["d"]
        idx = [i for i, x in enumerate(t) if x >= t0]
        if idx and t[-1] - t0 > settle_ms and d[-1] != "1":
            quiet = [t[i] - t[i - 1] for i in idx[1:] if t[i] > t[-1] - settle_ms]
            if quiet and max(quiet) < 50:
                break
        time.sleep(0.2)
    f = pg.evaluate("window.__svFrames.stop()")
    pg.evaluate("window.__svFrames.start()")
    return f["t"], f["d"]


def summary(t, d, t0):
    idx = [i for i, x in enumerate(t) if x >= t0]
    if not idx:
        return {"first": None, "full": None, "longest": None}
    gaps = [t[i] - t[i - 1] for i in idx if i > 0]
    longest = max(gaps) if gaps else 0
    if any(x in ("0", "1") for x in d):
        ones = [i for i in idx if d[i] == "1"]
        first = t[ones[0]] - t0 if ones else None
        zeros = [i for i in idx if d[i] == "0" and (not ones or i > ones[0])]
        full = t[zeros[0]] - t0 if zeros else first
        if first is None:                                # drawn within one frame
            first = full
    else:                                                # the old one-canvas drawing: the end of the longest frame
        k = max(idx[1:], key=lambda i: t[i] - t[i - 1]) if len(idx) > 1 else idx[0]
        first = full = t[k] - t0
    return {"first": round(first / 1000, 3) if first is not None else None,
            "full": round(full / 1000, 3) if full is not None else None, "longest": round(longest)}


def measure(root, rows, dpr, chromium):
    from playwright.sync_api import sync_playwright
    folder = tempfile.mkdtemp(prefix="sv-measure-sweeps-")
    table(os.path.join(folder, "big_sets.csv"), rows)
    srv = Server(root)
    out = {"rows": rows, "dpr": dpr}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(**({"executable_path": chromium} if chromium else {}))
            ctx = b.new_context(viewport={"width": 1400, "height": 900}, device_scale_factor=dpr)
            pg = ctx.new_page()
            pg.add_init_script(FRAMES)
            pg.goto(srv.url)
            pg.locator(".areas .area-btn", has_text="Sweeps").click()
            pg.locator(".sw-welcome .btn", has_text="I have results").click()
            pg.wait_for_function("document.querySelector('.crumbs input') && document.querySelector('.crumbs input').value !== ''")
            pg.fill(".crumbs input", folder); pg.press(".crumbs input", "Enter")
            pg.locator(".dialog .fs-row", has_text="big_sets.csv").click(); pg.click(".dialog-foot .btn.primary")
            pg.wait_for_selector(".sw-steps", timeout=300000)
            pg.wait_for_function("window.__svSweeps.idle()", timeout=300000)
            pg.evaluate("window.__svFrames.start()")
            t0 = pg.evaluate("performance.now()")
            pg.locator(".sw-step-btn[data-step='results']").click()
            pg.wait_for_selector(".pp canvas", timeout=300000)
            pg.wait_for_function("window.__svSweeps.idle()", timeout=300000)
            out["open"] = summary(*frames_after(pg, t0), t0)
            # a filter: half the lines kept
            t0 = pg.evaluate("performance.now()")
            pg.evaluate("window.__svSweeps.filter('out_0', {kind: 'ranges', ranges: [[0, 99]]})")
            out["filter"] = summary(*frames_after(pg, t0), t0)
            # a brush dragged on the third axis
            bx = pg.locator(".pp canvas").bounding_box()
            names = pg.locator(".pp-axis-name")
            ax = names.nth(2).bounding_box()
            x = ax["x"] + ax["width"] / 2
            t0 = pg.evaluate("performance.now()")
            pg.mouse.move(x, bx["y"] + 80); pg.mouse.down()
            for i in range(20):
                pg.mouse.move(x, bx["y"] + 80 + i * 8)
            t_up = pg.evaluate("performance.now()")
            pg.mouse.up()
            t, d = frames_after(pg, t0)
            drag = [t[i] - t[i - 1] for i, x2 in enumerate(t) if i and t0 <= x2 <= t_up]
            after = summary(t, d, t_up)
            out["brush"] = {"longestWhileDragging": round(max(drag)) if drag else None, "fullAfter": after["full"], "longest": after["longest"]}
            # hover over the lines
            t0 = pg.evaluate("performance.now()")
            for i in range(30):
                pg.mouse.move(bx["x"] + 100 + i * 20, bx["y"] + 150 + (i % 5) * 20)
            t, d = frames_after(pg, t0, settle_ms=300)
            gaps = [t[i] - t[i - 1] for i, x2 in enumerate(t) if i and x2 >= t0]
            out["hover"] = {"longest": round(max(gaps)) if gaps else None}
            b.close()
    finally:
        srv.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=int, default=200_000)
    ap.add_argument("--dpr", default="1,2", help="device pixel ratios, comma-separated")
    ap.add_argument("--root", default=ROOT, help="the checkout to run (default: this one)")
    a = ap.parse_args()
    chromium = os.environ.get("SV_CHROMIUM") or None
    for dpr in [float(x) for x in a.dpr.split(",")]:
        print(json.dumps(measure(os.path.abspath(a.root), a.rows, dpr, chromium)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
