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
from typing import Dict, List, Optional, Tuple
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
    """
    Reset all global state to initial values (P0 - clean start).
    
    This ensures:
    - No ghost plots from previous sessions
    - No cached signal data
    - Clean view state with no assignments
    """
    global runs, derived_signals, signal_settings, view_state, stream_engine
    runs = []
    derived_signals = {}
    signal_settings = {}
    view_state = ViewState()
    # Ensure subplots are initialized but EMPTY (no auto-assignment)
    view_state.subplots = [SubplotConfig(index=0)]
    stream_engine = StreamEngine()
    print("[INIT] Global state reset - clean start, no cached data", flush=True)

# Initialize clean state on module load
runs: List[Run] = []
derived_signals: Dict[str, DerivedSignal] = {}
signal_settings: Dict[str, Dict] = {}
view_state = ViewState()
stream_engine = StreamEngine()
_reset_state()  # Ensure clean start - P0 requirement


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
                # Check if signal has custom settings
                has_settings = sig_key in signal_settings and any(
                    signal_settings[sig_key].get(k) for k in ["display_name", "color", "is_state"]
                    if k != "line_width" or signal_settings[sig_key].get(k, 1.5) != 1.5
                )
                settings_indicator = " ⚙" if has_settings else ""
                
                signal_items.append(
                    html.Div([
                        html.Span(
                            sig + settings_indicator,
                            id={"type": "signal-item", "key": sig_key},
                            className="small",
                            style={"cursor": "pointer", "flex": "1"},
                            n_clicks=0,
                        ),
                        html.Button(
                            "⚙",
                            id={"type": "btn-signal-props", "key": sig_key},
                            className="btn btn-link btn-sm p-0 text-muted",
                            style={"fontSize": "10px"},
                            title="Edit properties",
                            n_clicks=0,
                        ),
                    ], className="py-1 px-2 signal-item d-flex align-items-center")
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
    State("select-linked-runs", "value"),
    prevent_initial_call=True,
)
def handle_assignment(signal_clicks, remove_clicks, vs_data, active_subplot, linked_runs):
    """
    Handle signal assignment - ONLY when user explicitly clicks.
    
    Features:
    - Check that the triggered n_clicks is actually > 0 to prevent auto-assignment
    - Support linked CSV mode: when linked, assign same signal from all linked CSVs
    """
    global view_state
    
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    trigger_value = ctx.triggered[0]["value"]
    
    # CRITICAL: Only assign if user actually clicked (n_clicks > 0)
    # This prevents auto-assignment when signal tree is rebuilt
    if trigger_value is None or trigger_value == 0:
        return dash.no_update, dash.no_update
    
    active_sp = int(active_subplot or 0)
    
    # Ensure subplot config exists
    while len(view_state.subplots) <= active_sp:
        view_state.subplots.append(SubplotConfig(index=len(view_state.subplots)))
    
    sp_config = view_state.subplots[active_sp]
    
    if "signal-item" in trigger:
        # Add signal - only if actually clicked
        trigger_dict = json.loads(trigger.rsplit(".", 1)[0])
        sig_key = trigger_dict["key"]
        
        run_idx, sig_name = parse_signal_key(sig_key)
        
        # Check if linked mode is active
        linked_runs = linked_runs or []
        if linked_runs and len(linked_runs) >= 2 and run_idx != DERIVED_RUN_IDX:
            # Linked mode: add same signal from ALL linked runs
            linked_runs = [int(r) for r in linked_runs]
            added = []
            for link_run_idx in linked_runs:
                if link_run_idx < len(runs) and sig_name in runs[link_run_idx].signals:
                    linked_key = make_signal_key(link_run_idx, sig_name)
                    if linked_key not in sp_config.assigned_signals:
                        sp_config.assigned_signals.append(linked_key)
                        added.append(linked_key)
            print(f"[ASSIGN LINKED] Added {len(added)} signals for '{sig_name}' from linked runs", flush=True)
        else:
            # Normal mode: add just this signal
            print(f"[ASSIGN] User clicked: {sig_key} -> Subplot {active_sp + 1}", flush=True)
            if sig_key not in sp_config.assigned_signals:
                sp_config.assigned_signals.append(sig_key)
    
    elif "btn-remove-assigned" in trigger:
        # Remove signal
        trigger_dict = json.loads(trigger.rsplit(".", 1)[0])
        idx = trigger_dict["index"]
        
        # Check if linked mode
        linked_runs = linked_runs or []
        if linked_runs and len(linked_runs) >= 2 and 0 <= idx < len(sp_config.assigned_signals):
            sig_key = sp_config.assigned_signals[idx]
            run_idx, sig_name = parse_signal_key(sig_key)
            
            if run_idx != DERIVED_RUN_IDX:
                # Linked mode: remove same signal from ALL linked runs
                linked_runs = [int(r) for r in linked_runs]
                to_remove = []
                for link_run_idx in linked_runs:
                    linked_key = make_signal_key(link_run_idx, sig_name)
                    if linked_key in sp_config.assigned_signals:
                        to_remove.append(linked_key)
                for key in to_remove:
                    sp_config.assigned_signals.remove(key)
                print(f"[REMOVE LINKED] Removed {len(to_remove)} signals for '{sig_name}'", flush=True)
            else:
                sp_config.assigned_signals.pop(idx)
        elif 0 <= idx < len(sp_config.assigned_signals):
            sp_config.assigned_signals.pop(idx)
    
    view_state.active_subplot = active_sp
    
    return _view_state_to_dict(), build_assigned_list(sp_config, runs)


@app.callback(
    Output("link-mode-panel", "style"),
    Output("btn-toggle-link-mode", "color"),
    Output("btn-toggle-link-mode", "outline"),
    Input("btn-toggle-link-mode", "n_clicks"),
    State("link-mode-panel", "style"),
    prevent_initial_call=True,
)
def toggle_link_mode(n_clicks, current_style):
    """Toggle link mode panel visibility"""
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update
    
    is_hidden = current_style and current_style.get("display") == "none"
    if is_hidden:
        return {"display": "block"}, "info", False
    else:
        return {"display": "none"}, "secondary", True


@app.callback(
    Output("select-linked-runs", "options"),
    Input("store-refresh", "data"),
)
def update_linked_runs_options(refresh):
    """Update linked runs dropdown options"""
    if not runs:
        return []
    return [{"label": run.csv_display_name, "value": i} for i, run in enumerate(runs)]


@app.callback(
    Output("select-linked-runs", "value"),
    Input("btn-link-all", "n_clicks"),
    Input("btn-unlink-all", "n_clicks"),
    prevent_initial_call=True,
)
def handle_link_buttons(link_all_clicks, unlink_all_clicks):
    """
    Handle Link All / Unlink All buttons (Feature 2).
    
    - Link All: Select all loaded CSVs for linking
    - Unlink All: Clear all linked selections
    """
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    
    if "btn-link-all" in trigger:
        # Link all runs
        if runs:
            print(f"[LINK] Linked all {len(runs)} runs", flush=True)
            return list(range(len(runs)))
        return []
    
    elif "btn-unlink-all" in trigger:
        # Unlink all
        print("[LINK] Unlinked all runs", flush=True)
        return []
    
    return dash.no_update


def build_assigned_list(sp_config: SubplotConfig, runs_list: List[Run]) -> list:
    """Build assigned signals list with edit button for properties"""
    if not sp_config.assigned_signals:
        return [html.P("Click signals to assign", className="text-muted small")]
    
    items = []
    run_paths = [r.file_path for r in runs_list]
    
    for idx, sig_key in enumerate(sp_config.assigned_signals):
        run_idx, sig_name = parse_signal_key(sig_key)
        
        # Get custom display name if set
        settings = signal_settings.get(sig_key, {})
        custom_name = settings.get("display_name")
        label = custom_name if custom_name else get_signal_label(run_idx, sig_name, run_paths)
        
        # Show indicator for special settings
        indicators = []
        if settings.get("is_state"):
            indicators.append("📊")  # State signal indicator
        if settings.get("scale", 1.0) != 1.0 or settings.get("offset", 0.0) != 0.0:
            indicators.append("⚡")  # Scale/offset applied
        
        indicator_str = " ".join(indicators)
        
        items.append(
            dbc.Row([
                # Signal label with indicators
                dbc.Col([
                    html.Span(indicator_str + " " if indicator_str else "", className="small"),
                    html.Span(label, className="small text-truncate", title=sig_name),
                ], width=8, className="d-flex align-items-center"),
                # Edit button
                dbc.Col(
                    html.Button("✎", id={"type": "btn-edit-signal", "key": sig_key},
                               className="btn btn-link btn-sm text-info p-0",
                               title="Edit signal properties"),
                    width=2, className="text-center",
                ),
                # Remove button
                dbc.Col(
                    html.Button("×", id={"type": "btn-remove-assigned", "index": idx},
                               className="btn btn-link btn-sm text-danger p-0"),
                    width=2, className="text-end",
                ),
            ], className="g-0 mb-1 align-items-center")
        )
    return items


def _view_state_to_dict() -> dict:
    """
    Convert ViewState to dict for store (P1, P5 - complete state preservation).
    
    Saves ALL subplot properties to ensure tab switching preserves data.
    CRITICAL: Uses list() to create copies to avoid reference sharing between tabs.
    """
    return {
        "layout_rows": view_state.layout_rows,
        "layout_cols": view_state.layout_cols,
        "active_subplot": view_state.active_subplot,
        "theme": view_state.theme,
        "cursor_time": view_state.cursor_time,
        "cursor_enabled": view_state.cursor_enabled,
        "cursor_show_all": getattr(view_state, 'cursor_show_all', True),
        "subplots": [
            {
                "index": sp.index,
                "mode": sp.mode,
                "assigned_signals": list(sp.assigned_signals),  # Copy!
                "x_signal": sp.x_signal,
                "y_signals": list(sp.y_signals),  # Copy!
                "xy_alignment": sp.xy_alignment,
                "title": sp.title,
                "caption": sp.caption,
                "description": sp.description,
                "include_in_report": sp.include_in_report,
            }
            for sp in view_state.subplots
        ],
    }


# =============================================================================
# CALLBACKS: Layout & Subplot Selection
# =============================================================================

