"""
Signal Viewer - Operations Engine
======================================
Unary, binary, and multi-signal operations.
Handles different time bases via alignment.
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from enum import Enum

from svcore.models import Run, DerivedSignal, parse_signal_key, DERIVED_RUN_IDX
from svcore.naming import get_derived_name


class AlignmentMethod(Enum):
    """Time base alignment method"""
    NEAREST = "nearest"      # Nearest neighbor
    LINEAR = "linear"        # Linear interpolation


class UnaryOp(Enum):
    """Unary operations (single signal)"""
    DERIVATIVE = "derivative"
    INTEGRAL = "integral"
    ABS = "abs"
    RMS = "rms"
    NORMALIZE = "normalize"
    NEGATE = "negate"
    SQRT = "sqrt"


class BinaryOp(Enum):
    """Binary operations (two signals) - uses ASCII operators for compatibility"""
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    ABS_DIFF = "|A-B|"


class MultiOp(Enum):
    """Multi-signal operations (3+ signals)"""
    NORM = "norm"        # L2 norm
    MEAN = "mean"
    MIN = "min"
    MAX = "max"
    SUM = "sum"


def apply_unary(
    runs: List[Run],
    derived: Dict[str, DerivedSignal],
    signal_key: str,
    operation: UnaryOp,
) -> Optional[DerivedSignal]:
    """
    Apply unary operation to a signal.
    
    Args:
        runs: List of runs
        derived: Dict of derived signals
        signal_key: Signal key "run_idx:signal_name"
        operation: Unary operation to apply
        
    Returns:
        DerivedSignal or None if failed
    """
    run_idx, sig_name = parse_signal_key(signal_key)
    time, data = _get_data(runs, derived, run_idx, sig_name)
    
    if len(data) == 0:
        return None
    
    try:
        if operation == UnaryOp.DERIVATIVE:
            if len(data) < 2:
                return None
            with np.errstate(divide="ignore", invalid="ignore"):
                result = np.gradient(np.asarray(data, dtype=np.float64), np.asarray(time, dtype=np.float64))
            result[~np.isfinite(result)] = np.nan  # duplicate timestamps -> NaN, not inf
        elif operation == UnaryOp.INTEGRAL:
            # cumulative trapezoid - correct for non-uniform sampling, starts at 0
            result = cumulative_trapezoid(time, data)
        elif operation == UnaryOp.ABS:
            result = np.abs(data)
        elif operation == UnaryOp.RMS:
            # Running RMS (window of 10 samples)
            window = min(10, len(data))
            result = np.sqrt(np.maximum(moving_average(np.asarray(data, dtype=np.float64) ** 2, window), 0.0))
        elif operation == UnaryOp.NORMALIZE:
            data_min, data_max = np.nanmin(data), np.nanmax(data)
            if np.isfinite(data_min) and data_max > data_min:
                result = (data - data_min) / (data_max - data_min)
            else:
                result = np.zeros_like(data)
        elif operation == UnaryOp.NEGATE:
            result = -data
        elif operation == UnaryOp.SQRT:
            result = np.sqrt(np.abs(data))
        else:
            return None
        
        name = get_derived_name(operation.value, sig_name)
        return DerivedSignal(
            name=name,
            time=time.copy(),
            data=result,
            operation=operation.value,
            source_signals=[signal_key],
        )
        
    except Exception as e:
        print(f"[ERROR] Unary operation failed: {e}")
        return None


def apply_binary(
    runs: List[Run],
    derived: Dict[str, DerivedSignal],
    signal_a: str,
    signal_b: str,
    operation: BinaryOp,
    alignment: AlignmentMethod = AlignmentMethod.LINEAR,
) -> Optional[DerivedSignal]:
    """
    Apply binary operation to two signals.
    
    Args:
        runs: List of runs
        derived: Dict of derived signals
        signal_a: First signal key
        signal_b: Second signal key
        operation: Binary operation
        alignment: Alignment method for different time bases
        
    Returns:
        DerivedSignal or None if failed
    """
    run_a, name_a = parse_signal_key(signal_a)
    run_b, name_b = parse_signal_key(signal_b)
    
    time_a, data_a = _get_data(runs, derived, run_a, name_a)
    time_b, data_b = _get_data(runs, derived, run_b, name_b)
    
    if len(data_a) == 0 or len(data_b) == 0:
        return None
    
    try:
        # Align to common time base
        time_out, data_a_aligned, data_b_aligned = _align_signals(
            time_a, data_a, time_b, data_b, alignment
        )
        
        if operation == BinaryOp.ADD:
            result = data_a_aligned + data_b_aligned
        elif operation == BinaryOp.SUB:
            result = data_a_aligned - data_b_aligned
        elif operation == BinaryOp.MUL:
            result = data_a_aligned * data_b_aligned
        elif operation == BinaryOp.DIV:
            # division by zero -> NaN (gap), not a fake 0 value
            a_f = np.asarray(data_a_aligned, dtype=np.float64)
            b_f = np.asarray(data_b_aligned, dtype=np.float64)
            result = np.divide(a_f, b_f, where=b_f != 0, out=np.full_like(a_f, np.nan))
        elif operation == BinaryOp.ABS_DIFF:
            result = np.abs(data_a_aligned - data_b_aligned)
        else:
            return None
        
        name = get_derived_name(operation.value, name_a, name_b)
        return DerivedSignal(
            name=name,
            time=time_out,
            data=result,
            operation=operation.value,
            source_signals=[signal_a, signal_b],
        )
        
    except Exception as e:
        print(f"[ERROR] Binary operation failed: {e}")
        return None


def apply_multi(
    runs: List[Run],
    derived: Dict[str, DerivedSignal],
    signal_keys: List[str],
    operation: MultiOp,
    alignment: AlignmentMethod = AlignmentMethod.LINEAR,
) -> Optional[DerivedSignal]:
    """
    Apply multi-signal operation.
    
    Args:
        runs: List of runs
        derived: Dict of derived signals
        signal_keys: List of signal keys
        operation: Multi-signal operation
        alignment: Alignment method
        
    Returns:
        DerivedSignal or None if failed
    """
    if len(signal_keys) < 2:
        return None
    
    try:
        # Get all data
        all_data = []
        all_names = []
        base_time = None
        
        for key in signal_keys:
            run_idx, sig_name = parse_signal_key(key)
            time, data = _get_data(runs, derived, run_idx, sig_name)
            
            if len(data) == 0:
                continue
            
            if base_time is None:
                base_time = time
                all_data.append(data)
            else:
                # Align to base time
                if alignment == AlignmentMethod.NEAREST:
                    all_data.append(np.asarray(data)[nearest_indices(time, base_time)])
                else:
                    all_data.append(np.interp(base_time, time, data))
            
            all_names.append(sig_name)
        
        if len(all_data) < 2 or base_time is None:
            return None
        
        data_matrix = np.array(all_data)
        
        if operation == MultiOp.NORM:
            result = np.sqrt(np.sum(data_matrix**2, axis=0))
        elif operation == MultiOp.MEAN:
            result = np.mean(data_matrix, axis=0)
        elif operation == MultiOp.MIN:
            result = np.min(data_matrix, axis=0)
        elif operation == MultiOp.MAX:
            result = np.max(data_matrix, axis=0)
        elif operation == MultiOp.SUM:
            result = np.sum(data_matrix, axis=0)
        else:
            return None
        
        name = get_derived_name(operation.value, *all_names)
        return DerivedSignal(
            name=name,
            time=base_time,
            data=result,
            operation=operation.value,
            source_signals=signal_keys,
        )
        
    except Exception as e:
        print(f"[ERROR] Multi operation failed: {e}")
        return None


def _get_data(
    runs: List[Run],
    derived: Dict[str, DerivedSignal],
    run_idx: int,
    sig_name: str,
) -> Tuple[np.ndarray, np.ndarray]:
    """Get signal data from runs or derived"""
    if run_idx == DERIVED_RUN_IDX:
        if sig_name in derived:
            ds = derived[sig_name]
            return ds.time, ds.data
        return np.array([]), np.array([])
    
    if 0 <= run_idx < len(runs):
        return runs[run_idx].get_signal_data(sig_name)
    
    return np.array([]), np.array([])


def nearest_indices(t_src: np.ndarray, t_query: np.ndarray) -> np.ndarray:
    """Index of the truly NEAREST sample in sorted t_src for each query time
    (np.searchsorted alone returns the next sample, i.e. up to one full step off)."""
    t_src = np.asarray(t_src)
    n = len(t_src)
    idx = np.clip(np.searchsorted(t_src, t_query), 0, n - 1)
    left = np.clip(idx - 1, 0, n - 1)
    use_left = np.abs(t_src[left] - t_query) <= np.abs(t_src[idx] - t_query)
    return np.where(use_left, left, idx)


def _align_signals(
    time_a: np.ndarray,
    data_a: np.ndarray,
    time_b: np.ndarray,
    data_b: np.ndarray,
    method: AlignmentMethod,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Align two signals to common time base"""
    # Use the denser time base
    if len(time_a) >= len(time_b):
        base_time = time_a
        a_aligned = data_a
        if method == AlignmentMethod.NEAREST:
            b_aligned = np.asarray(data_b)[nearest_indices(time_b, base_time)]
        else:
            b_aligned = np.interp(base_time, time_b, data_b)
    else:
        base_time = time_b
        b_aligned = data_b
        if method == AlignmentMethod.NEAREST:
            a_aligned = np.asarray(data_a)[nearest_indices(time_a, base_time)]
        else:
            a_aligned = np.interp(base_time, time_a, data_a)
    
    return base_time, a_aligned, b_aligned


