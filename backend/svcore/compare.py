"""
Run comparison (phase 4).

The same signal from several runs is compared to a baseline: a chosen run, or the mean of all runs.

C1 - judged at full resolution, in both directions. Each run is a piecewise-linear curve between its
own samples, so the largest difference between two runs is at a sample of one of them: `pass`,
`withinPct` and `maxAbsDiff` are computed on the union of the run's and the baseline's samples
inside the overlap (the run's samples against the baseline interpolated there, and the baseline's
samples against the run). The descriptive numbers (RMS, mean, std, correlation, the profile) use
the baseline's own samples, all of them. Only the drawn difference trace is decimated. Before C1
everything ran on the baseline's samples strided down to `max_points` (200k in the CLI, 20k-50k in
the UI list), so a short excursion - or one between two samples of a slow golden run - passed.
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


def _grid(base_t: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """The baseline's own samples inside [lo, hi] - all of them (C1: no stride)."""
    i0, i1 = np.searchsorted(base_t, lo, "left"), np.searchsorted(base_t, hi, "right")
    return np.asarray(base_t[i0:i1], dtype=np.float64)


def _union(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """The sorted union of two sample-time vectors (both already inside the overlap)."""
    if len(a) == len(b) and np.array_equal(a, b):
        return a
    return np.union1d(a, b)


def _widen(v: np.ndarray, tol_abs: Optional[float], tol_pct: Optional[float]) -> np.ndarray:
    """The allowed difference at a baseline value: the larger of abs and pct x |value| (SDI)."""
    w = np.zeros(len(v))
    if tol_abs is not None:
        w = np.maximum(w, abs(tol_abs))
    if tol_pct is not None:
        w = np.maximum(w, np.abs(v) * abs(tol_pct) / 100.0)
    return w


def _judge_band(grid: np.ndarray, base_g: np.ndarray, u: np.ndarray, base_u: np.ndarray,
                tol_abs: Optional[float], tol_pct: Optional[float], tol_k: int,
                period: Optional[float]) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """The allowed difference (low, high) relative to the baseline at the judging times `u`. With a
    time tolerance the baseline's lowest / highest within +-tol_k of ITS OWN samples (the SDI rule,
    as before C1) is interpolated to `u`; angles have no time tolerance (as before)."""
    if tol_abs is None and tol_pct is None and (not tol_k or period):
        return None
    if tol_k > 0 and not period:
        from scipy.ndimage import maximum_filter1d, minimum_filter1d
        lo_g = minimum_filter1d(np.where(np.isfinite(base_g), base_g, np.inf), 2 * tol_k + 1, mode="nearest")
        hi_g = maximum_filter1d(np.where(np.isfinite(base_g), base_g, -np.inf), 2 * tol_k + 1, mode="nearest")
        if u is grid:
            lo_u, hi_u = lo_g, hi_g
        else:
            fin = np.isfinite(lo_g) & np.isfinite(hi_g)
            lo_u = np.interp(u, grid[fin], lo_g[fin]) if fin.any() else np.full(len(u), np.nan)
            hi_u = np.interp(u, grid[fin], hi_g[fin]) if fin.any() else np.full(len(u), np.nan)
        lo_u = np.fmin(lo_u, base_u)
        hi_u = np.fmax(hi_u, base_u)
        return lo_u - _widen(lo_u, tol_abs, tol_pct) - base_u, hi_u + _widen(hi_u, tol_abs, tol_pct) - base_u
    w = _widen(base_u, tol_abs, tol_pct)
    return -w, w


def _judge(u: np.ndarray, base_u: np.ndarray, other_u: np.ndarray, band: Optional[Tuple[np.ndarray, np.ndarray]],
           period: Optional[float]) -> Dict:
    """maxAbsDiff (and withinPct / pass with a band) over every judging time where both have data."""
    ok = np.isfinite(base_u) & np.isfinite(other_u)
    if not ok.any():
        return {}
    d = _wrap(other_u[ok] - base_u[ok], period) if period else other_u[ok] - base_u[ok]
    res: Dict = {"maxAbsDiff": float(np.max(np.abs(d))), "judgedSamples": int(ok.sum())}
    if band is not None:
        inside = (d >= band[0][ok]) & (d <= band[1][ok])
        res["withinPct"] = float(inside.mean() * 100.0)
        res["pass"] = bool(inside.all())
    return res


def metrics(base: np.ndarray, other: np.ndarray, tol_abs: Optional[float], tol_pct: Optional[float],
            period: Optional[float] = None, tol_k: int = 0) -> Dict:
    """tol_k: the time tolerance in grid samples - the baseline's band at a sample is its lowest and
    highest value within +-tol_k samples (as the Simulink Data Inspector's time tolerance), then
    widened by abs / pct: a run a little early or late passes."""
    ok = np.isfinite(base) & np.isfinite(other)
    if ok.sum() < 2:
        return {"valid": False}
    lo_b = hi_b = None
    if tol_k > 0 and not period:
        from scipy.ndimage import maximum_filter1d, minimum_filter1d
        filled = np.where(np.isfinite(base), base, np.nan)
        lo_b = minimum_filter1d(np.where(np.isfinite(filled), filled, np.inf), 2 * tol_k + 1, mode="nearest")[ok]
        hi_b = maximum_filter1d(np.where(np.isfinite(filled), filled, -np.inf), 2 * tol_k + 1, mode="nearest")[ok]
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
    if lo_b is not None and hi_b is not None:
        def widen(v: np.ndarray) -> np.ndarray:
            w = np.zeros(len(v))
            if tol_abs is not None:
                w = np.maximum(w, abs(tol_abs))
            if tol_pct is not None:
                w = np.maximum(w, np.abs(v) * abs(tol_pct) / 100.0)
            return w
        inside = (o >= lo_b - widen(lo_b)) & (o <= hi_b + widen(hi_b))
        res["withinPct"] = float(inside.mean() * 100.0)
        res["pass"] = bool(inside.all())
    elif tol_abs is not None or tol_pct is not None:
        # the band is the LARGER of the two (as the Simulink Data Inspector: max(abs, rel x |baseline|)).
        # It was the smaller: with a percentage the band closed to 0 wherever the golden value crossed 0,
        # so a roll angle with --tol-pct failed at every zero crossing, and adding pct to abs tightened it.
        lim = np.zeros(len(b))
        if tol_abs is not None:
            lim = np.maximum(lim, abs(tol_abs))
        if tol_pct is not None:
            lim = np.maximum(lim, np.abs(b) * abs(tol_pct) / 100.0)
        inside = np.abs(d) <= lim
        res["withinPct"] = float(inside.mean() * 100.0)
        res["pass"] = bool(inside.all())
    return res


PROFILE_BINS = 32


def difference_trace(grid: np.ndarray, base: np.ndarray, other: np.ndarray,
                     band: Optional[Tuple[np.ndarray, np.ndarray]], period: Optional[float], points: int) -> Dict:
    """U5 (SDI-style difference view): run - baseline over time with the tolerance band (`band`: the
    allowed difference low / high at each `grid` time, see `_judge_band`) and the stretches outside
    it. C1: `grid` is the full judging grid; the stretches outside are found on all of it and only the
    curve is reduced to about `points` buckets (each keeps its lowest and highest difference, so a
    spike stays)."""
    ok = np.isfinite(base) & np.isfinite(other)
    d = np.where(ok, _wrap(other - base, period) if period else other - base, np.nan)
    out: List[List[float]] = []
    if band is not None:
        bad = ok & ((d < band[0]) | (d > band[1]))
        edges = np.flatnonzero(np.diff(np.concatenate([[0], bad.astype(np.int8), [0]])))
        # stretches a hair apart (noise around the band's edge) are one: the gap must be at least
        # 0.2 % of the comparison to count - else a noisy signal listed hundreds of slivers
        gap = 0.002 * float(grid[-1] - grid[0]) if len(grid) > 1 else 0.0
        for a, b in zip(edges[::2], edges[1::2]):
            t_a, t_b = float(grid[a]), float(grid[min(b, len(grid)) - 1])
            if out and t_a - out[-1][1] <= gap:
                out[-1][1] = t_b
            else:
                out.append([t_a, t_b])
    n = len(grid)
    k = max(1, int(np.ceil(n / max(points, 1))))
    t_out: List[float] = []
    d_out: List[Optional[float]] = []
    lo_out: List[Optional[float]] = []
    hi_out: List[Optional[float]] = []
    r = lambda v: float(f"{v:.6g}") if np.isfinite(v) else None   # noqa: E731
    for i in range(0, n, k):
        sl = slice(i, min(n, i + k))
        seg = d[sl]
        fin = np.isfinite(seg)
        lo_b = float(np.nanmin(band[0][sl])) if band is not None and np.isfinite(band[0][sl]).any() else np.nan
        hi_b = float(np.nanmax(band[1][sl])) if band is not None and np.isfinite(band[1][sl]).any() else np.nan
        if not fin.any():
            t_out.append(float(grid[i])); d_out.append(None); lo_out.append(r(lo_b)); hi_out.append(r(hi_b))
            continue
        j_lo, j_hi = int(np.nanargmin(np.where(fin, seg, np.inf))), int(np.nanargmax(np.where(fin, seg, -np.inf)))
        for j in sorted({j_lo, j_hi}):
            t_out.append(float(grid[i + j])); d_out.append(r(float(seg[j]))); lo_out.append(r(lo_b)); hi_out.append(r(hi_b))
    return {"t": t_out, "d": d_out, **({"lo": lo_out, "hi": hi_out} if band is not None else {}), "out": out[:2000]}


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


def _on(u: np.ndarray, t: np.ndarray, y: np.ndarray, alignment: str, period: Optional[float]) -> np.ndarray:
    # an angle is unwrapped before resampling (else a 359 -> 1 step interpolates through 180)
    return align_to(u, t, _unwrap(y, period) if period else y, alignment)


def _mean_on(u: np.ndarray, series: List[Tuple[str, np.ndarray, np.ndarray]], alignment: str,
             period: Optional[float]) -> np.ndarray:
    """The mean of all runs at the times `u`, one run at a time (memory: a few vectors of len(u))."""
    acc = np.zeros(len(u))
    acc2 = np.zeros(len(u)) if period else None
    cnt = np.zeros(len(u))
    for _, t, y in series:
        v = _on(u, t, y, alignment, period)
        fin = np.isfinite(v)
        if period:
            a = v * (2 * np.pi / period)
            acc[fin] += np.sin(a[fin])
            assert acc2 is not None
            acc2[fin] += np.cos(a[fin])
        else:
            acc[fin] += v[fin]
        cnt += fin
    with np.errstate(invalid="ignore", divide="ignore"):
        if period:
            assert acc2 is not None
            out = np.arctan2(acc / cnt, acc2 / cnt) * (period / (2 * np.pi))
        else:
            out = acc / cnt
    out[cnt == 0] = np.nan
    return out


def compare(series: List[Tuple[str, np.ndarray, np.ndarray]], baseline: str, alignment: str = "linear",
            tol_abs: Optional[float] = None, tol_pct: Optional[float] = None, max_points: int = 200_000,
            tol_time: Optional[float] = None, trace: int = 0) -> Dict:
    """series: [(signal id, time, data)]; baseline: a signal id from series, or "mean". trace > 0: each
    row also has its difference over time with the tolerance band (U5, `difference_trace`).

    max_points: kept for callers; since C1 nothing that is judged or reported is reduced (the CLI and
    the UI give the same numbers whatever they pass) - only the drawn trace is, to about `trace`."""
    del max_points
    if len(series) < 2:
        raise ValueError("Choose at least two runs to compare.")
    lo = max(float(t[0]) for _, t, _ in series)
    hi = min(float(t[-1]) for _, t, _ in series)
    if hi <= lo:
        raise ValueError("The runs do not overlap in time. Try aligning them in time first.")
    ref = next((s for s in series if s[0] == baseline), series[0])
    grid = _grid(ref[1], lo, hi)
    sid0 = series[0][0]
    period = angle_period(sid0[sid0.find("/") + 1:], [np.asarray(y, dtype=np.float64) for _, _, y in series])

    def base_at(u: np.ndarray) -> np.ndarray:
        return _mean_on(u, series, alignment, period) if baseline == "mean" else _on(u, ref[1], ref[2], alignment, period)
    base = base_at(grid)
    tol_k = 0
    if tol_time and tol_time > 0 and len(grid) > 1:
        step = float(np.median(np.diff(grid)))
        tol_k = int(np.ceil(tol_time / step)) if step > 0 else 0
    rows = []
    for sid, t, y in series:
        if baseline != "mean" and sid == ref[0]:
            continue
        other = _on(grid, t, y, alignment, period)
        # descriptive numbers on the baseline's own samples (all of them); the band only via _judge
        m = metrics(base, other, None, None, period)
        if m.get("valid"):
            t64 = np.asarray(t, dtype=np.float64)
            own = t64[np.searchsorted(t64, lo, "left"):np.searchsorted(t64, hi, "right")]
            u = _union(grid, own)
            base_u = base if u is grid else base_at(u)
            other_u = other if u is grid else _on(u, t, y, alignment, period)
            band = _judge_band(grid, base, u, base_u, tol_abs, tol_pct, tol_k, period)
            j = _judge(u, base_u, other_u, band, period)
            m.update(j)
            m["profile"] = diff_profile(base, other, period=period)
            if trace > 0:
                m["trace"] = difference_trace(u, base_u, other_u, band, period, trace)
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
