"""
PlotManager - Handles plotting and visualization with Plotly
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from typing import List, Dict, Optional, Tuple
import pandas as pd
from helpers import get_text_direction_style, get_text_direction_attr

# Color palette
SIGNAL_COLORS = [
    "#2E86AB",
    "#A23B72",
    "#F18F01",
    "#C73E1D",
    "#3B1F2B",
    "#95C623",
    "#5E60CE",
    "#4EA8DE",
    "#48BFE3",
    "#64DFDF",
    "#72EFDD",
    "#80FFDB",
    "#E63946",
    "#F4A261",
    "#2A9D8F",
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
        self.custom_y_labels = {}  # dict: (tab_idx, subplot_idx) -> label_text
        self.subplot_titles = {}  # dict: (tab_idx, subplot_idx) -> title_text
        self.subplot_metadata = (
            {}
        )  # dict: (tab_idx, subplot_idx) -> {caption, description}
        self.tuple_signals = []
        self.tuple_mode = []
        self.x_axis_signals = []  # list of lists: tab_idx -> [signal_names per subplot]
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
            rows=rows,
            cols=cols,
            subplot_titles=[f"Subplot {i+1}" for i in range(rows * cols)],
            vertical_spacing=0.18 if rows > 1 else 0.1,  # More space for labels
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

        if not any(
            df is not None and not df.empty for df in self.app.data_manager.data_tables
        ):
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

            if (
                subplot_idx < len(self.tuple_mode[tab_idx])
                and self.tuple_mode[tab_idx][subplot_idx]
            ):
                self.plot_tuple_signals(fig, tab_idx, subplot_idx, row, col)
            else:
                self.plot_regular_signals(fig, tab_idx, subplot_idx, row, col, assigned)

        # Update layout with proper spacing
        layout = self.tab_layouts.get(tab_idx, {"rows": 1, "cols": 1})
        rows = layout.get("rows", 1)

        fig.update_layout(
            height=max(500, 280 * rows), showlegend=True, hovermode="closest"
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
        """Plot regular signals"""
        if not assigned:
            return

        x_axis_signal = "Time"
        if subplot_idx < len(self.x_axis_signals[tab_idx]):
            x_axis_signal = self.x_axis_signals[tab_idx][subplot_idx]

        color_idx = 0

        for sig_info in assigned:
            csv_idx = sig_info.get("csv_idx", -1)
            signal_name = sig_info.get("signal", "")

            if csv_idx == -1:
                time_data, signal_data = self.app.signal_operations.get_signal_data(
                    signal_name
                )
            else:
                # Request decimated data from DataManager (server-side LOD + cache)
                time_data, signal_data = self.app.data_manager.get_signal_data_ext(
                    csv_idx,
                    signal_name,
                    max_points=50000,
                    start=None,
                    end=None,
                    use_cache=True,
                )

            if len(time_data) == 0:
                continue

            # Get X-axis data
            if x_axis_signal == "Time":
                x_data = time_data
            else:
                x_csv_idx = sig_info.get("x_csv_idx", csv_idx)
                x_data, _ = self.app.data_manager.get_signal_data(
                    x_csv_idx, x_axis_signal
                )
                if len(x_data) == 0:
                    x_data = time_data

            # If X-axis is not Time, request decimated X axis as well
            max_points = 50000
            if x_axis_signal != "Time":
                x_data, _ = self.app.data_manager.get_signal_data_ext(
                    x_csv_idx,
                    x_axis_signal,
                    max_points=max_points,
                    start=None,
                    end=None,
                    use_cache=True,
                )

            # Get color
            color = sig_info.get("color", SIGNAL_COLORS[color_idx % len(SIGNAL_COLORS)])
            line_width = sig_info.get("line_width", 1.5)
            # Add trace: use WebGL Scattergl for large traces for performance
            use_scattergl = len(x_data) > 20000
            trace_cls = go.Scattergl if use_scattergl else go.Scatter
            fig.add_trace(
                trace_cls(
                    x=x_data,
                    y=signal_data,
                    mode="lines",
                    name=f"{signal_name}",
                    line=dict(color=color, width=line_width),
                    showlegend=True,
                    hovertemplate=f"<b>{signal_name}</b><br>X: %{{x:.4f}}<br>Y: %{{y:.4f}}<extra></extra>",
                ),
                row=row,
                col=col,
            )

            color_idx += 1

    def plot_tuple_signals(
        self, fig, tab_idx: int, subplot_idx: int, row: int, col: int
    ):
        """Plot X-Y pair signals (tuple mode)"""
        if subplot_idx >= len(self.tuple_signals[tab_idx]):
            return

        tuples = self.tuple_signals[tab_idx][subplot_idx]
        if not tuples:
            return

        color_idx = 0

        for tuple_info in tuples:
            x_sig = tuple_info.get("x_signal", {})
            y_sig = tuple_info.get("y_signal", {})
            label = tuple_info.get("label", "")
            color = tuple_info.get(
                "color", SIGNAL_COLORS[color_idx % len(SIGNAL_COLORS)]
            )

            if x_sig.get("csv_idx", -1) == -1:
                x_time, x_data = self.app.signal_operations.get_signal_data(
                    x_sig.get("signal", "")
                )
            else:
                x_time, x_data = self.app.data_manager.get_signal_data(
                    x_sig.get("csv_idx", 0), x_sig.get("signal", "")
                )

            if y_sig.get("csv_idx", -1) == -1:
                y_time, y_data = self.app.signal_operations.get_signal_data(
                    y_sig.get("signal", "")
                )
            else:
                y_time, y_data = self.app.data_manager.get_signal_data(
                    y_sig.get("csv_idx", 0), y_sig.get("signal", "")
                )

            if len(x_data) == 0 or len(y_data) == 0:
                continue

            if len(x_data) != len(y_data):
                min_len = min(len(x_data), len(y_data))
                x_data = x_data[:min_len]
                y_data = y_data[:min_len]

            max_points = 50000
            # Ask DataManager for decimated pair if large
            if len(x_data) > max_points:
                x_data, y_data = self.app.data_manager.get_signal_data_ext(
                    csv_idx,
                    signal_name,
                    max_points=max_points,
                    start=None,
                    end=None,
                    use_cache=True,
                )

            use_scattergl = len(x_data) > 20000
            trace_cls = go.Scattergl if use_scattergl else go.Scatter
            fig.add_trace(
                trace_cls(
                    x=x_data,
                    y=y_data,
                    mode="lines",
                    name=label,
                    line=dict(color=color, width=1.5),
                    showlegend=True,
                ),
                row=row,
                col=col,
            )

            color_idx += 1

    def downsample_data(self, x_data, y_data, max_points: int):
        """Downsample data for better performance"""
        # If already small enough, return as-is
        if len(x_data) <= max_points:
            return x_data, y_data

        x = np.asarray(x_data)
        y = np.asarray(y_data)
        n = len(x)

        # Ensure at least first and last are preserved
        if max_points < 3:
            max_points = 3

        # Number of interior samples (excluding first and last)
        interior_target = max_points - 2

        # We'll produce up to 2 points per bin (min and max) to preserve peaks
        bins = max(1, interior_target // 2)

        # Compute bin edges excluding first and last points
        idx = np.linspace(1, n - 1, bins + 1, dtype=int)

        out_x = [x[0]]
        out_y = [y[0]]

        for i in range(len(idx) - 1):
            s = idx[i]
            e = idx[i + 1]
            if e <= s:
                continue
            seg_y = y[s:e]
            seg_x = x[s:e]
            # find local min and max within segment
            local_min_i = np.argmin(seg_y) + s
            local_max_i = np.argmax(seg_y) + s
            # append in time order to preserve waveform
            if local_min_i < local_max_i:
                out_x.append(x[local_min_i])
                out_y.append(y[local_min_i])
                out_x.append(x[local_max_i])
                out_y.append(y[local_max_i])
            else:
                out_x.append(x[local_max_i])
                out_y.append(y[local_max_i])
                out_x.append(x[local_min_i])
                out_y.append(y[local_min_i])

        out_x.append(x[-1])
        out_y.append(y[-1])

        # Trim if we slightly exceeded max_points
        if len(out_x) > max_points:
            # uniformly sample the assembled decimated points
            inds = np.linspace(0, len(out_x) - 1, max_points, dtype=int)
            out_x = list(np.asarray(out_x)[inds])
            out_y = list(np.asarray(out_y)[inds])

        return np.asarray(out_x), np.asarray(out_y)

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

    def get_tab_figure(self, tab_idx: int = 0):
        """Return the Plotly figure for a tab (or None)."""
        if 0 <= tab_idx < len(self.plot_tabs):
            return self.plot_tabs[tab_idx]
        return None

    def get_tab_html(self, tab_idx: int = 0) -> str:
        """Return a self-contained HTML string for the tab's Plotly figure.

        The returned HTML embeds the Plotly.js library so it works offline.
        """
        fig = self.get_tab_figure(tab_idx)
        if fig is None:
            return ""

        # Use Plotly's to_html to create a full, self-contained HTML page
        try:
            html = fig.to_html(full_html=True, include_plotlyjs=True)
            return html
        except Exception:
            # As a fallback, return an empty page
            return "<html><body><h3>Unable to render plot</h3></body></html>"

    def get_all_tabs_html(self) -> str:
        """Return a single HTML page that contains all tab figures and a simple tabbed UI.

        Each tab's Plotly div is embedded; Plotly.js is included once for the first figure.
        """
        if not self.plot_tabs:
            return "<html><body><h3>No plots available</h3></body></html>"

        parts = []
        # collect metadata strings per tab to include below each fragment
        tab_meta = []
        # Collect per-tab HTML fragments (not full HTML)
        for i, fig in enumerate(self.plot_tabs):
            try:
                # include_plotlyjs only for the first fragment
                fragment = fig.to_html(full_html=False, include_plotlyjs=(i == 0))
            except Exception:
                fragment = f"<div><h4>Tab {i+1}: Unable to render</h4></div>"
            parts.append(fragment)

            # Build metadata HTML for this tab (per-subplot captions/descriptions)
            meta_parts = ["<div class='tab-metadata' style='margin-top:8px;'>"]
            # find number of subplots from axes_arrays
            axes = self.axes_arrays[i] if i < len(self.axes_arrays) else []
            for subplot_idx in range(len(axes)):
                key = (i, subplot_idx)
                title = self.subplot_titles.get(key, f"Subplot {subplot_idx+1}")
                meta = self.subplot_metadata.get(key, {})
                caption = meta.get("caption", "") if isinstance(meta, dict) else ""
                description = (
                    meta.get("description", "") if isinstance(meta, dict) else ""
                )
                # preserve multi-line text using pre-wrap with RTL support
                caption_style = f"white-space:pre-wrap;margin:6px 0;font-style:italic;color:#cbd5e1;{get_text_direction_style(caption)}"
                caption_html = (
                    f"<div dir='{get_text_direction_attr(caption)}' style='{caption_style}'>{self._escape_html(caption)}</div>"
                    if caption
                    else ""
                )
                description_style = f"white-space:pre-wrap;margin:6px 0;color:#e2e8f0;{get_text_direction_style(description)}"
                description_html = (
                    f"<div dir='{get_text_direction_attr(description)}' style='{description_style}'>{self._escape_html(description)}</div>"
                    if description
                    else ""
                )
                meta_parts.append(
                    f"<h4 style='margin:6px 0 2px 0;color:#e6eef8;'>{self._escape_html(title)}</h4>"
                )
                if caption_html:
                    meta_parts.append(caption_html)
                if description_html:
                    meta_parts.append(description_html)

            meta_parts.append("</div>")
            tab_meta.append("\n".join(meta_parts))

        # Build a simple tab UI: buttons to switch visible divs
        html_parts = [
            "<!doctype html>",
            "<html>",
            "<head>",
            "<meta charset='utf-8'/>",
            "<meta http-equiv='Content-Type' content='text/html; charset=utf-8'/>",
            "<style>",
            "body{background:#0f1724;color:#e6eef8;font-family:Arial,Helvetica,sans-serif}",
            ".tabs{margin:10px 0}",
            ".tabbtn{background:#1e293b;color:#fff;border:none;padding:8px 12px;margin-right:6px;cursor:pointer;border-radius:4px}",
            ".tabbtn.active{background:#2563eb}",
            ".plot-container{margin-top:12px}",
            "div[style*='direction: rtl']{direction:rtl;text-align:right}",
            "div[style*='direction: ltr']{direction:ltr;text-align:left}",
            "</style>",
            "</head>",
            "<body>",
            "<div style='padding:12px'>",
            "<h2>Signal Viewer - Plots</h2>",
            "<div class='tabs' id='tabs'>",
        ]

        # Tab buttons
        for i in range(len(parts)):
            html_parts.append(
                f"<button class='tabbtn{' active' if i==0 else ''}' onclick='showTab({i})'>Tab {i+1}</button>"
            )

        html_parts.append("</div>")

        # Add each fragment wrapped in a container with an id
        for i, frag in enumerate(parts):
            html_parts.append(
                f"<div id='tab-{i}' class='plot-container' style='display:{'block' if i==0 else 'none'}'>"
            )
            html_parts.append(frag)
            # append metadata HTML block for this tab
            if i < len(tab_meta):
                html_parts.append(tab_meta[i])
            html_parts.append("</div>")

        # JS to switch tabs
        html_parts.extend(
            [
                "<script>",
                "function showTab(i){",
                "  const n = %d;" % len(parts),
                "  for(let j=0;j<n;j++){",
                "    document.getElementById('tab-'+j).style.display = (j===i)?'block':'none';",
                "    document.getElementsByClassName('tabbtn')[j].classList.toggle('active', j===i);",
                "  }",
                "}",
                "</script>",
                "</div>",
                "</body>",
                "</html>",
            ]
        )

        return "\n".join(html_parts)

    def _escape_html(self, text: str) -> str:
        """Simple HTML escape to prevent breaking the generated page."""
        if not isinstance(text, str):
            return ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    def set_subplot_metadata(
        self, tab_idx: int, subplot_idx: int, caption: str = "", description: str = ""
    ):
        key = (tab_idx, subplot_idx)
        self.subplot_metadata[key] = {
            "caption": caption or "",
            "description": description or "",
        }

    def get_subplot_metadata(self, tab_idx: int, subplot_idx: int) -> Dict:
        return self.subplot_metadata.get((tab_idx, subplot_idx), {})

    def remove_tab(self, tab_idx: int):
        """Remove a tab and its associated state.

        Safely removes entries from all internal lists and rebuilds `tab_layouts`.
        """
        if tab_idx < 0 or tab_idx >= len(self.plot_tabs):
            return

        # snapshot existing layouts to rebuild after removal
        layouts = [
            self.tab_layouts.get(i, {"rows": 1, "cols": 1})
            for i in range(len(self.plot_tabs))
        ]

        # remove parallel structures
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

        # rebuild tab_layouts sequentially excluding removed index
        self.tab_layouts = {}
        new_i = 0
        for i, l in enumerate(layouts):
            if i == tab_idx:
                continue
            self.tab_layouts[new_i] = l
            new_i += 1

    def move_tab(self, from_idx: int, to_idx: int):
        """Move a tab from one index to another, preserving all parallel structures.

        If indices are out-of-range or equal, the call is a no-op.
        """
        n = len(self.plot_tabs)
        if (
            from_idx < 0
            or from_idx >= n
            or to_idx < 0
            or to_idx >= n
            or from_idx == to_idx
        ):
            return

        # move in each parallel list
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

        # rebuild tab_layouts using the preserved order
        layouts = [self.tab_layouts.get(i, {"rows": 1, "cols": 1}) for i in range(n)]
        item = layouts.pop(from_idx)
        layouts.insert(to_idx, item)
        self.tab_layouts = {i: layouts[i] for i in range(len(layouts))}

    def insert_tab(
        self,
        index: int,
        rows: int = 1,
        cols: int = 1,
        assigned_signals: Optional[List[List[Dict]]] = None,
    ):
        """Insert a new tab at the given index.

        `assigned_signals` is expected to be a list of lists matching rows*cols length;
        each inner list contains signal_info dicts for that subplot.
        """
        # Build figure similarly to create_tab but insert at index
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

        # Insert into parallel lists
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

        # rebuild tab_layouts
        new_layouts = {}
        i = 0
        for old_i in range(len(self.plot_tabs)):
            if old_i == index:
                new_layouts[i] = {"rows": rows, "cols": cols}
            else:
                # try to take from existing mapping (shifted)
                src = old_i if old_i < index else old_i - 1
                new_layouts[i] = self.tab_layouts.get(src, {"rows": 1, "cols": 1})
            i += 1

        self.tab_layouts = new_layouts

    def set_subplot_title(self, tab_idx: int, subplot_idx: int, title: str):
        """Set a custom title for a subplot."""
        key = (tab_idx, subplot_idx)
        if title:
            self.subplot_titles[key] = title
        else:
            self.subplot_titles.pop(key, None)

    def get_subplot_title(self, tab_idx: int, subplot_idx: int) -> str:
        """Get the custom title for a subplot, or empty string if not set."""
        key = (tab_idx, subplot_idx)
        return self.subplot_titles.get(key, "")

    def set_axis_signal(self, tab_idx: int, subplot_idx: int, signal_name: str):
        """Set the X-axis signal for a subplot. Use 'Time' for the default time axis."""
        if tab_idx >= len(self.x_axis_signals):
            return
        if subplot_idx >= len(self.x_axis_signals[tab_idx]):
            return
        self.x_axis_signals[tab_idx][subplot_idx] = signal_name

    def get_axis_signal(self, tab_idx: int, subplot_idx: int) -> str:
        """Get the X-axis signal for a subplot."""
        if tab_idx >= len(self.x_axis_signals):
            return "Time"
        if subplot_idx >= len(self.x_axis_signals[tab_idx]):
            return "Time"
        return self.x_axis_signals[tab_idx][subplot_idx]
