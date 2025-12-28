"""
LinkingManager - Handles signal linking functionality
"""

from typing import Dict, List, Set, Optional
import numpy as np


class LinkingManager:
    """Manages signal linking and comparison"""

    def __init__(self, app):
        self.app = app
        self.linked_nodes = {}  # Dict: node_id -> linked_node_ids
        self.linked_signals = {}  # Dict: signal_name -> linked_signal_names
        self.linking_groups = []  # List of linking groups
        self.show_link_indicators = True
        self.auto_link_mode = "off"  # 'off', 'nodes', 'signals', 'patterns'
        self.linking_rules = []

    def create_link_group(self, node_indices: List[int]) -> bool:
        """Create a link group from node indices"""
        try:
            group = {
                "nodes": node_indices,
                "signals": [],
                "created_at": np.datetime64("now"),
            }
            self.linking_groups.append(group)
            return True
        except Exception:
            return False

    def link_signals(self, signal1_name: str, signal2_name: str) -> bool:
        """Link two signals"""
        try:
            if signal1_name not in self.linked_signals:
                self.linked_signals[signal1_name] = set()
            if signal2_name not in self.linked_signals:
                self.linked_signals[signal2_name] = set()

            self.linked_signals[signal1_name].add(signal2_name)
            self.linked_signals[signal2_name].add(signal1_name)
            return True
        except Exception:
            return False

    def unlink_signals(self, signal1_name: str, signal2_name: str) -> bool:
        """Unlink two signals"""
        try:
            if signal1_name in self.linked_signals:
                self.linked_signals[signal1_name].discard(signal2_name)
            if signal2_name in self.linked_signals:
                self.linked_signals[signal2_name].discard(signal1_name)
            return True
        except Exception:
            return False

    def get_linked_signals(self, signal_name: str) -> List[str]:
        """Get all signals linked to a given signal"""
        return list(self.linked_signals.get(signal_name, set()))

    def clear_all_links(self):
        """Clear all links"""
        self.linked_nodes = {}
        self.linked_signals = {}
        self.linking_groups = []


def compare_signals(self, signal_keys: List[str]) -> Dict:
    """
    Compare multiple signals with proper error handling and validation.

    Args:
        signal_keys: List of signal keys in format "csv_idx:signal_name"

    Returns:
        Dictionary with statistics and correlations
    """
    from helpers import parse_signal_key

    comparison = {
        "signals": signal_keys,
        "statistics": {},
        "correlations": {},
        "errors": [],
    }

    # Validate and collect signal data
    signal_data_map = {}
    for signal_key in signal_keys:
        try:
            csv_idx, signal_name = parse_signal_key(signal_key)

            # Handle derived signals
            if csv_idx == -1:
                if signal_name in self.app.data_manager.derived_signals:
                    time_data = self.app.data_manager.derived_signals[signal_name][
                        "time"
                    ]
                    signal_data = self.app.data_manager.derived_signals[signal_name][
                        "data"
                    ]
                else:
                    comparison["errors"].append(
                        f"Derived signal not found: {signal_name}"
                    )
                    continue
            else:
                time_data, signal_data = self.app.data_manager.get_signal_data(
                    csv_idx, signal_name
                )

            if len(signal_data) == 0:
                comparison["errors"].append(f"No data for signal: {signal_key}")
                continue

            signal_data_map[signal_key] = {
                "time": time_data,
                "data": signal_data,
                "csv_idx": csv_idx,
                "name": signal_name,
            }

        except Exception as e:
            comparison["errors"].append(f"Error loading {signal_key}: {str(e)}")

    # Calculate statistics for each valid signal
    for signal_key, sig_info in signal_data_map.items():
        try:
            data = sig_info["data"]
            comparison["statistics"][signal_key] = {
                "mean": float(np.mean(data)),
                "std": float(np.std(data)),
                "min": float(np.min(data)),
                "max": float(np.max(data)),
                "rms": float(np.sqrt(np.mean(data**2))),
                "median": float(np.median(data)),
                "samples": len(data),
            }
        except Exception as e:
            comparison["errors"].append(f"Statistics error for {signal_key}: {str(e)}")

    # Calculate correlations between all pairs
    signal_keys_valid = list(signal_data_map.keys())
    for i, sig1_key in enumerate(signal_keys_valid):
        for sig2_key in signal_keys_valid[i + 1 :]:
            try:
                sig1 = signal_data_map[sig1_key]
                sig2 = signal_data_map[sig2_key]

                time1, data1 = sig1["time"], sig1["data"]
                time2, data2 = sig2["time"], sig2["data"]

                # Find overlapping time range
                t_start = max(time1.min(), time2.min())
                t_end = min(time1.max(), time2.max())

                if t_start >= t_end:
                    comparison["errors"].append(
                        f"No time overlap between {sig1_key} and {sig2_key}"
                    )
                    continue

                # Create common time vector
                n_samples = min(len(time1), len(time2), 1000)  # Limit for performance
                time_common = np.linspace(t_start, t_end, n_samples)

                # Interpolate both signals
                data1_interp = np.interp(time_common, time1, data1)
                data2_interp = np.interp(time_common, time2, data2)

                # Check for constant signals (zero variance)
                if np.std(data1_interp) == 0 or np.std(data2_interp) == 0:
                    comparison["correlations"][f"{sig1_key} vs {sig2_key}"] = {
                        "correlation": None,
                        "note": "One or both signals are constant",
                    }
                    continue

                # Calculate correlation
                corr_matrix = np.corrcoef(data1_interp, data2_interp)
                correlation = float(corr_matrix[0, 1])

                # Check for valid correlation
                if np.isnan(correlation) or np.isinf(correlation):
                    comparison["correlations"][f"{sig1_key} vs {sig2_key}"] = {
                        "correlation": None,
                        "note": "Invalid correlation (NaN/Inf)",
                    }
                else:
                    comparison["correlations"][f"{sig1_key} vs {sig2_key}"] = {
                        "correlation": correlation,
                        "samples": n_samples,
                        "time_range": [float(t_start), float(t_end)],
                    }

            except Exception as e:
                comparison["errors"].append(
                    f"Correlation error for {sig1_key} vs {sig2_key}: {str(e)}"
                )

    return comparison
