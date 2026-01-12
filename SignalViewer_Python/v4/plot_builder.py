"""
Signal Viewer Pro v4.0 - Plot Builder
=====================================
Efficient Plotly figure creation with per-subplot legends.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from config import THEMES, SIGNAL_COLORS, MAX_ROWS, MAX_COLS
from data_manager import data_manager
from state import parse_signal_key


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
    ) -> go.Figure:
        """
        Build a complete figure with all subplots and signals.
        Each subplot has its own legend.
        """
        rows = layout_config.get("rows", 1)
        cols = layout_config.get("cols", 1)
        theme = settings.get("theme", "dark")
        link_axes = settings.get("link_axes", True)
        
        colors = THEMES.get(theme, THEMES["dark"])
        total_subplots = rows * cols
        
        # Create subplot titles (will show legend info)
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
                    
                    # Get color for this signal
                    color = SIGNAL_COLORS[sig_idx % len(SIGNAL_COLORS)]
                    
                    # Get CSV name for legend
                    csv_info = data_manager.csv_files.get(csv_id, {})
                    csv_name = csv_info.get("name", csv_id)
                    # Shorten CSV name
                    if len(csv_name) > 12:
                        csv_name = csv_name[:10] + ".."
                    
                    # Create trace with legendgroup for per-subplot legend
                    fig.add_trace(
                        go.Scattergl(
                            x=t,
                            y=y,
                            mode='lines',
                            name=f"{sig_name}",
                            legendgroup=f"subplot_{sp_idx}",
                            legendgrouptitle_text=f"Subplot {sp_idx + 1}",
                            showlegend=True,
                            line=dict(color=color, width=1.5),
                            hovertemplate=(
                                f"<b>{sig_name}</b> ({csv_name})<br>"
                                f"T: %{{x:.4f}}<br>"
                                f"V: %{{y:.4f}}"
                                f"<extra></extra>"
                            ),
                        ),
                        row=row,
                        col=col,
                    )
                except Exception as e:
                    print(f"Error loading signal {sig_key}: {e}")
        
        # Configure layout
        fig.update_layout(
            template="plotly_dark" if theme == "dark" else "plotly_white",
            paper_bgcolor=colors["bg_plot"],
            plot_bgcolor=colors["bg_plot"],
            margin=dict(l=60, r=20, t=40, b=50),
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02,
                font=dict(size=10),
                bgcolor="rgba(0,0,0,0.3)",
                bordercolor=colors["border"],
                borderwidth=1,
                tracegroupgap=10,
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
            bg_color = "rgba(78, 168, 222, 0.05)" if is_selected else colors["bg_plot"]
            
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
        
        # Add cursor line if visible
        if cursor_x is not None:
            shapes = []
            for i in range(total_subplots):
                xref = f"x{i+1}" if i > 0 else "x"
                yref = f"y{i+1} domain" if i > 0 else "y domain"
                
                shapes.append(
                    dict(
                        type="line",
                        xref=xref,
                        yref=yref,
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
            fig.update_layout(shapes=shapes)
        
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
                
                # Interpolate value at cursor_x
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


# Global instance
plot_builder = PlotBuilder()
