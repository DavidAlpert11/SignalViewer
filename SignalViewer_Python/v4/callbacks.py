"""
Signal Viewer Pro v4.0 - Callbacks
==================================
All Dash callbacks - properly synchronized.
"""

from dash import Input, Output, State, callback_context, ALL, no_update, Patch
import dash
from dash import html
import dash_bootstrap_components as dbc
import json
import os
import tkinter as tk
from tkinter import filedialog

from config import SIGNAL_COLORS, THEMES
from data_manager import data_manager
from plot_builder import plot_builder
from state import make_signal_key, parse_signal_key


def register_callbacks(app):
    """Register all callbacks with the Dash app."""
    
    # =========================================================================
    # 1. CSV FILE LOADING
    # =========================================================================
    
    @app.callback(
        [
            Output("store-csv-files", "data"),
            Output("csv-file-list", "children"),
            Output("btn-clear-csv", "style"),
        ],
        [
            Input("btn-add-csv", "n_clicks"),
            Input("btn-clear-csv", "n_clicks"),
            Input({"type": "remove-csv", "id": ALL}, "n_clicks"),
        ],
        [
            State("store-csv-files", "data"),
            State("store-assignments", "data"),
        ],
        prevent_initial_call=True,
    )
    def handle_csv_files(add_click, clear_click, remove_clicks, csv_files, assignments):
        """Handle CSV file operations: add, remove, clear."""
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        
        csv_files = csv_files or {}
        
        # Add new CSV files
        if "btn-add-csv" in trigger:
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            filepaths = filedialog.askopenfilenames(
                title="Select CSV Files",
                filetypes=[("CSV files", "*.csv *.txt *.tsv"), ("All files", "*.*")]
            )
            root.destroy()
            
            for fp in filepaths:
                try:
                    info = data_manager.load_csv(fp)
                    csv_files[info["id"]] = info
                except Exception as e:
                    print(f"Error loading {fp}: {e}")
        
        # Clear all CSVs
        elif "btn-clear-csv" in trigger:
            data_manager.clear_all()
            csv_files = {}
        
        # Remove specific CSV - FIXED: Only remove this CSV's data
        elif "remove-csv" in trigger:
            try:
                trigger_id = json.loads(trigger.split(".")[0])
                csv_id = trigger_id.get("id")
                if csv_id and csv_id in csv_files:
                    # Remove ONLY this CSV from data manager
                    data_manager.remove_csv(csv_id)
                    del csv_files[csv_id]
            except Exception as e:
                print(f"Error removing CSV: {e}")
        
        # Build file list UI
        file_items = []
        for csv_id, info in csv_files.items():
            file_items.append(
                html.Div([
                    html.Span("📄", className="file-icon"),
                    html.Span(info["name"], className="file-name", title=info["path"]),
                    html.Span(f"({info['row_count']} rows)", className="file-rows"),
                    html.Button("×", id={"type": "remove-csv", "id": csv_id}, className="file-remove"),
                ], className="file-item")
            )
        
        if not file_items:
            file_items = [html.Div("No files loaded", className="no-files")]
        
        show_clear = {"display": "block"} if csv_files else {"display": "none"}
        
        return csv_files, file_items, show_clear
    
    # =========================================================================
    # 2. CLEAN ASSIGNMENTS WHEN CSV REMOVED
    # =========================================================================
    
    @app.callback(
        Output("store-assignments", "data", allow_duplicate=True),
        Input("store-csv-files", "data"),
        State("store-assignments", "data"),
        prevent_initial_call=True,
    )
    def clean_assignments_on_csv_change(csv_files, assignments):
        """Remove assignments for CSVs that no longer exist."""
        if not assignments:
            return {"0": []}
        
        csv_files = csv_files or {}
        valid_csv_ids = set(csv_files.keys())
        
        # Clean each subplot's assignments
        cleaned = {}
        for sp_key, sig_list in assignments.items():
            if isinstance(sig_list, list):
                # Keep only signals from CSVs that still exist
                cleaned[sp_key] = [
                    sig_key for sig_key in sig_list
                    if parse_signal_key(sig_key)[0] in valid_csv_ids
                ]
            else:
                cleaned[sp_key] = []
        
        return cleaned
    
    # =========================================================================
    # 3. SIGNAL TREE WITH CHECKBOX STATE
    # =========================================================================
    
    @app.callback(
        Output("signal-tree", "children"),
        [
            Input("store-csv-files", "data"),
            Input("store-assignments", "data"),
            Input("store-selected-subplot", "data"),
            Input("signal-search", "value"),
        ],
    )
    def update_signal_tree(csv_files, assignments, selected_subplot, search):
        """Update signal tree with proper checkbox states."""
        csv_files = csv_files or {}
        assignments = assignments or {}
        search = (search or "").lower().strip()
        sp_key = str(selected_subplot or 0)
        
        if not csv_files:
            return html.Div("Load CSV files to see signals", className="no-signals")
        
        # Get currently assigned signals for this subplot
        assigned_keys = set(assignments.get(sp_key, []))
        
        tree_items = []
        
        for csv_id, info in csv_files.items():
            signals = info.get("signals", [])
            
            # Filter by search
            if search:
                signals = [s for s in signals if search in s.lower()]
            
            if not signals:
                continue
            
            # Build signal items with proper checked state
            signal_items = []
            for sig_name in signals:
                sig_key = f"{csv_id}:{sig_name}"
                is_checked = sig_key in assigned_keys
                
                signal_items.append(
                    html.Div([
                        dbc.Checkbox(
                            id={"type": "signal-check", "key": sig_key},
                            value=is_checked,
                            className="signal-checkbox",
                        ),
                        html.Span(sig_name, className="signal-name", title=f"{info['name']} / {sig_name}"),
                    ], className="signal-item" + (" assigned" if is_checked else ""))
                )
            
            # CSV group with header
            tree_items.append(
                html.Div([
                    html.Div([
                        html.Span("▼", className="expand-icon"),
                        html.Span("📄", className="csv-icon"),
                        html.Span(info["name"], className="csv-name"),
                        html.Span(f"({len(signals)})", className="signal-count"),
                    ], className="csv-header"),
                    html.Div(signal_items, className="csv-signals expanded"),
                ], className="csv-group")
            )
        
        if not tree_items:
            return html.Div("No matching signals", className="no-signals")
        
        return tree_items
    
    # =========================================================================
    # 4. HANDLE SIGNAL CHECKBOX CLICKS
    # =========================================================================
    
    @app.callback(
        Output("store-assignments", "data"),
        [
            Input({"type": "signal-check", "key": ALL}, "value"),
            Input({"type": "remove-signal", "key": ALL}, "n_clicks"),
            Input("btn-remove-all", "n_clicks"),
        ],
        [
            State({"type": "signal-check", "key": ALL}, "id"),
            State("store-assignments", "data"),
            State("store-selected-subplot", "data"),
        ],
        prevent_initial_call=True,
    )
    def handle_signal_toggle(check_values, remove_clicks, remove_all, 
                            check_ids, assignments, selected_subplot):
        """Handle signal assignment from checkboxes and remove buttons."""
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        
        assignments = assignments or {}
        sp_key = str(selected_subplot or 0)
        
        if sp_key not in assignments:
            assignments[sp_key] = []
        
        # Remove all signals from current subplot
        if "btn-remove-all" in trigger:
            assignments[sp_key] = []
            return assignments
        
        # Remove specific signal
        if "remove-signal" in trigger:
            try:
                trigger_id = json.loads(trigger.split(".")[0])
                sig_key = trigger_id.get("key")
                if sig_key and sig_key in assignments[sp_key]:
                    assignments[sp_key].remove(sig_key)
            except Exception:
                pass
            return assignments
        
        # Handle checkbox toggle - rebuild from checkbox state
        if "signal-check" in trigger and check_ids and check_values:
            new_assignments = []
            
            for i, checkbox_id in enumerate(check_ids):
                sig_key = checkbox_id.get("key")
                is_checked = check_values[i] if i < len(check_values) else False
                
                if is_checked and sig_key:
                    new_assignments.append(sig_key)
            
            assignments[sp_key] = new_assignments
        
        return assignments
    
    # =========================================================================
    # 5. ASSIGNED LIST DISPLAY
    # =========================================================================
    
    @app.callback(
        [
            Output("assigned-list", "children"),
            Output("btn-remove-all", "style"),
        ],
        [
            Input("store-assignments", "data"),
            Input("store-selected-subplot", "data"),
        ],
        State("store-csv-files", "data"),
    )
    def update_assigned_list(assignments, selected_subplot, csv_files):
        """Update the assigned signals list display."""
        assignments = assignments or {}
        csv_files = csv_files or {}
        sp_key = str(selected_subplot or 0)
        
        sig_keys = assignments.get(sp_key, [])
        
        if not sig_keys:
            return [html.Div("No signals assigned", className="no-assigned")], {"display": "none"}
        
        items = []
        for i, sig_key in enumerate(sig_keys):
            csv_id, sig_name = parse_signal_key(sig_key)
            csv_info = csv_files.get(csv_id, {})
            csv_name = csv_info.get("name", csv_id)[:15]
            color = SIGNAL_COLORS[i % len(SIGNAL_COLORS)]
            
            items.append(
                html.Div([
                    html.Div(className="color-dot", style={"backgroundColor": color}),
                    html.Span(sig_name, className="assigned-name"),
                    html.Span(f"({csv_name})", className="assigned-csv"),
                    html.Button("×", className="remove-btn", id={"type": "remove-signal", "key": sig_key}),
                ], className="assigned-item")
            )
        
        return items, {"display": "block"}
    
    # =========================================================================
    # 6. MAIN PLOT UPDATE
    # =========================================================================
    
    @app.callback(
        Output("main-plot", "figure"),
        [
            Input("store-assignments", "data"),
            Input("store-layout", "data"),
            Input("store-settings", "data"),
            Input("store-cursor", "data"),
            Input("store-selected-subplot", "data"),
        ],
    )
    def update_plot(assignments, layout_config, settings, cursor, selected_subplot):
        """Update the main plot when data changes."""
        assignments = assignments or {"0": []}
        layout_config = layout_config or {"rows": 1, "cols": 1}
        settings = settings or {"theme": "dark"}
        
        # Check if we have any signals assigned
        has_signals = any(signals for signals in assignments.values() if signals)
        
        if not has_signals:
            return plot_builder.build_empty_figure(settings.get("theme", "dark"))
        
        cursor_x = cursor.get("x") if cursor and cursor.get("visible") else None
        
        return plot_builder.build_figure(
            assignments=assignments,
            layout_config=layout_config,
            settings=settings,
            cursor_x=cursor_x,
            selected_subplot=selected_subplot or 0,
        )
    
    # =========================================================================
    # 7. LAYOUT CONTROLS
    # =========================================================================
    
    @app.callback(
        [
            Output("store-layout", "data"),
            Output("subplot-select", "options"),
            Output("subplot-select", "value"),
        ],
        [
            Input("layout-rows", "value"),
            Input("layout-cols", "value"),
        ],
        State("store-selected-subplot", "data"),
    )
    def update_layout(rows, cols, current_subplot):
        """Update subplot grid layout."""
        rows = int(rows) if rows else 1
        cols = int(cols) if cols else 1
        
        total = rows * cols
        options = [{"label": str(i + 1), "value": str(i)} for i in range(total)]
        
        current = int(current_subplot) if current_subplot is not None else 0
        if current >= total:
            current = 0
        
        return {"rows": rows, "cols": cols}, options, str(current)
    
    @app.callback(
        [
            Output("store-selected-subplot", "data"),
            Output("assigned-subplot-label", "children"),
        ],
        Input("subplot-select", "value"),
    )
    def update_selected_subplot(value):
        """Update selected subplot."""
        subplot = int(value) if value else 0
        return subplot, f"(Subplot {subplot + 1})"
    
    # =========================================================================
    # 8. THEME TOGGLE
    # =========================================================================
    
    @app.callback(
        Output("store-settings", "data"),
        Input("theme-switch", "value"),
        State("store-settings", "data"),
    )
    def toggle_theme(is_dark, settings):
        """Toggle between dark and light theme."""
        settings = settings or {}
        settings["theme"] = "dark" if is_dark else "light"
        return settings
    
    # =========================================================================
    # 9. CURSOR CONTROL
    # =========================================================================
    
    @app.callback(
        [
            Output("store-cursor", "data"),
            Output("cursor-value", "children"),
            Output("cursor-signals", "children"),
        ],
        [
            Input("cursor-slider", "value"),
            Input("cursor-toggle", "value"),
            Input("main-plot", "clickData"),
        ],
        [
            State("store-cursor", "data"),
            State("store-csv-files", "data"),
            State("store-assignments", "data"),
            State("store-selected-subplot", "data"),
        ],
        prevent_initial_call=True,
    )
    def update_cursor(slider_value, cursor_visible, click_data, 
                     cursor_state, csv_files, assignments, selected_subplot):
        """Update cursor position and display values."""
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        
        cursor_state = cursor_state or {"x": None, "visible": True}
        
        # Get time range from first CSV
        t_min, t_max = 0, 100
        if csv_files:
            first_id = list(csv_files.keys())[0]
            t_min, t_max = data_manager.get_time_range(first_id)
        
        # Handle toggle
        if "cursor-toggle" in trigger:
            cursor_state["visible"] = cursor_visible
        
        # Handle slider
        elif "cursor-slider" in trigger:
            cursor_x = t_min + (slider_value / 100.0) * (t_max - t_min)
            cursor_state["x"] = cursor_x
        
        # Handle plot click
        elif "main-plot" in trigger and click_data:
            try:
                x = click_data["points"][0]["x"]
                cursor_state["x"] = x
            except (KeyError, IndexError, TypeError):
                pass
        
        # Format cursor value
        cursor_x = cursor_state.get("x")
        if cursor_x is not None:
            cursor_text = f"{cursor_x:.4f}"
        else:
            cursor_text = "--"
        
        # Get signal values at cursor
        signal_values = []
        if cursor_x is not None and cursor_state.get("visible"):
            values = plot_builder.get_cursor_values(
                cursor_x, 
                assignments or {}, 
                selected_subplot or 0
            )
            for v in values[:5]:
                signal_values.append(
                    html.Div([
                        html.Span(f"{v['signal'][:15]}: ", className="sig-name"),
                        html.Span(f"{v['value']:.4f}", className="sig-value"),
                    ], className="cursor-sig-item")
                )
        
        return cursor_state, cursor_text, signal_values
    
    @app.callback(
        [
            Output("cursor-slider", "min"),
            Output("cursor-slider", "max"),
            Output("cursor-slider", "value"),
        ],
        Input("store-csv-files", "data"),
        State("store-cursor", "data"),
    )
    def update_cursor_range(csv_files, cursor_state):
        """Update cursor slider range based on loaded data."""
        if not csv_files:
            return 0, 100, 50
        
        t_min, t_max = float('inf'), float('-inf')
        for csv_id in csv_files:
            try:
                min_t, max_t = data_manager.get_time_range(csv_id)
                t_min = min(t_min, min_t)
                t_max = max(t_max, max_t)
            except Exception:
                pass
        
        if t_min == float('inf'):
            t_min, t_max = 0, 100
        
        current_x = cursor_state.get("x") if cursor_state else None
        if current_x is not None and t_min <= current_x <= t_max:
            value = ((current_x - t_min) / (t_max - t_min)) * 100
        else:
            value = 50
        
        return 0, 100, value
    
    # =========================================================================
    # 10. CURSOR ANIMATION
    # =========================================================================
    
    @app.callback(
        Output("cursor-interval", "disabled"),
        [
            Input("btn-play", "n_clicks"),
            Input("btn-stop", "n_clicks"),
        ],
        prevent_initial_call=True,
    )
    def control_cursor_animation(play_click, stop_click):
        """Control cursor play/stop."""
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        
        if "btn-play" in trigger:
            return False
        elif "btn-stop" in trigger:
            return True
        
        return True
    
    @app.callback(
        Output("cursor-slider", "value", allow_duplicate=True),
        Input("cursor-interval", "n_intervals"),
        State("cursor-slider", "value"),
        prevent_initial_call=True,
    )
    def animate_cursor(n_intervals, current_value):
        """Animate cursor position."""
        if current_value is None:
            return 0
        
        new_value = current_value + 0.5
        if new_value > 100:
            new_value = 0
        
        return new_value
    
    # =========================================================================
    # 11. SESSION SAVE/LOAD
    # =========================================================================
    
    @app.callback(
        Output("download-session", "data"),
        Input("btn-save", "n_clicks"),
        [
            State("store-csv-files", "data"),
            State("store-assignments", "data"),
            State("store-layout", "data"),
            State("store-settings", "data"),
        ],
        prevent_initial_call=True,
    )
    def save_session(n_clicks, csv_files, assignments, layout_config, settings):
        """Save session to JSON file."""
        if not n_clicks:
            return no_update
        
        session_data = {
            "version": "4.0",
            "csv_files": csv_files,
            "assignments": assignments,
            "layout": layout_config,
            "settings": settings,
        }
        
        return dict(
            content=json.dumps(session_data, indent=2),
            filename="signal_viewer_session.json",
        )
    
    @app.callback(
        [
            Output("store-csv-files", "data", allow_duplicate=True),
            Output("store-assignments", "data", allow_duplicate=True),
            Output("store-layout", "data", allow_duplicate=True),
            Output("store-settings", "data", allow_duplicate=True),
        ],
        Input("btn-load", "n_clicks"),
        prevent_initial_call=True,
    )
    def load_session(n_clicks):
        """Load session from JSON file."""
        if not n_clicks:
            return no_update, no_update, no_update, no_update
        
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        filepath = filedialog.askopenfilename(
            title="Load Session",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        root.destroy()
        
        if not filepath:
            return no_update, no_update, no_update, no_update
        
        try:
            with open(filepath, 'r') as f:
                session_data = json.load(f)
            
            csv_files = session_data.get("csv_files", {})
            for csv_id, info in csv_files.items():
                fp = info.get("path")
                if fp and os.path.exists(fp):
                    try:
                        data_manager.load_csv(fp, csv_id)
                    except Exception:
                        pass
            
            return (
                csv_files,
                session_data.get("assignments", {"0": []}),
                session_data.get("layout", {"rows": 1, "cols": 1}),
                session_data.get("settings", {"theme": "dark"}),
            )
            
        except Exception as e:
            print(f"Error loading session: {e}")
            return no_update, no_update, no_update, no_update


def register_clientside_callbacks(app):
    """Register clientside callbacks for instant UI responses."""
    
    app.clientside_callback(
        """
        function(isDark) {
            document.body.classList.toggle('light-theme', !isDark);
            document.body.classList.toggle('dark-theme', isDark);
            return window.dash_clientside.no_update;
        }
        """,
        Output("root", "className"),
        Input("theme-switch", "value"),
    )