def _old_idx_to_row_col(idx: int, old_cols: int) -> Tuple[int, int]:
    """Convert old subplot index to (row, col) 0-based."""
    return (idx // old_cols, idx % old_cols)


def _row_col_to_new_idx(row: int, col: int, new_cols: int) -> int:
    """Convert (row, col) 0-based to new subplot index."""
    return row * new_cols + col


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
    
    Visual position preservation strategy:
    - Signals stay in the SAME ROW/COL position visually
    - When going from 2x1 to 2x2: top stays top-left, bottom stays bottom-left
    - When shrinking, orphan signals move to nearest valid position
    """
    global view_state
    
    rows = int(rows or 1)
    cols = int(cols or 1)
    new_total = rows * cols
    old_rows = view_state.layout_rows
    old_cols = view_state.layout_cols
    old_total = old_rows * old_cols
    
    print(f"[LAYOUT] Changing from {old_rows}x{old_cols} to {rows}x{cols}", flush=True)
    
    # Collect all current assignments with their visual positions
    old_assignments = {}  # {(row, col): [signal_keys]}
    for i, sp in enumerate(view_state.subplots):
        if sp.assigned_signals:
            r, c = _old_idx_to_row_col(i, old_cols)
            old_assignments[(r, c)] = sp.assigned_signals.copy()
            print(f"  Subplot {i} (r{r+1},c{c+1}): {sp.assigned_signals}", flush=True)
    
    # Update layout dimensions
    view_state.layout_rows = rows
    view_state.layout_cols = cols
    
    # Create new subplot configs
    new_subplots = [SubplotConfig(index=i) for i in range(new_total)]
    
    # Remap assignments to preserve visual position
    orphan_signals = []
    for (old_row, old_col), signals in old_assignments.items():
        # If row/col still valid in new layout, keep there
        if old_row < rows and old_col < cols:
            new_idx = _row_col_to_new_idx(old_row, old_col, cols)
            new_subplots[new_idx].assigned_signals = signals.copy()
            print(f"  Remapped (r{old_row+1},c{old_col+1}) -> Subplot {new_idx+1}", flush=True)
        else:
            # Position no longer exists - find nearest valid
            # Clamp row and col to new bounds
            clamped_row = min(old_row, rows - 1)
            clamped_col = min(old_col, cols - 1)
            new_idx = _row_col_to_new_idx(clamped_row, clamped_col, cols)
            new_subplots[new_idx].assigned_signals.extend(signals)
            print(f"  Orphan (r{old_row+1},c{old_col+1}) -> Subplot {new_idx+1}", flush=True)
    
    # Copy other properties from old subplots based on visual position
    old_props = {}  # {(row, col): props_dict}
    for i, sp in enumerate(view_state.subplots):
        r, c = _old_idx_to_row_col(i, old_cols)
        old_props[(r, c)] = {
            "mode": sp.mode,
            "title": sp.title,
            "caption": sp.caption,
            "description": sp.description,
            "x_signal": sp.x_signal,
            "y_signals": sp.y_signals,
        }
    
    # Apply old props to new subplots at same visual position
    for i, new_sp in enumerate(new_subplots):
        r, c = _old_idx_to_row_col(i, cols)
        if (r, c) in old_props:
            props = old_props[(r, c)]
            new_sp.mode = props.get("mode", "time")
            new_sp.title = props.get("title", "")
            new_sp.caption = props.get("caption", "")
            new_sp.description = props.get("description", "")
            new_sp.x_signal = props.get("x_signal")
            new_sp.y_signals = props.get("y_signals", [])
    
    view_state.subplots = new_subplots
    
    # Remap active subplot to preserve visual position
    old_active = int(current_sp or 0)
    old_active_row, old_active_col = _old_idx_to_row_col(old_active, old_cols)
    
    # Clamp to new bounds if needed
    new_active_row = min(old_active_row, rows - 1)
    new_active_col = min(old_active_col, cols - 1)
    value = _row_col_to_new_idx(new_active_row, new_active_col, cols)
    view_state.active_subplot = value
    
    print(f"[LAYOUT] Active subplot: {old_active} (r{old_active_row+1},c{old_active_col+1}) -> {value}", flush=True)
    
    # Format: "N / M" for compact display
    options = [{"label": f"{i + 1} / {new_total}", "value": i} for i in range(new_total)]
    
    # Get current subplot config for assigned list
    sp_config = view_state.subplots[value]
    assigned_list = build_assigned_list(sp_config, runs)
    
    print(f"[LAYOUT] Done: {len(options)} subplots, selected={value}", flush=True)
    
    return options, value, assigned_list


# Initialize subplot selector on app load (runs once on startup)
@app.callback(
    Output("select-subplot", "options", allow_duplicate=True),
    Output("select-subplot", "value", allow_duplicate=True),
    Output("active-subplot-badge", "children", allow_duplicate=True),
    Input("store-refresh", "data"),
    prevent_initial_call='initial_duplicate',  # Allow initial call with duplicate outputs
)
def init_subplot_selector(refresh):
    """
    Initialize subplot selector on app startup.
    Ensures the SP: dropdown always shows a proper value (never empty).
    """
    global view_state
    
    total = view_state.layout_rows * view_state.layout_cols
    options = [{"label": f"{i + 1} / {total}", "value": i} for i in range(total)]
    value = min(view_state.active_subplot, total - 1) if total > 0 else 0
    badge = f"Subplot {value + 1} / {total}"
    
    return options, value, badge


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


# =============================================================================
# CALLBACKS: Axis Limits (Feature 5)
# =============================================================================

@app.callback(
    Output("input-xlim-min", "value"),
    Output("input-xlim-max", "value"),
    Output("input-ylim-min", "value"),
    Output("input-ylim-max", "value"),
    Input("select-subplot", "value"),
    Input("btn-reset-axis-limits", "n_clicks"),
    State("select-axis-scope", "value"),
    prevent_initial_call=True,
)
def load_axis_limits(subplot_idx, reset_clicks, scope):
    """Load current axis limits for the active subplot"""
    global view_state
    
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
    
    sp_idx = int(subplot_idx or 0)
    
    # On reset, clear limits based on scope
    if "btn-reset-axis-limits" in trigger:
        if scope == "all":
            # Reset all subplots in tab
            total = view_state.layout_rows * view_state.layout_cols
            for i in range(min(total, len(view_state.subplots))):
                view_state.subplots[i].xlim = None
                view_state.subplots[i].ylim = None
            print(f"[AXIS] Reset limits for ALL {total} subplots", flush=True)
        else:
            # Reset active subplot only
            if sp_idx < len(view_state.subplots):
                view_state.subplots[sp_idx].xlim = None
                view_state.subplots[sp_idx].ylim = None
                print(f"[AXIS] Reset limits for subplot {sp_idx + 1}", flush=True)
        return None, None, None, None
    
    # Load current limits from active subplot
    if sp_idx < len(view_state.subplots):
        sp_config = view_state.subplots[sp_idx]
        xlim = sp_config.xlim
        ylim = sp_config.ylim
        
        return (
            xlim[0] if xlim else None,
            xlim[1] if xlim else None,
            ylim[0] if ylim else None,
            ylim[1] if ylim else None,
        )
    
    return None, None, None, None


@app.callback(
    Output("store-refresh", "data", allow_duplicate=True),
    Input("btn-apply-axis-limits", "n_clicks"),
    State("input-xlim-min", "value"),
    State("input-xlim-max", "value"),
    State("input-ylim-min", "value"),
    State("input-ylim-max", "value"),
    State("select-axis-scope", "value"),
    State("select-subplot", "value"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def apply_axis_limits(n_clicks, xlim_min, xlim_max, ylim_min, ylim_max, scope, subplot_idx, refresh):
    """Apply axis limits to active subplot or all subplots in tab"""
    global view_state
    
    if not n_clicks:
        return dash.no_update
    
    # Build xlim/ylim values
    xlim = None
    ylim = None
    
    if xlim_min is not None and xlim_max is not None:
        xlim = [float(xlim_min), float(xlim_max)]
    elif xlim_min is not None or xlim_max is not None:
        xlim = [
            float(xlim_min) if xlim_min is not None else None,
            float(xlim_max) if xlim_max is not None else None,
        ]
    
    if ylim_min is not None and ylim_max is not None:
        ylim = [float(ylim_min), float(ylim_max)]
    elif ylim_min is not None or ylim_max is not None:
        ylim = [
            float(ylim_min) if ylim_min is not None else None,
            float(ylim_max) if ylim_max is not None else None,
        ]
    
    if scope == "all":
        # Apply to all subplots in current tab
        total = view_state.layout_rows * view_state.layout_cols
        for i in range(total):
            while len(view_state.subplots) <= i:
                view_state.subplots.append(SubplotConfig(index=len(view_state.subplots)))
            view_state.subplots[i].xlim = xlim
            view_state.subplots[i].ylim = ylim
        print(f"[AXIS] Set limits for ALL {total} subplots: xlim={xlim}, ylim={ylim}", flush=True)
    else:
        # Apply to active subplot only
        sp_idx = int(subplot_idx or 0)
        while len(view_state.subplots) <= sp_idx:
            view_state.subplots.append(SubplotConfig(index=len(view_state.subplots)))
        view_state.subplots[sp_idx].xlim = xlim
        view_state.subplots[sp_idx].ylim = ylim
        print(f"[AXIS] Set limits for subplot {sp_idx + 1}: xlim={xlim}, ylim={ylim}", flush=True)
    
    return (refresh or 0) + 1


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
    Output("cursor-slider", "disabled"),
    Input("store-refresh", "data"),
    Input("switch-cursor", "value"),
    State("cursor-slider", "value"),
)
def update_cursor_range(refresh, cursor_enabled, current_value):
    """
    Update cursor slider range based on ASSIGNED signals only (P0-3).
    
    - Min/max computed from assigned signals in current view
    - If no signals assigned, slider is disabled
    - Preserves current value if within new range
    """
    is_enabled = cursor_enabled and len(cursor_enabled) > 0
    if not is_enabled or not runs:
        return 0, 100, 0, True  # Disabled
    
    # Find time range from ASSIGNED signals only
    t_min, t_max = float('inf'), float('-inf')
    has_assigned = False
    
    for sp in view_state.subplots:
        for sig_key in sp.assigned_signals:
            run_idx, sig_name = parse_signal_key(sig_key)
            
            if run_idx == DERIVED_RUN_IDX:
                if sig_name in derived_signals:
                    ds = derived_signals[sig_name]
                    if len(ds.time) > 0:
                        t_min = min(t_min, float(ds.time[0]))
                        t_max = max(t_max, float(ds.time[-1]))
                        has_assigned = True
            elif 0 <= run_idx < len(runs):
                run = runs[run_idx]
                if len(run.time) > 0:
                    t_min = min(t_min, float(run.time[0]))
                    t_max = max(t_max, float(run.time[-1]))
                    has_assigned = True
    
    if not has_assigned or t_min >= t_max:
        return 0, 100, 0, True  # Disabled - no signals assigned
    
    # Preserve current value if within range, else reset to min
    new_value = current_value if (current_value is not None and t_min <= current_value <= t_max) else t_min
    
    return t_min, t_max, new_value, False  # Enabled


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
    Output("cursor-time-display", "children", allow_duplicate=True),
    Input("btn-cursor-jump", "n_clicks"),
    Input("cursor-jump-input", "n_submit"),  # Also trigger on Enter key
    State("cursor-jump-input", "value"),
    State("cursor-slider", "min"),
    State("cursor-slider", "max"),
    prevent_initial_call=True,
)
def cursor_jump_to_time(n_clicks, n_submit, target_time, t_min, t_max):
    """
    Jump cursor to specific time - finds NEAREST SAMPLE.
    
    - Triggers on button click OR Enter key press
    - Finds nearest actual sample time (not interpolated)
    - Supports decimal values (1.24, 0.001, etc.)
    """
    import numpy as np
    
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    
    # Check if target_time is provided
    if target_time is None or target_time == "":
        return dash.no_update, dash.no_update
    
    try:
        target_time = float(target_time)
    except (ValueError, TypeError):
        return dash.no_update, dash.no_update
    
    # Find nearest sample time from ASSIGNED signals
    nearest_time = target_time
    min_dist = float('inf')
    
    for sp in view_state.subplots:
        for sig_key in sp.assigned_signals:
            run_idx, sig_name = parse_signal_key(sig_key)
            
            time_arr = None
            if run_idx == DERIVED_RUN_IDX:
                if sig_name in derived_signals:
                    time_arr = derived_signals[sig_name].time
            elif 0 <= run_idx < len(runs):
                time_arr = runs[run_idx].time
            
            if time_arr is not None and len(time_arr) > 0:
                idx = np.searchsorted(time_arr, target_time)
                # Check both neighbors
                for check_idx in [max(0, idx - 1), min(len(time_arr) - 1, idx)]:
                    dist = abs(time_arr[check_idx] - target_time)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_time = float(time_arr[check_idx])
    
    # Clamp to valid range
    nearest_time = max(t_min, min(t_max, nearest_time))
    
    # Update global state
    view_state.cursor_time = nearest_time
    
    print(f"[CURSOR] Jump to T={target_time:.6f} → nearest sample T={nearest_time:.6f}", flush=True)
    return nearest_time, f"T = {nearest_time:.6f}"


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
    """
    Save complete session (P5 - Complete persistence).
    
    Includes:
    - Run paths
    - Complete view state with all subplot properties
    - Signal settings (colors, widths, etc.)
    - Derived signals
    """
    from datetime import datetime
    
    run_paths = [r.file_path for r in runs]
    
    # Serialize derived signals
    derived_data = {}
    for name, ds in derived_signals.items():
        derived_data[name] = {
            "name": ds.name,
            "time": ds.time.tolist(),
            "data": ds.data.tolist(),
            "operation": ds.operation,
            "source_signals": ds.source_signals,
            "display_name": ds.display_name,
            "color": ds.color,
            "line_width": ds.line_width,
        }
    
    session = {
        "version": "5.0",
        "timestamp": datetime.now().isoformat(),
        "run_paths": run_paths,
        "view_state": _view_state_to_dict(),
        "signal_settings": signal_settings,
        "derived_signals": derived_data,
    }
    
    content = json.dumps(session, indent=2)
    filename = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    print(f"[SESSION] Saved: {len(run_paths)} runs, {len(derived_data)} derived signals", flush=True)
    
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
    
    # Clear and reload (P5 - Complete persistence)
    runs = []
    derived_signals.clear()
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
    signal_settings.clear()
    signal_settings.update(session.get("signal_settings", {}))
    
    # Restore derived signals
    import numpy as np
    for name, ds_data in session.get("derived_signals", {}).items():
        derived_signals[name] = DerivedSignal(
            name=ds_data.get("name", name),
            time=np.array(ds_data.get("time", [])),
            data=np.array(ds_data.get("data", [])),
            operation=ds_data.get("operation", "loaded"),
            source_signals=ds_data.get("source_signals", []),
            display_name=ds_data.get("display_name"),
            color=ds_data.get("color"),
            line_width=ds_data.get("line_width", 1.5),
        )
    
    actual_paths = [r.file_path for r in runs]
    
    print(f"[SESSION] Loaded: {len(runs)} runs, {len(derived_signals)} derived signals", flush=True)
    
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
    Render tab bar with clickable tabs (P2-6).
    
    Required UX:
    - Tab1 × Tab2 × +
    - Tabs numbered sequentially: Tab 1, Tab 2, ...
    - Exactly N tabs visible = N views
    - Cannot remove last tab
    """
    # Ensure we always have at least one tab
    if not tabs:
        tabs = [{"id": "tab_1", "name": "Tab 1"}]
    
    # Ensure active_tab is valid
    if not active_tab or not any(t["id"] == active_tab for t in tabs):
        active_tab = tabs[0]["id"]
    
    tab_buttons = []
    can_close = len(tabs) > 1  # Cannot remove last tab
    
    print(f"[TABS] Rendering {len(tabs)} tabs, active={active_tab}", flush=True)
    
    for idx, tab in enumerate(tabs):
        is_active = tab["id"] == active_tab
        
        # Tab button - shows sequential number (Tab 1, Tab 2, ...)
        display_name = f"Tab {idx + 1}"
        
        tab_buttons.append(
            dbc.Button(
                display_name,
                id={"type": "btn-tab", "id": tab["id"]},
                size="sm",
                color="info" if is_active else "secondary",
                outline=not is_active,
                className="me-1",
                n_clicks=0,
                style={"fontWeight": "bold" if is_active else "normal"},
            )
        )
        
        # Close button (×) only if >1 tab exists
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
    
    return tab_buttons if tab_buttons else [html.Span("Tab 1", className="text-info small")]


@app.callback(
    Output("store-tabs", "data", allow_duplicate=True),
    Output("store-active-tab", "data", allow_duplicate=True),
    Output("store-tab-view-states", "data", allow_duplicate=True),
    Output("store-refresh", "data", allow_duplicate=True),
    Output("select-rows", "value", allow_duplicate=True),
    Output("select-cols", "value", allow_duplicate=True),
    Output("select-subplot", "value", allow_duplicate=True),
    Input("btn-add-tab", "n_clicks"),
    State("store-tabs", "data"),
    State("store-active-tab", "data"),
    State("store-tab-view-states", "data"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def add_tab(n_clicks, tabs, current_tab, tab_view_states, refresh):
    """
    Add a new tab with fresh view state (P2-6).
    
    - New tab is numbered sequentially
    - New tab starts with empty view state
    """
    global view_state
    
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    tabs = tabs or []
    tab_view_states = tab_view_states or {}
    
    # Save current view state to current tab before creating new one
    if current_tab:
        tab_view_states[current_tab] = _view_state_to_dict()
    
    # Generate unique ID with timestamp for uniqueness
    new_num = len(tabs) + 1
    new_id = f"tab_{new_num}_{int(datetime.now().timestamp())}"
    new_tab = {"id": new_id, "name": f"Tab {new_num}"}
    tabs.append(new_tab)
    
    # Reset view state for new tab (fresh start, no signals assigned)
    view_state.layout_rows = 1
    view_state.layout_cols = 1
    view_state.active_subplot = 0
    view_state.subplots = [SubplotConfig(index=0)]
    
    print(f"[TABS] Created Tab {new_num}: {new_id}", flush=True)
    
    return (
        tabs,
        new_id,
        tab_view_states,
        (refresh or 0) + 1,
        1,  # Reset rows
        1,  # Reset cols
        0,  # Reset subplot
    )


@app.callback(
    Output("store-active-tab", "data", allow_duplicate=True),
    Output("store-tab-view-states", "data", allow_duplicate=True),
    Output("store-refresh", "data", allow_duplicate=True),
    Output("select-rows", "value", allow_duplicate=True),
    Output("select-cols", "value", allow_duplicate=True),
    Output("select-subplot", "value", allow_duplicate=True),
    Input({"type": "btn-tab", "id": ALL}, "n_clicks"),
    State("store-tabs", "data"),
    State("store-active-tab", "data"),
    State("store-tab-view-states", "data"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def switch_tab(tab_clicks, tabs, current_tab, tab_view_states, refresh):
    """
    Switch to clicked tab with per-tab view state management.
    
    - Saves current view state to current tab
    - Restores view state from target tab
    - Updates layout controls to match
    """
    global view_state
    
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Check if any button was actually clicked
    if not any(c for c in tab_clicks if c):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    try:
        trigger_dict = json.loads(trigger.rsplit(".", 1)[0])
        new_tab_id = trigger_dict["id"]
    except:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Don't do anything if clicking on the same tab
    if new_tab_id == current_tab:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    tab_view_states = tab_view_states or {}
    
    # Save current view state to current tab
    if current_tab:
        tab_view_states[current_tab] = _view_state_to_dict()
        print(f"[TABS] Saved view state for tab: {current_tab}", flush=True)
    
    # Restore view state from target tab (or use defaults for new tab)
    if new_tab_id in tab_view_states:
        saved_state = tab_view_states[new_tab_id]
        view_state.layout_rows = saved_state.get("layout_rows", 1)
        view_state.layout_cols = saved_state.get("layout_cols", 1)
        view_state.active_subplot = saved_state.get("active_subplot", 0)
        view_state.theme = saved_state.get("theme", "dark")
        view_state.cursor_time = saved_state.get("cursor_time")
        view_state.cursor_enabled = saved_state.get("cursor_enabled", False)
        
        # Restore subplot configs with ALL properties (P1 - preserve all data)
        # CRITICAL: Use list() to create copies, not references
        view_state.subplots = []
        for sp_data in saved_state.get("subplots", []):
            sp = SubplotConfig(
                index=sp_data.get("index", len(view_state.subplots)),
                mode=sp_data.get("mode", "time"),
                assigned_signals=list(sp_data.get("assigned_signals", [])),  # Copy!
                x_signal=sp_data.get("x_signal"),
                y_signals=list(sp_data.get("y_signals", [])),  # Copy!
                xy_alignment=sp_data.get("xy_alignment", "linear"),
                title=sp_data.get("title", ""),
                caption=sp_data.get("caption", ""),
                description=sp_data.get("description", ""),
                include_in_report=sp_data.get("include_in_report", True),
            )
            view_state.subplots.append(sp)
        
        print(f"[TABS] Restored view state for tab: {new_tab_id} with {len(view_state.subplots)} subplots", flush=True)
        for i, sp in enumerate(view_state.subplots):
            print(f"  Subplot {i}: {sp.assigned_signals}", flush=True)
    else:
        # New tab - reset to defaults but keep data
        view_state.layout_rows = 1
        view_state.layout_cols = 1
        view_state.active_subplot = 0
        view_state.subplots = [SubplotConfig(index=0)]
        print(f"[TABS] Created fresh view state for new tab: {new_tab_id}", flush=True)
    
    print(f"[TABS] Switched to tab: {new_tab_id}", flush=True)
    
    return (
        new_tab_id,
        tab_view_states,
        (refresh or 0) + 1,
        view_state.layout_rows,
        view_state.layout_cols,
        view_state.active_subplot,
    )


@app.callback(
    Output("store-tabs", "data", allow_duplicate=True),
    Output("store-active-tab", "data", allow_duplicate=True),
    Output("store-tab-view-states", "data", allow_duplicate=True),
    Output("store-refresh", "data", allow_duplicate=True),
    Output("select-rows", "value", allow_duplicate=True),
    Output("select-cols", "value", allow_duplicate=True),
    Output("select-subplot", "value", allow_duplicate=True),
    Input({"type": "btn-close-tab", "id": ALL}, "n_clicks"),
    State("store-tabs", "data"),
    State("store-active-tab", "data"),
    State("store-tab-view-states", "data"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def close_tab(close_clicks, tabs, active_tab, tab_view_states, refresh):
    """Close a tab - disabled if only 1 tab"""
    global view_state
    
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    if not any(c for c in close_clicks if c):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    if len(tabs) <= 1:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    try:
        trigger_dict = json.loads(trigger.rsplit(".", 1)[0])
        tab_id = trigger_dict["id"]
    except:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    tab_view_states = tab_view_states or {}
    
    # Remove tab and its view state
    tabs = [t for t in tabs if t["id"] != tab_id]
    if tab_id in tab_view_states:
        del tab_view_states[tab_id]
    
    # If we closed the active tab, switch to first tab and restore its state
    if active_tab == tab_id:
        new_active = tabs[0]["id"]
        
        # Restore view state from new active tab
        if new_active in tab_view_states:
            saved_state = tab_view_states[new_active]
            view_state.layout_rows = saved_state.get("layout_rows", 1)
            view_state.layout_cols = saved_state.get("layout_cols", 1)
            view_state.active_subplot = saved_state.get("active_subplot", 0)
            
            # Restore subplot configs
            view_state.subplots = []
            for sp_data in saved_state.get("subplots", []):
                view_state.subplots.append(SubplotConfig(
                    index=sp_data.get("index", len(view_state.subplots)),
                    mode=sp_data.get("mode", "time"),
                    assigned_signals=sp_data.get("assigned_signals", []),
                ))
        
        print(f"[TABS] Closed tab: {tab_id}, switched to: {new_active}", flush=True)
        
        return (
            tabs,
            new_active,
            tab_view_states,
            (refresh or 0) + 1,
            view_state.layout_rows,
            view_state.layout_cols,
            view_state.active_subplot,
        )
    else:
        print(f"[TABS] Closed tab: {tab_id}", flush=True)
        return tabs, active_tab, tab_view_states, refresh, dash.no_update, dash.no_update, dash.no_update


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
    Output("select-compare-runs", "options"),
    Output("select-baseline-run", "options"),
    Input("store-refresh", "data"),
    Input("collapse-compare", "is_open"),
)
def update_compare_run_options(refresh, is_open):
    """Populate run dropdowns for compare (P3 - multi-CSV)"""
    if not is_open or not runs:
        return [], []
    
    options = [
        {"label": run.csv_display_name, "value": i}
        for i, run in enumerate(runs)
    ]
    return options, options


@app.callback(
    Output("select-baseline-run", "disabled"),
    Input("select-baseline-method", "value"),
)
def toggle_baseline_dropdown(method):
    """Enable/disable baseline run dropdown based on method"""
    return method != "specific"


@app.callback(
    Output("select-compare-signal", "options"),
    Output("compare-common-signals", "children"),
    Input("select-compare-runs", "value"),
)
def update_compare_signal_options(selected_runs):
    """
    Populate signal dropdown with common signals across all selected runs (P3).
    
    Shows:
    - Common signals: appear in ALL selected runs
    - Info about how many signals are common
    """
    if not selected_runs or len(selected_runs) < 2:
        return [], "Select 2+ runs to see common signals"
    
    # Find common signals across all selected runs
    common_signals = None
    for run_idx in selected_runs:
        run_idx = int(run_idx)
        if run_idx < len(runs):
            run_signals = set(runs[run_idx].signals.keys())
            if common_signals is None:
                common_signals = run_signals
            else:
                common_signals = common_signals & run_signals
    
    if not common_signals:
        return [], f"No common signals across {len(selected_runs)} runs"
    
    # Build options for common signals
    options = [{"label": s, "value": s} for s in sorted(common_signals)]
    
    # Count unique signals
    all_signals = set()
    for run_idx in selected_runs:
        run_idx = int(run_idx)
        if run_idx < len(runs):
            all_signals.update(runs[run_idx].signals.keys())
    
    info = f"✓ {len(common_signals)} common signals (of {len(all_signals)} total)"
    
    return options, info


@app.callback(
    Output("compare-results", "children"),
    Output("signal-tree", "children", allow_duplicate=True),
    Output("store-refresh", "data", allow_duplicate=True),
    Input("btn-compare", "n_clicks"),
    State("select-compare-runs", "value"),
    State("select-baseline-method", "value"),
    State("select-baseline-run", "value"),
    State("select-compare-signal", "value"),
    State("select-compare-alignment", "value"),
    State("store-refresh", "data"),
    State("store-collapsed-runs", "data"),
    prevent_initial_call=True,
)
def run_comparison(n_clicks, selected_runs, baseline_method, baseline_run_idx, signal_name, alignment, refresh, collapsed_runs):
    """
    Execute multi-CSV comparison (P3 - Advanced Compare).
    
    Supports:
    - 2+ CSVs comparison
    - Mean or specific baseline
    - RMS difference and correlation metrics
    - Creates delta derived signals
    """
    import numpy as np
    
    if not selected_runs or len(selected_runs) < 2:
        return html.Span("⚠️ Select 2+ runs to compare", className="text-warning"), dash.no_update, dash.no_update
    
    if not signal_name:
        return html.Span("⚠️ Select a signal to compare", className="text-warning"), dash.no_update, dash.no_update
    
    selected_runs = [int(r) for r in selected_runs]
    
    try:
        # Collect signal data from all selected runs
        signal_data = []  # List of (time, data, run_name)
        
        for run_idx in selected_runs:
            if run_idx >= len(runs):
                continue
            run = runs[run_idx]
            if signal_name not in run.signals:
                continue
            time_arr, data_arr = run.get_signal_data(signal_name)
            if len(time_arr) > 0:
                signal_data.append((time_arr, data_arr, run.csv_display_name, run_idx))
        
        if len(signal_data) < 2:
            return html.Span("⚠️ Signal not found in enough runs", className="text-warning"), dash.no_update, dash.no_update
        
        # Compute baseline
        if baseline_method == "specific" and baseline_run_idx is not None:
            baseline_run_idx = int(baseline_run_idx)
            baseline_entry = next((s for s in signal_data if s[3] == baseline_run_idx), signal_data[0])
            baseline_time = baseline_entry[0]
            baseline_data = baseline_entry[1]
            baseline_name = baseline_entry[2]
        else:
            # Mean baseline - use first run's time base, average all
            baseline_time = signal_data[0][0]
            aligned_data = []
            for t, d, name, idx in signal_data:
                aligned = np.interp(baseline_time, t, d)
                aligned_data.append(aligned)
            baseline_data = np.mean(aligned_data, axis=0)
            baseline_name = "Mean"
        
        # Compute metrics for each run vs baseline
        results = []
        created_deltas = []
        
        for t, d, name, run_idx in signal_data:
            # Align to baseline time
            if alignment == "baseline":
                time_common = baseline_time
                data_aligned = np.interp(baseline_time, t, d)
            elif alignment == "intersection":
                t_start = max(baseline_time[0], t[0])
                t_end = min(baseline_time[-1], t[-1])
                mask = (baseline_time >= t_start) & (baseline_time <= t_end)
                time_common = baseline_time[mask]
                data_aligned = np.interp(time_common, t, d)
                baseline_aligned = baseline_data[mask] if baseline_method != "specific" else np.interp(time_common, baseline_time, baseline_data)
            else:  # union
                time_common = np.sort(np.unique(np.concatenate([baseline_time, t])))
                data_aligned = np.interp(time_common, t, d)
            
            # Use baseline_data aligned to time_common
            if alignment == "intersection":
                bl_aligned = baseline_aligned
            else:
                bl_aligned = np.interp(time_common, baseline_time, baseline_data)
            
            # Compute diff
            diff = data_aligned - bl_aligned
            rms_diff = float(np.sqrt(np.mean(diff**2)))
            max_diff = float(np.max(np.abs(diff)))
            
            # Correlation
            corr = float(np.corrcoef(data_aligned, bl_aligned)[0, 1]) if len(data_aligned) > 1 else 0.0
            
            # Percent difference relative to baseline std
            bl_std = np.std(bl_aligned)
            pct_diff = (rms_diff / bl_std * 100) if bl_std > 0 else 0.0
            
            results.append({
                "name": name,
                "run_idx": run_idx,
                "rms": rms_diff,
                "max": max_diff,
                "corr": corr,
                "pct": pct_diff,
            })
            
            # Create delta signal
            delta_name = f"Δ({signal_name})_{name}"
            derived_signals[delta_name] = DerivedSignal(
                name=delta_name,
                time=time_common,
                data=diff,
                operation="compare",
                source_signals=[f"{run_idx}:{signal_name}"],
            )
            created_deltas.append(delta_name)
        
        # Sort by RMS diff (most different first)
        results.sort(key=lambda x: x["rms"], reverse=True)
        
        print(f"[COMPARE] Compared {signal_name} across {len(signal_data)} runs", flush=True)
        
        # Build results display
        result_items = [
            html.Div([
                html.Strong(f"Comparison: {signal_name}", className="text-info"),
                html.Span(f" vs {baseline_name}", className="text-muted small"),
            ], className="mb-2"),
        ]
        
        for r in results:
            status = "⚠️" if r["pct"] > 10 else "✓"
            color = "text-warning" if r["pct"] > 10 else "text-success"
            result_items.append(
                html.Div([
                    html.Span(f"{status} {r['name']}: ", className="small"),
                    html.Strong(f"{r['pct']:.1f}%", className=f"small {color}"),
                    html.Span(f" (RMS={r['rms']:.4g}, r={r['corr']:.3f})", className="text-muted small"),
                ], className="mb-1")
            )
        
        result_items.append(html.Hr(className="my-2"))
        result_items.append(html.Div([
            html.Span(f"✅ Created {len(created_deltas)} delta signals", className="text-success small"),
        ]))
        
        return html.Div(result_items), build_signal_tree(runs, "", collapsed_runs or {}), (refresh or 0) + 1
        
    except Exception as e:
        print(f"[COMPARE ERROR] {e}", flush=True)
        import traceback
        traceback.print_exc()
        return html.Span(f"❌ Error: {str(e)[:50]}", className="text-danger"), dash.no_update, dash.no_update


@app.callback(
    Output("compare-results", "children", allow_duplicate=True),
    Output("signal-tree", "children", allow_duplicate=True),
    Output("store-refresh", "data", allow_duplicate=True),
    Input("btn-generate-deltas", "n_clicks"),
    State("select-compare-runs", "value"),
    State("select-baseline-method", "value"),
    State("select-baseline-run", "value"),
    State("select-compare-alignment", "value"),
    State("store-refresh", "data"),
    State("store-collapsed-runs", "data"),
    prevent_initial_call=True,
)
def generate_all_deltas(n_clicks, selected_runs, baseline_method, baseline_run_idx, alignment, refresh, collapsed_runs):
    """
    Generate delta signals for ALL common signals (P3 - Advanced Compare).
    """
    import numpy as np
    
    if not selected_runs or len(selected_runs) < 2:
        return html.Span("⚠️ Select 2+ runs first", className="text-warning"), dash.no_update, dash.no_update
    
    selected_runs = [int(r) for r in selected_runs]
    
    # Find common signals
    common_signals = None
    for run_idx in selected_runs:
        if run_idx < len(runs):
            run_signals = set(runs[run_idx].signals.keys())
            if common_signals is None:
                common_signals = run_signals
            else:
                common_signals = common_signals & run_signals
    
    if not common_signals:
        return html.Span("⚠️ No common signals found", className="text-warning"), dash.no_update, dash.no_update
    
    try:
        created_count = 0
        
        for signal_name in common_signals:
            # Collect signal data
            signal_data = []
            for run_idx in selected_runs:
                if run_idx >= len(runs):
                    continue
                run = runs[run_idx]
                if signal_name not in run.signals:
                    continue
                time_arr, data_arr = run.get_signal_data(signal_name)
                if len(time_arr) > 0:
                    signal_data.append((time_arr, data_arr, run.csv_display_name, run_idx))
            
            if len(signal_data) < 2:
                continue
            
            # Compute baseline - Feature 8: Reference CSV approach
            if baseline_method == "specific" and baseline_run_idx is not None:
                baseline_run_idx_int = int(baseline_run_idx)
                baseline_entry = next((s for s in signal_data if s[3] == baseline_run_idx_int), signal_data[0])
            else:
                # Use mean as baseline
                baseline_entry = signal_data[0]  # Use first for time base
            
            baseline_time = baseline_entry[0]
            baseline_data = baseline_entry[1]
            baseline_run = baseline_entry[3]
            baseline_name = baseline_entry[2]
            
            # Create deltas only for NON-baseline runs (Feature 8 fix)
            for t, d, name, run_idx in signal_data:
                # Skip the baseline CSV - no need for delta of baseline vs itself
                if run_idx == baseline_run:
                    continue
                
                time_common = baseline_time
                data_aligned = np.interp(baseline_time, t, d)
                diff = data_aligned - baseline_data
                
                # Improved naming: show it's delta vs baseline
                delta_name = f"Δ({signal_name})_{name}_vs_{baseline_name}"
                derived_signals[delta_name] = DerivedSignal(
                    name=delta_name,
                    time=time_common,
                    data=diff,
                    operation="compare_delta",
                    source_signals=[f"{run_idx}:{signal_name}", f"{baseline_run}:{signal_name}"],
                )
                created_count += 1
        
        print(f"[COMPARE] Generated {created_count} delta signals for {len(common_signals)} signals", flush=True)
        
        return (
            html.Span(f"✅ Created {created_count} delta signals", className="text-success"),
            build_signal_tree(runs, "", collapsed_runs or {}),
            (refresh or 0) + 1,
        )
        
    except Exception as e:
        print(f"[COMPARE ERROR] {e}", flush=True)
        return html.Span(f"❌ Error: {str(e)[:50]}", className="text-danger"), dash.no_update, dash.no_update


@app.callback(
    Output("modal-compare-all", "is_open"),
    Output("compare-all-results", "children"),
    Output("store-compare-all-data", "data"),
    Input("btn-compare-all", "n_clicks"),
    Input("btn-compare-all-close", "n_clicks"),
    State("select-compare-runs", "value"),
    State("select-baseline-method", "value"),
    State("select-baseline-run", "value"),
    State("modal-compare-all", "is_open"),
    prevent_initial_call=True,
)
def compare_all_signals_modal(compare_clicks, close_clicks, selected_runs, baseline_method, baseline_run_idx, is_open):
    """
    Compare ALL common signals and show ranked results in a modal.
    
    - Computes RMS diff for each common signal
    - Ranks by largest difference first
    - Color codes: red (>10%), yellow (5-10%), green (<5%)
    """
    import numpy as np
    
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    
    if "btn-compare-all-close" in trigger:
        return False, dash.no_update, dash.no_update
    
    if "btn-compare-all" not in trigger:
        return dash.no_update, dash.no_update, dash.no_update
    
    if not selected_runs or len(selected_runs) < 2:
        return True, html.Span("⚠️ Select 2+ runs first", className="text-warning"), {}
    
    selected_runs = [int(r) for r in selected_runs]
    
    # Find common signals
    common_signals = None
    for run_idx in selected_runs:
        if run_idx < len(runs):
            run_signals = set(runs[run_idx].signals.keys())
            if common_signals is None:
                common_signals = run_signals
            else:
                common_signals = common_signals & run_signals
    
    if not common_signals:
        return True, html.Span("⚠️ No common signals found", className="text-warning"), {}
    
    # Compute metrics for each signal
    results = []
    
    for signal_name in common_signals:
        try:
            # Collect signal data
            signal_data = []
            for run_idx in selected_runs:
                if run_idx >= len(runs):
                    continue
                run = runs[run_idx]
                if signal_name not in run.signals:
                    continue
                time_arr, data_arr = run.get_signal_data(signal_name)
                if len(time_arr) > 0:
                    signal_data.append((time_arr, data_arr, run.csv_display_name, run_idx))
            
            if len(signal_data) < 2:
                continue
            
            # Compute baseline
            baseline_time = signal_data[0][0]
            aligned_data = []
            for t, d, name, idx in signal_data:
                aligned = np.interp(baseline_time, t, d)
                aligned_data.append(aligned)
            baseline_data = np.mean(aligned_data, axis=0)
            
            # Compute max RMS diff across all runs
            max_rms = 0
            for aligned in aligned_data:
                diff = aligned - baseline_data
                rms = float(np.sqrt(np.mean(diff**2)))
                max_rms = max(max_rms, rms)
            
            # Compute percent diff
            bl_std = np.std(baseline_data)
            pct_diff = (max_rms / bl_std * 100) if bl_std > 0 else 0.0
            
            results.append({
                "signal": signal_name,
                "rms": max_rms,
                "pct": pct_diff,
            })
        except Exception as e:
            print(f"[COMPARE ALL] Error processing {signal_name}: {e}", flush=True)
    
    # Sort by RMS diff (largest first)
    results.sort(key=lambda x: x["rms"], reverse=True)
    
    # Build results table
    table_rows = []
    for r in results:
        if r["pct"] > 10:
            color = "danger"
            icon = "⚠️"
        elif r["pct"] > 5:
            color = "warning"
            icon = "⚡"
        else:
            color = "success"
            icon = "✓"
        
        table_rows.append(
            dbc.Row([
                dbc.Col(html.Span(icon, className="me-2"), width=1),
                dbc.Col(html.Span(r["signal"], className="small"), width=6),
                dbc.Col(html.Span(f"{r['pct']:.1f}%", className=f"small text-{color} fw-bold"), width=2),
                dbc.Col(html.Span(f"{r['rms']:.4g}", className="small text-muted"), width=3),
            ], className="py-1 border-bottom border-secondary")
        )
    
    # Header row
    header = dbc.Row([
        dbc.Col("", width=1),
        dbc.Col(html.Strong("Signal", className="small"), width=6),
        dbc.Col(html.Strong("Diff %", className="small"), width=2),
        dbc.Col(html.Strong("RMS", className="small"), width=3),
    ], className="py-1 bg-secondary text-white")
    
    content = html.Div([
        header, 
        html.Div(table_rows, style={"maxHeight": "300px", "overflowY": "auto"}),
        html.Hr(className="my-2"),
        dbc.Button(
            "📊 Create Subplots (1 per signal, all CSVs overlaid)",
            id="btn-create-compare-subplots",
            color="info",
            size="sm",
            className="mt-2 w-100",
        ),
    ])
    
    print(f"[COMPARE ALL] Compared {len(results)} signals", flush=True)
    
    # Store results and selected runs for subplot creation
    return True, content, {"results": results, "selected_runs": selected_runs}


@app.callback(
    Output("download-compare-csv", "data"),
    Input("btn-compare-export-csv", "n_clicks"),
    State("store-compare-all-data", "data"),
    prevent_initial_call=True,
)
def export_compare_csv(n_clicks, compare_data):
    """Export compare results as CSV"""
    if not n_clicks or not compare_data:
        return dash.no_update
    
    results = compare_data.get("results", [])
    if not results:
        return dash.no_update
    
    lines = ["Signal,Diff %,RMS"]
    for r in results:
        lines.append(f"{r['signal']},{r['pct']:.2f},{r['rms']:.6g}")
    
    content = "\n".join(lines)
    return dict(content=content, filename="compare_results.csv")


@app.callback(
    Output("store-refresh", "data", allow_duplicate=True),
    Output("select-rows", "value", allow_duplicate=True),
    Output("select-cols", "value", allow_duplicate=True),
    Output("modal-compare-all", "is_open", allow_duplicate=True),
    Output("store-tabs", "data", allow_duplicate=True),
    Output("store-active-tab", "data", allow_duplicate=True),
    Output("store-tab-view-states", "data", allow_duplicate=True),
    Input("btn-create-compare-subplots", "n_clicks"),
    State("store-compare-all-data", "data"),
    State("store-refresh", "data"),
    State("store-tabs", "data"),
    State("store-tab-view-states", "data"),
    prevent_initial_call=True,
)
def create_compare_subplots(n_clicks, compare_data, refresh, existing_tabs, existing_tab_states):
    """
    Create subplots - one per common signal, with all CSV signals overlaid.
    
    Feature 9: For >16 signals, create multiple tabs (4x4 max per tab).
    
    This creates a grid layout where each subplot shows one signal
    from all selected CSVs overlaid for visual comparison.
    """
    global view_state
    
    if not n_clicks or not compare_data:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    results = compare_data.get("results", [])
    selected_runs = compare_data.get("selected_runs", [])
    
    if not results or not selected_runs:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    num_signals = len(results)
    MAX_SUBPLOTS_PER_TAB = 16
    
    # Feature 9: Handle >16 signals with multiple tabs
    if num_signals > MAX_SUBPLOTS_PER_TAB:
        # Calculate number of tabs needed
        num_tabs = (num_signals + MAX_SUBPLOTS_PER_TAB - 1) // MAX_SUBPLOTS_PER_TAB
        
        # Initialize tabs list and states
        new_tabs = existing_tabs or []
        new_tab_states = existing_tab_states or {}
        first_new_tab_id = None
        
        for tab_idx in range(num_tabs):
            start_idx = tab_idx * MAX_SUBPLOTS_PER_TAB
            end_idx = min(start_idx + MAX_SUBPLOTS_PER_TAB, num_signals)
            tab_results = results[start_idx:end_idx]
            tab_signal_count = len(tab_results)
            
            # Determine optimal grid for this tab
            if tab_signal_count <= 4:
                tab_rows, tab_cols = 2, 2
            elif tab_signal_count <= 9:
                tab_rows, tab_cols = 3, 3
            else:
                tab_rows, tab_cols = 4, 4
            
            # Create new tab
            tab_id = f"compare_{tab_idx + 1}_{int(datetime.now().timestamp())}"
            tab_name = f"Compare {tab_idx + 1}"
            new_tabs.append({"id": tab_id, "name": tab_name})
            
            if first_new_tab_id is None:
                first_new_tab_id = tab_id
            
            # Create subplots for this tab
            tab_subplots = []
            for i, r in enumerate(tab_results):
                signal_name = r["signal"]
                sp = SubplotConfig(
                    index=i,
                    mode="time",
                    title=signal_name,
                    caption=f"Diff: {r['pct']:.1f}%",
                )
                
                # Assign same signal from all selected runs
                for run_idx in selected_runs:
                    if run_idx < len(runs) and signal_name in runs[run_idx].signals:
                        sig_key = make_signal_key(run_idx, signal_name)
                        sp.assigned_signals.append(sig_key)
                
                tab_subplots.append(sp)
            
            # Fill remaining subplots
            while len(tab_subplots) < tab_rows * tab_cols:
                tab_subplots.append(SubplotConfig(index=len(tab_subplots)))
            
            # Save tab view state
            new_tab_states[tab_id] = {
                "layout_rows": tab_rows,
                "layout_cols": tab_cols,
                "active_subplot": 0,
                "subplots": [
                    {
                        "index": sp.index,
                        "mode": sp.mode,
                        "assigned_signals": sp.assigned_signals,
                        "title": sp.title,
                        "caption": sp.caption,
                    }
                    for sp in tab_subplots
                ],
            }
        
        # Update current view state to first new tab
        first_state = new_tab_states[first_new_tab_id]
        view_state.layout_rows = first_state["layout_rows"]
        view_state.layout_cols = first_state["layout_cols"]
        view_state.active_subplot = 0
        view_state.subplots = []
        for sp_data in first_state["subplots"]:
            view_state.subplots.append(SubplotConfig(
                index=sp_data["index"],
                mode=sp_data["mode"],
                assigned_signals=sp_data["assigned_signals"],
                title=sp_data.get("title", ""),
                caption=sp_data.get("caption", ""),
            ))
        
        print(f"[COMPARE SUBPLOTS] Created {num_tabs} tabs for {num_signals} signals", flush=True)
        
        return (
            (refresh or 0) + 1,
            view_state.layout_rows,
            view_state.layout_cols,
            False,  # Close modal
            new_tabs,
            first_new_tab_id,
            new_tab_states,
        )
    
    # Original behavior for <=16 signals
    # Determine optimal grid layout (aim for roughly 2 columns)
    if num_signals <= 2:
        rows, cols = 1, num_signals
    elif num_signals <= 4:
        rows, cols = 2, 2
    elif num_signals <= 6:
        rows, cols = 3, 2
    elif num_signals <= 9:
        rows, cols = 3, 3
    elif num_signals <= 12:
        rows, cols = 4, 3
    else:
        rows, cols = 4, 4
    
    # Update view state
    view_state.layout_rows = rows
    view_state.layout_cols = cols
    view_state.active_subplot = 0
    
    # Create subplots, one per signal
    view_state.subplots = []
    for i, r in enumerate(results[:16]):  # Limit to 16
        signal_name = r["signal"]
        
        # Create subplot with all CSV signals assigned
        sp = SubplotConfig(
            index=i,
            mode="time",
            title=signal_name,
            caption=f"Diff: {r['pct']:.1f}%",
        )
        
        # Assign same signal from all selected runs
        for run_idx in selected_runs:
            if run_idx < len(runs) and signal_name in runs[run_idx].signals:
                sig_key = make_signal_key(run_idx, signal_name)
                sp.assigned_signals.append(sig_key)
        
        view_state.subplots.append(sp)
    
    # Fill remaining subplots if grid is larger than signals
    while len(view_state.subplots) < rows * cols:
        view_state.subplots.append(SubplotConfig(index=len(view_state.subplots)))
    
    print(f"[COMPARE SUBPLOTS] Created {rows}x{cols} grid for {num_signals} signals", flush=True)
    
    # Keep existing tabs unchanged for <=16 signals
    return (refresh or 0) + 1, rows, cols, False, dash.no_update, dash.no_update, dash.no_update


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
            signal_names = []
            
            for t, d, n in signals_data:
                signal_names.append(n)
                if len(t) == len(result_time) and np.allclose(t, result_time):
                    aligned_data.append(d)
                else:
                    aligned_data.append(np.interp(result_time, t, d))
            
            stacked = np.vstack(aligned_data)
            
            # Build descriptive name from signal names
            if len(signal_names) <= 3:
                names_str = ", ".join(signal_names)
            else:
                names_str = f"{signal_names[0]}, ..., {signal_names[-1]}"
            
            if operation == "norm":
                result = np.sqrt(np.sum(stacked**2, axis=0))
                op_label = f"norm({names_str})"
            elif operation == "mean":
                result = np.mean(stacked, axis=0)
                op_label = f"mean({names_str})"
            elif operation == "max":
                result = np.max(stacked, axis=0)
                op_label = f"max({names_str})"
            elif operation == "min":
                result = np.min(stacked, axis=0)
                op_label = f"min({names_str})"
            else:
                result = stacked[0]
                op_label = f"multi({names_str})"
        
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
    Input("report-scope", "value"),
    State("modal-report", "is_open"),
    State("store-tabs", "data"),
    State("store-tab-view-states", "data"),
    State("store-active-tab", "data"),
    prevent_initial_call=True,
)
def toggle_report_modal(open_clicks, cancel_clicks, scope, is_open, tabs, tab_view_states, active_tab):
    """
    Toggle report modal and populate subplot list based on scope.
    
    Feature 3: Scope-aware subplot editing:
    - scope='current': Show only subplots from current tab
    - scope='all': Show subplots from ALL tabs, grouped by tab name
    """
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    
    if "btn-report-cancel" in trigger:
        return False, dash.no_update
    
    if "btn-report" in trigger or "report-scope" in trigger:
        # Determine if we should open or just update list
        should_open = "btn-report" in trigger
        tabs = tabs or [{"id": "tab_1", "name": "Tab 1"}]
        tab_view_states = tab_view_states or {}
        scope = scope or "current"
        
        subplot_items = []
        subplot_index = 0  # Global index for IDs
        
        if scope == "current":
            # Show only current tab's subplots
            total = view_state.layout_rows * view_state.layout_cols
            
            subplot_items.append(html.Div([
                html.Strong("Current Tab Subplots", className="text-info"),
            ], className="mb-2 mt-1"))
            
            for i in range(total):
                sp_config = view_state.subplots[i] if i < len(view_state.subplots) else SubplotConfig(index=i)
                sig_count = len(sp_config.assigned_signals)
                
                subplot_items.append(_create_subplot_card(subplot_index, i+1, sp_config, sig_count))
                subplot_index += 1
        
        else:  # scope == "all"
            # Show ALL tabs' subplots, grouped by tab
            for tab in tabs:
                tab_id = tab["id"]
                tab_name = tab.get("name", tab_id)
                
                # Get view state for this tab
                if tab_id == active_tab:
                    # Current tab uses global view_state
                    tab_rows = view_state.layout_rows
                    tab_cols = view_state.layout_cols
                    tab_subplots = view_state.subplots
                elif tab_id in tab_view_states:
                    saved_state = tab_view_states[tab_id]
                    tab_rows = saved_state.get("layout_rows", 1)
                    tab_cols = saved_state.get("layout_cols", 1)
                    # Reconstruct subplot configs from saved state
                    tab_subplots = []
                    for sp_data in saved_state.get("subplots", []):
                        tab_subplots.append(SubplotConfig(
                            index=sp_data.get("index", 0),
                            mode=sp_data.get("mode", "time"),
                            assigned_signals=sp_data.get("assigned_signals", []),
                            title=sp_data.get("title", ""),
                            caption=sp_data.get("caption", ""),
                            description=sp_data.get("description", ""),
                            include_in_report=sp_data.get("include_in_report", True),
                        ))
                else:
                    tab_rows, tab_cols = 1, 1
                    tab_subplots = [SubplotConfig(index=0)]
                
                total = tab_rows * tab_cols
                
                # Tab header
                subplot_items.append(html.Div([
                    html.Strong(f"📑 {tab_name}", className="text-info"),
                    html.Span(f" ({tab_rows}×{tab_cols})", className="text-muted small ms-2"),
                ], className="mb-2 mt-3 border-bottom border-secondary pb-1"))
                
                for i in range(total):
                    sp_config = tab_subplots[i] if i < len(tab_subplots) else SubplotConfig(index=i)
                    sig_count = len(sp_config.assigned_signals)
                    
                    subplot_items.append(_create_subplot_card(subplot_index, i+1, sp_config, sig_count, tab_name))
                    subplot_index += 1
        
        # Add note about Enter key
        subplot_items.append(html.Small(
            "💡 Press Shift+Enter for new lines in text areas",
            className="text-muted d-block mt-2"
        ))
        
        if should_open:
            return True, subplot_items
        else:
            return dash.no_update, subplot_items
    
    return is_open, dash.no_update


def _create_subplot_card(global_idx: int, local_num: int, sp_config: SubplotConfig, sig_count: int, tab_name: str = None):
    """Create a subplot card for the report builder"""
    label = f"Subplot {local_num}"
    if tab_name:
        label = f"{tab_name} - Subplot {local_num}"
    
    return dbc.Card([
        dbc.CardBody([
            dbc.Checklist(
                id={"type": "report-include-subplot", "index": global_idx},
                options=[{"label": f"{label} ({sig_count} signals)", "value": True}],
                value=[True] if sp_config.include_in_report else [],
                inline=True,
                className="mb-1 fw-bold",
            ),
            # Title
            dbc.Textarea(
                id={"type": "report-subplot-title", "index": global_idx},
                value=sp_config.title,
                placeholder="Title...",
                rows=1,
                className="mb-1",
                style={"fontSize": "12px", "resize": "vertical"},
            ),
            # Caption - multi-line
            dbc.Textarea(
                id={"type": "report-subplot-caption", "index": global_idx},
                value=sp_config.caption,
                placeholder="Caption (short description)...",
                rows=2,
                className="mb-1",
                style={"fontSize": "11px", "resize": "vertical"},
            ),
            # Description - multi-line
            dbc.Textarea(
                id={"type": "report-subplot-description", "index": global_idx},
                value=sp_config.description,
                placeholder="Description (detailed, multi-line)...",
                rows=3,
                className="mb-1",
                style={"fontSize": "11px", "resize": "vertical"},
            ),
        ], className="p-2"),
    ], className="mb-2")


@app.callback(
    Output("download-report", "data"),
    Input("btn-report-export", "n_clicks"),
    State("report-title", "value"),
    State("report-intro", "value"),
    State("report-conclusion", "value"),
    State("report-rtl", "value"),
    State("report-scope", "value"),
    State("report-format", "value"),
    State({"type": "report-include-subplot", "index": ALL}, "value"),
    State({"type": "report-subplot-title", "index": ALL}, "value"),
    State({"type": "report-subplot-caption", "index": ALL}, "value"),
    State({"type": "report-subplot-description", "index": ALL}, "value"),
    State("store-tab-view-states", "data"),
    State("store-active-tab", "data"),
    prevent_initial_call=True,
)
def export_report(n_clicks, title, intro, conclusion, rtl, scope, format_type, include_list, titles, captions, descriptions, tab_view_states, active_tab):
    """
    Export report to HTML, DOCX or CSV (P2 - current tab vs all tabs).
    
    - scope='current': Export only the current tab
    - scope='all': Export all tabs with sections
    """
    from datetime import datetime
    
    if not n_clicks:
        return dash.no_update
    
    # Update subplot metadata including description
    for i, (include, sp_title, sp_caption, sp_desc) in enumerate(zip(include_list, titles, captions, descriptions)):
        if i < len(view_state.subplots):
            view_state.subplots[i].include_in_report = bool(include and len(include) > 0)
            view_state.subplots[i].title = sp_title or ""
            view_state.subplots[i].caption = sp_caption or ""
            view_state.subplots[i].description = sp_desc or ""
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if format_type == "csv":
        # Export data as CSV
        content = _build_csv_export()
        return dict(content=content, filename=f"signal_data_{timestamp}.csv")
    
    elif format_type == "docx":
        # Export DOCX - Feature 4: Support all tabs, per-tab layout, preserve axis limits
        from report.builder import Report, export_docx_multi_tab, DOCX_AVAILABLE
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
        
        # Collect figures and sections based on scope
        figures = []
        tab_view_states = tab_view_states or {}
        
        if scope == "all":
            # Export all tabs - Fix 5: sort tabs in order (tab1, tab2, etc.)
            from report.builder import ReportSection
            
            # Collect all tabs in order: put current tab in its position, not first
            all_tabs = {}
            
            # Add current tab's state to the collection under its ID
            all_tabs[active_tab] = {
                "layout_rows": view_state.layout_rows,
                "layout_cols": view_state.layout_cols,
                "subplots": view_state.subplots,
                "name": "Current Tab",
                "is_current": True,
            }
            
            # Add other saved tabs
            for tab_id, saved_state in tab_view_states.items():
                if tab_id == active_tab:
                    continue  # Already added as current
                all_tabs[tab_id] = saved_state
                all_tabs[tab_id]["is_current"] = False
            
            # Sort tabs by ID to ensure tab1, tab2, etc. order
            sorted_tabs = sorted(all_tabs.items(), key=lambda x: x[0])
            
            tab_idx = 0
            for tab_id, tab_data in sorted_tabs:
                tab_idx += 1
                is_current = tab_data.get("is_current", False)
                
                if is_current:
                    # Use current view_state directly
                    tab_fig, _ = create_figure(runs, derived_signals, view_state, signal_settings, for_export=True)
                    tab_name = tab_data.get("name", f"Tab {tab_idx}")
                    
                    # Add subplot sections
                    for i, sp in enumerate(view_state.subplots):
                        if not sp.include_in_report:
                            continue
                        section = ReportSection(
                            title=sp.title or f"Subplot {i + 1}",
                            content=sp.caption or "",
                            signals=sp.assigned_signals.copy(),
                        )
                        report.subplot_sections.append(section)
                else:
                    # Reconstruct view state for this tab
                    tab_vs = ViewState(
                        layout_rows=tab_data.get("layout_rows", 1),
                        layout_cols=tab_data.get("layout_cols", 1),
                        active_subplot=0,
                        theme=view_state.theme,
                    )
                    tab_vs.subplots = []
                    for sp_data in tab_data.get("subplots", []):
                        tab_vs.subplots.append(SubplotConfig(
                            index=sp_data.get("index", 0),
                            mode=sp_data.get("mode", "time"),
                            assigned_signals=sp_data.get("assigned_signals", []),
                            xlim=sp_data.get("xlim"),
                            ylim=sp_data.get("ylim"),
                            title=sp_data.get("title", ""),
                            caption=sp_data.get("caption", ""),
                            description=sp_data.get("description", ""),
                        ))
                    
                    tab_fig, _ = create_figure(runs, derived_signals, tab_vs, signal_settings, for_export=True)
                    tab_name = tab_data.get("name", f"Tab {tab_idx}")
                
                figures.append((tab_name, tab_fig))
        else:
            # Current tab only
            fig, _ = create_figure(runs, derived_signals, view_state, signal_settings, for_export=True)
            figures.append(("", fig))
            
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
        
        # Export to temp file
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = tmp.name
        
        success = export_docx_multi_tab(report, tmp_path, figures=figures, rtl=bool(rtl))
        
        if success:
            with open(tmp_path, 'rb') as f:
                content = base64.b64encode(f.read()).decode('utf-8')
            import os
            os.unlink(tmp_path)
            return dict(content=content, filename=f"report_{timestamp}.docx", base64=True)
        else:
            return dash.no_update
    
    else:  # HTML
        # Build HTML report (P2: scope support, P0-14: RTL support for Hebrew)
        html_content = _build_html_report(title, intro, conclusion, rtl, scope, tab_view_states, active_tab)
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


def _build_html_report(title: str, intro: str, conclusion: str, rtl: bool, 
                       scope: str = "current", tab_view_states: dict = None, 
                       active_tab: str = None) -> str:
    """
    Build offline HTML report with embedded plots.
    
    P2: Supports 'current' tab only or 'all' tabs.
    P0-14: RTL support for Hebrew.
    """
    import plotly.io as pio
    
    direction = "rtl" if rtl else "ltr"
    align = "right" if rtl else "left"
    
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
        h3 {{ color: #666; margin-top: 20px; border-left: 4px solid #2196F3; padding-left: 10px; }}
        .section {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .tab-section {{ border-left: 4px solid #4CAF50; margin-top: 30px; }}
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
        intro_html = intro.replace('\n', '<br>')
        html += f"""
    <div class="section">
        <h2>Introduction</h2>
        <p dir="{direction}">{intro_html}</p>
    </div>
"""
    
    def add_tab_section(tab_name: str, subplots_list: list, rows: int = None, cols: int = None) -> str:
        """Helper to generate a tab section's HTML with per-tab layout"""
        section_html = ""
        
        # Create a temporary view state for this tab with its own layout
        temp_view = ViewState()
        temp_view.layout_rows = rows if rows else view_state.layout_rows
        temp_view.layout_cols = cols if cols else view_state.layout_cols
        temp_view.subplots = subplots_list
        temp_view.theme = view_state.theme
        
        # Create figure for this tab (with for_export=True for clean output)
        fig, _ = create_figure(runs, derived_signals, temp_view, signal_settings, for_export=True)
        plot_html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
        
        section_html += f"""
        <div class="plot-container">
            {plot_html}
        </div>
"""
        
        # Add per-subplot info
        for i, sp in enumerate(subplots_list):
            if not getattr(sp, 'include_in_report', True):
                continue
            
            sp_title = getattr(sp, 'title', '') or f"Subplot {i+1}"
            caption = getattr(sp, 'caption', '')
            description = getattr(sp, 'description', '')
            assigned = getattr(sp, 'assigned_signals', [])
            mode = getattr(sp, 'mode', 'time')
            
            section_html += f"""
        <div class="subplot-info">
            <strong>{sp_title}</strong>
"""
            if caption:
                caption_html = caption.replace('\n', '<br>')
                section_html += f"<p><em>{caption_html}</em></p>"
            
            if description:
                desc_html = description.replace('\n', '<br>')
                section_html += f"<div style='margin-top: 10px;'>{desc_html}</div>"
            
            section_html += f"""
            <small>Signals: {len(assigned)}, Mode: {mode.upper()}</small>
        </div>
"""
        return section_html
    
    # Export based on scope
    if scope == "all" and tab_view_states:
        # Export all tabs with their own layouts (Fix 4)
        # First sort tabs to ensure tab1, tab2, etc. order
        sorted_tabs = sorted(tab_view_states.items(), key=lambda x: x[0])
        
        tab_idx = 0
        for tab_id, tab_data in sorted_tabs:
            tab_idx += 1
            # Get per-tab layout dimensions
            tab_rows = tab_data.get("layout_rows", 1)
            tab_cols = tab_data.get("layout_cols", 1)
            
            subplots = []
            for sp_data in tab_data.get("subplots", []):
                sp = SubplotConfig(
                    index=sp_data.get("index", 0),
                    mode=sp_data.get("mode", "time"),
                    assigned_signals=sp_data.get("assigned_signals", []),
                    xlim=sp_data.get("xlim"),
                    ylim=sp_data.get("ylim"),
                    title=sp_data.get("title", ""),
                    caption=sp_data.get("caption", ""),
                    description=sp_data.get("description", ""),
                    include_in_report=sp_data.get("include_in_report", True),
                )
                subplots.append(sp)
            
            tab_name = tab_data.get("name", f"Tab {tab_idx}")
            if subplots:
                html += f"""
    <div class="section tab-section">
        <h3>{tab_name}</h3>
"""
                html += add_tab_section(tab_name, subplots, tab_rows, tab_cols)
                html += "    </div>\n"
        
        # Also add current tab if not in tab_view_states
        if active_tab and active_tab not in tab_view_states:
            html += f"""
    <div class="section tab-section">
        <h3>Current Tab</h3>
"""
            html += add_tab_section("Current", view_state.subplots, view_state.layout_rows, view_state.layout_cols)
            html += "    </div>\n"
    else:
        # Current tab only (default) - without active highlight for clean export
        fig, _ = create_figure(runs, derived_signals, view_state, signal_settings, for_export=True)
        plot_html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
        
        html += f"""
    <div class="section">
        <h2>Plots</h2>
        <div class="plot-container">
            {plot_html}
        </div>
"""
        
        for i, sp in enumerate(view_state.subplots):
            if not sp.include_in_report:
                continue
            
            sp_title = sp.title or f"Subplot {i+1}"
            html += f"""
        <div class="subplot-info">
            <strong>{sp_title}</strong>
"""
            if sp.caption:
                caption_html = sp.caption.replace('\n', '<br>')
                html += f"<p><em>{caption_html}</em></p>"
            
            if sp.description:
                desc_html = sp.description.replace('\n', '<br>')
                html += f"<div style='margin-top: 10px;'>{desc_html}</div>"
            
            html += f"""
            <small>Signals: {len(sp.assigned_signals)}, Mode: {sp.mode.upper()}</small>
        </div>
"""
        html += "    </div>\n"
    
    if conclusion:
        conclusion_html = conclusion.replace('\n', '<br>')
        html += f"""
    <div class="section">
        <h2>Conclusion</h2>
        <p dir="{direction}">{conclusion_html}</p>
    </div>
"""
    
    html += """
</body>
</html>
"""
    
    return html


# =============================================================================
# CALLBACKS: Signal Properties Modal
# =============================================================================

@app.callback(
    Output("modal-signal-props", "is_open"),
    Output("signal-props-original-name", "children"),
    Output("signal-props-display-name", "value"),
    Output("signal-props-line-width", "value"),
    Output("signal-props-color", "value"),
    Output("signal-props-scale", "value"),
    Output("signal-props-offset", "value"),
    Output("signal-props-time-offset", "value"),
    Output("signal-props-type", "value"),
    Output("signal-props-current-key", "data"),
    Input({"type": "btn-edit-signal", "key": ALL}, "n_clicks"),
    Input({"type": "btn-signal-props", "key": ALL}, "n_clicks"),
    Input("btn-signal-props-cancel", "n_clicks"),
    Input("btn-signal-props-apply", "n_clicks"),
    State("signal-props-current-key", "data"),
    State("modal-signal-props", "is_open"),
    prevent_initial_call=True,
)
def toggle_signal_props_modal(edit_clicks, props_clicks, cancel_click, apply_click, current_key, is_open):
    """Open/close signal properties modal (from Signals panel or Assigned panel)"""
    global signal_settings
    
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    trigger = ctx.triggered[0]["prop_id"]
    trigger_value = ctx.triggered[0]["value"]
    
    # Cancel or Apply clicked - close modal
    if "btn-signal-props-cancel" in trigger or "btn-signal-props-apply" in trigger:
        return False, "", "", 1.5, "#2E86AB", 1.0, 0.0, 0.0, "normal", None
    
    # Edit button clicked (from Assigned panel or Signals panel) - open modal
    if "btn-edit-signal" in trigger or "btn-signal-props" in trigger:
        # Check if any button was actually clicked
        all_clicks = (edit_clicks or []) + (props_clicks or [])
        if not trigger_value or trigger_value == 0:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        
        try:
            trigger_dict = json.loads(trigger.rsplit(".", 1)[0])
            sig_key = trigger_dict["key"]
        except:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        
        # Get current settings
        settings = signal_settings.get(sig_key, {})
        
        # Parse signal info
        run_idx, sig_name = parse_signal_key(sig_key)
        
        print(f"[PROPS] Opening properties for: {sig_key}", flush=True)
        
        return (
            True,  # Open modal
            sig_name,  # Original name
            settings.get("display_name", ""),
            settings.get("line_width", 1.5),
            settings.get("color", "#2E86AB"),
            settings.get("scale", 1.0),
            settings.get("offset", 0.0),
            settings.get("time_offset", 0.0),
            "state" if settings.get("is_state", False) else "normal",
            sig_key,
        )
    
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update


@app.callback(
    Output("store-refresh", "data", allow_duplicate=True),
    Output("assigned-list", "children", allow_duplicate=True),
    Input("btn-signal-props-apply", "n_clicks"),
    State("signal-props-current-key", "data"),
    State("signal-props-display-name", "value"),
    State("signal-props-line-width", "value"),
    State("signal-props-color", "value"),
    State("signal-props-scale", "value"),
    State("signal-props-offset", "value"),
    State("signal-props-time-offset", "value"),
    State("signal-props-type", "value"),
    State("select-subplot", "value"),
    State("store-refresh", "data"),
    prevent_initial_call=True,
)
def apply_signal_props(n_clicks, sig_key, display_name, line_width, color, scale, offset, time_offset, sig_type, active_sp, refresh):
    """Apply signal property changes"""
    global signal_settings
    
    if not n_clicks or not sig_key:
        return dash.no_update, dash.no_update
    
    # Store settings
    signal_settings[sig_key] = {
        "display_name": display_name if display_name else None,
        "line_width": float(line_width or 1.5),
        "color": color or None,
        "scale": float(scale or 1.0),
        "offset": float(offset or 0.0),
        "time_offset": float(time_offset or 0.0),
        "is_state": sig_type == "state",
    }
    
    print(f"[SIGNAL PROPS] Updated {sig_key}: {signal_settings[sig_key]}", flush=True)
    
    # Rebuild assigned list
    sp_idx = int(active_sp or 0)
    sp_config = view_state.subplots[sp_idx] if sp_idx < len(view_state.subplots) else SubplotConfig(index=sp_idx)
    
    return (refresh or 0) + 1, build_assigned_list(sp_config, runs)


@app.callback(
    Output("signal-props-display-name", "value", allow_duplicate=True),
    Output("signal-props-line-width", "value", allow_duplicate=True),
    Output("signal-props-color", "value", allow_duplicate=True),
    Output("signal-props-scale", "value", allow_duplicate=True),
    Output("signal-props-offset", "value", allow_duplicate=True),
    Output("signal-props-time-offset", "value", allow_duplicate=True),
    Output("signal-props-type", "value", allow_duplicate=True),
    Input("btn-signal-props-reset", "n_clicks"),
    State("signal-props-current-key", "data"),
    prevent_initial_call=True,
)
def reset_signal_props(n_clicks, sig_key):
    """Reset signal properties to defaults"""
    global signal_settings
    
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Remove settings for this signal
    if sig_key in signal_settings:
        del signal_settings[sig_key]
        print(f"[SIGNAL PROPS] Reset {sig_key} to defaults", flush=True)
    
    return "", 1.5, "#2E86AB", 1.0, 0.0, 0.0, "normal"


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
