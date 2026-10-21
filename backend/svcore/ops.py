"""
Signal Viewer - signal maths shared by the analysis engine, formulas and reports:
nearest-sample lookup, spectra (FFT / Welch), Butterworth filters, statistics,
moving average and integral.

(The Dash-era per-signal operation classes that lived here were removed in T34: nothing called
them; the operations are in svcore/analysis.py and svcore/formula.py.)
"""

import weakref
from typing import Any, Dict, Optional, Tuple

import numpy as np


def nearest_indices(t_src: np.ndarray, t_query: np.ndarray) -> np.ndarray:
    """Index of the truly NEAREST sample in sorted t_src for each query time
    (np.searchsorted alone returns the next sample, i.e. up to one full step off)."""
    t_src = np.asarray(t_src)
    n = len(t_src)
    idx = np.clip(np.searchsorted(t_src, t_query), 0, n - 1)
    left = np.clip(idx - 1, 0, n - 1)
    use_left = np.abs(t_src[left] - t_query) <= np.abs(t_src[idx] - t_query)
    return np.where(use_left, left, idx)


# =============================================================================
# FFT ANALYSIS
# =============================================================================

GAP_FACTOR = 1.5        # a step longer than 1.5 median intervals is a gap (a logger pause, a lost packet)
MAX_UNIFORM_SAMPLES = 20_000_000


GAP_ISOLATED = 5.0      # a step 5 x longer than BOTH its neighbours (and > GAP_FACTOR medians) is a gap


def isolated_gaps(steps: np.ndarray, median_step: float) -> np.ndarray:
    """Which time steps are GAPS - time with no data (a logger pause, a radio dropout): a step more
    than GAP_ISOLATED times longer than both neighbouring steps and longer than GAP_FACTOR median
    steps. Long steps that follow each other (a variable-step solver's steady state, a slower logging
    rate) are sparse sampling, not gaps. Shared by spectra (A1, what the plot reports) and statistics (A3)."""
    d = np.asarray(steps, dtype=np.float64)
    if len(d) < 2:
        return d > GAP_FACTOR * median_step
    prev = np.concatenate([d[1:2], d[:-1]])               # the first step's only neighbour is the next
    nxt = np.concatenate([d[1:], d[-2:-1]])               # the last step's only neighbour is the previous
    return (d > GAP_ISOLATED * prev) & (d > GAP_ISOLATED * nxt) & (d > GAP_FACTOR * median_step)


def uniform_samples(time: np.ndarray, data: np.ndarray,
                    max_samples: int = MAX_UNIFORM_SAMPLES) -> Tuple[float, np.ndarray, Dict[str, Any]]:
    """The signal on an evenly spaced time grid, as every spectrum needs (A1).

    An FFT takes sample k to be at k*dt. Flight logs break that: a logger pause, dropped packets,
    jitter. With the mean interval of a 20 s record that has a 2 s pause, a 37 Hz tone was shown at
    33.3 Hz. So:
      * no gap (no step above GAP_FACTOR median steps), no NaN, time increasing: the samples are
        used as they are with the MEAN interval - timestamp jitter is noise on the stamps, not on
        the samples, and interpolating would only blur the high frequencies;
      * otherwise the samples (NaN left out) are linearly interpolated in TIME onto a grid of the
        MEDIAN interval (what the logger meant to do). The frequencies are then right; a bridged
        gap holds no signal, so amplitudes are lower by about the share of time it covers.

    Returns (dt, y, info); info = {"resampled": bool, "fs": Hz, "gaps": count, "gapTime": s} - gaps
    and gapTime count only real gaps (isolated_gaps), not sparse sampling, which is resampled too.
    dt is 0 (and y empty) when the signal has no usable interval."""
    t = np.asarray(time, dtype=np.float64)
    y = np.asarray(data, dtype=np.float64)
    ok = np.isfinite(t) & np.isfinite(y)
    if not ok.all():
        t, y = t[ok], y[ok]
    info: Dict[str, Any] = {"resampled": False, "fs": None, "gaps": 0, "gapTime": 0.0}
    if len(t) < 2:
        return 0.0, np.array([]), info
    steps = np.diff(t)
    pos = steps[steps > 0]
    if not len(pos):
        return 0.0, np.array([]), info
    dt = float(np.median(pos))
    gap = isolated_gaps(steps, dt)                        # reported: time with no data
    info["gaps"] = int(gap.sum())
    info["gapTime"] = float(np.sum(steps[gap] - dt)) if info["gaps"] else 0.0
    if ok.all() and not bool(np.any(steps > GAP_FACTOR * dt)) and bool(np.all(steps > 0)):
        dt = float(t[-1] - t[0]) / (len(t) - 1)
        info["fs"] = 1.0 / dt
        return dt, y, info
    info["fs"] = 1.0 / dt
    n = int(np.floor((t[-1] - t[0]) / dt + 1e-9)) + 1
    if n > max_samples:
        raise ValueError("Too many samples for a spectrum - zoom in.")
    grid = t[0] + np.arange(n) * dt
    info["resampled"] = True
    return dt, np.interp(grid, t, y), info


