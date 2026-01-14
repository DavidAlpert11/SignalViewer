"""
Signal Viewer Pro - UI Layout
==============================
Main layout and panel definitions for Dash app.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc


def create_layout():
    """Create the main application layout"""
    return dbc.Container([
        # =====================================================================
        # STORES (State management)
        # =====================================================================
        dcc.Store(id="store-runs", data=[]),                    # List of run file paths
        dcc.Store(id="store-view-state", data={}),              # ViewState as dict
        dcc.Store(id="store-derived", data={}),                 # Derived signals
        dcc.Store(id="store-signal-settings", data={}),         # Per-signal settings
        dcc.Store(id="store-compare-results", data=[]),         # Compare results
        dcc.Store(id="store-stream-config", data={}),           # Stream config
        dcc.Store(id="store-report", data={}),                  # Report data
        dcc.Store(id="store-refresh", data=0),                  # Refresh trigger
        dcc.Store(id="store-selected-files", data=[]),          # Multi-file import selection
        dcc.Store(id="store-collapsed-runs", data={}),          # Collapsed state per run {idx: bool}
        
        # =====================================================================
        # HEADER
        # =====================================================================
        dbc.Row([
            dbc.Col([
                html.H4("Signal Viewer Pro", className="mb-0 text-light"),
            ], width="auto"),
            dbc.Col([
                # Mode indicators
                html.Div(id="mode-badges", className="d-inline-flex gap-2 me-3"),
            ], className="d-flex align-items-center"),
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button("📂 Import", id="btn-import", color="primary", size="sm"),
                    dbc.Button("🔄 Refresh", id="btn-refresh", color="secondary", size="sm", outline=True, 
                              title="Re-read all CSVs"),
                    dbc.Button("▶️ Stream", id="btn-stream-toggle", color="secondary", size="sm", outline=True,
                              title="Toggle auto-refresh"),
                    dbc.Button("💾 Save", id="btn-save", color="secondary", size="sm", outline=True),
                    dbc.Button("📁 Load", id="btn-load", color="secondary", size="sm", outline=True),
                ], className="me-2"),
                # Stream rate selector (visible when streaming)
                html.Div([
                    dbc.Select(
                        id="select-stream-rate",
                        options=[
                            {"label": "0.5s", "value": 500},
                            {"label": "1s", "value": 1000},
                            {"label": "2s", "value": 2000},
                            {"label": "5s", "value": 5000},
                        ],
                        value=1000,
                        size="sm",
                        style={"width": "60px", "display": "inline-block"},
                    ),
                ], id="stream-rate-container", style={"display": "none"}, className="me-2"),
                dbc.Button("🗑️ Clear All", id="btn-clear-all", color="danger", size="sm", outline=True, className="me-2"),
                dbc.Button("📊 Report", id="btn-report", color="info", size="sm", outline=True, className="me-2"),
                dbc.Button("🌙", id="btn-theme", color="link", size="sm"),
            ], className="text-end"),
        ], className="py-2 px-3 bg-dark border-bottom border-secondary align-items-center"),
        
        # =====================================================================
        # MAIN CONTENT
        # =====================================================================
        dbc.Row([
            # -----------------------------------------------------------------
            # LEFT SIDEBAR: Runs & Signals
            # -----------------------------------------------------------------
            dbc.Col([
                # Runs Panel (SDI: "Runs/Sources")
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("📁 Runs"),
                        dbc.Badge(id="runs-count", color="secondary", className="ms-2"),
                    ], className="py-2"),
                    dbc.CardBody([
                        html.Div(id="runs-list"),
                    ], className="p-2", style={"maxHeight": "180px", "overflowY": "auto"}),
                ], className="mb-2"),
                
                # Signals Panel
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("📈 Signals"),
                        dbc.Input(
                            id="signal-search",
                            placeholder="Filter...",
                            size="sm",
                            className="ms-2",
                            style={"width": "100px", "display": "inline-block"},
                        ),
                    ], className="py-2 d-flex align-items-center justify-content-between"),
                    dbc.CardBody([
                        html.Div(id="signal-tree"),
                    ], className="p-2", style={"maxHeight": "300px", "overflowY": "auto"}),
                ], className="mb-2"),
                
                # Assigned Panel (current subplot)
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("✓ Assigned"),
                        dbc.Badge(id="active-subplot-badge", color="primary", className="ms-2"),
                    ], className="py-2"),
                    dbc.CardBody([
                        # Time mode: signal list
                        html.Div(id="assigned-list"),
                        
                        # X-Y mode controls (hidden by default)
                        html.Div([
                            html.Hr(className="my-2"),
                            html.Label("X-Y Mode Configuration", className="small fw-bold text-info"),
                            
                            # X signal selector (only X - Y comes from assigned list)
                            html.Div([
                                html.Label("X Axis Signal:", className="small text-muted"),
                                dcc.Dropdown(
                                    id="xy-x-signal",
                                    options=[],
                                    placeholder="Select X signal...",
                                    className="mb-2",
                                    style={"fontSize": "11px"},
                                ),
                            ]),
                            
                            # Hidden - Y signals now come from assigned list, kept for callback compatibility
                            dcc.Store(id="xy-y-signals", data=[]),
                            
                            # Y signals explanation
                            html.Div([
                                html.Small("📌 Y signals: Assign signals normally in the list above.", 
                                          className="text-info"),
                            ], className="mb-2"),
                            
                            # Alignment method
                            html.Div([
                                html.Label("Alignment:", className="small text-muted"),
                                dbc.RadioItems(
                                    id="xy-alignment",
                                    options=[
                                        {"label": "Linear interp.", "value": "linear"},
                                        {"label": "Nearest", "value": "nearest"},
                                    ],
                                    value="linear",
                                    inline=True,
                                    className="small",
                                ),
                            ]),
                            html.Small("Interpolates Y to X's time base for alignment", className="text-muted"),
                        ], id="xy-controls", style={"display": "none"}),
                    ], className="p-2", style={"maxHeight": "300px", "overflowY": "auto"}),
                ]),
            ], width=2, className="bg-dark p-2", style={"height": "calc(100vh - 60px)", "overflowY": "auto"}),
            
            # -----------------------------------------------------------------
            # CENTER: Plot Area
            # -----------------------------------------------------------------
            dbc.Col([
                # Tab Bar (P1: SDI-like views)
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            # Tab container
                            html.Div(id="tab-bar", className="d-flex align-items-center"),
                            # Add tab button
                            dbc.Button("+ Tab", id="btn-add-tab", size="sm", color="secondary", 
                                      outline=True, className="ms-2"),
                        ], className="d-flex align-items-center"),
                    ]),
                ], className="py-1 px-3 bg-dark border-bottom border-secondary"),
                
                # Hidden stores for tabs - Start with "View 1" not hidden "main"
                dcc.Store(id="store-tabs", data=[{"id": "view_1", "name": "View 1"}]),
                dcc.Store(id="store-active-tab", data="view_1"),
                
                # Toolbar
                dbc.Row([
                    dbc.Col([
                        # Layout selector
                        dbc.InputGroup([
                            dbc.InputGroupText("Layout", className="small"),
                            dbc.Select(
                                id="select-rows",
                                options=[{"label": str(i), "value": i} for i in range(1, 5)],
                                value=1,
                                size="sm",
                                style={"width": "50px"},
                            ),
                            dbc.InputGroupText("×", className="small"),
                            dbc.Select(
                                id="select-cols",
                                options=[{"label": str(i), "value": i} for i in range(1, 5)],
                                value=1,
                                size="sm",
                                style={"width": "50px"},
                            ),
                        ], size="sm", className="me-2"),
                    ], width="auto"),
                    dbc.Col([
                        # Subplot selector - WIDER for full label visibility (fix clipping)
                        dbc.InputGroup([
                            dbc.Select(
                                id="select-subplot",
                                options=[{"label": "Subplot 1 / 1", "value": 0}],
                                value=0,
                                size="sm",
                                style={"minWidth": "160px", "fontSize": "13px"},
                            ),
                        ], size="sm", className="me-2"),
                    ], width="auto"),
                    dbc.Col([
                        # Mode toggle with text labels (not just icons)
                        dbc.ButtonGroup([
                            dbc.Button("📈 Time", id="btn-mode-time", size="sm", color="primary", outline=False),
                            dbc.Button("🔀 X-Y", id="btn-mode-xy", size="sm", color="secondary", outline=True),
                        ], size="sm", className="me-2"),
                    ], width="auto"),
                    dbc.Col([
                        # Cursor toggle - square button style matching Time/X-Y (P0-19)
                        dbc.ButtonGroup([
                            dbc.Button("📍 Cursor", id="btn-cursor-toggle", size="sm", color="secondary", outline=True),
                        ], size="sm"),
                        # Hidden switch for backward compatibility
                        dcc.Checklist(id="switch-cursor", options=[{"label": "", "value": True}], value=[], style={"display": "none"}),
                    ], width="auto"),
                    dbc.Col([
                        # Cursor display scope: Active or All subplots (P0-19)
                        dbc.ButtonGroup([
                            dbc.Button("Active", id="btn-cursor-active", size="sm", color="primary", outline=False),
                            dbc.Button("All", id="btn-cursor-all", size="sm", color="secondary", outline=True),
                        ], size="sm", className="ms-1", id="cursor-scope-group"),
                    ], width="auto", id="cursor-scope-col", style={"display": "none"}),
                    dbc.Col([
                        # Clear subplot button
                        dbc.Button("🗑️ Clear", id="btn-clear-subplot", size="sm", color="danger", outline=True),
                    ], width="auto", className="ms-auto"),
                ], className="py-2 px-3 bg-dark border-bottom border-secondary align-items-center g-0"),
                
                # Hidden store for subplot mode
                dcc.Store(id="store-subplot-mode", data="time"),
                
                # Cursor controls (shown when cursor enabled)
                html.Div([
                    dbc.Row([
                        dbc.Col([
                            html.Span("T:", className="text-muted small me-2"),
                        ], width="auto"),
                        dbc.Col([
                            dcc.Slider(
                                id="cursor-slider",
                                min=0, max=100, value=0,
                                marks=None,
                                tooltip={"placement": "bottom", "always_visible": True},
                                className="w-100",
                            ),
                        ]),
                        # Jump to time input
                        dbc.Col([
                            dbc.InputGroup([
                                dbc.Input(
                                    id="cursor-jump-input",
                                    type="number",
                                    placeholder="Jump to T...",
                                    size="sm",
                                    style={"width": "90px"},
                                    debounce=True,
                                ),
                                dbc.Button("→", id="btn-cursor-jump", size="sm", color="info", outline=True),
                            ], size="sm"),
                        ], width="auto"),
                        dbc.Col([
                            html.Span(id="cursor-time-display", className="text-info small fw-bold"),
                        ], width="auto"),
                    ], className="align-items-center"),
                ], id="cursor-controls", style={"display": "none"}, className="py-2 px-3 bg-dark"),
                
                # Main plot - height controlled by figure, min-height ensures visibility
                dcc.Graph(
                    id="main-plot",
                    config={
                        "displayModeBar": True,
                        "scrollZoom": True,
                        "displaylogo": False,
                    },
                    style={"minHeight": "500px", "height": "auto"},
                ),
            ], width=8, className="p-0", style={"overflowY": "auto", "maxHeight": "calc(100vh - 60px)"}),
            
            # -----------------------------------------------------------------
            # RIGHT SIDEBAR: Cursor Values + Tools (collapsed)
            # -----------------------------------------------------------------
            dbc.Col([
                # Cursor Values (shown when cursor enabled)
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("📍 Cursor Values", className="small"),
                        dbc.Switch(
                            id="switch-inspector-all",
                            label="All",
                            value=True,
                            className="float-end small mb-0",
                            style={"fontSize": "10px"},
                        ),
                    ], className="py-1 d-flex align-items-center justify-content-between"),
                    dbc.CardBody([
                        html.Div(id="inspector-values"),
                    ], className="p-2", style={"maxHeight": "250px", "overflowY": "auto"}),
                ], className="mb-2"),
                
                # Operations Panel (collapsed by default)
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("⚙ Operations", className="small"),
                        dbc.Button("▼", id="btn-toggle-ops", size="sm", color="link", className="float-end p-0"),
                    ], className="py-1"),
                    dbc.Collapse([
                        dbc.CardBody([
                            create_operations_panel(),
                        ], className="p-2"),
                    ], id="collapse-ops", is_open=False),
                ], className="mb-2"),
                
                # Compare Panel (collapsed by default)
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("⚖ Compare", className="small"),
                        dbc.Button("▼", id="btn-toggle-compare", size="sm", color="link", className="float-end p-0"),
                    ], className="py-1"),
                    dbc.Collapse([
                        dbc.CardBody([
                            create_compare_panel(),
                        ], className="p-2"),
                    ], id="collapse-compare", is_open=False),
                ], className="mb-2"),
                
                # Stream Panel removed - functionality moved to header buttons
                # Keep collapse-stream for callback compatibility but hide it
                dbc.Collapse([
                    html.Div(id="stream-status-hidden"),
                ], id="collapse-stream", is_open=False, style={"display": "none"}),
            ], width=2, className="bg-dark p-2", style={"height": "calc(100vh - 60px)", "overflowY": "auto"}),
        ], className="g-0"),
        
        # =====================================================================
        # MODALS
        # =====================================================================
        create_import_modal(),
        create_report_modal(),
        
        # Hidden components
        dcc.Download(id="download-session"),
        dcc.Download(id="download-report"),
        dcc.Interval(id="interval-stream", interval=500, disabled=True),
        dcc.Interval(id="interval-replay", interval=50, disabled=True),
        
    ], fluid=True, className="vh-100 p-0")


def create_operations_panel():
    """Create the operations panel content with signal selection"""
    return html.Div([
        # Operation type selector
        dbc.Label("Operation Type", className="small fw-bold"),
        dbc.RadioItems(
            id="select-op-type",
            options=[
                {"label": "Unary (1)", "value": "unary"},
                {"label": "Binary (2)", "value": "binary"},
                {"label": "Multi (N)", "value": "multi"},
            ],
            value="unary",
            inline=True,
            className="mb-2 small",
        ),
        
        # Signal selection
        dbc.Label("Select Signal(s)", className="small"),
        dcc.Dropdown(
            id="select-op-signals",
            options=[],
            multi=True,
            placeholder="Select signals...",
            className="mb-2",
            style={"fontSize": "11px"},
        ),
        
        # Operation dropdown (populated dynamically)
        dbc.Label("Operation", className="small"),
        dbc.Select(
            id="select-operation",
            options=[
                # Unary ops
                {"label": "Derivative (d/dt)", "value": "derivative"},
                {"label": "Integral (∫dt)", "value": "integral"},
                {"label": "Absolute |x|", "value": "abs"},
                {"label": "Normalize (0-1)", "value": "normalize"},
                {"label": "RMS", "value": "rms"},
            ],
            value="derivative",
            size="sm",
            className="mb-2",
        ),
        
        # Alignment (for binary/multi)
        html.Div([
            dbc.Label("Alignment", className="small"),
            dbc.Select(
                id="select-op-alignment",
                options=[
                    {"label": "Linear interpolation", "value": "linear"},
                    {"label": "Nearest neighbor", "value": "nearest"},
                ],
                value="linear",
                size="sm",
                className="mb-2",
            ),
        ], id="op-alignment-group"),
        
        # Output name
        dbc.Label("Output Name", className="small"),
        dbc.Input(
            id="input-op-output-name",
            placeholder="Auto-generated",
            size="sm",
            className="mb-2",
        ),
        
        # Apply button
        dbc.Button("Create Derived Signal", id="btn-apply-op", color="success", size="sm", className="w-100"),
        
        # Status message
        html.Div(id="op-status", className="mt-2 small"),
    ])


def create_compare_panel():
    """Create the compare panel content with full options"""
    return html.Div([
        # Run selectors
        dbc.Label("Baseline Run (A)", className="small fw-bold"),
        dcc.Dropdown(
            id="select-baseline-run",
            options=[],
            placeholder="Select run A...",
            className="mb-2",
            style={"fontSize": "11px"},
        ),
        
        dbc.Label("Compare To Run (B)", className="small fw-bold"),
        dcc.Dropdown(
            id="select-compare-run",
            options=[],
            placeholder="Select run B...",
            className="mb-2",
            style={"fontSize": "11px"},
        ),
        
        # Signal selector
        dbc.Label("Signal to Compare", className="small"),
        dcc.Dropdown(
            id="select-compare-signal",
            options=[],
            placeholder="Select signal...",
            className="mb-2",
            style={"fontSize": "11px"},
        ),
        dbc.Checkbox(
            id="check-common-only",
            label="Show only common signals",
            value=True,
            className="small mb-2",
        ),
        
        # Alignment options
        dbc.Label("Time Alignment", className="small"),
        dbc.Select(
            id="select-compare-alignment",
            options=[
                {"label": "Baseline time (A)", "value": "baseline"},
                {"label": "Union (all points)", "value": "union"},
                {"label": "Intersection only", "value": "intersection"},
            ],
            value="baseline",
            size="sm",
            className="mb-2",
        ),
        dbc.Button("Compare", id="btn-compare", color="info", size="sm", className="w-100"),
        html.Div(id="compare-results", className="mt-2 small"),
    ])


def create_stream_panel():
    """
    Create the Smart Incremental Refresh panel (P0-18).
    
    Replaces the old streaming panel with a smarter button:
    - Detects file growth (appended rows) and reads only new data
    - Detects file rewrite (size smaller) and does full reload with warning
    - Updates plots and derived signals incrementally
    """
    return html.Div([
        html.P("Monitor CSV files for updates.", className="small text-muted mb-2"),
        
        # Smart Refresh button
        dbc.Button(
            "🔄 Smart Refresh",
            id="btn-smart-refresh",
            color="info",
            outline=True,
            size="sm",
            className="w-100 mb-2",
        ),
        
        # Auto-refresh option
        dbc.Switch(id="switch-auto-refresh", label="Auto-refresh (5s)", value=False, className="mb-2"),
        
        # Status indicator
        html.Div([
            html.Small("Status: ", className="text-muted"),
            html.Span(id="smart-refresh-status", className="small text-success"),
        ], className="mb-2"),
        
        # Last check info
        html.Div(id="smart-refresh-info", className="small text-muted"),
        
        # Hidden stores for incremental tracking
        dcc.Store(id="store-file-offsets", data={}),  # {path: {offset, mtime, size}}
    ])


def create_import_modal():
    """Create the CSV import modal"""
    return dbc.Modal([
        dbc.ModalHeader("Import CSV"),
        dbc.ModalBody([
            dbc.Row([
                dbc.Col([
                    dbc.Label("File", className="small"),
                    dbc.Input(id="import-file-path", readonly=True, size="sm"),
                    dbc.Button("Browse...", id="btn-browse", size="sm", className="mt-1"),
                ], width=12, className="mb-2"),
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Checkbox(id="import-has-header", label="Has Header Row", value=True),
                ], width=6),
                dbc.Col([
                    dbc.Label("Header Row", className="small"),
                    dbc.Input(id="import-header-row", type="number", value=0, size="sm"),
                ], width=6),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Skip Rows", className="small"),
                    dbc.Input(id="import-skip-rows", type="number", value=0, size="sm"),
                ], width=6),
                dbc.Col([
                    dbc.Label("Delimiter", className="small"),
                    dbc.Select(
                        id="import-delimiter",
                        options=[
                            {"label": "Auto", "value": "auto"},
                            {"label": "Comma (,)", "value": ","},
                            {"label": "Semicolon (;)", "value": ";"},
                            {"label": "Tab", "value": "\t"},
                            {"label": "Space", "value": " "},
                        ],
                        value="auto",
                        size="sm",
                    ),
                ], width=6),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Time Column", className="small"),
                    dbc.Select(id="import-time-col", size="sm"),
                ], width=12),
            ], className="mb-2"),
            dbc.Label("Preview", className="small"),
            html.Div(id="import-preview", style={"maxHeight": "200px", "overflowY": "auto", "fontSize": "11px"}),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="btn-import-cancel", color="secondary", size="sm"),
            dbc.Button("Import", id="btn-import-confirm", color="primary", size="sm"),
        ]),
    ], id="modal-import", size="lg", is_open=False)


def create_report_modal():
    """Create the report builder modal (P0-9, P0-14 with RTL/Hebrew support)"""
    return dbc.Modal([
        dbc.ModalHeader("Report Builder"),
        dbc.ModalBody([
            # Report Title
            dbc.Label("Report Title", className="small"),
            dbc.Input(id="report-title", value="Signal Analysis Report", size="sm", className="mb-2"),
            
            # RTL Toggle for Hebrew support (P0-14)
            dbc.Row([
                dbc.Col([
                    dbc.Label("Text Direction", className="small"),
                ], width=6),
                dbc.Col([
                    dbc.Switch(
                        id="report-rtl",
                        label="Right-to-Left (Hebrew/Arabic)",
                        value=False,
                        className="small",
                    ),
                ], width=6),
            ], className="mb-2"),
            
            # Introduction (supports Hebrew/RTL)
            dbc.Label("Introduction", className="small"),
            dbc.Textarea(id="report-intro", rows=3, className="mb-2", 
                        placeholder="Enter introduction text (supports Hebrew)..."),
            
            # Conclusion
            dbc.Label("Summary / Conclusion", className="small"),
            dbc.Textarea(id="report-conclusion", rows=3, className="mb-2",
                        placeholder="Enter conclusion text (supports Hebrew)..."),
            
            # Include Subplots with per-subplot metadata
            dbc.Label("Include Subplots:", className="small"),
            html.Div(id="report-subplot-list"),
            
            # Export format
            dbc.Row([
                dbc.Col([
                    dbc.Label("Export Format", className="small"),
                    dbc.RadioItems(
                        id="report-format",
                        options=[
                            {"label": "HTML (offline)", "value": "html"},
                            {"label": "Word (.docx)", "value": "docx"},
                            {"label": "CSV (data only)", "value": "csv"},
                        ],
                        value="html",
                        inline=True,
                        className="small",
                    ),
                ]),
            ], className="mt-3"),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="btn-report-cancel", color="secondary", size="sm"),
            dbc.Button("Export", id="btn-report-export", color="primary", size="sm"),
        ]),
    ], id="modal-report", size="lg", is_open=False)

