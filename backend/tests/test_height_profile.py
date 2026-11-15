"""F5 - the height profile: the distance along any track with positions, its height and the ground under it (the
offline map's elevation), at most n points; without positions it is refused; where the ground is coarse it says
what to do."""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import basemap  # noqa: E402
from app.heightprofile import profile  # noqa: E402

needs_map = pytest.mark.skipif(not basemap.available(), reason="offline map data not built")


def test_distance_along_the_track_matches_a_reference():
    # due north along a meridian: 0.01 deg of latitude = 1111.95 m (sphere of radius 6371008.8 m)
    lat = np.linspace(31.0, 31.1, 11)
    out = profile(np.arange(11.0), lat, np.full(11, 35.0), np.full(11, 500.0))
    assert out["length_m"] == pytest.approx(0.1 * math.pi / 180 * 6_371_008.8, rel=1e-6)
    assert out["d"][0] == 0 and out["d"] == sorted(out["d"]) and len(out["t"]) == 11
    assert out["alt"] == [500.0] * 11


@needs_map
def test_the_ground_under_a_track_over_jerusalem_and_its_height_above_it():
    t = np.arange(50.0)
    lat = np.full(50, 31.77)
    lon = np.linspace(35.18, 35.24, 50)
    out = profile(t, lat, lon, np.full(50, 1500.0))
    g = [x for x in out["ground"] if x is not None]
    assert len(g) == 50 and 600 < np.median(g) < 900          # Jerusalem lies at ~750 m
    assert all(abs(a - (1500.0 - gr)) < 0.02 for a, gr in zip(out["agl"], out["ground"]))
    assert out["why"] == "" and out["step_m"] is not None and out["step_m"] <= 1000   # the fine grid of the region


@needs_map
def test_coarse_ground_says_what_to_do(monkeypatch):
    monkeypatch.setattr(basemap, "step_at", lambda la, lo: 11_000.0)
    out = profile(np.arange(3.0), np.array([10.0, 10.01, 10.02]), np.array([10.0, 10.0, 10.0]))
    assert ".hgt" in out["why"] and "Keep this area offline" in out["why"] and out["alt"] is None


def test_decimated_evenly_along_the_distance_with_the_ends():
    n = 20000
    lat = np.linspace(31.0, 31.5, n)
    out = profile(np.arange(float(n)), lat, np.full(n, 35.0), n=500)
    assert len(out["d"]) <= 500 and out["t"][0] == 0 and out["t"][-1] == n - 1
    steps = np.diff(out["d"])
    assert steps.max() < 3 * steps.mean()


def test_radians_and_bad_points():
    lat = np.radians([31.0, 31.01, np.nan, 31.02])
    lon = np.radians([35.0, 35.0, 35.0, 35.0])
    out = profile(np.arange(4.0), lat, lon, radians=True)
    assert len(out["d"]) == 3 and out["length_m"] == pytest.approx(0.02 * math.pi / 180 * 6_371_008.8, rel=1e-6)


def test_no_position_is_refused():
    with pytest.raises(ValueError, match="No position"):
        profile(np.arange(3.0), np.array([np.nan, 0, 0]), np.array([np.nan, 0, 0]))


def test_route(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    p = tmp_path / "track.csv"
    p.write_text("time,lat,lon,alt\n" + "\n".join(f"{i},{31.77},{35.18 + i * 0.001},{1500}" for i in range(60)))
    r = c.post("/api/files/open", json={"paths": [str(p)]}).json()
    rid = r["opened"][0]["id"]
    out = c.post("/api/profile", json={"lat": f"{rid}/lat", "lon": f"{rid}/lon", "alt": f"{rid}/alt"}).json()
    assert len(out["d"]) == 60 and out["alt"][0] == 1500.0
    assert c.post("/api/profile", json={"lat": f"{rid}/nope", "lon": f"{rid}/lon"}).status_code == 404


@needs_map
def test_height_over_the_ground_is_turned_into_height_above_the_sea():
    lat, lon = np.full(5, 31.77), np.linspace(35.20, 35.22, 5)
    msl = profile(np.arange(5.0), lat, lon, np.full(5, 100.0), alt_ref="agl")
    assert all(abs(a - (g + 100.0)) < 0.02 for a, g in zip(msl["alt"], msl["ground"]))
    assert all(abs(x - 100.0) < 0.02 for x in msl["agl"])
