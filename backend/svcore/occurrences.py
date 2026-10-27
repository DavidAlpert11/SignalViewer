"""The stretches of a named condition, looked at together (investigation spec, step 3).

  occurrence_stats  max / min / mean of a signal in each stretch (the occurrences table);
  windows           each stretch of a signal on a common time axis from its start, end or peak, and
                    their mean (the occurrences overlay);
  differ            for every signal of a file: how different it is inside the stretches from
                    outside them, ranked ("what differs in the occurrences").
"""
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

Iv = Sequence[Sequence[float]]          # [(start, end)] - pairs from JSON are lists
MAX_OVERLAY = 200


def _f(a) -> np.ndarray:
    return np.asarray(a, dtype=np.float64)


def occurrence_stats(t, y, intervals: Iv) -> List[dict]:
    t, y = _f(t), _f(y)
    out: List[Dict[str, Optional[float]]] = []
    for a, b in intervals:
        i0, i1 = np.searchsorted(t, a, "left"), np.searchsorted(t, b, "right")
        seg, ts = y[i0:i1], t[i0:i1]
        ok = np.isfinite(seg)
        if not ok.any():
            out.append({"max": None, "min": None, "mean": None, "tMax": None})
            continue
        s, tt = seg[ok], ts[ok]
        k = int(np.argmax(s))
        out.append({"max": float(s.max()), "min": float(s.min()), "mean": float(s.mean()), "tMax": float(tt[k])})
    return out


def windows(t, y, intervals: Iv, align: str = "start", pad: float = 0.5, n: int = 400) -> Dict[str, object]:
    """Every stretch of (t, y) on one relative time axis: 0 = its start ("start"), its end ("end")
    or its peak ("peak": the sample furthest from the stretch's median). `pad`: the share of the
    longest stretch shown before and after. Returns grid, one curve per stretch (None where it has
    no data) and their mean (where at least one has data)."""
    t, y = _f(t), _f(y)
    iv = [(float(a), float(b)) for a, b in intervals][:MAX_OVERLAY]
    if not iv or len(t) < 2:
        return {"grid": [], "curves": [], "mean": [], "cut": len(intervals) > MAX_OVERLAY}
    longest = max(max(b - a for a, b in iv), float(np.median(np.diff(t))) * 4)
    zeros = []
    for a, b in iv:
        if align == "end":
            zeros.append(b)
        elif align == "peak":
            i0, i1 = np.searchsorted(t, a, "left"), np.searchsorted(t, b, "right")
            seg = y[i0:i1]
            ok = np.isfinite(seg)
            zeros.append(float(t[i0:i1][ok][np.argmax(np.abs(seg[ok] - np.median(seg[ok])))]) if ok.any() else a)
        else:
            zeros.append(a)
    lo, hi = (-longest * (1 + pad), longest * pad) if align == "end" else \
        ((-longest * (0.5 + pad), longest * (0.5 + pad)) if align == "peak" else (-longest * pad, longest * (1 + pad)))
    grid = np.linspace(lo, hi, n)
    curves = []
    for (a, b), z in zip(iv, zeros):
        # a stretch shows its own length plus the same padding - not the next stretch's data
        w0, w1 = (a - longest * pad, b + longest * pad)
        g = grid + z
        v = np.interp(g, t, y, left=np.nan, right=np.nan)
        v[(g < w0) | (g > w1)] = np.nan
        curves.append(v)
    stack = np.vstack(curves)
    with np.errstate(all="ignore"):
        cnt = np.isfinite(stack).sum(axis=0)
        mean = np.where(cnt > 0, np.nansum(stack, axis=0) / np.maximum(cnt, 1), np.nan)
    clean = lambda a: [None if not np.isfinite(x) else float(x) for x in a]   # noqa: E731
    return {"grid": [float(x) for x in grid], "curves": [clean(c) for c in curves], "mean": clean(mean),
            "cut": len(intervals) > MAX_OVERLAY}


def inside_mask(t, intervals: Iv) -> np.ndarray:
    t = _f(t)
    m = np.zeros(len(t), dtype=bool)
    for a, b in intervals:
        m[np.searchsorted(t, a, "left"):np.searchsorted(t, b, "right")] = True
    return m


def differ_one(t, y, intervals: Iv) -> Optional[Tuple[float, float, float, float]]:
    """(effect, mean inside, mean outside, share of time inside) - effect: the difference of the means
    in units of the usual spread outside (how many times the ordinary variation it is)."""
    t, y = _f(t), _f(y)
    m = inside_mask(t, intervals)
    ok = np.isfinite(y)
    yi, yo = y[m & ok], y[~m & ok]
    if len(yi) < 2 or len(yo) < 2:
        return None
    mi, mo = float(yi.mean()), float(yo.mean())
    so = float(yo.std())
    if so <= 0:
        so = float(np.std(y[ok])) or 0.0
    if so <= 0:
        return None if mi == mo else (float("inf"), mi, mo, float(m.mean()))
    return (abs(mi - mo) / so, mi, mo, float(m.mean()))
