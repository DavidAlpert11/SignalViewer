"""
Signal Viewer Pro - Helper Functions
=====================================
Utility functions used across the application.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np
import pandas as pd

from config import DERIVED_CSV_IDX, TIME_COLUMN

# Configure logging
logger = logging.getLogger("SignalViewer")


def get_csv_display_name(filepath: str, all_paths: List[str]) -> str:
    """
    Get display name for a CSV file, including parent folder if filename is duplicate.

    Args:
        filepath: Full path to the CSV file
        all_paths: List of all CSV paths to check for duplicates

    Returns:
        Display name (either basename or parent/basename if duplicate)
    """
    basename = os.path.basename(filepath)
    basenames = [os.path.basename(p) for p in all_paths]

    if basenames.count(basename) > 1:
        parent = os.path.basename(os.path.dirname(filepath))
        return f"{parent}/{basename}" if parent else basename
    return basename


def get_csv_short_name(filepath: str) -> str:
    """Get short name (filename without extension) for CSV file."""
    return os.path.splitext(os.path.basename(filepath))[0]


def parse_signal_key(key: str) -> Tuple[int, str]:
    """
    Parse a signal key into csv_idx and signal_name.

    Args:
        key: Signal key in format "csv_idx:signal_name"

    Returns:
        Tuple of (csv_idx, signal_name)
    """
    parts = key.split(":", 1)
    if len(parts) == 2:
        return int(parts[0]), parts[1]
    return -1, key


def make_signal_key(csv_idx: int, signal_name: str) -> str:
    """Create a signal key from csv_idx and signal_name."""
    return f"{csv_idx}:{signal_name}"


def get_signal_label(
    csv_idx: int,
    signal_name: str,
    csv_paths: List[str],
    display_name: Optional[str] = None,
) -> str:
    """
    Get display label for a signal.
    Includes folder info when CSVs have duplicate filenames.

    Args:
        csv_idx: Index of CSV file (-1 for derived signals)
        signal_name: Name of the signal
        csv_paths: List of CSV file paths
        display_name: Optional custom display name

    Returns:
        Formatted label like "signal_name (csv_name)" or "signal_name (folder/csv_name)"
    """
    name = display_name or signal_name

    if csv_idx == DERIVED_CSV_IDX:
        return f"{name} (D)"

    if 0 <= csv_idx < len(csv_paths):
        # Use get_csv_display_name which includes parent folder for duplicates
        csv_display = get_csv_display_name(csv_paths[csv_idx], csv_paths)
        # Remove extension for cleaner display
        csv_display = os.path.splitext(csv_display)[0]
        return f"{name} ({csv_display})"

    return f"{name} (C{csv_idx + 1})"


def interpolate_value_at_x(
    x_data: np.ndarray, y_data: np.ndarray, target_x: float
) -> Optional[float]:
    """
    Interpolate signal value at a specific x position.

    Args:
        x_data: X axis data (typically time)
        y_data: Y axis data (signal values)
        target_x: X position to interpolate at

    Returns:
        Interpolated value or None if interpolation fails
    """
    try:
        if len(x_data) == 0 or len(y_data) == 0:
            return None
        return float(np.interp(target_x, x_data, y_data))
    except Exception:
        return None


def safe_json_parse(json_string: str) -> Optional[Dict]:
    """Safely parse JSON string, returning None on failure."""
    import json

    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return None


def get_assignment_signals(
    assignment: Union[List, Dict], mode: str = "time"
) -> List[Dict[str, Any]]:
    """
    Extract list of signals from an assignment (handles both time and xy modes).

    Args:
        assignment: Assignment data (list for time mode, dict for xy mode)
        mode: Plot mode ("time" or "xy")

    Returns:
        List of signal info dicts with csv_idx and signal keys
    """
    if mode == "xy" and isinstance(assignment, dict):
        signals = []
        for axis in ["x", "y"]:
            if assignment.get(axis):
                signals.append(assignment[axis])
        return signals

    if isinstance(assignment, list):
        return assignment

    return []


def is_signal_assigned(
    csv_idx: int, signal_name: str, assignment: Union[List, Dict], mode: str = "time"
) -> bool:
    """
    Check if a signal is assigned to a subplot.

    Args:
        csv_idx: CSV index
        signal_name: Signal name
        assignment: Assignment data
        mode: Plot mode

    Returns:
        True if signal is assigned
    """
    key = make_signal_key(csv_idx, signal_name)
    signals = get_assignment_signals(assignment, mode)

    for sig in signals:
        if make_signal_key(sig.get("csv_idx", -999), sig.get("signal", "")) == key:
            return True
    return False


def calculate_derived_signal(
    operation: str, time_data: np.ndarray, signal_data: np.ndarray
) -> np.ndarray:
    """
    Calculate derived signal based on operation type.

    Args:
        operation: Operation type (derivative, integral, abs, sqrt, negate)
        time_data: Time array
        signal_data: Signal data array

    Returns:
        Computed result array
    """
    if operation == "derivative":
        return np.gradient(signal_data, time_data)
    elif operation == "integral":
        dt = np.mean(np.diff(time_data)) if len(time_data) > 1 else 1.0
        return np.cumsum(signal_data) * dt
    elif operation == "abs":
        return np.abs(signal_data)
    elif operation == "sqrt":
        return np.sqrt(np.abs(signal_data))
    elif operation == "negate":
        return -signal_data
    else:
        return signal_data


def calculate_multi_signal_operation(
    operation: str, signals_data: List[np.ndarray]
) -> np.ndarray:
    """
    Calculate operation on multiple signals.

    Args:
        operation: Operation type (add, sub, mul, div, norm, mean)
        signals_data: List of signal data arrays (already aligned)

    Returns:
        Computed result array
    """
    if len(signals_data) < 2:
        return signals_data[0] if signals_data else np.array([])

    a, b = np.array(signals_data[0]), np.array(signals_data[1])

    if operation == "add":
        return a + b
    elif operation == "sub":
        return a - b
    elif operation == "mul":
        return a * b
    elif operation == "div":
        return np.divide(a, b, where=b != 0, out=np.zeros_like(a, dtype=float))
    elif operation == "norm":
        return np.sqrt(sum(np.array(s) ** 2 for s in signals_data))
    elif operation == "mean":
        return np.mean(signals_data, axis=0)
    else:
        return a


def clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp value between min and max."""
    return max(min_val, min(max_val, value))


