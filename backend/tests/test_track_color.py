"""A map object's track coloured by another signal (owner, 2026-11-03): a state held until its next
sample (no blend of two flight modes), a value interpolated; NaN where the signal has no data."""
import base64

import numpy as np

from test_backend import _open, client


def _dec(s):
    return np.frombuffer(base64.b64decode(s), dtype=np.float32)


def test_track_colour_state_and_value(tmp_path):
    t = np.arange(0, 10, 0.5)
    mode = np.where(t < 4, 0.0, 5.0)
    sigs, run = _open(tmp_path, "trk.csv", ["Time", "Lat", "Lon", "Mode", "Alt"],
                      [t, 32 + t * 1e-4, 35 + t * 1e-4, mode, t * 10])
    body = {"lat": sigs["Lat"]["id"], "lon": sigs["Lon"]["id"]}
    r = client.post("/api/object_track", json={**body, "color": sigs["Mode"]["id"], "colorStep": True}).json()
    c = _dec(r["color"])
    assert set(np.unique(c)) == {0.0, 5.0} and c[0] == 0 and c[-1] == 5     # only the two modes, no 2.5
    r = client.post("/api/object_track", json={**body, "color": sigs["Alt"]["id"]}).json()
    assert np.allclose(_dec(r["color"]), t * 10)
    # no colour asked, or a signal that is gone: no colour (one colour on the map)
    assert "color" not in client.post("/api/object_track", json=body).json()
    assert "color" not in client.post("/api/object_track", json={**body, "color": "nope/x"}).json()
    client.delete(f"/api/runs/{run['id']}")
