"""T13: limits (pass / fail). A signal passes when every sample of the checked window is within
[lo, hi] (either may be None = no limit). The values checked are the ones on the plot
(scale and offset applied) - what the engineer set the limit against."""
from typing import Dict, List, Optional

import numpy as np

MAX_SPANS = 500


def check_limits(t: np.ndarray, y: np.ndarray, lo: Optional[float], hi: Optional[float],
                 t0: Optional[float] = None, t1: Optional[float] = None) -> Dict:
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if t0 is not None and t1 is not None:
        i0, i1 = np.searchsorted(t, min(t0, t1), "left"), np.searchsorted(t, max(t0, t1), "right")
        t, y = t[i0:i1], y[i0:i1]
    ok = np.isfinite(y)
    t, y = t[ok], y[ok]
    res = {"lo": lo, "hi": hi, "samples": int(len(y)), "pass": True, "violations": 0,
           "timeOutside": 0.0, "first": None, "worst": None, "worstT": None, "spans": []}
    if not len(y) or (lo is None and hi is None):
        return res
    over = np.zeros(len(y)) if hi is None else np.maximum(y - hi, 0)
    under = np.zeros(len(y)) if lo is None else np.maximum(lo - y, 0)
    excess = np.where(over > 0, over, -under)          # + above hi, - below lo, 0 inside
    bad = excess != 0
    if not bad.any():
        return res
    # stretches of consecutive outside samples; a stretch lasts until the next sample inside
    d = np.diff(bad.astype(np.int8))
    starts = list(np.flatnonzero(d == 1) + 1)
    ends = list(np.flatnonzero(d == -1) + 1)
    if bad[0]:
        starts.insert(0, 0)
    if bad[-1]:
        ends.append(len(y))
    spans: List[List[float]] = []
    outside = 0.0
    for a, b in zip(starts, ends):
        ta = float(t[a])
        tb = float(t[b]) if b < len(t) else float(t[-1])
        outside += tb - ta
        if len(spans) < MAX_SPANS:
            spans.append([ta, tb])
    k = int(np.argmax(np.abs(excess)))
    res.update({"pass": False, "violations": len(starts), "timeOutside": outside, "first": float(t[starts[0]]),
                "worst": float(excess[k]), "worstT": float(t[k]), "spans": spans})
    return res