def format_cursor_value(value: float, precision: int = 4) -> str:
    """Format a cursor value for display."""
    return f"{value:.{precision}f}"


class PlotDataCollector:
    """Helper class to collect signal data for plotting."""

    def __init__(self):
        self.traces: List[Dict] = []
        self.color_idx: int = 0
        self.trace_idx: int = 0

    def add_trace(
        self,
        x_data: np.ndarray,
        y_data: np.ndarray,
        name: str,
        color: str,
        subplot_idx: int,
        **kwargs,
    ) -> None:
        """Add a trace to the collection."""
        self.traces.append(
            {
                "x_data": x_data,
                "y_data": y_data,
                "name": name,
                "color": color,
                "subplot_idx": subplot_idx,
                "trace_idx": self.trace_idx,
                **kwargs,
            }
        )
        self.trace_idx += 1
        self.color_idx += 1

    def get_traces_for_subplot(self, subplot_idx: int) -> List[Dict]:
        """Get all traces for a specific subplot."""
        return [t for t in self.traces if t["subplot_idx"] == subplot_idx]


def contains_hebrew(text: str) -> bool:
    """
    Detect if text contains Hebrew characters.

    Args:
        text: Text to check

    Returns:
        True if text contains Hebrew characters, False otherwise
    """
    if not text:
        return False
    # Hebrew Unicode range: U+0590 to U+05FF
    hebrew_range = range(0x0590, 0x0600)
    return any(ord(char) in hebrew_range for char in text)


def get_text_direction_style(text: str) -> str:
    """
    Get CSS direction style based on text content.

    Args:
        text: Text to analyze

    Returns:
        CSS style string with direction and text-align properties
    """
    if contains_hebrew(text):
        return "direction: rtl !important; text-align: right !important; unicode-bidi: embed !important;"
    return "direction: ltr !important; text-align: left !important; unicode-bidi: embed !important;"


def get_text_direction_attr(text: str) -> str:
    """
    Get HTML dir attribute based on text content.

    Args:
        text: Text to analyze

    Returns:
        'rtl' for Hebrew text, 'ltr' for others
    """
    return "rtl" if contains_hebrew(text) else "ltr"


# =============================================================================
# Signal Comparison Functions
# =============================================================================

