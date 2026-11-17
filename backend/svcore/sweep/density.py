"""Every run in the picture, however many there are (owner, 2026-11-17; CLAUDE.md: no point is ever left out of a
picture). Above the cap the page does not get the runs to draw one by one; it gets them counted per cell of the
picture - every run counts - and the runs of the sparse cells (the outliers: the runs a sample would most likely
drop) one by one. And the charts' numbers (histogram counts, box statistics, correlations) of every run.

The page says how its axes cut values into cells: per axis `edges` - ascending cell borders in the column's values
(the page's own scale: linear, log, reversed...), or `labels` - a text column's categories, a cell each. A value
outside the edges, or none, falls in the last cell ("missing", drawn below the axis)."""
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from svcore.sweep.encode import labels_of

# a cell with at most this many runs: its runs are drawn one by one (an outlier must never be a faint shade)
SPARSE = 3
# at most this many runs drawn one by one; above it the sparse threshold is lowered (fewer, rarer runs)
MAX_SPARSE_RUNS = 20_000


def cells(s: pd.Series, axis: Dict[str, Any]) -> np.ndarray:
    """Each value's cell on one axis (0..k-1), k = the missing cell."""
    if axis.get("labels") is not None:
        labels = [str(x) for x in axis["labels"]]
        k = len(labels)
        at = {x: i for i, x in enumerate(labels)}
        return labels_of(s).map(at).fillna(k).to_numpy(dtype=np.int64)
    edges = np.asarray(axis.get("edges") or [], dtype=np.float64)
    k = max(1, len(edges) - 1)
    v = pd.to_numeric(s, errors="coerce").to_numpy(dtype=np.float32, na_value=np.nan).astype(np.float64)
    c = _even(v, edges)                     # the usual case (a linear or log axis): arithmetic, not a search
    if c is None:
        c = np.searchsorted(edges, v, side="right") - 1
        if len(edges):
            c[v == edges[-1]] = k - 1
    with np.errstate(invalid="ignore"):
        bad = ~np.isfinite(v) | (c < 0) | (c >= k)
    c[bad] = k
    return c.astype(np.int64)


def _even(v: np.ndarray, edges: np.ndarray) -> Optional[np.ndarray]:
    """Cells of evenly spaced edges - in the values or in their logarithm - by arithmetic; None otherwise."""
    if len(edges) < 2 or not np.all(np.isfinite(edges)):
        return None
    k = len(edges) - 1
    for f in (None, np.log10):
        if f is not None and edges[0] <= 0:
            return None
        e = edges if f is None else f(edges)
        d = np.diff(e)
        if d[0] > 0 and np.allclose(d, d[0], rtol=1e-6, atol=0):
            with np.errstate(invalid="ignore", divide="ignore"):
                x = v if f is None else f(v)
                c = np.floor((x - e[0]) / d[0])
                c[x == e[-1]] = k - 1               # the top edge belongs to the last cell
            return np.where(np.isfinite(c), c, -1).astype(np.int64)
    return None


def n_cells(axis: Dict[str, Any]) -> int:
    return (len(axis["labels"]) if axis.get("labels") is not None else max(1, len(axis.get("edges") or []) - 1)) + 1


