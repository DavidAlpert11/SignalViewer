"""
Signal Viewer Pro v4.0 - Plot Builder
=====================================
Efficient Plotly figure creation with proper legend and cursor annotations.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
from typing import Dict, List, Optional, Tuple, Any
from config import THEMES, SIGNAL_COLORS, MAX_ROWS, MAX_COLS
from data_manager import data_manager
from state import parse_signal_key


def get_unique_csv_display_name(csv_id: str, all_csv_files: Dict) -> str:
    """Get a unique display name for a CSV, handling duplicates."""
    csv_info = all_csv_files.get(csv_id, {})
    csv_name = csv_info.get("name", csv_id)
    csv_path = csv_info.get("path", "")
    
    # Check if there are other CSVs with the same filename
    same_name_csvs = [
        cid for cid, info in all_csv_files.items()
        if info.get("name") == csv_name and cid != csv_id
    ]
    
    if same_name_csvs:
        # Add parent folder to distinguish
        parent = os.path.basename(os.path.dirname(csv_path))
        if parent:
            return f"{parent}/{csv_name}"
    
    return csv_name


class PlotBuilder:
    """Builds Plotly figures efficiently."""
    
    def __init__(self):
        self._cache: Dict[str, go.Figure] = {}
    
    def build_figure(
        self,
        assignments: Dict[str, List[str]],
        layout_config: Dict,
        settings: Dict,
        cursor_x: Optional[float] = None,
        selected_subplot: int = 0,
        signal_props: Optional[Dict] = None,
    ) -> go.Figure:
        """
        Build a complete figure with all subplots and signals.
        Individual legend items, proper CSV naming, and cursor annotations.
        """
        rows = layout_config.get("rows", 1)
        cols = layout_config.get("cols", 1)
        theme = settings.get("theme", "dark")
        link_axes = settings.get("link_axes", True)
        
        colors = THEMES.get(theme, THEMES["dark"])
        total_subplots = rows * cols
        signal_props = signal_props or {}
        
        # Get all CSV files for naming
        all_csv_files = data_manager.csv_files
        
        # Check for duplicate signal names across CSVs
        signal_name_counts = {}
        for sp_key, sig_keys in assignments.items():
            for sig_key in sig_keys:
                _, sig_name = parse_signal_key(sig_key)
                signal_name_counts[sig_name] = signal_name_counts.get(sig_name, 0) + 1
        
        # Create subplot titles
        subplot_titles = []
        for i in range(total_subplots):
            sig_count = len(assignments.get(str(i), []))
            subplot_titles.append(f"Subplot {i+1}" if sig_count > 0 else f"Subplot {i+1} (empty)")
        
        # Create subplots
        fig = make_subplots(
            rows=rows,
            cols=cols,
            shared_xaxes=link_axes,
            vertical_spacing=0.12,
            horizontal_spacing=0.08,
            subplot_titles=subplot_titles,
        )
        
        # Track cursor values for annotations
        cursor_annotations = []
        
        # Add traces for each subplot
        for sp_idx in range(total_subplots):
            sp_key = str(sp_idx)
            signal_keys = assignments.get(sp_key, [])
            
            row = sp_idx // cols + 1
            col = sp_idx % cols + 1
            
            for sig_idx, sig_key in enumerate(signal_keys):
                csv_id, sig_name = parse_signal_key(sig_key)
                
                try:
                    t, y = data_manager.get_downsampled_data(csv_id, sig_name)
                    
                    # Get signal properties (color, width, etc.)
                    props = signal_props.get(sig_key, {})
                    color = props.get("color", SIGNAL_COLORS[sig_idx % len(SIGNAL_COLORS)])
                    line_width = props.get("width", 1.5)
                    scale = props.get("scale", 1.0)
                    offset = props.get("offset", 0.0)
                    display_name = props.get("display_name")
                    
                    # Apply scale and offset
                    y = y * scale + offset
                    
                    # Build legend name with CSV context if needed
                    csv_display = get_unique_csv_display_name(csv_id, all_csv_files)
                    if len(csv_display) > 15:
                        csv_display = csv_display[:13] + ".."
                    
                    # If signal name appears in multiple CSVs, show CSV name
                    if signal_name_counts.get(sig_name, 0) > 1:
                        legend_name = f"{sig_name} ({csv_display})"
                    else:
                        legend_name = sig_name
                    
                    # Use custom display name if set
                    if display_name:
                        legend_name = display_name
                    
                    # Add subplot prefix if multiple subplots
                    if total_subplots > 1:
                        legend_name = f"[{sp_idx+1}] {legend_name}"
                    
                    # Create trace - NO legendgroup so each signal toggles independently
                    fig.add_trace(
                        go.Scattergl(
                            x=t,
                            y=y,
                            mode='lines',
                            name=legend_name,
                            showlegend=True,
                            line=dict(color=color, width=line_width),
                            hovertemplate=(
                                f"<b>{sig_name}</b> ({csv_display})<br>"
                                f"T: %{{x:.4f}}<br>"
                                f"V: %{{y:.4f}}"
                                f"<extra></extra>"
                            ),
                        ),
                        row=row,
                        col=col,
                    )
                    
                    # Calculate cursor value for annotation
                    if cursor_x is not None and len(t) > 1:
                        value = np.interp(cursor_x, t, y)
                        cursor_annotations.append({
                            "subplot": sp_idx,
                            "signal": sig_name,
                            "value": value,
                            "color": color,
                            "row": row,
                            "col": col,
                        })
                        
                except Exception as e:
                    print(f"Error loading signal {sig_key}: {e}")
        
        # Configure layout
        fig.update_layout(
            template="plotly_dark" if theme == "dark" else "plotly_white",
            paper_bgcolor=colors["bg_plot"],
            plot_bgcolor=colors["bg_plot"],
            margin=dict(l=60, r=150, t=40, b=50),  # More space for legend
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02,
                font=dict(size=10),
                bgcolor="rgba(0,0,0,0.3)" if theme == "dark" else "rgba(255,255,255,0.8)",
                bordercolor=colors["border"],
                borderwidth=1,
                itemclick="toggle",  # Single click toggles
                itemdoubleclick="toggleothers",  # Double click isolates
            ),
            hovermode="x unified",
        )
        
        # Configure axes with subplot highlighting
        for i in range(total_subplots):
            x_axis = f"xaxis{i+1}" if i > 0 else "xaxis"
            y_axis = f"yaxis{i+1}" if i > 0 else "yaxis"
            
            is_selected = (i == selected_subplot)
            border_color = colors["accent"] if is_selected else colors["grid"]
            border_width = 3 if is_selected else 1
            
            fig.update_layout(**{
                x_axis: dict(
                    showgrid=True,
                    gridcolor=colors["grid"],
                    linecolor=border_color,
                    linewidth=border_width,
                    zeroline=False,
                    tickfont=dict(size=10, color=colors["text_secondary"]),
                    mirror=True,
                ),
                y_axis: dict(
                    showgrid=True,
                    gridcolor=colors["grid"],
                    linecolor=border_color,
                    linewidth=border_width,
                    zeroline=False,
                    tickfont=dict(size=10, color=colors["text_secondary"]),
                    mirror=True,
                ),
            })
        
        # Add cursor line and value annotations
        if cursor_x is not None:
            shapes = []
            annotations = []
            
            for i in range(total_subplots):
                xref = f"x{i+1}" if i > 0 else "x"
                yref = f"y{i+1}" if i > 0 else "y"
                yref_domain = f"y{i+1} domain" if i > 0 else "y domain"
                
                # Cursor line
                shapes.append(
                    dict(
                        type="line",
                        xref=xref,
                        yref=yref_domain,
                        x0=cursor_x,
                        x1=cursor_x,
                        y0=0,
                        y1=1,
                        line=dict(
                            color=colors["accent_secondary"], 
                            width=2, 
                            dash="dash"
                        ),
                    )
                )
            
            # Add value annotations near cursor for each signal
            for ann in cursor_annotations:
                sp_idx = ann["subplot"]
                xref = f"x{sp_idx+1}" if sp_idx > 0 else "x"
                yref = f"y{sp_idx+1}" if sp_idx > 0 else "y"
                
                annotations.append(
                    dict(
                        x=cursor_x,
                        y=ann["value"],
                        xref=xref,
                        yref=yref,
                        text=f"{ann['signal']}: {ann['value']:.3f}",
                        showarrow=True,
                        arrowhead=0,
                        arrowsize=0.5,
                        arrowwidth=1,
                        arrowcolor=ann["color"],
                        ax=40,
                        ay=0,
                        font=dict(size=9, color=ann["color"]),
                        bgcolor="rgba(0,0,0,0.7)" if theme == "dark" else "rgba(255,255,255,0.9)",
                        bordercolor=ann["color"],
                        borderwidth=1,
                        borderpad=2,
                    )
                )
            
            fig.update_layout(shapes=shapes, annotations=annotations)
        
        return fig
    
    def build_empty_figure(self, theme: str = "dark") -> go.Figure:
        """Build an empty placeholder figure."""
        colors = THEMES.get(theme, THEMES["dark"])
        
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark" if theme == "dark" else "plotly_white",
            paper_bgcolor=colors["bg_plot"],
            plot_bgcolor=colors["bg_plot"],
            xaxis=dict(
                visible=True,
                showgrid=True,
                gridcolor=colors["grid"],
                zeroline=False,
            ),
            yaxis=dict(
                visible=True,
                showgrid=True,
                gridcolor=colors["grid"],
                zeroline=False,
            ),
            annotations=[
                dict(
                    text="📂 Load CSV files and assign signals to plot",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=16, color=colors["text_secondary"]),
                )
            ],
            margin=dict(l=60, r=20, t=40, b=50),
        )
        return fig
    
    def get_cursor_values(
        self,
        cursor_x: float,
        assignments: Dict[str, List[str]],
        subplot: int = 0,
    ) -> List[Dict]:
        """Get signal values at cursor position for a specific subplot."""
        values = []
        sp_key = str(subplot)
        signal_keys = assignments.get(sp_key, [])
        
        for sig_key in signal_keys:
            csv_id, sig_name = parse_signal_key(sig_key)
            
            try:
                t, y = data_manager.get_signal_data(csv_id, sig_name)
                
                if len(t) > 1:
                    value = np.interp(cursor_x, t, y)
                    values.append({
                        "signal": sig_name,
                        "value": float(value),
                        "key": sig_key,
                    })
            except Exception:
                pass
        
        return values
    
    def build_xy_figure(
        self,
        x_signal_key: str,
        y_signal_keys: List[str],
        settings: Dict,
        signal_props: Optional[Dict] = None,
    ) -> go.Figure:
        """Build an X-Y correlation plot."""
        theme = settings.get("theme", "dark")
        colors = THEMES.get(theme, THEMES["dark"])
        signal_props = signal_props or {}
        
        fig = go.Figure()
        
        # Get X signal data
        x_csv_id, x_sig_name = parse_signal_key(x_signal_key)
        try:
            x_t, x_data = data_manager.get_signal_data(x_csv_id, x_sig_name)
        except Exception as e:
            print(f"Error loading X signal: {e}")
            return self.build_empty_figure(theme)
        
        # Add Y signals
        for i, y_key in enumerate(y_signal_keys):
            y_csv_id, y_sig_name = parse_signal_key(y_key)
            
            try:
                y_t, y_data = data_manager.get_signal_data(y_csv_id, y_sig_name)
                
                # Interpolate Y to X time base
                y_interp = np.interp(x_t, y_t, y_data)
                
                props = signal_props.get(y_key, {})
                color = props.get("color", SIGNAL_COLORS[i % len(SIGNAL_COLORS)])
                
                fig.add_trace(
                    go.Scattergl(
                        x=x_data,
                        y=y_interp,
                        mode='lines+markers',
                        name=y_sig_name,
                        marker=dict(size=3, color=color),
                        line=dict(color=color, width=1),
                    )
                )
            except Exception as e:
                print(f"Error loading Y signal {y_key}: {e}")
        
        fig.update_layout(
            template="plotly_dark" if theme == "dark" else "plotly_white",
            paper_bgcolor=colors["bg_plot"],
            plot_bgcolor=colors["bg_plot"],
            xaxis_title=x_sig_name,
            yaxis_title="Y Signals",
            showlegend=True,
            margin=dict(l=60, r=20, t=40, b=50),
        )
        
        return fig


# Global instance
plot_builder = PlotBuilder()
