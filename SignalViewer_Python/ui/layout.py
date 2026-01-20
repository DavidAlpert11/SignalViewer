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
        # Core data stores
        dcc.Store(id="store-runs", data=[]),                    # List of run file paths
        dcc.Store(id="store-view-state", data={}),              # ViewState as dict
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
                        dbc.Button(
                            "🔗",
                            id="btn-toggle-link-mode",
                            size="sm",
                            color="secondary",
                            outline=True,
                            className="ms-auto",
                            title="Link/Unlink CSVs: When linked, assigning a signal assigns it from ALL linked CSVs",
                        ),
                    ], className="py-2 d-flex align-items-center"),
                    dbc.CardBody([
                        # Link mode selector (hidden by default) - Feature 2 Enhanced
                        html.Div([
                            html.Small("🔗 Linked CSVs:", className="text-info d-block mb-1"),
                            dcc.Dropdown(
                                id="select-linked-runs",
                                options=[],
                                multi=True,
                                placeholder="Select CSVs to link...",
                                style={"fontSize": "11px"},
                                className="mb-2",
                            ),
                            # Quick action buttons
                            dbc.ButtonGroup([
                                dbc.Button("Link All", id="btn-link-all", size="sm", color="info", outline=True),
                                dbc.Button("Unlink All", id="btn-unlink-all", size="sm", color="secondary", outline=True),
                            ], size="sm", className="mb-2"),
                            html.Small(
                                "When linked, clicking a signal assigns/removes it from ALL linked CSVs.",
                                className="text-muted d-block mb-2",
                            ),
                        ], id="link-mode-panel", style={"display": "none"}),
                        html.Div(id="runs-list"),
                    ], className="p-2", style={"maxHeight": "220px", "overflowY": "auto"}),
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
                
                # Hidden stores for tabs - Start with "Tab 1" (P2-6)
                dcc.Store(id="store-tabs", data=[{"id": "tab_1", "name": "Tab 1"}]),
                dcc.Store(id="store-active-tab", data="tab_1"),
                dcc.Store(id="store-tab-view-states", data={}),  # Per-tab view state: {tab_id: view_state_dict}
                
                # Toolbar
                dbc.Row([
                    dbc.Col([
                        # Layout selector - compact styling to prevent white space masking values
                        dbc.InputGroup([
                            dbc.InputGroupText("R:", className="small", style={"padding": "0.25rem 0.4rem"}),
                            dbc.Select(
                                id="select-rows",
                                options=[{"label": str(i), "value": i} for i in range(1, 5)],
                                value=1,
                                size="sm",
                                style={"width": "45px", "minWidth": "45px", "padding": "0.25rem"},
                            ),
                            dbc.InputGroupText("×", className="small", style={"padding": "0.25rem 0.3rem"}),
                            dbc.InputGroupText("C:", className="small", style={"padding": "0.25rem 0.4rem"}),
                            dbc.Select(
                                id="select-cols",
                                options=[{"label": str(i), "value": i} for i in range(1, 5)],
                                value=1,
                                size="sm",
                                style={"width": "45px", "minWidth": "45px", "padding": "0.25rem"},
                            ),
                        ], size="sm", className="me-2", style={"flexWrap": "nowrap"}),
                    ], width="auto"),
                    dbc.Col([
                        # Subplot selector - shows "1 / N" by default
                        dbc.InputGroup([
                            dbc.InputGroupText("SP:", className="small", style={"padding": "0.25rem 0.4rem"}),
                            dbc.Select(
                                id="select-subplot",
                                options=[{"label": "1 / 1", "value": 0}],
                                value=0,
                                size="sm",
                                style={"minWidth": "65px", "padding": "0.25rem"},
                            ),
                        ], size="sm", className="me-2", style={"flexWrap": "nowrap"}),
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
                        # Axis limits button with popover
                        html.Div([
                            dbc.Button("📐 Axis", id="btn-axis-limits", size="sm", color="secondary", outline=True),
                            dbc.Popover([
                                dbc.PopoverHeader("Axis Limits"),
                                dbc.PopoverBody([
                                    # Scope: active subplot or all subplots
                                    dbc.RadioItems(
                                        id="select-axis-scope",
                                        options=[
                                            {"label": "Active subplot", "value": "active"},
                                            {"label": "All subplots in tab", "value": "all"},
                                        ],
                                        value="active",
                                        inline=True,
                                        className="small mb-2",
                                    ),
                                    dbc.Row([
                                        dbc.Col([
                                            dbc.Label("X-min", className="small mb-0"),
                                            dbc.Input(id="input-xlim-min", type="number", size="sm", placeholder="auto", step="any"),
                                        ], width=6),
                                        dbc.Col([
                                            dbc.Label("X-max", className="small mb-0"),
                                            dbc.Input(id="input-xlim-max", type="number", size="sm", placeholder="auto", step="any"),
                                        ], width=6),
                                    ], className="mb-2"),
                                    dbc.Row([
                                        dbc.Col([
                                            dbc.Label("Y-min", className="small mb-0"),
                                            dbc.Input(id="input-ylim-min", type="number", size="sm", placeholder="auto", step="any"),
                                        ], width=6),
                                        dbc.Col([
                                            dbc.Label("Y-max", className="small mb-0"),
                                            dbc.Input(id="input-ylim-max", type="number", size="sm", placeholder="auto", step="any"),
                                        ], width=6),
                                    ], className="mb-2"),
                                    dbc.Button("Apply", id="btn-apply-axis-limits", size="sm", color="primary", className="me-1"),
                                    dbc.Button("Reset", id="btn-reset-axis-limits", size="sm", color="secondary", outline=True),
                                ]),
                            ], target="btn-axis-limits", trigger="click", placement="bottom"),
                        ]),
                    ], width="auto", className="ms-2"),
                    dbc.Col([
                        # Clear subplot button
                        dbc.Button("🗑️ Clear", id="btn-clear-subplot", size="sm", color="danger", outline=True),
                    ], width="auto", className="ms-auto"),
                ], className="py-2 px-3 bg-dark border-bottom border-secondary align-items-center g-0"),
                
                # Hidden store for subplot mode
                
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
                                    style={"width": "100px"},
                                    debounce=True,
                                    step="any",  # Allow decimal values like 1.24
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
                # Note: Active/All toggle is in the toolbar buttons (btn-cursor-active/all)
                dbc.Card([
                    dbc.CardHeader([
                        html.Span("📍 Cursor Values", className="small"),
                    ], className="py-1"),
                    dbc.CardBody([
                        html.Div(id="inspector-values"),
                    ], className="p-2", style={"maxHeight": "250px", "overflowY": "auto"}),
                    # Hidden switch for callback compatibility
                    dcc.Checklist(id="switch-inspector-all", options=[{"label": "", "value": True}], 
                                  value=[True], style={"display": "none"}),
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
        create_signal_properties_modal(),
        create_compare_all_modal(),
        
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
    """
    Create the compare panel content (P3 - Advanced Multi-CSV Compare).
    
    Features:
    - Multi-run selection (2+ CSVs)
    - Baseline method (mean or specific CSV)
    - Common signals detection
    - Similarity scoring
    - Derived signal generation
    """
    return html.Div([
        # Multi-run selection
        dbc.Label("Select Runs to Compare", className="small fw-bold"),
        dcc.Dropdown(
            id="select-compare-runs",
            options=[],
            multi=True,
            placeholder="Select 2 or more runs...",
            className="mb-2",
            style={"fontSize": "11px"},
        ),
        
        # Baseline method
        dbc.Label("Baseline Method", className="small"),
        dbc.RadioItems(
            id="select-baseline-method",
            options=[
                {"label": "Mean of all selected", "value": "mean"},
                {"label": "Specific run:", "value": "specific"},
            ],
            value="mean",
            inline=True,
            className="small mb-1",
        ),
        dcc.Dropdown(
            id="select-baseline-run",
            options=[],
            placeholder="Select baseline run...",
            className="mb-2",
            style={"fontSize": "11px"},
            disabled=True,  # Enabled when "specific" is selected
        ),
        
        # Signal selector with filtering
        dbc.Label("Signal to Compare", className="small"),
        dcc.Dropdown(
            id="select-compare-signal",
            options=[],
            placeholder="Select signal...",
            className="mb-2",
            style={"fontSize": "11px"},
        ),
        
        # Show common signals info
        html.Div(id="compare-common-signals", className="small text-muted mb-2"),
        
        # Alignment options
        dbc.Label("Time Alignment", className="small"),
        dbc.Select(
            id="select-compare-alignment",
            options=[
                {"label": "Baseline time", "value": "baseline"},
                {"label": "Union (all points)", "value": "union"},
                {"label": "Intersection only", "value": "intersection"},
            ],
            value="baseline",
            size="sm",
            className="mb-2",
        ),
        
        # Compare single signal
        dbc.Button("Compare Signal", id="btn-compare", color="info", size="sm", className="w-100 mb-2"),
        
        # Compare all signals button
        dbc.Button("Compare All Common Signals", id="btn-compare-all", color="success", 
                   size="sm", outline=True, className="w-100 mb-2"),
        
        # Generate delta signals
        dbc.Button("Generate Delta Signals", id="btn-generate-deltas", color="warning",
                   size="sm", outline=True, className="w-100 mb-2"),
        
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
    """
    Create the report builder modal (P6-13, P6-14).
    
    All text fields are multi-line (Textarea) to support Enter/new lines.
    Each subplot has: Title, Caption, Description (multi-line).
    """
    return dbc.Modal([
        dbc.ModalHeader("Report Builder"),
        dbc.ModalBody([
            # Report Title - multi-line (P6-14)
            dbc.Label("Report Title", className="small fw-bold"),
            dbc.Textarea(
                id="report-title", 
                value="Signal Analysis Report", 
                rows=1, 
                className="mb-2",
                style={"resize": "vertical"},
            ),
            
            # RTL Toggle for Hebrew support
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
            
            # Introduction - multi-line (P6-14)
            dbc.Label("Introduction", className="small fw-bold"),
            dbc.Textarea(
                id="report-intro", 
                rows=4, 
                className="mb-2", 
                placeholder="Enter introduction text (supports multi-line and Hebrew)...",
                style={"resize": "vertical"},
            ),
            
            # Conclusion - multi-line (P6-14)
            dbc.Label("Summary / Conclusion", className="small fw-bold"),
            dbc.Textarea(
                id="report-conclusion", 
                rows=4, 
                className="mb-2",
                placeholder="Enter conclusion text (supports multi-line and Hebrew)...",
                style={"resize": "vertical"},
            ),
            
            # Include Subplots with per-subplot metadata (P6-13)
            dbc.Label("Include Subplots:", className="small fw-bold mt-2"),
            html.Small("Each subplot can have Title, Caption, and Description", className="text-muted d-block mb-2"),
            html.Div(id="report-subplot-list", style={"maxHeight": "300px", "overflowY": "auto"}),
            
            # Export scope (P2 - current tab vs all tabs)
            dbc.Row([
                dbc.Col([
                    dbc.Label("Export Scope", className="small fw-bold"),
                    dbc.RadioItems(
                        id="report-scope",
                        options=[
                            {"label": "Current Tab Only", "value": "current"},
                            {"label": "All Tabs", "value": "all"},
                        ],
                        value="current",
                        inline=True,
                        className="small",
                    ),
                ]),
            ], className="mt-3"),
            
            # Export format
            dbc.Row([
                dbc.Col([
                    dbc.Label("Export Format", className="small fw-bold"),
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
            ], className="mt-2"),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="btn-report-cancel", color="secondary", size="sm"),
            dbc.Button("Export", id="btn-report-export", color="primary", size="sm"),
        ]),
    ], id="modal-report", size="lg", is_open=False)


def create_signal_properties_modal():
    """Create the signal properties modal for editing signal display settings"""
    return dbc.Modal([
        dbc.ModalHeader("Signal Properties"),
        dbc.ModalBody([
            # Signal info (read-only)
            dbc.Row([
                dbc.Col([
                    dbc.Label("Original Name", className="small text-muted"),
                    html.Div(id="signal-props-original-name", className="small fw-bold text-info mb-2"),
                ], width=12),
            ]),
            
            # Display Name (rename)
            dbc.Row([
                dbc.Col([
                    dbc.Label("Display Name (rename)", className="small"),
                    dbc.Input(
                        id="signal-props-display-name",
                        placeholder="Enter custom display name...",
                        size="sm",
                        className="mb-2",
                    ),
                ], width=12),
            ]),
            
            # Line Width
            dbc.Row([
                dbc.Col([
                    dbc.Label("Line Width", className="small"),
                    dbc.Input(
                        id="signal-props-line-width",
                        type="number",
                        value=1.5,
                        min=0.5,
                        max=5,
                        step=0.5,
                        size="sm",
                        className="mb-2",
                    ),
                ], width=6),
                # Color picker
                dbc.Col([
                    dbc.Label("Color", className="small"),
                    dbc.Input(
                        id="signal-props-color",
                        type="color",
                        value="#2E86AB",
                        size="sm",
                        className="mb-2",
                        style={"height": "38px", "padding": "2px"},
                    ),
                ], width=6),
            ]),
            
            # Scale factor and Value Offset
            dbc.Row([
                dbc.Col([
                    dbc.Label("Scale Factor", className="small"),
                    dbc.Input(
                        id="signal-props-scale",
                        type="number",
                        value=1.0,
                        step=0.1,
                        size="sm",
                        className="mb-2",
                    ),
                    html.Small("Multiply signal values by this factor", className="text-muted"),
                ], width=6),
                # Value Offset
                dbc.Col([
                    dbc.Label("Value Offset", className="small"),
                    dbc.Input(
                        id="signal-props-offset",
                        type="number",
                        value=0.0,
                        step=0.1,
                        size="sm",
                        className="mb-2",
                    ),
                    html.Small("Add offset to signal values", className="text-muted"),
                ], width=6),
            ]),
            
            # Time Offset
            dbc.Row([
                dbc.Col([
                    dbc.Label("Time Offset (seconds)", className="small"),
                    dbc.Input(
                        id="signal-props-time-offset",
                        type="number",
                        value=0.0,
                        step=0.1,
                        size="sm",
                        className="mb-2",
                    ),
                    html.Small("Shift signal in time (positive = shift right)", className="text-muted"),
                ], width=6),
            ]),
            
            html.Hr(className="my-2"),
            
            # Signal Type toggle
            dbc.Row([
                dbc.Col([
                    dbc.Label("Signal Type", className="small fw-bold"),
                    dbc.RadioItems(
                        id="signal-props-type",
                        options=[
                            {"label": "📈 Regular Signal (continuous line)", "value": "normal"},
                            {"label": "📊 State Signal (vertical lines at transitions)", "value": "state"},
                        ],
                        value="normal",
                        className="mb-2",
                    ),
                    html.Small(
                        "State signals show vertical lines where the value changes, useful for digital/discrete signals.",
                        className="text-muted",
                    ),
                ], width=12),
            ]),
            
            # Hidden store for current signal key
            dcc.Store(id="signal-props-current-key", data=None),
        ]),
        dbc.ModalFooter([
            dbc.Button("Reset", id="btn-signal-props-reset", color="warning", size="sm", outline=True),
            dbc.Button("Cancel", id="btn-signal-props-cancel", color="secondary", size="sm"),
            dbc.Button("Apply", id="btn-signal-props-apply", color="primary", size="sm"),
        ]),
    ], id="modal-signal-props", size="md", is_open=False)


def create_compare_all_modal():
    """
    Create modal for comparing all common signals.
    
    Shows a ranked list of signals by difference (most different first),
    with color coding (red for large diff, green for small diff).
    """
    return dbc.Modal([
        dbc.ModalHeader("Compare All Common Signals"),
        dbc.ModalBody([
            html.P("Comparison results for all common signals, ranked by difference:", className="small text-muted"),
            
            # Legend
            html.Div([
                html.Span("⚠️ Red: > 10% diff", className="text-danger small me-3"),
                html.Span("⚡ Yellow: 5-10% diff", className="text-warning small me-3"),
                html.Span("✓ Green: < 5% diff", className="text-success small"),
            ], className="mb-3 p-2 bg-dark rounded"),
            
            # Results table (populated by callback)
            html.Div(id="compare-all-results", style={"maxHeight": "400px", "overflowY": "auto"}),
            
            # Export options
            html.Hr(className="my-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Actions:", className="small"),
                ], width=3),
                dbc.Col([
                    dbc.Button("Export Results as CSV", id="btn-compare-export-csv", 
                               color="info", size="sm", outline=True, className="me-2"),
                ], width="auto"),
            ]),
        ]),
        dbc.ModalFooter([
            dbc.Button("Close", id="btn-compare-all-close", color="secondary", size="sm"),
        ]),
        
        # Store for comparison data
        dcc.Store(id="store-compare-all-data", data={}),
        dcc.Download(id="download-compare-csv"),
    ], id="modal-compare-all", size="lg", is_open=False)
