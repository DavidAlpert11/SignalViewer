"""The time axis of a file: which column is its time, and in what unit (owner's request, 2026-10-26).

Users change it while they work: a column other than the one found becomes the time, and a time
logged in milliseconds (or minutes...) is put in seconds - or the other way round - with a scale.
The time an app shows is  t * scale + offset  (the offset is the file's existing time offset).

Everything that is computed against time - derivatives, integrals, filters in Hz, spectra, the
time-weighted statistics - is computed against the NEW axis afterwards, so the checks here tell
the user, before the change, what the new axis looks like and what will mean something else.
"""
import re
from typing import Dict, List, Optional, Tuple

import numpy as np

from svcore.models import Run

# a time unit -> its length in seconds (the scale that puts a column in that unit into seconds)
UNIT_SECONDS: Dict[str, float] = {"ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1.0, "min": 60.0, "h": 3600.0}

# formats whose time comes from a column the user can choose, and formats whose time can be
# scaled. Flight logs and ROS recordings carry their own clock in seconds: only the offset applies.
TIME_COLUMN_FORMATS = {"csv", "mat", "parquet"}
TIME_SCALE_FORMATS = {"csv", "mat", "parquet", "hdf5"}

_UNIT_PATTERNS: List[Tuple[str, str]] = [
    (r"(^|[\W_])(ns|nsec|nanos?|nanoseconds?)$", "ns"),
    (r"(^|[\W_])(us|usec|µs|micros|microseconds?)$", "us"),
    (r"(^|[\W_])(ms|msec|millis|milliseconds?)$", "ms"),
    (r"(^|[\W_])(min|mins|minutes?)$", "min"),
    (r"(^|[\W_])(h|hr|hrs|hours?)$", "h"),
    (r"(^|[\W_])(s|sec|secs|seconds?)$", "s"),
]


def unit_from_name(name: str) -> Optional[str]:
    """The time unit a column's name says: `time_boot_ms`, `t [us]`, `Time (min)`, `stamp_ns`.
    None when the name says nothing (most files: then it is taken to be seconds)."""
    n = str(name or "").strip().lower()
    m = re.search(r"[\[(]\s*([^\])]+?)\s*[\])]\s*$", n)       # a unit in brackets wins
    if m:
        n = "_" + m.group(1).strip()
    for pat, unit in _UNIT_PATTERNS:
        if re.search(pat, n):
            return unit
    return None


def analyze(values: np.ndarray, name: str = "") -> dict:
    """What this column would look like as the time axis: how many values, whether they only go
    up, repeated values, missing values, the usual step and the long gaps, and the unit its name
    says. Read by the Time axis dialog before anything changes."""
    v = np.asarray(values, dtype=np.float64)
    finite = np.isfinite(v)
    out: dict = {"n": int(v.size), "missing": int((~finite).sum()), "unit": unit_from_name(name)}
    x = v[finite]
    if x.size == 0:
        out.update(order="empty", min=None, max=None)
        return out
    out["min"], out["max"] = float(x.min()), float(x.max())
    if x.size < 2:
        out.update(order="increasing", repeats=0, backSteps=0, step=None, gaps=0, maxGap=None)
        return out
    d = np.diff(x)
    back = int((d < 0).sum())
    repeats = int((d == 0).sum())
    if back == 0:
        order = "increasing" if repeats == 0 else "nondecreasing"
    elif back == d.size - repeats:
        order = "decreasing"
    else:
        order = "mixed"
    out.update(order=order, repeats=repeats, backSteps=back)
    pos = d[d > 0] if back == 0 else np.abs(np.diff(np.sort(x)))
    pos = pos[pos > 0]
    if pos.size:
        step = float(np.median(pos))
        big = pos > 10 * step
        out.update(step=step, gaps=int(big.sum()), maxGap=float(pos.max()))
    else:
        out.update(step=None, gaps=0, maxGap=None)
    return out


def scale_of(settings: Optional[dict], key: str) -> float:
    """A positive, finite scale from import settings (1 when absent or not usable)."""
    try:
        s = float((settings or {}).get(key) or 1.0)
    except (TypeError, ValueError):
        return 1.0
    return s if np.isfinite(s) and s > 0 else 1.0


def apply_scales(run: Run, scale: float, own_scale: float) -> None:
    """Put the file's time vectors on the chosen unit: `scale` for the main time (and every signal
    that uses it), `own_scale` for signals with a time column of their own (Speed + Speed_time,
    a group's time_boot_ms) - those are often in another unit than the main time. Scaling makes a
    new array, so a memory-mapped cache file is never written to."""
    if scale != 1.0:
        run.time = np.asarray(run.time, dtype=np.float64) * scale
    if own_scale != 1.0:
        done: Dict[int, np.ndarray] = {}        # signals of one group share one time vector
        for sg in run.signals.values():
            if sg.time is not None:
                key = id(sg.time)
                if key not in done:
                    done[key] = np.asarray(sg.time, dtype=np.float64) * own_scale
                sg.time = done[key]
    if scale != 1.0 or own_scale != 1.0:
        run.compute_metadata()


def map_times(old_time: np.ndarray, old_offset: float, new_time: np.ndarray, new_offset: float,
              same_rows: bool, times: List[float]) -> List[Optional[float]]:
    """Times on the old axis (as shown: with the offset) -> the same rows' times on the new axis.
    Only when the rows did not move (same row count, neither axis re-sorted): None otherwise."""
    if not same_rows or len(old_time) != len(new_time) or len(old_time) == 0:
        return [None] * len(times)
    ot = np.asarray(old_time, dtype=np.float64)
    nt = np.asarray(new_time, dtype=np.float64)
    out: List[Optional[float]] = []
    for t in times:
        try:
            x = float(t) - old_offset
        except (TypeError, ValueError):
            out.append(None)
            continue
        if not np.isfinite(x):
            out.append(None)
            continue
        # a time between two rows stays between the same two rows
        i = int(np.clip(np.searchsorted(ot, x), 1, len(ot) - 1)) if len(ot) > 1 else 0
        if len(ot) == 1:
            out.append(float(nt[0]) + new_offset)
            continue
        a, b = ot[i - 1], ot[i]
        f = 0.0 if b == a else (x - a) / (b - a)
        out.append(float(nt[i - 1] + f * (nt[i] - nt[i - 1])) + new_offset)
    return out