def compute_welch(time: np.ndarray, data: np.ndarray, window: str = "hanning",
                  info: Optional[Dict[str, Any]] = None) -> Tuple[np.ndarray, np.ndarray]:
    """Welch power spectral density (units^2/Hz): the recording is cut into overlapping pieces
    whose spectra are averaged - much less noisy than one FFT, the usual view for vibration.
    Same preparation as compute_fft (an even time grid, see uniform_samples; mean removed).
    info, when given, is filled with what uniform_samples did."""
    from scipy.signal import welch
    if len(data) < 16:
        return np.array([]), np.array([])
    try:
        dt, data, how = uniform_samples(time, data)
    except ValueError as e:
        if info is not None:
            info["error"] = str(e)
        return np.array([]), np.array([])
    if info is not None:
        info.update(how)
    n = len(data)
    if not dt > 0 or n < 16:
        return np.array([]), np.array([])
    # about 8 pieces (50 % overlap -> ~15 averages), a power of two, at least 256 samples
    nperseg = int(min(n, max(256, 2 ** int(np.floor(np.log2(max(n / 8, 1)))))))
    win = {"hanning": "hann", "hamming": "hamming", "blackman": "blackman"}.get(window, "boxcar")
    f, p = welch(data, fs=1.0 / dt, window=win, nperseg=nperseg, detrend="constant", scaling="density")
    return f, p