def align_two_signals(
    t_ref: np.ndarray,
    y_ref: np.ndarray,
    t_other: np.ndarray,
    y_other: np.ndarray,
    method: str = "linear",
) -> Tuple[np.ndarray, np.ndarray, bool]:
    """
    Align one signal to another's time base for X-Y plotting.
    
    This is used for X-Y mode where X signal provides the reference time base
    and Y signals need to be interpolated to match.
    
    Args:
        t_ref: Reference time vector (X signal's time)
        y_ref: Reference data vector (X signal's values - becomes X axis)
        t_other: Other signal's time vector
        y_other: Other signal's data vector (becomes Y axis after alignment)
        method: "linear" or "nearest"
        
    Returns:
        Tuple of (y_other_aligned, has_overlap: bool)
        - y_other_aligned: Y signal interpolated onto t_ref's time base
        - has_overlap: True if there was sufficient time overlap
    """
    if len(t_ref) == 0 or len(t_other) == 0:
        return np.array([]), False
    
    # Check for time overlap
    t_min = max(t_ref.min(), t_other.min())
    t_max = min(t_ref.max(), t_other.max())
    
    if t_max <= t_min:
        # No overlap
        return np.array([]), False
    
    # Create mask for overlapping region in reference time
    overlap_mask = (t_ref >= t_min) & (t_ref <= t_max)
    t_overlap = t_ref[overlap_mask]
    
    if len(t_overlap) < 2:
        return np.array([]), False
    
    try:
        if method == "nearest":
            # Nearest neighbor
            y_aligned = np.asarray(y_other)[nearest_indices(t_other, t_overlap)]
        else:
            # Linear interpolation (default)
            y_aligned = np.interp(t_overlap, t_other, y_other)
        
        # Return full-length arrays matching t_ref (NaN outside overlap)
        result = np.full(len(t_ref), np.nan)
        result[overlap_mask] = y_aligned
        
        return result, True
        
    except Exception as e:
        print(f"[ALIGN] Alignment failed: {e}", flush=True)
        return np.array([]), False


