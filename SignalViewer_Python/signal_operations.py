"""
SignalOperationsManager - Handles derived signals and operations
"""

import numpy as np
from typing import Dict, List, Optional, Tuple

try:
    from scipy import integrate, interpolate

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("Warning: scipy not installed. Some operations may be limited.")


class SignalOperationsManager:
    """Manages signal operations (derivative, integral, math operations)"""

    def __init__(self, app):
        self.app = app
        self.derived_signals = {}  # Dict: signal_name -> signal_data
        self.operation_history = []
        self.interpolation_method = "linear"
        self.max_history_size = 50
        self.operation_counter = 0

    def compute_derivative(
        self,
        signal_name: str,
        method: str = "gradient",
        smoothing: bool = False,
        window_size: int = 5,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute derivative of a signal"""
        time_data, signal_data = self.get_signal_data(signal_name)

        if len(time_data) == 0:
            return np.array([]), np.array([])

        # Apply smoothing if requested
        if smoothing and window_size > 1:
            signal_data = self.smooth_signal(signal_data, window_size)

        # Compute derivative based on method
        if method == "gradient":
            derivative = np.gradient(signal_data, time_data)
        elif method == "forward":
            derivative = np.diff(signal_data) / np.diff(time_data)
            time_data = time_data[:-1]
        elif method == "backward":
            derivative = np.diff(signal_data) / np.diff(time_data)
            time_data = time_data[1:]
        elif method == "central":
            derivative = np.gradient(signal_data, time_data)
        else:
            derivative = np.gradient(signal_data, time_data)

        return time_data, derivative

    def compute_integral(
        self,
        signal_name: str,
        method: str = "trapezoidal",
        initial_value: Optional[float] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute integral of a signal"""
        time_data, signal_data = self.get_signal_data(signal_name)

        if len(time_data) == 0:
            return np.array([]), np.array([])

        # Compute integral based on method
        if method == "trapezoidal":
            integral = integrate.cumulative_trapezoid(signal_data, time_data, initial=0)
        elif method == "simpson":
            # Use trapezoidal as approximation for Simpson
            integral = integrate.cumulative_trapezoid(signal_data, time_data, initial=0)
        elif method == "sum":
            dt = np.diff(time_data)
            integral = np.cumsum(signal_data[:-1] * dt)
            time_data = time_data[:-1]
        else:
            integral = integrate.cumulative_trapezoid(signal_data, time_data, initial=0)

        # Apply initial value if specified
        if initial_value is not None:
            integral = integral + initial_value

        return time_data, integral

    def compute_operation(
        self, operation: str, signal1_name: str, signal2_name: str
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute operation between two signals"""
        time1, data1 = self.get_signal_data(signal1_name)
        time2, data2 = self.get_signal_data(signal2_name)

        if len(time1) == 0 or len(time2) == 0:
            return np.array([]), np.array([])

        # Interpolate to common time base
        time_data, data1_interp, data2_interp = self.interpolate_to_common_time(
            time1, data1, time2, data2
        )

        # Perform operation
        if operation == "add":
            result = data1_interp + data2_interp
        elif operation == "subtract":
            result = data1_interp - data2_interp
        elif operation == "multiply":
            result = data1_interp * data2_interp
        elif operation == "divide":
            result = np.divide(
                data1_interp,
                data2_interp,
                out=np.zeros_like(data1_interp),
                where=data2_interp != 0,
            )
        else:
            result = data1_interp

        return time_data, result

    def interpolate_to_common_time(
        self, time1: np.ndarray, data1: np.ndarray, time2: np.ndarray, data2: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Interpolate two signals to common time base"""
        # Find common time range
        t_min = max(time1.min(), time2.min())
        t_max = min(time1.max(), time2.max())

        # Create common time base
        n_points = max(len(time1), len(time2))
        time_common = np.linspace(t_min, t_max, n_points)

        # Interpolate
        if self.interpolation_method == "linear":
            data1_interp = np.interp(time_common, time1, data1)
            data2_interp = np.interp(time_common, time2, data2)
        else:
            # Use scipy interpolation for other methods
            f1 = interpolate.interp1d(
                time1,
                data1,
                kind=self.interpolation_method,
                bounds_error=False,
                fill_value="extrapolate",
            )
            f2 = interpolate.interp1d(
                time2,
                data2,
                kind=self.interpolation_method,
                bounds_error=False,
                fill_value="extrapolate",
            )
            data1_interp = f1(time_common)
            data2_interp = f2(time_common)

        return time_common, data1_interp, data2_interp

    def get_signal_data(self, signal_name: str) -> Tuple[np.ndarray, np.ndarray]:
        """Get signal data (time and values) with caching"""
        # Check if it's a derived signal
        if signal_name in self.derived_signals:
            signal_data = self.derived_signals[signal_name]
            return signal_data.get("time", np.array([])), signal_data.get(
                "data", np.array([])
            )

        # Not a derived signal - shouldn't happen but return empty
        print(f"Warning: {signal_name} not found in derived signals")
        return np.array([]), np.array([])

    def add_derived_signal(
        self,
        signal_name: str,
        time_data: np.ndarray,
        signal_data: np.ndarray,
        operation_info: Dict,
    ):
        """Add a derived signal"""
        self.derived_signals[signal_name] = {
            "time": time_data,
            "data": signal_data,
            "operation": operation_info,
        }

        # Add to history
        self.operation_history.append(
            {
                "signal_name": signal_name,
                "operation": operation_info,
                "timestamp": np.datetime64("now"),
            }
        )

        # Limit history size
        if len(self.operation_history) > self.max_history_size:
            self.operation_history = self.operation_history[-self.max_history_size :]

    def smooth_signal(self, signal_data: np.ndarray, window_size: int) -> np.ndarray:
        """Apply smoothing filter to signal"""
        if window_size < 2:
            return signal_data

        # Simple moving average
        kernel = np.ones(window_size) / window_size
        smoothed = np.convolve(signal_data, kernel, mode="same")
        return smoothed

    def clear_all_derived_signals(self):
        """Clear all derived signals"""
        self.derived_signals = {}
        self.operation_history = []
