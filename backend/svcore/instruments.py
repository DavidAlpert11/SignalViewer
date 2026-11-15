"""F4: live instruments - the values in force at one time (the newest while live), for any source.

An instrument shows the last value received, never an interpolation: between two samples the reading
is the older one, and how old it is (`age`) says whether the source is still sending. The attitude
comes from the object the map would draw (its roll / pitch / yaw signals or a quaternion), in degrees
by the app's one angle-unit rule; the ground speed from its positions over about the last second."""
from typing import Dict, Optional, Tuple

import numpy as np

LOOK_BACK = 200_000       # samples searched back for a real value (a multi-rate CSV holds NaN between its rows)


def last_sample(time: np.ndarray, data: np.ndarray, target: float) -> Optional[Tuple[float, float]]:
    """(value, time) of the last real (finite) sample at or before target; None before the first."""
    n = len(time)
    if n == 0:
        return None
    i = int(np.searchsorted(time, float(target), side="right")) - 1
    if i < 0:
        return None
    lo = max(0, i - LOOK_BACK)
    ok = np.flatnonzero(np.isfinite(np.asarray(data[lo:i + 1], dtype=np.float64)))
    if not len(ok):
        return None
    j = lo + int(ok[-1])
    return float(data[j]), float(time[j])


def typical_step(time: np.ndarray, target: float, n: int = 50) -> Optional[float]:
    """The median interval of the last n samples at or before target - what "late" means for this signal
    (a 0.1 Hz battery reading is not stale after 3 s; a 50 Hz attitude is)."""
    i = int(np.searchsorted(time, float(target), side="right"))
    d = np.diff(np.asarray(time[max(0, i - n):i], dtype=np.float64))
    d = d[np.isfinite(d) & (d > 0)]
    return float(np.median(d)) if len(d) else None


def quat_to_euler(w: float, x: float, y: float, z: float) -> Optional[Dict[str, float]]:
    """Hamilton, w first, body to NED (as PX4 logs it) -> roll / pitch / yaw in degrees (as the 3D view)."""
    n = float(np.sqrt(w * w + x * x + y * y + z * z))
    if not np.isfinite(n) or n == 0:
        return None
    w, x, y, z = w / n, x / n, y / n, z / n
    return {"roll": float(np.degrees(np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)))),
            "pitch": float(np.degrees(np.arcsin(np.clip(2 * (w * y - z * x), -1, 1)))),
            "yaw": float(np.degrees(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))))}


def ground_speed(t: np.ndarray, lat: np.ndarray, lon: np.ndarray, target: float, span: float = 1.0) -> Optional[float]:
    """m/s over the positions of the last `span` seconds before target (at least two samples apart);
    None when there are not two positions. Great-circle distance on a sphere (R = 6371 km)."""
    i = int(np.searchsorted(t, float(target), side="right")) - 1
    if i < 1:
        return None
    lo = max(0, i - LOOK_BACK)
    seg = slice(lo, i + 1)
    ts, la, lo_ = (np.asarray(a[seg], dtype=np.float64) for a in (t, lat, lon))
    ok = np.flatnonzero(np.isfinite(la) & np.isfinite(lo_) & (np.abs(la) <= 90) & (np.abs(lo_) <= 180))
    if len(ok) < 2:
        return None
    b = int(ok[-1])
    a_cands = ok[ts[ok] <= ts[b] - span]
    a = int(a_cands[-1]) if len(a_cands) else int(ok[0])
    dt = ts[b] - ts[a]
    if a == b or not dt > 0:
        return None
    p1, p2 = np.radians(la[a]), np.radians(la[b])
    dp, dl = p2 - p1, np.radians(lo_[b] - lo_[a])
    h = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return float(2 * 6_371_000.0 * np.arcsin(min(1.0, float(np.sqrt(h)))) / dt)