def parallel(df: Any, axes: Sequence[Dict[str, Any]], keep: np.ndarray, series: Optional[np.ndarray] = None,
             n_series: int = 1, sparse: int = SPARSE, max_sparse: int = MAX_SPARSE_RUNS) -> Dict[str, Any]:
    """Per pair of neighbouring axes, how many runs go from each cell of the one to each cell of the other - the
    runs kept (by series) and those left out apart - and which runs are in a sparse cell of any pair (kept ones
    only: they are the outliers to draw as lines). `df`: the columns by name (a DataFrame or a dict of Series)."""
    n = len(keep)
    cs = [cells(df[a["column"]], a) for a in axes]
    ks = [n_cells(a) for a in axes]
    ser = np.zeros(n, dtype=np.int64) if series is None else np.asarray(series, dtype=np.int64)
    ik, io = np.flatnonzero(keep), np.flatnonzero(~keep)
    sk = ser[ik]
    pairs = []
    rare = np.full(len(ik), np.iinfo(np.int64).max, dtype=np.int64)   # per kept run: the fewest runs it shares a cell pair with
    for i in range(len(axes) - 1):
        a, b, ka, kb = cs[i], cs[i + 1], ks[i], ks[i + 1]
        key = a * kb + b
        kk, ko = key[ik], key[io]
        out: Dict[str, Any] = {}
        for name, kkey, nser in (("kept", kk * n_series + sk, n_series), ("out", ko, 1)):
            cnt = np.bincount(kkey, minlength=ka * kb * nser)
            nz = np.flatnonzero(cnt)
            out[name] = {"a": (nz // nser // kb).tolist(), "b": (nz // nser % kb).tolist(),
                         "s": (nz % nser).tolist(), "n": cnt[nz].tolist()}
        tot = np.bincount(kk, minlength=ka * kb)
        np.minimum(rare, tot[kk], out=rare)
        pairs.append(out)
    if len(axes) == 1:                              # one axis: its cells alone
        rare = np.bincount(cs[0][ik], minlength=ks[0])[cs[0][ik]]
    th = sparse
    lone = ik[rare <= th]
    while len(lone) > max_sparse and th > 1:
        th -= 1
        lone = ik[rare <= th]
    if len(lone) > max_sparse:                      # even single runs are too many: the rarest kept ones first
        lone = np.sort(ik[np.argsort(rare, kind="stable")[:max_sparse]])
    return {"pairs": pairs, "cells": ks, "sparse": lone, "sparseAt": int(th)}


def grid2d(x: pd.Series, y: pd.Series, ax: Dict[str, Any], ay: Dict[str, Any], keep: np.ndarray,
           series: Optional[np.ndarray] = None, n_series: int = 1, sparse: int = SPARSE,
           max_sparse: int = MAX_SPARSE_RUNS) -> Dict[str, Any]:
    """A scatter of every run: how many runs (kept, by series) in each cell of x by y, and the runs of the sparse
    cells one by one."""
    cx, cy = cells(x, ax), cells(y, ay)
    kx, ky = n_cells(ax), n_cells(ay)
    ser = np.zeros(len(x), dtype=np.int64) if series is None else np.asarray(series, dtype=np.int64)
    key = cx * ky + cy
    kk = key[keep] * n_series + ser[keep]
    cnt = np.bincount(kk, minlength=kx * ky * n_series)
    nz = np.flatnonzero(cnt)
    tot = np.bincount(key[keep], minlength=kx * ky)
    lone_all = np.flatnonzero(keep)
    rare = tot[key[lone_all]]
    th = sparse
    lone = lone_all[rare <= th]
    while len(lone) > max_sparse and th > 1:
        th -= 1
        lone = lone_all[rare <= th]
    if len(lone) > max_sparse:
        lone = np.sort(lone_all[np.argsort(rare, kind="stable")[:max_sparse]])
    return {"x": (nz // n_series // ky).tolist(), "y": (nz // n_series % ky).tolist(), "s": (nz % n_series).tolist(),
            "n": cnt[nz].tolist(), "cells": [kx, ky], "sparse": lone, "sparseAt": int(th)}


# ----------------------------------------------------------------------------- the charts' numbers, of every run
def histogram(v: np.ndarray, lo: float, hi: float, bins: int, series: np.ndarray, n_series: int) -> List[List[int]]:
    """As the page's stats.histogram: `bins` equal bins over [lo, hi] (a value outside goes to the end bin), per series."""
    ok = np.isfinite(v)
    w = (hi - lo) / bins if hi > lo else 1.0
    b = np.clip(np.floor((v[ok] - lo) / w), 0, bins - 1).astype(np.int64)
    s = series[ok]
    good = (s >= 0) & (s < n_series)
    cnt = np.bincount(s[good] * bins + b[good], minlength=n_series * bins)
    return cnt.reshape(n_series, bins).tolist()


def box(v: np.ndarray, max_out: int = 200) -> Optional[Dict[str, Any]]:
    """As the page's stats.boxStats (quartiles linear between points, whiskers at a data point within 1.5 IQR); the
    points beyond the whiskers - the most extreme first when there are more than max_out."""
    a = np.sort(v[np.isfinite(v)])
    if not len(a):
        return None
    q1, med, q3 = (float(x) for x in np.percentile(a, [25, 50, 75]))
    iqr = q3 - q1
    lo = float(a[np.searchsorted(a, q1 - 1.5 * iqr, side="left")])
    hi = float(a[np.searchsorted(a, q3 + 1.5 * iqr, side="right") - 1])
    below, above = a[a < lo], a[a > hi]
    if len(below) + len(above) > max_out:          # the furthest out on each side, half each
        h = max_out // 2
        below, above = below[:h], above[-h:]
    return {"q1": q1, "med": med, "q3": q3, "lo": lo, "hi": hi, "n": int(len(a)),
            "out": [float(x) for x in np.concatenate([below, above])]}


def correlation(cols: List[np.ndarray], method: str) -> List[List[Optional[float]]]:
    """Pearson's r (or Spearman's rho: on ranks with ties averaged) of each pair, over the runs where both are numbers."""
    k = len(cols)
    out: List[List[Optional[float]]] = [[None] * k for _ in range(k)]
    for i in range(k):
        for j in range(k):
            x, y = cols[i], cols[j]
            ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() < 3:
                continue
            a, b = x[ok], y[ok]
            if method == "spearman":
                a, b = pd.Series(a).rank().to_numpy(), pd.Series(b).rank().to_numpy()
            a, b = a - a.mean(), b - b.mean()
            den = np.sqrt((a * a).sum() * (b * b).sum())
            out[i][j] = float((a * b).sum() / den) if den > 0 else None
    return out


# ----------------------------------------------------------------------------- the axes, as the page draws them
# cells per axis of a number column (a linear or log axis): enough for bands a few pixels high, few enough that a
# pair of axes has at most a few thousand cells to draw
AXIS_CELLS = 64
PLACES_MAX = 400                     # a number column with at most this many values can be a category axis


def domain(s: pd.Series) -> Dict[str, Any]:
    """What the page needs to build an axis of a number column for the whole table (not only the runs it got):
    the smallest and largest value, the smallest above zero (a log axis) and - when there are few - every value."""
    v = pd.to_numeric(s, errors="coerce").to_numpy(dtype=np.float32, na_value=np.nan).astype(np.float64)
    v = v[np.isfinite(v)]
    if not len(v):
        return {}
    pos = v[v > 0]
    out: Dict[str, Any] = {"lo": float(v.min()), "hi": float(v.max())}
    if len(pos):
        out["loPos"] = float(pos.min())
    u = pd.unique(v[: 1_000_000]) if len(v) > 1_000_000 else pd.unique(v)
    if len(u) <= PLACES_MAX and (len(v) <= 1_000_000 or len(pd.unique(v)) <= PLACES_MAX):
        out["places"] = sorted(float(x) for x in u)
    return out


def axis_cells(dom: Dict[str, Any], scale: str, labels: Optional[List[str]] = None) -> Dict[str, Any]:
    """How an axis cuts values into cells, as the page's makeScale places them: a text column - its labels; a
    category / ordinal number axis - its values (cells between their midpoints); a linear or log axis - AXIS_CELLS
    even cells over the domain (in the logarithm for log)."""
    if labels is not None:
        return {"labels": labels, "centers": list(range(len(labels)))}
    if scale in ("category", "ordinal") and dom.get("places") is not None:
        p = dom["places"]
        mids = [(a + b) / 2 for a, b in zip(p, p[1:])]
        return {"edges": [-np.inf, *mids, np.inf], "centers": p}
    lo, hi = dom.get("lo", 0.0), dom.get("hi", 1.0)
    if scale == "log":
        lo = dom.get("loPos", 1.0)
        a, b = np.log10(lo), np.log10(hi) if hi > 0 else np.log10(lo) + 1
        if b <= a:
            b = a + 1
        e = np.linspace(a, b, AXIS_CELLS + 1)
        return {"edges": (10 ** e).tolist(), "centers": (10 ** ((e[:-1] + e[1:]) / 2)).tolist()}
    if hi == lo:
        pad = abs(lo) * 0.05 or 1.0
        lo, hi = lo - pad, hi + pad
    e = np.linspace(lo, hi, AXIS_CELLS + 1)
    return {"edges": e.tolist(), "centers": ((e[:-1] + e[1:]) / 2).tolist()}