def compute_fft(
    time: np.ndarray,
    data: np.ndarray,
    window: str = "hanning",
    info: Optional[Dict[str, Any]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Single-sided amplitude spectrum (a sine of amplitude A shows as A at its frequency).

    Args:
        time: Time array
        data: Signal data
        window: Window function ("hanning", "hamming", "blackman", "none")
        info: optional dict, filled with what uniform_samples did (resampled, fs, gaps)

    Returns:
        (frequencies, magnitudes) arrays
    """
    if len(data) < 2:
        return np.array([]), np.array([])
    try:
        dt, data, how = uniform_samples(time, data)
    except ValueError as e:
        if info is not None:
            info["error"] = str(e)
        return np.array([]), np.array([])
    if info is not None:
        info.update(how)
    n = len(data)
    if not dt > 0 or n < 2:
        return np.array([]), np.array([])

    # Remove DC component (mean)
    data_centered = data - np.mean(data)
    
    # Apply window function
    if window == "hanning":
        win = np.hanning(n)
    elif window == "hamming":
        win = np.hamming(n)
    elif window == "blackman":
        win = np.blackman(n)
    else:
        win = np.ones(n)
    
    windowed_data = data_centered * win
    
    # Compute FFT (real input)
    fft_result = np.fft.rfft(windowed_data)
    freqs = np.fft.rfftfreq(n, dt)
    
    # Calculate magnitude (normalized)
    magnitudes = np.abs(fft_result) * 2.0 / np.sum(win)
    
    # Skip DC component (first element)
    return freqs[1:], magnitudes[1:]


# =============================================================================
# SIGNAL FILTERING
# =============================================================================

class FilterError(ValueError):
    """A filter that cannot be applied, said in words for the user (never raw data instead)."""


def zero_phase_design_cutoff(cutoff: float, fs: float, filter_type: str, order: int = 4) -> float:
    """The Butterworth cut-off (Hz) to design with so that the ZERO-PHASE result is at -3 dB at `cutoff` (A2).

    Running a filter forward and backward squares its magnitude: a Butterworth designed at fc is at
    -3 dB at fc once, so at -6 dB after both passes, and the band edge the user asked for moved
    (a "10 Hz" low-pass halved a 10 Hz signal). For the squared response to be at half power
    (|H|^4 = 1/2) the single filter must be at |H|^2 = 1/sqrt(2) there, which for a digital
    Butterworth (bilinear, pre-warped: w = tan(pi f / fs)) gives
        low-pass:   w_c = w / (sqrt(2) - 1) ** (1 / (2 N))
        high-pass:  w_c = w * (sqrt(2) - 1) ** (1 / (2 N))
    exactly, at any cut-off below Nyquist. For order 4: the design frequency is about 1.12 x the
    cut-off for a low-pass and 0.90 x for a high-pass (more where the cut-off is near Nyquist).

    To reproduce a result in MATLAB / SciPy: filtfilt(butter(N, fd / (fs/2)), x) with fd = this value."""
    k = (np.sqrt(2.0) - 1.0) ** (1.0 / (2 * int(order)))
    w = np.tan(np.pi * float(cutoff) / float(fs))
    wc = w / k if filter_type == "lowpass" else w * k
    return float(np.arctan(wc) * fs / np.pi)


def apply_filter(time: np.ndarray, data: np.ndarray, filter_type: str, cutoff: float,
                 order: int = 4) -> np.ndarray:
    """Butterworth low-pass / high-pass, run forward and backward (zero phase: no delay, so a
    filtered step stays where the raw step is). The cut-off is the -3 dB (half-power) point of the
    RESULT, as its name says: the filter is designed for the two passes (zero_phase_design_cutoff;
    before A2 the result was at -6 dB there). The sample rate is the median sample interval,
    which ignores logging jitter and gaps. NaN samples are bridged for the filter and are NaN
    again in the result.

    Until T34 this was a moving average (the code avoided scipy, which is now a dependency) and
    it returned the RAW data, silently, whenever it could not filter."""
    from scipy.signal import butter, sosfiltfilt
    if filter_type not in ("lowpass", "highpass"):
        raise FilterError(f"Unknown filter: {filter_type}.")
    y = np.asarray(data, dtype=np.float64)
    t = np.asarray(time, dtype=np.float64)
    n = len(y)
    if n < 2 or len(t) != n:
        raise FilterError("The signal is too short to filter.")
    steps = np.diff(t)
    steps = steps[np.isfinite(steps) & (steps > 0)]
    if not len(steps):
        raise FilterError("The time of this signal does not increase, so its sample rate is unknown.")
    fs = 1.0 / float(np.median(steps))
    nyq = 0.5 * fs
    cutoff = float(cutoff)
    if not (0 < cutoff < nyq):
        raise FilterError(f"The cut-off ({cutoff:g} Hz) must be above 0 and below half the sample "
                          f"rate ({nyq:.6g} Hz).")
    ok = np.isfinite(y)
    if ok.sum() < 2:
        return np.full(n, np.nan)
    filled = y if ok.all() else np.interp(np.arange(n), np.flatnonzero(ok), y[ok])
    wn = zero_phase_design_cutoff(cutoff, fs, filter_type, int(order)) / nyq
    wn = min(max(wn, 1e-12), 1.0 - 1e-9)          # a cut-off right at Nyquist rounds to 1.0
    sos = butter(int(order), wn, btype=filter_type, output="sos")
    # the default edge padding needs more samples than a very short signal has
    padlen = min(3 * (2 * len(sos) + 1), n - 1)
    out = sosfiltfilt(sos, filled, padlen=padlen)
    out[~ok] = np.nan
    return out


# =============================================================================
# SIGNAL STATISTICS
# =============================================================================

# Results per (time array, data array, range). The key holds the arrays' ids, and the entry holds
# weak references to the arrays themselves: CPython gives a new array the address of one just freed,
# so an id alone would hand a fresh array (a filtered or scaled copy, a reloaded file) the numbers of
# an old one (F23). A weak reference does not keep a big temporary alive; a dead one is a miss.
_STATS_CACHE: Dict[tuple, Tuple[Any, Any, Dict[str, float]]] = {}
_STATS_CACHE_MAX = 256


def _weak(a):
    try:
        return weakref.ref(a)
    except TypeError:            # not weak-referenceable (a list...): never matched again
        return lambda: None


def time_weights(t: np.ndarray) -> Tuple[Optional[np.ndarray], int]:
    """How much time each sample stands for, for mean / RMS / std (A3); (None, 0) when the samples
    are evenly spaced (every step within +-50 % of the median), where plain sample statistics are
    already time statistics - so evenly sampled results are exactly what they always were.

    Uneven sampling - a variable-step solver, a logging rate that changes, on-change logging - gives
    each sample half the interval to each neighbour (the midpoint rule: the mean of the curve the plot
    draws). Before A3 every sample counted once, so 1000 samples of the first second outweighed 99
    samples of the next 99 s: a mean of 9.9 where the signal was 10 for 1 s and 0 for 99 s.

    A GAP (isolated_gaps: a logger pause, a radio dropout) is time with no data, not time the two
    samples around it stood for: it counts as one regular step (the shorter neighbour). Long steps that
    follow each other (a solver's steady state) are not gaps. Returns (weights, number of gaps)."""
    t = np.asarray(t, dtype=np.float64)
    n = len(t)
    if n < 3:
        return None, 0
    d = np.diff(t)
    d = np.where(np.isfinite(d) & (d > 0), d, 0.0)
    pos = d[d > 0]
    if not len(pos):
        return None, 0
    med = float(np.median(pos))
    if bool(np.all(np.abs(d - med) <= 0.5 * med)):
        return None, 0
    gap = isolated_gaps(d, med)
    prev = np.concatenate([d[1:2], d[:-1]])
    nxt = np.concatenate([d[1:], d[-2:-1]])
    d_eff = np.where(gap, np.minimum(prev, nxt), d)
    w = np.zeros(n)
    w[:-1] += 0.5 * d_eff
    w[1:] += 0.5 * d_eff
    if not w.sum() > 0:
        return None, 0
    return w, int(gap.sum())


def _stats_of(seg: np.ndarray, w: Optional[np.ndarray]) -> Dict[str, Any]:
    vmin, vmax = float(seg.min()), float(seg.max())
    if w is None:
        mean, ms = float(seg.mean()), float(np.mean(seg * seg))
        var = float(seg.var())
    else:
        sw = float(w.sum())
        mean = float(np.dot(w, seg) / sw)
        ms = float(np.dot(w, seg * seg) / sw)
        var = float(np.dot(w, (seg - mean) ** 2) / sw)
    return {"min": vmin, "max": vmax, "mean": mean, "std": float(np.sqrt(max(var, 0.0))),
            "rms": float(np.sqrt(max(ms, 0.0))), "peak_to_peak": vmax - vmin, "samples": int(seg.size)}


def compute_signal_stats(
    time: np.ndarray,
    data: np.ndarray,
    t_start: Optional[float] = None,
    t_end: Optional[float] = None,
    mask: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Statistics for a signal (or a time region of it, or the samples where `mask` is True - e.g.
    while a state holds).

    * NaN-safe (one missing sample no longer turns every statistic into NaN)
    * mean, RMS and std are TIME statistics (A3): on uneven sampling each sample is weighted by the
      time it stands for (time_weights); then the result has "weighting": "time" (and "gaps").
      Evenly sampled signals: plain sample statistics, as before. std is the population std.
    * With a mask the weights come from the whole signal, so the stretch between two masked parts
      is never taken for a gap or bridged.
    * Region lookup with binary search on the (sorted) time vector, no boolean mask
    * Results cached per data identity, so the panels do not rescan huge arrays on every refresh
    """
    if len(data) == 0:
        return {}
    key = (id(time), id(data), len(data), t_start, t_end)
    if mask is None:
        hit = _STATS_CACHE.get(key)
        if hit is not None and hit[0]() is time and hit[1]() is data:
            return hit[2]

    i0, i1 = 0, len(time)
    if t_start is not None:
        i0 = int(np.searchsorted(time, t_start, side="left"))
    if t_end is not None:
        i1 = int(np.searchsorted(time, t_end, side="right"))
    if i1 <= i0:
        return {}
    seg = np.asarray(data[i0:i1], dtype=np.float64)
    tseg = np.asarray(time[i0:i1], dtype=np.float64)
    finite = np.isfinite(seg)
    keep = finite if mask is None else finite & np.asarray(mask[i0:i1], dtype=bool)
    if not keep.any():
        return {}
    # weights over every finite sample (NaN samples' time goes to their neighbours), then the selection
    w_all, gaps = time_weights(tseg[finite])
    w = None
    if w_all is not None:
        w_full = np.zeros(len(seg))
        w_full[finite] = w_all
        w = w_full[keep]
        if not w.sum() > 0:
            w = None
    sel = seg[keep]
    result = _stats_of(sel, w)
    tk = tseg[keep]
    result["duration"] = float(tk[-1] - tk[0]) if len(tk) > 1 else 0.0
    if w is not None:
        result["weighting"] = "time"
        result["gaps"] = gaps
    if mask is None:
        if len(_STATS_CACHE) >= _STATS_CACHE_MAX:
            _STATS_CACHE.pop(next(iter(_STATS_CACHE)))
        _STATS_CACHE.pop(key, None)
        _STATS_CACHE[key] = (_weak(time), _weak(data), result)
    return result


# =============================================================================
# O(N) NUMERIC HELPERS
# =============================================================================

def moving_average(data: np.ndarray, window: int) -> np.ndarray:
    """
    Centered moving average in O(N) using a cumulative sum.
    Replaces np.convolve(..., mode='same'), which is O(N*window) (hours for a long signal
    with a low cut-off) and returns a LONGER array when window > len(data).
    Edges use the available samples only (no zero-padding bias). NaN samples are ignored.
    """
    data = np.asarray(data, dtype=np.float64)
    n = len(data)
    if n == 0:
        return data.copy()
    window = int(max(1, min(window, n)))
    if window == 1:
        return data.copy()
    finite = np.isfinite(data)
    vals = np.where(finite, data, 0.0)
    csum = np.concatenate([[0.0], np.cumsum(vals)])
    ccnt = np.concatenate([[0], np.cumsum(finite)])
    half_l = window // 2
    half_r = window - half_l - 1
    idx = np.arange(n)
    lo = np.clip(idx - half_l, 0, n)
    hi = np.clip(idx + half_r + 1, 0, n)
    cnt = ccnt[hi] - ccnt[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (csum[hi] - csum[lo]) / cnt
    out[cnt == 0] = np.nan
    return out


def cumulative_trapezoid(time: np.ndarray, data: np.ndarray) -> np.ndarray:
    """Cumulative trapezoidal integral (starts at 0, handles non-uniform time; NaN treated as 0)."""
    t = np.asarray(time, dtype=np.float64)
    y = np.nan_to_num(np.asarray(data, dtype=np.float64), nan=0.0)
    if len(y) < 2:
        return np.zeros_like(y)
    out = np.empty_like(y)
    out[0] = 0.0
    np.cumsum(0.5 * (y[1:] + y[:-1]) * np.diff(t), out=out[1:])
    return out
