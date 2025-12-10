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
        self.auto_link_mode = 'off'  # 'off', 'nodes', 'signals', 'patterns'
        self.linking_rules = []
    
    def create_link_group(self, node_indices: List[int]) -> bool:
        """Create a link group from node indices"""
        try:
            group = {
                'nodes': node_indices,
                'signals': [],
                'created_at': np.datetime64('now')
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
    
    def compare_signals(self, signal_names: List[str]) -> Dict:
        """Compare multiple signals"""
        comparison = {
            'signals': signal_names,
            'statistics': {},
            'correlations': {}
        }
        
        # Calculate statistics for each signal
        for signal_name in signal_names:
            time_data, signal_data = self.app.data_manager.get_signal_data(0, signal_name)
            if len(signal_data) > 0:
                comparison['statistics'][signal_name] = {
                    'mean': float(np.mean(signal_data)),
                    'std': float(np.std(signal_data)),
                    'min': float(np.min(signal_data)),
                    'max': float(np.max(signal_data)),
                    'rms': float(np.sqrt(np.mean(signal_data**2)))
                }
        
        # Calculate correlations
        for i, sig1 in enumerate(signal_names):
            for sig2 in signal_names[i+1:]:
                time1, data1 = self.app.data_manager.get_signal_data(0, sig1)
                time2, data2 = self.app.data_manager.get_signal_data(0, sig2)
                
                if len(data1) > 0 and len(data2) > 0:
                    # Interpolate to common time
                    time_common = np.linspace(
                        max(time1.min(), time2.min()),
                        min(time1.max(), time2.max()),
                        min(len(time1), len(time2))
                    )
                    data1_interp = np.interp(time_common, time1, data1)
                    data2_interp = np.interp(time_common, time2, data2)
                    
                    correlation = float(np.corrcoef(data1_interp, data2_interp)[0, 1])
                    comparison['correlations'][f"{sig1} vs {sig2}"] = correlation
        
        return comparison

