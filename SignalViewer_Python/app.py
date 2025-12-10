"""
Signal Viewer Pro - Modern Signal Visualization Application
"""

import dash
from dash import dcc, html, Input, Output, State, callback_context, ALL

try:
    import dash_bootstrap_components as dbc
except ImportError:
    print("ERROR: pip install dash-bootstrap-components")
    raise

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import os
import base64
import json
from datetime import datetime

from data_manager import DataManager
from signal_operations import SignalOperationsManager
from linking_manager import LinkingManager

SIGNAL_COLORS = [
    "#2E86AB",
    "#A23B72",
    "#F18F01",
    "#C73E1D",
    "#3B1F2B",
    "#95C623",
    "#5E60CE",
    "#4EA8DE",
    "#48BFE3",
    "#64DFDF",
    "#72EFDD",
    "#80FFDB",
    "#E63946",
    "#F4A261",
    "#2A9D8F",
]

THEMES = {
    "dark": {
        "bg": "#1a1a2e",
        "card": "#16213e",
        "card_header": "#0f3460",
        "text": "#e8e8e8",
        "muted": "#aaa",
        "border": "#333",
        "input_bg": "#2a2a3e",
        "plot_bg": "#1a1a2e",
        "paper_bg": "#16213e",
        "grid": "#444",
        "checkbox_border": "#666",
        "checkbox_bg": "#2a2a3e",
        "accent": "#4ea8de",
        "button_bg": "#0f3460",
        "button_text": "#e8e8e8",
    },
    "light": {
        "bg": "#f0f2f5",
        "card": "#ffffff",
        "card_header": "#e3e7eb",
        "text": "#1a1a2e",
        "muted": "#5a6268",
        "border": "#ced4da",
        "input_bg": "#ffffff",
        "plot_bg": "#ffffff",
        "paper_bg": "#fafbfc",
        "grid": "#dee2e6",
        "checkbox_border": "#495057",
        "checkbox_bg": "#ffffff",
        "accent": "#2E86AB",
        "button_bg": "#e3e7eb",
        "button_text": "#1a1a2e",
    },
}


