"""
Run comparison (phase 4).

The same signal from several runs is resampled onto one time grid (the baseline's
samples inside the common overlap, at most `max_points` of them) and compared to a
baseline: a chosen run, or the mean of all runs.
"""

from typing import Dict, List, Optional, Tuple

import numpy as np

from svcore.analysis import align_to

# F16: headings / yaw wrap at 0/360 - 359 deg vs 1 deg is 2 deg apart, not 358. An angle is a signal whose
# unit is an angle (not a rate: "deg/s" is not) and that is named like a direction, or whose values
# really sweep most of a turn. Roll / pitch in a small range are angles too, but never 180 apart.
_ANGLE_UNITS = {"deg": 360.0, "degree": 360.0, "degrees": 360.0, "°": 360.0, "rad": 2 * np.pi, "radian": 2 * np.pi, "radians": 2 * np.pi}
_ANGLE_WORDS = ("yaw", "heading", "hdg", "course", "cog", "bearing", "azimuth", "azi", "psi", "track", "wind_dir", "winddir", "direction")


def angle_period(name: str, values: List[np.ndarray]) -> Optional[float]:
    """360 (or 2 pi) when the signal `name` ("ATT.Yaw [deg]") is an angle that wraps, else None."""
    unit = name[name.rfind("[") + 1:name.rfind("]")].strip().lower() if name.rstrip().endswith("]") and "[" in name else ""
    period = _ANGLE_UNITS.get(unit)
    if period is None:
        return None
    low = name.lower()
    if any(w in low for w in _ANGLE_WORDS):
        return period
    spans = [float(np.nanmax(v) - np.nanmin(v)) for v in values if len(v) and np.isfinite(v).any()]
    return period if spans and max(spans) >= 0.75 * period else None


def _wrap(d: np.ndarray, period: float) -> np.ndarray:
    return (d + period / 2) % period - period / 2


def _unwrap(y: np.ndarray, period: float) -> np.ndarray:
    y = np.asarray(y, dtype=np.float64)
    out = y.copy()
    ok = np.isfinite(y)
    if ok.any():
        out[ok] = np.unwrap(y[ok], period=period)
    return out


def _circular_mean(rows: np.ndarray, period: float) -> np.ndarray:
    a = rows * (2 * np.pi / period)
    return np.arctan2(np.nanmean(np.sin(a), axis=0), np.nanmean(np.cos(a), axis=0)) * (period / (2 * np.pi))


def _grid(base_t: np.ndarray, lo: float, hi: float, max_points: int) -> np.ndarray:
    i0, i1 = np.searchsorted(base_t, lo, "left"), np.searchsorted(base_t, hi, "right")
    g = np.asarray(base_t[i0:i1], dtype=np.float64)
    if len(g) > max_points:
        g = g[:: int(np.ceil(len(g) / max_points))]
    return g


def metrics(base: np.ndarray, other: np.ndarray, tol_abs: Optional[float], tol_pct: Optional[float],
            period: Optional[float] = None) -> Dict:
    ok = np.isfinite(base) & np.isfinite(other)
    if ok.sum() < 2:
        return {"valid": False}
    b, o = base[ok], other[ok]
    d = _wrap(o - b, period) if period else o - b
    if period:                  # the shapes without the 0/360 jumps, for the range and the correlation
        b, o = _unwrap(b, period), _unwrap(o, period)
    # error is relative to the baseline's range (an angle: at most one turn); a constant baseline uses its magnitude
    span = float(np.ptp(b)) or float(np.max(np.abs(b))) or 1.0
    if period:
        span = min(span, period)
    res = {
        "valid": True,
        "samples": int(ok.sum()),
        "rmsDiff": float(np.sqrt(np.mean(d * d))),
        "maxAbsDiff": float(np.max(np.abs(d))),
        "meanDiff": float(np.mean(d)),
        "stdDiff": float(np.std(d)),
        "rmsPct": float(np.sqrt(np.mean(d * d)) / span * 100.0),
        "matchPct": float(max(0.0, 100.0 - np.sqrt(np.mean(d * d)) / span * 100.0)),
        "correlation": float(np.corrcoef(b, o)[0, 1]) if np.std(b) > 0 and np.std(o) > 0 else (1.0 if np.allclose(b, o) else 0.0),
    }
    if tol_abs is not None or tol_pct is not None:
        lim = np.full(len(b), np.inf)
        if tol_abs is not None:
            lim = np.minimum(lim, tol_abs)
        if tol_pct is not None:
            lim = np.minimum(lim, np.abs(b) * tol_pct / 100.0)
        inside = np.abs(d) <= lim
        res["withinPct"] = float(inside.mean() * 100.0)
        res["pass"] = bool(inside.all())
    return res


PROFILE_BINS = 32


def diff_profile(base: np.ndarray, other: np.ndarray, bins: int = PROFILE_BINS, period: Optional[float] = None) -> List[Optional[float]]:
    """RMS of (other - base) in `bins` equal time slices, as % of the baseline's range
    (None for a slice with no valid sample: drawn as a gap)."""
    d = _wrap(other - base, period) if period else other - base
    ok = np.isfinite(d)
    if period:
        base = _unwrap(base, period)
    span = float(np.nanmax(base) - np.nanmin(base)) if np.isfinite(base).any() else 0.0
    if period:
        span = min(span, period)
    span = span or float(np.nanmax(np.abs(base))) if np.isfinite(base).any() else 1.0
    span = span or 1.0
    out = []
    for part, okp in zip(np.array_split(d, bins), np.array_split(ok, bins)):
        out.append(round(float(np.sqrt(np.mean(part[okp] ** 2)) / span * 100.0), 3) if okp.any() else None)
    return out


