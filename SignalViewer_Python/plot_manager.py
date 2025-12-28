"""
PlotManager - Enhanced plotting with Plotly
Version 2.0 - WebGL optimized for large datasets
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from typing import List, Dict, Optional, Tuple
import pandas as pd
from helpers import get_text_direction_style, get_text_direction_attr

# Color palette
SIGNAL_COLORS = [
    "#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#3B1F2B",
    "#95C623", "#5E60CE", "#4EA8DE", "#48BFE3", "#64DFDF",
    "#72EFDD", "#80FFDB", "#E63946", "#F4A261", "#2A9D8F",
]

# Performance thresholds
WEBGL_THRESHOLD = 5000  # Use Scattergl above this many points
MAX_POINTS_DEFAULT = 50000  # Default LOD level


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
        self.subplot_titles = {}
        self.subplot_metadata = {}
        self.tuple_signals = []
        self.tuple_mode = []
        self.x_axis_signals = []
        self.tab_layouts = {}
        
        # Performance settings
        self.use_webgl = True  # Enable WebGL by default
        self.max_points = MAX_POINTS_DEFAULT
        self.auto_decimate = True

    def initialize(self):
        """Initialize plot manager"""
        self.create_default_tab()

    def create_default_tab(self):
        """Create default tab with subplots"""
        self.create_tab(rows=1, cols=1)

    def create_tab(self, rows: int = 1, cols: int = 1):
        """Create a new plot tab"""
        tab_idx = len(self.plot_tabs)

        fig = make_subplots(
            rows=rows,
            cols=cols,
            subplot_titles=[f"Subplot {i+1}" for i in range(rows * cols)],
            vertical_spacing=0.18 if rows > 1 else 0.1,
            horizontal_spacing=0.15 if cols > 1 else 0.1,
        )

        # Dark theme layout
        fig.update_layout(
            paper_bgcolor="#16213e",
            plot_bgcolor="#1a1a2e",
            font=dict(color="#e8e8e8", size=10),
            height=max(500, 280 * rows),
            showlegend=True,
            legend=dict(
                bgcolor="rgba(22, 33, 62, 0.9)",
                bordercolor="#333",
                borderwidth=1,
                font=dict(size=10),
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
            margin=dict(l=70, r=50, t=80, b=70),
            hovermode='closest',
        )

        # Style axes
        for i in range(1, rows * cols + 1):
            r = (i - 1) // cols + 1
            c = (i - 1) % cols + 1

            fig.update_xaxes(
                gridcolor="#333",
                zerolinecolor="#444",
                title_text="Time",
                title_font=dict(size=11),
                tickfont=dict(size=9),
                row=r,
                col=c,
            )
            fig.update_yaxes(
                gridcolor="#333",
                zerolinecolor="#444",
                title_text="Value",
                title_font=dict(size=11),
                tickfont=dict(size=9),
                row=r,
                col=c,
            )

        self.plot_tabs.append(fig)
        self.axes_arrays.append(
            [(row, col) for row in range(1, rows + 1) for col in range(1, cols + 1)]
        )
        self.assigned_signals.append([[] for _ in range(rows * cols)])
        self.tuple_signals.append([[] for _ in range(rows * cols)])
        self.tuple_mode.append([False for _ in range(rows * cols)])
        self.x_axis_signals.append(["Time" for _ in range(rows * cols)])
        self.tab_layouts[tab_idx] = {"rows": rows, "cols": cols}

    def refresh_plots(self, tab_idx: Optional[int] = None):
        """Refresh plots for specified tab or current tab"""
        if tab_idx is None:
            tab_idx = self.current_tab_idx

        if tab_idx >= len(self.plot_tabs) or len(self.plot_tabs) == 0:
            return

        if not self.app.data_manager.data_tables:
            return

        if not any(df is not None and not df.empty 
                  for df in self.app.data_manager.data_tables):
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
        layout = self.tab_layouts.get(tab_idx, {"rows": 1, "cols": 1})
        rows = layout.get("rows", 1)

        fig.update_layout(
            height=max(500, 280 * rows),
            showlegend=True,
            hovermode="closest"
        )

    def plot_regular_signals(
        self,
        fig,
        tab_idx: int,
        subplot_idx: int,
        row: int,
        col: int,
        assigned: List[Dict],
    ):
        """Plot regular signals with WebGL optimization"""
        if not assigned:
            return

        x_axis_signal = "Time"
        if subplot_idx < len(self.x_axis_signals[tab_idx]):
            x_axis_signal = self.x_axis_signals[tab_idx][subplot_idx]

        color_idx = 0

        for sig_info in assigned:
            csv_idx = sig_info.get("csv_idx", -1)
            signal_name = sig_info.get("signal", "")

            # Get signal data with decimation
            if csv_idx == -1:
                # Derived signal
                time_data, signal_data = self.app.signal_operations.get_signal_data(
                    signal_name
                )
            else:
                # Request decimated data with caching
                time_data, signal_data = self.app.data_manager.get_signal_data_ext(
                    csv_idx,
                    signal_name,
                    max_points=self.max_points if self.auto_decimate else None,
                    use_cache=True,
                )

            if len(time_data) == 0:
                continue

            # Get X-axis data
            if x_axis_signal == "Time":
                x_data = time_data
            else:
                x_csv_idx = sig_info.get("x_csv_idx", csv_idx)
                x_data, _ = self.app.data_manager.get_signal_data_ext(
                    x_csv_idx,
                    x_axis_signal,
                    max_points=self.max_points if self.auto_decimate else None,
                    use_cache=True,
                )
                if len(x_data) == 0:
                    x_data = time_data

            # Ensure equal length
            min_len = min(len(x_data), len(signal_data))
            x_data = x_data[:min_len]
            y_data = signal_data[:min_len]

            # Choose trace type based on data size and settings
            use_scattergl = self.use_webgl and len(x_data) > WEBGL_THRESHOLD
            
            color = SIGNAL_COLORS[color_idx % len(SIGNAL_COLORS)]
            
            # Get custom display name
            display_name = sig_info.get("display_name", signal_name)
            
            # Create appropriate trace
            if use_scattergl:
                trace = go.Scattergl(
                    x=x_data,
                    y=y_data,
                    mode="lines",
                    name=display_name,
                    line=dict(color=color, width=1.5),
                    hovertemplate=f"<b>{display_name}</b><br>" +
                                f"{x_axis_signal}: %{{x:.4f}}<br>" +
                                "Value: %{y:.4f}<extra></extra>",
                )
            else:
                trace = go.Scatter(
                    x=x_data,
                    y=y_data,
                    mode="lines",
                    name=display_name,
                    line=dict(color=color, width=1.5),
                    hovertemplate=f"<b>{display_name}</b><br>" +
                                f"{x_axis_signal}: %{{x:.4f}}<br>" +
                                "Value: %{y:.4f}<extra></extra>",
                )

            fig.add_trace(trace, row=row, col=col)
            color_idx += 1

        # Update axis labels
        custom_y = self.custom_y_labels.get((tab_idx, subplot_idx), "Value")
        fig.update_xaxes(title_text=x_axis_signal, row=row, col=col)
        fig.update_yaxes(title_text=custom_y, row=row, col=col)

    def plot_tuple_signals(self, fig, tab_idx: int, subplot_idx: int, row: int, col: int):
        """Plot signals in tuple/XY mode"""
        if subplot_idx >= len(self.tuple_signals[tab_idx]):
            return

        tuple_list = self.tuple_signals[tab_idx][subplot_idx]
        if not tuple_list:
            return

        color_idx = 0

        for tuple_info in tuple_list:
            x_csv_idx = tuple_info.get("x_csv_idx", -1)
            y_csv_idx = tuple_info.get("y_csv_idx", -1)
            x_signal = tuple_info.get("x_signal", "")
            y_signal = tuple_info.get("y_signal", "")

            # Get X data
            if x_csv_idx == -1:
                x_data, _ = self.app.signal_operations.get_signal_data(x_signal)
            else:
                x_data, _ = self.app.data_manager.get_signal_data_ext(
                    x_csv_idx, x_signal,
                    max_points=self.max_points if self.auto_decimate else None,
                    use_cache=True,
                )

            # Get Y data
            if y_csv_idx == -1:
                y_data, _ = self.app.signal_operations.get_signal_data(y_signal)
            else:
                _, y_data = self.app.data_manager.get_signal_data_ext(
                    y_csv_idx, y_signal,
                    max_points=self.max_points if self.auto_decimate else None,
                    use_cache=True,
                )

            if len(x_data) == 0 or len(y_data) == 0:
                continue

            # Ensure equal length
            min_len = min(len(x_data), len(y_data))
            x_data = x_data[:min_len]
            y_data = y_data[:min_len]

            color = SIGNAL_COLORS[color_idx % len(SIGNAL_COLORS)]
            
            x_display = tuple_info.get("x_display_name", x_signal)
            y_display = tuple_info.get("y_display_name", y_signal)
            
            # Use WebGL for large datasets
            use_scattergl = self.use_webgl and len(x_data) > WEBGL_THRESHOLD

            if use_scattergl:
                trace = go.Scattergl(
                    x=x_data,
                    y=y_data,
                    mode="lines",
                    name=f"{y_display} vs {x_display}",
                    line=dict(color=color, width=1.5),
                    hovertemplate=f"<b>{y_display} vs {x_display}</b><br>" +
                                f"X: %{{x:.4f}}<br>Y: %{{y:.4f}}<extra></extra>",
                )
            else:
                trace = go.Scatter(
                    x=x_data,
                    y=y_data,
                    mode="lines",
                    name=f"{y_display} vs {x_display}",
                    line=dict(color=color, width=1.5),
                    hovertemplate=f"<b>{y_display} vs {x_display}</b><br>" +
                                f"X: %{{x:.4f}}<br>Y: %{{y:.4f}}<extra></extra>",
                )

            fig.add_trace(trace, row=row, col=col)
            color_idx += 1

        # Update axis labels for XY mode
        fig.update_xaxes(title_text="X Axis", row=row, col=col)
        fig.update_yaxes(title_text="Y Axis", row=row, col=col)

    def export_to_html(self, tab_idx: int, filename: str) -> bool:
        """Export tab to standalone HTML file"""
        try:
            if tab_idx < 0 or tab_idx >= len(self.plot_tabs):
                return False

            fig = self.plot_tabs[tab_idx]
            
            # Export with WebGL support
            fig.write_html(
                filename,
                config={
                    'displayModeBar': True,
                    'displaylogo': False,
                    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                    'toImageButtonOptions': {
                        'format': 'png',
                        'filename': 'signal_viewer_plot',
                        'height': 1080,
                        'width': 1920,
                        'scale': 2
                    }
                },
                include_plotlyjs='cdn',  # Use CDN for smaller file size
            )
            
            return True
            
        except Exception as e:
            print(f"Error exporting to HTML: {e}")
            return False

    def export_to_html_rtl(self, tab_idx: int) -> str:
        """Export tab to HTML string with RTL support"""
        if tab_idx < 0 or tab_idx >= len(self.plot_tabs):
            return ""

        try:
            fig = self.plot_tabs[tab_idx]
            
            # Get basic HTML
            html_content = fig.to_html(
                include_plotlyjs='cdn',
                config={
                    'displayModeBar': True,
                    'displaylogo': False,
                }
            )

            # Add RTL support
            rtl_style = """
            <style>
            body { 
                direction: rtl; 
                font-family: Arial, sans-serif; 
            }
            .plotly { 
                direction: ltr !important; 
            }
            </style>
            """
            
            html_content = html_content.replace('</head>', f'{rtl_style}</head>')
            
            return html_content

        except Exception as e:
            print(f"Error generating HTML: {e}")
            return ""

    def set_subplot_metadata(self, tab_idx: int, subplot_idx: int, 
                           caption: str = "", description: str = ""):
        """Set metadata for subplot"""
        key = (tab_idx, subplot_idx)
        self.subplot_metadata[key] = {
            "caption": caption or "",
            "description": description or "",
        }

    def get_subplot_metadata(self, tab_idx: int, subplot_idx: int) -> Dict:
        """Get metadata for subplot"""
        return self.subplot_metadata.get((tab_idx, subplot_idx), {})

    def remove_tab(self, tab_idx: int):
        """Remove a tab and its associated state"""
        if tab_idx < 0 or tab_idx >= len(self.plot_tabs):
            return

        layouts = [
            self.tab_layouts.get(i, {"rows": 1, "cols": 1})
            for i in range(len(self.plot_tabs))
        ]

        self.plot_tabs.pop(tab_idx)
        if tab_idx < len(self.axes_arrays):
            self.axes_arrays.pop(tab_idx)
        if tab_idx < len(self.assigned_signals):
            self.assigned_signals.pop(tab_idx)
        if tab_idx < len(self.tuple_signals):
            self.tuple_signals.pop(tab_idx)
        if tab_idx < len(self.tuple_mode):
            self.tuple_mode.pop(tab_idx)
        if tab_idx < len(self.x_axis_signals):
            self.x_axis_signals.pop(tab_idx)

        self.tab_layouts = {}
        new_i = 0
        for i, layout in enumerate(layouts):
            if i == tab_idx:
                continue
            self.tab_layouts[new_i] = layout
            new_i += 1

    def move_tab(self, from_idx: int, to_idx: int):
        """Move a tab from one index to another"""
        n = len(self.plot_tabs)
        if (from_idx < 0 or from_idx >= n or to_idx < 0 or 
            to_idx >= n or from_idx == to_idx):
            return

        def _move_list(lst):
            item = lst.pop(from_idx)
            lst.insert(to_idx, item)

        _move_list(self.plot_tabs)
        if len(self.axes_arrays) == n:
            _move_list(self.axes_arrays)
        if len(self.assigned_signals) == n:
            _move_list(self.assigned_signals)
        if len(self.tuple_signals) == n:
            _move_list(self.tuple_signals)
        if len(self.tuple_mode) == n:
            _move_list(self.tuple_mode)
        if len(self.x_axis_signals) == n:
            _move_list(self.x_axis_signals)

        layouts = [self.tab_layouts.get(i, {"rows": 1, "cols": 1}) for i in range(n)]
        item = layouts.pop(from_idx)
        layouts.insert(to_idx, item)
        self.tab_layouts = {i: layouts[i] for i in range(len(layouts))}

    def insert_tab(self, index: int, rows: int = 1, cols: int = 1,
                   assigned_signals: Optional[List[List[Dict]]] = None):
        """Insert a new tab at the given index"""
        fig = make_subplots(
            rows=rows,
            cols=cols,
            subplot_titles=[f"Subplot {i+1}" for i in range(rows * cols)],
            vertical_spacing=0.18 if rows > 1 else 0.1,
            horizontal_spacing=0.15 if cols > 1 else 0.1,
        )

        fig.update_layout(
            paper_bgcolor="#16213e",
            plot_bgcolor="#1a1a2e",
            font=dict(color="#e8e8e8", size=10),
            height=max(500, 280 * rows),
            showlegend=True,
            legend=dict(
                bgcolor="rgba(22, 33, 62, 0.9)",
                bordercolor="#333",
                borderwidth=1,
                font=dict(size=10),
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
            margin=dict(l=70, r=50, t=80, b=70),
        )

        for i in range(1, rows * cols + 1):
            r = (i - 1) // cols + 1
            c = (i - 1) % cols + 1
            fig.update_xaxes(
                gridcolor="#333",
                zerolinecolor="#444",
                title_text="Time",
                title_font=dict(size=11),
                tickfont=dict(size=9),
                row=r, col=c,
            )
            fig.update_yaxes(
                gridcolor="#333",
                zerolinecolor="#444",
                title_text="Value",
                title_font=dict(size=11),
                tickfont=dict(size=9),
                row=r, col=c,
            )

        if index < 0:
            index = 0
        if index > len(self.plot_tabs):
            index = len(self.plot_tabs)

        self.plot_tabs.insert(index, fig)
        self.axes_arrays.insert(
            index,
            [(row, col) for row in range(1, rows + 1) for col in range(1, cols + 1)],
        )
        if assigned_signals is None:
            self.assigned_signals.insert(index, [[] for _ in range(rows * cols)])
        else:
            self.assigned_signals.insert(index, assigned_signals)
        self.tuple_signals.insert(index, [[] for _ in range(rows * cols)])
        self.tuple_mode.insert(index, [False for _ in range(rows * cols)])
        self.x_axis_signals.insert(index, ["Time" for _ in range(rows * cols)])

        new_layouts = {}
        i = 0
        for old_i in range(len(self.plot_tabs)):
            if old_i == index:
                new_layouts[i] = {"rows": rows, "cols": cols}
            else:
                src = old_i if old_i < index else old_i - 1
                new_layouts[i] = self.tab_layouts.get(src, {"rows": 1, "cols": 1})
            i += 1

        self.tab_layouts = new_layouts

    def set_subplot_title(self, tab_idx: int, subplot_idx: int, title: str):
        """Set a custom title for a subplot"""
        key = (tab_idx, subplot_idx)
        if title:
            self.subplot_titles[key] = title
        else:
            self.subplot_titles.pop(key, None)

    def get_subplot_title(self, tab_idx: int, subplot_idx: int) -> str:
        """Get the custom title for a subplot"""
        key = (tab_idx, subplot_idx)
        return self.subplot_titles.get(key, "")

    def set_axis_signal(self, tab_idx: int, subplot_idx: int, signal_name: str):
        """Set the X-axis signal for a subplot"""
        if tab_idx >= len(self.x_axis_signals):
            return
        if subplot_idx >= len(self.x_axis_signals[tab_idx]):
            return
        self.x_axis_signals[tab_idx][subplot_idx] = signal_name

    def get_axis_signal(self, tab_idx: int, subplot_idx: int) -> str:
        """Get the X-axis signal for a subplot"""
        if tab_idx >= len(self.x_axis_signals):
            return "Time"
        if subplot_idx >= len(self.x_axis_signals[tab_idx]):
            return "Time"
        return self.x_axis_signals[tab_idx][subplot_idx]

    def set_performance_mode(self, use_webgl: bool = True, max_points: int = 50000):
        """Configure performance settings"""
        self.use_webgl = use_webgl
        self.max_points = max_points
        print(f"⚙️ Performance mode: WebGL={use_webgl}, MaxPoints={max_points}")

    def get_performance_info(self) -> Dict:
        """Get current performance settings"""
        return {
            'use_webgl': self.use_webgl,
            'max_points': self.max_points,
            'auto_decimate': self.auto_decimate,
            'webgl_threshold': WEBGL_THRESHOLD,
        }