def get_xy_plot_data(
    runs: List[Run],
    derived: Dict[str, DerivedSignal],
    x_signal_key: str,
    y_signal_keys: List[str],
    alignment_method: str = "linear",
) -> List[Tuple[str, np.ndarray, np.ndarray, str]]:
    """
    Prepare X-Y plot data by aligning Y signals to X signal's time base.
    
    Args:
        runs: List of runs
        derived: Dict of derived signals
        x_signal_key: Signal key for X axis
        y_signal_keys: List of signal keys for Y axes
        alignment_method: "linear" or "nearest"
        
    Returns:
        List of (label, x_data, y_data, error_msg) tuples
        error_msg is empty if successful
    """
    results = []
    
    # Get X signal data
    x_run_idx, x_name = parse_signal_key(x_signal_key)
    t_x, data_x = _get_data(runs, derived, x_run_idx, x_name)
    
    if len(t_x) == 0:
        return [(x_name, np.array([]), np.array([]), "X signal has no data")]
    
    # For each Y signal, align to X's time base
    for y_key in y_signal_keys:
        if y_key == x_signal_key:
            continue  # Skip if Y is same as X
        
        y_run_idx, y_name = parse_signal_key(y_key)
        t_y, data_y = _get_data(runs, derived, y_run_idx, y_name)
        
        if len(t_y) == 0:
            results.append((y_name, np.array([]), np.array([]), "Y signal has no data"))
            continue
        
        # Align Y to X's time base
        y_aligned, has_overlap = align_two_signals(t_x, data_x, t_y, data_y, alignment_method)
        
        if not has_overlap:
            results.append((y_name, np.array([]), np.array([]), "No time overlap between X and Y"))
            continue
        
        # X values are the X signal's data (at overlapping times)
        valid_mask = ~np.isnan(y_aligned)
        x_values = data_x[valid_mask] if len(data_x) == len(y_aligned) else data_x
        y_values = y_aligned[valid_mask]
        
        results.append((y_name, x_values, y_values, ""))
    
    return results


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


