"""
Signal Viewer Pro v4.0 - Plot Builder
=====================================
Efficient Plotly figure creation.
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
        self._cache_keys: List[str] = []
        self._max_cache = 10
    
    def build_figure(
        self,
        assignments: Dict[str, List[str]],  # {subplot_id: [signal_keys]}
        layout_config: Dict,                 # {rows, cols}
        settings: Dict,                      # {theme, link_axes, ...}
        cursor_x: Optional[float] = None,
        selected_subplot: int = 0,
    ) -> go.Figure:
        """
        Build a complete figure with all subplots and signals.
        
        Args:
            assignments: Signal assignments per subplot
            layout_config: Grid configuration
            settings: Display settings
            cursor_x: Cursor X position (optional)
            selected_subplot: Currently selected subplot index
            
        Returns:
            Plotly Figure object
        """
        rows = layout_config.get("rows", 1)
        cols = layout_config.get("cols", 1)
        theme = settings.get("theme", "dark")
        link_axes = settings.get("link_axes", True)
        
        colors = THEMES.get(theme, THEMES["dark"])
        
        # Create subplots
        fig = make_subplots(
            rows=rows,
            cols=cols,
            shared_xaxes=link_axes,
            vertical_spacing=0.08,
            horizontal_spacing=0.05,
        )
        
        # Track used colors per subplot
        color_indices = {}
        
        # Add traces for each subplot
        for sp_idx in range(rows * cols):
            sp_key = str(sp_idx)
            signal_keys = assignments.get(sp_key, [])
            
            row = sp_idx // cols + 1
            col = sp_idx % cols + 1
            
            color_indices[sp_idx] = 0
            
            for sig_key in signal_keys:
                csv_id, sig_name = parse_signal_key(sig_key)
                
                try:
                    t, y = data_manager.get_downsampled_data(csv_id, sig_name)
                    
                    # Get color
                    color = SIGNAL_COLORS[color_indices[sp_idx] % len(SIGNAL_COLORS)]
                    color_indices[sp_idx] += 1
                    
                    # Get CSV name for legend
                    csv_info = data_manager.csv_files.get(csv_id, {})
                    csv_name = csv_info.get("name", csv_id)[:10]
                    
                    fig.add_trace(
                        go.Scattergl(
                            x=t,
                            y=y,
                            mode='lines',
                            name=f"{sig_name} ({csv_name})",
                            line=dict(color=color, width=1.5),
                            hovertemplate=f"<b>{sig_name}</b><br>T: %{{x:.4f}}<br>V: %{{y:.4f}}<extra></extra>",
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
            margin=dict(l=50, r=20, t=30, b=50),
            showlegend=settings.get("show_legend", True),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
                font=dict(size=10),
            ),
            hovermode="x unified",
        )
        
        # Configure axes
        for i in range(rows * cols):
            x_axis = f"xaxis{i+1}" if i > 0 else "xaxis"
            y_axis = f"yaxis{i+1}" if i > 0 else "yaxis"
            
            is_selected = (i == selected_subplot)
            border_color = colors["accent"] if is_selected else colors["grid"]
            border_width = 2 if is_selected else 1
            
            fig.update_layout(**{
                x_axis: dict(
                    showgrid=settings.get("show_grid", True),
                    gridcolor=colors["grid"],
                    linecolor=border_color,
                    linewidth=border_width,
                    zeroline=False,
                    tickfont=dict(size=10),
                ),
                y_axis: dict(
                    showgrid=settings.get("show_grid", True),
                    gridcolor=colors["grid"],
                    linecolor=border_color,
                    linewidth=border_width,
                    zeroline=False,
                    tickfont=dict(size=10),
                ),
            })
        
        # Add cursor line if visible
        if cursor_x is not None:
            shapes = []
            for i in range(rows * cols):
                shapes.append(
                    dict(
                        type="line",
                        xref=f"x{i+1}" if i > 0 else "x",
                        yref=f"y{i+1} domain" if i > 0 else "y domain",
                        x0=cursor_x,
                        x1=cursor_x,
                        y0=0,
                        y1=1,
                        line=dict(color=colors["accent_secondary"], width=2, dash="dash"),
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
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            annotations=[
                dict(
                    text="Load CSV files and assign signals to plot",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=16, color=colors["text_secondary"]),
                )
            ],
            margin=dict(l=20, r=20, t=20, b=20),
        )
        return fig
    
    def get_cursor_values(
        self,
        cursor_x: float,
        assignments: Dict[str, List[str]],
        subplot: int = 0,
    ) -> List[Dict]:
        """Get signal values at cursor position."""
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
                        "value": value,
                        "key": sig_key,
                    })
            except Exception:
                pass
        
        return values


# Global instance
plot_builder = PlotBuilder()

