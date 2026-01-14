"""
Signal Viewer Pro - Main Application
=====================================
SDI-like offline signal viewer with lossless visualization.

Usage:
    python app.py
    Then open http://127.0.0.1:8050
"""

import os
import json
import webbrowser
import threading
from typing import Dict, List, Optional
from datetime import datetime

import dash
from dash import dcc, html, Input, Output, State, callback_context, ALL
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

# Core modules
from core.models import (
    Run, DerivedSignal, ViewState, SubplotConfig, Tab,
    make_signal_key, parse_signal_key, DERIVED_RUN_IDX
)
from core.naming import get_csv_display_name, get_signal_label
from core.session import save_session, load_session, parse_view_state

# IO modules
from loaders.csv_loader import load_csv, CSVImportSettings, preview_csv, detect_delimiter

# Visualization
from viz.figure_factory import create_figure, create_empty_grid, subplot_idx_to_row_col, THEMES

# Operations
from ops.engine import (
    apply_unary, apply_binary, apply_multi,
    UnaryOp, BinaryOp, MultiOp, AlignmentMethod
)

# Compare
from compare.engine import (
    compare_runs, CompareConfig, SyncMethod, InterpolationMethod, ToleranceSpec
)

# Stream
from stream.engine import StreamEngine, StreamConfig

# Report
from report.builder import build_report, export_html

# UI Layout
from ui.layout import create_layout


# =============================================================================
# CONFIGURATION
# =============================================================================
APP_TITLE = "Signal Viewer Pro v4.0"
APP_HOST = "127.0.0.1"
APP_PORT = 8050


# =============================================================================
# APP INITIALIZATION
# =============================================================================

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True,
    title="Signal Viewer Pro",
)

# =============================================================================
# GLOBAL STATE (cleared on each startup - no auto-reload)
# =============================================================================

def _reset_state():
    """Reset all global state to initial values (clean start)"""
    global runs, derived_signals, signal_settings, view_state, stream_engine
    runs = []
    derived_signals = {}
    signal_settings = {}
    view_state = ViewState()
    stream_engine = StreamEngine()
    print("[INIT] Global state reset to initial values", flush=True)

# Initialize clean state on module load
runs: List[Run] = []
derived_signals: Dict[str, DerivedSignal] = {}
signal_settings: Dict[str, Dict] = {}
view_state = ViewState()
stream_engine = StreamEngine()
_reset_state()  # Ensure clean start


# =============================================================================
# LAYOUT
# =============================================================================

app.layout = create_layout()


# =============================================================================
# CALLBACKS: CSV Import
# =============================================================================

@app.callback(
    Output("modal-import", "is_open"),
    Input("btn-import", "n_clicks"),
    Input("btn-import-cancel", "n_clicks"),
    Input("btn-import-confirm", "n_clicks"),
    State("modal-import", "is_open"),
    prevent_initial_call=True,
)
def toggle_import_modal(open_clicks, cancel_clicks, confirm_clicks, is_open):
    ctx = callback_context
    if ctx.triggered:
        trigger = ctx.triggered[0]["prop_id"]
        if "btn-import" in trigger:
            return True
        return False
    return is_open


@app.callback(
    Output("import-file-path", "value"),
    Output("import-preview", "children"),
    Output("import-time-col", "options"),
    Output("store-selected-files", "data"),
    Input("btn-browse", "n_clicks"),
    State("store-selected-files", "data"),
    prevent_initial_call=True,
)
def browse_file(n_clicks, existing_files):
    """Multi-file selection with preview of first file"""
    import tkinter as tk
    from tkinter import filedialog
    
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    # Use multi-select file dialog
    file_paths = filedialog.askopenfilenames(
        title="Select CSV file(s)",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
    )
    root.destroy()
    
    if not file_paths:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Convert to list
    file_list = list(file_paths)
    
    # Preview first file
    first_file = file_list[0]
    rows, cols = preview_csv(first_file, max_rows=10)
    
    if not rows:
        preview_content = html.Div([
            html.P(f"Selected {len(file_list)} file(s):", className="fw-bold"),
            html.Ul([html.Li(os.path.basename(f)) for f in file_list], className="small"),
            html.P("Failed to preview first file", className="text-warning"),
        ])
        return first_file, preview_content, [], file_list
    
    # Build preview with file list
    file_list_ui = html.Div([
        html.P(f"Selected {len(file_list)} file(s):", className="fw-bold text-info mb-1"),
        html.Ul([html.Li(os.path.basename(f), className="small") for f in file_list], className="mb-2"),
    ]) if len(file_list) > 1 else html.Div()
    
    table = html.Table([
        html.Thead(html.Tr([html.Th(c, className="px-2") for c in cols])),
        html.Tbody([
            html.Tr([html.Td(cell, className="px-2") for cell in row])
            for row in rows[:8]
        ]),
    ], className="table table-sm table-dark table-striped")
    
    preview_content = html.Div([
        file_list_ui,
        html.P(f"Preview of: {os.path.basename(first_file)}", className="small text-muted") if len(file_list) > 1 else html.Div(),
        table,
    ])
    
    # Time column options
    time_options = [{"label": c, "value": c} for c in cols]
    
    # Display string (show count if multiple)
    display_path = f"{len(file_list)} files selected" if len(file_list) > 1 else first_file
    
    return display_path, preview_content, time_options, file_list