def compute_psd(
    time: np.ndarray,
    data: np.ndarray,
    window: str = "hanning"
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute Power Spectral Density of signal.
    
    Args:
        time: Time array
        data: Signal data
        window: Window function
        
    Returns:
        (frequencies, psd) arrays
    """
    freqs, mags = compute_fft(time, data, window)
    if len(freqs) == 0:
        return freqs, mags
    
    # PSD is magnitude squared
    psd = mags ** 2
    return freqs, psd


# =============================================================================
# SIGNAL FILTERING
# =============================================================================

def apply_filter(
    time: np.ndarray,
    data: np.ndarray,
    filter_type: str,
    cutoff: float,
    order: int = 4
) -> np.ndarray:
    """
    Apply digital filter to signal.
    
    Args:
        time: Time array (used to determine sampling frequency)
        data: Signal data
        filter_type: "lowpass", "highpass", "bandpass", "bandstop"
        cutoff: Cutoff frequency (Hz) or [low, high] for bandpass/bandstop
        order: Filter order (default 4)
        
    Returns:
        Filtered data array
    """
    if len(data) < order * 3:
        return data  # Not enough data for filtering
    
    # Calculate sampling frequency
    dt = (float(time[-1]) - float(time[0])) / (len(time) - 1)
    if not np.isfinite(dt) or dt <= 0:
        return data
    
    fs = 1.0 / dt
    nyq = fs / 2.0
    
    # Normalize cutoff to Nyquist frequency
    if isinstance(cutoff, (list, tuple)):
        # Bandpass/bandstop
        wn = [c / nyq for c in cutoff]
        wn = [max(0.001, min(0.999, w)) for w in wn]
    else:
        wn = cutoff / nyq
        wn = max(0.001, min(0.999, wn))
    
    try:
        # Use simple IIR filter (Butterworth)
        # Implement manually to avoid scipy dependency
        # For now, use moving average as fallback
        if filter_type == "lowpass":
            # Simple low-pass: moving average
            window_size = max(3, int(fs / (cutoff * 2)))
            filtered = moving_average(data, window_size)
        elif filter_type == "highpass":
            # High-pass: original minus low-pass
            window_size = max(3, int(fs / (cutoff * 2)))
            filtered = data - moving_average(data, window_size)
        elif filter_type == "moving_avg":
            # Simple moving average
            window_size = max(3, int(cutoff))  # cutoff as window size
            filtered = moving_average(data, window_size)
        else:
            filtered = data
        
        return filtered
        
    except Exception:
        return data


def create_filtered_signal(
    runs: List[Run],
    derived: Dict[str, DerivedSignal],
    signal_key: str,
    filter_type: str,
    cutoff: float,
) -> Optional[DerivedSignal]:
    """
    Create a filtered version of a signal.
    
    Args:
        runs: List of runs
        derived: Dict of derived signals
        signal_key: Signal to filter
        filter_type: Filter type
        cutoff: Cutoff frequency or window size
        
    Returns:
        DerivedSignal with filtered data
    """
    run_idx, sig_name = parse_signal_key(signal_key)
    time, data = _get_data(runs, derived, run_idx, sig_name)
    
    if len(data) == 0:
        return None
    
    filtered = apply_filter(time, data, filter_type, cutoff)
    
    name = get_derived_name(f"{filter_type}_{cutoff:.1f}Hz", sig_name)
    return DerivedSignal(
        name=name,
        time=time.copy(),
        data=filtered,
        operation=f"{filter_type}(cutoff={cutoff})",
        source_signals=[signal_key],
    )


# =============================================================================
# SIGNAL STATISTICS
# =============================================================================

_STATS_CACHE: Dict[tuple, Dict[str, float]] = {}
_STATS_CACHE_MAX = 256


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
    if hit is not None:
        return hit

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
    _STATS_CACHE[key] = result
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
