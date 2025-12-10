"""
PlotManager - Handles plotting and visualization with Plotly
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from typing import List, Dict, Optional, Tuple
import pandas as pd

# Color palette
SIGNAL_COLORS = [
    '#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B',
    '#95C623', '#5E60CE', '#4EA8DE', '#48BFE3', '#64DFDF',
    '#72EFDD', '#80FFDB', '#E63946', '#F4A261', '#2A9D8F'
]


class PlotManager:
    """Manages plots, subplots, and signal assignments"""
    
    def __init__(self, app):
        self.app = app
        self.plot_tabs = []
        self.axes_arrays = []
        self.assigned_signals = []
        self.selected_subplot_idx = 0
        self.current_tab_idx = 0
        self.custom_y_labels = {}
        self.tuple_signals = []
        self.tuple_mode = []
        self.x_axis_signals = []
        self.tab_layouts = {}
    
    def initialize(self):
        """Initialize plot manager"""
        self.create_default_tab()
    
    def create_default_tab(self):
        """Create default tab with subplots"""
        self.create_tab(rows=1, cols=1)
    
    def create_tab(self, rows: int = 1, cols: int = 1):
        """Create a new plot tab"""
        tab_idx = len(self.plot_tabs)
        
        # Create subplot figure with proper spacing
        fig = make_subplots(
            rows=rows, cols=cols,
            subplot_titles=[f'Subplot {i+1}' for i in range(rows * cols)],
            vertical_spacing=0.18 if rows > 1 else 0.1,  # More space for labels
            horizontal_spacing=0.15 if cols > 1 else 0.1
        )
        
        # Dark theme layout
        fig.update_layout(
            paper_bgcolor='#16213e',
            plot_bgcolor='#1a1a2e',
            font=dict(color='#e8e8e8', size=10),
            height=max(500, 280 * rows),
            showlegend=True,
            legend=dict(
                bgcolor='rgba(22, 33, 62, 0.9)',
                bordercolor='#333',
                borderwidth=1,
                font=dict(size=10),
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            ),
            margin=dict(l=70, r=50, t=80, b=70)
        )
        
        # Style axes
        for i in range(1, rows * cols + 1):
            r = (i - 1) // cols + 1
            c = (i - 1) % cols + 1
            
            fig.update_xaxes(
                gridcolor='#333',
                zerolinecolor='#444',
                title_text='Time',
                title_font=dict(size=11),
                tickfont=dict(size=9),
                row=r, col=c
            )
            fig.update_yaxes(
                gridcolor='#333',
                zerolinecolor='#444',
                title_text='Value',
                title_font=dict(size=11),
                tickfont=dict(size=9),
                row=r, col=c
            )
        
        self.plot_tabs.append(fig)
        self.axes_arrays.append([(row, col) for row in range(1, rows+1) for col in range(1, cols+1)])
        self.assigned_signals.append([[] for _ in range(rows * cols)])
        self.tuple_signals.append([[] for _ in range(rows * cols)])
        self.tuple_mode.append([False for _ in range(rows * cols)])
        self.x_axis_signals.append(['Time' for _ in range(rows * cols)])
        self.tab_layouts[tab_idx] = {'rows': rows, 'cols': cols}
    
    def refresh_plots(self, tab_idx: Optional[int] = None):
        """Refresh plots for specified tab or current tab"""
        if tab_idx is None:
            tab_idx = self.current_tab_idx
        
        if tab_idx >= len(self.plot_tabs) or len(self.plot_tabs) == 0:
            return
        
        if not self.app.data_manager.data_tables:
            return
        
        if not any(df is not None and not df.empty for df in self.app.data_manager.data_tables):
            return
        
        fig = self.plot_tabs[tab_idx]
        axes_arr = self.axes_arrays[tab_idx]
        assignments = self.assigned_signals[tab_idx]
        
        # Clear existing traces
        fig.data = []
        
        # Plot signals for each subplot
        for subplot_idx, (row, col) in enumerate(axes_arr):
            if subplot_idx >= len(assignments):
                continue
            
            assigned = assignments[subplot_idx]
            
            if (subplot_idx < len(self.tuple_mode[tab_idx]) and 
                self.tuple_mode[tab_idx][subplot_idx]):
                self.plot_tuple_signals(fig, tab_idx, subplot_idx, row, col)
            else:
                self.plot_regular_signals(fig, tab_idx, subplot_idx, row, col, assigned)
        
        # Update layout with proper spacing
        layout = self.tab_layouts.get(tab_idx, {'rows': 1, 'cols': 1})
        rows = layout.get('rows', 1)
        
        fig.update_layout(
            height=max(500, 280 * rows),
            showlegend=True,
            hovermode='closest'
        )
    
    def plot_regular_signals(self, fig, tab_idx: int, subplot_idx: int, 
                            row: int, col: int, assigned: List[Dict]):
        """Plot regular signals"""
        if not assigned:
            return
        
        x_axis_signal = 'Time'
        if subplot_idx < len(self.x_axis_signals[tab_idx]):
            x_axis_signal = self.x_axis_signals[tab_idx][subplot_idx]
        
        color_idx = 0
        
        for sig_info in assigned:
            csv_idx = sig_info.get('csv_idx', -1)
            signal_name = sig_info.get('signal', '')
            
            if csv_idx == -1:
                time_data, signal_data = self.app.signal_operations.get_signal_data(signal_name)
            else:
                time_data, signal_data = self.app.data_manager.get_signal_data(csv_idx, signal_name)
            
            if len(time_data) == 0:
                continue
            
            # Get X-axis data
            if x_axis_signal == 'Time':
                x_data = time_data
            else:
                x_csv_idx = sig_info.get('x_csv_idx', csv_idx)
                x_data, _ = self.app.data_manager.get_signal_data(x_csv_idx, x_axis_signal)
                if len(x_data) == 0:
                    x_data = time_data
            
            # Downsample for large datasets
            max_points = 50000
            if len(x_data) > max_points:
                x_data, signal_data = self.downsample_data(x_data, signal_data, max_points)
            
            # Get color
            color = sig_info.get('color', SIGNAL_COLORS[color_idx % len(SIGNAL_COLORS)])
            line_width = sig_info.get('line_width', 1.5)
            
            # Add trace
            fig.add_trace(
                go.Scatter(
                    x=x_data,
                    y=signal_data,
                    mode='lines',
                    name=f"{signal_name}",
                    line=dict(color=color, width=line_width),
                    showlegend=True,
                    hovertemplate=f"<b>{signal_name}</b><br>X: %{{x:.4f}}<br>Y: %{{y:.4f}}<extra></extra>"
                ),
                row=row, col=col
            )
            
            color_idx += 1
    
    def plot_tuple_signals(self, fig, tab_idx: int, subplot_idx: int, row: int, col: int):
        """Plot X-Y pair signals (tuple mode)"""
        if subplot_idx >= len(self.tuple_signals[tab_idx]):
            return
        
        tuples = self.tuple_signals[tab_idx][subplot_idx]
        if not tuples:
            return
        
        color_idx = 0
        
        for tuple_info in tuples:
            x_sig = tuple_info.get('x_signal', {})
            y_sig = tuple_info.get('y_signal', {})
            label = tuple_info.get('label', '')
            color = tuple_info.get('color', SIGNAL_COLORS[color_idx % len(SIGNAL_COLORS)])
            
            if x_sig.get('csv_idx', -1) == -1:
                x_time, x_data = self.app.signal_operations.get_signal_data(x_sig.get('signal', ''))
            else:
                x_time, x_data = self.app.data_manager.get_signal_data(
                    x_sig.get('csv_idx', 0), x_sig.get('signal', '')
                )
            
            if y_sig.get('csv_idx', -1) == -1:
                y_time, y_data = self.app.signal_operations.get_signal_data(y_sig.get('signal', ''))
            else:
                y_time, y_data = self.app.data_manager.get_signal_data(
                    y_sig.get('csv_idx', 0), y_sig.get('signal', '')
                )
            
            if len(x_data) == 0 or len(y_data) == 0:
                continue
            
            if len(x_data) != len(y_data):
                min_len = min(len(x_data), len(y_data))
                x_data = x_data[:min_len]
                y_data = y_data[:min_len]
            
            max_points = 50000
            if len(x_data) > max_points:
                x_data, y_data = self.downsample_data(x_data, y_data, max_points)
            
            fig.add_trace(
                go.Scatter(
                    x=x_data,
                    y=y_data,
                    mode='lines',
                    name=label,
                    line=dict(color=color, width=1.5),
                    showlegend=True
                ),
                row=row, col=col
            )
            
            color_idx += 1
    
    def downsample_data(self, x_data, y_data, max_points: int):
        """Downsample data for better performance"""
        if len(x_data) <= max_points:
            return x_data, y_data
        
        # Use numpy for efficient downsampling
        x_arr = np.array(x_data) if not isinstance(x_data, np.ndarray) else x_data
        y_arr = np.array(y_data) if not isinstance(y_data, np.ndarray) else y_data
        
        # Simple uniform sampling
        indices = np.linspace(0, len(x_arr) - 1, max_points, dtype=int)
        
        return x_arr[indices], y_arr[indices]
    
    def get_signal_color(self, signal_name: str, csv_idx: int) -> str:
        """Get color for a signal"""
        idx = hash(f"{signal_name}_{csv_idx}") % len(SIGNAL_COLORS)
        return SIGNAL_COLORS[idx]
    
    def assign_signal(self, tab_idx: int, subplot_idx: int, signal_info: Dict):
        """Assign a signal to a subplot"""
        while tab_idx >= len(self.assigned_signals):
            self.create_tab()
        
        while subplot_idx >= len(self.assigned_signals[tab_idx]):
            self.assigned_signals[tab_idx].append([])
        
        if signal_info not in self.assigned_signals[tab_idx][subplot_idx]:
            self.assigned_signals[tab_idx][subplot_idx].append(signal_info)
    
    def remove_signal(self, tab_idx: int, subplot_idx: int, signal_info: Dict):
        """Remove a signal from a subplot"""
        if tab_idx < len(self.assigned_signals):
            if subplot_idx < len(self.assigned_signals[tab_idx]):
                try:
                    self.assigned_signals[tab_idx][subplot_idx].remove(signal_info)
                except ValueError:
                    pass
    
    def clear_subplot(self, tab_idx: int, subplot_idx: int):
        """Clear all signals from a subplot"""
        if tab_idx < len(self.assigned_signals):
            if subplot_idx < len(self.assigned_signals[tab_idx]):
                self.assigned_signals[tab_idx][subplot_idx] = []
    
    def get_subplot_signals(self, tab_idx: int, subplot_idx: int) -> List[Dict]:
        """Get signals assigned to a subplot"""
        if tab_idx < len(self.assigned_signals):
            if subplot_idx < len(self.assigned_signals[tab_idx]):
                return self.assigned_signals[tab_idx][subplot_idx]
        return []
