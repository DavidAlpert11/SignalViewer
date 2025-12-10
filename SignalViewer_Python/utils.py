"""
Utility functions for Signal Viewer
"""
import numpy as np
import pandas as pd
from typing import Tuple, List


def downsample_data(x_data: np.ndarray, y_data: np.ndarray, 
                   max_points: int) -> Tuple[np.ndarray, np.ndarray]:
    """Downsample data for large datasets"""
    n = len(x_data)
    if n <= max_points:
        return x_data, y_data
    
    dec_factor = max(1, n // max_points)
    indices = list(range(0, n, dec_factor))
    
    # Always include last point
    if indices[-1] != n - 1:
        indices.append(n - 1)
    
    return x_data[indices], y_data[indices]


def validate_csv_format(df: pd.DataFrame) -> bool:
    """Validate CSV format"""
    try:
        if df.empty:
            return False
        
        # Check for Time column
        if 'Time' not in df.columns and len(df.columns) > 0:
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
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_signal_statistics(time_data: np.ndarray, signal_data: np.ndarray) -> dict:
    """Calculate signal statistics"""
    if len(signal_data) == 0:
        return {}
    
    valid_mask = ~np.isnan(signal_data)
    valid_data = signal_data[valid_mask]
    
    if len(valid_data) == 0:
        return {}
    
    stats = {
        'mean': float(np.mean(valid_data)),
        'std': float(np.std(valid_data)),
        'min': float(np.min(valid_data)),
        'max': float(np.max(valid_data)),
        'rms': float(np.sqrt(np.mean(valid_data**2))),
        'count': int(len(valid_data))
    }
    
    if len(time_data) > 1:
        dt = np.diff(time_data[valid_mask])
        if len(dt) > 0 and np.mean(dt) > 0:
            stats['sample_rate'] = float(1.0 / np.mean(dt))
    
    return stats


def rgb_to_plotly_color(rgb_tuple: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to Plotly color string"""
    return f"rgb({rgb_tuple[0]}, {rgb_tuple[1]}, {rgb_tuple[2]})"


def plotly_color_to_rgb(color_str: str) -> Tuple[int, int, int]:
    """Convert Plotly color string to RGB tuple"""
    if color_str.startswith('rgb('):
        rgb_str = color_str[4:-1]
        return tuple(map(int, rgb_str.split(',')))
    return (0, 0, 0)

