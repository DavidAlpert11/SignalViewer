"""
Signal Viewer Pro v4.0 - Callbacks
==================================
All Dash callbacks in one place.
Target: ~15 callbacks total.
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
from layout import create_csv_group, create_assigned_signal


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
        State("store-csv-files", "data"),
        prevent_initial_call=True,
    )
    def handle_csv_files(add_click, clear_click, remove_clicks, csv_files):
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
            except Exception:
                pass
        
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
    # 2. SIGNAL TREE
    # =========================================================================
    
    @app.callback(
        Output("signal-tree", "children"),
        [
            Input("store-csv-files", "data"),
            Input("signal-search", "value"),
        ],
    )
    def update_signal_tree(csv_files, search):
        """Update the signal tree when CSVs change or search is used."""
        csv_files = csv_files or {}
        search = (search or "").lower().strip()
        
        if not csv_files:
            return html.Div("Load CSV files to see signals", className="no-signals")
        
        tree_items = []
        
        for csv_id, info in csv_files.items():
            signals = info.get("signals", [])
            
            # Filter by search
            if search:
                signals = [s for s in signals if search in s.lower()]
            
            if signals:
                tree_items.append(create_csv_group(csv_id, info["name"], signals))
        
        if not tree_items:
            return html.Div("No matching signals", className="no-signals")
        
        return tree_items
    
    # =========================================================================
    # 3. SIGNAL ASSIGNMENT
    # =========================================================================
    
    @app.callback(
        [
            Output("store-assignments", "data"),
            Output("assigned-list", "children"),
            Output("btn-remove-all", "style"),
        ],
        [
            Input({"type": "signal-check", "key": ALL}, "value"),
            Input({"type": "remove-signal", "key": ALL}, "n_clicks"),
            Input("btn-remove-all", "n_clicks"),
        ],
        [
            State({"type": "signal-check", "key": ALL}, "id"),
            State("store-assignments", "data"),
            State("store-selected-subplot", "data"),
            State("store-csv-files", "data"),
        ],
        prevent_initial_call=True,
    )
    def handle_assignments(check_values, remove_clicks, remove_all, check_ids, 
                          assignments, selected_subplot, csv_files):
        """Handle signal assignment and removal."""
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
        
        assignments = assignments or {"0": []}
        sp_key = str(selected_subplot or 0)
        csv_files = csv_files or {}
        
        if sp_key not in assignments:
            assignments[sp_key] = []
        
        current = set(assignments[sp_key])
        
        # Remove all signals
        if "btn-remove-all" in trigger:
            assignments[sp_key] = []
        
        # Remove specific signal
        elif "remove-signal" in trigger:
            try:
                trigger_id = json.loads(trigger.split(".")[0])
                sig_key = trigger_id.get("key")
                if sig_key in current:
                    current.remove(sig_key)
                assignments[sp_key] = list(current)
            except Exception:
                pass
        
        # Toggle signal from checkbox
        elif "signal-check" in trigger:
            # Build mapping of checkbox id to value
            if check_ids and check_values:
                for i, checkbox_id in enumerate(check_ids):
                    sig_key = checkbox_id.get("key")
                    is_checked = check_values[i] if i < len(check_values) else False
                    
                    if is_checked and sig_key not in current:
                        current.add(sig_key)
                    elif not is_checked and sig_key in current:
                        current.remove(sig_key)
                
                assignments[sp_key] = list(current)
        
        # Build assigned list UI
        assigned_items = []
        for i, sig_key in enumerate(assignments.get(sp_key, [])):
            csv_id, sig_name = parse_signal_key(sig_key)
            csv_info = csv_files.get(csv_id, {})
            csv_name = csv_info.get("name", csv_id)[:15]
            color = SIGNAL_COLORS[i % len(SIGNAL_COLORS)]
            
            assigned_items.append(create_assigned_signal(sig_key, sig_name, csv_name, color))
        
        if not assigned_items:
            assigned_items = [html.Div("No signals assigned", className="no-assigned")]
        
        show_remove = {"display": "block"} if assignments.get(sp_key) else {"display": "none"}
        
        return assignments, assigned_items, show_remove
    
    # =========================================================================
    # 4. MAIN PLOT UPDATE
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
        has_signals = any(signals for signals in assignments.values())
        
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
    # 5. LAYOUT CONTROLS
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
        
        # Build subplot options
        options = [{"label": str(i + 1), "value": str(i)} for i in range(total)]
        
        # Reset to subplot 0 if current is out of range
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
    # 6. THEME TOGGLE
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
    # 7. CURSOR CONTROL
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
            # Convert slider (0-100) to actual time value
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
            for v in values[:5]:  # Show max 5 signals
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
        
        # Get global time range
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
        
        # Set slider to middle or current position
        current_x = cursor_state.get("x") if cursor_state else None
        if current_x is not None and t_min <= current_x <= t_max:
            value = ((current_x - t_min) / (t_max - t_min)) * 100
        else:
            value = 50
        
        return 0, 100, value
    
    # =========================================================================
    # 8. CURSOR ANIMATION
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
            return False  # Enable interval
        elif "btn-stop" in trigger:
            return True  # Disable interval
        
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
    # 9. SESSION SAVE/LOAD
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
            
            # Reload CSV files
            csv_files = session_data.get("csv_files", {})
            for csv_id, info in csv_files.items():
                filepath = info.get("path")
                if filepath and os.path.exists(filepath):
                    try:
                        data_manager.load_csv(filepath, csv_id)
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
    
    # =========================================================================
    # 10. DOUBLE-CLICK SUBPLOT SELECTION
    # =========================================================================
    
    @app.callback(
        Output("subplot-select", "value", allow_duplicate=True),
        Input("main-plot", "clickData"),
        [
            State("store-layout", "data"),
        ],
        prevent_initial_call=True,
    )
    def select_subplot_by_click(click_data, layout_config):
        """Select subplot by clicking on it."""
        if not click_data:
            return no_update
        
        # This is a simplified version - would need curveNumber to determine subplot
        # For now, just return no_update
        return no_update


def register_clientside_callbacks(app):
    """Register clientside callbacks for instant UI responses."""
    
    # Theme class toggle
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

