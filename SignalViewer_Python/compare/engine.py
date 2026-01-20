"""
Signal Viewer Pro - Compare Engine
===================================
Compare signals between runs with alignment, sync, and delta computation.
Matches SDI comparison capabilities.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class SyncMethod(Enum):
    """Time synchronization method"""
    BASELINE = "baseline"    # Use baseline's time points
    UNION = "union"          # Union of time points (requires interpolation)
    INTERSECTION = "intersection"  # Only overlapping time range


class InterpolationMethod(Enum):
    """Interpolation method for sync"""
    LINEAR = "linear"
    NEAREST = "nearest"


@dataclass
class ToleranceSpec:
    """Tolerance specification for comparison"""
    absolute: Optional[float] = None  # Absolute tolerance
    relative: Optional[float] = None  # Relative tolerance (0-1)
    time: Optional[float] = None      # Time tolerance (for alignment)


@dataclass
class CompareResult:
    """Result of signal comparison"""
    signal_name: str
    baseline_name: str
    compare_to_name: str
    
    # Aligned data
    time: np.ndarray
    baseline_data: np.ndarray
    compare_data: np.ndarray
    delta: np.ndarray
    
    # Metrics
    max_abs_diff: float
    rms_diff: float
    mean_diff: float
    correlation: float
    
    # Tolerance results
    within_tolerance: bool = True
    tolerance_violations: int = 0
    tolerance_violation_pct: float = 0.0


@dataclass 
class CompareConfig:
    """Configuration for comparison"""
    baseline_run_idx: int
    compare_run_idx: int
    signal_names: List[str]
    sync_method: SyncMethod = SyncMethod.BASELINE
    interpolation: InterpolationMethod = InterpolationMethod.LINEAR
    time_shift: float = 0.0  # Manual time shift for compare run
    tolerance: Optional[ToleranceSpec] = None


def compare_runs(
    baseline_time: np.ndarray,
    baseline_data: np.ndarray,
    compare_time: np.ndarray,
    compare_data: np.ndarray,
    config: CompareConfig,
    signal_name: str,
    baseline_name: str,
    compare_name: str,
) -> Optional[CompareResult]:
    """
    Compare two signals from different runs.
    
    Args:
        baseline_time: Baseline time array
        baseline_data: Baseline signal data
        compare_time: Compare-to time array
        compare_data: Compare-to signal data
        config: Comparison configuration
        signal_name: Signal name
        baseline_name: Baseline run name
        compare_name: Compare-to run name
        
    Returns:
        CompareResult or None if failed
    """
    if len(baseline_data) == 0 or len(compare_data) == 0:
        return None
    
    try:
        # Apply time shift
        compare_time_shifted = compare_time + config.time_shift
        
        # Synchronize time bases
        time_out, base_aligned, comp_aligned = _sync_signals(
            baseline_time, baseline_data,
            compare_time_shifted, compare_data,
            config.sync_method,
            config.interpolation,
        )
        
        if len(time_out) == 0:
            return None
        
        # Compute delta
        delta = base_aligned - comp_aligned
        abs_delta = np.abs(delta)
        
        # Compute metrics
        max_abs_diff = float(np.max(abs_delta))
        rms_diff = float(np.sqrt(np.mean(delta**2)))
        mean_diff = float(np.mean(delta))
        
        # Correlation
        if len(base_aligned) > 1:
            correlation = float(np.corrcoef(base_aligned, comp_aligned)[0, 1])
        else:
            correlation = 1.0
        
        # Tolerance check
        within_tolerance = True
        violations = 0
        violation_pct = 0.0
        
        if config.tolerance:
            tol = config.tolerance
            violation_mask = np.zeros(len(abs_delta), dtype=bool)
            
            if tol.absolute is not None:
                violation_mask |= (abs_delta > tol.absolute)
            
            if tol.relative is not None:
                # Relative to baseline magnitude
                base_mag = np.abs(base_aligned)
                rel_threshold = base_mag * tol.relative
                rel_threshold = np.maximum(rel_threshold, 1e-10)  # Avoid division by zero
                violation_mask |= (abs_delta > rel_threshold)
            
            violations = int(np.sum(violation_mask))
            violation_pct = 100.0 * violations / len(abs_delta) if len(abs_delta) > 0 else 0.0
            within_tolerance = violations == 0
        
        return CompareResult(
            signal_name=signal_name,
            baseline_name=baseline_name,
            compare_to_name=compare_name,
            time=time_out,
            baseline_data=base_aligned,
            compare_data=comp_aligned,
            delta=delta,
            max_abs_diff=max_abs_diff,
            rms_diff=rms_diff,
            mean_diff=mean_diff,
            correlation=correlation,
            within_tolerance=within_tolerance,
            tolerance_violations=violations,
            tolerance_violation_pct=violation_pct,
        )
        
    except Exception as e:
        print(f"[ERROR] Compare failed: {e}")
        return None


def _sync_signals(
    time_a: np.ndarray,
    data_a: np.ndarray,
    time_b: np.ndarray,
    data_b: np.ndarray,
    sync_method: SyncMethod,
    interp_method: InterpolationMethod,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Synchronize two signals to a common time base.
    """
    if sync_method == SyncMethod.BASELINE:
        # Use baseline time, interpolate compare
        time_out = time_a
        a_out = data_a
        b_out = _interpolate(time_b, data_b, time_out, interp_method)
        
    elif sync_method == SyncMethod.UNION:
        # Union of all time points
        time_out = np.unique(np.concatenate([time_a, time_b]))
        a_out = _interpolate(time_a, data_a, time_out, interp_method)
        b_out = _interpolate(time_b, data_b, time_out, interp_method)
        
    elif sync_method == SyncMethod.INTERSECTION:
        # Only overlapping time range
        t_start = max(time_a[0], time_b[0])
        t_end = min(time_a[-1], time_b[-1])
        
        if t_start >= t_end:
            return np.array([]), np.array([]), np.array([])
        
        # Use denser time base within overlap
        mask_a = (time_a >= t_start) & (time_a <= t_end)
        mask_b = (time_b >= t_start) & (time_b <= t_end)
        
        if np.sum(mask_a) >= np.sum(mask_b):
            time_out = time_a[mask_a]
        else:
            time_out = time_b[mask_b]
        
        a_out = _interpolate(time_a, data_a, time_out, interp_method)
        b_out = _interpolate(time_b, data_b, time_out, interp_method)
    
    else:
        time_out = time_a
        a_out = data_a
        b_out = _interpolate(time_b, data_b, time_out, interp_method)
    
    return time_out, a_out, b_out


