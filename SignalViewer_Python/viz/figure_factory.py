"""
Signal Viewer Pro - Figure Factory
===================================
Creates Plotly figures with subplots, traces, and cursor.
LOSSLESS: All data points are plotted.

INPUTS/OUTPUTS:
    create_figure(runs, derived_signals, view_state, signal_settings)
        -> (go.Figure, cursor_values dict)
    
    Subplot index mapping (1-based for Plotly):
        subplot_idx (0-based) -> (row, col) where:
            row = (subplot_idx // cols) + 1
            col = (subplot_idx % cols) + 1
        
        Example for 2x2 grid:
            subplot 0 -> row=1, col=1 (top-left)
            subplot 1 -> row=1, col=2 (top-right)
            subplot 2 -> row=2, col=1 (bottom-left)
            subplot 3 -> row=2, col=2 (bottom-right)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.models import Run, DerivedSignal, SubplotConfig, ViewState, SignalType, parse_signal_key, DERIVED_RUN_IDX
from core.naming import get_signal_label


# Signal colors
COLORS = [
    "#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#95C623",
    "#5E60CE", "#4EA8DE", "#48BFE3", "#64DFDF", "#72EFDD",
    "#E63946", "#F4A261", "#2A9D8F", "#80FFDB", "#3B1F2B",
]

# Theme definitions
THEMES = {
    "dark": {
        "bg": "#0d1117",
        "paper": "#161b22",
        "text": "#e6edf3",
        "grid": "#21262d",
        "border": "#30363d",
        "accent": "#58a6ff",
        "active_bg": "#1f2937",
    },
    "light": {
        "bg": "#ffffff",
        "paper": "#f6f8fa",
        "text": "#24292f",
        "grid": "#d8dee4",
        "border": "#d0d7de",
        "accent": "#0969da",
        "active_bg": "#e8f4fd",
    },
}


def subplot_idx_to_row_col(subplot_idx: int, cols: int) -> Tuple[int, int]:
    """
    Convert 0-based subplot index to 1-based (row, col) for Plotly.
    
    Canonical mapping used everywhere:
        row = (subplot_idx // cols) + 1
        col = (subplot_idx % cols) + 1
    """
    row = (subplot_idx // cols) + 1
    col = (subplot_idx % cols) + 1
    return row, col


def row_col_to_subplot_idx(row: int, col: int, cols: int) -> int:
    """
    Convert 1-based (row, col) to 0-based subplot index.
    """
    return (row - 1) * cols + (col - 1)


def create_empty_grid(rows: int, cols: int, theme_name: str = "dark") -> go.Figure:
    """
    Create an empty subplot grid with proper axes.
    Used to prove grid exists independent of signal logic.
    
    Args:
        rows: Number of rows
        cols: Number of columns
        theme_name: "dark" or "light"
        
    Returns:
        Empty Plotly figure with grid layout
    """
    theme = THEMES.get(theme_name, THEMES["dark"])
    height = max(700, 320 * rows)
    
    fig = make_subplots(
        rows=rows, cols=cols,
        shared_xaxes=True,
        vertical_spacing=0.08 if rows > 1 else 0.05,
        horizontal_spacing=0.05 if cols > 1 else 0.02,
        subplot_titles=[f"Subplot {i+1}" for i in range(rows * cols)],
    )
    
    # Apply base styling
    fig.update_layout(
        template="plotly_dark" if theme_name == "dark" else "plotly_white",
        paper_bgcolor=theme["paper"],
        plot_bgcolor=theme["bg"],
        font=dict(color=theme["text"], size=11),
        margin=dict(l=60, r=20, t=40, b=40),
        height=height,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
    )
    
    # Style each subplot
    for sp_idx in range(rows * cols):
        row, col = subplot_idx_to_row_col(sp_idx, cols)
        fig.update_xaxes(
            showgrid=True, gridcolor=theme["grid"],
            linecolor=theme["border"], linewidth=1,
            title_text="Time" if row == rows else "",
            row=row, col=col,
        )
        fig.update_yaxes(
            showgrid=True, gridcolor=theme["grid"],
            linecolor=theme["border"], linewidth=1,
            row=row, col=col,
        )
    
    print(f"[FIGURE] Created empty grid: {rows}x{cols} = {rows*cols} subplots, height={height}px", flush=True)
    return fig


def create_figure(
    runs: List[Run],
    derived_signals: Dict[str, DerivedSignal],
    view_state: ViewState,
    signal_settings: Dict[str, Dict],
) -> Tuple[go.Figure, Dict]:
    """
    Create the main plot figure.
    
    CANONICAL FIGURE CREATION:
        - Uses make_subplots(rows, cols) to create actual grid
        - Each trace bound to correct subplot via row=, col=
        - Height dynamically set: max(700, 320 * rows)
        - Active subplot highlighted with accent border
    
    Args:
        runs: List of loaded runs
        derived_signals: Dict of derived signals
        view_state: Current view state
        signal_settings: Per-signal display settings
        
    Returns:
        Tuple of (figure, cursor_values dict)
    """
    rows = view_state.layout_rows
    cols = view_state.layout_cols
    total_subplots = rows * cols
    theme = THEMES.get(view_state.theme, THEMES["dark"])
    height = max(700, 320 * rows)
    
    print(f"[FIGURE] Building figure: {rows}x{cols} = {total_subplots} subplots, active={view_state.active_subplot}", flush=True)
    
    # Create subplots with proper spacing and titles
    subplot_titles = [f"Subplot {i+1}" for i in range(total_subplots)] if total_subplots > 1 else None
    
    fig = make_subplots(
        rows=rows, cols=cols,
        shared_xaxes=False,  # Independent axes for better visibility
        vertical_spacing=0.12 if rows > 1 else 0.05,
        horizontal_spacing=0.08 if cols > 1 else 0.02,
        subplot_titles=subplot_titles,
    )
    
    # Track cursor values and time range
    cursor_values = {}
    time_min, time_max = float('inf'), float('-inf')
    color_idx = 0
    traces_per_subplot = {i: 0 for i in range(total_subplots)}
    
    # Ensure we have enough subplot configs
    while len(view_state.subplots) < total_subplots:
        view_state.subplots.append(SubplotConfig(index=len(view_state.subplots)))
    
    # Add invisible placeholder traces to ensure all subplots are visible
    for sp_idx in range(total_subplots):
        row, col = subplot_idx_to_row_col(sp_idx, cols)
        fig.add_trace(
            go.Scatter(
                x=[0], y=[0],
                mode="markers",
                marker=dict(size=0.1, opacity=0),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=row, col=col,
        )
    
    # Add traces for each subplot
    for sp_idx in range(total_subplots):
        sp_config = view_state.subplots[sp_idx]
        row, col = subplot_idx_to_row_col(sp_idx, cols)
        
        if sp_config.mode == "xy":
            # X-Y mode
            _add_xy_traces(fig, runs, derived_signals, sp_config, row, col, color_idx, signal_settings)
        else:
            # Time mode
            for sig_key in sp_config.assigned_signals:
                run_idx, sig_name = parse_signal_key(sig_key)
                
                # Get data
                time_data, sig_data = _get_signal_data(runs, derived_signals, run_idx, sig_name)
                
                if len(time_data) == 0:
                    continue
                
                # Update time range
                time_min = min(time_min, float(time_data[0]))
                time_max = max(time_max, float(time_data[-1]))
                
                # Get settings
                settings = signal_settings.get(sig_key, {})
                color = settings.get("color") or COLORS[color_idx % len(COLORS)]
                width = settings.get("line_width", 1.5)
                
                # Get label
                run_paths = [r.file_path for r in runs]
                label = get_signal_label(run_idx, sig_name, run_paths, settings.get("display_name"))
                
                # Check if state signal
                is_state = settings.get("is_state", False)
                
                if is_state:
                    # State signal: render as transitions
                    _add_state_trace(fig, time_data, sig_data, label, color, row, col)
                else:
                    # Normal signal with per-subplot legend group
                    # Use legendgroup to group traces by subplot for per-subplot legends
                    fig.add_trace(
                        go.Scattergl(
                            x=time_data,
                            y=sig_data,
                            name=label,
                            mode="lines",
                            line=dict(color=color, width=width),
                            hovertemplate=f"<b>{label}</b><br>T: %{{x:.4f}}<br>V: %{{y:.4g}}<extra></extra>",
                            legendgroup=f"subplot_{sp_idx}",
                            legendgrouptitle_text=f"Subplot {sp_idx + 1}" if traces_per_subplot[sp_idx] == 0 else None,
                        ),
                        row=row, col=col,
                    )
                
                # Track trace count per subplot
                traces_per_subplot[sp_idx] += 1
                
                # Cursor value
                if view_state.cursor_enabled and view_state.cursor_time is not None:
                    val = _interpolate_at(time_data, sig_data, view_state.cursor_time)
                    cursor_values[sig_key] = {
                        "value": val,
                        "label": label,
                        "color": color,
                        "subplot": sp_idx,
                    }
                
                color_idx += 1
    
    # Add cursor line to all subplots
    if view_state.cursor_enabled and view_state.cursor_time is not None:
        for sp_idx in range(total_subplots):
            row, col = subplot_idx_to_row_col(sp_idx, cols)
            fig.add_vline(
                x=view_state.cursor_time,
                line=dict(color="#ff6b6b", width=2, dash="dash"),
                row=row, col=col,
            )
    
    # Apply styling with dynamic height
    fig.update_layout(
        template="plotly_dark" if view_state.theme == "dark" else "plotly_white",
        paper_bgcolor=theme["paper"],
        plot_bgcolor=theme["bg"],
        font=dict(color=theme["text"], size=11),
        margin=dict(l=60, r=20, t=40, b=40),
        height=height,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x unified",
        uirevision="stable",
    )
    
    # Highlight active subplot with distinct styling
    for sp_idx in range(total_subplots):
        row, col = subplot_idx_to_row_col(sp_idx, cols)
        is_active = sp_idx == view_state.active_subplot
        
        # Active subplot gets accent color border
        border_color = theme["accent"] if is_active else theme["border"]
        border_width = 3 if is_active else 1
        
        # Update axes styling
        fig.update_xaxes(
            showgrid=True, gridcolor=theme["grid"],
            linecolor=border_color, linewidth=border_width,
            mirror=True,
            row=row, col=col,
        )
        fig.update_yaxes(
            showgrid=True, gridcolor=theme["grid"],
            linecolor=border_color, linewidth=border_width,
            mirror=True,
            row=row, col=col,
        )
        
        # Add "[ACTIVE]" annotation for active subplot
        if is_active and total_subplots > 1:
            fig.add_annotation(
                text=f"⬤ Subplot {sp_idx + 1}",
                xref=f"x{sp_idx + 1 if sp_idx > 0 else ''} domain",
                yref=f"y{sp_idx + 1 if sp_idx > 0 else ''} domain",
                x=0.02, y=0.98,
                showarrow=False,
                font=dict(color=theme["accent"], size=10),
                bgcolor=theme["paper"],
                borderpad=2,
            )
    
    # Log trace counts
    print(f"[FIGURE] Traces per subplot: {traces_per_subplot}", flush=True)
    
    return fig, cursor_values


def _get_signal_data(
    runs: List[Run],
    derived: Dict[str, DerivedSignal],
    run_idx: int,
    sig_name: str,
) -> Tuple[np.ndarray, np.ndarray]:
    """Get signal data from runs or derived signals"""
    if run_idx == DERIVED_RUN_IDX:
        if sig_name in derived:
            ds = derived[sig_name]
            return ds.time, ds.data
        return np.array([]), np.array([])
    
    if 0 <= run_idx < len(runs):
        return runs[run_idx].get_signal_data(sig_name)
    
    return np.array([]), np.array([])


def _interpolate_at(time: np.ndarray, data: np.ndarray, target: float) -> Optional[float]:
    """Interpolate value at target time"""
    if len(time) == 0:
        return None
    try:
        return float(np.interp(target, time, data))
    except:
        return None


def _add_state_trace(
    fig: go.Figure,
    time: np.ndarray,
    data: np.ndarray,
    label: str,
    color: str,
    row: int,
    col: int,
):
    """Add state signal as vertical transition lines"""
    if len(time) < 2:
        return
    
    # Find transitions
    transitions = np.where(np.diff(data) != 0)[0]
    
    for idx in transitions:
        t = time[idx]
        fig.add_vline(
            x=t,
            line=dict(color=color, width=1, dash="dot"),
            annotation_text=f"{data[idx+1]:.0f}",
            annotation_position="top",
            row=row, col=col,
        )


def _add_xy_traces(
    fig: go.Figure,
    runs: List[Run],
    derived: Dict[str, DerivedSignal],
    sp_config: SubplotConfig,
    row: int,
    col: int,
    color_start: int,
    signal_settings: Dict,
):
    """
    Add X-Y traces to subplot.
    
    In X-Y mode:
    - X signal comes from sp_config.x_signal
    - Y signals come from sp_config.assigned_signals (not y_signals)
    - Alignment is done per the sp_config.xy_alignment method
    """
    if not sp_config.x_signal:
        # Show help message
        print(f"[X-Y] Subplot {sp_config.index}: No X signal selected", flush=True)
        return
    
    # Get X data
    x_run_idx, x_sig_name = parse_signal_key(sp_config.x_signal)
    x_time, x_data = _get_signal_data(runs, derived, x_run_idx, x_sig_name)
    
    if len(x_data) == 0:
        print(f"[X-Y] X signal '{x_sig_name}' has no data", flush=True)
        return
    
    run_paths = [r.file_path for r in runs]
    x_label = get_signal_label(x_run_idx, x_sig_name, run_paths)
    print(f"[X-Y] X axis: {x_label}, {len(x_data)} points", flush=True)
    
    color_idx = color_start
    alignment_method = sp_config.xy_alignment or "linear"
    
    # Y signals come from assigned_signals (P0-13)
    y_keys = sp_config.assigned_signals
    
    for y_key in y_keys:
        # Skip if Y signal is the same as X signal
        if y_key == sp_config.x_signal:
            continue
        
        y_run_idx, y_sig_name = parse_signal_key(y_key)
        y_time, y_data = _get_signal_data(runs, derived, y_run_idx, y_sig_name)
        
        if len(y_data) == 0:
            print(f"[X-Y] Y signal '{y_sig_name}' has no data", flush=True)
            continue
        
        # Check time overlap for proper alignment
        t_min = max(x_time.min(), y_time.min())
        t_max = min(x_time.max(), y_time.max())
        
        if t_max <= t_min:
            # No time overlap
            print(f"[X-Y] No time overlap for Y signal '{y_sig_name}'", flush=True)
            continue
        
        # Align Y to X's time base
        overlap_mask = (x_time >= t_min) & (x_time <= t_max)
        x_time_overlap = x_time[overlap_mask]
        x_data_overlap = x_data[overlap_mask]
        
        if len(x_time_overlap) < 2:
            continue
        
        if alignment_method == "nearest":
            # Nearest neighbor
            indices = np.searchsorted(y_time, x_time_overlap)
            indices = np.clip(indices, 0, len(y_data) - 1)
            y_aligned = y_data[indices]
        else:
            # Linear interpolation (default)
            y_aligned = np.interp(x_time_overlap, y_time, y_data)
        
        settings = signal_settings.get(y_key, {})
        color = settings.get("color") or COLORS[color_idx % len(COLORS)]
        
        y_label = get_signal_label(y_run_idx, y_sig_name, run_paths)
        
        fig.add_trace(
            go.Scattergl(
                x=x_data_overlap,
                y=y_aligned,
                name=f"{y_label} vs {x_label}",
                mode="lines",
                line=dict(color=color, width=1.5),
                hovertemplate=f"<b>{y_label}</b><br>X({x_label}): %{{x:.4g}}<br>Y: %{{y:.4g}}<extra></extra>",
            ),
            row=row, col=col,
        )
        
        color_idx += 1
        print(f"[X-Y] Added trace: {y_label} ({len(y_aligned)} points)", flush=True)

