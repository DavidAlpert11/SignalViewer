"""
Signal Viewer Pro v4.0 - Callbacks
==================================
All Dash callbacks - comprehensive feature set.
"""

from dash import Input, Output, State, callback_context, ALL, no_update, Patch
import dash
from dash import html
import dash_bootstrap_components as dbc
import json
import os
import numpy as np
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
        
        # Remove specific CSV
        elif "remove-csv" in trigger:
            try:
                trigger_id = json.loads(trigger.split(".")[0])
                csv_id = trigger_id.get("id")
                if csv_id and csv_id in csv_files:
                    data_manager.remove_csv(csv_id)
                    del csv_files[csv_id]
            except Exception as e:
                print(f"Error removing CSV: {e}")
        
        # Build file list UI with unique names
        file_items = []
        for csv_id, info in csv_files.items():
            # Check for duplicate names
            same_name_count = sum(1 for cid, inf in csv_files.items() 
                                 if inf["name"] == info["name"] and cid != csv_id)
            
            display_name = info["name"]
            if same_name_count > 0:
                parent = os.path.basename(os.path.dirname(info["path"]))
                if parent:
                    display_name = f"{parent}/{info['name']}"
            
            file_items.append(
                html.Div([
                    html.Span("📄", className="file-icon"),
                    html.Span(display_name, className="file-name", title=info["path"]),
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
        
        cleaned = {}
        for sp_key, sig_list in assignments.items():
            if isinstance(sig_list, list):
                cleaned[sp_key] = [
                    sig_key for sig_key in sig_list
                    if parse_signal_key(sig_key)[0] in valid_csv_ids
                ]
            else:
                cleaned[sp_key] = []
        
        return cleaned
    
    # =========================================================================
    # 3. SIGNAL TREE WITH AUTOCOMPLETE
    # =========================================================================
    
    @app.callback(
        [
            Output("signal-tree", "children"),
            Output("autocomplete-dropdown", "children"),
            Output("autocomplete-dropdown", "style"),
        ],
        [
            Input("store-csv-files", "data"),
            Input("store-assignments", "data"),
            Input("store-selected-subplot", "data"),
            Input("signal-search", "value"),
        ],
    )
    def update_signal_tree(csv_files, assignments, selected_subplot, search):
        """Update signal tree with autocomplete suggestions."""
        csv_files = csv_files or {}
        assignments = assignments or {}
        search = (search or "").lower().strip()
        sp_key = str(selected_subplot or 0)
        
        if not csv_files:
            return html.Div("Load CSV files to see signals", className="no-signals"), [], {"display": "none"}
        
        assigned_keys = set(assignments.get(sp_key, []))
        
        # Build autocomplete suggestions
        all_signals = []
        for csv_id, info in csv_files.items():
            for sig in info.get("signals", []):
                all_signals.append({"csv_id": csv_id, "csv_name": info["name"], "signal": sig})
        
        suggestions = []
        if search and len(search) >= 1:
            matching = [s for s in all_signals if search in s["signal"].lower()][:8]
            for s in matching:
                sig_key = f"{s['csv_id']}:{s['signal']}"
                is_assigned = sig_key in assigned_keys
                suggestions.append(
                    html.Div([
                        html.Span("✓ " if is_assigned else "", className="suggestion-check"),
                        html.Span(s["signal"], className="suggestion-signal"),
                        html.Span(f"({s['csv_name']})", className="suggestion-csv"),
                    ], className="suggestion-item" + (" assigned" if is_assigned else ""),
                       id={"type": "autocomplete-item", "key": sig_key})
                )
        
        suggestion_style = {"display": "block"} if suggestions else {"display": "none"}
        
        # Build tree
        tree_items = []
        for csv_id, info in csv_files.items():
            signals = info.get("signals", [])
            
            if search:
                signals = [s for s in signals if search in s.lower()]
            
            if not signals:
                continue
            
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
            
            # Unique CSV display name
            same_name_count = sum(1 for cid, inf in csv_files.items() 
                                 if inf["name"] == info["name"] and cid != csv_id)
            display_name = info["name"]
            if same_name_count > 0:
                parent = os.path.basename(os.path.dirname(info["path"]))
                if parent:
                    display_name = f"{parent}/{info['name']}"
            
            tree_items.append(
                html.Div([
                    html.Div([
                        html.Span("▼", className="expand-icon"),
                        html.Span("📄", className="csv-icon"),
                        html.Span(display_name, className="csv-name"),
                        html.Span(f"({len(signals)})", className="signal-count"),
                    ], className="csv-header"),
                    html.Div(signal_items, className="csv-signals expanded"),
                ], className="csv-group")
            )
        
        if not tree_items:
            return html.Div("No matching signals", className="no-signals"), suggestions, suggestion_style
        
        return tree_items, suggestions, suggestion_style
    
    # =========================================================================
    # 4. HANDLE SIGNAL CHECKBOX AND AUTOCOMPLETE CLICKS
    # =========================================================================
    
    @app.callback(
        Output("store-assignments", "data"),
        [
            Input({"type": "signal-check", "key": ALL}, "value"),
            Input({"type": "remove-signal", "key": ALL}, "n_clicks"),
            Input({"type": "autocomplete-item", "key": ALL}, "n_clicks"),
            Input("btn-remove-all", "n_clicks"),
        ],
        [
            State({"type": "signal-check", "key": ALL}, "id"),
            State("store-assignments", "data"),
            State("store-selected-subplot", "data"),
        ],
        prevent_initial_call=True,
    )
    def handle_signal_toggle(check_values, remove_clicks, autocomplete_clicks, remove_all,
                            check_ids, assignments, selected_subplot):
        """Handle signal assignment from checkboxes, remove buttons, and autocomplete."""
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        
        assignments = assignments or {}
        sp_key = str(selected_subplot or 0)
        
        if sp_key not in assignments:
            assignments[sp_key] = []
        
        if "btn-remove-all" in trigger:
            assignments[sp_key] = []
            return assignments
        
        if "remove-signal" in trigger:
            try:
                trigger_id = json.loads(trigger.split(".")[0])
                sig_key = trigger_id.get("key")
                if sig_key and sig_key in assignments[sp_key]:
                    assignments[sp_key].remove(sig_key)
            except Exception:
                pass
            return assignments
        
        # Handle autocomplete click - toggle the signal
        if "autocomplete-item" in trigger:
            try:
                trigger_id = json.loads(trigger.split(".")[0])
                sig_key = trigger_id.get("key")
                if sig_key:
                    if sig_key in assignments[sp_key]:
                        assignments[sp_key].remove(sig_key)
                    else:
                        assignments[sp_key].append(sig_key)
            except Exception:
                pass
            return assignments
        
        # Handle checkbox toggle
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
            Output("xy-x-signal", "options"),
        ],
        [
            Input("store-assignments", "data"),
            Input("store-selected-subplot", "data"),
        ],
        State("store-csv-files", "data"),
    )
    def update_assigned_list(assignments, selected_subplot, csv_files):
        """Update the assigned signals list and X-Y signal options."""
        assignments = assignments or {}
        csv_files = csv_files or {}
        sp_key = str(selected_subplot or 0)
        
        sig_keys = assignments.get(sp_key, [])
        
        if not sig_keys:
            return [html.Div("No signals assigned", className="no-assigned")], {"display": "none"}, []
        
        items = []
        xy_options = []
        
        for i, sig_key in enumerate(sig_keys):
            csv_id, sig_name = parse_signal_key(sig_key)
            csv_info = csv_files.get(csv_id, {})
            
            # Unique CSV name
            same_name_count = sum(1 for cid, inf in csv_files.items() 
                                 if inf.get("name") == csv_info.get("name") and cid != csv_id)
            csv_name = csv_info.get("name", csv_id)
            if same_name_count > 0:
                parent = os.path.basename(os.path.dirname(csv_info.get("path", "")))
                if parent:
                    csv_name = f"{parent}/{csv_name}"
            
            display_csv = csv_name[:15] if len(csv_name) > 15 else csv_name
            color = SIGNAL_COLORS[i % len(SIGNAL_COLORS)]
            
            items.append(
                html.Div([
                    html.Div(className="color-dot", style={"backgroundColor": color}),
                    html.Span(sig_name, className="assigned-name"),
                    html.Span(f"({display_csv})", className="assigned-csv"),
                    html.Button("⚙", className="settings-btn", 
                               id={"type": "signal-settings", "key": sig_key}, title="Properties"),
                    html.Button("×", className="remove-btn", 
                               id={"type": "remove-signal", "key": sig_key}),
                ], className="assigned-item")
            )
            
            xy_options.append({"label": f"{sig_name} ({display_csv})", "value": sig_key})
        
        return items, {"display": "block"}, xy_options
    
    # =========================================================================
    # 6. MAIN PLOT UPDATE (with X-Y mode support)
    # =========================================================================
    
    @app.callback(
        Output("main-plot", "figure"),
        [
            Input("store-assignments", "data"),
            Input("store-layout", "data"),
            Input("store-settings", "data"),
            Input("store-cursor", "data"),
            Input("store-selected-subplot", "data"),
            Input("store-signal-props", "data"),
            Input("store-subplot-modes", "data"),
            Input("xy-x-signal", "value"),
            Input("xy-mode-switch", "value"),
        ],
    )
    def update_plot(assignments, layout_config, settings, cursor, selected_subplot,
                   signal_props, subplot_modes, xy_x_signal, xy_mode):
        """Update the main plot when data changes."""
        assignments = assignments or {"0": []}
        layout_config = layout_config or {"rows": 1, "cols": 1}
        settings = settings or {"theme": "dark"}
        signal_props = signal_props or {}
        
        has_signals = any(signals for signals in assignments.values() if signals)
        
        if not has_signals:
            return plot_builder.build_empty_figure(settings.get("theme", "dark"))
        
        sp_key = str(selected_subplot or 0)
        
        # Check if X-Y mode is enabled for current subplot
        if xy_mode and xy_x_signal:
            y_signals = [s for s in assignments.get(sp_key, []) if s != xy_x_signal]
            if y_signals:
                return plot_builder.build_xy_figure(
                    x_signal_key=xy_x_signal,
                    y_signal_keys=y_signals,
                    settings=settings,
                    signal_props=signal_props,
                )
        
        cursor_x = cursor.get("x") if cursor and cursor.get("visible") else None
        
        return plot_builder.build_figure(
            assignments=assignments,
            layout_config=layout_config,
            settings=settings,
            cursor_x=cursor_x,
            selected_subplot=selected_subplot or 0,
            signal_props=signal_props,
        )
    
    # =========================================================================
    # 7. X-Y MODE TOGGLE
    # =========================================================================
    
    @app.callback(
        Output("xy-x-signal", "style"),
        Input("xy-mode-switch", "value"),
    )
    def toggle_xy_mode_ui(xy_mode):
        """Show/hide X-axis signal selector."""
        return {"display": "block"} if xy_mode else {"display": "none"}
    
    # =========================================================================
    # 8. LAYOUT CONTROLS
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
    # 9. THEME TOGGLE
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
    # 10. CURSOR CONTROL (with actual time values)
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
            State("cursor-slider", "min"),
            State("cursor-slider", "max"),
        ],
        prevent_initial_call=True,
    )
    def update_cursor(slider_value, cursor_visible, click_data, 
                     cursor_state, csv_files, assignments, selected_subplot, t_min, t_max):
        """Update cursor position and display values."""
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        
        cursor_state = cursor_state or {"x": None, "visible": True}
        
        if "cursor-toggle" in trigger:
            cursor_state["visible"] = cursor_visible
        
        elif "cursor-slider" in trigger:
            cursor_state["x"] = slider_value  # Slider now uses actual time values
        
        elif "main-plot" in trigger and click_data:
            try:
                x = click_data["points"][0]["x"]
                cursor_state["x"] = x
            except (KeyError, IndexError, TypeError):
                pass
        
        cursor_x = cursor_state.get("x")
        cursor_text = f"{cursor_x:.4f}" if cursor_x is not None else "--"
        
        # Get signal values at cursor
        signal_values = []
        if cursor_x is not None and cursor_state.get("visible"):
            values = plot_builder.get_cursor_values(
                cursor_x, 
                assignments or {}, 
                selected_subplot or 0
            )
            for v in values[:6]:
                signal_values.append(
                    html.Div([
                        html.Span(f"{v['signal'][:12]}: ", className="sig-name"),
                        html.Span(f"{v['value']:.3f}", className="sig-value"),
                    ], className="cursor-sig-item")
                )
        
        return cursor_state, cursor_text, signal_values
    
    @app.callback(
        [
            Output("cursor-slider", "min"),
            Output("cursor-slider", "max"),
            Output("cursor-slider", "value"),
            Output("cursor-slider", "step"),
            Output("cursor-min", "children"),
            Output("cursor-max", "children"),
        ],
        Input("store-csv-files", "data"),
        State("store-cursor", "data"),
    )
    def update_cursor_range(csv_files, cursor_state):
        """Update cursor slider range to use actual time values."""
        if not csv_files:
            return 0, 100, 50, 0.01, "0", "100"
        
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
        
        # Calculate step based on range
        range_val = t_max - t_min
        step = range_val / 10000  # High resolution
        
        current_x = cursor_state.get("x") if cursor_state else None
        if current_x is not None and t_min <= current_x <= t_max:
            value = current_x
        else:
            value = (t_min + t_max) / 2
        
        return t_min, t_max, value, step, f"{t_min:.2f}", f"{t_max:.2f}"
    
    # =========================================================================
    # 11. CURSOR ANIMATION
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
        [
            State("cursor-slider", "value"),
            State("cursor-slider", "min"),
            State("cursor-slider", "max"),
        ],
        prevent_initial_call=True,
    )
    def animate_cursor(n_intervals, current_value, t_min, t_max):
        """Animate cursor position with actual time values."""
        if current_value is None:
            return t_min
        
        step = (t_max - t_min) / 200  # Animation step
        new_value = current_value + step
        
        if new_value > t_max:
            new_value = t_min
        
        return new_value
    
    # =========================================================================
    # 12. SIGNAL PROPERTIES MODAL
    # =========================================================================
    
    @app.callback(
        [
            Output("modal-signal-props", "is_open"),
            Output("props-signal-name", "value"),
            Output("props-signal-key", "data"),
            Output("props-display-name", "value"),
            Output("props-color", "value"),
            Output("props-line-width", "value"),
            Output("props-scale", "value"),
            Output("props-offset", "value"),
        ],
        [
            Input({"type": "signal-settings", "key": ALL}, "n_clicks"),
            Input("props-cancel", "n_clicks"),
            Input("props-apply", "n_clicks"),
        ],
        [
            State({"type": "signal-settings", "key": ALL}, "id"),
            State("store-signal-props", "data"),
        ],
        prevent_initial_call=True,
    )
    def handle_signal_props_modal(settings_clicks, cancel_click, apply_click,
                                  settings_ids, signal_props):
        """Open/close signal properties modal."""
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        
        signal_props = signal_props or {}
        
        if "props-cancel" in trigger or "props-apply" in trigger:
            return False, "", "", "", "#00ffff", 1.5, 1.0, 0
        
        if "signal-settings" in trigger:
            try:
                trigger_id = json.loads(trigger.split(".")[0])
                sig_key = trigger_id.get("key")
                _, sig_name = parse_signal_key(sig_key)
                
                props = signal_props.get(sig_key, {})
                
                return (
                    True,
                    sig_name,
                    sig_key,
                    props.get("display_name", ""),
                    props.get("color", "#00ffff"),
                    props.get("width", 1.5),
                    props.get("scale", 1.0),
                    props.get("offset", 0),
                )
            except Exception:
                pass
        
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update
    
    @app.callback(
        Output("store-signal-props", "data"),
        Input("props-apply", "n_clicks"),
        [
            State("props-signal-key", "data"),
            State("props-display-name", "value"),
            State("props-color", "value"),
            State("props-line-width", "value"),
            State("props-scale", "value"),
            State("props-offset", "value"),
            State("store-signal-props", "data"),
        ],
        prevent_initial_call=True,
    )
    def apply_signal_props(n_clicks, sig_key, display_name, color, width, scale, offset, signal_props):
        """Apply signal properties."""
        if not n_clicks or not sig_key:
            return no_update
        
        signal_props = signal_props or {}
        signal_props[sig_key] = {
            "display_name": display_name or "",
            "color": color or "#00ffff",
            "width": float(width) if width else 1.5,
            "scale": float(scale) if scale else 1.0,
            "offset": float(offset) if offset else 0,
        }
        
        return signal_props
    
    # =========================================================================
    # 13. DERIVED SIGNALS MODAL
    # =========================================================================
    
    @app.callback(
        Output("modal-derived-signal", "is_open"),
        [
            Input("btn-derived", "n_clicks"),
            Input("derived-cancel", "n_clicks"),
            Input("derived-create", "n_clicks"),
        ],
        prevent_initial_call=True,
    )
    def toggle_derived_modal(open_click, cancel_click, create_click):
        """Toggle derived signal modal."""
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        
        if "btn-derived" in trigger:
            return True
        return False
    
    @app.callback(
        [
            Output("derived-signal-a", "options"),
            Output("derived-signal-b", "options"),
        ],
        Input("store-csv-files", "data"),
    )
    def update_derived_signal_options(csv_files):
        """Update signal options for derived signal modal."""
        csv_files = csv_files or {}
        
        options = []
        for csv_id, info in csv_files.items():
            for sig in info.get("signals", []):
                sig_key = f"{csv_id}:{sig}"
                options.append({"label": f"{sig} ({info['name']})", "value": sig_key})
        
        return options, options
    
    @app.callback(
        [
            Output("derived-signal-b-container", "style"),
            Output("derived-constant-container", "style"),
        ],
        Input("derived-operation", "value"),
    )
    def update_derived_form(operation):
        """Show/hide form elements based on operation."""
        binary_ops = ["sum", "diff", "product", "ratio"]
        const_ops = ["scale", "offset"]
        
        b_style = {"display": "block"} if operation in binary_ops else {"display": "none"}
        c_style = {"display": "block"} if operation in const_ops else {"display": "none"}
        
        return b_style, c_style
    
    @app.callback(
        [
            Output("store-csv-files", "data", allow_duplicate=True),
            Output("derived-output-name", "value"),
        ],
        Input("derived-create", "n_clicks"),
        [
            State("derived-operation", "value"),
            State("derived-signal-a", "value"),
            State("derived-signal-b", "value"),
            State("derived-constant", "value"),
            State("derived-output-name", "value"),
            State("store-csv-files", "data"),
        ],
        prevent_initial_call=True,
    )
    def create_derived_signal(n_clicks, operation, sig_a, sig_b, constant, output_name, csv_files):
        """Create a new derived signal."""
        if not n_clicks or not sig_a:
            return no_update, no_update
        
        csv_files = csv_files or {}
        
        try:
            csv_id_a, sig_name_a = parse_signal_key(sig_a)
            t_a, y_a = data_manager.get_signal_data(csv_id_a, sig_name_a)
            
            constant = float(constant) if constant else 1.0
            output_name = output_name or f"derived_{operation}"
            
            if operation == "derivative":
                y_out = np.gradient(y_a, t_a)
            elif operation == "integral":
                y_out = np.cumsum(y_a) * np.mean(np.diff(t_a))
            elif operation == "scale":
                y_out = y_a * constant
            elif operation == "offset":
                y_out = y_a + constant
            elif operation == "abs":
                y_out = np.abs(y_a)
            elif operation == "neg":
                y_out = -y_a
            elif operation in ["sum", "diff", "product", "ratio"] and sig_b:
                csv_id_b, sig_name_b = parse_signal_key(sig_b)
                t_b, y_b = data_manager.get_signal_data(csv_id_b, sig_name_b)
                y_b_interp = np.interp(t_a, t_b, y_b)
                
                if operation == "sum":
                    y_out = y_a + y_b_interp
                elif operation == "diff":
                    y_out = y_a - y_b_interp
                elif operation == "product":
                    y_out = y_a * y_b_interp
                elif operation == "ratio":
                    y_out = np.divide(y_a, y_b_interp, where=y_b_interp!=0)
            else:
                return no_update, no_update
            
            # Add derived signal to data manager
            derived_id = data_manager.add_derived_signal(
                name=output_name,
                time=t_a,
                values=y_out,
                source_csv=csv_id_a,
            )
            
            # Update csv_files with new derived signal
            csv_files[derived_id] = {
                "id": derived_id,
                "name": f"[Derived] {output_name}",
                "path": "",
                "signals": [output_name],
                "row_count": len(t_a),
                "is_derived": True,
            }
            
            return csv_files, ""
            
        except Exception as e:
            print(f"Error creating derived signal: {e}")
            return no_update, no_update
    
    # =========================================================================
    # 14. EXPORT MODAL
    # =========================================================================
    
    @app.callback(
        Output("modal-export", "is_open"),
        [
            Input("btn-export", "n_clicks"),
            Input("export-close", "n_clicks"),
        ],
        prevent_initial_call=True,
    )
    def toggle_export_modal(open_click, close_click):
        """Toggle export modal."""
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        
        if "btn-export" in trigger:
            return True
        return False
    
    @app.callback(
        Output("download-export", "data"),
        [
            Input("btn-export-csv", "n_clicks"),
            Input("btn-export-html", "n_clicks"),
        ],
        [
            State("store-assignments", "data"),
            State("store-selected-subplot", "data"),
            State("store-csv-files", "data"),
            State("export-include-time", "value"),
            State("export-all-subplots", "value"),
            State("export-interpolate", "value"),
            State("export-html-title", "value"),
            State("main-plot", "figure"),
        ],
        prevent_initial_call=True,
    )
    def handle_export(csv_click, html_click, assignments, selected_subplot, csv_files,
                     include_time, all_subplots, interpolate, html_title, figure):
        """Handle export actions."""
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        
        if "btn-export-csv" in trigger:
            return export_csv_data(
                assignments, selected_subplot, csv_files,
                include_time, all_subplots, interpolate
            )
        
        elif "btn-export-html" in trigger:
            return export_html_report(figure, html_title or "Signal Viewer Report")
        
        return no_update
    
    # =========================================================================
    # 15. SESSION SAVE/LOAD
    # =========================================================================
    
    @app.callback(
        Output("download-session", "data"),
        Input("btn-save", "n_clicks"),
        [
            State("store-csv-files", "data"),
            State("store-assignments", "data"),
            State("store-layout", "data"),
            State("store-settings", "data"),
            State("store-signal-props", "data"),
        ],
        prevent_initial_call=True,
    )
    def save_session(n_clicks, csv_files, assignments, layout_config, settings, signal_props):
        """Save session to JSON file."""
        if not n_clicks:
            return no_update
        
        session_data = {
            "version": "4.0",
            "csv_files": csv_files,
            "assignments": assignments,
            "layout": layout_config,
            "settings": settings,
            "signal_props": signal_props,
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
            Output("store-signal-props", "data", allow_duplicate=True),
        ],
        Input("btn-load", "n_clicks"),
        prevent_initial_call=True,
    )
    def load_session(n_clicks):
        """Load session from JSON file."""
        if not n_clicks:
            return no_update, no_update, no_update, no_update, no_update
        
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        filepath = filedialog.askopenfilename(
            title="Load Session",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        root.destroy()
        
        if not filepath:
            return no_update, no_update, no_update, no_update, no_update
        
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
                session_data.get("signal_props", {}),
            )
            
        except Exception as e:
            print(f"Error loading session: {e}")
            return no_update, no_update, no_update, no_update, no_update