@app.callback(
    Output("runs-list", "children"),
    Output("signal-tree", "children"),
    Output("store-runs", "data"),
    Output("store-refresh", "data"),
    Output("modal-import", "is_open", allow_duplicate=True),
    Input("btn-import-confirm", "n_clicks"),
    State("store-selected-files", "data"),
    State("import-has-header", "value"),
    State("import-header-row", "value"),
    State("import-skip-rows", "value"),
    State("import-delimiter", "value"),
    State("import-time-col", "value"),
    State("store-runs", "data"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def do_import(n_clicks, selected_files, has_header, header_row, skip_rows, delimiter, time_col, run_paths, refresh):
    """Import multiple files with shared settings"""
    global runs
    
    if not selected_files:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    run_paths = run_paths or []
    imported_count = 0
    
    settings = CSVImportSettings(
        has_header=has_header,
        header_row=int(header_row or 0),
        skip_rows=int(skip_rows or 0),
        delimiter=None if delimiter == "auto" else delimiter,
        time_column=time_col or "Time",
    )
    
    # Import all selected files
    for file_path in selected_files:
        if not os.path.isfile(file_path):
            print(f"[IMPORT] Skipping missing file: {file_path}", flush=True)
            continue
        
        if file_path in run_paths:
            print(f"[IMPORT] Skipping already loaded: {file_path}", flush=True)
            continue
        
        all_paths = run_paths + [file_path]
        run = load_csv(file_path, all_paths, settings)
        
        if run:
            runs.append(run)
            run_paths.append(file_path)
            stream_engine.register_run(len(runs) - 1, file_path)
            imported_count += 1
    
    print(f"[IMPORT] Loaded {imported_count} file(s)", flush=True)
    
    return (
        build_runs_list(run_paths),
        build_signal_tree(runs),
        run_paths,
        (refresh or 0) + 1,
        False,  # Close modal
    )


# =============================================================================
# CALLBACKS: Runs & Signals UI
# =============================================================================

def build_runs_list(run_paths: List[str]) -> list:
    """Build runs list UI"""
    if not run_paths:
        return [html.P("No runs loaded", className="text-muted small")]
    
    items = []
    for idx, path in enumerate(run_paths):
        display = get_csv_display_name(path, run_paths)
        items.append(
            dbc.Row([
                dbc.Col(html.Span(display, className="small text-truncate", title=path), width=10),
                dbc.Col(
                    html.Button("×", id={"type": "btn-remove-run", "index": idx},
                               className="btn btn-link btn-sm text-danger p-0"),
                    width=2, className="text-end",
                ),
            ], className="g-0 mb-1 align-items-center")
        )
    return items


def build_signal_tree(runs_list: List[Run], search_filter: str = "", collapsed_runs: Dict = None) -> list:
    """Build signal tree UI with collapsible sections and full signal list"""
    if not runs_list:
        return [html.P("Load a CSV to see signals", className="text-muted small")]
    
    collapsed_runs = collapsed_runs or {}
    items = []
    search_lower = search_filter.lower()
    
    for run_idx, run in enumerate(runs_list):
        signals = list(run.signals.keys())
        if search_lower:
            signals = [s for s in signals if search_lower in s.lower()]
        
        total_signals = len(run.signals)
        filtered_count = len(signals)
        is_collapsed = collapsed_runs.get(str(run_idx), False)
        
        # Run header with collapse toggle and remove button
        collapse_icon = "▶" if is_collapsed else "▼"
        items.append(html.Div([
            dbc.Button(
                collapse_icon,
                id={"type": "btn-collapse-run", "index": run_idx},
                size="sm",
                color="link",
                className="p-0 me-1 text-info",
                style={"fontSize": "10px", "width": "16px"},
                n_clicks=0,
            ),
            html.Span(run.csv_display_name, className="text-info small fw-bold"),
            html.Span(f" ({filtered_count}/{total_signals})", className="text-muted small"),
            html.Button(
                "×",
                id={"type": "btn-remove-run", "index": run_idx},
                className="btn btn-link btn-sm text-danger p-0 float-end",
                title="Remove this run",
            ),
        ], className="mt-2 mb-1 d-flex align-items-center"))
        
        # Signals container (collapsible) - hide if collapsed
        if not is_collapsed:
            signal_items = []
            for sig in signals:  # NO LIMIT - show all signals
                sig_key = make_signal_key(run_idx, sig)
                signal_items.append(
                    html.Div(
                        sig,
                        id={"type": "signal-item", "key": sig_key},
                        className="small py-1 px-2 signal-item",
                        style={"cursor": "pointer"},
                        n_clicks=0,
                    )
                )
            
            items.append(html.Div(
                signal_items,
                id={"type": "run-signals-container", "index": run_idx},
                style={"maxHeight": "200px", "overflowY": "auto"},
            ))
    
    # Derived signals (P0-8: with removal controls)
    if derived_signals:
        items.append(html.Div([
            html.Strong("Derived", className="text-warning small"),
            html.Span(f" ({len(derived_signals)})", className="text-muted small"),
            # Clear all derived signals button
            html.Button(
                "Clear All",
                id="btn-clear-all-derived",
                className="btn btn-link btn-sm text-danger p-0 float-end",
                title="Remove all derived signals",
                style={"fontSize": "10px"},
            ),
        ], className="mt-2 mb-1 d-flex align-items-center"))
        
        for name in derived_signals.keys():
            sig_key = make_signal_key(DERIVED_RUN_IDX, name)
            items.append(
                html.Div([
                    # Clickable signal name
                    html.Span(
                        name,
                        id={"type": "signal-item", "key": sig_key},
                        className="small text-warning",
                        style={"cursor": "pointer", "flex": "1"},
                        n_clicks=0,
                    ),
                    # Remove button for this derived signal
                    html.Button(
                        "×",
                        id={"type": "btn-remove-derived", "name": name},
                        className="btn btn-link btn-sm text-danger p-0 ms-1",
                        title=f"Remove {name}",
                        style={"fontSize": "10px"},
                    ),
                ], className="py-1 px-2 signal-item d-flex align-items-center")
            )
    
    return items if items else [html.P("No signals match filter", className="text-muted small")]


@app.callback(
    Output("signal-tree", "children", allow_duplicate=True),
    Input("signal-search", "value"),
    State("store-collapsed-runs", "data"),
    prevent_initial_call=True,
)
def filter_signals(search_value, collapsed_runs):
    return build_signal_tree(runs, search_value or "", collapsed_runs or {})


@app.callback(
    Output("store-collapsed-runs", "data"),
    Output("signal-tree", "children", allow_duplicate=True),
    Input({"type": "btn-collapse-run", "index": ALL}, "n_clicks"),
    State("store-collapsed-runs", "data"),
    State("signal-search", "value"),
    prevent_initial_call=True,
)
def toggle_run_collapse(collapse_clicks, collapsed_runs, search_value):
    """Toggle collapse state for a run's signal list"""
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    if not any(c for c in collapse_clicks if c):
        return dash.no_update, dash.no_update
    
    try:
        trigger_dict = json.loads(trigger.rsplit(".", 1)[0])
        run_idx = trigger_dict["index"]
    except:
        return dash.no_update, dash.no_update
    
    collapsed_runs = collapsed_runs or {}
    idx_str = str(run_idx)
    collapsed_runs[idx_str] = not collapsed_runs.get(idx_str, False)
    
    print(f"[COLLAPSE] Run {run_idx} collapsed={collapsed_runs[idx_str]}", flush=True)
    
    return collapsed_runs, build_signal_tree(runs, search_value or "", collapsed_runs)


@app.callback(
    Output("runs-list", "children", allow_duplicate=True),
    Output("signal-tree", "children", allow_duplicate=True),
    Output("store-runs", "data", allow_duplicate=True),
    Output("store-refresh", "data", allow_duplicate=True),
    Input({"type": "btn-remove-run", "index": ALL}, "n_clicks"),
    State("store-runs", "data"),
    State("store-refresh", "data"),
    State("store-collapsed-runs", "data"),
    prevent_initial_call=True,
)
def remove_run(remove_clicks, run_paths, refresh, collapsed_runs):
    """Remove a run from the list"""
    global runs, view_state
    
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    if not any(c for c in remove_clicks if c):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Find which run to remove
    try:
        trigger_dict = json.loads(trigger.rsplit(".", 1)[0])
        run_idx = trigger_dict["index"]
    except:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    if run_idx < 0 or run_idx >= len(runs):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Remove run
    removed_run = runs.pop(run_idx)
    run_paths = [r.file_path for r in runs]
    
    print(f"[REMOVE] Removed run: {removed_run.csv_display_name}", flush=True)
    
    # Clear assignments referencing removed run
    for sp in view_state.subplots:
        sp.assigned_signals = [
            sig for sig in sp.assigned_signals
            if not sig.startswith(f"{run_idx}:")
        ]
        # Adjust indices for runs after removed one
        updated_signals = []
        for sig in sp.assigned_signals:
            parts = sig.split(":", 1)
            if len(parts) == 2:
                idx = int(parts[0])
                if idx > run_idx:
                    updated_signals.append(f"{idx - 1}:{parts[1]}")
                else:
                    updated_signals.append(sig)
            else:
                updated_signals.append(sig)
        sp.assigned_signals = updated_signals
    
    return (
        build_runs_list(run_paths),
        build_signal_tree(runs, "", collapsed_runs or {}),
        run_paths,
        (refresh or 0) + 1,
    )


# =============================================================================
# CALLBACKS: Signal Assignment
# =============================================================================

@app.callback(
    Output("store-view-state", "data"),
    Output("assigned-list", "children"),
    Input({"type": "signal-item", "key": ALL}, "n_clicks"),
    Input({"type": "btn-remove-assigned", "index": ALL}, "n_clicks"),
    State("store-view-state", "data"),
    State("select-subplot", "value"),
    prevent_initial_call=True,
)
def handle_assignment(signal_clicks, remove_clicks, vs_data, active_subplot):
    global view_state
    
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    active_sp = int(active_subplot or 0)
    
    # Ensure subplot config exists
    while len(view_state.subplots) <= active_sp:
        view_state.subplots.append(SubplotConfig(index=len(view_state.subplots)))
    
    sp_config = view_state.subplots[active_sp]
    
    if "signal-item" in trigger:
        # Add signal
        trigger_dict = json.loads(trigger.rsplit(".", 1)[0])
        sig_key = trigger_dict["key"]
        
        if sig_key not in sp_config.assigned_signals:
            sp_config.assigned_signals.append(sig_key)
    
    elif "btn-remove-assigned" in trigger:
        # Remove signal
        trigger_dict = json.loads(trigger.rsplit(".", 1)[0])
        idx = trigger_dict["index"]
        if 0 <= idx < len(sp_config.assigned_signals):
            sp_config.assigned_signals.pop(idx)
    
    view_state.active_subplot = active_sp
    
    return _view_state_to_dict(), build_assigned_list(sp_config, runs)


def build_assigned_list(sp_config: SubplotConfig, runs_list: List[Run]) -> list:
    """Build assigned signals list"""
    if not sp_config.assigned_signals:
        return [html.P("Click signals to assign", className="text-muted small")]
    
    items = []
    run_paths = [r.file_path for r in runs_list]
    
    for idx, sig_key in enumerate(sp_config.assigned_signals):
        run_idx, sig_name = parse_signal_key(sig_key)
        label = get_signal_label(run_idx, sig_name, run_paths)
        
        items.append(
            dbc.Row([
                dbc.Col(html.Span(label, className="small text-truncate"), width=10),
                dbc.Col(
                    html.Button("×", id={"type": "btn-remove-assigned", "index": idx},
                               className="btn btn-link btn-sm text-danger p-0"),
                    width=2, className="text-end",
                ),
            ], className="g-0 mb-1 align-items-center")
        )
    return items


def _view_state_to_dict() -> dict:
    """Convert ViewState to dict for store"""
    return {
        "layout_rows": view_state.layout_rows,
        "layout_cols": view_state.layout_cols,
        "active_subplot": view_state.active_subplot,
        "theme": view_state.theme,
        "cursor_time": view_state.cursor_time,
        "cursor_enabled": view_state.cursor_enabled,
        "subplots": [
            {
                "index": sp.index,
                "mode": sp.mode,
                "assigned_signals": sp.assigned_signals,
            }
            for sp in view_state.subplots
        ],
    }


# =============================================================================
# CALLBACKS: Layout & Subplot Selection
# =============================================================================

@app.callback(
    Output("select-subplot", "options"),
    Output("select-subplot", "value"),
    Output("assigned-list", "children", allow_duplicate=True),
    Input("select-rows", "value"),
    Input("select-cols", "value"),
    State("select-subplot", "value"),
    prevent_initial_call=True,
)
def update_layout(rows, cols, current_sp):
    """
    Update subplot selector when layout changes.
    
    Assignment preservation strategy (A4):
    - Subplots 0 to (new_total - 1) keep their assignments
    - Orphan subplots (index >= new_total) have their signals moved to last subplot
    """
    global view_state
    
    rows = int(rows or 1)
    cols = int(cols or 1)
    new_total = rows * cols
    old_total = view_state.layout_rows * view_state.layout_cols
    
    print(f"[LAYOUT] Changing from {old_total} to {new_total} subplots", flush=True)
    
    # Log current assignments before change
    for i, sp in enumerate(view_state.subplots):
        if sp.assigned_signals:
            print(f"  Subplot {i}: {sp.assigned_signals}", flush=True)
    
    view_state.layout_rows = rows
    view_state.layout_cols = cols
    
    # Ensure enough subplot configs exist
    while len(view_state.subplots) < new_total:
        view_state.subplots.append(SubplotConfig(index=len(view_state.subplots)))
    
    # Handle orphan assignments (move to last subplot)
    if new_total < old_total:
        last_sp = view_state.subplots[new_total - 1]
        for sp_idx in range(new_total, len(view_state.subplots)):
            orphan_sp = view_state.subplots[sp_idx]
            # Move orphan signals to last valid subplot
            for sig_key in orphan_sp.assigned_signals:
                if sig_key not in last_sp.assigned_signals:
                    last_sp.assigned_signals.append(sig_key)
            # Clear orphan
            orphan_sp.assigned_signals = []
        print(f"[LAYOUT] Orphan signals moved to subplot {new_total}", flush=True)
    
    # Clamp active subplot
    value = min(int(current_sp or 0), new_total - 1)
    view_state.active_subplot = value
    
    # Format: "Subplot N / M" for clear visibility
    options = [{"label": f"Subplot {i + 1} / {new_total}", "value": i} for i in range(new_total)]
    
    # Get current subplot config for assigned list
    sp_config = view_state.subplots[value]
    assigned_list = build_assigned_list(sp_config, runs)
    
    print(f"[LAYOUT] Selector updated: {len(options)} options, selected={value}, signals={sp_config.assigned_signals}", flush=True)
    
    return options, value, assigned_list


@app.callback(
    Output("active-subplot-badge", "children"),
    Output("assigned-list", "children", allow_duplicate=True),
    Output("btn-mode-time", "color"),
    Output("btn-mode-time", "outline"),
    Output("btn-mode-xy", "color"),
    Output("btn-mode-xy", "outline"),
    Input("select-subplot", "value"),
    prevent_initial_call=True,
)
def select_subplot(subplot_idx):
    """
    Select a subplot - does NOT clear assignments, only displays them.
    Assignments are stable and persist across subplot switches.
    """
    global view_state
    
    sp_idx = int(subplot_idx or 0)
    view_state.active_subplot = sp_idx
    
    # Ensure subplot config exists - create and store if needed
    while len(view_state.subplots) <= sp_idx:
        view_state.subplots.append(SubplotConfig(index=len(view_state.subplots)))
    
    sp_config = view_state.subplots[sp_idx]
    
    # Mode button styling based on current subplot mode
    is_time = sp_config.mode == "time"
    time_color = "primary" if is_time else "secondary"
    time_outline = False if is_time else True
    xy_color = "primary" if not is_time else "secondary"
    xy_outline = False if not is_time else True
    
    total = view_state.layout_rows * view_state.layout_cols
    
    print(f"[SELECT] Subplot {sp_idx + 1}/{total}, signals={sp_config.assigned_signals}", flush=True)
    
    return (
        f"Subplot {sp_idx + 1} / {total}",
        build_assigned_list(sp_config, runs),
        time_color, time_outline,
        xy_color, xy_outline,
    )


@app.callback(
    Output("assigned-list", "children", allow_duplicate=True),
    Output("store-refresh", "data", allow_duplicate=True),
    Input("btn-clear-subplot", "n_clicks"),
    State("select-subplot", "value"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def clear_subplot(n_clicks, subplot_idx, refresh):
    """Clear all assignments from the selected subplot"""
    global view_state
    
    sp_idx = int(subplot_idx or 0)
    
    if sp_idx < len(view_state.subplots):
        view_state.subplots[sp_idx].assigned_signals = []
        view_state.subplots[sp_idx].x_signal = None
        view_state.subplots[sp_idx].y_signals = []
        print(f"[CLEAR] Cleared subplot {sp_idx + 1}", flush=True)
    
    sp_config = view_state.subplots[sp_idx] if sp_idx < len(view_state.subplots) else SubplotConfig(index=sp_idx)
    
    return build_assigned_list(sp_config, runs), (refresh or 0) + 1


@app.callback(
    Output("runs-list", "children", allow_duplicate=True),
    Output("signal-tree", "children", allow_duplicate=True),
    Output("assigned-list", "children", allow_duplicate=True),
    Output("store-runs", "data", allow_duplicate=True),
    Output("store-refresh", "data", allow_duplicate=True),
    Input("btn-clear-all", "n_clicks"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def clear_all(n_clicks, refresh):
    """Clear all runs, derived signals, and assignments"""
    global runs, derived_signals, view_state
    
    # Clear everything
    runs = []
    derived_signals = {}
    view_state.subplots = [SubplotConfig(index=0)]
    view_state.active_subplot = 0
    
    print("[CLEAR ALL] Reset to initial state", flush=True)
    
    return (
        build_runs_list([]),
        build_signal_tree([]),
        [html.P("Click signals to assign", className="text-muted small")],
        [],
        (refresh or 0) + 1,
    )


# =============================================================================
# CALLBACKS: X-Y Mode
# =============================================================================

@app.callback(
    Output("xy-controls", "style"),
    Output("xy-x-signal", "options"),
    Output("xy-x-signal", "value"),
    Input("btn-mode-time", "n_clicks"),
    Input("btn-mode-xy", "n_clicks"),
    Input("select-subplot", "value"),
    State("store-runs", "data"),
)
def update_xy_controls(time_clicks, xy_clicks, subplot_idx, run_paths):
    """
    Show/hide X-Y controls and populate X signal dropdown.
    Y signals come from the assigned list (P0-13).
    """
    global view_state
    
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
    sp_idx = int(subplot_idx or 0)
    
    # Ensure subplot config exists
    while len(view_state.subplots) <= sp_idx:
        view_state.subplots.append(SubplotConfig(index=len(view_state.subplots)))
    
    sp_config = view_state.subplots[sp_idx]
    
    # Handle mode toggle
    if "btn-mode-time" in trigger:
        sp_config.mode = "time"
        print(f"[MODE] Subplot {sp_idx}: Time mode", flush=True)
    elif "btn-mode-xy" in trigger:
        sp_config.mode = "xy"
        print(f"[MODE] Subplot {sp_idx}: X-Y mode", flush=True)
    
    # Show/hide based on mode
    if sp_config.mode != "xy":
        return {"display": "none"}, [], None
    
    # Build X signal options from all runs + assigned signals
    options = []
    for run_idx, run in enumerate(runs):
        for sig_name in run.signals.keys():
            sig_key = make_signal_key(run_idx, sig_name)
            label = get_signal_label(run_idx, sig_name, [r.file_path for r in runs])
            options.append({"label": label, "value": sig_key})
    
    # Add derived signals
    for name in derived_signals.keys():
        sig_key = make_signal_key(DERIVED_RUN_IDX, name)
        options.append({"label": f"{name} — Derived", "value": sig_key})
    
    return (
        {"display": "block"},
        options,
        sp_config.x_signal,
    )


@app.callback(
    Output("store-refresh", "data", allow_duplicate=True),
    Input("xy-x-signal", "value"),
    Input("xy-alignment", "value"),
    State("select-subplot", "value"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def update_xy_config(x_signal, alignment, subplot_idx, refresh):
    """
    Update subplot X-Y configuration when X signal or alignment is changed.
    Y signals come from the assigned list automatically (P0-13).
    """
    global view_state
    
    sp_idx = int(subplot_idx or 0)
    
    if sp_idx < len(view_state.subplots):
        sp_config = view_state.subplots[sp_idx]
        sp_config.x_signal = x_signal
        # Y signals are the assigned signals (excluding X if it's in there)
        sp_config.xy_alignment = alignment or "linear"
        
        print(f"[X-Y] Subplot {sp_idx}: X={x_signal}, align={alignment}", flush=True)
    
    return (refresh or 0) + 1


# =============================================================================
# CALLBACKS: Cursor
# =============================================================================

@app.callback(
    Output("cursor-controls", "style"),
    Output("interval-replay", "disabled"),
    Output("btn-cursor-toggle", "color"),
    Output("btn-cursor-toggle", "outline"),
    Output("cursor-scope-col", "style"),
    Input("btn-cursor-toggle", "n_clicks"),
    State("switch-cursor", "value"),
    prevent_initial_call=True,
)
def toggle_cursor_button(n_clicks, current_value):
    """Toggle cursor on/off with button click (P0-19)"""
    global view_state
    
    # Toggle state
    enabled = not (current_value and len(current_value) > 0)
    view_state.cursor_enabled = enabled
    
    style = {"display": "block"} if enabled else {"display": "none"}
    btn_color = "primary" if enabled else "secondary"
    btn_outline = False if enabled else True
    scope_style = {} if enabled else {"display": "none"}
    
    print(f"[CURSOR] Toggle: {enabled}", flush=True)
    return style, not enabled, btn_color, btn_outline, scope_style


@app.callback(
    Output("switch-cursor", "value"),
    Input("btn-cursor-toggle", "n_clicks"),
    State("switch-cursor", "value"),
    prevent_initial_call=True,
)
def sync_cursor_checklist(n_clicks, current_value):
    """Keep hidden checklist in sync with button"""
    return [] if (current_value and len(current_value) > 0) else [True]


@app.callback(
    Output("btn-cursor-active", "color"),
    Output("btn-cursor-active", "outline"),
    Output("btn-cursor-all", "color"),
    Output("btn-cursor-all", "outline"),
    Output("store-refresh", "data", allow_duplicate=True),
    Input("btn-cursor-active", "n_clicks"),
    Input("btn-cursor-all", "n_clicks"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def toggle_cursor_scope(active_clicks, all_clicks, refresh):
    """
    Toggle cursor scope between Active and All subplots.
    
    Fixed behavior (task_add.md):
    - Active: show cursor values only for active subplot
    - All: show cursor values grouped by subplot
    - Buttons must visibly toggle AND actually change output
    """
    global view_state
    
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    
    if "btn-cursor-active" in trigger:
        view_state.cursor_show_all = False
        print(f"[CURSOR] Scope: Active only", flush=True)
        return "primary", False, "secondary", True, (refresh or 0) + 1
    else:
        view_state.cursor_show_all = True
        print(f"[CURSOR] Scope: All subplots", flush=True)
        return "secondary", True, "primary", False, (refresh or 0) + 1


@app.callback(
    Output("cursor-slider", "min"),
    Output("cursor-slider", "max"),
    Output("cursor-slider", "value"),
    Input("store-refresh", "data"),
    Input("switch-cursor", "value"),
)
def update_cursor_range(refresh, cursor_enabled):
    is_enabled = cursor_enabled and len(cursor_enabled) > 0
    if not is_enabled or not runs:
        return 0, 100, 0
    
    # Find time range
    t_min, t_max = float('inf'), float('-inf')
    for run in runs:
        if len(run.time) > 0:
            t_min = min(t_min, float(run.time[0]))
            t_max = max(t_max, float(run.time[-1]))
    
    if t_min >= t_max:
        return 0, 100, 0
    
    return t_min, t_max, t_min


@app.callback(
    Output("cursor-time-display", "children"),
    Input("cursor-slider", "value"),
)
def update_cursor_display(cursor_time):
    global view_state
    view_state.cursor_time = cursor_time
    return f"T = {cursor_time:.6f}" if cursor_time is not None else ""


@app.callback(
    Output("cursor-slider", "value", allow_duplicate=True),
    Input("btn-cursor-jump", "n_clicks"),
    State("cursor-jump-input", "value"),
    State("cursor-slider", "min"),
    State("cursor-slider", "max"),
    prevent_initial_call=True,
)
def cursor_jump_to_time(n_clicks, target_time, t_min, t_max):
    """Jump cursor to specific time (nearest sample)"""
    if not n_clicks or target_time is None:
        return dash.no_update
    
    target_time = float(target_time)
    
    # Find nearest sample time
    nearest_time = target_time
    min_dist = float('inf')
    
    for run in runs:
        if len(run.time) > 0:
            import numpy as np
            idx = np.searchsorted(run.time, target_time)
            # Check both neighbors
            for check_idx in [max(0, idx - 1), min(len(run.time) - 1, idx)]:
                dist = abs(run.time[check_idx] - target_time)
                if dist < min_dist:
                    min_dist = dist
                    nearest_time = float(run.time[check_idx])
    
    # Clamp to valid range
    nearest_time = max(t_min, min(t_max, nearest_time))
    
    print(f"[CURSOR] Jump to T={target_time:.6f} → nearest sample T={nearest_time:.6f}", flush=True)
    return nearest_time


# =============================================================================
# CALLBACKS: Stream Toggle
# =============================================================================

@app.callback(
    Output("btn-stream-toggle", "color"),
    Output("btn-stream-toggle", "outline"),
    Output("btn-stream-toggle", "children"),
    Output("stream-rate-container", "style"),
    Output("interval-stream", "disabled"),
    Output("interval-stream", "interval"),
    Input("btn-stream-toggle", "n_clicks"),
    State("select-stream-rate", "value"),
    State("interval-stream", "disabled"),
    prevent_initial_call=True,
)
def toggle_stream(n_clicks, rate, is_disabled):
    """Toggle streaming mode on/off"""
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Toggle state
    streaming = is_disabled  # If was disabled, now enable
    
    if streaming:
        print(f"[STREAM] Started at {rate}ms interval", flush=True)
        return "success", False, "⏹️ Stop", {}, False, int(rate)
    else:
        print(f"[STREAM] Stopped", flush=True)
        return "secondary", True, "▶️ Stream", {"display": "none"}, True, 1000


@app.callback(
    Output("store-refresh", "data", allow_duplicate=True),
    Input("interval-stream", "n_intervals"),
    State("store-refresh", "data"),
    State("interval-stream", "disabled"),
    prevent_initial_call=True,
)
def stream_refresh(n_intervals, refresh, is_disabled):
    """Periodic refresh when streaming"""
    if is_disabled:
        return dash.no_update
    
    global runs
    
    # Incremental reload
    for run in runs:
        if os.path.isfile(run.file_path):
            stat = os.stat(run.file_path)
            # Check if file changed (simplified - just check mtime)
            # In production, would track offset for true incremental read
    
    return (refresh or 0) + 1


# =============================================================================
# CALLBACKS: Main Plot
# =============================================================================

@app.callback(
    Output("main-plot", "figure"),
    Output("inspector-values", "children"),
    Input("store-view-state", "data"),
    Input("store-refresh", "data"),
    Input("cursor-slider", "value"),
    Input("btn-theme", "n_clicks"),
    Input("select-rows", "value"),
    Input("select-cols", "value"),
    Input("select-subplot", "value"),
    Input("switch-inspector-all", "value"),
    Input("btn-mode-time", "n_clicks"),
    Input("btn-mode-xy", "n_clicks"),
)
def update_plot(vs_data, refresh, cursor_time, theme_clicks, layout_rows, layout_cols, 
                active_sp, inspector_show_all, mode_time_clicks, mode_xy_clicks):
    global view_state
    
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
    
    # Toggle theme on button click
    if "btn-theme" in trigger:
        view_state.theme = "light" if view_state.theme == "dark" else "dark"
    
    # Handle mode toggle
    if "btn-mode-time" in trigger:
        if view_state.active_subplot < len(view_state.subplots):
            view_state.subplots[view_state.active_subplot].mode = "time"
            print(f"[MODE] Subplot {view_state.active_subplot} set to Time mode", flush=True)
    elif "btn-mode-xy" in trigger:
        if view_state.active_subplot < len(view_state.subplots):
            view_state.subplots[view_state.active_subplot].mode = "xy"
            print(f"[MODE] Subplot {view_state.active_subplot} set to X-Y mode", flush=True)
    
    # Update layout from dropdowns (source of truth)
    view_state.layout_rows = int(layout_rows or 1)
    view_state.layout_cols = int(layout_cols or 1)
    view_state.active_subplot = int(active_sp or 0)
    
    # Clamp active subplot to valid range
    total = view_state.layout_rows * view_state.layout_cols
    if view_state.active_subplot >= total:
        view_state.active_subplot = total - 1
    
    # Update cursor time
    view_state.cursor_time = cursor_time
    
    # Log layout changes
    if "select-rows" in trigger or "select-cols" in trigger:
        print(f"[LAYOUT] Changed to {view_state.layout_rows}x{view_state.layout_cols} = {total} subplots", flush=True)
    if "select-subplot" in trigger:
        print(f"[SUBPLOT] Active subplot changed to {view_state.active_subplot}", flush=True)
    
    # Create figure
    fig, cursor_values = create_figure(
        runs,
        derived_signals,
        view_state,
        signal_settings,
    )
    
    # Build inspector with cursor values grouped by subplot
    # Use cursor_show_all from view_state (managed by scope buttons)
    show_all = view_state.cursor_show_all if hasattr(view_state, 'cursor_show_all') else True
    inspector = build_inspector(
        cursor_values,
        active_subplot=view_state.active_subplot,
        show_all=show_all,
        cursor_time=view_state.cursor_time if view_state.cursor_enabled else None,
    )
    
    return fig, inspector


def build_inspector(cursor_values: Dict, active_subplot: int = 0, show_all: bool = True, cursor_time: float = None) -> list:
    """
    Build inspector panel content grouped by subplot.
    
    Layout (P0-11): 2-column flex row with:
        - Left: signal name (truncated if too long)
        - Right: numeric value in monospace font
    
    Args:
        cursor_values: Dict of signal_key -> {value, label, color, subplot}
        active_subplot: Currently active subplot index
        show_all: If True, show all subplots; if False, show only active
        cursor_time: Current cursor time for display
    """
    if not cursor_values:
        return [html.P("Enable cursor to see values", className="text-muted small")]
    
    # Group by subplot
    by_subplot = {}
    for sig_key, info in cursor_values.items():
        sp_idx = info.get("subplot", 0)
        if sp_idx not in by_subplot:
            by_subplot[sp_idx] = []
        by_subplot[sp_idx].append(info)
    
    if not by_subplot:
        return [html.P("No values at cursor", className="text-muted small")]
    
    items = []
    
    # Show cursor time prominently
    if cursor_time is not None:
        items.append(html.Div([
            html.Strong("T = ", className="small text-muted"),
            html.Span(f"{cursor_time:.6f}", className="small text-info fw-bold", 
                     style={"fontFamily": "monospace"}),
        ], className="mb-2 pb-1 border-bottom border-secondary"))
    
    # Render each subplot section
    for sp_idx in sorted(by_subplot.keys()):
        # Filter by active subplot if not showing all
        if not show_all and sp_idx != active_subplot:
            continue
        
        signals = by_subplot[sp_idx]
        is_active = sp_idx == active_subplot
        
        # Subplot header
        header_class = "small fw-bold mb-1 text-info" if is_active else "small fw-bold mb-1 text-muted"
        items.append(html.Div(f"Subplot {sp_idx + 1}", className=header_class))
        
        # Signal values - 2 column flex layout (P0-11)
        for info in signals:
            val = info.get("value")
            label = info.get("label", "?")
            color = info.get("color", "#fff")
            
            if val is not None:
                # Use flex row with space-between for alignment
                items.append(
                    html.Div([
                        # Left column: color dot + label
                        html.Div([
                            html.Span("●", style={"color": color}, className="me-1"),
                            html.Span(label, className="small text-truncate", 
                                     style={"maxWidth": "100px", "display": "inline-block"}),
                        ], style={"flex": "1", "minWidth": "0"}),
                        
                        # Right column: value in monospace
                        html.Span(f"{val:.4g}", className="small text-warning",
                                 style={"fontFamily": "monospace", "fontWeight": "bold", 
                                       "textAlign": "right", "minWidth": "70px"}),
                    ], className="d-flex align-items-center justify-content-between mb-1 ms-2")
                )
        
        items.append(html.Hr(className="my-1 opacity-25"))
    
    return items if items else [html.P("No values at cursor", className="text-muted small")]


# =============================================================================
# CALLBACKS: Theme
# =============================================================================

@app.callback(
    Output("runs-count", "children"),
    Input("store-runs", "data"),
)
def update_runs_count(run_paths):
    return str(len(run_paths or []))


# =============================================================================
# CALLBACKS: Session Save/Load
# =============================================================================

@app.callback(
    Output("download-session", "data"),
    Input("btn-save", "n_clicks"),
    prevent_initial_call=True,
)
def save_session_callback(n_clicks):
    from datetime import datetime
    
    run_paths = [r.file_path for r in runs]
    
    session = {
        "version": "4.0",
        "timestamp": datetime.now().isoformat(),
        "run_paths": run_paths,
        "view_state": _view_state_to_dict(),
        "signal_settings": signal_settings,
    }
    
    content = json.dumps(session, indent=2)
    filename = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    return dict(content=content, filename=filename)


@app.callback(
    Output("runs-list", "children", allow_duplicate=True),
    Output("signal-tree", "children", allow_duplicate=True),
    Output("store-runs", "data", allow_duplicate=True),
    Output("store-view-state", "data", allow_duplicate=True),
    Output("store-refresh", "data", allow_duplicate=True),
    Input("btn-load", "n_clicks"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def load_session_callback(n_clicks, refresh):
    global runs, view_state, signal_settings
    
    import tkinter as tk
    from tkinter import filedialog
    
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    file_path = filedialog.askopenfilename(
        title="Load Session",
        filetypes=[("JSON files", "*.json")],
    )
    root.destroy()
    
    if not file_path:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    session = load_session(file_path)
    if not session:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Clear and reload
    runs = []
    run_paths = session.get("run_paths", [])
    
    for path in run_paths:
        if os.path.isfile(path):
            run = load_csv(path, run_paths)
            if run:
                runs.append(run)
        else:
            print(f"[WARN] Session file not found: {path}", flush=True)
    
    # Restore view state
    view_state = parse_view_state(session)
    signal_settings = session.get("signal_settings", {})
    
    actual_paths = [r.file_path for r in runs]
    
    return (
        build_runs_list(actual_paths),
        build_signal_tree(runs),
        actual_paths,
        _view_state_to_dict(),
        (refresh or 0) + 1,
    )


# =============================================================================
# CALLBACKS: Refresh (P0-15: Full reconciliation)
# =============================================================================

@app.callback(
    Output("store-refresh", "data", allow_duplicate=True),
    Output("runs-list", "children", allow_duplicate=True),
    Output("signal-tree", "children", allow_duplicate=True),
    Input("btn-refresh", "n_clicks"),
    State("store-refresh", "data"),
    State("store-collapsed-runs", "data"),
    prevent_initial_call=True,
)
def refresh_data(n_clicks, refresh, collapsed_runs):
    """
    Refresh callback (P0-15): Re-reads all CSVs and reconciles signals.
    
    - Re-reads each CSV from disk
    - Detects added/removed columns
    - Updates tree and assignments
    - Re-computes derived signals (marks broken if inputs missing)
    - Preserves user settings where possible
    """
    global runs, derived_signals, view_state
    
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update
    
    print(f"[REFRESH] Starting full refresh...", flush=True)
    
    # Track previous signal names per run for reconciliation
    previous_signals = {}
    for run_idx, run in enumerate(runs):
        previous_signals[run_idx] = set(run.signals.keys())
    
    # Reload all CSVs from disk
    new_runs = []
    run_paths = [r.file_path for r in runs]
    
    for run in runs:
        if not os.path.isfile(run.file_path):
            print(f"[REFRESH] File not found (skipping): {run.file_path}", flush=True)
            continue
        
        new_run = load_csv(run.file_path, run_paths)
        if new_run:
            new_runs.append(new_run)
            new_sigs = set(new_run.signals.keys())
            old_sigs = previous_signals.get(len(new_runs) - 1, set())
            
            added = new_sigs - old_sigs
            removed = old_sigs - new_sigs
            
            if added:
                print(f"[REFRESH] {run.csv_display_name}: +{len(added)} signals ({list(added)[:3]}...)", flush=True)
            if removed:
                print(f"[REFRESH] {run.csv_display_name}: -{len(removed)} signals ({list(removed)[:3]}...)", flush=True)
    
    runs = new_runs
    
    # Reconcile assignments - remove signals that no longer exist
    for sp in view_state.subplots:
        valid_signals = []
        for sig_key in sp.assigned_signals:
            run_idx, sig_name = parse_signal_key(sig_key)
            
            if run_idx == DERIVED_RUN_IDX:
                # Check if derived still exists
                if sig_name in derived_signals:
                    valid_signals.append(sig_key)
            elif 0 <= run_idx < len(runs):
                if sig_name in runs[run_idx].signals:
                    valid_signals.append(sig_key)
        
        if len(valid_signals) < len(sp.assigned_signals):
            print(f"[REFRESH] Subplot {sp.index}: {len(sp.assigned_signals) - len(valid_signals)} signals removed", flush=True)
        sp.assigned_signals = valid_signals
    
    # Re-compute derived signals (check for broken dependencies)
    broken_derived = []
    for name, ds in derived_signals.items():
        inputs_valid = True
        for src_key in ds.source_signals:
            run_idx, sig_name = parse_signal_key(src_key)
            
            if run_idx == DERIVED_RUN_IDX:
                if sig_name not in derived_signals:
                    inputs_valid = False
                    break
            elif 0 <= run_idx < len(runs):
                if sig_name not in runs[run_idx].signals:
                    inputs_valid = False
                    break
            else:
                inputs_valid = False
                break
        
        if not inputs_valid:
            broken_derived.append(name)
            print(f"[REFRESH] Derived signal '{name}' marked broken (missing inputs)", flush=True)
    
    # Mark broken derived signals (keep them but note status)
    for name in broken_derived:
        ds = derived_signals[name]
        ds.display_name = f"⚠ {ds.name} (broken)"
    
    print(f"[REFRESH] Complete: {len(runs)} runs, {len(derived_signals)} derived, {len(broken_derived)} broken", flush=True)
    
    return (
        (refresh or 0) + 1,
        build_runs_list([r.file_path for r in runs]),
        build_signal_tree(runs, "", collapsed_runs or {}),
    )


# =============================================================================
# CALLBACKS: Tab System (P1)
# =============================================================================

@app.callback(
    Output("tab-bar", "children"),
    Input("store-tabs", "data"),
    Input("store-active-tab", "data"),
)
def render_tab_bar(tabs, active_tab):
    """
    Render tab bar with clickable tabs.
    
    Fixed behavior (task_add.md):
    - Exactly N visible tabs = N views
    - No implicit "main" tab
    - All tabs can be closed if there's >1 tab
    """
    if not tabs:
        tabs = [{"id": "view_1", "name": "View 1"}]
    
    tab_buttons = []
    can_close = len(tabs) > 1  # Can only close if there's more than one tab
    
    for tab in tabs:
        is_active = tab["id"] == active_tab
        color = "info" if is_active else "secondary"
        outline = not is_active
        
        tab_buttons.append(
            dbc.Button(
                tab["name"],
                id={"type": "btn-tab", "id": tab["id"]},
                size="sm",
                color=color,
                outline=outline,
                className="me-1",
                n_clicks=0,
            )
        )
        
        # Add close button for ALL tabs if >1 tab exists
        if can_close:
            tab_buttons.append(
                dbc.Button(
                    "×",
                    id={"type": "btn-close-tab", "id": tab["id"]},
                    size="sm",
                    color="danger",
                    outline=True,
                    className="me-2 px-1",
                    style={"fontSize": "10px"},
                    n_clicks=0,
                )
            )
    
    return tab_buttons


@app.callback(
    Output("store-tabs", "data", allow_duplicate=True),
    Output("store-active-tab", "data", allow_duplicate=True),
    Input("btn-add-tab", "n_clicks"),
    State("store-tabs", "data"),
    prevent_initial_call=True,
)
def add_tab(n_clicks, tabs):
    """Add a new tab (P1)"""
    if not n_clicks:
        return dash.no_update, dash.no_update
    
    tabs = tabs or []
    new_id = f"tab_{len(tabs) + 1}"
    new_tab = {"id": new_id, "name": f"View {len(tabs) + 1}"}
    tabs.append(new_tab)
    
    print(f"[TABS] Created new tab: {new_id}", flush=True)
    
    return tabs, new_id


@app.callback(
    Output("store-active-tab", "data", allow_duplicate=True),
    Input({"type": "btn-tab", "id": ALL}, "n_clicks"),
    State("store-tabs", "data"),
    prevent_initial_call=True,
)
def switch_tab(tab_clicks, tabs):
    """Switch to clicked tab (P1)"""
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update
    
    # Check if any button was actually clicked
    if not any(c for c in tab_clicks if c):
        return dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    try:
        trigger_dict = json.loads(trigger.rsplit(".", 1)[0])
        tab_id = trigger_dict["id"]
        print(f"[TABS] Switched to tab: {tab_id}", flush=True)
        return tab_id
    except:
        return dash.no_update


@app.callback(
    Output("store-tabs", "data", allow_duplicate=True),
    Output("store-active-tab", "data", allow_duplicate=True),
    Input({"type": "btn-close-tab", "id": ALL}, "n_clicks"),
    State("store-tabs", "data"),
    State("store-active-tab", "data"),
    prevent_initial_call=True,
)
def close_tab(close_clicks, tabs, active_tab):
    """Close a tab (P1) - disabled if only 1 tab"""
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    
    if not any(c for c in close_clicks if c):
        return dash.no_update, dash.no_update
    
    if len(tabs) <= 1:
        return dash.no_update, dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    try:
        trigger_dict = json.loads(trigger.rsplit(".", 1)[0])
        tab_id = trigger_dict["id"]
    except:
        return dash.no_update, dash.no_update
    
    # Remove tab
    tabs = [t for t in tabs if t["id"] != tab_id]
    
    # If we closed the active tab, switch to first tab
    new_active = active_tab if active_tab != tab_id else tabs[0]["id"]
    
    print(f"[TABS] Closed tab: {tab_id}", flush=True)
    
    return tabs, new_active


# =============================================================================
# CALLBACKS: Smart Incremental Refresh (P0-18)
# =============================================================================

@app.callback(
    Output("store-refresh", "data", allow_duplicate=True),
    Output("smart-refresh-status", "children"),
    Output("smart-refresh-info", "children"),
    Output("store-file-offsets", "data"),
    Input("btn-smart-refresh", "n_clicks"),
    State("store-file-offsets", "data"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def smart_incremental_refresh(n_clicks, file_offsets, refresh):
    """
    Smart Incremental Refresh (P0-18):
    - Checks each CSV file for changes
    - If file grew: read only appended lines
    - If file shrank/rewritten: full reload with warning
    - Updates plots and derived signals
    """
    global runs
    
    if not n_clicks or not runs:
        return dash.no_update, "No files loaded", "", {}
    
    file_offsets = file_offsets or {}
    
    appended_count = 0
    reloaded_count = 0
    unchanged_count = 0
    
    for run_idx, run in enumerate(runs):
        path = run.file_path
        
        if not os.path.isfile(path):
            continue
        
        # Get current file stats
        stat = os.stat(path)
        current_size = stat.st_size
        current_mtime = stat.st_mtime
        
        # Get previous stats
        prev_info = file_offsets.get(path, {})
        prev_size = prev_info.get("size", 0)
        prev_mtime = prev_info.get("mtime", 0)
        
        if current_mtime == prev_mtime and current_size == prev_size:
            # No change
            unchanged_count += 1
            continue
        
        if current_size > prev_size and current_mtime > prev_mtime:
            # File grew - try incremental read
            try:
                import pandas as pd
                
                # Read only new rows
                with open(path, 'r') as f:
                    # Skip to previous position
                    f.seek(prev_size)
                    new_data = f.read()
                
                if new_data.strip():
                    # Parse new rows
                    from io import StringIO
                    # Add header for parsing
                    header = ",".join(run.signals.keys())
                    new_df = pd.read_csv(StringIO(new_data), header=None, names=list(run.signals.keys()))
                    
                    # Append to existing data
                    if len(new_df) > 0:
                        for col in new_df.columns:
                            if col in run.signals:
                                import numpy as np
                                run.signals[col].data = np.append(run.signals[col].data, new_df[col].values)
                        
                        # Update time if it exists
                        if 'Time' in new_df.columns:
                            run.time = np.append(run.time, new_df['Time'].values)
                        
                        run.compute_metadata()
                        appended_count += 1
                        print(f"[SMART] Appended {len(new_df)} rows to {run.csv_display_name}", flush=True)
                
            except Exception as e:
                # Fallback to full reload
                print(f"[SMART] Incremental read failed, full reload: {e}", flush=True)
                run_paths = [r.file_path for r in runs]
                new_run = load_csv(path, run_paths)
                if new_run:
                    runs[run_idx] = new_run
                    reloaded_count += 1
        
        else:
            # File rewritten (size smaller or other change) - full reload
            run_paths = [r.file_path for r in runs]
            new_run = load_csv(path, run_paths)
            if new_run:
                runs[run_idx] = new_run
                reloaded_count += 1
                print(f"[SMART] Full reload: {run.csv_display_name} (file rewritten)", flush=True)
        
        # Update offset tracking
        file_offsets[path] = {"size": current_size, "mtime": current_mtime}
    
    # Build status message
    status_parts = []
    if appended_count:
        status_parts.append(f"{appended_count} updated")
    if reloaded_count:
        status_parts.append(f"{reloaded_count} reloaded")
    if unchanged_count:
        status_parts.append(f"{unchanged_count} unchanged")
    
    status = ", ".join(status_parts) if status_parts else "No changes"
    info = f"Checked at {datetime.now().strftime('%H:%M:%S')}"
    
    return (refresh or 0) + 1, status, info, file_offsets


# =============================================================================
# CALLBACKS: Panel Toggles
# =============================================================================

@app.callback(
    Output("collapse-ops", "is_open"),
    Input("btn-toggle-ops", "n_clicks"),
    State("collapse-ops", "is_open"),
    prevent_initial_call=True,
)
def toggle_ops_panel(n_clicks, is_open):
    return not is_open


@app.callback(
    Output("collapse-compare", "is_open"),
    Input("btn-toggle-compare", "n_clicks"),
    State("collapse-compare", "is_open"),
    prevent_initial_call=True,
)
def toggle_compare_panel(n_clicks, is_open):
    return not is_open


# =============================================================================
# CALLBACKS: Compare Panel
# =============================================================================

@app.callback(
    Output("select-baseline-run", "options"),
    Output("select-compare-run", "options"),
    Input("store-refresh", "data"),
    Input("collapse-compare", "is_open"),
)
def update_compare_run_options(refresh, is_open):
    """Populate run dropdowns for compare"""
    if not is_open or not runs:
        return [], []
    
    options = [
        {"label": run.csv_display_name, "value": i}
        for i, run in enumerate(runs)
    ]
    return options, options


@app.callback(
    Output("select-compare-signal", "options"),
    Input("select-baseline-run", "value"),
    Input("select-compare-run", "value"),
    Input("check-common-only", "value"),
)
def update_compare_signal_options(run_a_idx, run_b_idx, common_only):
    """Populate signal dropdown with common or all signals"""
    if run_a_idx is None:
        return []
    
    run_a_idx = int(run_a_idx)
    signals_a = set(runs[run_a_idx].signals.keys()) if run_a_idx < len(runs) else set()
    
    if run_b_idx is not None:
        run_b_idx = int(run_b_idx)
        signals_b = set(runs[run_b_idx].signals.keys()) if run_b_idx < len(runs) else set()
        
        if common_only:
            signals = signals_a & signals_b
        else:
            signals = signals_a | signals_b
    else:
        signals = signals_a
    
    return [{"label": s, "value": s} for s in sorted(signals)]


@app.callback(
    Output("compare-results", "children"),
    Input("btn-compare", "n_clicks"),
    State("select-baseline-run", "value"),
    State("select-compare-run", "value"),
    State("select-compare-signal", "value"),
    State("select-compare-alignment", "value"),
    prevent_initial_call=True,
)
def run_comparison(n_clicks, run_a_idx, run_b_idx, signal_name, alignment):
    """Execute comparison and show results"""
    import numpy as np
    
    if run_a_idx is None or run_b_idx is None or not signal_name:
        return html.Span("⚠️ Select runs and signal", className="text-warning")
    
    run_a_idx = int(run_a_idx)
    run_b_idx = int(run_b_idx)
    
    if run_a_idx >= len(runs) or run_b_idx >= len(runs):
        return html.Span("⚠️ Invalid run selection", className="text-warning")
    
    run_a = runs[run_a_idx]
    run_b = runs[run_b_idx]
    
    if signal_name not in run_a.signals or signal_name not in run_b.signals:
        return html.Span(f"⚠️ Signal '{signal_name}' not in both runs", className="text-warning")
    
    try:
        # Get data
        time_a, data_a = run_a.get_signal_data(signal_name)
        time_b, data_b = run_b.get_signal_data(signal_name)
        
        # Align time bases
        if alignment == "baseline":
            # Use A's time base, interpolate B
            time_common = time_a
            data_a_aligned = data_a
            data_b_aligned = np.interp(time_a, time_b, data_b)
        elif alignment == "union":
            # Union of time points
            time_common = np.sort(np.unique(np.concatenate([time_a, time_b])))
            data_a_aligned = np.interp(time_common, time_a, data_a)
            data_b_aligned = np.interp(time_common, time_b, data_b)
        else:  # intersection
            # Only overlapping region
            t_start = max(time_a[0], time_b[0])
            t_end = min(time_a[-1], time_b[-1])
            mask_a = (time_a >= t_start) & (time_a <= t_end)
            time_common = time_a[mask_a]
            data_a_aligned = data_a[mask_a]
            data_b_aligned = np.interp(time_common, time_b, data_b)
        
        # Calculate metrics
        diff = data_a_aligned - data_b_aligned
        max_abs_diff = float(np.max(np.abs(diff)))
        rms_diff = float(np.sqrt(np.mean(diff**2)))
        
        # Correlation
        if len(data_a_aligned) > 1:
            corr = float(np.corrcoef(data_a_aligned, data_b_aligned)[0, 1])
        else:
            corr = 0.0
        
        # Create delta as derived signal
        delta_name = f"Δ({signal_name})"
        derived_signals[delta_name] = DerivedSignal(
            name=delta_name,
            time=time_common,
            data=diff,
            operation="compare",
            source_signals=[f"{run_a_idx}:{signal_name}", f"{run_b_idx}:{signal_name}"],
        )
        
        print(f"[COMPARE] {signal_name}: MaxDiff={max_abs_diff:.4g}, RMS={rms_diff:.4g}, Corr={corr:.4f}", flush=True)
        
        return html.Div([
            html.Div([
                html.Strong("Comparison Results", className="text-info"),
            ], className="mb-2"),
            html.Div([
                html.Span("Max |Δ|: ", className="text-muted"),
                html.Strong(f"{max_abs_diff:.4g}", className="text-warning"),
            ]),
            html.Div([
                html.Span("RMS Δ: ", className="text-muted"),
                html.Strong(f"{rms_diff:.4g}", className="text-warning"),
            ]),
            html.Div([
                html.Span("Correlation: ", className="text-muted"),
                html.Strong(f"{corr:.4f}", className="text-success" if corr > 0.9 else "text-warning"),
            ]),
            html.Div([
                html.Span(f"Samples: {len(time_common)}", className="text-muted small"),
            ]),
            html.Hr(className="my-2"),
            html.Div([
                html.Span(f"✅ Created: {delta_name}", className="text-success small"),
            ]),
            html.Hr(className="my-1"),
            html.Small("📌 View delta signal in Derived section or use tabs for side-by-side.", 
                      className="text-info"),
        ])
        
    except Exception as e:
        print(f"[COMPARE ERROR] {e}", flush=True)
        return html.Span(f"❌ Error: {str(e)[:50]}", className="text-danger")


# Note: P2-16 and P2-17 (Compare workflows with new tabs) are partially implemented.
# The full implementation would require:
# 1. A dedicated compare tab layout with 2x1 subplots (overlay + diff)
# 2. Per-tab view state management
# 3. Compare runs ranking table
# These are marked as advanced features for future implementation.


@app.callback(
    Output("collapse-stream", "is_open"),
    Input("btn-toggle-stream", "n_clicks"),
    State("collapse-stream", "is_open"),
    prevent_initial_call=True,
)
def toggle_stream_panel(n_clicks, is_open):
    return not is_open


# =============================================================================
# CALLBACKS: Operations Panel
# =============================================================================

@app.callback(
    Output("select-op-signals", "options"),
    Input("store-refresh", "data"),
    Input("collapse-ops", "is_open"),
)
def update_op_signals_options(refresh, is_open):
    """Populate signal dropdown for operations"""
    if not is_open:
        return []
    
    options = []
    for run_idx, run in enumerate(runs):
        for sig_name in run.signals.keys():
            sig_key = make_signal_key(run_idx, sig_name)
            label = get_signal_label(run_idx, sig_name, [r.file_path for r in runs])
            options.append({"label": label, "value": sig_key})
    
    # Add derived signals
    for name in derived_signals.keys():
        sig_key = make_signal_key(DERIVED_RUN_IDX, name)
        options.append({"label": f"{name} — Derived", "value": sig_key})
    
    return options


@app.callback(
    Output("select-operation", "options"),
    Input("select-op-type", "value"),
)
def update_operation_options(op_type):
    """Update operation dropdown based on selected type"""
    if op_type == "unary":
        return [
            {"label": "Derivative (d/dt)", "value": "derivative"},
            {"label": "Integral (∫dt)", "value": "integral"},
            {"label": "Absolute |x|", "value": "abs"},
            {"label": "Normalize (0-1)", "value": "normalize"},
            {"label": "RMS (rolling)", "value": "rms"},
            {"label": "Smooth (moving avg)", "value": "smooth"},
        ]
    elif op_type == "binary":
        return [
            {"label": "A + B (sum)", "value": "add"},
            {"label": "A − B (difference)", "value": "subtract"},
            {"label": "A × B (product)", "value": "multiply"},
            {"label": "A ÷ B (ratio)", "value": "divide"},
            {"label": "|A − B| (abs diff)", "value": "abs_diff"},
        ]
    else:  # multi
        return [
            {"label": "Norm (√Σx²)", "value": "norm"},
            {"label": "Mean", "value": "mean"},
            {"label": "Max envelope", "value": "max"},
            {"label": "Min envelope", "value": "min"},
        ]


@app.callback(
    Output("op-status", "children"),
    Output("signal-tree", "children", allow_duplicate=True),
    Output("store-refresh", "data", allow_duplicate=True),
    Input("btn-apply-op", "n_clicks"),
    State("select-op-type", "value"),
    State("select-op-signals", "value"),
    State("select-operation", "value"),
    State("select-op-alignment", "value"),
    State("input-op-output-name", "value"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def apply_operation(n_clicks, op_type, signal_keys, operation, alignment, output_name, refresh):
    """Apply operation and create derived signal"""
    global derived_signals
    
    if not signal_keys:
        return html.Span("⚠️ Select signal(s)", className="text-warning"), dash.no_update, dash.no_update
    
    # Validate signal count
    if op_type == "unary" and len(signal_keys) != 1:
        return html.Span("⚠️ Select exactly 1 signal", className="text-warning"), dash.no_update, dash.no_update
    if op_type == "binary" and len(signal_keys) != 2:
        return html.Span("⚠️ Select exactly 2 signals", className="text-warning"), dash.no_update, dash.no_update
    if op_type == "multi" and len(signal_keys) < 2:
        return html.Span("⚠️ Select 2+ signals", className="text-warning"), dash.no_update, dash.no_update
    
    try:
        # Get signal data
        signals_data = []
        for sig_key in signal_keys:
            run_idx, sig_name = parse_signal_key(sig_key)
            if run_idx == DERIVED_RUN_IDX:
                if sig_name in derived_signals:
                    ds = derived_signals[sig_name]
                    signals_data.append((ds.time, ds.data, sig_name))
            elif 0 <= run_idx < len(runs):
                time_data, sig_data = runs[run_idx].get_signal_data(sig_name)
                signals_data.append((time_data, sig_data, sig_name))
        
        if not signals_data:
            return html.Span("⚠️ No valid signal data", className="text-warning"), dash.no_update, dash.no_update
        
        # Apply operation
        import numpy as np
        
        if op_type == "unary":
            time, data, name = signals_data[0]
            if operation == "derivative":
                result = np.gradient(data, time)
                op_label = f"d({name})/dt"
            elif operation == "integral":
                result = np.cumsum(data) * np.mean(np.diff(time)) if len(time) > 1 else data
                op_label = f"∫{name}"
            elif operation == "abs":
                result = np.abs(data)
                op_label = f"|{name}|"
            elif operation == "normalize":
                min_v, max_v = np.min(data), np.max(data)
                result = (data - min_v) / (max_v - min_v) if max_v > min_v else data * 0
                op_label = f"norm({name})"
            elif operation == "rms":
                window = min(100, len(data) // 10) or 10
                result = np.sqrt(np.convolve(data**2, np.ones(window)/window, mode='same'))
                op_label = f"rms({name})"
            elif operation == "smooth":
                window = min(50, len(data) // 20) or 5
                result = np.convolve(data, np.ones(window)/window, mode='same')
                op_label = f"smooth({name})"
            else:
                result = data
                op_label = name
            
            result_time = time
            
        elif op_type == "binary":
            t1, d1, n1 = signals_data[0]
            t2, d2, n2 = signals_data[1]
            
            # Align time bases
            if len(t1) >= len(t2):
                result_time = t1
                if alignment == "nearest":
                    indices = np.searchsorted(t2, t1)
                    indices = np.clip(indices, 0, len(d2) - 1)
                    d2_aligned = d2[indices]
                else:
                    d2_aligned = np.interp(t1, t2, d2)
                d1_aligned = d1
            else:
                result_time = t2
                if alignment == "nearest":
                    indices = np.searchsorted(t1, t2)
                    indices = np.clip(indices, 0, len(d1) - 1)
                    d1_aligned = d1[indices]
                else:
                    d1_aligned = np.interp(t2, t1, d1)
                d2_aligned = d2
            
            if operation == "add":
                result = d1_aligned + d2_aligned
                op_label = f"{n1} + {n2}"
            elif operation == "subtract":
                result = d1_aligned - d2_aligned
                op_label = f"{n1} − {n2}"
            elif operation == "multiply":
                result = d1_aligned * d2_aligned
                op_label = f"{n1} × {n2}"
            elif operation == "divide":
                result = d1_aligned / np.where(d2_aligned != 0, d2_aligned, 1)
                op_label = f"{n1} ÷ {n2}"
            elif operation == "abs_diff":
                result = np.abs(d1_aligned - d2_aligned)
                op_label = f"|{n1} − {n2}|"
            else:
                result = d1_aligned
                op_label = n1
                
        else:  # multi
            # Use first signal's time base
            result_time = signals_data[0][0]
            aligned_data = []
            
            for t, d, n in signals_data:
                if len(t) == len(result_time) and np.allclose(t, result_time):
                    aligned_data.append(d)
                else:
                    aligned_data.append(np.interp(result_time, t, d))
            
            stacked = np.vstack(aligned_data)
            
            if operation == "norm":
                result = np.sqrt(np.sum(stacked**2, axis=0))
                op_label = f"norm({len(signals_data)} signals)"
            elif operation == "mean":
                result = np.mean(stacked, axis=0)
                op_label = f"mean({len(signals_data)} signals)"
            elif operation == "max":
                result = np.max(stacked, axis=0)
                op_label = f"max({len(signals_data)} signals)"
            elif operation == "min":
                result = np.min(stacked, axis=0)
                op_label = f"min({len(signals_data)} signals)"
            else:
                result = stacked[0]
                op_label = "multi"
        
        # Create derived signal
        final_name = output_name if output_name else op_label
        
        derived_signals[final_name] = DerivedSignal(
            name=final_name,
            time=result_time,
            data=result,
            operation=operation,
            source_signals=signal_keys,
        )
        
        print(f"[OPS] Created derived signal: {final_name}", flush=True)
        
        return (
            html.Span(f"✅ Created: {final_name}", className="text-success"),
            build_signal_tree(runs, ""),
            (refresh or 0) + 1,
        )
        
    except Exception as e:
        print(f"[OPS ERROR] {e}", flush=True)
        return html.Span(f"❌ Error: {str(e)[:50]}", className="text-danger"), dash.no_update, dash.no_update


# =============================================================================
# CALLBACKS: Report Builder (P0-9, P0-14)
# =============================================================================

@app.callback(
    Output("modal-report", "is_open"),
    Output("report-subplot-list", "children"),
    Input("btn-report", "n_clicks"),
    Input("btn-report-cancel", "n_clicks"),
    State("modal-report", "is_open"),
    prevent_initial_call=True,
)
def toggle_report_modal(open_clicks, cancel_clicks, is_open):
    """Toggle report modal and populate subplot list"""
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    
    if "btn-report-cancel" in trigger:
        return False, dash.no_update
    
    if "btn-report" in trigger:
        # Build subplot checkbox list with per-subplot settings (P0-10)
        total = view_state.layout_rows * view_state.layout_cols
        subplot_items = []
        
        for i in range(total):
            sp_config = view_state.subplots[i] if i < len(view_state.subplots) else SubplotConfig(index=i)
            sig_count = len(sp_config.assigned_signals)
            
            subplot_items.append(dbc.Card([
                dbc.CardBody([
                    dbc.Checklist(
                        id={"type": "report-include-subplot", "index": i},
                        options=[{"label": f"Subplot {i+1} ({sig_count} signals)", "value": True}],
                        value=[True] if sp_config.include_in_report else [],
                        inline=True,
                        className="mb-1",
                    ),
                    # Per-subplot title/caption/description (P0-10)
                    dbc.Input(
                        id={"type": "report-subplot-title", "index": i},
                        value=sp_config.title,
                        placeholder="Title (optional)...",
                        size="sm",
                        className="mb-1",
                    ),
                    dbc.Textarea(
                        id={"type": "report-subplot-caption", "index": i},
                        value=sp_config.caption,
                        placeholder="Caption (optional)...",
                        rows=1,
                        className="mb-1",
                        style={"fontSize": "11px"},
                    ),
                ], className="p-2"),
            ], className="mb-1"))
        
        return True, subplot_items
    
    return is_open, dash.no_update


@app.callback(
    Output("download-report", "data"),
    Input("btn-report-export", "n_clicks"),
    State("report-title", "value"),
    State("report-intro", "value"),
    State("report-conclusion", "value"),
    State("report-rtl", "value"),
    State("report-format", "value"),
    State({"type": "report-include-subplot", "index": ALL}, "value"),
    State({"type": "report-subplot-title", "index": ALL}, "value"),
    State({"type": "report-subplot-caption", "index": ALL}, "value"),
    prevent_initial_call=True,
)
def export_report(n_clicks, title, intro, conclusion, rtl, format_type, include_list, titles, captions):
    """Export report to HTML or CSV (P0-9)"""
    from datetime import datetime
    
    if not n_clicks:
        return dash.no_update
    
    # Update subplot metadata
    for i, (include, sp_title, sp_caption) in enumerate(zip(include_list, titles, captions)):
        if i < len(view_state.subplots):
            view_state.subplots[i].include_in_report = bool(include and len(include) > 0)
            view_state.subplots[i].title = sp_title or ""
            view_state.subplots[i].caption = sp_caption or ""
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if format_type == "csv":
        # Export data as CSV
        content = _build_csv_export()
        return dict(content=content, filename=f"signal_data_{timestamp}.csv")
    
    elif format_type == "docx":
        # Export DOCX (P1-3: Word document export)
        from report.builder import Report, export_docx, DOCX_AVAILABLE
        import tempfile
        import base64
        
        if not DOCX_AVAILABLE:
            print("[ERROR] python-docx not installed - cannot export DOCX", flush=True)
            return dash.no_update
        
        # Build report object
        report = Report(
            title=title or "Signal Viewer Report",
            introduction=intro or "",
            conclusion=conclusion or "",
            runs=[get_csv_display_name(r.file_path, [r.file_path for r in runs]) for r in runs],
        )
        
        # Add subplot sections
        from report.builder import ReportSection
        for i, sp in enumerate(view_state.subplots):
            if not sp.include_in_report:
                continue
            section = ReportSection(
                title=sp.title or f"Subplot {i + 1}",
                content=sp.caption or "",
                signals=sp.assigned_signals.copy(),
            )
            report.subplot_sections.append(section)
        
        # Create figure for embedding
        fig, _ = create_figure(runs, derived_signals, view_state, signal_settings)
        
        # Export to temp file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = tmp.name
        
        success = export_docx(report, tmp_path, figure=fig, rtl=bool(rtl))
        
        if success:
            with open(tmp_path, 'rb') as f:
                content = base64.b64encode(f.read()).decode('utf-8')
            import os
            os.unlink(tmp_path)
            return dict(content=content, filename=f"report_{timestamp}.docx", base64=True)
        else:
            return dash.no_update
    
    else:  # HTML
        # Build HTML report (P0-14: RTL support for Hebrew)
        html_content = _build_html_report(title, intro, conclusion, rtl)
        return dict(content=html_content, filename=f"report_{timestamp}.html")


def _build_csv_export() -> str:
    """Build CSV export with all visible signals"""
    import io
    lines = []
    
    # Header
    header = ["Time"]
    for sp in view_state.subplots:
        if not sp.include_in_report:
            continue
        for sig_key in sp.assigned_signals:
            run_idx, sig_name = parse_signal_key(sig_key)
            label = get_signal_label(run_idx, sig_name, [r.file_path for r in runs])
            header.append(label)
    
    lines.append(",".join(header))
    
    # Find common time base
    all_times = []
    for run in runs:
        if len(run.time) > 0:
            all_times.append(run.time)
    
    if not all_times:
        return "\n".join(lines)
    
    # Use densest time base
    common_time = max(all_times, key=len)
    
    # Build data rows
    import numpy as np
    for t_idx, t in enumerate(common_time):
        row = [f"{t:.6f}"]
        
        for sp in view_state.subplots:
            if not sp.include_in_report:
                continue
            for sig_key in sp.assigned_signals:
                run_idx, sig_name = parse_signal_key(sig_key)
                
                if run_idx == DERIVED_RUN_IDX:
                    if sig_name in derived_signals:
                        ds = derived_signals[sig_name]
                        val = np.interp(t, ds.time, ds.data)
                    else:
                        val = ""
                elif 0 <= run_idx < len(runs):
                    time_data, sig_data = runs[run_idx].get_signal_data(sig_name)
                    val = np.interp(t, time_data, sig_data) if len(time_data) > 0 else ""
                else:
                    val = ""
                
                row.append(f"{val:.6g}" if isinstance(val, (int, float)) else str(val))
        
        lines.append(",".join(row))
    
    return "\n".join(lines)


def _build_html_report(title: str, intro: str, conclusion: str, rtl: bool) -> str:
    """Build offline HTML report with embedded plots (P0-14: RTL support)"""
    import plotly.io as pio
    
    direction = "rtl" if rtl else "ltr"
    align = "right" if rtl else "left"
    
    # Create figure for report
    fig, _ = create_figure(runs, derived_signals, view_state, signal_settings)
    
    # Convert to HTML div
    plot_html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    
    html = f"""<!DOCTYPE html>
<html lang="{'he' if rtl else 'en'}" dir="{direction}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
            direction: {direction};
            text-align: {align};
        }}
        h1 {{ color: #333; border-bottom: 2px solid #2196F3; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .section {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .plot-container {{ margin: 20px 0; }}
        .subplot-info {{ background: #f9f9f9; padding: 10px; border-radius: 4px; margin-top: 10px; }}
        .meta {{ color: #666; font-size: 12px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="meta">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
"""
    
    if intro:
        html += f"""
    <div class="section">
        <h2>Introduction</h2>
        <p dir="{direction}">{intro}</p>
    </div>
"""
    
    # Add plots
    html += f"""
    <div class="section">
        <h2>Plots</h2>
        <div class="plot-container">
            {plot_html}
        </div>
"""
    
    # Add per-subplot info
    for i, sp in enumerate(view_state.subplots):
        if not sp.include_in_report:
            continue
        
        sp_title = sp.title or f"Subplot {i+1}"
        html += f"""
        <div class="subplot-info">
            <strong>{sp_title}</strong>
"""
        if sp.caption:
            html += f"<p>{sp.caption}</p>"
        
        html += f"""
            <small>Signals: {len(sp.assigned_signals)}, Mode: {sp.mode.upper()}</small>
        </div>
"""
    
    html += "    </div>\n"
    
    if conclusion:
        html += f"""
    <div class="section">
        <h2>Conclusion</h2>
        <p dir="{direction}">{conclusion}</p>
    </div>
"""
    
    html += """
</body>
</html>
"""
    
    return html


# =============================================================================
# CALLBACKS: Derived Signal Removal (P0-8)
# =============================================================================

@app.callback(
    Output("signal-tree", "children", allow_duplicate=True),
    Output("store-refresh", "data", allow_duplicate=True),
    Input("btn-clear-all-derived", "n_clicks"),
    State("store-refresh", "data"),
    State("store-collapsed-runs", "data"),
    prevent_initial_call=True,
)
def clear_all_derived(n_clicks, refresh, collapsed_runs):
    """Clear all derived signals (P0-8)"""
    global derived_signals, view_state
    
    if not n_clicks:
        return dash.no_update, dash.no_update
    
    # Get list of derived signal names to remove from assignments
    derived_names = list(derived_signals.keys())
    
    # Clear derived signals dict
    derived_signals.clear()
    
    # Remove from subplot assignments
    for sp in view_state.subplots:
        sp.assigned_signals = [
            sig for sig in sp.assigned_signals
            if not sig.startswith(f"{DERIVED_RUN_IDX}:")
        ]
    
    print(f"[DERIVED] Cleared all {len(derived_names)} derived signals", flush=True)
    
    return build_signal_tree(runs, "", collapsed_runs or {}), (refresh or 0) + 1


@app.callback(
    Output("signal-tree", "children", allow_duplicate=True),
    Output("store-refresh", "data", allow_duplicate=True),
    Input({"type": "btn-remove-derived", "name": ALL}, "n_clicks"),
    State("store-refresh", "data"),
    State("store-collapsed-runs", "data"),
    prevent_initial_call=True,
)
def remove_single_derived(remove_clicks, refresh, collapsed_runs):
    """Remove a single derived signal (P0-8)"""
    global derived_signals, view_state
    
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    
    # Check if any button was actually clicked
    if not any(c for c in remove_clicks if c):
        return dash.no_update, dash.no_update
    
    # Find which button was clicked
    trigger = ctx.triggered[0]["prop_id"]
    try:
        trigger_dict = json.loads(trigger.rsplit(".", 1)[0])
        derived_name = trigger_dict["name"]
    except:
        return dash.no_update, dash.no_update
    
    if derived_name not in derived_signals:
        return dash.no_update, dash.no_update
    
    # Check for dependent derived signals
    dependents = []
    sig_key_to_remove = make_signal_key(DERIVED_RUN_IDX, derived_name)
    for name, ds in derived_signals.items():
        if name != derived_name and sig_key_to_remove in ds.source_signals:
            dependents.append(name)
    
    # Remove dependents too (cascading delete)
    for dep_name in dependents:
        del derived_signals[dep_name]
        print(f"[DERIVED] Also removed dependent: {dep_name}", flush=True)
    
    # Remove the target derived signal
    del derived_signals[derived_name]
    
    # Remove from subplot assignments
    for sp in view_state.subplots:
        sp.assigned_signals = [
            sig for sig in sp.assigned_signals
            if sig != sig_key_to_remove and not any(
                sig == make_signal_key(DERIVED_RUN_IDX, dep) for dep in dependents
            )
        ]
    
    print(f"[DERIVED] Removed '{derived_name}' and {len(dependents)} dependents", flush=True)
    
    return build_signal_tree(runs, "", collapsed_runs or {}), (refresh or 0) + 1


# =============================================================================
# MAIN
# =============================================================================

def open_browser():
    """Open browser after startup"""
    import time
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8050")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  Signal Viewer Pro")
    print("  http://127.0.0.1:8050")
    print("=" * 50 + "\n")
    
    # Auto-open browser
    threading.Thread(target=open_browser, daemon=True).start()
    
    app.run_server(
        host="127.0.0.1",
        port=8050,
        debug=False,
    )
