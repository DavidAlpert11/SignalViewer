"""
Signal Viewer Pro v4.0 - Layout
===============================
Clean, modern UI layout definition with all features.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
from config import APP_TITLE, APP_VERSION, MAX_ROWS, MAX_COLS, SIGNAL_COLORS


def create_layout() -> html.Div:
    """Create the main application layout."""
    
    return html.Div([
        # Stores for state management
        dcc.Store(id="store-csv-files", data={}),
        dcc.Store(id="store-assignments", data={"0": []}),
        dcc.Store(id="store-layout", data={"rows": 1, "cols": 1}),
        dcc.Store(id="store-cursor", data={"x": None, "visible": True}),
        dcc.Store(id="store-settings", data={"theme": "dark", "link_axes": True}),
        dcc.Store(id="store-selected-subplot", data=0),
        dcc.Store(id="store-subplot-modes", data={}),  # X-Y mode per subplot
        dcc.Store(id="store-signal-props", data={}),  # Signal properties (color, scale, etc.)
        dcc.Store(id="store-autocomplete", data=[]),  # Search suggestions
        dcc.Download(id="download-session"),
        dcc.Download(id="download-export"),
        
        # Hidden file input for native dialog
        dcc.Upload(
            id="upload-csv",
            children=html.Div(id="upload-trigger"),
            style={"display": "none"},
            multiple=True,
        ),
        
        # Modals
        create_signal_props_modal(),
        create_derived_signal_modal(),
        create_export_modal(),
        
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
            
            # Export button
            dbc.Button("📤", id="btn-export", size="sm", outline=True, color="secondary",
                      title="Export plot/data", className="export-btn"),
            
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
        
        # Signals section with autocomplete
        html.Div([
            html.Div([
                html.H6("📈 Signals", className="section-title"),
                dbc.Button("➕", id="btn-derived", size="sm", outline=True, color="info",
                          title="Add derived signal", className="derived-btn"),
            ], className="section-header"),
            
            # Search input with autocomplete
            html.Div([
                dbc.Input(
                    id="signal-search",
                    placeholder="🔍 Search signals...",
                    size="sm",
                    className="signal-search",
                    debounce=True,
                ),
                html.Div(id="autocomplete-dropdown", className="autocomplete-dropdown"),
            ], className="search-container"),
            
            # Signal tree
            html.Div(id="signal-tree", className="signal-tree"),
            
        ], className="sidebar-section signals-section"),
        
        # Assigned signals section
        html.Div([
            html.Div([
                html.H6("✅ Assigned", className="section-title"),
                html.Span(id="assigned-subplot-label", className="subplot-label"),
            ], className="section-header"),
            
            # X-Y mode toggle
            html.Div([
                dbc.Switch(
                    id="xy-mode-switch",
                    label="X-Y Mode",
                    value=False,
                    className="xy-mode-switch",
                ),
                dbc.Select(
                    id="xy-x-signal",
                    options=[],
                    value="",
                    className="xy-x-signal",
                    style={"display": "none"},
                ),
            ], className="xy-mode-container"),
            
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
                    "toImageButtonOptions": {
                        "format": "png",
                        "height": 800,
                        "width": 1200,
                        "scale": 2,
                    },
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
            
            # Slider with actual time values
            html.Div([
                html.Span("", id="cursor-min", className="cursor-min"),
                dcc.Slider(
                    id="cursor-slider",
                    min=0,
                    max=100,
                    value=50,
                    step=0.001,
                    marks=None,
                    tooltip={"placement": "top", "always_visible": True},
                    updatemode="drag",
                    className="cursor-slider",
                ),
                html.Span("", id="cursor-max", className="cursor-max"),
            ], className="slider-container"),
            
            # Cursor value display
            html.Div([
                html.Span("T: ", className="cursor-label"),
                html.Span("--", id="cursor-value", className="cursor-value"),
            ], className="cursor-display"),
            
            # Signal values at cursor (scrollable)
            html.Div(id="cursor-signals", className="cursor-signals"),
            
        ], id="cursor-bar", className="cursor-bar"),
        
        # Interval for cursor animation
        dcc.Interval(
            id="cursor-interval",
            interval=100,
            disabled=True,
        ),
        
    ], className="plot-area")


def create_signal_props_modal() -> dbc.Modal:
    """Create modal for editing signal properties."""
    
    return dbc.Modal([
        dbc.ModalHeader("Signal Properties"),
        dbc.ModalBody([
            # Signal name (read-only)
            dbc.InputGroup([
                dbc.InputGroupText("Signal:"),
                dbc.Input(id="props-signal-name", disabled=True),
            ], className="mb-3"),
            
            # Custom display name
            dbc.InputGroup([
                dbc.InputGroupText("Display Name:"),
                dbc.Input(id="props-display-name", placeholder="Custom name..."),
            ], className="mb-3"),
            
            # Color picker
            dbc.InputGroup([
                dbc.InputGroupText("Color:"),
                dbc.Input(id="props-color", type="color", value="#00ffff"),
            ], className="mb-3"),
            
            # Line width
            dbc.InputGroup([
                dbc.InputGroupText("Line Width:"),
                dbc.Input(id="props-line-width", type="number", value=1.5, min=0.5, max=5, step=0.5),
            ], className="mb-3"),
            
            # Scale factor
            dbc.InputGroup([
                dbc.InputGroupText("Scale:"),
                dbc.Input(id="props-scale", type="number", value=1.0, step=0.1),
            ], className="mb-3"),
            
            # Offset
            dbc.InputGroup([
                dbc.InputGroupText("Offset:"),
                dbc.Input(id="props-offset", type="number", value=0, step=0.1),
            ], className="mb-3"),
            
            # Hidden field for signal key
            dcc.Store(id="props-signal-key", data=""),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="props-cancel", color="secondary"),
            dbc.Button("Apply", id="props-apply", color="primary"),
        ]),
    ], id="modal-signal-props", centered=True)


def create_derived_signal_modal() -> dbc.Modal:
    """Create modal for creating derived signals."""
    
    return dbc.Modal([
        dbc.ModalHeader("Create Derived Signal"),
        dbc.ModalBody([
            # Operation type
            dbc.Label("Operation:"),
            dbc.Select(
                id="derived-operation",
                options=[
                    {"label": "Derivative (dY/dT)", "value": "derivative"},
                    {"label": "Integral (∫Y dT)", "value": "integral"},
                    {"label": "Scale (Y × K)", "value": "scale"},
                    {"label": "Offset (Y + C)", "value": "offset"},
                    {"label": "Absolute (|Y|)", "value": "abs"},
                    {"label": "Negative (-Y)", "value": "neg"},
                    {"label": "Sum (A + B)", "value": "sum"},
                    {"label": "Difference (A - B)", "value": "diff"},
                    {"label": "Product (A × B)", "value": "product"},
                    {"label": "Ratio (A / B)", "value": "ratio"},
                    {"label": "Average (avg(signals))", "value": "avg"},
                ],
                value="derivative",
                className="mb-3",
            ),
            
            # Primary signal
            dbc.Label("Signal:"),
            dbc.Select(id="derived-signal-a", options=[], className="mb-3"),
            
            # Secondary signal (for binary operations)
            html.Div([
                dbc.Label("Second Signal:"),
                dbc.Select(id="derived-signal-b", options=[], className="mb-3"),
            ], id="derived-signal-b-container", style={"display": "none"}),
            
            # Constant value (for scale/offset)
            html.Div([
                dbc.Label("Constant:"),
                dbc.Input(id="derived-constant", type="number", value=1.0, className="mb-3"),
            ], id="derived-constant-container", style={"display": "none"}),
            
            # Output name
            dbc.Label("Output Name:"),
            dbc.Input(id="derived-output-name", placeholder="derived_signal", className="mb-3"),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="derived-cancel", color="secondary"),
            dbc.Button("Create", id="derived-create", color="primary"),
        ]),
    ], id="modal-derived-signal", centered=True)


def create_export_modal() -> dbc.Modal:
    """Create modal for export options."""
    
    return dbc.Modal([
        dbc.ModalHeader("Export"),
        dbc.ModalBody([
            dbc.Tabs([
                dbc.Tab([
                    html.P("Export the current plot as an image.", className="mt-3"),
                    dbc.Select(
                        id="export-image-format",
                        options=[
                            {"label": "PNG (High Resolution)", "value": "png"},
                            {"label": "SVG (Vector)", "value": "svg"},
                            {"label": "PDF (Print)", "value": "pdf"},
                            {"label": "WebP (Web)", "value": "webp"},
                        ],
                        value="png",
                        className="mb-3",
                    ),
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Width:"),
                            dbc.Input(id="export-width", type="number", value=1200),
                        ]),
                        dbc.Col([
                            dbc.Label("Height:"),
                            dbc.Input(id="export-height", type="number", value=800),
                        ]),
                    ], className="mb-3"),
                    dbc.Button("Export Image", id="btn-export-image", color="primary", className="w-100"),
                ], label="Image", tab_id="export-image"),
                
                dbc.Tab([
                    html.P("Export assigned signals as CSV data.", className="mt-3"),
                    dbc.Checkbox(id="export-include-time", label="Include time column", value=True, className="mb-2"),
                    dbc.Checkbox(id="export-all-subplots", label="Export all subplots", value=False, className="mb-2"),
                    dbc.Checkbox(id="export-interpolate", label="Interpolate to common time base", value=True, className="mb-2"),
                    dbc.Button("Export CSV", id="btn-export-csv", color="primary", className="w-100 mt-3"),
                ], label="Data", tab_id="export-data"),
                
                dbc.Tab([
                    html.P("Export as interactive HTML file.", className="mt-3"),
                    dbc.Checkbox(id="export-html-include-data", label="Include data in file", value=True, className="mb-2"),
                    dbc.Input(id="export-html-title", placeholder="Report Title", className="mb-3"),
                    dbc.Button("Export HTML", id="btn-export-html", color="primary", className="w-100"),
                ], label="HTML", tab_id="export-html"),
            ], id="export-tabs"),
        ]),
        dbc.ModalFooter([
            dbc.Button("Close", id="export-close", color="secondary"),
        ]),
    ], id="modal-export", centered=True, size="lg")


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
    """Create an assigned signal item with settings button."""
    
    return html.Div([
        html.Div(className="color-dot", style={"backgroundColor": color}),
        html.Span(signal_name, className="assigned-name"),
        html.Span(f"({csv_name})", className="assigned-csv"),
        html.Button("⚙", className="settings-btn", id={"type": "signal-settings", "key": signal_key}, 
                   title="Signal properties"),
        html.Button("×", className="remove-btn", id={"type": "remove-signal", "key": signal_key}),
    ], className="assigned-item", id={"type": "assigned-item", "key": signal_key})
