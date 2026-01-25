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
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import ViewState as ViewStateType
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
    for_export: bool = False,
    shared_x: bool = False,
) -> Tuple[go.Figure, Dict]:
    """
    Create the main plot figure.
    
    CANONICAL FIGURE CREATION:
        - Uses make_subplots(rows, cols) to create actual grid
        - Each trace bound to correct subplot via row=, col=
        - Height dynamically set: max(700, 320 * rows)
        - Active subplot highlighted with accent border (unless for_export=True)
    
    Args:
        runs: List of loaded runs
        derived_signals: Dict of derived signals
        view_state: Current view state
        signal_settings: Per-signal display settings
        for_export: If True, hide active subplot highlight for clean export
        shared_x: If True, link X axes across all subplots (same column)
        
    Returns:
        Tuple of (figure, cursor_values dict)
    """
    rows = view_state.layout_rows
    cols = view_state.layout_cols
    total_subplots = rows * cols
    theme = THEMES.get(view_state.theme, THEMES["dark"])
    height = max(700, 320 * rows)
    
    print(f"[FIGURE] Building figure: {rows}x{cols} = {total_subplots} subplots, active={view_state.active_subplot}", flush=True)
    
    # Create subplots with proper spacing and custom titles from SubplotConfig
    def get_subplot_title(idx):
        """Get subplot title - use custom title if set, otherwise default"""
        if idx < len(view_state.subplots) and view_state.subplots[idx].title:
            return view_state.subplots[idx].title
        return f"Subplot {idx+1}"
    
    subplot_titles = [get_subplot_title(i) for i in range(total_subplots)]
    
    fig = make_subplots(
        rows=rows, cols=cols,
        shared_xaxes=False,  # Don't use built-in sharing (hides x-ticks)
        vertical_spacing=0.15 if rows > 1 else 0.05,  # Increased spacing to prevent xlabel/title overlap
        horizontal_spacing=0.08 if cols > 1 else 0.02,
        subplot_titles=subplot_titles,
    )
    
    # If shared_x is True, link ALL subplot x-axes together while keeping ticks visible
    if shared_x and total_subplots > 1:
        # Make all x-axes match the first one
        for sp_idx in range(1, total_subplots):
            row, col = subplot_idx_to_row_col(sp_idx, cols)
            axis_name = f"xaxis{sp_idx + 1}" if sp_idx > 0 else "xaxis"
            fig.update_layout(**{axis_name: dict(matches='x', showticklabels=True)})
    
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
            # X-Y mode - add traces and get cursor values
            xy_cursor, trace_count = _add_xy_traces(
                fig, runs, derived_signals, sp_config, row, col, 
                color_idx, signal_settings, view_state, sp_idx,
                total_subplots, traces_per_subplot[sp_idx]
            )
            traces_per_subplot[sp_idx] += trace_count
            cursor_values.update(xy_cursor or {})
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
                width = settings.get("line_width") or 1.5
                
                # Apply scale and offset transformations
                scale = settings.get("scale", 1.0) or 1.0
                offset = settings.get("offset", 0.0) or 0.0
                time_offset = settings.get("time_offset", 0.0) or 0.0
                
                if scale != 1.0 or offset != 0.0:
                    sig_data = sig_data * scale + offset
                
                # Apply time offset
                if time_offset != 0.0:
                    time_data = time_data + time_offset
                
                # Get label
                run_paths = [r.file_path for r in runs]
                label = get_signal_label(run_idx, sig_name, run_paths, settings.get("display_name"))
                
                # Check if state signal
                is_state = settings.get("is_state", False)
                
                if is_state:
                    # State signal: render as transitions (vertical lines at value changes)
                    _add_state_trace(fig, time_data, sig_data, label, color, width, row, col, sp_idx, total_subplots)
                    traces_per_subplot[sp_idx] += 1
                else:
                    # Normal signal - Feature 7: Group by subplot, individual toggle
                    # Each trace in subplot shares legendgroup for grouping, but toggleitem allows individual toggle
                    is_first_in_subplot = traces_per_subplot[sp_idx] == 0
                    subplot_group = f"SP{sp_idx+1}"
                    
                    fig.add_trace(
                        go.Scattergl(
                            x=time_data,
                            y=sig_data,
                            name=label,  # Clean label without SP suffix (group header shows subplot)
                            mode="lines",
                            line=dict(color=color, width=width),
                            hovertemplate=f"<b>{label}</b><br>T: %{{x:.4f}}<br>V: %{{y:.4g}}<extra></extra>",
                            # Group by subplot for organized legend
                            legendgroup=subplot_group,
                            # Add group title for first trace in each subplot (only when multiple subplots)
                            legendgrouptitle=dict(text=f"Subplot {sp_idx+1}") if is_first_in_subplot and total_subplots > 1 else None,
                        ),
                        row=row, col=col,
                    )
                    traces_per_subplot[sp_idx] += 1
                
                # Cursor value (show transformed value)
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
            sp_config = view_state.subplots[sp_idx] if sp_idx < len(view_state.subplots) else None
            
            # For X-Y mode, cursor should be at the X value corresponding to cursor time
            if sp_config and sp_config.mode == "xy" and sp_config.x_signal:
                x_run_idx, x_sig_name = parse_signal_key(sp_config.x_signal)
                x_time, x_data = _get_signal_data(runs, derived_signals, x_run_idx, x_sig_name)
                if len(x_time) > 0 and len(x_data) > 0:
                    # Find X value at cursor time
                    cursor_x = _interpolate_at(x_time, x_data, view_state.cursor_time)
                    if cursor_x is not None:
                        fig.add_vline(
                            x=cursor_x,
                            line=dict(color="#ff6b6b", width=2, dash="dash"),
                            row=row, col=col,
                        )
            else:
                # Time mode - cursor at time value
                fig.add_vline(
                    x=view_state.cursor_time,
                    line=dict(color="#ff6b6b", width=2, dash="dash"),
                    row=row, col=col,
                )
    
    # Apply styling with dynamic height
    # Feature 7: Legend grouped by subplot with click-to-toggle
    fig.update_layout(
        template="plotly_dark" if view_state.theme == "dark" else "plotly_white",
        paper_bgcolor=theme["paper"],
        plot_bgcolor=theme["bg"],
        font=dict(color=theme["text"], size=11),
        margin=dict(l=60, r=150, t=40, b=40),  # Extra right margin for vertical legend
        height=height,
        legend=dict(
            orientation="v",  # Vertical for grouped display
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,  # Position to the right of the plot
            bgcolor="rgba(0,0,0,0.5)",
            bordercolor=theme["border"],
            borderwidth=1,
            groupclick="toggleitem",  # Click toggles only that trace, not the group
            tracegroupgap=10,  # Gap between groups
            font=dict(size=10),
        ),
        hovermode="x unified",
        uirevision="stable",
    )
    
    # Adjust subplot title positions to prevent overlap with xlabels from row above
    if rows > 1 and total_subplots > 1:
        annotations = list(fig.layout.annotations)
        for ann in annotations:
            # Move subplot titles up slightly
            if ann.y is not None:
                ann.y = ann.y + 0.02
        fig.update_layout(annotations=annotations)
    
    # Style subplots - highlight active one (unless exporting)
    for sp_idx in range(total_subplots):
        row, col = subplot_idx_to_row_col(sp_idx, cols)
        is_active = sp_idx == view_state.active_subplot
        
        # Active subplot gets accent color border (but not in export mode)
        if for_export:
            border_color = theme["border"]
            border_width = 1
        else:
            border_color = theme["accent"] if is_active else theme["border"]
            border_width = 3 if is_active else 1
        
        # Get subplot config for axis label
        sp_config = view_state.subplots[sp_idx] if sp_idx < len(view_state.subplots) else None
        
        # X axis label: "Time" for time mode (X-Y mode sets its own label in _add_xy_traces)
        x_axis_label = "Time"
        if sp_config and sp_config.mode == "time":
            x_axis_label = "Time"
        
        # Update axes styling
        fig.update_xaxes(
            showgrid=True, gridcolor=theme["grid"],
            linecolor=border_color, linewidth=border_width,
            mirror=True,
            title_text=x_axis_label if (sp_config and sp_config.mode == "time") else None,
            row=row, col=col,
        )
        fig.update_yaxes(
            showgrid=True, gridcolor=theme["grid"],
            linecolor=border_color, linewidth=border_width,
            mirror=True,
            row=row, col=col,
        )
        
        # Apply custom axis limits if set (Feature 5)
        if sp_config:
            if sp_config.xlim and len(sp_config.xlim) == 2:
                # Handle partial limits (one value can be None for auto)
                x_range = [
                    sp_config.xlim[0] if sp_config.xlim[0] is not None else None,
                    sp_config.xlim[1] if sp_config.xlim[1] is not None else None,
                ]
                if x_range[0] is not None and x_range[1] is not None:
                    fig.update_xaxes(range=x_range, row=row, col=col)
            
            if sp_config.ylim and len(sp_config.ylim) == 2:
                y_range = [
                    sp_config.ylim[0] if sp_config.ylim[0] is not None else None,
                    sp_config.ylim[1] if sp_config.ylim[1] is not None else None,
                ]
                if y_range[0] is not None and y_range[1] is not None:
                    fig.update_yaxes(range=y_range, row=row, col=col)
        
        # Add "[ACTIVE]" annotation for active subplot (not in export mode)
        if is_active and total_subplots > 1 and not for_export:
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
    width: float,
    row: int,
    col: int,
    sp_idx: int = 0,
    total_subplots: int = 1,
):
    """
    Add state signal as vertical X-lines at value changes with state value annotations.
    
    State signals show:
    - Vertical X-lines where the value changes (as actual traces for legend toggle)
    - Text annotations showing the incoming state value
    - Initial value annotation at the start
    
    Uses actual traces (not vlines) so legend clicks properly hide/show the signal.
    """
    if len(time) < 1:
        return
    
    # Find transitions (where value changes)
    transitions = np.where(np.diff(data) != 0)[0] if len(time) > 1 else np.array([])
    
    # Calculate y range for vertical lines
    y_max = float(np.max(data)) if len(data) > 0 else 1.0
    y_min = float(np.min(data)) if len(data) > 0 else 0.0
    y_range = y_max - y_min if y_max != y_min else 1.0
    # Extend y range for visibility
    y_bottom = y_min - y_range * 0.1
    y_top = y_max + y_range * 0.2
    annotation_y = y_max + y_range * 0.15
    
    # Build x and y arrays for vertical lines (using None to break the lines)
    x_lines = []
    y_lines = []
    annotations_data = []  # (x, text) pairs
    
    # Initial vertical line
    initial_time = float(time[0])
    initial_value = int(data[0]) if np.issubdtype(data.dtype, np.integer) else f"{data[0]:.1f}"
    x_lines.extend([initial_time, initial_time, None])
    y_lines.extend([y_bottom, y_top, None])
    annotations_data.append((initial_time, str(initial_value)))
    
    # Transition vertical lines
    for idx in transitions:
        t = float(time[idx + 1])
        new_val = data[idx + 1]
        new_val_str = int(new_val) if np.issubdtype(data.dtype, np.integer) or new_val == int(new_val) else f"{new_val:.1f}"
        x_lines.extend([t, t, None])
        y_lines.extend([y_bottom, y_top, None])
        annotations_data.append((t, str(new_val_str)))
    
    # Subplot group for legend
    subplot_group = f"SP{sp_idx+1}"
    is_first_in_subplot = False  # Will be determined by caller
    
    # Add single trace with all vertical lines (toggleable via legend)
    fig.add_trace(
        go.Scattergl(
            x=x_lines,
            y=y_lines,
            name=label,
            mode="lines",
            line=dict(color=color, width=width),
            hovertemplate=f"<b>{label}</b><br>State transition<extra></extra>",
            legendgroup=subplot_group,
            legendgrouptitle=dict(text=f"Subplot {sp_idx+1}") if total_subplots > 1 else None,
        ),
        row=row, col=col,
    )
    
    # Add annotations for state values
    x_axis = f"x{sp_idx + 1}" if sp_idx > 0 else "x"
    y_axis = f"y{sp_idx + 1}" if sp_idx > 0 else "y"
    
    for ann_x, ann_text in annotations_data:
        fig.add_annotation(
            x=ann_x,
            y=annotation_y,
            xref=x_axis,
            yref=y_axis,
            text=f"<b>{ann_text}</b>",
            showarrow=False,
            font=dict(color=color, size=10),
            bgcolor="rgba(0,0,0,0.7)",
            borderpad=2,
        )
    
    print(f"[STATE] Added state signal '{label}' with {len(transitions)} transitions", flush=True)


