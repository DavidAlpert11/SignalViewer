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

def compute_welch(time: np.ndarray, data: np.ndarray, window: str = "hanning") -> Tuple[np.ndarray, np.ndarray]:
    """Welch power spectral density (units^2/Hz): the recording is cut into overlapping pieces
    whose spectra are averaged - much less noisy than one FFT, the usual view for vibration.
    Same preparation as compute_fft (mean sample interval, gaps filled, mean removed)."""
    from scipy.signal import welch
    n = len(data)
    if n < 16:
        return np.array([]), np.array([])
    dt = (float(time[-1]) - float(time[0])) / (n - 1)
    if not np.isfinite(dt) or dt <= 0:
        return np.array([]), np.array([])
    data = np.asarray(data, dtype=np.float64)
    finite = np.isfinite(data)
    if not finite.all():
        if not finite.any():
            return np.array([]), np.array([])
        idx = np.arange(n)
        data = np.interp(idx, idx[finite], data[finite])
    # about 8 pieces (50 % overlap -> ~15 averages), a power of two, at least 256 samples
    nperseg = int(min(n, max(256, 2 ** int(np.floor(np.log2(max(n / 8, 1)))))))
    win = {"hanning": "hann", "hamming": "hamming", "blackman": "blackman"}.get(window, "boxcar")
    f, p = welch(data, fs=1.0 / dt, window=win, nperseg=nperseg, detrend="constant", scaling="density")
    return f, p


def compute_fft(
    time: np.ndarray,
    data: np.ndarray,
    window: str = "hanning"
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute FFT of signal.
    
    Args:
        time: Time array
        data: Signal data
        window: Window function ("hanning", "hamming", "blackman", "none")
        
    Returns:
        (frequencies, magnitudes) arrays
    """
    if len(data) < 2:
        return np.array([]), np.array([])
    
    # Calculate sampling interval from time array (mean dt, O(1) memory)
    n = len(data)
    dt = (float(time[-1]) - float(time[0])) / (n - 1)
    if not np.isfinite(dt) or dt <= 0:
        return np.array([]), np.array([])
    
    data = np.asarray(data, dtype=np.float64)
    finite = np.isfinite(data)
    if not finite.all():
        if not finite.any():
            return np.array([]), np.array([])
        # fill NaN gaps by linear interpolation (one NaN would otherwise poison the whole FFT)
        idx = np.arange(n)
        data = np.interp(idx, idx[finite], data[finite])
    
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


def apply_filter(time: np.ndarray, data: np.ndarray, filter_type: str, cutoff: float,
                 order: int = 4) -> np.ndarray:
    """Butterworth low-pass / high-pass, run forward and backward (zero phase: no delay, so a
    filtered step stays where the raw step is). The sample rate is the median sample interval,
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
    nyq = 0.5 / float(np.median(steps))
    cutoff = float(cutoff)
    if not (0 < cutoff < nyq):
        raise FilterError(f"The cut-off ({cutoff:g} Hz) must be above 0 and below half the sample "
                          f"rate ({nyq:.6g} Hz).")
    ok = np.isfinite(y)
    if ok.sum() < 2:
        return np.full(n, np.nan)
    filled = y if ok.all() else np.interp(np.arange(n), np.flatnonzero(ok), y[ok])
    sos = butter(int(order), cutoff / nyq, btype=filter_type, output="sos")
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


def compute_signal_stats(
    time: np.ndarray,
    data: np.ndarray,
    t_start: Optional[float] = None,
    t_end: Optional[float] = None,
) -> Dict[str, float]:
    """
    Statistics for a signal (or a time region of it).

    * NaN-safe (one missing sample no longer turns every statistic into NaN)
    * Region lookup with binary search on the (sorted) time vector, no boolean mask
    * Results cached per data identity, so the panels do not rescan huge arrays on every refresh
    """
    if len(data) == 0:
        return {}
    key = (id(time), id(data), len(data), t_start, t_end)
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
    finite = np.isfinite(seg)
    if not finite.all():
        seg = seg[finite]
    if seg.size == 0:
        return {}

    vmin, vmax = float(seg.min()), float(seg.max())
    result = {
        "min": vmin,
        "max": vmax,
        "mean": float(seg.mean()),
        "std": float(seg.std()),
        "rms": float(np.sqrt(np.mean(seg * seg))),
        "peak_to_peak": vmax - vmin,
        "samples": int(seg.size),
        "duration": float(time[i1 - 1] - time[i0]) if i1 - i0 > 1 else 0.0,
    }
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