def compare_signals(
    time1: np.ndarray, 
    data1: np.ndarray, 
    time2: np.ndarray, 
    data2: np.ndarray,
    interpolate: bool = True
) -> Dict[str, Any]:
    """
    Compare two signals and compute difference metrics.
    
    Args:
        time1, data1: First signal (time, values)
        time2, data2: Second signal (time, values)
        interpolate: If True, interpolate to common time base
    
    Returns:
        Dict with comparison metrics:
        - correlation: Pearson correlation coefficient
        - rmse: Root mean square error
        - mae: Mean absolute error  
        - max_diff: Maximum absolute difference
        - mean_diff: Mean difference (bias)
        - percent_diff: Average percentage difference
        - match_rate: Percentage of points within 1% of each other
    """
    try:
        if len(data1) == 0 or len(data2) == 0:
            return {"error": "Empty data"}
        
        # Interpolate to common time base if needed
        if interpolate and len(time1) != len(time2):
            # Use the finer time grid
            if len(time1) > len(time2):
                common_time = time1
                data2_interp = np.interp(common_time, time2, data2)
                data1_interp = data1
            else:
                common_time = time2
                data1_interp = np.interp(common_time, time1, data1)
                data2_interp = data2
        else:
            # Same length - use directly
            min_len = min(len(data1), len(data2))
            data1_interp = data1[:min_len]
            data2_interp = data2[:min_len]
        
        # Remove NaN values
        valid_mask = ~(np.isnan(data1_interp) | np.isnan(data2_interp))
        d1 = data1_interp[valid_mask]
        d2 = data2_interp[valid_mask]
        
        if len(d1) < 2:
            return {"error": "Not enough valid data points"}
        
        # Compute difference
        diff = d1 - d2
        abs_diff = np.abs(diff)
        
        # Compute metrics
        correlation = float(np.corrcoef(d1, d2)[0, 1]) if len(d1) > 1 else 0.0
        rmse = float(np.sqrt(np.mean(diff**2)))
        mae = float(np.mean(abs_diff))
        max_diff = float(np.max(abs_diff))
        mean_diff = float(np.mean(diff))
        
        # Percentage difference (avoid division by zero)
        with np.errstate(divide='ignore', invalid='ignore'):
            d1_safe = np.where(np.abs(d1) > 1e-10, d1, 1e-10)
            percent_diff = float(np.mean(np.abs(diff / d1_safe) * 100))
        
        # Match rate: percentage within 1% of reference
        match_threshold = 0.01 * np.max(np.abs(d1)) if np.max(np.abs(d1)) > 0 else 0.01
        match_rate = float(np.sum(abs_diff < match_threshold) / len(abs_diff) * 100)
        
        return {
            "correlation": round(correlation, 4),
            "rmse": round(rmse, 6),
            "mae": round(mae, 6),
            "max_diff": round(max_diff, 6),
            "mean_diff": round(mean_diff, 6),
            "percent_diff": round(percent_diff, 2),
            "match_rate": round(match_rate, 1),
            "num_points": len(d1),
            "diff_data": diff.tolist() if len(diff) < 10000 else diff[::max(1, len(diff)//10000)].tolist()
        }
        
    except Exception as e:
        return {"error": str(e)}


def compare_csv_signals(
    df1: pd.DataFrame, 
    df2: pd.DataFrame,
    time_col: str = "Time"
) -> Dict[str, Dict]:
    """
    Compare all matching signals between two CSVs.
    
    Args:
        df1, df2: DataFrames to compare
        time_col: Name of time column
    
    Returns:
        Dict mapping signal name to comparison metrics
    """
    results = {}
    
    # Find common signals (excluding time column)
    cols1 = set(df1.columns) - {time_col}
    cols2 = set(df2.columns) - {time_col}
    common_signals = cols1.intersection(cols2)
    
    if not common_signals:
        return {"_summary": {"error": "No common signals found", "common_count": 0}}
    
    time1 = df1[time_col].values if time_col in df1.columns else np.arange(len(df1))
    time2 = df2[time_col].values if time_col in df2.columns else np.arange(len(df2))
    
    for signal in sorted(common_signals):
        try:
            data1 = df1[signal].values.astype(float)
            data2 = df2[signal].values.astype(float)
            results[signal] = compare_signals(time1, data1, time2, data2)
        except Exception as e:
            results[signal] = {"error": str(e)}
    
    # Summary statistics
    valid_results = [r for r in results.values() if "error" not in r]
    if valid_results:
        avg_corr = np.mean([r["correlation"] for r in valid_results])
        avg_rmse = np.mean([r["rmse"] for r in valid_results])
        results["_summary"] = {
            "common_count": len(common_signals),
            "compared_count": len(valid_results),
            "avg_correlation": round(avg_corr, 4),
            "avg_rmse": round(avg_rmse, 6),
            "signals_matched": list(common_signals)
        }
    else:
        results["_summary"] = {"common_count": len(common_signals), "compared_count": 0}
    
    return results