def _add_xy_traces(
    fig: go.Figure,
    runs: List[Run],
    derived: Dict[str, DerivedSignal],
    sp_config: SubplotConfig,
    row: int,
    col: int,
    color_start: int,
    signal_settings: Dict,
    view_state: Any = None,
    sp_idx: int = 0,
    total_subplots: int = 1,
    current_trace_count: int = 0,
) -> Tuple[Dict, int]:
    """
    Add X-Y traces to subplot (P3-8, P7-15).
    
    In X-Y mode:
    - X signal comes from sp_config.x_signal
    - Y signals come from sp_config.assigned_signals
    - X axis label = X signal name (not "Time")
    - Cursor values show X and Y signal values at cursor time
    
    Returns:
        Tuple of (cursor_values dict, trace_count added)
    """
    cursor_values = {}
    
    if not sp_config.x_signal:
        print(f"[X-Y] Subplot {sp_config.index}: No X signal selected", flush=True)
        return cursor_values, 0
    
    # Get X data
    x_run_idx, x_sig_name = parse_signal_key(sp_config.x_signal)
    x_time, x_data = _get_signal_data(runs, derived, x_run_idx, x_sig_name)
    
    if len(x_data) == 0:
        print(f"[X-Y] X signal '{x_sig_name}' has no data", flush=True)
        return cursor_values, 0
    
    run_paths = [r.file_path for r in runs]
    x_label = get_signal_label(x_run_idx, x_sig_name, run_paths)
    print(f"[X-Y] X axis: {x_label}, {len(x_data)} points", flush=True)
    
    # Update X axis label to show X signal name (P3-8)
    fig.update_xaxes(title_text=x_label, row=row, col=col)
    
    color_idx = color_start
    alignment_method = sp_config.xy_alignment or "linear"
    
    # Add cursor values for X signal if cursor is enabled (P7-15)
    if view_state and view_state.cursor_enabled and view_state.cursor_time is not None:
        x_val = _interpolate_at(x_time, x_data, view_state.cursor_time)
        cursor_values[sp_config.x_signal] = {
            "value": x_val,
            "label": f"X: {x_label}",
            "color": "#58a6ff",
            "subplot": sp_idx,
        }
    
    # Y signals come from assigned_signals
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
            print(f"[X-Y] No time overlap for Y signal '{y_sig_name}'", flush=True)
            continue
        
        # Align Y to X's time base
        overlap_mask = (x_time >= t_min) & (x_time <= t_max)
        x_time_overlap = x_time[overlap_mask]
        x_data_overlap = x_data[overlap_mask]
        
        if len(x_time_overlap) < 2:
            continue
        
        if alignment_method == "nearest":
            indices = np.searchsorted(y_time, x_time_overlap)
            indices = np.clip(indices, 0, len(y_data) - 1)
            y_aligned = y_data[indices]
        else:
            y_aligned = np.interp(x_time_overlap, y_time, y_data)
        
        settings = signal_settings.get(y_key, {})
        color = settings.get("color") or COLORS[color_idx % len(COLORS)]
        
        y_label = get_signal_label(y_run_idx, y_sig_name, run_paths)
        
        # Add trace with proper legend grouping (Fix 3)
        subplot_group = f"SP{sp_idx+1}"
        is_first_in_subplot = current_trace_count == 0
        
        fig.add_trace(
            go.Scattergl(
                x=x_data_overlap,
                y=y_aligned,
                name=f"{y_label} vs {x_label}",
                mode="lines",
                line=dict(color=color, width=1.5),
                hovertemplate=f"<b>{y_label}</b><br>X({x_label}): %{{x:.4g}}<br>Y: %{{y:.4g}}<extra></extra>",
                legendgroup=subplot_group,
                legendgrouptitle=dict(text=f"Subplot {sp_idx+1}") if is_first_in_subplot and total_subplots > 1 else None,
            ),
            row=row, col=col,
        )
        current_trace_count += 1
        
        # Add cursor value for Y signal (P7-15)
        if view_state and view_state.cursor_enabled and view_state.cursor_time is not None:
            y_val = _interpolate_at(y_time, y_data, view_state.cursor_time)
            cursor_values[y_key] = {
                "value": y_val,
                "label": f"Y: {y_label}",
                "color": color,
                "subplot": sp_idx,
            }
        
        color_idx += 1
        print(f"[X-Y] Added trace: {y_label} ({len(y_aligned)} points)", flush=True)
    
    return cursor_values, current_trace_count