def export_csv_data(assignments, selected_subplot, csv_files, include_time, all_subplots, interpolate):
    """Export assigned signals to CSV format."""
    import io
    
    assignments = assignments or {}
    csv_files = csv_files or {}
    
    # Get signals to export
    if all_subplots:
        all_signals = []
        for sp_signals in assignments.values():
            all_signals.extend(sp_signals)
    else:
        sp_key = str(selected_subplot or 0)
        all_signals = assignments.get(sp_key, [])
    
    if not all_signals:
        return no_update
    
    # Collect data
    data_dict = {}
    common_time = None
    
    for sig_key in all_signals:
        csv_id, sig_name = parse_signal_key(sig_key)
        try:
            t, y = data_manager.get_signal_data(csv_id, sig_name)
            
            if common_time is None:
                common_time = t
            elif interpolate:
                y = np.interp(common_time, t, y)
            
            # Unique column name
            csv_info = csv_files.get(csv_id, {})
            col_name = f"{sig_name}_{csv_info.get('name', csv_id)[:10]}"
            data_dict[col_name] = y
            
        except Exception:
            pass
    
    if not data_dict:
        return no_update
    
    # Build CSV content
    buffer = io.StringIO()
    
    if include_time and common_time is not None:
        buffer.write("Time," + ",".join(data_dict.keys()) + "\n")
        for i in range(len(common_time)):
            row = [f"{common_time[i]:.6f}"]
            for col_data in data_dict.values():
                if i < len(col_data):
                    row.append(f"{col_data[i]:.6f}")
                else:
                    row.append("")
            buffer.write(",".join(row) + "\n")
    else:
        buffer.write(",".join(data_dict.keys()) + "\n")
        max_len = max(len(v) for v in data_dict.values())
        for i in range(max_len):
            row = []
            for col_data in data_dict.values():
                if i < len(col_data):
                    row.append(f"{col_data[i]:.6f}")
                else:
                    row.append("")
            buffer.write(",".join(row) + "\n")
    
    return dict(content=buffer.getvalue(), filename="exported_signals.csv")


def export_html_report(figure, title):
    """Export plot as interactive HTML."""
    import plotly.io as pio
    
    if not figure:
        return no_update
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #fff; }}
        h1 {{ text-align: center; color: #00d4ff; }}
        .plot-container {{ width: 100%; max-width: 1400px; margin: 0 auto; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="plot-container" id="plot"></div>
    <script>
        var figure = {json.dumps(figure)};
        Plotly.newPlot('plot', figure.data, figure.layout, {{responsive: true}});
    </script>
    <footer style="text-align: center; margin-top: 20px; color: #666;">
        Generated by Signal Viewer Pro v4.0
    </footer>
</body>
</html>
"""
    
    return dict(content=html_content, filename="signal_viewer_report.html")


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

