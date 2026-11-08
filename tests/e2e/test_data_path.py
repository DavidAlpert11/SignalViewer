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
    # counted in the page itself: each /api/data fetch, and those rejected as aborted (the browser's own verdict)
    pg.evaluate("""() => {
        window.__data = { sent: 0, aborted: 0, bin: 0 };
        const real = window.fetch;
        window.fetch = (url, init) => {
            if (String(url).endsWith('/api/data')) {
                window.__data.sent++;
                if (JSON.parse(init.body).format === 'bin') window.__data.bin++;
                return real(url, init).catch((e) => { if (e.name === 'AbortError') window.__data.aborted++; throw e; });
            }
            return real(url, init);
        };
    }""")

    def slow(route):                                            # a slow server: every answer takes 0.6 s
        time.sleep(0.6)
        route.continue_()
    pg.route("**/api/data", slow)
    # the wheel steps come from the page itself, 150 ms apart (each after the 60 ms debounce): a route
    # handler holds the test's thread while it waits, so steps sent from here would wait for it too
    pg.evaluate("""() => {
        const el = document.querySelector('.plot .u-over'), b = el.getBoundingClientRect();
        const at = { clientX: b.left + b.width / 2, clientY: b.top + b.height / 2, deltaY: -100, bubbles: true, cancelable: true };
        for (let k = 0; k < 4; k++) setTimeout(() => el.dispatchEvent(new WheelEvent('wheel', at)), 150 * k);
    }""")
    pg.wait_for_timeout(4000)
    pg.unroute("**/api/data")
    d = pg.evaluate("window.__data")
    assert d["sent"] >= 3 and d["aborted"] >= 2 and d["bin"] == d["sent"], d
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
