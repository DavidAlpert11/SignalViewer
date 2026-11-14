"""F2: statistics of the visible window - equal to numpy on the window's samples, fast on big signals."""
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store
from svcore.windowstats import BLOCK, window_stats

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    yield
    for rid in list(store.order):
        store.remove(rid)


def ref(t, y, a, b):
    seg = y[(t >= a) & (t <= b)]
    seg = seg[np.isfinite(seg)]
    return (len(seg), seg.min(), seg.max(), seg.mean()) if len(seg) else (0, None, None, None)


@pytest.mark.parametrize("a,b", [(0.0, 1e9), (12.3, 12.31), (100.0, 4000.0), (3.3, 9999.0), (-5, 0.0)])
def test_equals_numpy_on_the_window(a, b):
    rng = np.random.default_rng(1)
    t = np.cumsum(rng.uniform(0.01, 0.2, 200_000))
    y = rng.normal(size=len(t)) * 3 + np.sin(t)
    y[rng.integers(0, len(y), 500)] = np.nan
    y[150_000:150_000 + 3 * BLOCK] = np.nan                                     # whole blocks of NaN
    s = window_stats(t, y, a, b)
    n, lo, hi, mean = ref(t, y, a, b)
    if n == 0:
        assert s == {}
        return
    assert s["n"] == n and s["min"] == lo and s["max"] == hi
    assert s["mean"] == pytest.approx(mean, rel=1e-9, abs=1e-12)


def test_endpoint_applies_offsets_and_skips_states(tmp_path):
    p = tmp_path / "r.csv"
    t = np.arange(0, 100, 0.01)
    np.savetxt(p, np.column_stack([t, t * 2, (t > 50).astype(int)]), delimiter=",", header="Time,A,Mode", comments="", fmt="%.6g")
    info = client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]
    ids = {s["name"]: s["id"] for s in info["signals"]}
    store.set_time_offset(info["id"], 10.0)
    off = 10.0
    r = client.post("/api/stats/window", json={"signals": [ids["A"], ids["Mode"], "gone/x"], "t0": 20 + off, "t1": 30 + off}).json()["stats"]
    a = r[ids["A"]]
    assert a["min"] == pytest.approx(40) and a["max"] == pytest.approx(60) and a["mean"] == pytest.approx(50)
    assert a["t0"] == pytest.approx(20 + off) and a["n"] == 1001
    assert ids["Mode"] not in r and "gone/x" not in r


def test_a_big_signal_answers_fast_after_the_first_time():
    n = 20_000_000
    t = np.arange(n, dtype=np.float64) * 1e-3
    y = np.sin(t).astype(np.float32)
    window_stats(t, y, 0, 1)                                                      # small: read directly
    window_stats(t, y, 10.0, n * 1e-3)                                            # the blocks once
    t0 = time.perf_counter()
    for k in range(50):
        window_stats(t, y, 100.0 + k, 15000.0 - k)
    per = (time.perf_counter() - t0) / 50
    assert per < 0.005, f"{per * 1000:.2f} ms per window"
