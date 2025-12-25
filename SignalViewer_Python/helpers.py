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

    Args:
        csv_idx: Index of CSV file (-1 for derived signals)
        signal_name: Name of the signal
        csv_paths: List of CSV file paths
        display_name: Optional custom display name

    Returns:
        Formatted label like "signal_name (csv_name)" or "signal_name (D)"
    """
    name = display_name or signal_name

    if csv_idx == DERIVED_CSV_IDX:
        return f"{name} (D)"

    if 0 <= csv_idx < len(csv_paths):
        csv_name = get_csv_short_name(csv_paths[csv_idx])
        return f"{name} ({csv_name})"

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