def compare(series: List[Tuple[str, np.ndarray, np.ndarray]], baseline: str, alignment: str = "linear",
            tol_abs: Optional[float] = None, tol_pct: Optional[float] = None, max_points: int = 200_000) -> Dict:
    """series: [(signal id, time, data)]; baseline: a signal id from series, or "mean"."""
    if len(series) < 2:
        raise ValueError("Choose at least two runs to compare.")
    lo = max(float(t[0]) for _, t, _ in series)
    hi = min(float(t[-1]) for _, t, _ in series)
    if hi <= lo:
        raise ValueError("The runs do not overlap in time. Try aligning them in time first.")
    ref = next((s for s in series if s[0] == baseline), series[0])
    grid = _grid(ref[1], lo, hi, max_points)
    sid0 = series[0][0]
    period = angle_period(sid0[sid0.find("/") + 1:], [np.asarray(y, dtype=np.float64) for _, _, y in series])
    # an angle is unwrapped before resampling (else a 359 -> 1 step interpolates through 180)
    aligned = {sid: align_to(grid, t, _unwrap(y, period) if period else y, alignment) for sid, t, y in series}
    if baseline == "mean":
        stack = np.vstack(list(aligned.values()))
        base = _circular_mean(stack, period) if period else np.nanmean(stack, axis=0)
    else:
        base = aligned[ref[0]]
    rows = []
    for sid, _, _ in series:
        if baseline != "mean" and sid == ref[0]:
            continue
        m = metrics(base, aligned[sid], tol_abs, tol_pct, period)
        if m.get("valid"):
            m["profile"] = diff_profile(base, aligned[sid], period=period)
        rows.append({"id": sid, **m})
    return {"overlap": [lo, hi], "gridPoints": int(len(grid)), "baseline": baseline if baseline == "mean" else ref[0], "rows": rows,
            **({"angle": period} if period else {})}


def _xcorr(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """c[k] = sum_i x[i+k] * y[i] for lags k = -(n-1) .. (n-1), via FFT."""
    n = len(x)
    c = np.fft.irfft(np.fft.rfft(x, 2 * n) * np.conj(np.fft.rfft(y, 2 * n)), 2 * n)
    return np.concatenate([c[-(n - 1):], c[:n]])


def auto_shift(base: Tuple[np.ndarray, np.ndarray], other: Tuple[np.ndarray, np.ndarray], max_points: int = 20000,
               max_shift_frac: float = 0.25, min_overlap: float = 0.5) -> float:
    """
    Time shift to ADD to `other` so it best lines up with `base`.

    Minimizes the mean squared difference over the overlap for every candidate lag
    (computed for all lags at once with FFT correlations). Unlike plain cross-correlation
    this is not biased toward zero lag by DC offsets or slow trends, and it is robust to noise.
    """
    (tb, yb), (to, yo) = base, other
    lo = min(float(tb[0]), float(to[0]))
    hi = max(float(tb[-1]), float(to[-1]))
    dt_b = (float(tb[-1]) - float(tb[0])) / max(1, len(tb) - 1)
    dt_o = (float(to[-1]) - float(to[0])) / max(1, len(to) - 1)
    dt = max(min(dt_b, dt_o), (hi - lo) / max_points)
    grid = np.arange(lo, hi, dt)
    a = np.interp(grid, tb, np.asarray(yb, dtype=np.float64), left=np.nan, right=np.nan)
    b = np.interp(grid, to, np.asarray(yo, dtype=np.float64), left=np.nan, right=np.nan)
    # Standardize: the shift must depend on the shape, not on gain or offset differences
    # between runs (a run with 10% lower gain otherwise pulls the minimum off).
    for arr in (a, b):
        m, sd = np.nanmean(arr), np.nanstd(arr)
        arr -= m
        if sd > 0:
            arr /= sd
    wa, wb = np.isfinite(a).astype(float), np.isfinite(b).astype(float)
    a0, b0 = np.where(wa > 0, a, 0.0), np.where(wb > 0, b, 0.0)
    n = len(grid)
    count = _xcorr(wa, wb)                         # overlapping samples per lag
    s_aa = _xcorr(a0 * a0, wb)
    s_bb = _xcorr(wa, b0 * b0)
    cross = _xcorr(a0, b0)
    lags = np.arange(-(n - 1), n)
    ok = (np.abs(lags) <= int(n * max_shift_frac)) & (count >= min_overlap * min(wa.sum(), wb.sum()))
    if not ok.any():
        return 0.0
    mse = np.full(len(lags), np.inf)
    mse[ok] = (s_aa[ok] + s_bb[ok] - 2 * cross[ok]) / count[ok]
    k = int(np.argmin(mse))
    # sub-sample refinement (parabola through the minimum)
    frac = 0.0
    if 0 < k < len(mse) - 1 and np.isfinite(mse[k - 1]) and np.isfinite(mse[k + 1]):
        den = mse[k - 1] - 2 * mse[k] + mse[k + 1]
        if den > 0:
            frac = 0.5 * (mse[k - 1] - mse[k + 1]) / den
    return float((lags[k] + frac) * dt)
