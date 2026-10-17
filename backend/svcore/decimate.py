"""
Signal Viewer - Display Decimation (large-file support)
===========================================================

The browser cannot draw (or even receive) tens of millions of points per trace:
a 10M-sample signal is ~200 MB of JSON per redraw. This module reduces ONLY what
is sent to the browser. Data in memory is untouched, and cursor values,
statistics, FFT, derived signals, compare and CSV export all still use the full
resolution data.

Algorithm: min/max per bin (a.k.a. "M4-lite").
    * Every bin keeps its minimum AND maximum sample (real samples, not averages),
      in their original order, so spikes / glitches are never lost visually.
    * Viewport aware: the currently visible X range gets the full point budget,
      the parts outside it get a coarse overview (so panning never shows emptiness).
      When the user zooms in, the app re-renders with the new range, so detail
      increases until individual raw samples are drawn (lossless at deep zoom).
    * NaN gaps are preserved (a bin that is all NaN becomes a gap).
    * Memory bounded: works in blocks, never copies the full signal.

Configuration:
    SV_MAX_POINTS=<n>  points per trace sent to the browser (default 4000).
    SV_MAX_POINTS=0    disables decimation (original "lossless" behaviour).
"""

import os
import weakref
from typing import Optional, Sequence, Tuple

import numpy as np

MAX_POINTS_PER_TRACE = int(os.environ.get("SV_MAX_POINTS", "4000"))
_BLOCK = 1 << 22  # samples processed per block (bounded temporary memory)


def decimation_enabled() -> bool:
    return MAX_POINTS_PER_TRACE > 0


