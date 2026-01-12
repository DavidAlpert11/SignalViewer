"""
Signal Viewer Pro v4.0 - Layout
===============================
Clean, modern UI layout definition.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
from config import APP_TITLE, APP_VERSION, MAX_ROWS, MAX_COLS


def create_layout() -> html.Div:
    """Create the main application layout."""
    
    return html.Div([
        # Stores for state management (minimal set)
        dcc.Store(id="store-csv-files", data={}),
        dcc.Store(id="store-assignments", data={"0": []}),
        dcc.Store(id="store-layout", data={"rows": 1, "cols": 1}),
        dcc.Store(id="store-cursor", data={"x": None, "visible": True}),
        dcc.Store(id="store-settings", data={"theme": "dark", "link_axes": True}),
        dcc.Store(id="store-selected-subplot", data=0),
        dcc.Download(id="download-session"),
        
        # Hidden file input for native dialog
        dcc.Upload(
            id="upload-csv",
            children=html.Div(id="upload-trigger"),
            style={"display": "none"},
            multiple=True,
        ),
        
        # Main container
        html.Div([
            # Header
            create_header(),
            
            # Main content area
            html.Div([
                # Sidebar
                create_sidebar(),
                
                # Plot area
                create_plot_area(),
            ], className="main-content"),
            
        ], className="app-container", id="app-container"),
        
    ], id="root")


def create_header() -> html.Div:
    """Create the header bar."""
    
    return html.Div([
        # Logo and title
        html.Div([
            html.Span("📊", className="logo-icon"),
            html.Span(f"{APP_TITLE}", className="app-title"),
            html.Span(f"v{APP_VERSION}", className="app-version"),
        ], className="header-left"),
        
        # Controls
        html.Div([
            # Layout selector
            html.Div([
                html.Label("Layout:", className="control-label"),
                dbc.Select(
                    id="layout-rows",
                    options=[{"label": f"{i}R", "value": i} for i in range(1, MAX_ROWS + 1)],
                    value=1,
                    className="layout-select",
                ),
                html.Span("×", className="layout-x"),
                dbc.Select(
                    id="layout-cols",
                    options=[{"label": f"{i}C", "value": i} for i in range(1, MAX_COLS + 1)],
                    value=1,
                    className="layout-select",
                ),
            ], className="layout-control"),
            
            # Subplot selector
            html.Div([
                html.Label("Subplot:", className="control-label"),
                dbc.Select(
                    id="subplot-select",
                    options=[{"label": "1", "value": "0"}],
                    value="0",
                    className="subplot-select",
                ),
            ], className="subplot-control"),
            
            # Theme toggle
            dbc.Switch(
                id="theme-switch",
                label="🌙",
                value=True,
                className="theme-switch",
            ),
            
            # Session buttons
            dbc.ButtonGroup([
                dbc.Button("💾 Save", id="btn-save", size="sm", outline=True, color="secondary"),
                dbc.Button("📂 Load", id="btn-load", size="sm", outline=True, color="secondary"),
            ], className="session-buttons"),
            
        ], className="header-right"),
        
    ], className="header")


def create_sidebar() -> html.Div:
    """Create the sidebar with file and signal management."""
    
    return html.Div([
        # Files section
        html.Div([
            html.Div([
                html.H6("📁 Data Files", className="section-title"),
                dbc.Button("+ Add CSV", id="btn-add-csv", size="sm", color="primary", className="add-btn"),
            ], className="section-header"),
            
            html.Div(id="csv-file-list", className="file-list"),
            
            dbc.Button("Clear All", id="btn-clear-csv", size="sm", color="danger", outline=True, 
                      className="clear-btn", style={"display": "none"}),
        ], className="sidebar-section"),
        
        # Signals section
        html.Div([
            html.Div([
                html.H6("📈 Signals", className="section-title"),
            ], className="section-header"),
            
            # Search input
            dbc.Input(
                id="signal-search",
                placeholder="🔍 Search signals...",
                size="sm",
                className="signal-search",
            ),
            
            # Signal tree
            html.Div(id="signal-tree", className="signal-tree"),
            
        ], className="sidebar-section signals-section"),
        
        # Assigned signals section
        html.Div([
            html.Div([
                html.H6("✅ Assigned", className="section-title"),
                html.Span(id="assigned-subplot-label", className="subplot-label"),
            ], className="section-header"),
            
            html.Div(id="assigned-list", className="assigned-list"),
            
            dbc.Button("Remove All", id="btn-remove-all", size="sm", color="secondary", outline=True,
                      className="remove-all-btn", style={"display": "none"}),
        ], className="sidebar-section assigned-section"),
        
    ], className="sidebar")


def create_plot_area() -> html.Div:
    """Create the main plot area."""
    
    return html.Div([
        # Plot container
        html.Div([
            dcc.Graph(
                id="main-plot",
                config={
                    "displayModeBar": True,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                    "scrollZoom": True,
                },
                className="plot-graph",
            ),
        ], className="plot-container"),
        
        # Cursor control bar
        html.Div([
            # Cursor toggle
            dbc.Switch(
                id="cursor-toggle",
                label="Cursor",
                value=True,
                className="cursor-toggle",
            ),
            
            # Play/Stop buttons
            dbc.ButtonGroup([
                dbc.Button("▶", id="btn-play", size="sm", color="success", outline=True, className="play-btn"),
                dbc.Button("⏹", id="btn-stop", size="sm", color="danger", outline=True, className="stop-btn"),
            ], className="cursor-buttons"),
            
            # Slider
            html.Div([
                dcc.Slider(
                    id="cursor-slider",
                    min=0,
                    max=100,
                    value=50,
                    step=0.01,
                    marks=None,
                    tooltip={"placement": "top", "always_visible": False},
                    updatemode="drag",
                    className="cursor-slider",
                ),
            ], className="slider-container"),
            
            # Cursor value display
            html.Div([
                html.Span("T: ", className="cursor-label"),
                html.Span("--", id="cursor-value", className="cursor-value"),
            ], className="cursor-display"),
            
            # Signal values at cursor
            html.Div(id="cursor-signals", className="cursor-signals"),
            
        ], id="cursor-bar", className="cursor-bar"),
        
        # Interval for cursor animation
        dcc.Interval(
            id="cursor-interval",
            interval=100,
            disabled=True,
        ),
        
    ], className="plot-area")


def create_signal_item(csv_id: str, csv_name: str, signal_name: str, checked: bool = False) -> html.Div:
    """Create a single signal item for the tree."""
    
    signal_key = f"{csv_id}:{signal_name}"
    
    return html.Div([
        dbc.Checkbox(
            id={"type": "signal-check", "key": signal_key},
            value=checked,
            className="signal-checkbox",
        ),
        html.Span(signal_name, className="signal-name", title=f"{csv_name} / {signal_name}"),
    ], className="signal-item")


def create_csv_group(csv_id: str, csv_name: str, signals: list, expanded: bool = True) -> html.Div:
    """Create a collapsible CSV group in the signal tree."""
    
    return html.Div([
        html.Div([
            html.Span("▼" if expanded else "▶", className="expand-icon", id={"type": "csv-expand", "id": csv_id}),
            html.Span("📄", className="csv-icon"),
            html.Span(csv_name, className="csv-name"),
            html.Span(f"({len(signals)})", className="signal-count"),
        ], className="csv-header", id={"type": "csv-header", "id": csv_id}),
        
        html.Div([
            create_signal_item(csv_id, csv_name, sig) for sig in signals
        ], className="csv-signals" + (" expanded" if expanded else " collapsed"), 
           id={"type": "csv-signals", "id": csv_id}),
    ], className="csv-group")


def create_assigned_signal(signal_key: str, signal_name: str, csv_name: str, color: str) -> html.Div:
    """Create an assigned signal item."""
    
    return html.Div([
        html.Div(className="color-dot", style={"backgroundColor": color}),
        html.Span(signal_name, className="assigned-name"),
        html.Span(f"({csv_name})", className="assigned-csv"),
        html.Button("×", className="remove-btn", id={"type": "remove-signal", "key": signal_key}),
    ], className="assigned-item")

