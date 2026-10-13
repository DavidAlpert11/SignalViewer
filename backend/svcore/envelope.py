"""T14: Monte-Carlo view - many runs of one quantity as an envelope.
All series are interpolated onto one time grid over their common overlap; per grid point:
min, max, lower / upper percentile and median. A run is an outlier when its RMS distance from
the median sits above the biggest (more than 3x) jump in the ranking of all runs' distances -
clearly apart from the rest; at most half of the runs."""
from typing import Dict, List, Optional, Tuple

import numpy as np


def envelope(series: List[Tuple[np.ndarray, np.ndarray]], t0: Optional[float] = None, t1: Optional[float] = None,
             points: int = 2000, pct: float = 5.0) -> Optional[Dict]:
    if len(series) < 2:
        return None
    ts = [np.asarray(t, dtype=np.float64) for t, _ in series]
    lo = max(float(t[0]) for t in ts if len(t))
    hi = min(float(t[-1]) for t in ts if len(t))
    if t0 is not None and t1 is not None:
        lo, hi = max(lo, min(t0, t1)), min(hi, max(t0, t1))
    if not hi > lo:
        return None
    grid = np.linspace(lo, hi, int(max(50, min(points, 20000))))
    m = np.vstack([np.interp(grid, t, np.asarray(y, dtype=np.float64), left=np.nan, right=np.nan)
                   for t, (_, y) in zip(ts, series)])
    with np.errstate(all="ignore"):
        p_lo, med, p_hi = np.nanpercentile(m, [pct, 50.0, 100.0 - pct], axis=0)
        dev = np.sqrt(np.nanmean((m - med) ** 2, axis=1))
    # Outliers: runs clearly SEPARATED from the rest. Rank the runs by distance from the median
    # and find the biggest jump between neighbours; when it is more than 3x, every run above it
    # is an outlier (a group of several bad runs is found too) - at most half of the runs.
    # (Ratios to the median distance flag ordinary runs: those distances are skewed - most runs
    # sit near the median - so any fixed multiple of it catches the normal tail.)
    order = [int(i) for i in np.argsort(-np.nan_to_num(dev, nan=-1.0)) if np.isfinite(dev[i])]
    best, cut = 3.0, 0
    for k in range(min(len(order) // 2, len(order) - 1)):
        a, b = dev[order[k]], dev[order[k + 1]]
        ratio = a / b if b > 0 else (np.inf if a > 0 else 0.0)
        if ratio > best:
            best, cut = ratio, k + 1
    flagged = set(order[:cut])
    outlier = [i in flagged for i in range(len(dev))]
    return {"t": grid, "min": np.nanmin(m, axis=0), "max": np.nanmax(m, axis=0), "lo": p_lo, "median": med, "hi": p_hi,
            "deviation": [float(d) for d in dev], "outlier": outlier, "pct": pct}
