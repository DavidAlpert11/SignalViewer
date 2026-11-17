"""The needle (owner, 2026-11-17: "in analysis it is critical to see every point - a skip can hide the problem"):
one short spike in a long recording must be in what every view draws - the time plot, X-Y, 3D, the map's track,
the objects' error trace, the Monte-Carlo envelope. CLAUDE.md: no point is ever left out of a picture."""
import base64
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from svcore.csv_loader import load_csv  # noqa: E402
from svcore.decimate import path_thin  # noqa: E402

client = TestClient(app)
N = 400_000                       # 1000 s at 400 Hz
AT = 123_457                      # the needle: one sample, not on any round stride
SPIKE = 50.0


def _f64(s):
    return np.frombuffer(base64.b64decode(s), dtype=np.float64)


def _f32(s):
    return np.frombuffer(base64.b64decode(s), dtype=np.float32)


@pytest.fixture(scope="module")
def rid(tmp_path_factory):
    t = np.arange(N) / 400.0
    x = np.sin(t * 0.05)
    y = np.cos(t * 0.05)
    z = 0.1 * np.sin(t)
    lat = 32.0 + 0.001 * np.sin(t * 0.01)
    lon = 34.8 + 0.001 * np.cos(t * 0.01)
    y[AT] = SPIKE                 # a glitch in one sample of y
    z[AT] = SPIKE                 # and of z
    lat[AT] = 32.5                # a jump of the position (half a degree north) for one sample
    p = tmp_path_factory.mktemp("needle") / "needle.csv"
    with open(p, "w") as f:
        f.write("time,x,y,z,lat,lon\n")
        for row in zip(t, x, y, z, lat, lon):
            f.write(",".join(f"{v:.9g}" for v in row) + "\n")
    run = store.add_pushed("needle", load_csv(str(p), [str(p)]))[0]
    yield run.id
    store.remove(run.id)


def test_path_thin_keeps_every_extreme():
    rng = np.random.default_rng(0)
    a, b = rng.normal(0, 1, 1_000_003), rng.normal(0, 1, 1_000_003)
    a[777_777], b[12_345] = 99.0, -99.0
    idx = path_thin([a, b], 20_000)
    assert len(idx) <= 22_000 and np.all(np.diff(idx) > 0)
    assert 777_777 in idx and 12_345 in idx and idx[0] == 0 and idx[-1] == len(a) - 1
    assert len(path_thin([a], 10_000_000)) == len(a)                    # fewer than asked: every sample


def test_time_plot(rid):
    r = client.post("/api/data", json={"signals": [f"{rid}/y"], "points": 2000}).json()
    s = r["series"][0]
    y = _f32(s["y"]).astype(float) + s.get("yRef", 0.0)
    assert s["decimated"] and abs(np.nanmax(y) - SPIKE) < 1e-3


def test_xy_plot(rid):
    r = client.post("/api/xy", json={"x": f"{rid}/x", "ys": [f"{rid}/y"], "relative": True}).json()
    s = r["series"][0]
    y = _f32(s["y"]).astype(float) + s.get("yRef", 0.0)
    assert s["n"] <= 20_000 and abs(np.nanmax(y) - SPIKE) < 1e-3


def test_3d_plot(rid):
    r = client.post("/api/xyz", json={"tracks": [{"x": f"{rid}/x", "y": f"{rid}/y", "z": f"{rid}/z"}]}).json()
    tr = r["tracks"][0]
    z = _f32(tr["z"]).astype(float)
    assert len(z) <= 25_000 and abs(np.nanmax(z) - SPIKE) < 1e-3


def test_map_track(rid):
    r = client.post("/api/object_track", json={"lat": f"{rid}/lat", "lon": f"{rid}/lon", "points": 5000}).json()
    lat = _f64(r["lat"])
    assert r["n"] <= 7000 and abs(np.nanmax(lat) - 32.5) < 1e-9


def test_objects_error_trace():
    from app.routes.objects import _thin
    t = np.arange(N) / 400.0
    e = np.zeros(N)
    e[AT] = SPIKE
    out = _thin(t, e, 2000)
    assert len(out["y"]) <= 2500 and max(out["y"]) == SPIKE


def test_envelope_band():
    from svcore.envelope import envelope
    t = np.arange(N) / 400.0
    runs = [(t, np.sin(t) + k * 0.01) for k in range(5)]
    spiky = np.sin(t).copy()
    spiky[AT] = SPIKE
    runs.append((t, spiky))
    r = envelope(runs, points=2000)
    assert len(r["t"]) <= 2000 and abs(np.nanmax(r["max"]) - SPIKE) < 1e-6