class SignalViewerApp:
    def __init__(self):
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.CYBORG, dbc.icons.FONT_AWESOME],
            external_scripts=[
                "https://unpkg.com/split.js@1.6.5/dist/split.min.js"
            ],
            suppress_callback_exceptions=True,
        )
        self.app.title = "Signal Viewer Pro"

        self.data_manager = DataManager(self)
        self.signal_operations = SignalOperationsManager(self)
        self.linking_manager = LinkingManager(self)

        self.derived_signals = {}
        self.signal_properties = {}

        self.app.layout = self.create_layout()
        self.setup_callbacks()

    def create_layout(self):
        return html.Div(
            id="app-container",
            style={
                "backgroundColor": "#1a1a2e",
                "minHeight": "100vh",
                "padding": "10px",
            },
            children=[
                # Stores
                dcc.Store(id="store-csv-files", data=[]),
                dcc.Store(id="store-assignments", data={"0": {"0": []}}),
                dcc.Store(id="store-layouts", data={"0": {"rows": 1, "cols": 1}}),
                dcc.Store(id="store-theme", data="dark"),
                dcc.Store(id="store-selected-subplot", data=0),
                dcc.Store(id="store-selected-tab", data=0),
                dcc.Store(id="store-num-tabs", data=1),
                dcc.Store(id="store-derived", data={}),
                dcc.Store(id="store-signal-props", data={}),
                dcc.Store(id="store-links", data=[]),
                dcc.Store(id="store-context-signal", data=None),
                dcc.Store(id="store-link-axes", data={}),
                dcc.Store(id="store-highlighted", data=[]),
                dcc.Store(id="store-refresh-trigger", data=0),
                dcc.Store(id="store-search-filters", data=[]),
                dcc.Store(id="store-cursor-x", data={"x": None, "initialized": False}),
                dcc.Store(id="store-subplot-modes", data={}),  # {tab: {subplot: "time"|"xy"}}
                dcc.Download(id="download-session"),
                dbc.Container(
                    [
                        # Header
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.H4(
                                        "📊 Signal Viewer Pro",
                                        className="text-primary fw-bold mb-0",
                                    ),
                                    width=6,
                                ),
                                dbc.Col(
                                    [
                                        html.Div(
                                            [
                                                html.Span("☀️", className="me-1"),
                                                dbc.Switch(
                                                    id="theme-switch",
                                                    value=True,
                                                    className="d-inline",
                                                ),
                                                html.Span("🌙", className="ms-1"),
                                                dbc.Badge(
                                                    id="status-badge",
                                                    children="Ready",
                                                    color="info",
                                                    className="ms-3",
                                                ),
                                            ],
                                            className="d-flex align-items-center justify-content-end",
                                        )
                                    ],
                                    width=6,
                                ),
                            ],
                            className="py-2 mb-2 border-bottom",
                        ),
                        # Split trigger store and interval
                        dcc.Store(id="store-split-init", data=False),
                        dcc.Interval(id="interval-split-init", interval=500, max_intervals=5),
                        # Main content - split layout
                        html.Div(
                            [
                                # Sidebar
                                html.Div(
                                    [
                                        # Panel 1: CSV Upload
                                        html.Div(
                                            [
                                                dbc.Card(
                                            [
                                                dbc.CardHeader(
                                                    [
                                                        html.Small(
                                                            "📁 Data Sources",
                                                            className="fw-bold",
                                                        ),
                                                        dbc.Button(
                                                            "Clear",
                                                            id="btn-clear-csv",
                                                            size="sm",
                                                            color="danger",
                                                            outline=True,
                                                            className="float-end py-0",
                                                            style={"fontSize": "10px"},
                                                        ),
                                                    ],
                                                    id="card-header-csv",
                                                    className="py-2",
                                                ),
                                                dbc.CardBody(
                                                    [
                                                        dcc.Upload(
                                                            id="upload-csv",
                                                            children=html.Div(
                                                                [
                                                                    html.I(
                                                                        className="fas fa-cloud-upload-alt me-2"
                                                                    ),
                                                                    "Drop/Click CSV",
                                                                ],
                                                                className="text-center",
                                                            ),
                                                            style={
                                                                "border": "2px dashed #4ea8de",
                                                                "borderRadius": "5px",
                                                                "padding": "12px",
                                                                "cursor": "pointer",
                                                            },
                                                            multiple=True,
                                                        ),
                                                        html.Div(
                                                            id="csv-list",
                                                            className="mt-2",
                                                            style={
                                                                "maxHeight": "80px",
                                                                "overflowY": "auto",
                                                            },
                                                        ),
                                                    ],
                                                    id="card-body-csv",
                                                    className="py-2",
                                                ),
                                                ],
                                                id="card-csv",
                                            ),
                                            ],
                                            id="split-panel-1",
                                            className="split-panel",
                                        ),
                                        # Panel 2: Signal Browser
                                        html.Div(
                                            [
                                                dbc.Card(
                                            [
                                                dbc.CardHeader(
                                                    [
                                                        html.Small(
                                                            "📶 Signals",
                                                            className="fw-bold",
                                                        ),
                                                        dbc.Button(
                                                            "🔗",
                                                            id="btn-link",
                                                            size="sm",
                                                            color="info",
                                                            outline=True,
                                                            title="Link CSVs",
                                                            className="float-end",
                                                        ),
                                                    ],
                                                    id="card-header-signals",
                                                    className="py-2",
                                                ),
                                                dbc.CardBody(
                                                    [
                                                        # Search with filter list
                                                        html.Div(
                                                            [
                                                                dbc.InputGroup(
                                                                    [
                                                                        dbc.Input(
                                                                            id="search-input",
                                                                            placeholder="Search...",
                                                                            size="sm",
                                                                        ),
                                                                        dbc.Button(
                                                                            "+",
                                                                            id="btn-add-filter",
                                                                            size="sm",
                                                                            color="success",
                                                                            outline=True,
                                                                            title="Add to filter list",
                                                                        ),
                                                                    ],
                                                                    size="sm",
                                                                ),
                                                                # Active filters display
                                                                html.Div(
                                                                    id="filter-list-display",
                                                                    className="mt-1",
                                                                    style={"fontSize": "10px"},
                                                                ),
                                                            ],
                                                            className="mb-2",
                                                        ),
                                                        html.Div(
                                                            [
                                                                html.Small(
                                                                    "Assign → ",
                                                                    className="text-muted",
                                                                ),
                                                                html.Span(
                                                                    id="target-info",
                                                                    className="text-info fw-bold small",
                                                                ),
                                                            ],
                                                            className="mb-1 p-1 rounded",
                                                            id="target-box",
                                                        ),
                                                        html.Div(
                                                            [
                                                                html.Small(
                                                                    "Selected for ops: ",
                                                                    className="text-muted",
                                                                ),
                                                                html.Span(
                                                                    id="highlight-count",
                                                                    children="0",
                                                                    className="text-warning fw-bold",
                                                                ),
                                                                dbc.Button(
                                                                    "⚙️ Operate",
                                                                    id="btn-operate-selected",
                                                                    size="sm",
                                                                    color="warning",
                                                                    outline=True,
                                                                    className="ms-2",
                                                                    style={
                                                                        "fontSize": "10px"
                                                                    },
                                                                ),
                                                                dbc.Button(
                                                                    "Clear",
                                                                    id="btn-clear-highlight",
                                                                    size="sm",
                                                                    color="secondary",
                                                                    outline=True,
                                                                    className="ms-1",
                                                                    style={
                                                                        "fontSize": "10px"
                                                                    },
                                                                ),
                                                            ],
                                                            className="mb-2",
                                                        ),
                                                        html.Div(
                                                            id="signal-tree",
                                                            children=[
                                                                html.Span(
                                                                    "Loading...",
                                                                    className="text-muted small",
                                                                )
                                                            ],
                                                            style={
                                                                "flex": "1",
                                                                "overflowY": "auto",
                                                            },
                                                        ),
                                                    ],
                                                    id="card-body-signals",
                                                    className="py-2",
                                                ),
                                            ],
                                                    id="card-signals",
                                                ),
                                            ],
                                            id="split-panel-2",
                                            className="split-panel",
                                        ),
                                        # Hidden elements for callback compatibility
                                        html.Div(
                                            [
                                                html.Div(
                                                    id="derived-list",
                                                    style={"display": "none"},
                                                ),
                                                html.Div(
                                                    id="btn-clear-derived",
                                                    style={"display": "none"},
                                                ),
                                            ],
                                            style={"display": "none"},
                                        ),
                                        # Panel 3: Assigned
                                        html.Div(
                                            [
                                                dbc.Card(
                                                    [
                                                        dbc.CardHeader(
                                                            html.Small(
                                                                "📋 Assigned",
                                                                className="fw-bold",
                                                            ),
                                                            id="card-header-assigned",
                                                            className="py-2",
                                                        ),
                                                        dbc.CardBody(
                                                            [
                                                                # Mode toggle: Time vs X-Y
                                                                html.Div(
                                                                    [
                                                                        dbc.RadioItems(
                                                                            id="subplot-mode-toggle",
                                                                            options=[
                                                                                {"label": "📈 Time", "value": "time"},
                                                                                {"label": "⚡ X-Y", "value": "xy"},
                                                                            ],
                                                                            value="time",
                                                                            inline=True,
                                                                            className="small",
                                                                        ),
                                                                    ],
                                                                    className="mb-2 text-center",
                                                                ),
                                                                # X-Y assignment controls (shown only in xy mode)
                                                                html.Div(
                                                                    [
                                                                        html.Div(
                                                                            [
                                                                                html.Small("X: ", className="text-info fw-bold"),
                                                                                html.Small(id="xy-x-signal", children="(none)", className="text-muted"),
                                                                            ],
                                                                            className="d-flex align-items-center",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Small("Y: ", className="text-warning fw-bold"),
                                                                                html.Small(id="xy-y-signal", children="(none)", className="text-muted"),
                                                                            ],
                                                                            className="d-flex align-items-center",
                                                                        ),
                                                                    ],
                                                                    id="xy-controls",
                                                                    style={"display": "none"},
                                                                    className="mb-2 border rounded p-1",
                                                                ),
                                                                html.Div(
                                                                    id="assigned-list",
                                                                    style={
                                                                        "overflowY": "auto",
                                                                        "flex": "1",
                                                                    },
                                                                ),
                                                                dbc.Button(
                                                                    "🗑️ Remove",
                                                                    id="btn-remove",
                                                                    size="sm",
                                                                    color="danger",
                                                                    className="w-100 mt-2",
                                                                ),
                                                            ],
                                                            id="card-body-assigned",
                                                            className="py-2",
                                                        ),
                                                    ],
                                                    id="card-assigned",
                                                ),
                                                html.Div(
                                                    id="status-text",
                                                    className="text-center small mt-1",
                                                    style={"fontSize": "10px"},
                                                ),
                                            ],
                                            id="split-panel-3",
                                            className="split-panel",
                                        ),
                                    ],
                                    id="split-sidebar",
                                    className="split-sidebar",
                                ),
                                # Plot Area
                                html.Div(
                                    [
                                        dbc.Card(
                                            [
                                                dbc.CardHeader(
                                                    [
                                                        dbc.Row(
                                                            [
                                                                dbc.Col(
                                                                    [
                                                                        dbc.ButtonGroup(
                                                                            [
                                                                                dbc.Button(
                                                                                    "+ Tab",
                                                                                    id="btn-add-tab",
                                                                                    size="sm",
                                                                                    color="primary",
                                                                                ),
                                                                                dbc.Button(
                                                                                    "- Tab",
                                                                                    id="btn-del-tab",
                                                                                    size="sm",
                                                                                    color="danger",
                                                                                ),
                                                                                dbc.Button(
                                                                                    "💾 Save",
                                                                                    id="btn-save",
                                                                                    size="sm",
                                                                                    color="success",
                                                                                    title="Save session to file",
                                                                                ),
                                                                                dcc.Upload(
                                                                                    id="upload-session",
                                                                                    children=dbc.Button(
                                                                                        "📂 Load",
                                                                                        size="sm",
                                                                                        color="info",
                                                                                        title="Load session from file",
                                                                                    ),
                                                                                    accept=".json",
                                                                                ),
                                                                                # Hidden btn-load for callback compatibility
                                                                                html.Div(
                                                                                    id="btn-load",
                                                                                    style={"display": "none"},
                                                                                ),
                                                                                dbc.Button(
                                                                                    "🔄",
                                                                                    id="btn-refresh",
                                                                                    size="sm",
                                                                                    color="secondary",
                                                                                    title="Refresh CSVs",
                                                                                ),
                                                                            ]
                                                                        )
                                                                    ],
                                                                    width=4,
                                                                ),
                                                                dbc.Col(
                                                                    [
                                                                        html.Div(
                                                                            [
                                                                                dbc.Input(
                                                                                    id="rows-input",
                                                                                    type="number",
                                                                                    value=1,
                                                                                    min=1,
                                                                                    max=4,
                                                                                    size="sm",
                                                                                    style={
                                                                                        "width": "40px",
                                                                                        "display": "inline-block",
                                                                                    },
                                                                                ),
                                                                                html.Span(
                                                                                    "×",
                                                                                    className="mx-1",
                                                                                ),
                                                                                dbc.Input(
                                                                                    id="cols-input",
                                                                                    type="number",
                                                                                    value=1,
                                                                                    min=1,
                                                                                    max=4,
                                                                                    size="sm",
                                                                                    style={
                                                                                        "width": "40px",
                                                                                        "display": "inline-block",
                                                                                    },
                                                                                ),
                                                                                # Hidden subplot selector (needed for callbacks)
                                                                                dbc.Select(
                                                                                    id="subplot-select",
                                                                                    style={"display": "none"},
                                                                                ),
                                                                                dbc.Input(
                                                                                    id="subplot-input",
                                                                                    type="number",
                                                                                    style={"display": "none"},
                                                                                ),
                                                                                dbc.Checkbox(
                                                                                    id="link-axes-check",
                                                                                    label="Link",
                                                                                    value=False,
                                                                                    className="ms-2 small",
                                                                                ),
                                                                                dbc.Checkbox(
                                                                                    id="time-cursor-check",
                                                                                    label="Cursor",
                                                                                    value=True,
                                                                                    className="ms-2 small",
                                                                                ),
                                                                            ],
                                                                            className="d-flex align-items-center justify-content-end",
                                                                        )
                                                                    ],
                                                                    width=8,
                                                                ),
                                                            ]
                                                        )
                                                    ],
                                                    id="card-header-plot",
                                                    className="py-2",
                                                ),
                                                dbc.CardBody(
                                                    [
                                                        dcc.Tabs(
                                                            id="tabs",
                                                            value="tab-0",
                                                            children=[
                                                                dcc.Tab(
                                                                    label="Tab 1",
                                                                    value="tab-0",
                                                                )
                                                            ],
                                                            className="mb-2",
                                                        ),
                                                        dcc.Graph(
                                                            id="plot",
                                                            figure={
                                                                "data": [],
                                                                "layout": {
                                                                    "xaxis": {
                                                                        "title": "Time"
                                                                    },
                                                                    "yaxis": {
                                                                        "title": "Value"
                                                                    },
                                                                    "template": "plotly_dark",
                                                                    "paper_bgcolor": "#16213e",
                                                                    "plot_bgcolor": "#1a1a2e",
                                                                    "font": {
                                                                        "color": "#e8e8e8"
                                                                    },
                                                                    "margin": {
                                                                        "l": 50,
                                                                        "r": 20,
                                                                        "t": 30,
                                                                        "b": 40,
                                                                    },
                                                                },
                                                            },
                                                            config={
                                                                "displayModeBar": True,
                                                                "displaylogo": False,
                                                            },
                                                            style={"height": "100%"},
                                                        ),
                                                    ],
                                                    id="card-body-plot",
                                                    className="p-2",
                                                ),
                                            ],
                                            id="card-plot",
                                        )
                                    ],
                                    id="split-plot",
                                    className="split-plot",
                                ),
                            ],
                            id="split-container",
                            className="split-container",
                        ),
                    ],
                    fluid=True,
                ),
                # Modals
                self.create_link_modal(),
                self.create_props_modal(),
                self.create_ops_modal(),
                self.create_multi_ops_modal(),
            ],
        )

    def create_link_modal(self):
        return dbc.Modal(
            [
                dbc.ModalHeader("🔗 Link CSV Files"),
                dbc.ModalBody(
                    [
                        html.P(
                            "Linked CSVs: same signal names auto-assign/unassign together",
                            className="small text-muted",
                        ),
                        dbc.Checklist(
                            id="link-checks", options=[], value=[], switch=True
                        ),
                        dbc.Input(
                            id="link-name",
                            placeholder="Group name",
                            size="sm",
                            className="mt-2",
                        ),
                    ]
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button(
                            "Create", id="btn-create-link", color="primary", size="sm"
                        ),
                        dbc.Button(
                            "Close", id="btn-close-link", color="secondary", size="sm"
                        ),
                    ]
                ),
            ],
            id="modal-link",
            is_open=False,
        )

    def create_props_modal(self):
        return dbc.Modal(
            [
                dbc.ModalHeader(id="props-title", children="Signal Properties"),
                dbc.ModalBody(
                    [
                        dbc.Label("Display Name:", className="small"),
                        dbc.Input(id="prop-name", size="sm", className="mb-2"),
                        dbc.Label("Scale Factor:", className="small"),
                        dbc.Input(
                            id="prop-scale",
                            type="number",
                            value=1.0,
                            size="sm",
                            className="mb-2",
                        ),
                        dbc.Label("Color:", className="small"),
                        dbc.Input(
                            id="prop-color",
                            type="color",
                            value="#2E86AB",
                            className="mb-2",
                            style={"height": "35px"},
                        ),
                        dbc.Label("Line Width:", className="small"),
                        dbc.Input(
                            id="prop-width",
                            type="number",
                            value=1.5,
                            min=0.5,
                            max=5,
                            step=0.5,
                            size="sm",
                        ),
                        dbc.Checkbox(
                            id="prop-apply-tree",
                            label="Show name in tree",
                            value=True,
                            className="mt-2",
                        ),
                        dbc.Checkbox(
                            id="prop-state-signal",
                            label="State signal (step display)",
                            value=False,
                            className="mt-2",
                        ),
                    ]
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button(
                            "Apply", id="btn-apply-props", color="primary", size="sm"
                        ),
                        dbc.Button(
                            "Close", id="btn-close-props", color="secondary", size="sm"
                        ),
                    ]
                ),
            ],
            id="modal-props",
            is_open=False,
        )

    def create_ops_modal(self):
        return dbc.Modal(
            [
                dbc.ModalHeader(id="ops-title", children="Signal Operation"),
                dbc.ModalBody(
                    [
                        dbc.Label("Operation:", className="small"),
                        dbc.Select(
                            id="op-type",
                            size="sm",
                            className="mb-2",
                            options=[
                                {"label": "∂ Derivative", "value": "derivative"},
                                {"label": "∫ Integral", "value": "integral"},
                                {"label": "|x| Absolute", "value": "abs"},
                                {"label": "√x Square Root", "value": "sqrt"},
                                {"label": "-x Negate", "value": "negate"},
                            ],
                            value="derivative",
                        ),
                        dbc.Label("Result Name:", className="small"),
                        dbc.Input(id="op-result-name", size="sm", className="mb-2"),
                    ]
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button(
                            "Compute", id="btn-compute-op", color="primary", size="sm"
                        ),
                        dbc.Button(
                            "Close", id="btn-close-ops", color="secondary", size="sm"
                        ),
                    ]
                ),
            ],
            id="modal-ops",
            is_open=False,
        )

    def create_multi_ops_modal(self):
        return dbc.Modal(
            [
                dbc.ModalHeader("⚙️ Operations on Selected Signals"),
                dbc.ModalBody(
                    [
                        html.Div(id="selected-signals-info", className="mb-2"),
                        dbc.Label("Operation:", className="small"),
                        dbc.Select(
                            id="multi-op-type",
                            size="sm",
                            className="mb-2",
                            options=[
                                {"label": "A + B", "value": "add"},
                                {"label": "A - B", "value": "sub"},
                                {"label": "A × B", "value": "mul"},
                                {"label": "A ÷ B", "value": "div"},
                                {"label": "||signals|| Norm", "value": "norm"},
                                {"label": "Mean", "value": "mean"},
                            ],
                            value="add",
                        ),
                        dbc.Label("Result Name:", className="small"),
                        dbc.Input(id="multi-op-name", size="sm", placeholder="result"),
                    ]
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button(
                            "Compute",
                            id="btn-compute-multi",
                            color="primary",
                            size="sm",
                        ),
                        dbc.Button(
                            "Close", id="btn-close-multi", color="secondary", size="sm"
                        ),
                    ]
                ),
            ],
            id="modal-multi-ops",
            is_open=False,
        )

    def create_figure(
        self,
        rows,
        cols,
        theme,
        selected_subplot=0,
        assignments=None,
        tab_key="0",
        link_axes=False,
        time_cursor=True,
        cursor_x=None,
        subplot_modes=None,  # {subplot_key: "time"|"xy"}
    ):
        colors = THEMES[theme]

        fig = make_subplots(
            rows=rows,
            cols=cols,
            subplot_titles=[f"Subplot {i+1}" for i in range(rows * cols)],
            vertical_spacing=0.18 if rows > 1 else 0.12,
            horizontal_spacing=0.15 if cols > 1 else 0.1,
            shared_xaxes=link_axes,
            shared_yaxes=link_axes,
        )

        # Calculate legend positions for each subplot
        legend_configs = {}
        for sp_idx in range(rows * cols):
            r = sp_idx // cols  # 0-indexed row
            c = sp_idx % cols  # 0-indexed col

            # Calculate x,y position for this subplot's legend
            # Each subplot gets a legend in its top-right corner
            x_start = c / cols
            x_end = (c + 1) / cols
            y_start = 1 - (r + 1) / rows
            y_end = 1 - r / rows

            legend_name = f"legend{sp_idx + 1}" if sp_idx > 0 else "legend"
            legend_configs[legend_name] = dict(
                bgcolor=colors["card"],
                bordercolor=colors["border"],
                font=dict(size=8),
                x=x_end - 0.02,
                y=y_end - 0.02,
                xanchor="right",
                yanchor="top",
                tracegroupgap=1,
                itemclick="toggle",
                itemdoubleclick="toggleothers",
            )

        fig.update_layout(
            paper_bgcolor=colors["paper_bg"],
            plot_bgcolor=colors["plot_bg"],
            font=dict(color=colors["text"], size=10),
            height=max(480, 240 * rows),
            showlegend=True,
            margin=dict(l=50, r=30, t=60, b=50),
            hovermode="closest",  # Always use closest, cursor is click-based
            hoverlabel=dict(
                bgcolor="rgba(0,0,0,0.8)",
                font_size=11,
                font_color="#e8e8e8",
            ),
            **legend_configs,
        )

        # Style each subplot - always show grid even if empty
        for i in range(rows * cols):
            r = i // cols + 1
            c = i % cols + 1

            border_color = "#4ea8de" if i == selected_subplot else colors["grid"]
            border_width = 2 if i == selected_subplot else 1

            # Add a small invisible trace to ensure axes are shown
            fig.add_trace(
                go.Scatter(
                    x=[0],
                    y=[0],
                    mode="markers",
                    marker=dict(size=1, opacity=0),
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=r,
                col=c,
            )

            fig.update_xaxes(
                gridcolor=colors["grid"],
                zerolinecolor=colors["border"],
                title_text="Time",
                title_font=dict(size=9),
                tickfont=dict(size=8),
                showline=True,
                linewidth=border_width,
                linecolor=border_color,
                mirror=True,
                showgrid=True,
                autorange=True,
                showspikes=False,  # Cursor is click-based, not hover-based
                row=r,
                col=c,
            )
            fig.update_yaxes(
                gridcolor=colors["grid"],
                zerolinecolor=colors["border"],
                title_text="Value",
                title_font=dict(size=9),
                tickfont=dict(size=8),
                showline=True,
                linewidth=border_width,
                linecolor=border_color,
                mirror=True,
                showgrid=True,
                autorange=True,
                row=r,
                col=c,
            )

        # Plot signals - each subplot gets its own legend group
        # Also collect signal data for cursor value display
        subplot_signal_data = {}  # {sp_idx: [(x_arr, y_arr, name, color), ...]}
        subplot_modes = subplot_modes or {}
        
        if assignments and tab_key in assignments:
            # First pass: collect all signal names to check for duplicates
            all_signal_names = []
            for sp_idx in range(rows * cols):
                sp_assignment = assignments.get(tab_key, {}).get(str(sp_idx), [])
                # Handle both list (time mode) and dict (xy mode) formats
                if isinstance(sp_assignment, list):
                    for sig in sp_assignment:
                        all_signal_names.append(sig.get("signal", ""))
                elif isinstance(sp_assignment, dict):
                    if "x" in sp_assignment:
                        all_signal_names.append(sp_assignment["x"].get("signal", ""))
                    if "y" in sp_assignment:
                        all_signal_names.append(sp_assignment["y"].get("signal", ""))
            # Find duplicate signal names
            duplicate_signals = set(n for n in all_signal_names if all_signal_names.count(n) > 1)
            
            color_idx = 0
            trace_idx = 0  # Unique trace counter for independent legend behavior
            for sp_idx in range(rows * cols):
                subplot_signal_data[sp_idx] = []
                sp_assignment = assignments.get(tab_key, {}).get(str(sp_idx), [])
                r = sp_idx // cols + 1
                c = sp_idx % cols + 1
                
                # Get subplot mode
                subplot_mode = subplot_modes.get(str(sp_idx), "time")
                
                # Handle X-Y mode
                if subplot_mode == "xy" and isinstance(sp_assignment, dict):
                    x_info = sp_assignment.get("x", {})
                    y_info = sp_assignment.get("y", {})
                    
                    if x_info and y_info:
                        # Get X signal data
                        x_csv_idx = x_info.get("csv_idx", -1)
                        x_signal_name = x_info.get("signal", "")
                        x_data = None
                        x_label = ""
                        
                        if x_csv_idx == -1 and x_signal_name in self.derived_signals:
                            ds = self.derived_signals[x_signal_name]
                            x_data = np.array(ds.get("data", []))
                            x_label = f"{x_signal_name} (D)"
                        elif x_csv_idx >= 0 and x_csv_idx < len(self.data_manager.data_tables):
                            df = self.data_manager.data_tables[x_csv_idx]
                            if df is not None and x_signal_name in df.columns:
                                x_data = df[x_signal_name].values
                                if x_csv_idx < len(self.data_manager.csv_file_paths):
                                    csv_path = self.data_manager.csv_file_paths[x_csv_idx]
                                    csv_label = os.path.splitext(os.path.basename(csv_path))[0]
                                else:
                                    csv_label = f"C{x_csv_idx+1}"
                                x_label = f"{x_signal_name} ({csv_label})"
                        
                        # Get Y signal data
                        y_csv_idx = y_info.get("csv_idx", -1)
                        y_signal_name = y_info.get("signal", "")
                        y_data = None
                        y_label = ""
                        
                        if y_csv_idx == -1 and y_signal_name in self.derived_signals:
                            ds = self.derived_signals[y_signal_name]
                            y_data = np.array(ds.get("data", []))
                            y_label = f"{y_signal_name} (D)"
                        elif y_csv_idx >= 0 and y_csv_idx < len(self.data_manager.data_tables):
                            df = self.data_manager.data_tables[y_csv_idx]
                            if df is not None and y_signal_name in df.columns:
                                y_data = df[y_signal_name].values
                                if y_csv_idx < len(self.data_manager.csv_file_paths):
                                    csv_path = self.data_manager.csv_file_paths[y_csv_idx]
                                    csv_label = os.path.splitext(os.path.basename(csv_path))[0]
                                else:
                                    csv_label = f"C{y_csv_idx+1}"
                                y_label = f"{y_signal_name} ({csv_label})"
                        
                        if x_data is not None and y_data is not None:
                            # Ensure same length
                            min_len = min(len(x_data), len(y_data))
                            x_data = x_data[:min_len]
                            y_data = y_data[:min_len]
                            
                            legend_ref = f"legend{sp_idx + 1}" if sp_idx > 0 else "legend"
                            unique_legend_group = f"trace_{trace_idx}"
                            color = SIGNAL_COLORS[color_idx % len(SIGNAL_COLORS)]
                            
                            fig.add_trace(
                                go.Scatter(
                                    x=x_data,
                                    y=y_data,
                                    mode="lines+markers",
                                    name=f"{y_label} vs {x_label}",
                                    line=dict(color=color, width=1.5),
                                    marker=dict(size=3, color=color),
                                    legendgroup=unique_legend_group,
                                    showlegend=True,
                                    legend=legend_ref,
                                ),
                                row=r,
                                col=c,
                            )
                            
                            # Update axis labels for X-Y mode
                            fig.update_xaxes(title_text=x_label, row=r, col=c)
                            fig.update_yaxes(title_text=y_label, row=r, col=c)
                            
                            subplot_signal_data[sp_idx].append((x_data, y_data, f"{y_label} vs {x_label}", color))
                            trace_idx += 1
                            color_idx += 1
                    continue  # Skip to next subplot
                
                # Time mode: process list of signals
                sp_signals = sp_assignment if isinstance(sp_assignment, list) else []

                for sig in sp_signals:
                    csv_idx = sig.get("csv_idx", -1)
                    signal_name = sig.get("signal", "")
                    is_state_signal = sig.get("is_state", False)

                    if csv_idx == -1 and signal_name in self.derived_signals:
                        ds = self.derived_signals[signal_name]
                        x_data = ds.get("time", [])
                        y_data = ds.get("data", [])
                        csv_label = "D"  # Derived
                    elif csv_idx >= 0 and csv_idx < len(self.data_manager.data_tables):
                        df = self.data_manager.data_tables[csv_idx]
                        if df is not None and signal_name in df.columns:
                            time_col = "Time" if "Time" in df.columns else df.columns[0]
                            x_data = df[time_col].values
                            y_data = df[signal_name].values
                            # Get CSV filename for legend
                            if csv_idx < len(self.data_manager.csv_file_paths):
                                csv_path = self.data_manager.csv_file_paths[csv_idx]
                                csv_label = os.path.splitext(
                                    os.path.basename(csv_path)
                                )[0]
                            else:
                                csv_label = f"C{csv_idx+1}"
                        else:
                            continue
                    else:
                        continue

                    prop_key = f"{csv_idx}:{signal_name}"
                    props = self.signal_properties.get(prop_key, {})
                    color = props.get(
                        "color", SIGNAL_COLORS[color_idx % len(SIGNAL_COLORS)]
                    )
                    width = props.get("width", 1.5)
                    scale = props.get("scale", 1.0)
                    display_name = props.get("display_name", signal_name)
                    is_state_signal = props.get("is_state", is_state_signal)

                    # Build legend name: format as "signal (csv_name)"
                    legend_name = f"{display_name} ({csv_label})"

                    y_scaled = np.array(y_data) * scale
                    x_arr = np.array(x_data)
                    
                    # Collect signal data for cursor value display
                    subplot_signal_data[sp_idx].append((x_arr, y_scaled, legend_name, color))

                    # Assign trace to this subplot's legend
                    legend_ref = f"legend{sp_idx + 1}" if sp_idx > 0 else "legend"
                    # Unique legendgroup for each trace so clicking hides only that trace
                    unique_legend_group = f"trace_{trace_idx}"
                    
                    if is_state_signal:
                        # State signal: draw vertical lines at value changes
                        # Find indices where value changes
                        changes = np.where(np.diff(y_scaled) != 0)[0] + 1
                        
                        # Add first visible indicator as a scatter point
                        first_shown = True
                        for change_idx in changes:
                            if change_idx < len(x_arr):
                                # Draw vertical line using shape
                                fig.add_vline(
                                    x=x_arr[change_idx],
                                    line=dict(color=color, width=width, dash="solid"),
                                    row=r,
                                    col=c,
                                )
                        
                        # Add invisible trace for legend
                        fig.add_trace(
                            go.Scatter(
                                x=[None],
                                y=[None],
                                mode="lines",
                                name=f"{legend_name} (state)",
                                line=dict(color=color, width=width),
                                legendgroup=unique_legend_group,
                                showlegend=True,
                                legend=legend_ref,
                            ),
                            row=r,
                            col=c,
                        )
                    else:
                        # Regular signal: normal line plot
                        fig.add_trace(
                            go.Scatter(
                                x=x_arr,
                                y=y_scaled,
                                mode="lines",
                                name=legend_name,
                                line=dict(color=color, width=width),
                                legendgroup=unique_legend_group,
                                showlegend=True,
                                legend=legend_ref,
                            ),
                            row=r,
                            col=c,
                        )
                    trace_idx += 1
                    color_idx += 1

        # Add time cursor vertical lines to all subplots with signal values
        if time_cursor and cursor_x is not None:
            for sp_idx in range(rows * cols):
                r = sp_idx // cols + 1
                c = sp_idx % cols + 1
                
                # Get axis references for this subplot
                xref = f"x{sp_idx + 1}" if sp_idx > 0 else "x"
                yref = f"y{sp_idx + 1} domain" if sp_idx > 0 else "y domain"
                yref_data = f"y{sp_idx + 1}" if sp_idx > 0 else "y"
                
                fig.add_shape(
                    type="line",
                    x0=cursor_x,
                    x1=cursor_x,
                    y0=0,
                    y1=1,
                    xref=xref,
                    yref=yref,
                    line=dict(color="#ff6b6b", width=2, dash="solid"),
                )
                
                # Build cursor info text with signal values
                cursor_text_lines = [f"t={cursor_x:.4f}"]
                
                # Get signal values at cursor position for this subplot
                if sp_idx in subplot_signal_data:
                    for x_arr, y_arr, sig_name, sig_color in subplot_signal_data[sp_idx]:
                        if len(x_arr) > 0 and len(y_arr) > 0:
                            # Interpolate value at cursor_x
                            try:
                                val = np.interp(cursor_x, x_arr, y_arr)
                                cursor_text_lines.append(f"{sig_name}: {val:.4f}")
                            except:
                                pass
                
                cursor_text = "<br>".join(cursor_text_lines)
                
                # Add annotation with time and signal values
                fig.add_annotation(
                    x=cursor_x,
                    y=1,
                    xref=xref,
                    yref=yref,
                    text=cursor_text,
                    showarrow=False,
                    bgcolor="rgba(40, 40, 40, 0.9)",
                    font=dict(color="white", size=9),
                    align="left",
                    yshift=10,
                    bordercolor="#ff6b6b",
                    borderwidth=1,
                    borderpad=4,
                )

        return fig

    def setup_callbacks(self):
        print("DEBUG: Setting up callbacks...")

        # Theme toggle
        @self.app.callback(
            [
                Output("app-container", "style"),
                Output("card-csv", "style"),
                Output("card-header-csv", "style"),
                Output("card-body-csv", "style"),
                Output("card-signals", "style"),
                Output("card-header-signals", "style"),
                Output("card-body-signals", "style"),
                Output("card-assigned", "style"),
                Output("card-header-assigned", "style"),
                Output("card-body-assigned", "style"),
                Output("card-plot", "style"),
                Output("card-header-plot", "style"),
                Output("card-body-plot", "style"),
                Output("target-box", "style"),
                Output("search-input", "style"),
                Output("store-theme", "data"),
            ],
            Input("theme-switch", "value"),
        )
        def update_theme(is_dark):
            theme = "dark" if is_dark else "light"
            c = THEMES[theme]
            card = {"backgroundColor": c["card"], "borderColor": c["border"]}
            header = {
                "backgroundColor": c["card_header"],
                "borderColor": c["border"],
                "color": c["text"],
            }
            body = {"backgroundColor": c["card"], "color": c["text"]}
            
            return (
                {
                    "backgroundColor": c["bg"],
                    "minHeight": "100vh",
                    "padding": "10px",
                    "color": c["text"],
                },
                card,
                header,
                body,
                card,
                header,
                body,
                card,
                header,
                body,
                card,
                header,
                body,
                {
                    "backgroundColor": c["input_bg"],
                    "borderColor": c["border"],
                    "padding": "5px",
                    "borderRadius": "4px",
                },
                {
                    "backgroundColor": c["input_bg"],
                    "borderColor": c["border"],
                    "color": c["text"],
                },
                theme,
            )

        # CSV Upload & Refresh
        @self.app.callback(
            [
                Output("store-csv-files", "data", allow_duplicate=True),
                Output("csv-list", "children"),
                Output("status-text", "children", allow_duplicate=True),
                Output("store-refresh-trigger", "data"),
                Output("store-assignments", "data", allow_duplicate=True),
            ],
            [
                Input("upload-csv", "contents"),
                Input("btn-clear-csv", "n_clicks"),
                Input({"type": "del-csv", "idx": ALL}, "n_clicks"),
                Input("btn-refresh", "n_clicks"),
            ],
            [
                State("upload-csv", "filename"),
                State("store-csv-files", "data"),
                State("store-refresh-trigger", "data"),
                State("store-assignments", "data"),
            ],
            prevent_initial_call=True,
        )
        def handle_csv(
            contents,
            clear_click,
            del_clicks,
            refresh_click,
            filenames,
            files,
            refresh_counter,
            assignments,
        ):
            ctx = callback_context
            trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
            files = files or []
            refresh_counter = refresh_counter or 0
            assignments = assignments or {}

            if "btn-clear-csv" in trigger:
                self.data_manager.csv_file_paths = []
                self.data_manager.data_tables = []
                # Clear all assignments when clearing CSV files
                return [], [], "Cleared", refresh_counter + 1, {"0": {"0": []}}

            if "btn-refresh" in trigger:
                for i in range(len(files)):
                    self.data_manager.last_read_rows[i] = 0
                    self.data_manager.data_tables[i] = None
                    self.data_manager.read_initial_data(i)
                new_derived = {}
                for name, ds in self.derived_signals.items():
                    source = ds.get("source", "")
                    op = ds.get("op", "derivative")
                    time_data, sig_data = None, None
                    for csv_idx, df in enumerate(self.data_manager.data_tables):
                        if df is not None and source in df.columns:
                            time_col = "Time" if "Time" in df.columns else df.columns[0]
                            time_data = df[time_col].values
                            sig_data = df[source].values
                            break
                    if time_data is not None:
                        try:
                            if op == "derivative":
                                result = np.gradient(sig_data, time_data)
                            elif op == "integral":
                                result = np.cumsum(sig_data) * np.mean(
                                    np.diff(time_data)
                                )
                            elif op == "abs":
                                result = np.abs(sig_data)
                            elif op == "sqrt":
                                result = np.sqrt(np.abs(sig_data))
                            elif op == "negate":
                                result = -sig_data
                            else:
                                result = sig_data
                            new_derived[name] = {
                                "time": time_data.tolist(),
                                "data": result.tolist(),
                                "source": source,
                                "op": op,
                            }
                        except:
                            pass
                self.derived_signals = new_derived
                return files, dash.no_update, "✅ Refreshed", refresh_counter + 1, dash.no_update

            if "del-csv" in trigger:
                for i, n in enumerate(del_clicks or []):
                    if n and i < len(files):
                        files.pop(i)
                        if i < len(self.data_manager.data_tables):
                            self.data_manager.data_tables.pop(i)
                        self.data_manager.csv_file_paths = files
                        refresh_counter = refresh_counter + 1
                        break

            if "upload-csv" in trigger and contents:
                if not isinstance(contents, list):
                    contents = [contents]
                if not isinstance(filenames, list):
                    filenames = [filenames]

                for content, fname in zip(contents, filenames):
                    if content is None or fname is None:
                        continue
                    os.makedirs("temp", exist_ok=True)
                    
                    # Generate unique path if filename already exists
                    base_name, ext = os.path.splitext(fname)
                    path = os.path.join("temp", fname)
                    counter = 1
                    while path in files or os.path.exists(path):
                        path = os.path.join("temp", f"{base_name}_{counter}{ext}")
                        counter += 1
                    
                    try:
                        decoded = base64.b64decode(content.split(",")[1])
                        with open(path, "wb") as f:
                            f.write(decoded)
                        if path not in files:
                            files.append(path)
                    except Exception as e:
                        print(f"Error loading {fname}: {e}")

                self.data_manager.csv_file_paths = files
                while len(self.data_manager.data_tables) < len(files):
                    self.data_manager.data_tables.append(None)
                    self.data_manager.last_read_rows.append(0)

                for i in range(len(files)):
                    if self.data_manager.data_tables[i] is None:
                        try:
                            self.data_manager.read_initial_data(i)
                            print(
                                f"DEBUG: Loaded CSV {i}: {files[i]}, columns: {list(self.data_manager.data_tables[i].columns) if self.data_manager.data_tables[i] is not None else 'None'}"
                            )
                        except Exception as e:
                            print(f"Error reading {files[i]}: {e}")

                # Increment refresh trigger to update tree
                refresh_counter = refresh_counter + 1
                print(
                    f"DEBUG: CSV files loaded, refresh_counter={refresh_counter}, files={files}"
                )

            items = [
                html.Div(
                    [
                        html.I(
                            className="fas fa-file me-1", style={"color": "#f4a261"}
                        ),
                        html.Span(os.path.basename(f), style={"fontSize": "10px"}),
                        html.A(
                            "×",
                            id={"type": "del-csv", "idx": i},
                            className="float-end text-danger",
                            style={"cursor": "pointer"},
                        ),
                    ],
                    className="py-1",
                )
                for i, f in enumerate(files)
            ]
            return files, items, f"{len(files)} CSV(s)", refresh_counter, dash.no_update

        # Search filter list management
        @self.app.callback(
            [
                Output("store-search-filters", "data"),
                Output("filter-list-display", "children"),
                Output("search-input", "value", allow_duplicate=True),
            ],
            [
                Input("btn-add-filter", "n_clicks"),
                Input({"type": "remove-filter", "idx": ALL}, "n_clicks"),
            ],
            [
                State("search-input", "value"),
                State("store-search-filters", "data"),
            ],
            prevent_initial_call=True,
        )
        def manage_filters(add_click, remove_clicks, search_value, filters):
            from dash import ctx
            filters = filters or []
            
            if ctx.triggered_id == "btn-add-filter" and add_click:
                # Add current search to filter list
                if search_value and search_value.strip() and search_value.strip() not in filters:
                    filters.append(search_value.strip())
            
            elif isinstance(ctx.triggered_id, dict) and ctx.triggered_id.get("type") == "remove-filter":
                # Remove filter by index
                idx = ctx.triggered_id.get("idx")
                if idx is not None and 0 <= idx < len(filters):
                    filters.pop(idx)
            
            # Build filter display
            if filters:
                filter_badges = [
                    dbc.Badge(
                        [
                            f,
                            html.Span(
                                " ×",
                                id={"type": "remove-filter", "idx": i},
                                style={"cursor": "pointer", "marginLeft": "5px"},
                            ),
                        ],
                        color="info",
                        className="me-1 mb-1",
                        style={"fontSize": "9px"},
                    )
                    for i, f in enumerate(filters)
                ]
                display = html.Div(
                    [
                        html.Small("Filters: ", className="text-muted"),
                        html.Span(filter_badges),
                    ]
                )
            else:
                display = html.Small("No active filters", className="text-muted")
            
            # Clear search input after adding
            clear_input = "" if ctx.triggered_id == "btn-add-filter" else dash.no_update
            
            return filters, display, clear_input

        # Signal tree with highlight selection - updates when subplot changes
        @self.app.callback(
            [
                Output("signal-tree", "children"),
                Output("target-info", "children"),
                Output("highlight-count", "children"),
            ],
            [
                Input("store-csv-files", "data"),
                Input("search-input", "value"),
                Input("store-selected-tab", "data"),
                Input("store-selected-subplot", "data"),
                Input("store-assignments", "data"),
                Input("store-links", "data"),
                Input("store-signal-props", "data"),
                Input("store-highlighted", "data"),
                Input("store-refresh-trigger", "data"),
                Input("subplot-select", "value"),
                Input("store-derived", "data"),
                Input("store-search-filters", "data"),
            ],
            prevent_initial_call=False,
        )
        def update_tree(
            files,
            search,
            tab,
            subplot,
            assignments,
            links,
            props,
            highlighted,
            refresh_trigger,
            subplot_dropdown,
            derived,
            search_filters,
        ):
            try:
                print(
                    f"DEBUG: update_tree called - files={files}, refresh_trigger={refresh_trigger}, csv_file_paths={self.data_manager.csv_file_paths}"
                )

                # Use dropdown value if available, otherwise use store
                if subplot_dropdown is not None:
                    subplot = int(subplot_dropdown)
                else:
                    subplot = subplot or 0
                tab = tab or 0
                target = f"Tab {tab+1}, Sub {subplot+1}"
                highlighted = highlighted or []

                assigned = set()
                if assignments:
                    for s in assignments.get(str(tab), {}).get(str(subplot), []):
                        assigned.add(f"{s['csv_idx']}:{s['signal']}")

                linked_csvs = {}
                for lg in links or []:
                    for idx in lg.get("csv_indices", []):
                        linked_csvs[idx] = lg.get("name", "L")

                tree = []
                search = (search or "").lower()
                props = props or {}

                # Use files from store if available, otherwise use data_manager
                csv_files = files if files else self.data_manager.csv_file_paths
                print(
                    f"DEBUG: Using csv_files={csv_files}, data_tables length={len(self.data_manager.data_tables)}"
                )

                # Check for duplicate filenames to determine display names
                basenames = [os.path.basename(fp) for fp in csv_files]
                duplicate_names = set(n for n in basenames if basenames.count(n) > 1)

                def get_display_name(fp):
                    """Get display name - include folder if filename is duplicate"""
                    basename = os.path.basename(fp)
                    if basename in duplicate_names:
                        # Include parent folder
                        parent = os.path.basename(os.path.dirname(fp))
                        return f"{parent}/{basename}" if parent else basename
                    return basename

                for csv_idx, fp in enumerate(csv_files):
                    print(f"DEBUG: Processing CSV {csv_idx}: {fp}")
                    while len(self.data_manager.data_tables) <= csv_idx:
                        self.data_manager.data_tables.append(None)

                    if self.data_manager.data_tables[csv_idx] is None:
                        try:
                            if os.path.exists(fp):
                                print(f"DEBUG: Reading initial data for CSV {csv_idx}")
                                self.data_manager.read_initial_data(csv_idx)
                        except Exception as e:
                            print(f"DEBUG: Error reading CSV {csv_idx}: {e}")
                            continue

                    df = self.data_manager.data_tables[csv_idx]
                    if df is None or df.empty:
                        print(f"DEBUG: CSV {csv_idx} is None or empty")
                        continue

                    fname = get_display_name(fp)
                    signals = [c for c in df.columns if c.lower() != "time"]
                    print(f"DEBUG: CSV {csv_idx} has signals: {signals}")
                    
                    # Apply search filters (filter list OR current search)
                    active_filters = list(search_filters or [])
                    if search and search.strip():
                        active_filters.append(search.strip())
                    
                    if active_filters:
                        # Signal must match at least one filter
                        filtered_signals = []
                        for sig in signals:
                            sig_lower = sig.lower()
                            if any(f.lower() in sig_lower for f in active_filters):
                                filtered_signals.append(sig)
                        signals = filtered_signals
                    
                    if not signals:
                        print(
                            f"DEBUG: No signals after search filter for CSV {csv_idx}"
                        )
                        continue

                    link_badge = (
                        dbc.Badge(
                            "🔗",
                            color="info",
                            className="ms-1",
                            pill=True,
                            style={"fontSize": "8px"},
                        )
                        if csv_idx in linked_csvs
                        else ""
                    )

                    sig_items = []
                    for sig in signals:
                        key = f"{csv_idx}:{sig}"
                        is_assigned = key in assigned
                        is_highlighted = key in highlighted
                        p = props.get(key, {})
                        display = (
                            p.get("display_name", sig)
                            if p.get("show_in_tree", True)
                            else sig
                        )

                        sig_items.append(
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            dbc.Checkbox(
                                                id={
                                                    "type": "sig-check",
                                                    "csv": csv_idx,
                                                    "sig": sig,
                                                },
                                                value=is_assigned,
                                                className="d-inline me-1",
                                                label="",
                                            ),
                                            html.Small(
                                                "📊",
                                                className="text-muted me-1",
                                                style={"fontSize": "8px"},
                                                title="Assign to subplot",
                                            ),
                                            dbc.Checkbox(
                                                id={
                                                    "type": "sig-highlight",
                                                    "csv": csv_idx,
                                                    "sig": sig,
                                                },
                                                value=is_highlighted,
                                                className="d-inline me-1",
                                                style={"accentColor": "#f4a261"},
                                                label="",
                                            ),
                                            html.Small(
                                                "⚙",
                                                className="text-warning me-2",
                                                style={"fontSize": "8px"},
                                                title="Select for operations",
                                            ),
                                            html.Span(
                                                display,
                                                style={
                                                    "fontSize": "10px",
                                                    "flex": "1",
                                                    "minWidth": "0",
                                                },
                                                className="me-2",
                                            ),
                                        ],
                                        className="d-flex align-items-center",
                                        style={"flex": "1", "minWidth": "0"},
                                    ),
                                    html.Div(
                                        [
                                            dbc.Button(
                                                "⚙",
                                                id={
                                                    "type": "sig-ops",
                                                    "csv": csv_idx,
                                                    "sig": sig,
                                                },
                                                size="sm",
                                                color="link",
                                                className="p-0 me-1",
                                                style={
                                                    "fontSize": "9px",
                                                    "lineHeight": "1",
                                                },
                                                title="Single operation",
                                            ),
                                            dbc.Button(
                                                "✎",
                                                id={
                                                    "type": "sig-props",
                                                    "csv": csv_idx,
                                                    "sig": sig,
                                                },
                                                size="sm",
                                                color="link",
                                                className="p-0",
                                                style={
                                                    "fontSize": "9px",
                                                    "lineHeight": "1",
                                                },
                                                title="Properties",
                                            ),
                                        ],
                                        className="d-flex align-items-center",
                                        style={"flexShrink": "0"},
                                    ),
                                ],
                                className="ms-2 py-1 px-1 d-flex justify-content-between align-items-center",
                                style={
                                    "backgroundColor": (
                                        "rgba(244,162,97,0.2)"
                                        if is_highlighted
                                        else "transparent"
                                    ),
                                    "borderRadius": "3px",
                                    "marginBottom": "2px",
                                },
                            )
                        )

                    tree.append(
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.I(
                                            className="fas fa-folder-open me-1",
                                            style={"color": "#f4a261"},
                                        ),
                                        html.Strong(fname, style={"fontSize": "10px"}),
                                        link_badge,
                                    ]
                                ),
                                html.Div(sig_items),
                            ],
                            className="mb-2 p-1 rounded",
                        )
                    )

                # Derived signals - with both checkboxes and operations
                derived = derived or {}
                if derived:
                    derived_items = []
                    for name in derived:
                        key = f"-1:{name}"
                        is_assigned = key in assigned
                        is_highlighted = key in highlighted
                        derived_items.append(
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            dbc.Checkbox(
                                                id={
                                                    "type": "sig-check",
                                                    "csv": -1,
                                                    "sig": name,
                                                },
                                                value=is_assigned,
                                                className="d-inline me-1",
                                                label="",
                                            ),
                                            html.Small(
                                                "📊",
                                                className="text-muted me-1",
                                                style={"fontSize": "8px"},
                                                title="Assign to subplot",
                                            ),
                                            dbc.Checkbox(
                                                id={
                                                    "type": "sig-highlight",
                                                    "csv": -1,
                                                    "sig": name,
                                                },
                                                value=is_highlighted,
                                                className="d-inline me-1",
                                                style={"accentColor": "#f4a261"},
                                                label="",
                                            ),
                                            html.Small(
                                                "⚙",
                                                className="text-warning me-2",
                                                style={"fontSize": "8px"},
                                                title="Select for operations",
                                            ),
                                            html.Span(
                                                f"📐 {name}",
                                                style={
                                                    "fontSize": "10px",
                                                    "flex": "1",
                                                    "minWidth": "0",
                                                },
                                                className="me-2",
                                            ),
                                        ],
                                        className="d-flex align-items-center",
                                        style={"flex": "1", "minWidth": "0"},
                                    ),
                                    html.Div(
                                        [
                                            dbc.Button(
                                                "⚙",
                                                id={
                                                    "type": "sig-ops",
                                                    "csv": -1,
                                                    "sig": name,
                                                },
                                                size="sm",
                                                color="link",
                                                className="p-0 me-1",
                                                style={
                                                    "fontSize": "9px",
                                                    "lineHeight": "1",
                                                },
                                                title="Single operation",
                                            ),
                                            dbc.Button(
                                                "✎",
                                                id={
                                                    "type": "sig-props",
                                                    "csv": -1,
                                                    "sig": name,
                                                },
                                                size="sm",
                                                color="link",
                                                className="p-0 me-1",
                                                style={
                                                    "fontSize": "9px",
                                                    "lineHeight": "1",
                                                },
                                                title="Properties",
                                            ),
                                            dbc.Button(
                                                "×",
                                                id={
                                                    "type": "del-derived",
                                                    "name": name,
                                                },
                                                size="sm",
                                                color="link",
                                                className="p-0 text-danger",
                                                style={
                                                    "fontSize": "10px",
                                                    "lineHeight": "1",
                                                },
                                                title="Delete",
                                            ),
                                        ],
                                        className="d-flex align-items-center",
                                        style={"flexShrink": "0"},
                                    ),
                                ],
                                className="ms-2 py-1 px-1 d-flex justify-content-between align-items-center",
                                style={
                                    "backgroundColor": (
                                        "rgba(244,162,97,0.2)"
                                        if is_highlighted
                                        else "transparent"
                                    )
                                },
                            )
                        )

                    # Add the Derived node to tree (OUTSIDE the for loop)
                    if derived_items:
                        tree.append(
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.I(
                                                className="fas fa-calculator me-1",
                                                style={"color": "#52b788"},
                                            ),
                                            html.Strong(
                                                "Derived", style={"fontSize": "11px"}
                                            ),
                                        ]
                                    ),
                                    html.Div(derived_items),
                                ],
                                className="mb-2 p-1 rounded",
                            )
                        )

                if not tree:
                    # Show helpful message when no signals
                    tree = [
                        html.Div(
                            [
                                html.I(
                                    className="fas fa-info-circle me-2",
                                    style={"color": "#4ea8de"},
                                ),
                                html.Span(
                                    "Upload CSV files to see signals",
                                    className="text-muted small",
                                ),
                            ],
                            className="p-2",
                        )
                    ]
                    if csv_files:
                        tree.append(
                            html.Small(
                                f"({len(csv_files)} files loaded but no signals found)",
                                className="text-warning d-block mt-1",
                            )
                        )
                        # Show more debug info
                        for i, fp in enumerate(csv_files):
                            has_data = (
                                i < len(self.data_manager.data_tables)
                                and self.data_manager.data_tables[i] is not None
                            )
                            status = "✓" if has_data else "✗"
                            tree.append(
                                html.Small(
                                    f"  {status} {os.path.basename(fp)}",
                                    className="text-muted d-block",
                                )
                            )

                print(
                    f"DEBUG: Returning tree with {len(tree)} items, csv_files={len(csv_files) if csv_files else 0}"
                )
                return tree, target, str(len(highlighted))
            except Exception as e:
                print(f"ERROR in update_tree: {e}")
                import traceback

                traceback.print_exc()
                return (
                    [
                        html.Span(
                            f"Error: {str(e)}", className="text-danger small d-block"
                        ),
                        html.Small(
                            "Check console for details", className="text-muted d-block"
                        ),
                    ],
                    "Error",
                    "0",
                )

        # Handle highlighting for operations
        @self.app.callback(
            Output("store-highlighted", "data"),
            [
                Input({"type": "sig-highlight", "csv": ALL, "sig": ALL}, "value"),
                Input("btn-clear-highlight", "n_clicks"),
            ],
            [
                State({"type": "sig-highlight", "csv": ALL, "sig": ALL}, "id"),
                State("store-highlighted", "data"),
            ],
            prevent_initial_call=True,
        )
        def handle_highlight(vals, clear_click, ids, current):
            ctx = callback_context
            trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

            if "btn-clear-highlight" in trigger:
                return []

            highlighted = []
            if vals and ids:
                for val, id_dict in zip(vals, ids):
                    if val:
                        highlighted.append(f"{id_dict['csv']}:{id_dict['sig']}")
            return highlighted

        # Derived signals list (in Derived card) - simple list with delete buttons
        # Full controls (checkboxes, ops, edit) are in the signal tree
        @self.app.callback(
            Output("derived-list", "children"),
            [Input("store-derived", "data")],
            prevent_initial_call=False,
        )
        def update_derived_list(derived):
            if not derived:
                return [
                    html.Span(
                        "None - use signal operations to create",
                        className="text-muted small",
                    )
                ]

            # Just show names - delete functionality is in the signal tree
            items = []
            for name in derived.keys():
                items.append(
                    html.Div(
                        [
                            html.Span(f"📐 {name}", style={"fontSize": "10px"}),
                        ],
                        className="py-1",
                    )
                )
            return items

        # Delete derived signal (from tree or clear all button)
        @self.app.callback(
            [
                Output("store-derived", "data", allow_duplicate=True),
                Output("store-assignments", "data", allow_duplicate=True),
                Output("status-text", "children", allow_duplicate=True),
            ],
            [
                Input({"type": "del-derived", "name": ALL}, "n_clicks"),
                Input("btn-clear-derived", "n_clicks"),
            ],
            [
                State("store-derived", "data"),
                State("store-assignments", "data"),
            ],
            prevent_initial_call=True,
        )
        def delete_derived(del_clicks_tree, clear_click, derived, assignments):
            derived = derived or {}
            assignments = assignments or {}

            # Use triggered_id for pattern-matching callbacks (Dash 2.x)
            from dash import ctx

            if not ctx.triggered_id:
                return dash.no_update, dash.no_update, dash.no_update

            def remove_from_assignments(signal_name):
                """Remove a derived signal from all assignments"""
                for tab_key in assignments:
                    for sp_key in assignments[tab_key]:
                        assignments[tab_key][sp_key] = [
                            s for s in assignments[tab_key][sp_key]
                            if not (s.get("csv_idx") == -1 and s.get("signal") == signal_name)
                        ]

            # Check if clear-all button was clicked
            if ctx.triggered_id == "btn-clear-derived" and clear_click:
                # Remove all derived signals from assignments
                for name in list(derived.keys()):
                    remove_from_assignments(name)
                self.derived_signals = {}
                return {}, assignments, "Cleared all derived"

            # Check if a specific delete button was clicked
            if (
                isinstance(ctx.triggered_id, dict)
                and ctx.triggered_id.get("type") == "del-derived"
            ):
                name = ctx.triggered_id.get("name", "")
                # Find the index of this button and check if it was actually clicked
                if del_clicks_tree:
                    for clicks in del_clicks_tree:
                        if clicks and clicks > 0:
                            if name and name in derived:
                                print(f"DEBUG: Deleting: {name}")
                                del derived[name]
                                remove_from_assignments(name)
                                self.derived_signals = derived
                                return derived, assignments, f"Deleted {name}"
                            break

            return dash.no_update, dash.no_update, dash.no_update

        # Update selected subplot store when dropdown changes
        @self.app.callback(
            Output("store-selected-subplot", "data", allow_duplicate=True),
            Input("subplot-select", "value"),
            prevent_initial_call=True,
        )
        def update_selected_subplot(val):
            return int(val) if val is not None else 0

        # Update subplot from typed input
        @self.app.callback(
            [
                Output("store-selected-subplot", "data", allow_duplicate=True),
                Output("subplot-select", "value", allow_duplicate=True),
                Output("subplot-input", "value"),
            ],
            Input("subplot-input", "value"),
            [
                State("rows-input", "value"),
                State("cols-input", "value"),
            ],
            prevent_initial_call=True,
        )
        def update_subplot_from_input(typed_value, rows, cols):
            if typed_value is None:
                return dash.no_update, dash.no_update, dash.no_update
            
            rows = int(rows or 1)
            cols = int(cols or 1)
            max_subplots = rows * cols
            
            # Convert 1-based input to 0-based index
            subplot_idx = int(typed_value) - 1
            
            # Clamp to valid range
            if subplot_idx < 0:
                subplot_idx = 0
            elif subplot_idx >= max_subplots:
                subplot_idx = max_subplots - 1
            
            return subplot_idx, str(subplot_idx), None  # Clear input after setting

        # Click on plot to select subplot - uses both clickData and relayoutData
        @self.app.callback(
            [
                Output("store-selected-subplot", "data", allow_duplicate=True),
                Output("subplot-select", "value", allow_duplicate=True),
            ],
            [
                Input("plot", "clickData"),
                Input("plot", "relayoutData"),
            ],
            [
                State("store-layouts", "data"),
                State("store-selected-tab", "data"),
                State("store-selected-subplot", "data"),
            ],
            prevent_initial_call=True,
        )
        def select_subplot_by_click(click_data, relayout_data, layouts, tab_idx, current_subplot):
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update, dash.no_update
            
            trigger = ctx.triggered[0]["prop_id"]
            subplot_idx = None
            
            # Handle clickData (clicking on a trace)
            if "clickData" in trigger and click_data:
                point = click_data.get("points", [{}])[0]
                x_axis = point.get("xaxis", "x")
                
                if x_axis == "x":
                    subplot_idx = 0
                else:
                    try:
                        subplot_idx = int(x_axis.replace("x", "")) - 1
                    except:
                        subplot_idx = 0
            
            # Handle relayoutData (clicking/zooming on subplot area)
            elif "relayoutData" in trigger and relayout_data:
                # relayoutData contains axis references like "xaxis.range[0]", "xaxis2.autorange", etc.
                for key in relayout_data.keys():
                    if key.startswith("xaxis"):
                        # Extract axis number from key like "xaxis2.range[0]"
                        axis_part = key.split(".")[0]  # "xaxis" or "xaxis2"
                        if axis_part == "xaxis":
                            subplot_idx = 0
                        else:
                            try:
                                subplot_idx = int(axis_part.replace("xaxis", "")) - 1
                            except:
                                pass
                        break
                    elif key.startswith("yaxis"):
                        axis_part = key.split(".")[0]
                        if axis_part == "yaxis":
                            subplot_idx = 0
                        else:
                            try:
                                subplot_idx = int(axis_part.replace("yaxis", "")) - 1
                            except:
                                pass
                        break
            
            if subplot_idx is not None:
                return subplot_idx, str(subplot_idx)
            
            return dash.no_update, dash.no_update

        # Handle signal assignments with proper linking (fixed bidirectional issue)
        @self.app.callback(
            [
                Output("store-assignments", "data", allow_duplicate=True),
                Output("plot", "figure"),
                Output("assigned-list", "children"),
                Output("store-selected-tab", "data", allow_duplicate=True),
                Output("store-selected-subplot", "data", allow_duplicate=True),
                Output("store-layouts", "data", allow_duplicate=True),
            ],
            [
                Input({"type": "sig-check", "csv": ALL, "sig": ALL}, "value"),
                Input("tabs", "value"),
                Input("subplot-select", "value"),
                Input("rows-input", "value"),
                Input("cols-input", "value"),
                Input("btn-remove", "n_clicks"),
                Input("theme-switch", "value"),
                Input("store-derived", "data"),
                Input("store-signal-props", "data"),
                Input("link-axes-check", "value"),
                Input("store-refresh-trigger", "data"),
                Input("time-cursor-check", "value"),
                Input("store-cursor-x", "data"),
                Input("store-subplot-modes", "data"),
            ],
            [
                State({"type": "sig-check", "csv": ALL, "sig": ALL}, "id"),
                State("store-assignments", "data"),
                State("store-layouts", "data"),
                State("store-selected-tab", "data"),
                State("store-selected-subplot", "data"),
                State("store-links", "data"),
                State({"type": "remove-check", "idx": ALL}, "value"),
                State({"type": "remove-check", "idx": ALL}, "id"),
            ],
            prevent_initial_call=True,
        )
        def handle_assignments(
            check_vals,
            active_tab,
            subplot_val,
            rows,
            cols,
            remove_click,
            is_dark,
            derived,
            props,
            link_axes,
            refresh_trigger,
            time_cursor,
            cursor_data,
            subplot_modes,
            check_ids,
            assignments,
            layouts,
            sel_tab,
            sel_subplot,
            links,
            remove_vals,
            remove_ids,
        ):
            ctx = callback_context

            if not ctx.triggered:
                trigger = ""
            else:
                trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

            assignments = assignments or {}
            layouts = layouts or {}
            theme = "dark" if is_dark else "light"

            if "tabs" in trigger and active_tab:
                sel_tab = int(active_tab.split("-")[1]) if "-" in active_tab else 0
            elif active_tab:
                sel_tab = int(active_tab.split("-")[1]) if "-" in active_tab else 0
            else:
                sel_tab = sel_tab or 0

            # Track if we should output sel_subplot or use no_update
            output_subplot = False
            
            # Only update sel_subplot if explicitly triggered by subplot-select dropdown
            if "subplot-select" in trigger and subplot_val is not None:
                sel_subplot = int(subplot_val)
                output_subplot = True
            elif sel_subplot is None:
                sel_subplot = int(subplot_val) if subplot_val is not None else 0
            # Keep sel_subplot as-is for cursor changes and other triggers

            tab_key = str(sel_tab)
            subplot_key = str(sel_subplot)

            if tab_key not in assignments:
                assignments[tab_key] = {}
            if subplot_key not in assignments[tab_key]:
                assignments[tab_key][subplot_key] = []

            rows = int(rows) if rows else 1
            cols = int(cols) if cols else 1
            
            # Get old layout to remap subplots if layout changed
            old_layout = layouts.get(tab_key, {"rows": 1, "cols": 1})
            old_rows = old_layout.get("rows", 1)
            old_cols = old_layout.get("cols", 1)
            
            # Remap assignments if layout changed (preserve row/col positions)
            if (old_rows != rows or old_cols != cols) and "rows-input" in trigger or "cols-input" in trigger:
                if tab_key in assignments:
                    old_assignments = assignments[tab_key].copy()
                    new_assignments = {}
                    
                    for old_sp_key, signals in old_assignments.items():
                        old_sp = int(old_sp_key)
                        # Calculate old row/col
                        old_row = old_sp // old_cols
                        old_col = old_sp % old_cols
                        # Calculate new index (preserving row/col position)
                        if old_row < rows and old_col < cols:
                            new_sp = old_row * cols + old_col
                            new_sp_key = str(new_sp)
                            if new_sp_key not in new_assignments:
                                new_assignments[new_sp_key] = []
                            new_assignments[new_sp_key].extend(signals)
                    
                    assignments[tab_key] = new_assignments
            
            layouts[tab_key] = {"rows": rows, "cols": cols}

            if sel_subplot >= rows * cols:
                sel_subplot = 0
                subplot_key = "0"

            # Get current subplot mode
            current_mode = tab_subplot_modes.get(subplot_key, "time")
            
            # Handle signal checkbox changes - FIXED linking logic
            if (
                check_vals is not None
                and check_ids is not None
                and len(check_vals) > 0
                and "sig-check" in trigger
            ):
                # Find which checkbox was actually clicked
                clicked_csv = None
                clicked_sig = None
                clicked_new_val = None

                import json as js

                try:
                    id_str = trigger.split(".")[0]
                    clicked_id = js.loads(id_str)
                    clicked_csv = clicked_id["csv"]
                    clicked_sig = clicked_id["sig"]
                    # Find the value for this specific checkbox
                    for val, id_dict in zip(check_vals, check_ids):
                        if (
                            id_dict["csv"] == clicked_csv
                            and id_dict["sig"] == clicked_sig
                        ):
                            clicked_new_val = val
                            break
                except:
                    pass

                # Handle X-Y mode assignment
                if current_mode == "xy":
                    if clicked_csv is not None and clicked_sig is not None and clicked_new_val:
                        # Initialize assignment as dict if needed
                        if not isinstance(assignments[tab_key].get(subplot_key), dict):
                            assignments[tab_key][subplot_key] = {"x": None, "y": None}
                        
                        xy_assignment = assignments[tab_key][subplot_key]
                        new_signal = {"csv_idx": clicked_csv, "signal": clicked_sig}
                        
                        # If X is not set, assign to X; otherwise assign to Y
                        if not xy_assignment.get("x"):
                            xy_assignment["x"] = new_signal
                        else:
                            xy_assignment["y"] = new_signal
                        
                        assignments[tab_key][subplot_key] = xy_assignment
                else:
                    # Time mode: original list-based logic
                    current = assignments[tab_key][subplot_key]
                    if not isinstance(current, list):
                        current = []
                        assignments[tab_key][subplot_key] = current
                    current_keys = {f"{s['csv_idx']}:{s['signal']}" for s in current}

                    # Only process the clicked checkbox and apply linking
                    if clicked_csv is not None and clicked_sig is not None:
                        csv_idx = clicked_csv
                        sig = clicked_sig
                        key = f"{csv_idx}:{sig}"

                        is_currently_assigned = key in current_keys
                        should_be_assigned = clicked_new_val if clicked_new_val else False

                        if should_be_assigned and not is_currently_assigned:
                            # ADD signal - check for linked CSVs
                            linked_indices = [csv_idx]
                            for lg in links or []:
                                if csv_idx in lg.get("csv_indices", []):
                                    linked_indices = lg["csv_indices"]
                                    break

                            # Add clicked signal and all linked versions
                            for linked_csv_idx in linked_indices:
                                linked_key = f"{linked_csv_idx}:{sig}"
                                if linked_key not in current_keys:
                                    if linked_csv_idx >= 0 and linked_csv_idx < len(
                                        self.data_manager.data_tables
                                    ):
                                        df = self.data_manager.data_tables[linked_csv_idx]
                                        if df is not None and sig in df.columns:
                                            assignments[tab_key][subplot_key].append(
                                                {"csv_idx": linked_csv_idx, "signal": sig}
                                            )
                                            current_keys.add(linked_key)
                                    elif linked_csv_idx == -1:
                                        if sig in self.derived_signals:
                                            assignments[tab_key][subplot_key].append(
                                                {"csv_idx": -1, "signal": sig}
                                            )
                                            current_keys.add(linked_key)

                        elif not should_be_assigned and is_currently_assigned:
                            # REMOVE signal - check for linked CSVs
                            linked_indices = [csv_idx]
                            for lg in links or []:
                                if csv_idx in lg.get("csv_indices", []):
                                    linked_indices = lg["csv_indices"]
                                    break

                            # Remove clicked signal and all linked versions
                            for linked_csv_idx in linked_indices:
                                linked_key = f"{linked_csv_idx}:{sig}"
                                assignments[tab_key][subplot_key] = [
                                    s
                                    for s in assignments[tab_key][subplot_key]
                                    if f"{s['csv_idx']}:{s['signal']}" != linked_key
                                ]

            if "btn-remove" in trigger and remove_vals:
                to_remove = {
                    id_dict["idx"]
                    for val, id_dict in zip(remove_vals, remove_ids)
                    if val
                }
                assignments[tab_key][subplot_key] = [
                    s
                    for i, s in enumerate(assignments[tab_key][subplot_key])
                    if i not in to_remove
                ]

            self.signal_properties = props or {}
            self.derived_signals = derived or {}

            # Get cursor X position
            cursor_x = None
            if time_cursor and cursor_data:
                cursor_x = cursor_data.get("x")
            
            # Get subplot modes for current tab
            tab_subplot_modes = (subplot_modes or {}).get(tab_key, {})
            
            fig = self.create_figure(
                rows, cols, theme, sel_subplot, assignments, tab_key, link_axes, time_cursor, cursor_x, tab_subplot_modes
            )

            assigned = assignments.get(tab_key, {}).get(subplot_key, [])
            current_mode = tab_subplot_modes.get(subplot_key, "time")
            items = []
            
            # Handle X-Y mode display
            if current_mode == "xy" and isinstance(assigned, dict):
                # Show X and Y signal info
                x_info = assigned.get("x", {})
                y_info = assigned.get("y", {})
                
                for axis, info in [("X", x_info), ("Y", y_info)]:
                    if info:
                        csv_idx = info.get("csv_idx", -1)
                        sig_name = info.get("signal", "")
                        if csv_idx == -1:
                            lbl = f"{sig_name} (D)"
                        else:
                            if csv_idx < len(self.data_manager.csv_file_paths):
                                csv_path = self.data_manager.csv_file_paths[csv_idx]
                                csv_filename = os.path.splitext(os.path.basename(csv_path))[0]
                            else:
                                csv_filename = f"C{csv_idx+1}"
                            lbl = f"{sig_name} ({csv_filename})"
                        
                        color = "info" if axis == "X" else "warning"
                        items.append(
                            html.Div(
                                [
                                    html.Span(f"{axis}: ", className=f"text-{color} fw-bold small"),
                                    html.Span(lbl, className="small"),
                                    dbc.Button(
                                        "×",
                                        id={"type": "xy-remove", "axis": axis.lower()},
                                        size="sm",
                                        color="danger",
                                        outline=True,
                                        className="ms-2 py-0 px-1",
                                        style={"fontSize": "10px"},
                                    ),
                                ],
                                className="d-flex align-items-center mb-1",
                            )
                        )
                if not items:
                    items = [html.Span("Assign X and Y signals", className="text-muted small")]
            else:
                # Time mode: show list of signals with checkboxes
                if isinstance(assigned, list):
                    for i, s in enumerate(assigned):
                        csv_idx = s.get("csv_idx", -1)
                        sig_name = s.get("signal", "")
                        if csv_idx == -1:
                            lbl = f"{sig_name} (D)"
                        else:
                            # Get CSV filename for display
                            if csv_idx < len(self.data_manager.csv_file_paths):
                                csv_path = self.data_manager.csv_file_paths[csv_idx]
                                csv_filename = os.path.splitext(os.path.basename(csv_path))[0]
                            else:
                                csv_filename = f"C{csv_idx+1}"
                            lbl = f"{sig_name} ({csv_filename})"
                        items.append(
                            dbc.Checkbox(
                                id={"type": "remove-check", "idx": i},
                                label=lbl,
                                value=False,
                                style={"fontSize": "10px"},
                            )
                        )
                if not items:
                    items = [html.Span("None", className="text-muted small")]

            # Only output sel_subplot if explicitly changed, otherwise use no_update
            subplot_output = sel_subplot if output_subplot else dash.no_update
            return assignments, fig, items, sel_tab, subplot_output, layouts

        # Subplot selector
        @self.app.callback(
            Output("subplot-select", "options"),
            [Input("rows-input", "value"), Input("cols-input", "value")],
        )
        def update_subplot_options(rows, cols):
            rows, cols = int(rows or 1), int(cols or 1)
            return [{"label": str(i + 1), "value": i} for i in range(rows * cols)]

        # Sync rows/cols inputs when tab changes (each tab has its own layout)
        @self.app.callback(
            [
                Output("rows-input", "value"),
                Output("cols-input", "value"),
                Output("subplot-select", "value"),
            ],
            [Input("tabs", "value")],
            [State("store-layouts", "data")],
            prevent_initial_call=True,
        )
        def sync_layout_on_tab_change(active_tab, layouts):
            if not active_tab:
                return 1, 1, 0
            tab_idx = int(active_tab.split("-")[1]) if "-" in active_tab else 0
            tab_key = str(tab_idx)
            layouts = layouts or {}
            layout = layouts.get(tab_key, {"rows": 1, "cols": 1})
            return layout.get("rows", 1), layout.get("cols", 1), 0

        # Handle subplot mode toggle (Time vs X-Y)
        @self.app.callback(
            [
                Output("store-subplot-modes", "data"),
                Output("xy-controls", "style"),
                Output("xy-x-signal", "children"),
                Output("xy-y-signal", "children"),
            ],
            [
                Input("subplot-mode-toggle", "value"),
                Input("store-selected-subplot", "data"),
                Input("tabs", "value"),
            ],
            [
                State("store-subplot-modes", "data"),
                State("store-assignments", "data"),
            ],
            prevent_initial_call=True,
        )
        def handle_subplot_mode(mode, sel_subplot, active_tab, modes, assignments):
            ctx = callback_context
            modes = modes or {}
            
            tab_idx = int(active_tab.split("-")[1]) if active_tab and "-" in active_tab else 0
            tab_key = str(tab_idx)
            subplot_key = str(sel_subplot or 0)
            
            if tab_key not in modes:
                modes[tab_key] = {}
            
            trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
            
            # If mode toggle triggered, update the mode
            if "subplot-mode-toggle" in trigger:
                modes[tab_key][subplot_key] = mode
            else:
                # Otherwise, get current mode for this subplot
                mode = modes.get(tab_key, {}).get(subplot_key, "time")
            
            # Show/hide X-Y controls based on mode
            xy_style = {"display": "block"} if mode == "xy" else {"display": "none"}
            
            # Get X and Y signal names if in xy mode
            x_signal = "(none)"
            y_signal = "(none)"
            
            if mode == "xy":
                assignment = assignments.get(tab_key, {}).get(subplot_key, {})
                if isinstance(assignment, dict):
                    x_info = assignment.get("x", {})
                    y_info = assignment.get("y", {})
                    if x_info:
                        x_signal = x_info.get("signal", "(none)")
                    if y_info:
                        y_signal = y_info.get("signal", "(none)")
            
            return modes, xy_style, x_signal, y_signal

        # Sync mode toggle when subplot changes
        @self.app.callback(
            Output("subplot-mode-toggle", "value"),
            [
                Input("store-selected-subplot", "data"),
                Input("tabs", "value"),
            ],
            [State("store-subplot-modes", "data")],
            prevent_initial_call=True,
        )
        def sync_mode_on_subplot_change(sel_subplot, active_tab, modes):
            modes = modes or {}
            tab_idx = int(active_tab.split("-")[1]) if active_tab and "-" in active_tab else 0
            tab_key = str(tab_idx)
            subplot_key = str(sel_subplot or 0)
            
            mode = modes.get(tab_key, {}).get(subplot_key, "time")
            return mode

        # Handle X/Y signal removal in X-Y mode
        @self.app.callback(
            Output("store-assignments", "data", allow_duplicate=True),
            [
                Input({"type": "xy-remove", "axis": ALL}, "n_clicks"),
            ],
            [
                State({"type": "xy-remove", "axis": ALL}, "id"),
                State("store-assignments", "data"),
                State("store-selected-tab", "data"),
                State("store-selected-subplot", "data"),
            ],
            prevent_initial_call=True,
        )
        def handle_xy_remove(n_clicks, ids, assignments, sel_tab, sel_subplot):
            ctx = callback_context
            if not ctx.triggered or not any(n_clicks):
                return dash.no_update
            
            trigger = ctx.triggered[0]["prop_id"]
            assignments = assignments or {}
            tab_key = str(sel_tab or 0)
            subplot_key = str(sel_subplot or 0)
            
            # Find which axis button was clicked
            try:
                import json as js
                id_str = trigger.split(".")[0]
                clicked_id = js.loads(id_str)
                axis = clicked_id.get("axis", "")
                
                if axis in ["x", "y"]:
                    assignment = assignments.get(tab_key, {}).get(subplot_key, {})
                    if isinstance(assignment, dict):
                        assignment[axis] = None
                        assignments[tab_key][subplot_key] = assignment
            except:
                pass
            
            return assignments

        # Tab management
        @self.app.callback(
            [
                Output("tabs", "children"),
                Output("store-num-tabs", "data"),
                Output("store-layouts", "data", allow_duplicate=True),
                Output("tabs", "value", allow_duplicate=True),
                Output("store-assignments", "data", allow_duplicate=True),
            ],
            [Input("btn-add-tab", "n_clicks"), Input("btn-del-tab", "n_clicks")],
            [
                State("tabs", "children"),
                State("tabs", "value"),
                State("store-layouts", "data"),
                State("store-assignments", "data"),
            ],
            prevent_initial_call=True,
        )
        def manage_tabs(add, delete, tabs, current, layouts, assignments):
            ctx = callback_context
            trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""
            tabs, layouts = tabs or [], layouts or {}
            assignments = assignments or {}
            new_active = current
            
            if trigger == "btn-add-tab":
                idx = len(tabs)
                tabs.append(dcc.Tab(label=f"Tab {idx+1}", value=f"tab-{idx}"))
                layouts[str(idx)] = {"rows": 1, "cols": 1}
                
            elif trigger == "btn-del-tab" and len(tabs) > 1:
                # Get current tab index
                del_idx = int(current.split("-")[1]) if current and "-" in current else 0
                
                # Remove the tab at del_idx
                tabs = [t for i, t in enumerate(tabs) if i != del_idx]
                
                # Rebuild layouts with new indices
                new_layouts = {}
                new_assignments = {}
                old_to_new = {}
                
                new_i = 0
                for old_i in range(len(tabs) + 1):  # +1 because we removed one
                    if old_i == del_idx:
                        continue  # Skip deleted tab
                    old_to_new[old_i] = new_i
                    # Copy layout
                    if str(old_i) in layouts:
                        new_layouts[str(new_i)] = layouts[str(old_i)]
                    # Copy assignments
                    if str(old_i) in assignments:
                        new_assignments[str(new_i)] = assignments[str(old_i)]
                    new_i += 1
                
                layouts = new_layouts
                assignments = new_assignments
                
                # Rename tabs
                for i, t in enumerate(tabs):
                    if isinstance(t, dict):
                        t["props"]["label"] = f"Tab {i+1}"
                        t["props"]["value"] = f"tab-{i}"
                
                # Set new active tab (previous tab or first tab)
                new_active_idx = max(0, del_idx - 1) if del_idx > 0 else 0
                new_active = f"tab-{new_active_idx}"
            
            return tabs, len(tabs), layouts, new_active, assignments

        # Link modal
        @self.app.callback(
            [Output("modal-link", "is_open"), Output("link-checks", "options")],
            [
                Input("btn-link", "n_clicks"),
                Input("btn-close-link", "n_clicks"),
                Input("btn-create-link", "n_clicks"),
            ],
            [State("modal-link", "is_open")],
            prevent_initial_call=True,
        )
        def toggle_link(o, c, cr, is_open):
            if "btn-link" in callback_context.triggered[0]["prop_id"]:
                return True, [
                    {"label": os.path.basename(f), "value": i}
                    for i, f in enumerate(self.data_manager.csv_file_paths)
                ]
            return False, []

        @self.app.callback(
            [
                Output("store-links", "data", allow_duplicate=True),
                Output("status-text", "children", allow_duplicate=True),
            ],
            Input("btn-create-link", "n_clicks"),
            [
                State("link-checks", "value"),
                State("link-name", "value"),
                State("store-links", "data"),
            ],
            prevent_initial_call=True,
        )
        def create_link(n, selected, name, links):
            if not n or not selected or len(selected) < 2:
                return dash.no_update, "Select 2+ CSVs"
            links = links or []
            links.append(
                {"csv_indices": selected, "name": name or f"Link{len(links)+1}"}
            )
            return links, f"✅ Linked"

        # Properties modal
        @self.app.callback(
            [
                Output("modal-props", "is_open"),
                Output("props-title", "children"),
                Output("store-context-signal", "data"),
                Output("prop-name", "value"),
                Output("prop-scale", "value"),
                Output("prop-color", "value"),
                Output("prop-width", "value"),
                Output("prop-state-signal", "value"),
            ],
            [
                Input({"type": "sig-props", "csv": ALL, "sig": ALL}, "n_clicks"),
                Input("btn-close-props", "n_clicks"),
            ],
            [State("store-signal-props", "data")],
            prevent_initial_call=True,
        )
        def toggle_props(clicks, close, props):
            trigger = (
                callback_context.triggered[0]["prop_id"]
                if callback_context.triggered
                else ""
            )
            if "sig-props" in trigger:
                for c in clicks or []:
                    if c:
                        import json as js

                        id_dict = js.loads(trigger.split(".")[0])
                        key = f"{id_dict['csv']}:{id_dict['sig']}"
                        p = (props or {}).get(key, {})
                        return (
                            True,
                            f"Props: {id_dict['sig']}",
                            key,
                            p.get("display_name", id_dict["sig"]),
                            p.get("scale", 1.0),
                            p.get("color", "#2E86AB"),
                            p.get("width", 1.5),
                            p.get("is_state", False),
                        )
            return False, "", None, "", 1.0, "#2E86AB", 1.5, False

        @self.app.callback(
            [
                Output("store-signal-props", "data", allow_duplicate=True),
                Output("status-text", "children", allow_duplicate=True),
            ],
            Input("btn-apply-props", "n_clicks"),
            [
                State("store-context-signal", "data"),
                State("prop-name", "value"),
                State("prop-scale", "value"),
                State("prop-color", "value"),
                State("prop-width", "value"),
                State("prop-apply-tree", "value"),
                State("prop-state-signal", "value"),
                State("store-signal-props", "data"),
            ],
            prevent_initial_call=True,
        )
        def apply_props(n, key, name, scale, color, width, show, is_state, props):
            if not n or not key:
                return dash.no_update, dash.no_update
            props = props or {}
            props[key] = {
                "display_name": name,
                "scale": float(scale or 1),
                "color": color,
                "width": float(width or 1.5),
                "show_in_tree": show,
                "is_state": is_state,
            }
            self.signal_properties = props
            return props, "✅ Saved"

        # Single signal operations
        @self.app.callback(
            [
                Output("modal-ops", "is_open"),
                Output("ops-title", "children"),
                Output("op-result-name", "value"),
            ],
            [
                Input({"type": "sig-ops", "csv": ALL, "sig": ALL}, "n_clicks"),
                Input("btn-close-ops", "n_clicks"),
            ],
            prevent_initial_call=True,
        )
        def toggle_ops(clicks, close):
            trigger = (
                callback_context.triggered[0]["prop_id"]
                if callback_context.triggered
                else ""
            )
            if "sig-ops" in trigger:
                for c in clicks or []:
                    if c:
                        import json as js

                        id_dict = js.loads(trigger.split(".")[0])
                        return True, f"Op: {id_dict['sig']}", f"d_{id_dict['sig']}"
            return False, "", ""

        @self.app.callback(
            [
                Output("store-derived", "data", allow_duplicate=True),
                Output("status-text", "children", allow_duplicate=True),
            ],
            Input("btn-compute-op", "n_clicks"),
            [
                State("ops-title", "children"),
                State("op-type", "value"),
                State("op-result-name", "value"),
                State("store-derived", "data"),
            ],
            prevent_initial_call=True,
        )
        def compute_op(n, title, op, name, derived):
            if not n or not title:
                return dash.no_update, dash.no_update
            sig = title.replace("Op: ", "")
            derived = derived or {}
            time_data, sig_data = None, None

            # Check if it's a derived signal
            if sig in self.derived_signals:
                ds = self.derived_signals[sig]
                time_data = ds.get("time", [])
                sig_data = ds.get("data", [])
            else:
                # Regular signal from CSV
                for csv_idx, df in enumerate(self.data_manager.data_tables):
                    if df is not None and sig in df.columns:
                        time_col = "Time" if "Time" in df.columns else df.columns[0]
                        time_data = df[time_col].values
                        sig_data = df[sig].values
                        break

            if time_data is None or len(time_data) == 0:
                return dash.no_update, "Signal not found"

            try:
                if op == "derivative":
                    result = np.gradient(sig_data, time_data)
                elif op == "integral":
                    result = np.cumsum(sig_data) * np.mean(np.diff(time_data))
                elif op == "abs":
                    result = np.abs(sig_data)
                elif op == "sqrt":
                    result = np.sqrt(np.abs(sig_data))
                elif op == "negate":
                    result = -sig_data
                else:
                    result = sig_data
                name = name or f"{op}_{sig}"
                derived[name] = {
                    "time": time_data.tolist(),
                    "data": result.tolist(),
                    "source": sig,
                    "op": op,
                }
                self.derived_signals = derived
                return derived, f"✅ {name}"
            except Exception as e:
                return dash.no_update, f"❌ {e}"

        # Multi-signal operations
        @self.app.callback(
            [
                Output("modal-multi-ops", "is_open"),
                Output("selected-signals-info", "children"),
            ],
            [
                Input("btn-operate-selected", "n_clicks"),
                Input("btn-close-multi", "n_clicks"),
                Input("btn-compute-multi", "n_clicks"),
            ],
            [State("store-highlighted", "data")],
            prevent_initial_call=True,
        )
        def toggle_multi(o, c, comp, highlighted):
            if "btn-operate-selected" in callback_context.triggered[0]["prop_id"]:
                info = (
                    f"Selected: {', '.join(h.split(':')[1] for h in (highlighted or []))}"
                    if highlighted
                    else "None selected"
                )
                return True, info
            return False, ""

        @self.app.callback(
            [
                Output("store-derived", "data", allow_duplicate=True),
                Output("status-text", "children", allow_duplicate=True),
            ],
            Input("btn-compute-multi", "n_clicks"),
            [
                State("store-highlighted", "data"),
                State("multi-op-type", "value"),
                State("multi-op-name", "value"),
                State("store-derived", "data"),
            ],
            prevent_initial_call=True,
        )
        def compute_multi(n, highlighted, op, name, derived):
            if not n or not highlighted or len(highlighted) < 2:
                return dash.no_update, "Select 2+ signals"
            derived = derived or {}
            signals_data, time_data = [], None

            for h in highlighted:
                csv_idx, sig = h.split(":", 1)
                csv_idx = int(csv_idx)

                # Get signal data
                if csv_idx == -1 and sig in self.derived_signals:
                    ds = self.derived_signals[sig]
                    sig_data = ds.get("data", [])
                    if time_data is None:
                        time_data = ds.get("time", [])
                elif csv_idx >= 0 and csv_idx < len(self.data_manager.data_tables):
                    df = self.data_manager.data_tables[csv_idx]
                    if df is not None and sig in df.columns:
                        if time_data is None:
                            time_col = "Time" if "Time" in df.columns else df.columns[0]
                            time_data = df[time_col].values
                        sig_data = df[sig].values
                    else:
                        continue
                else:
                    continue

                signals_data.append(sig_data)

            if len(signals_data) < 2:
                return dash.no_update, "Not enough data"

            try:
                min_len = min(len(s) for s in signals_data)
                signals_data = [s[:min_len] for s in signals_data]
                time_data = time_data[:min_len]
                a, b = np.array(signals_data[0]), np.array(signals_data[1])
                if op == "add":
                    result = a + b
                elif op == "sub":
                    result = a - b
                elif op == "mul":
                    result = a * b
                elif op == "div":
                    result = np.divide(a, b, where=b != 0)
                elif op == "norm":
                    result = np.sqrt(sum(np.array(s) ** 2 for s in signals_data))
                elif op == "mean":
                    result = np.mean(signals_data, axis=0)
                else:
                    result = a
                name = name or f"{op}_result"
                derived[name] = {
                    "time": time_data.tolist(),
                    "data": result.tolist(),
                    "source": "multi",
                    "op": op,
                }
                self.derived_signals = derived
                return derived, f"✅ {name}"
            except Exception as e:
                return dash.no_update, f"❌ {e}"

        # Save session - downloads to user's chosen location
        @self.app.callback(
            [
                Output("download-session", "data"),
                Output("status-text", "children", allow_duplicate=True),
            ],
            Input("btn-save", "n_clicks"),
            [
                State("store-csv-files", "data"),
                State("store-assignments", "data"),
                State("store-layouts", "data"),
                State("store-links", "data"),
                State("store-signal-props", "data"),
                State("store-derived", "data"),
                State("store-num-tabs", "data"),
                State("store-subplot-modes", "data"),
                State("store-cursor-x", "data"),
            ],
            prevent_initial_call=True,
        )
        def save_session(n, files, assign, layouts, links, props, derived, num_tabs, subplot_modes, cursor_x):
            if not n:
                return dash.no_update, dash.no_update
            try:
                session_data = {
                    "files": files,
                    "assignments": assign,
                    "layouts": layouts,
                    "links": links,
                    "props": props,
                    "derived": derived,
                    "num_tabs": num_tabs or 1,
                    "subplot_modes": subplot_modes or {},
                    "cursor_x": cursor_x,
                }
                # Generate filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"signal_viewer_session_{timestamp}.json"
                return (
                    dict(content=json.dumps(session_data, indent=2), filename=filename),
                    "✅ Saving...",
                )
            except Exception as e:
                return dash.no_update, f"❌ {e}"

        # Load session - from uploaded file
        @self.app.callback(
            [
                Output("store-csv-files", "data", allow_duplicate=True),
                Output("store-assignments", "data", allow_duplicate=True),
                Output("store-layouts", "data", allow_duplicate=True),
                Output("store-links", "data", allow_duplicate=True),
                Output("store-signal-props", "data", allow_duplicate=True),
                Output("store-derived", "data", allow_duplicate=True),
                Output("store-num-tabs", "data", allow_duplicate=True),
                Output("tabs", "children", allow_duplicate=True),
                Output("store-subplot-modes", "data", allow_duplicate=True),
                Output("store-cursor-x", "data", allow_duplicate=True),
                Output("status-text", "children", allow_duplicate=True),
            ],
            Input("upload-session", "contents"),
            State("upload-session", "filename"),
            prevent_initial_call=True,
        )
        def load_session(contents, filename):
            if not contents:
                return [dash.no_update] * 11
            try:
                # Decode uploaded file
                content_type, content_string = contents.split(",")
                decoded = base64.b64decode(content_string).decode("utf-8")
                d = json.loads(decoded)
                
                files = d.get("files", [])
                self.data_manager.csv_file_paths = files
                self.data_manager.data_tables = [None] * len(files)
                self.data_manager.last_read_rows = [0] * len(files)
                for i in range(len(files)):
                    if os.path.exists(files[i]):
                        self.data_manager.read_initial_data(i)
                self.derived_signals = d.get("derived", {})
                self.signal_properties = d.get("props", {})
                
                # Restore tabs
                num_tabs = d.get("num_tabs", 1)
                tabs_children = [
                    dcc.Tab(label=f"Tab {i+1}", value=f"tab-{i}")
                    for i in range(num_tabs)
                ]
                
                return (
                    files,
                    d.get("assignments", {}),
                    d.get("layouts", {}),
                    d.get("links", []),
                    d.get("props", {}),
                    d.get("derived", {}),
                    num_tabs,
                    tabs_children,
                    d.get("subplot_modes", {}),
                    d.get("cursor_x", {"x": None, "initialized": False}),
                    f"✅ Loaded: {filename}",
                )
            except Exception as e:
                return [dash.no_update] * 10 + [f"❌ {e}"]

        # Clientside callback to initialize Split.js after page loads
        self.app.clientside_callback(
            """
            function(n_intervals) {
                console.log('Split init attempt:', n_intervals);
                
                if (typeof Split === 'undefined') {
                    console.log('Split.js not loaded yet');
                    return window.dash_clientside.no_update;
                }
                
                var sidebar = document.getElementById('split-sidebar');
                var plot = document.getElementById('split-plot');
                var panel1 = document.getElementById('split-panel-1');
                var panel2 = document.getElementById('split-panel-2');
                var panel3 = document.getElementById('split-panel-3');
                
                if (!sidebar || !plot) {
                    console.log('Split elements not found yet');
                    return window.dash_clientside.no_update;
                }
                
                // Check if already initialized
                if (sidebar.dataset.splitInit === 'true') {
                    console.log('Already initialized');
                    return true;
                }
                
                try {
                    // Horizontal split: sidebar vs plot
                    Split(['#split-sidebar', '#split-plot'], {
                        sizes: [35, 65],
                        minSize: [300, 400],
                        gutterSize: 10,
                        cursor: 'col-resize',
                        direction: 'horizontal',
                        onDrag: function() {
                            window.dispatchEvent(new Event('resize'));
                        }
                    });
                    console.log('Horizontal split created');
                    
                    // Vertical split: panels in sidebar
                    if (panel1 && panel2 && panel3) {
                        Split(['#split-panel-1', '#split-panel-2', '#split-panel-3'], {
                            sizes: [18, 57, 25],
                            minSize: [80, 100, 80],
                            gutterSize: 8,
                            cursor: 'row-resize',
                            direction: 'vertical'
                        });
                        console.log('Vertical split created');
                    }
                    
                    sidebar.dataset.splitInit = 'true';
                    console.log('Split.js initialized successfully!');
                    return true;
                } catch (e) {
                    console.error('Split error:', e);
                    return window.dash_clientside.no_update;
                }
            }
            """,
            Output("store-split-init", "data"),
            Input("interval-split-init", "n_intervals"),
        )

        # Update cursor position from plot click (not hover)
        @self.app.callback(
            Output("store-cursor-x", "data"),
            [Input("plot", "clickData"), Input("time-cursor-check", "value")],
            [State("store-cursor-x", "data")],
            prevent_initial_call=True,
        )
        def update_cursor_position(click_data, cursor_enabled, current_cursor):
            if not cursor_enabled:
                return {"x": None, "initialized": False}
            
            current_cursor = current_cursor or {"x": None, "initialized": False}
            
            if click_data:
                try:
                    point = click_data.get("points", [{}])[0]
                    x_val = point.get("x", None)
                    if x_val is not None:
                        return {"x": float(x_val), "initialized": True}
                except:
                    pass
            
            return current_cursor

        print("DEBUG: All callbacks registered successfully!")


def main():
    import webbrowser, threading, time, traceback

    try:
        print("=" * 50)
        print("  Signal Viewer Pro - http://127.0.0.1:8050")
        print("=" * 50)
        print("DEBUG: Creating SignalViewerApp...")
        app = SignalViewerApp()
        print(f"DEBUG: App created, {len(app.app.callback_map)} callbacks registered")
        threading.Thread(
            target=lambda: (time.sleep(1.5), webbrowser.open("http://127.0.0.1:8050")),
            daemon=True,
        ).start()
        app.app.run(debug=False, port=8050, host="127.0.0.1")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        input("Press Enter...")


if __name__ == "__main__":
    main()
