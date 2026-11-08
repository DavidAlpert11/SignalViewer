"""P1: a run's time offset is applied to the question (a plot window, the cursor, a stats window) and
to the answer, not by copying the whole time vector on every request (20M samples: 160 MB and ~45 ms
each). The answers must be exactly those of a run whose time already includes the offset."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from svcore.models import Run, Signal  # noqa: E402

client = TestClient(app)
OFF = 12.375


def _run(name, t, base):
    r = Run(file_path=name, csv_display_name=name, time=t)
    r.signals["y"] = Signal(name="y", data=np.sin(base * 3) + 0.1 * base, time=t)
    r.signals["mode"] = Signal(name="mode", data=np.floor(base / 7) % 3, time=t)
    r.compute_metadata()
    return store.add_pushed(name, r)[0]


@pytest.fixture()
def pair():
    t = np.arange(60000) / 1024.0       # binary fractions: t + OFF is exact, so both runs' times agree exactly
    a = _run("p1_offset", t, t)         # the offset as a run offset
    store.set_time_offset(a.id, OFF)
    b = _run("p1_shifted", t + OFF, t)  # the same samples, already shifted
    yield a.id, b.id
    store.remove(a.id); store.remove(b.id)


def _post(path, body):
    r = client.post(path, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_signal_parts_is_signal_without_the_copy(pair):
    a, _ = pair
    t, y, off = store.signal_parts(f"{a}/y")
    t2, y2 = store.signal(f"{a}/y")
    assert off == OFF and np.allclose(t + off, t2) and y is y2
    assert t is store.get(a).run.signals["y"].time          # the stored array itself: no copy


@pytest.mark.parametrize("win", [None, (20.0, 20.5), (-100.0, 5.0)])
def test_data_window(pair, win):
    a, b = pair
    body = {"points": 2000, **({"x0": win[0], "x1": win[1]} if win else {})}
    ra = _post("/api/data", {**body, "signals": [f"{a}/y"]})["series"][0]
    rb = _post("/api/data", {**body, "signals": [f"{b}/y"]})["series"][0]
    import base64
    dec = lambda s, dt: np.frombuffer(base64.b64decode(s), dt)           # noqa: E731
    assert ra["n"] == rb["n"] and np.allclose(dec(ra["x"], np.float64), dec(rb["x"], np.float64), atol=1e-9)
    assert np.array_equal(dec(ra["y"], np.float32), dec(rb["y"], np.float32))


def test_cursor_neighbor_stats_limits(pair):
    a, b = pair
    for t in (OFF - 1, OFF + 3.21234, 40.0):
        va = _post("/api/cursor", {"signals": [f"{a}/y", f"{a}/mode"], "t": t})["values"]
        vb = _post("/api/cursor", {"signals": [f"{b}/y", f"{b}/mode"], "t": t})["values"]
        assert list(va.values()) == pytest.approx(list(vb.values()), nan_ok=True)
        for steps in (-2, 0, 1, 5):
            na = _post("/api/neighbor", {"signal": f"{a}/y", "t": t, "steps": steps})
            nb = _post("/api/neighbor", {"signal": f"{b}/y", "t": t, "steps": steps})
            assert na["index"] == nb["index"] and na["t"] == pytest.approx(nb["t"])
    sa = _post("/api/stats", {"signals": [f"{a}/y"], "t0": 20, "t1": 30})["stats"][f"{a}/y"]
    sb = _post("/api/stats", {"signals": [f"{b}/y"], "t0": 20, "t1": 30})["stats"][f"{b}/y"]
    assert sa == pytest.approx(sb)
    wa = _post("/api/stats", {"signals": [f"{a}/y"], "state": f"{a}/mode", "stateValues": [1]})["stats"][f"{a}/y"]
    wb = _post("/api/stats", {"signals": [f"{b}/y"], "state": f"{b}/mode", "stateValues": [1]})["stats"][f"{b}/y"]
    assert wa == pytest.approx(wb)
    la = _post("/api/limits", {"items": [{"id": f"{a}/y", "hi": 3}], "t0": 15, "t1": 50})["results"][f"{a}/y"]
    lb = _post("/api/limits", {"items": [{"id": f"{b}/y", "hi": 3}], "t0": 15, "t1": 50})["results"][f"{b}/y"]
    assert la == pytest.approx(lb)


def test_stats_cache_hits_with_an_offset(pair):
    """The stats cache is keyed on the time array's identity: with a copy per request it never hit."""
    from svcore import ops
    a, _ = pair
    body = {"signals": [f"{a}/y"], "t0": 20, "t1": 30}
    _post("/api/stats", body)
    calls = []
    real = ops._stats_of
    ops._stats_of = lambda *x, **k: calls.append(1) or real(*x, **k)
    try:
        _post("/api/stats", body)
    finally:
        ops._stats_of = real
    assert calls == []


def test_spectrogram_window(pair):
    a, b = pair
    body = {"x0": 20.0, "x1": 40.0, "nfft": 256, "width": 200, "height": 100}
    ra = _post("/api/spectrogram", {**body, "signal": f"{a}/y"})
    rb = _post("/api/spectrogram", {**body, "signal": f"{b}/y"})
    for k in ("t0", "t1", "sigT0", "sigT1", "nf", "nt"):
        assert ra[k] == pytest.approx(rb[k]), k
    assert ra["img"] == rb["img"]