def _interpolate(
    time_src: np.ndarray,
    data_src: np.ndarray,
    time_dst: np.ndarray,
    method: InterpolationMethod,
) -> np.ndarray:
    """Interpolate data to new time base"""
    if method == InterpolationMethod.NEAREST:
        indices = np.searchsorted(time_src, time_dst)
        indices = np.clip(indices, 0, len(data_src) - 1)
        return data_src[indices]
    else:
        return np.interp(time_dst, time_src, data_src)


def auto_time_shift(
    time_a: np.ndarray,
    data_a: np.ndarray,
    time_b: np.ndarray,
    data_b: np.ndarray,
    max_shift: float = 10.0,
) -> float:
    """
    Estimate optimal time shift using cross-correlation.
    
    Args:
        time_a, data_a: Baseline signal
        time_b, data_b: Compare signal
        max_shift: Maximum shift to search
        
    Returns:
        Estimated time shift (positive = B is ahead of A)
    """
    try:
        # Resample to common regular grid
        t_start = max(time_a[0], time_b[0])
        t_end = min(time_a[-1], time_b[-1])
        
        if t_end <= t_start:
            return 0.0
        
        dt = min(np.mean(np.diff(time_a)), np.mean(np.diff(time_b)))
        n_samples = int((t_end - t_start) / dt)
        n_samples = min(n_samples, 10000)  # Limit for performance
        
        t_common = np.linspace(t_start, t_end, n_samples)
        a_resampled = np.interp(t_common, time_a, data_a)
        b_resampled = np.interp(t_common, time_b, data_b)
        
        # Cross-correlation
        corr = np.correlate(a_resampled - np.mean(a_resampled),
                           b_resampled - np.mean(b_resampled),
                           mode='full')
        
        # Find peak
        lags = np.arange(-(n_samples-1), n_samples)
        peak_idx = np.argmax(corr)
        lag_samples = lags[peak_idx]
        
        time_shift = lag_samples * dt
        
        # Clamp to max shift
        return float(np.clip(time_shift, -max_shift, max_shift))
        
    except Exception:
        return 0.0

