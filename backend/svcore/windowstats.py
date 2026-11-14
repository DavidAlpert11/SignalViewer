"""
F2 - statistics of the visible window: min, mean, max (and the samples counted) of each signal over the
time range on screen, fast enough to follow every pan and zoom (shown in the legend on demand).

A signal is summarised once in blocks (min / max / sum / finite count per BLOCK samples, cached with
the arrays); a window then costs its whole blocks plus at most two partial blocks read directly - so a
20-million-sample signal answers in well under a millisecond after the first time, and exactly (the same
numbers as numpy on the window's samples, NaN skipped).

The mean here is the mean of the samples in the window (what is on screen). The Inspector's statistics
between the cursors keep their time weighting for uneven sampling (svcore/ops.compute_signal_stats).
"""

from typing import Any, Dict, Optional, Tuple

import numpy as np

from svcore.memcache import CACHE as MEMCACHE

BLOCK = 4096


def _blocks(y: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Per block of BLOCK samples: (min, max, sum, finite count); an all-NaN block has min +inf / max -inf."""
    n = len(y)
    k = n // BLOCK
    a = np.asarray(y[: k * BLOCK], dtype=np.float64).reshape(k, BLOCK)
    f = np.isfinite(a)
    lo = np.where(f, a, np.inf).min(axis=1)
    hi = np.where(f, a, -np.inf).max(axis=1)
    s = np.where(f, a, 0.0).sum(axis=1)
    c = f.sum(axis=1).astype(np.int64)
    return lo, hi, s, c


def _summary(t: np.ndarray, y: np.ndarray):
    key = ("winblocks", id(t), id(y), len(y))
    return MEMCACHE.get_or_compute(key, "stats", lambda: _blocks(y), owners=(t, y))


def _direct(seg: np.ndarray) -> Tuple[float, float, float, int]:
    seg = np.asarray(seg, dtype=np.float64)
    f = seg[np.isfinite(seg)]
    if not len(f):
        return np.inf, -np.inf, 0.0, 0
    return float(f.min()), float(f.max()), float(f.sum()), int(len(f))


def window_stats(t: np.ndarray, y: np.ndarray, t0: Optional[float], t1: Optional[float]) -> Dict[str, Any]:
    """{n, min, max, mean, t0, t1} of the samples with t0 <= t <= t1 (sorted t); {} when none is finite."""
    n = len(y)
    i0 = 0 if t0 is None else int(np.searchsorted(t, t0, side="left"))
    i1 = n if t1 is None else int(np.searchsorted(t, t1, side="right"))
    if i1 <= i0:
        return {}
    b0, b1 = -(-i0 // BLOCK), i1 // BLOCK          # whole blocks inside [i0, i1)
    if b1 - b0 < 2:                               # a small window: read it
        lo, hi, s, c = _direct(y[i0:i1])
    else:
        blo, bhi, bs, bc = _summary(t, y)
        parts = [_direct(y[i0:b0 * BLOCK]), _direct(y[b1 * BLOCK:i1]),
                 (float(blo[b0:b1].min()), float(bhi[b0:b1].max()), float(bs[b0:b1].sum()), int(bc[b0:b1].sum()))]
        lo = min(p[0] for p in parts)
        hi = max(p[1] for p in parts)
        s = sum(p[2] for p in parts)
        c = sum(p[3] for p in parts)
    if c == 0:
        return {}
    return {"n": int(c), "min": float(lo), "max": float(hi), "mean": float(s / c),
            "t0": float(t[i0]), "t1": float(t[i1 - 1])}


# ----------------------------------------------------------------------------- D14: *at a glance* numbers
GLANCE_STATS = ("min", "max", "mean", "first", "final", "range")


def glance_value(t: np.ndarray, y: np.ndarray, stat: str) -> Optional[Dict[str, Any]]:
    """One number of a whole run for the *run at a glance* strip: {value, t} (t: where it is reached, for
    min / max / first / final; None for mean / range). NaN samples are skipped; None when no sample is
    finite. `mean` is the plain mean of the samples (not time-weighted), as the window statistics."""
    if stat not in GLANCE_STATS:
        raise ValueError(f"Unknown statistic {stat!r} - use one of {', '.join(GLANCE_STATS)}.")
    if stat in ("first", "final"):
        f = np.flatnonzero(np.isfinite(np.asarray(y, dtype=np.float64)))
        if not len(f):
            return None
        i = int(f[0] if stat == "first" else f[-1])
        return {"value": float(y[i]), "t": float(t[i])}
    s = window_stats(t, y, None, None)
    if not s:
        return None
    if stat == "mean":
        return {"value": s["mean"], "t": None}
    if stat == "range":
        return {"value": s["max"] - s["min"], "t": None}
    a = np.asarray(y, dtype=np.float64)
    i = int(np.nanargmax(a) if stat == "max" else np.nanargmin(a))
    return {"value": s[stat], "t": float(t[i])}
