"""P3: the time plot's data path - each zoom / pan step aborts the plot's older requests instead of
waiting for them, the points arrive as binary arrays (no base64), and a value far from zero (a Unix
time) keeps its precision (float32 alone rounds 1.7e9 to steps of 128)."""
import os
import time

import numpy as np
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401

RANGE = "Object.values(s.ranges).find(r => r)"


def test_a_zoom_burst_aborts_the_older_requests(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")
    seen, aborted = [], []
    pg.on("request", lambda r: seen.append(r) if r.url.endswith("/api/data") else None)
    pg.on("requestfailed", lambda r: aborted.append(r) if r.url.endswith("/api/data") else None)

    def slow(route):                                            # a slow server: every answer takes 0.6 s
        time.sleep(0.6)
        route.continue_()
    pg.route("**/api/data", slow)
    b = pg.locator(".plot .u-over").first.bounding_box()
    pg.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
    for _ in range(4):                                          # each step after the 60 ms debounce
        pg.mouse.wheel(0, -100)
        pg.wait_for_timeout(150)
    pg.wait_for_timeout(1500)
    pg.unroute("**/api/data")
    assert len(seen) >= 3 and len(aborted) >= 2, (len(seen), len(aborted))
    assert all(r.post_data_json.get("format") == "bin" for r in seen)
    lo, hi = S(pg, RANGE)
    assert 0 < hi - lo < 30 * 0.8 ** 3                          # four steps in: the last window is kept
    assert not pg.locator(".toast.error").count()               # an aborted request is not an error


def test_a_unix_time_value_keeps_its_precision(pg):
    p = os.path.join(pg.env["data"], "epoch.csv")
    t = np.arange(0, 10, 0.01)
    with open(p, "w") as f:
        f.write("time,Epoch\n" + "".join(f"{x:.2f},{1.7e9 + 3 * np.sin(x):.6f}\n" for x in t))
    open_files(pg, "epoch.csv")
    sig(pg, "Epoch").click()
    pg.wait_for_selector(".plot .chip")
    ys = pg.evaluate("""async () => {
        const id = window.__sv.state().runs.find(r => r.name.startsWith('epoch')).signals.find(s => s.name === 'Epoch').id;
        const r = await fetch('/api/data', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ signals: [id], points: 4000, format: 'bin' }) });
        const buf = await r.arrayBuffer();
        const n = new DataView(buf).getUint32(0, true);
        const h = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, n))).series[0];
        const rel = new Float32Array(buf, 4 + n + h.yAt, h.n);
        return Array.from(rel, (v) => h.yRef + v);
    }""")
    want = 1.7e9 + 3 * np.sin(t)
    assert len(ys) == len(t) and np.max(np.abs(np.array(ys) - want)) < 1e-3