def _minmax_indices(y: np.ndarray, n_out: int) -> np.ndarray:
    """Indices of the min & max sample of each bin, in ascending order."""
    n = len(y)
    if n <= n_out or n_out < 4:
        return np.arange(n)
    # ceil -> the remainder is always shorter than one bin (with floor, up to
    # n_bins-1 samples were squeezed into a single trailing bin and drawn coarse)
    b = int(np.ceil(n / max(1, n_out // 2)))   # samples per bin
    n_bins = n // b
    main = n_bins * b
    idx_parts = []
    bins_per_block = max(1, _BLOCK // b)
    for start_bin in range(0, n_bins, bins_per_block):
        stop_bin = min(n_bins, start_bin + bins_per_block)
        s0, s1 = start_bin * b, stop_bin * b
        blk = np.asarray(y[s0:s1], dtype=np.float64).reshape(stop_bin - start_bin, b)
        nan = np.isnan(blk)
        if nan.any():
            imin = np.where(nan, np.inf, blk).argmin(axis=1)
            imax = np.where(nan, -np.inf, blk).argmax(axis=1)
        else:
            imin = blk.argmin(axis=1)
            imax = blk.argmax(axis=1)
        base = s0 + np.arange(stop_bin - start_bin) * b
        lo = np.minimum(imin, imax) + base
        hi = np.maximum(imin, imax) + base
        idx_parts.append(np.column_stack([lo, hi]).ravel())
    if main < n:  # remainder -> one extra bin
        tail = np.asarray(y[main:], dtype=np.float64)
        if np.isnan(tail).all():
            t_lo = t_hi = 0
        else:
            t_lo, t_hi = int(np.nanargmin(tail)), int(np.nanargmax(tail))
        idx_parts.append(np.array(sorted({main + t_lo, main + t_hi})))
    idx = np.concatenate(idx_parts)
    # always keep the first and last sample so the trace spans the full range
    if idx[0] != 0:
        idx = np.concatenate([[0], idx])
    if idx[-1] != n - 1:
        idx = np.concatenate([idx, [n - 1]])
    # remove consecutive duplicates (min == max index)
    keep = np.ones(len(idx), dtype=bool)
    keep[1:] = idx[1:] != idx[:-1]
    return idx[keep]


# ----------------------------------------------------------------------------
# Block summaries: the index of the min and max sample of every BLOCK samples,
# computed once per array (one scan) and cached. When a display bin spans many
# blocks, its min/max come from the summaries instead of rescanning raw samples.
# The result is identical (the global min of a bin is the min of its blocks' mins).
# ----------------------------------------------------------------------------
BLOCK = 1024
_summaries: "dict[tuple, tuple]" = {}


def _summary(y: np.ndarray):
    key = (id(y), len(y))
    hit = _summaries.get(key)
    if hit is not None and hit[0]() is y:
        return hit[1], hit[2], hit[3], hit[4]
    nb = len(y) // BLOCK
    imin = np.empty(nb, dtype=np.int64)
    imax = np.empty(nb, dtype=np.int64)
    step = max(1, _BLOCK // BLOCK)
    for b0 in range(0, nb, step):
        b1 = min(nb, b0 + step)
        blk = np.asarray(y[b0 * BLOCK:b1 * BLOCK], dtype=np.float64).reshape(b1 - b0, BLOCK)
        nan = np.isnan(blk)
        base = np.arange(b0, b1) * BLOCK
        if nan.any():
            imin[b0:b1] = np.where(nan, np.inf, blk).argmin(axis=1) + base
            imax[b0:b1] = np.where(nan, -np.inf, blk).argmax(axis=1) + base
        else:
            imin[b0:b1] = blk.argmin(axis=1) + base
            imax[b0:b1] = blk.argmax(axis=1) + base
    vmin = np.asarray(y[imin], dtype=np.float64)
    vmax = np.asarray(y[imax], dtype=np.float64)
    # Entries hold only a WEAK reference to the signal: a reloaded / replaced / closed file
    # frees its (possibly gigabyte-sized) arrays at once instead of being kept alive here.
    for k in [k for k, v in _summaries.items() if v[0]() is None]:
        _summaries.pop(k, None)
    if len(_summaries) > 256:
        _summaries.pop(next(iter(_summaries)))
    _summaries[key] = (weakref.ref(y), imin, imax, np.where(np.isnan(vmin), np.inf, vmin), np.where(np.isnan(vmax), -np.inf, vmax))
    return imin, imax, _summaries[key][3], _summaries[key][4]


def _minmax_range(y: np.ndarray, s0: int, s1: int, n_out: int) -> np.ndarray:
    """Indices (into y) of min/max per bin for y[s0:s1]; uses block summaries for wide bins."""
    s0, s1 = max(0, int(s0)), min(len(y), int(s1))
    n = s1 - s0
    if n <= n_out or n_out < 4:
        return np.arange(s0, s1)
    per_bin = n / max(1, n_out // 2)
    if per_bin < 2 * BLOCK or len(y) < 16 * BLOCK:
        return _minmax_indices(y[s0:s1], n_out) + s0
    imin, imax, vmin, vmax = _summary(y)
    b0 = -(-s0 // BLOCK)                      # first whole block
    b1 = s1 // BLOCK                          # end of whole blocks
    nbk = b1 - b0
    g = int(np.ceil(nbk / max(1, n_out // 2)))   # blocks per display bin
    ng = nbk // g
    parts = []
    if b0 * BLOCK > s0:                       # partial head
        parts.append(_minmax_indices(y[s0:b0 * BLOCK], 4) + s0)
    if ng > 0:
        e = b0 + ng * g
        a_min = vmin[b0:e].reshape(ng, g).argmin(axis=1) + np.arange(ng) * g + b0
        a_max = vmax[b0:e].reshape(ng, g).argmax(axis=1) + np.arange(ng) * g + b0
        lo, hi = imin[a_min], imax[a_max]
        parts.append(np.column_stack([np.minimum(lo, hi), np.maximum(lo, hi)]).ravel())
        if e < b1:                            # leftover whole blocks
            k0, k1 = e, b1
            j1 = vmin[k0:k1].argmin() + k0
            j2 = vmax[k0:k1].argmax() + k0
            parts.append(np.sort(np.array([imin[j1], imax[j2]])))
    if b1 * BLOCK < s1:                       # partial tail
        parts.append(_minmax_indices(y[b1 * BLOCK:s1], 4) + b1 * BLOCK)
    idx = np.concatenate(parts) if parts else np.arange(s0, s1)
    keep = np.ones(len(idx), dtype=bool)
    keep[1:] = idx[1:] != idx[:-1]
    return idx[keep]


def minmax_decimate(x: np.ndarray, y: np.ndarray, n_out: int) -> Tuple[np.ndarray, np.ndarray]:
    n = len(x)
    if n <= n_out:
        return np.asarray(x), np.asarray(y)
    idx = _minmax_indices(y, n_out)
    return np.asarray(x[idx]), np.asarray(y[idx])


def _dec_range(x, y, s0, s1, n_out):
    idx = _minmax_range(y, s0, s1, n_out)
    return np.asarray(x[idx]), np.asarray(y[idx])


def decimate_for_view(
    x: np.ndarray,
    y: np.ndarray,
    xrange: Optional[Sequence[float]] = None,
    n_out: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray, bool]:
    """
    Reduce a (sorted-x) trace for display.

    Args:
        x: monotonic non-decreasing x (time) values
        y: values
        xrange: currently visible [x0, x1] (None = full range)
        n_out: point budget for the visible range

    Returns:
        (x_display, y_display, was_decimated)

    By design the result is NOT clipped to xrange: the visible window gets the full budget,
    and the data on each side is kept at a coarse resolution (plus one point beyond each edge),
    so the line reaches the plot edges and panning shows context at once. A window entirely
    outside the data therefore still returns the (coarse) trace - the plot clips it.
    """
    n_out = MAX_POINTS_PER_TRACE if n_out is None else n_out
    n = len(x)
    if n_out <= 0 or n <= n_out:
        return np.asarray(x), np.asarray(y), False

    if xrange is None or len(xrange) != 2 or xrange[0] is None or xrange[1] is None:
        xd, yd = _dec_range(x, y, 0, n, n_out)
        return xd, yd, True

    x0, x1 = sorted((float(xrange[0]), float(xrange[1])))
    i0 = max(0, int(np.searchsorted(x, x0, side="left")) - 1)
    i1 = min(n, int(np.searchsorted(x, x1, side="right")) + 1)
    if i1 - i0 <= 0:
        xd, yd = _dec_range(x, y, 0, n, n_out)
        return xd, yd, True

    side_budget = max(64, n_out // 8)
    parts_x, parts_y = [], []
    if i0 > 0:
        lx, ly = _dec_range(x, y, 0, i0, side_budget)
        parts_x.append(lx); parts_y.append(ly)
    mx, my = _dec_range(x, y, i0, i1, n_out)
    parts_x.append(mx); parts_y.append(my)
    if i1 < n:
        rx, ry = _dec_range(x, y, i1, n, side_budget)
        parts_x.append(rx); parts_y.append(ry)
    return np.concatenate(parts_x), np.concatenate(parts_y), True


def stride_decimate(x: np.ndarray, y: np.ndarray, n_out: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray, bool]:
    """Uniform stride decimation, for non-monotonic x (X-Y plots)."""
    n_out = MAX_POINTS_PER_TRACE * 4 if n_out is None else n_out  # X-Y shapes need more points
    n = len(x)
    if n_out <= 0 or n <= n_out:
        return np.asarray(x), np.asarray(y), False
    step = int(np.ceil(n / n_out))
    return np.asarray(x[::step]), np.asarray(y[::step]), True


def hold_at(time: np.ndarray, data: np.ndarray, target: float, look_back: int = 200_000) -> Optional[float]:
    """The value IN FORCE at target: the last real (non-NaN) sample at or before it, not an
    interpolation. For states / text values / modes (between STABILIZE=0 and ACRO=1 there is no 0.2)."""
    n = len(time)
    if n == 0 or target is None:
        return None
    try:
        i = int(np.searchsorted(time, float(target), side="right")) - 1
        if i < 0:
            return None
        lo = max(0, i - look_back)
        seg = np.asarray(data[lo:i + 1], dtype=np.float64)
        ok = np.flatnonzero(np.isfinite(seg))
        return float(seg[ok[-1]]) if len(ok) else None
    except (TypeError, ValueError, IndexError):     # a target or values that are not numbers
        return None


def interp_at(time: np.ndarray, data: np.ndarray, target: float) -> Optional[float]:
    """
    O(log n) linear interpolation at a single point, without copying the arrays
    (np.interp converts the whole array to float64 first - expensive for big/float32/mmap data).
    """
    n = len(time)
    if n == 0 or target is None:
        return None
    try:
        target = float(target)
        if target <= time[0]:
            return float(data[0])
        if target >= time[n - 1]:
            return float(data[n - 1])
        i = int(np.searchsorted(time, target, side="right"))
        t0, t1 = float(time[i - 1]), float(time[i])
        v0, v1 = float(data[i - 1]), float(data[i])
        if t1 == t0:
            return v1
        return v0 + (v1 - v0) * (target - t0) / (t1 - t0)
    except (TypeError, ValueError, IndexError):     # a target or values that are not numbers
        return None
