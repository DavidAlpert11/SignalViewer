"""
Utility functions for Signal Viewer Pro
Enhanced with advanced algorithms
"""

import numpy as np
import pandas as pd
from typing import Tuple, List, Optional


def downsample_lttb(
    x_data: np.ndarray, y_data: np.ndarray, max_points: int
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Largest Triangle Three Buckets (LTTB) downsampling
    Better preserves visual appearance than simple decimation
    """
    n = len(x_data)
    if n <= max_points:
        return x_data, y_data

    if max_points < 3:
        max_points = 3

    # Output arrays
    out_x = np.zeros(max_points)
    out_y = np.zeros(max_points)

    # Always keep first and last
    out_x[0] = x_data[0]
    out_y[0] = y_data[0]
    out_x[-1] = x_data[-1]
    out_y[-1] = y_data[-1]

    # Bucket size
    bucket_size = (n - 2) / (max_points - 2)

    a = 0
    for i in range(1, max_points - 1):
        # Calculate point average for next bucket
        avg_range_start = int(np.floor((i + 1) * bucket_size) + 1)
        avg_range_end = int(np.floor((i + 2) * bucket_size) + 1)
        avg_range_end = min(avg_range_end, n)

        avg_x = np.mean(x_data[avg_range_start:avg_range_end])
        avg_y = np.mean(y_data[avg_range_start:avg_range_end])

        # Get range for this bucket
        range_offs = int(np.floor(i * bucket_size) + 1)
        range_to = int(np.floor((i + 1) * bucket_size) + 1)

        point_a_x = x_data[a]
        point_a_y = y_data[a]

        # Find point with largest triangle area
        areas = (
            np.abs(
                (point_a_x - avg_x) * (y_data[range_offs:range_to] - point_a_y)
                - (point_a_x - x_data[range_offs:range_to]) * (avg_y - point_a_y)
            )
            * 0.5
        )

        max_area_idx = np.argmax(areas) + range_offs

        out_x[i] = x_data[max_area_idx]
        out_y[i] = y_data[max_area_idx]
        a = max_area_idx

    return out_x, out_y


def downsample_minmax(
    x_data: np.ndarray, y_data: np.ndarray, max_points: int
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Min-Max downsampling - preserves peaks and valleys
    Fast and good for oscillating signals
    """
    n = len(x_data)
    if n <= max_points:
        return x_data, y_data

    if max_points < 3:
        max_points = 3

    # Number of bins
    interior_points = max_points - 2
    bins = max(1, interior_points // 2)

    indices = np.linspace(1, n - 1, bins + 1, dtype=int)

    out_x = [x_data[0]]
    out_y = [y_data[0]]

    for i in range(len(indices) - 1):
        s = indices[i]
        e = indices[i + 1]
        if e <= s:
            continue

        seg_y = y_data[s:e]
        local_min_i = np.argmin(seg_y) + s
        local_max_i = np.argmax(seg_y) + s

        # Add in order of occurrence
        if local_min_i < local_max_i:
            out_x.extend([x_data[local_min_i], x_data[local_max_i]])
            out_y.extend([y_data[local_min_i], y_data[local_max_i]])
        else:
            out_x.extend([x_data[local_max_i], x_data[local_min_i]])
            out_y.extend([y_data[local_max_i], y_data[local_min_i]])

    out_x.append(x_data[-1])
    out_y.append(y_data[-1])

    # Limit to max_points if we exceeded
    if len(out_x) > max_points:
        indices = np.linspace(0, len(out_x) - 1, max_points, dtype=int)
        out_x = [out_x[i] for i in indices]
        out_y = [out_y[i] for i in indices]

    return np.array(out_x), np.array(out_y)


def downsample_data(
    x_data: np.ndarray, y_data: np.ndarray, max_points: int, method: str = "lttb"
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Downsample data using specified method

    Args:
        x_data: X axis data
        y_data: Y axis data
        max_points: Maximum number of points to return
        method: 'lttb', 'minmax', or 'simple'

    Returns:
        Downsampled (x, y) arrays
    """
    n = len(x_data)
    if n <= max_points:
        return x_data, y_data

    if method == "lttb":
        return downsample_lttb(x_data, y_data, max_points)
    elif method == "minmax":
        return downsample_minmax(x_data, y_data, max_points)
    else:
        # Simple decimation
        dec_factor = max(1, n // max_points)
        indices = list(range(0, n, dec_factor))
        if indices[-1] != n - 1:
            indices.append(n - 1)
        return x_data[indices], y_data[indices]


def validate_csv_format(df: pd.DataFrame) -> bool:
    """Validate CSV format"""
    try:
        if df.empty:
            return False

        # Check for Time column
        if "Time" not in df.columns and len(df.columns) > 0:
            return False

        # Check for numeric data
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) < 2:  # At least Time + one signal
            return False

        return True
    except Exception:
        return False


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_signal_statistics(time_data: np.ndarray, signal_data: np.ndarray) -> dict:
    """Calculate comprehensive signal statistics"""
    if len(signal_data) == 0:
        return {}

    valid_mask = ~np.isnan(signal_data)
    valid_data = signal_data[valid_mask]

    if len(valid_data) == 0:
        return {}

    stats = {
        "mean": float(np.mean(valid_data)),
        "std": float(np.std(valid_data)),
        "min": float(np.min(valid_data)),
        "max": float(np.max(valid_data)),
        "rms": float(np.sqrt(np.mean(valid_data**2))),
        "median": float(np.median(valid_data)),
        "count": int(len(valid_data)),
        "range": float(np.ptp(valid_data)),
    }

    # Add percentiles
    stats["p25"] = float(np.percentile(valid_data, 25))
    stats["p75"] = float(np.percentile(valid_data, 75))
    stats["p95"] = float(np.percentile(valid_data, 95))

    if len(time_data) > 1 and len(time_data) == len(signal_data):
        valid_time = time_data[valid_mask]
        dt = np.diff(valid_time)
        if len(dt) > 0 and np.mean(dt) > 0:
            stats["sample_rate"] = float(1.0 / np.mean(dt))
            stats["duration"] = float(valid_time[-1] - valid_time[0])

    return stats


def detect_signal_type(signal_data: np.ndarray) -> str:
    """
    Detect signal type based on characteristics
    Returns: 'continuous', 'discrete', 'binary', or 'unknown'
    """
    if len(signal_data) == 0:
        return "unknown"

    valid_data = signal_data[~np.isnan(signal_data)]
    if len(valid_data) == 0:
        return "unknown"

    unique_vals = np.unique(valid_data)

    # Binary signal
    if len(unique_vals) == 2:
        return "binary"

    # Discrete signal (few unique values)
    if len(unique_vals) < 20:
        return "discrete"

    return "continuous"


def rgb_to_plotly_color(rgb_tuple: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to Plotly color string"""
    return f"rgb({rgb_tuple[0]}, {rgb_tuple[1]}, {rgb_tuple[2]})"


def plotly_color_to_rgb(color_str: str) -> Tuple[int, int, int]:
    """Convert Plotly color string to RGB tuple"""
    if color_str.startswith("rgb("):
        rgb_str = color_str[4:-1]
        return tuple(map(int, rgb_str.split(",")))
    return (0, 0, 0)


def estimate_memory_usage(
    n_signals: int, n_points: int, bytes_per_point: int = 8
) -> str:
    """Estimate memory usage for signals"""
    total_bytes = n_signals * n_points * bytes_per_point
    return format_file_size(total_bytes)


def find_peaks(
    signal_data: np.ndarray, threshold: Optional[float] = None
) -> np.ndarray:
    """
    Simple peak detection
    Returns indices of peaks
    """
    if len(signal_data) < 3:
        return np.array([])

    # Find local maxima
    peaks = []
    for i in range(1, len(signal_data) - 1):
        if signal_data[i] > signal_data[i - 1] and signal_data[i] > signal_data[i + 1]:
            if threshold is None or signal_data[i] > threshold:
                peaks.append(i)

    return np.array(peaks)


def smooth_signal(
    signal_data: np.ndarray, window_size: int = 5, method: str = "moving_average"
) -> np.ndarray:
    """
    Smooth signal using various methods

    Args:
        signal_data: Input signal
        window_size: Window size for smoothing
        method: 'moving_average', 'gaussian', or 'median'

    Returns:
        Smoothed signal
    """
    if window_size < 2:
        return signal_data

    if method == "moving_average":
        kernel = np.ones(window_size) / window_size
        return np.convolve(signal_data, kernel, mode="same")

    elif method == "median":
        # Simple median filter
        output = np.copy(signal_data)
        half_window = window_size // 2
        for i in range(half_window, len(signal_data) - half_window):
            output[i] = np.median(signal_data[i - half_window : i + half_window + 1])
        return output

    elif method == "gaussian":
        # Gaussian kernel
        sigma = window_size / 6.0
        x = np.arange(-window_size // 2, window_size // 2 + 1)
        kernel = np.exp(-0.5 * (x / sigma) ** 2)
        kernel = kernel / np.sum(kernel)
        return np.convolve(signal_data, kernel, mode="same")

    else:
        return signal_data


def align_signals_by_time(
    time1: np.ndarray,
    data1: np.ndarray,
    time2: np.ndarray,
    data2: np.ndarray,
    method: str = "linear",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Align two signals to common time base via interpolation

    Returns:
        (common_time, data1_aligned, data2_aligned)
    """
    # Find overlapping time range
    t_start = max(time1.min(), time2.min())
    t_end = min(time1.max(), time2.max())

    if t_start >= t_end:
        return np.array([]), np.array([]), np.array([])

    # Create common time vector
    n_points = min(len(time1), len(time2), 10000)
    common_time = np.linspace(t_start, t_end, n_points)

    # Interpolate both signals
    data1_aligned = np.interp(common_time, time1, data1)
    data2_aligned = np.interp(common_time, time2, data2)

    return common_time, data1_aligned, data2_aligned


def compute_correlation(data1: np.ndarray, data2: np.ndarray) -> Optional[float]:
    """
    Compute correlation coefficient between two signals
    Returns None if computation fails
    """
    try:
        if len(data1) != len(data2) or len(data1) < 2:
            return None

        # Remove NaN
        valid = ~(np.isnan(data1) | np.isnan(data2))
        if np.sum(valid) < 2:
            return None

        d1 = data1[valid]
        d2 = data2[valid]

        # Check for zero variance
        if np.std(d1) == 0 or np.std(d2) == 0:
            return None

        corr_matrix = np.corrcoef(d1, d2)
        corr = float(corr_matrix[0, 1])

        if np.isnan(corr) or np.isinf(corr):
            return None

        return corr

    except Exception:
        return None
