"""
F5 - the *height profile* of anything with a position: its height and the ground under it along the distance
travelled (any format: a log's GPS, a CSV's lat / lon, a simulation's LLA). The ground comes from the offline
map's elevation (app/basemap.py: the bundled grids, the user's .hgt files, Terrain Tiles kept on the disk or
fetched when the network is allowed); `step_m` says how fine it is where the track runs, and `why` says what to
do when it is coarse or missing. Heavy work stays here: the UI gets at most `n` points.
"""
import math
from typing import Dict, Optional

import numpy as np

from app import basemap

R_EARTH = 6_371_008.8
COARSE_M = 1_000.0                   # a ground grid coarser than this cannot show a hill under a track


def _dist(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Distance along the track (m), haversine between successive points."""
    la, lo = np.radians(lat), np.radians(lon)
    dla, dlo = np.diff(la), np.diff(lo)
    a = np.sin(dla / 2) ** 2 + np.cos(la[:-1]) * np.cos(la[1:]) * np.sin(dlo / 2) ** 2
    seg = 2 * R_EARTH * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    return np.concatenate([[0.0], np.cumsum(seg)])


def profile(t: np.ndarray, lat: np.ndarray, lon: np.ndarray, alt: Optional[np.ndarray] = None,
            n: int = 800, radians: bool = False, alt_ref: str = "msl") -> Dict:
    """{t, d, alt, ground, agl: lists of at most n points, length_m, step_m, source, why}. ValueError when the
    track has no position (the UI then does not offer the profile)."""
    t = np.asarray(t, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    if radians:
        lat, lon = np.degrees(lat), np.degrees(lon)
    m = min(len(t), len(lat), len(lon))
    t, lat, lon = t[:m], lat[:m], lon[:m]
    a = None if alt is None else np.asarray(alt, dtype=np.float64)[:m]
    ok = np.isfinite(t) & np.isfinite(lat) & np.isfinite(lon) & (np.abs(lat) <= 90) & (np.abs(lon) <= 180) & ~((lat == 0) & (lon == 0))
    if ok.sum() < 2:
        raise ValueError("No position to draw a profile of: the latitude / longitude have fewer than two valid points.")
    t, lat, lon = t[ok], lat[ok], lon[ok]
    a = None if a is None else a[ok]
    d = _dist(lat, lon)
    if len(d) > n:                                                   # evenly along the distance, ends kept
        idx = np.unique(np.searchsorted(d, np.linspace(0, d[-1], n)).clip(0, len(d) - 1))
        t, lat, lon, d = t[idx], lat[idx], lon[idx], d[idx]
        a = None if a is None else a[idx]
    spacing = float(d[-1] / max(1, len(d) - 1)) if len(d) > 1 else None
    g = basemap.ground_at(lat, lon, step_m=spacing) if basemap.available() else np.full(len(lat), np.nan)
    g = np.asarray(g, dtype=np.float64)
    mid = len(lat) // 2
    step = basemap.step_at(float(lat[mid]), float(lon[mid])) if basemap.available() else None
    has_ground = bool(np.isfinite(g).any())
    if a is not None and has_ground and alt_ref in ("agl", "home"):   # the object's height given over the ground / the start
        a = a + (g if alt_ref == "agl" else (g[np.isfinite(g)][0]))
    if not has_ground:
        why = "No ground heights here: the offline map's elevation data is missing."
    elif step is not None and step > COARSE_M:
        why = (f"The ground is coarse here (a point every {step / 1000:.0f} km): add .hgt elevation files (Settings > Map), "
               "or keep the area's ground heights offline (Map > Keep this area offline…).")
    else:
        why = ""

    def clean(v: Optional[np.ndarray]):
        if v is None:
            return None
        return [None if not math.isfinite(x) else round(float(x), 2) for x in v]
    agl = None if a is None or not has_ground else a - g
    return {"t": [round(float(x), 4) for x in t], "d": [round(float(x), 1) for x in d], "alt": clean(a),
            "ground": clean(g) if has_ground else None, "agl": clean(agl), "length_m": round(float(d[-1]), 1),
            "step_m": step, "why": why}


def vectors_along(t: np.ndarray, lat: np.ndarray, lon: np.ndarray, vn: np.ndarray, ve: np.ndarray,
                  alt: Optional[np.ndarray] = None, n: int = 40, radians: bool = False, alt_ref: str = "msl") -> Dict:
    """F6: any two signals (north, east components - a wind, a velocity, a force) as arrows along the track: n
    places evenly along the distance, each with its components at that moment. {t, lat, lon, alt, vn, ve, max}."""
    t = np.asarray(t, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    if radians:
        lat, lon = np.degrees(lat), np.degrees(lon)
    m = min(len(t), len(lat), len(lon), len(vn), len(ve))
    t, lat, lon = t[:m], lat[:m], lon[:m]
    vn, ve = np.asarray(vn, dtype=np.float64)[:m], np.asarray(ve, dtype=np.float64)[:m]
    a = None if alt is None else np.asarray(alt, dtype=np.float64)[:m]
    ok = (np.isfinite(t) & np.isfinite(lat) & np.isfinite(lon) & np.isfinite(vn) & np.isfinite(ve)
          & (np.abs(lat) <= 90) & (np.abs(lon) <= 180) & ~((lat == 0) & (lon == 0)))
    if ok.sum() < 2:
        raise ValueError("No arrows to draw: the position and the two components have fewer than two valid samples together.")
    t, lat, lon, vn, ve = t[ok], lat[ok], lon[ok], vn[ok], ve[ok]
    a = None if a is None else a[ok]
    d = _dist(lat, lon)
    idx = np.unique(np.searchsorted(d, np.linspace(0, d[-1], max(2, n))).clip(0, len(d) - 1))
    t, lat, lon, vn, ve = t[idx], lat[idx], lon[idx], vn[idx], ve[idx]
    a = None if a is None else a[idx]
    if a is not None and alt_ref in ("agl", "home") and basemap.available():
        g = np.asarray(basemap.ground_at(lat, lon, fetch=False), dtype=np.float64)
        if np.isfinite(g).any():
            a = a + (np.nan_to_num(g, nan=float(np.nanmedian(g))) if alt_ref == "agl" else g[np.isfinite(g)][0])
    r = lambda v, k: [round(float(x), k) for x in v]   # noqa: E731
    return {"t": r(t, 4), "lat": r(lat, 7), "lon": r(lon, 7), "alt": None if a is None else r(a, 2), "vn": r(vn, 3), "ve": r(ve, 3),
            "max": round(float(np.max(np.hypot(vn, ve))), 3)}
