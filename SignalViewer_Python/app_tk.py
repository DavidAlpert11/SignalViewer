"""
Signal Viewer Pro - Tkinter Version
====================================
High-performance signal visualization using native Tkinter + Matplotlib.

Features:
- Multi-CSV loading with native file dialogs
- Multi-tab, multi-subplot layouts (up to 4x4 grid)
- Interactive time cursor with synchronized value display
- Signal customization (color, scale, line width, display name)
- Derived signals (derivative, integral, math operations)
- X-Y plot mode for correlation analysis
- Session/template save/load
- CSV/HTML/PDF export
- Streaming mode for live CSV updates

Author: Signal Viewer Team
Version: 3.0 (Tkinter)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass, field
from collections import OrderedDict
import threading
import time

# Import shared modules
from data_manager import DataManager
from config import SIGNAL_COLORS, APP_TITLE
from helpers import (
    get_csv_display_name,
    make_signal_key,
    parse_signal_key,
    calculate_derived_signal,
    calculate_multi_signal_operation,
)


# ============================================================================
# Theme Configuration
# ============================================================================
@dataclass
class Theme:
    """Color scheme for UI theming"""
    name: str
    bg: str
    fg: str
    card_bg: str
    card_header: str
    accent: str
    border: str
    input_bg: str
    button_bg: str
    button_fg: str
    plot_bg: str
    plot_fg: str
    grid_color: str
    highlight: str


THEMES = {
    "dark": Theme(
        name="dark",
        bg="#1a1a2e",
        fg="#e8e8e8",
        card_bg="#16213e",
        card_header="#0f3460",
        accent="#4ea8de",
        border="#333333",
        input_bg="#2a2a3e",
        button_bg="#0f3460",
        button_fg="#e8e8e8",
        plot_bg="#1a1a2e",
        plot_fg="#e8e8e8",
        grid_color="#444444",
        highlight="#f4a261",
    ),
    "light": Theme(
        name="light",
        bg="#f0f2f5",
        fg="#1a1a2e",
        card_bg="#ffffff",
        card_header="#e3e7eb",
        accent="#2E86AB",
        border="#ced4da",
        input_bg="#ffffff",
        button_bg="#e3e7eb",
        button_fg="#1a1a2e",
        plot_bg="#ffffff",
        plot_fg="#1a1a2e",
        grid_color="#dee2e6",
        highlight="#f4a261",
    ),
}


# ============================================================================
# Data Classes
# ============================================================================
@dataclass
class SignalAssignment:
    """Represents a signal assigned to a subplot"""
    csv_idx: int
    signal_name: str
    color: str = ""
    scale: float = 1.0
    width: float = 1.5
    display_name: str = ""
    time_offset: float = 0.0
    is_state: bool = False


@dataclass
class Annotation:
    """Represents a plot annotation"""
    x: float
    y: float
    text: str
    color: str = "#ff6b6b"
    

@dataclass 
class SubplotConfig:
    """Configuration for a subplot"""
    signals: List[SignalAssignment] = field(default_factory=list)
    title: str = ""
    caption: str = ""
    description: str = ""
    mode: str = "time"  # "time" or "xy"
    x_signal_key: str = "time"
    annotations: List[Annotation] = field(default_factory=list)


@dataclass
class TabConfig:
    """Configuration for a tab"""
    name: str = "Tab 1"
    rows: int = 1
    cols: int = 1
    subplots: Dict[int, SubplotConfig] = field(default_factory=dict)


# ============================================================================
# Main Application Class
# ============================================================================
class SignalViewerApp:
    """Main application class for Signal Viewer Pro (Tkinter version)"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("📊 Signal Viewer Pro")
        self.root.geometry("1600x900")
        self.root.minsize(1200, 700)
        
        # Application state
        self.current_theme = THEMES["dark"]
        self.tabs: List[TabConfig] = [TabConfig()]
        self.current_tab_idx = 0
        self.current_subplot_idx = 0
        self.highlighted_signals: List[str] = []  # For multi-signal operations
        self.derived_signals: Dict[str, Dict] = {}  # {name: {time, data, info}}
        self.signal_properties: Dict[str, Dict] = {}  # {key: {color, scale, ...}}
        self.links: List[Dict] = []  # CSV linking groups
        self.cursor_x: Optional[float] = None
        self.cursor_enabled = True
        self.link_axes = False
        
        # CSV data management (reuse existing DataManager)
        self.csv_files: List[str] = []
        self.data_tables: List[pd.DataFrame] = []
        self.time_columns: Dict[int, str] = {}  # {csv_idx: column_name}
        
        # Streaming state
        self.streaming_active = False
        self.streaming_thread: Optional[threading.Thread] = None
        
        # UI components
        self.figure: Optional[Figure] = None
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.axes: List[plt.Axes] = []
        
        # Create UI
        self._create_styles()
        self._create_menu()
        self._create_main_layout()
        self._apply_theme()
        
        # Bind keyboard shortcuts
        self._bind_shortcuts()
        
        # Initial plot
        self._update_plot()
        
    # ========================================================================
    # UI Creation Methods
    # ========================================================================
    
    def _create_styles(self):
        """Configure ttk styles for theming"""
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
    def _apply_theme(self):
        """Apply current theme to all widgets"""
        t = self.current_theme
        
        # Configure root
        self.root.configure(bg=t.bg)
        
        # Configure styles
        self.style.configure(".", background=t.bg, foreground=t.fg)
        self.style.configure("TFrame", background=t.bg)
        self.style.configure("TLabel", background=t.bg, foreground=t.fg)
        self.style.configure("TButton", background=t.button_bg, foreground=t.button_fg)
        self.style.configure("TCheckbutton", background=t.bg, foreground=t.fg)
        self.style.configure("TEntry", fieldbackground=t.input_bg, foreground=t.fg)
        self.style.configure("Treeview", background=t.card_bg, foreground=t.fg, 
                           fieldbackground=t.card_bg)
        self.style.configure("Treeview.Heading", background=t.card_header, foreground=t.fg)
        self.style.configure("TNotebook", background=t.bg)
        self.style.configure("TNotebook.Tab", background=t.card_header, foreground=t.fg,
                           padding=[10, 5])
        self.style.map("TNotebook.Tab", 
                      background=[("selected", t.accent)],
                      foreground=[("selected", "#ffffff")])
        
        # Card frame style
        self.style.configure("Card.TFrame", background=t.card_bg)
        self.style.configure("CardHeader.TFrame", background=t.card_header)
        self.style.configure("CardHeader.TLabel", background=t.card_header, 
                           foreground=t.fg, font=("Segoe UI", 10, "bold"))
        
        # Update matplotlib figure colors
        if self.figure:
            self.figure.set_facecolor(t.plot_bg)
            for ax in self.axes:
                ax.set_facecolor(t.plot_bg)
                ax.tick_params(colors=t.plot_fg)
                ax.xaxis.label.set_color(t.plot_fg)
                ax.yaxis.label.set_color(t.plot_fg)
                ax.title.set_color(t.plot_fg)
                for spine in ax.spines.values():
                    spine.set_color(t.grid_color)
            self.canvas.draw()
            
    def _create_menu(self):
        """Create application menu bar"""
        menubar = tk.Menu(self.root, bg=self.current_theme.card_bg, 
                         fg=self.current_theme.fg)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open CSV...", command=self._open_csv_dialog,
                             accelerator="Ctrl+O")
        file_menu.add_command(label="Clear All CSVs", command=self._clear_csvs)
        file_menu.add_separator()
        file_menu.add_command(label="Save Session...", command=self._save_session,
                             accelerator="Ctrl+S")
        file_menu.add_command(label="Load Session...", command=self._load_session,
                             accelerator="Ctrl+L")
        file_menu.add_separator()
        file_menu.add_command(label="Save Template...", command=self._save_template)
        file_menu.add_command(label="Load Template...", command=self._load_template)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Alt+F4")
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Refresh CSVs", command=self._refresh_csvs,
                             accelerator="F5")
        edit_menu.add_command(label="Clear Signals from Subplot", 
                             command=self._clear_current_subplot)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Toggle Theme", command=self._toggle_theme,
                             accelerator="Ctrl+T")
        view_menu.add_checkbutton(label="Link Axes", 
                                 command=self._toggle_link_axes)
        view_menu.add_checkbutton(label="Time Cursor",
                                 command=self._toggle_cursor)
        
        # Export menu
        export_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Export", menu=export_menu)
        export_menu.add_command(label="Export to CSV...", command=self._export_csv)
        export_menu.add_command(label="Export to HTML...", command=self._export_html)
        export_menu.add_command(label="Export to PNG...", command=self._export_png)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Link CSVs...", command=self._show_link_dialog)
        tools_menu.add_command(label="Compare CSVs...", command=self._show_compare_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label="Time Column Settings...", 
                              command=self._show_time_column_dialog)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)
        
    def _create_main_layout(self):
        """Create the main application layout with resizable panes"""
        # Main horizontal paned window (sidebar | plot)
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left sidebar (vertical paned window)
        self.sidebar_paned = ttk.PanedWindow(self.main_paned, orient=tk.VERTICAL)
        self.main_paned.add(self.sidebar_paned, weight=0)
        
        # Create sidebar panels
        self._create_csv_panel()
        self._create_signals_panel()
        self._create_assigned_panel()
        
        # Right side: Plot area
        self.plot_frame = ttk.Frame(self.main_paned, style="Card.TFrame")
        self.main_paned.add(self.plot_frame, weight=1)
        
        self._create_plot_area()
        
    def _create_csv_panel(self):
        """Create CSV files panel"""
        panel = ttk.Frame(self.sidebar_paned, style="Card.TFrame")
        self.sidebar_paned.add(panel, weight=0)
        
        # Header
        header = ttk.Frame(panel, style="CardHeader.TFrame")
        header.pack(fill=tk.X)
        ttk.Label(header, text="📁 Data Sources", style="CardHeader.TLabel").pack(
            side=tk.LEFT, padx=10, pady=5)
        
        ttk.Button(header, text="Clear", width=6, 
                  command=self._clear_csvs).pack(side=tk.RIGHT, padx=5, pady=3)
        ttk.Button(header, text="⏱", width=3,
                  command=self._show_time_column_dialog).pack(side=tk.RIGHT, pady=3)
        
        # Body
        body = ttk.Frame(panel, style="Card.TFrame")
        body.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Browse button
        ttk.Button(body, text="📂 Browse Files...", 
                  command=self._open_csv_dialog).pack(fill=tk.X, pady=2)
        
        # CSV list
        self.csv_listbox = tk.Listbox(body, height=4, 
                                      bg=self.current_theme.input_bg,
                                      fg=self.current_theme.fg,
                                      selectbackground=self.current_theme.accent,
                                      borderwidth=1, relief="solid")
        self.csv_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.csv_listbox.bind("<Delete>", lambda e: self._delete_selected_csv())
        
    def _create_signals_panel(self):
        """Create signals tree panel"""
        panel = ttk.Frame(self.sidebar_paned, style="Card.TFrame")
        self.sidebar_paned.add(panel, weight=1)
        
        # Header
        header = ttk.Frame(panel, style="CardHeader.TFrame")
        header.pack(fill=tk.X)
        ttk.Label(header, text="📶 Signals", style="CardHeader.TLabel").pack(
            side=tk.LEFT, padx=10, pady=5)
        
        ttk.Button(header, text="🔗", width=3,
                  command=self._show_link_dialog).pack(side=tk.RIGHT, padx=2, pady=3)
        ttk.Button(header, text="📊", width=3,
                  command=self._show_compare_dialog).pack(side=tk.RIGHT, pady=3)
        
        # Body
        body = ttk.Frame(panel, style="Card.TFrame")
        body.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Search
        search_frame = ttk.Frame(body)
        search_frame.pack(fill=tk.X, pady=2)
        
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search_entry.insert(0, "Search...")
        search_entry.bind("<FocusIn>", lambda e: e.widget.delete(0, tk.END) 
                         if e.widget.get() == "Search..." else None)
        search_entry.bind("<KeyRelease>", lambda e: self._filter_signals_safe())
        
        # Target info
        self.target_label = ttk.Label(body, text="Assign → Tab 1, Subplot 1",
                                      foreground=self.current_theme.accent)
        self.target_label.pack(anchor=tk.W, pady=2)
        
        # Highlighted count
        highlight_frame = ttk.Frame(body)
        highlight_frame.pack(fill=tk.X, pady=2)
        ttk.Label(highlight_frame, text="Selected for ops:").pack(side=tk.LEFT)
        self.highlight_count_label = ttk.Label(highlight_frame, text="0",
                                               foreground=self.current_theme.highlight)
        self.highlight_count_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(highlight_frame, text="⚙ Operate", width=10,
                  command=self._show_multi_ops_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(highlight_frame, text="Clear", width=6,
                  command=self._clear_highlights).pack(side=tk.LEFT)
        
        # Signal tree
        tree_frame = ttk.Frame(body)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.signal_tree = ttk.Treeview(tree_frame, show="tree", selectmode="none")
        self.signal_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, 
                                 command=self.signal_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.signal_tree.configure(yscrollcommand=scrollbar.set)
        
        # Bind events
        self.signal_tree.bind("<Double-1>", self._on_signal_double_click)
        self.signal_tree.bind("<Button-3>", self._on_signal_right_click)
        
    def _create_assigned_panel(self):
        """Create assigned signals panel"""
        panel = ttk.Frame(self.sidebar_paned, style="Card.TFrame")
        self.sidebar_paned.add(panel, weight=0)
        
        # Header
        header = ttk.Frame(panel, style="CardHeader.TFrame")
        header.pack(fill=tk.X)
        ttk.Label(header, text="📋 Assigned", style="CardHeader.TLabel").pack(
            side=tk.LEFT, padx=10, pady=5)
        
        # Body
        body = ttk.Frame(panel, style="Card.TFrame")
        body.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Mode toggle
        mode_frame = ttk.Frame(body)
        mode_frame.pack(fill=tk.X, pady=5)
        
        self.mode_var = tk.StringVar(value="time")
        ttk.Radiobutton(mode_frame, text="📈 Time", variable=self.mode_var,
                       value="time", command=self._on_mode_change).pack(side=tk.LEFT)
        ttk.Radiobutton(mode_frame, text="⚡ X-Y", variable=self.mode_var,
                       value="xy", command=self._on_mode_change).pack(side=tk.LEFT)
        
        # X-axis selector (for XY mode)
        self.xy_frame = ttk.Frame(body)
        ttk.Label(self.xy_frame, text="X-Axis:").pack(side=tk.LEFT)
        self.xy_x_var = tk.StringVar(value="time")
        self.xy_x_combo = ttk.Combobox(self.xy_frame, textvariable=self.xy_x_var,
                                       state="readonly", width=20)
        self.xy_x_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.xy_x_combo.bind("<<ComboboxSelected>>", self._on_x_axis_change)
        
        # Subplot metadata
        meta_frame = ttk.LabelFrame(body, text="Subplot Info")
        meta_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(meta_frame, text="Title:").grid(row=0, column=0, sticky="w", padx=2)
        self.subplot_title_var = tk.StringVar()
        self.subplot_title_entry = ttk.Entry(meta_frame, textvariable=self.subplot_title_var)
        self.subplot_title_entry.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        self.subplot_title_entry.bind("<FocusOut>", self._save_subplot_metadata)
        
        meta_frame.columnconfigure(1, weight=1)
        
        # Assigned signals list
        self.assigned_listbox = tk.Listbox(body, height=6,
                                           bg=self.current_theme.input_bg,
                                           fg=self.current_theme.fg,
                                           selectmode=tk.EXTENDED,
                                           borderwidth=1, relief="solid")
        self.assigned_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.assigned_listbox.bind("<Double-1>", self._on_assigned_double_click)
        
        # Display options
        options_frame = ttk.Frame(body)
        options_frame.pack(fill=tk.X, pady=2)
        
        self.show_markers_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Markers", 
                       variable=self.show_markers_var,
                       command=self._update_plot).pack(side=tk.LEFT)
        
        self.normalize_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Normalize",
                       variable=self.normalize_var,
                       command=self._update_plot).pack(side=tk.LEFT)
        
        # Remove button
        ttk.Button(body, text="🗑 Remove Selected",
                  command=self._remove_selected_signals).pack(fill=tk.X, pady=5)
        
    def _create_plot_area(self):
        """Create the matplotlib plot area with tabs"""
        # TOP Toolbar frame (above tabs)
        top_toolbar = ttk.Frame(self.plot_frame)
        top_toolbar.pack(fill=tk.X, side=tk.TOP, pady=2)
        
        # Session buttons
        ttk.Button(top_toolbar, text="💾 Save", width=8,
                  command=self._save_session).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_toolbar, text="📂 Load", width=8,
                  command=self._load_session).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(top_toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Refresh and streaming  
        ttk.Button(top_toolbar, text="🔄 Refresh", width=10,
                  command=self._refresh_csvs).pack(side=tk.LEFT, padx=2)
        
        self.stream_btn = ttk.Button(top_toolbar, text="▶ Stream", width=10,
                                    command=self._toggle_streaming)
        self.stream_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(top_toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Layout controls
        ttk.Label(top_toolbar, text="Layout:").pack(side=tk.LEFT, padx=2)
        
        self.rows_var = tk.IntVar(value=1)
        rows_spin = ttk.Spinbox(top_toolbar, from_=1, to=4, width=3,
                               textvariable=self.rows_var,
                               command=self._on_layout_change)
        rows_spin.pack(side=tk.LEFT)
        
        ttk.Label(top_toolbar, text="×").pack(side=tk.LEFT)
        
        self.cols_var = tk.IntVar(value=1)
        cols_spin = ttk.Spinbox(top_toolbar, from_=1, to=4, width=3,
                               textvariable=self.cols_var,
                               command=self._on_layout_change)
        cols_spin.pack(side=tk.LEFT)
        
        # Subplot selector
        ttk.Label(top_toolbar, text="  Subplot:").pack(side=tk.LEFT, padx=2)
        self.subplot_var = tk.IntVar(value=1)
        self.subplot_spin = ttk.Spinbox(top_toolbar, from_=1, to=16, width=3,
                                       textvariable=self.subplot_var,
                                       command=self._on_subplot_change)
        self.subplot_spin.pack(side=tk.LEFT)
        
        ttk.Separator(top_toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Link axes checkbox
        self.link_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top_toolbar, text="Link Axes", variable=self.link_var,
                       command=self._toggle_link_axes).pack(side=tk.LEFT, padx=5)
        
        # Cursor checkbox
        self.cursor_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top_toolbar, text="Cursor", variable=self.cursor_var,
                       command=self._toggle_cursor).pack(side=tk.LEFT)
        
        # Tab buttons on right
        ttk.Button(top_toolbar, text="+ Tab", width=6,
                  command=self._add_tab).pack(side=tk.RIGHT, padx=2)
        ttk.Button(top_toolbar, text="− Tab", width=6,
                  command=self._remove_current_tab).pack(side=tk.RIGHT)
        
        ttk.Button(top_toolbar, text="📝 Note",
                  command=self._add_annotation).pack(side=tk.RIGHT, padx=5)
        
        # Tab notebook (main area)
        self.tab_notebook = ttk.Notebook(self.plot_frame)
        self.tab_notebook.pack(fill=tk.BOTH, expand=True, pady=2)
        self.tab_notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        # Store figure references per tab
        self.tab_figures: Dict[int, Tuple[Figure, FigureCanvasTkAgg]] = {}
        
        # Add initial tab
        self._add_tab()
        
    def _add_tab(self, name: str = None):
        """Add a new tab"""
        # Initialize tab_figures if not exists
        if not hasattr(self, 'tab_figures'):
            self.tab_figures = {}
            
        tab_idx = len(self.tab_figures)
        tab_name = name or f"Tab {tab_idx + 1}"
        
        # Create tab frame
        tab_frame = ttk.Frame(self.tab_notebook)
        self.tab_notebook.add(tab_frame, text=tab_name)
        
        # Create figure for this tab
        fig, canvas = self._create_tab_figure(tab_frame, tab_idx)
        
        # Store figure reference
        self.tab_figures[tab_idx] = (fig, canvas)
        
        # Set as current figure
        self.figure = fig
        self.canvas = canvas
        self.axes = []
        
        # Add tab config (avoid duplicates)
        if hasattr(self, 'tabs'):
            # Only add if not already there
            if len(self.tabs) <= tab_idx:
                self.tabs.append(TabConfig(name=tab_name))
            
        # Select the new tab
        self.tab_notebook.select(tab_idx)
        self.current_tab_idx = tab_idx
        
        # Update plot
        self.root.after(50, self._update_plot)  # Slight delay to ensure canvas is ready
        
    def _create_tab_figure(self, parent, tab_idx: int) -> Tuple[Figure, FigureCanvasTkAgg]:
        """Create matplotlib figure in a tab"""
        # Create figure with dark background
        fig = Figure(figsize=(10, 6), dpi=100, facecolor=self.current_theme.plot_bg)
        
        # Create canvas
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)
        
        # Add matplotlib navigation toolbar
        toolbar_frame = ttk.Frame(parent)
        toolbar_frame.pack(fill=tk.X, side=tk.BOTTOM)
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()
        
        # Connect click event for cursor
        canvas.mpl_connect('button_press_event', self._on_plot_click)
        
        # Initial draw
        canvas.draw()
        
        return fig, canvas
        
    # ========================================================================
    # Event Handlers
    # ========================================================================
    
    def _bind_shortcuts(self):
        """Bind keyboard shortcuts"""
        self.root.bind("<Control-o>", lambda e: self._open_csv_dialog())
        self.root.bind("<Control-s>", lambda e: self._save_session())
        self.root.bind("<Control-l>", lambda e: self._load_session())
        self.root.bind("<Control-t>", lambda e: self._toggle_theme())
        self.root.bind("<F5>", lambda e: self._refresh_csvs())
        self.root.bind("<Escape>", lambda e: self._clear_selection())
        
    def _on_tab_changed(self, event):
        """Handle tab change"""
        try:
            tab_idx = self.tab_notebook.index(self.tab_notebook.select())
            self.current_tab_idx = tab_idx
            
            # Switch to this tab's figure
            if hasattr(self, 'tab_figures') and tab_idx in self.tab_figures:
                self.figure, self.canvas = self.tab_figures[tab_idx]
                self.axes = []
                
            self._update_ui_for_tab()
        except Exception:
            pass  # Tab may not exist yet during initialization
        
    def _on_layout_change(self):
        """Handle layout (rows/cols) change"""
        rows = self.rows_var.get()
        cols = self.cols_var.get()
        
        tab = self.tabs[self.current_tab_idx]
        tab.rows = rows
        tab.cols = cols
        
        # Update subplot spinner max
        self.subplot_spin.configure(to=rows * cols)
        if self.subplot_var.get() > rows * cols:
            self.subplot_var.set(1)
            
        self._update_plot()
        
    def _on_subplot_change(self):
        """Handle subplot selection change"""
        self.current_subplot_idx = self.subplot_var.get() - 1
        self._update_assigned_list()
        self._update_target_label()
        self._update_plot()  # To highlight selected subplot
        
    def _on_mode_change(self):
        """Handle Time/XY mode change"""
        mode = self.mode_var.get()
        tab = self.tabs[self.current_tab_idx]
        
        # Ensure subplot config exists
        if self.current_subplot_idx not in tab.subplots:
            tab.subplots[self.current_subplot_idx] = SubplotConfig()
        
        tab.subplots[self.current_subplot_idx].mode = mode
        
        # Show/hide XY controls
        if mode == "xy":
            self.xy_frame.pack(fill=tk.X, after=self.mode_var)
            self._update_xy_combo()
        else:
            self.xy_frame.pack_forget()
            
        self._update_plot()
        
    def _on_x_axis_change(self, event=None):
        """Handle X-axis signal selection change"""
        tab = self.tabs[self.current_tab_idx]
        if self.current_subplot_idx in tab.subplots:
            tab.subplots[self.current_subplot_idx].x_signal_key = self.xy_x_var.get()
        self._update_plot()
        
    def _on_signal_double_click(self, event):
        """Handle double-click on signal in tree (assign/unassign)"""
        item = self.signal_tree.identify_row(event.y)
        if not item:
            return
            
        # Get signal info from item
        values = self.signal_tree.item(item)
        tags = values.get("tags", [])
        
        if "signal" in tags:
            # Extract csv_idx and signal_name from item ID
            parts = item.split(":")
            if len(parts) >= 2:
                csv_idx = int(parts[0])
                signal_name = ":".join(parts[1:])
                self._toggle_signal_assignment(csv_idx, signal_name)
                
    def _on_signal_right_click(self, event):
        """Show context menu for signal"""
        item = self.signal_tree.identify_row(event.y)
        if not item:
            return
            
        values = self.signal_tree.item(item)
        tags = values.get("tags", [])
        
        if "signal" in tags:
            parts = item.split(":")
            if len(parts) >= 2:
                csv_idx = int(parts[0])
                signal_name = ":".join(parts[1:])
                self._show_signal_context_menu(event, csv_idx, signal_name)
                
    def _on_assigned_double_click(self, event):
        """Show properties dialog for assigned signal"""
        selection = self.assigned_listbox.curselection()
        if selection:
            idx = selection[0]
            tab = self.tabs[self.current_tab_idx]
            sp_config = tab.subplots.get(self.current_subplot_idx)
            if sp_config and idx < len(sp_config.signals):
                sig = sp_config.signals[idx]
                self._show_properties_dialog(sig.csv_idx, sig.signal_name)
                
    def _on_plot_click(self, event):
        """Handle click on plot - set cursor position or select subplot"""
        if event.inaxes is None:
            return
            
        # Find which subplot was clicked
        for idx, ax in enumerate(self.axes):
            if event.inaxes == ax:
                # Check if this is a subplot selection click (middle button)
                if event.button == 2:  # Middle click
                    self.subplot_var.set(idx + 1)
                    self._on_subplot_change()
                else:
                    # Left click - set cursor position
                    if self.cursor_enabled:
                        self.cursor_x = event.xdata
                        self._update_plot()
                break
                
    # ========================================================================
    # Data Management
    # ========================================================================
    
    def _open_csv_dialog(self):
        """Open file dialog to select CSV files"""
        files = filedialog.askopenfilenames(
            title="Select CSV Files",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=os.path.expanduser("~")
        )
        
        if files:
            for f in files:
                if f not in self.csv_files:
                    self._load_csv(f)
                    
    def _load_csv(self, filepath: str):
        """Load a CSV file"""
        try:
            df = pd.read_csv(filepath, low_memory=False)
            
            # Ensure Time column exists
            if "Time" not in df.columns:
                time_cols = [c for c in df.columns 
                           if c.lower() in ['time', 't', 'timestamp', 'datetime']]
                if time_cols:
                    df.rename(columns={time_cols[0]: 'Time'}, inplace=True)
                else:
                    df.rename(columns={df.columns[0]: 'Time'}, inplace=True)
            
            self.csv_files.append(filepath)
            self.data_tables.append(df)
            
            # Update CSV listbox
            display_name = get_csv_display_name(filepath, self.csv_files)
            self.csv_listbox.insert(tk.END, f"📄 {display_name} ({len(df)} rows)")
            
            # Update signal tree
            self._update_signal_tree()
            
            print(f"[OK] Loaded: {os.path.basename(filepath)} ({len(df)} rows)")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV:\n{str(e)}")
            
    def _clear_csvs(self):
        """Clear all loaded CSVs"""
        self.csv_files.clear()
        self.data_tables.clear()
        self.csv_listbox.delete(0, tk.END)
        self._update_signal_tree()
        self._update_plot()
        
    def _delete_selected_csv(self):
        """Delete selected CSV from list"""
        selection = self.csv_listbox.curselection()
        if selection:
            idx = selection[0]
            self.csv_files.pop(idx)
            self.data_tables.pop(idx)
            self.csv_listbox.delete(idx)
            self._update_signal_tree()
            self._update_plot()
            
    def _refresh_csvs(self):
        """Refresh all CSVs from disk"""
        for idx, filepath in enumerate(self.csv_files):
            if os.path.exists(filepath):
                try:
                    df = pd.read_csv(filepath, low_memory=False)
                    if "Time" not in df.columns:
                        df.rename(columns={df.columns[0]: 'Time'}, inplace=True)
                    self.data_tables[idx] = df
                    print(f"[OK] Refreshed: {os.path.basename(filepath)}")
                except Exception as e:
                    print(f"[ERROR] Refresh failed for {filepath}: {e}")
        
        self._update_signal_tree()
        self._update_plot()
        
    # ========================================================================
    # Signal Management
    # ========================================================================
    
    def _update_signal_tree(self):
        """Update the signal tree view"""
        # Clear existing items
        for item in self.signal_tree.get_children():
            self.signal_tree.delete(item)
            
        # Add CSV nodes
        for csv_idx, filepath in enumerate(self.csv_files):
            if csv_idx >= len(self.data_tables):
                continue
                
            df = self.data_tables[csv_idx]
            if df is None:
                continue
                
            display_name = get_csv_display_name(filepath, self.csv_files)
            signals = [c for c in df.columns if c.lower() != 'time']
            
            # Add CSV parent node
            csv_node = self.signal_tree.insert("", tk.END, iid=f"csv_{csv_idx}",
                                               text=f"📁 {display_name} ({len(signals)})",
                                               open=True, tags=("csv",))
            
            # Add ALL signal nodes (no limit - user requested)
            for sig_idx, sig in enumerate(signals):
                item_id = f"{csv_idx}:{sig}"
                # Check if assigned or highlighted
                is_assigned = self._is_signal_assigned(csv_idx, sig)
                sig_key = make_signal_key(csv_idx, sig)
                is_highlighted = sig_key in self.highlighted_signals
                
                # Build prefix
                prefix = ""
                if is_assigned:
                    prefix = "✓ "
                if is_highlighted:
                    prefix = "★ " + prefix
                    
                tag = "assigned" if is_assigned else ("highlighted" if is_highlighted else "signal")
                
                self.signal_tree.insert(csv_node, tk.END, iid=item_id,
                                        text=f"  {prefix}{sig}",
                                        tags=(tag, "signal"))
        
        # Add derived signals
        if self.derived_signals:
            derived_node = self.signal_tree.insert("", tk.END, iid="derived",
                                                   text="🧮 Derived Signals",
                                                   open=True, tags=("derived",))
            for name in self.derived_signals:
                self.signal_tree.insert(derived_node, tk.END, iid=f"-1:{name}",
                                        text=f"  {name}", tags=("signal",))
                                        
    def _filter_signals_safe(self):
        """Safe filter that checks if signal_tree exists"""
        if hasattr(self, 'signal_tree'):
            self._filter_signals()
            
    def _filter_signals(self):
        """Filter signals in tree based on search"""
        if not hasattr(self, 'signal_tree'):
            return
            
        search = self.search_var.get().lower()
        if search == "search..." or not search:
            self._update_signal_tree()
            return
            
        # Filter by search term
        for csv_node in self.signal_tree.get_children():
            has_match = False
            for item in self.signal_tree.get_children(csv_node):
                text = self.signal_tree.item(item, "text").lower()
                if search in text:
                    has_match = True
                else:
                    self.signal_tree.detach(item)
            # Hide CSV if no matches
            if not has_match:
                self.signal_tree.detach(csv_node)
                
    def _is_signal_assigned(self, csv_idx: int, signal_name: str) -> bool:
        """Check if a signal is assigned to current subplot"""
        tab = self.tabs[self.current_tab_idx]
        sp_config = tab.subplots.get(self.current_subplot_idx)
        if not sp_config:
            return False
        return any(s.csv_idx == csv_idx and s.signal_name == signal_name 
                  for s in sp_config.signals)
                  
    def _toggle_signal_assignment(self, csv_idx: int, signal_name: str):
        """Toggle signal assignment to current subplot"""
        tab = self.tabs[self.current_tab_idx]
        
        # Ensure subplot config exists
        if self.current_subplot_idx not in tab.subplots:
            tab.subplots[self.current_subplot_idx] = SubplotConfig()
            
        sp_config = tab.subplots[self.current_subplot_idx]
        
        # Check if already assigned
        existing = None
        for i, sig in enumerate(sp_config.signals):
            if sig.csv_idx == csv_idx and sig.signal_name == signal_name:
                existing = i
                break
                
        if existing is not None:
            # Remove assignment
            sp_config.signals.pop(existing)
        else:
            # Add assignment with default color
            color_idx = len(sp_config.signals) % len(SIGNAL_COLORS)
            sp_config.signals.append(SignalAssignment(
                csv_idx=csv_idx,
                signal_name=signal_name,
                color=SIGNAL_COLORS[color_idx],
                display_name=signal_name
            ))
            
        self._update_signal_tree()
        self._update_assigned_list()
        self._update_plot()
        
    def _remove_selected_signals(self):
        """Remove selected signals from current subplot"""
        selection = list(self.assigned_listbox.curselection())
        if not selection:
            return
            
        tab = self.tabs[self.current_tab_idx]
        sp_config = tab.subplots.get(self.current_subplot_idx)
        if not sp_config:
            return
            
        # Remove in reverse order to maintain indices
        for idx in reversed(selection):
            if idx < len(sp_config.signals):
                sp_config.signals.pop(idx)
                
        self._update_signal_tree()
        self._update_assigned_list()
        self._update_plot()
        
    def _clear_current_subplot(self):
        """Clear all signals from current subplot"""
        tab = self.tabs[self.current_tab_idx]
        if self.current_subplot_idx in tab.subplots:
            tab.subplots[self.current_subplot_idx].signals.clear()
            
        self._update_signal_tree()
        self._update_assigned_list()
        self._update_plot()
        
    # ========================================================================
    # Plotting
    # ========================================================================
    
    def _update_plot(self):
        """Update the matplotlib plot"""
        if not self.figure or not self.canvas:
            return
            
        # Guard against invalid tab index
        if self.current_tab_idx >= len(self.tabs):
            return
            
        tab = self.tabs[self.current_tab_idx]
        rows, cols = tab.rows, tab.cols
        t = self.current_theme
        
        # Clear figure
        self.figure.clear()
        self.axes.clear()
        
        # Create subplots
        for sp_idx in range(rows * cols):
            ax = self.figure.add_subplot(rows, cols, sp_idx + 1)
            self.axes.append(ax)
            
            # Style subplot
            ax.set_facecolor(t.plot_bg)
            ax.tick_params(colors=t.plot_fg, labelsize=8)
            ax.xaxis.label.set_color(t.plot_fg)
            ax.yaxis.label.set_color(t.plot_fg)
            ax.grid(True, color=t.grid_color, alpha=0.3, linewidth=0.5)
            
            # Highlight selected subplot
            if sp_idx == self.current_subplot_idx:
                for spine in ax.spines.values():
                    spine.set_color(t.accent)
                    spine.set_linewidth(2)
            else:
                for spine in ax.spines.values():
                    spine.set_color(t.grid_color)
                    spine.set_linewidth(1)
            
            # Get subplot config
            sp_config = tab.subplots.get(sp_idx, SubplotConfig())
            
            # Set title
            title = sp_config.title or f"Subplot {sp_idx + 1}"
            ax.set_title(title, color=t.plot_fg, fontsize=9)
            
            # Plot signals
            self._plot_signals(ax, sp_config, sp_idx)
            
            # Draw annotations
            if sp_config.annotations:
                self._draw_annotations(ax, sp_config)
            
            # Add legend if signals present
            if sp_config.signals:
                ax.legend(loc='upper right', fontsize=7, 
                         facecolor=t.card_bg, edgecolor=t.border,
                         labelcolor=t.fg)
        
        # Add cursor if enabled
        if self.cursor_enabled and self.cursor_x is not None:
            self._draw_cursor()
            
        # Adjust layout and draw
        self.figure.tight_layout()
        self.canvas.draw()
        
    def _plot_signals(self, ax: plt.Axes, sp_config: SubplotConfig, sp_idx: int):
        """Plot signals on an axis"""
        if not sp_config.signals:
            ax.set_xlabel("Time", fontsize=8)
            ax.set_ylabel("Value", fontsize=8)
            return
            
        # Get X-axis data
        x_label = "Time"
        
        for sig in sp_config.signals:
            csv_idx = sig.csv_idx
            signal_name = sig.signal_name
            
            # Get data
            if csv_idx == -1:
                # Derived signal
                if signal_name in self.derived_signals:
                    ds = self.derived_signals[signal_name]
                    x_data = np.array(ds.get("time", []))
                    y_data = np.array(ds.get("data", []))
                else:
                    continue
            elif 0 <= csv_idx < len(self.data_tables):
                df = self.data_tables[csv_idx]
                if df is None or signal_name not in df.columns:
                    continue
                    
                # Get time column
                time_col = self.time_columns.get(csv_idx, "Time")
                if time_col not in df.columns:
                    time_col = df.columns[0]
                    
                x_data = df[time_col].values
                y_data = df[signal_name].values
            else:
                continue
                
            # Apply scale
            if sig.scale != 1.0:
                y_data = y_data * sig.scale
                
            # Apply time offset
            if sig.time_offset != 0:
                x_data = x_data + sig.time_offset
                
            # Handle XY mode
            if sp_config.mode == "xy" and sp_config.x_signal_key != "time":
                x_key = sp_config.x_signal_key
                x_csv, x_sig = parse_signal_key(x_key)
                if 0 <= x_csv < len(self.data_tables):
                    x_df = self.data_tables[x_csv]
                    if x_df is not None and x_sig in x_df.columns:
                        x_data = x_df[x_sig].values
                        x_label = x_sig
                        
            # Normalize if enabled
            if self.normalize_var.get() and len(y_data) > 0:
                y_min, y_max = np.nanmin(y_data), np.nanmax(y_data)
                if y_max != y_min:
                    y_data = (y_data - y_min) / (y_max - y_min)
            
            # Plot
            display_name = sig.display_name or signal_name
            line_width = sig.width
            
            # Use thinner lines for large datasets
            if len(x_data) > 10000:
                line_width = 0.5
                
            if sig.is_state:
                # State signal - step plot
                ax.step(x_data, y_data, where='post', 
                       color=sig.color, linewidth=line_width, label=display_name)
            else:
                # Regular line plot
                marker = 'o' if self.show_markers_var.get() and len(x_data) < 1000 else None
                markersize = 2 if marker else None
                ax.plot(x_data, y_data, color=sig.color, linewidth=line_width,
                       label=display_name, marker=marker, markersize=markersize)
                       
        ax.set_xlabel(x_label, fontsize=8)
        ax.set_ylabel("Value", fontsize=8)
        
    def _draw_cursor(self):
        """Draw vertical cursor line on all subplots"""
        if self.cursor_x is None:
            return
            
        for ax in self.axes:
            ax.axvline(x=self.cursor_x, color='#ff6b6b', linewidth=1.5, 
                      linestyle='-', alpha=0.8)
            
            # Add cursor annotation
            ylim = ax.get_ylim()
            ax.annotate(f't={self.cursor_x:.4f}', 
                       xy=(self.cursor_x, ylim[1]),
                       xytext=(5, -5), textcoords='offset points',
                       fontsize=7, color='#ff6b6b',
                       bbox=dict(boxstyle='round,pad=0.3', 
                                facecolor='#282828', edgecolor='#ff6b6b'))
                                
    # ========================================================================
    # UI Updates
    # ========================================================================
    
    def _update_target_label(self):
        """Update the 'Assign →' label"""
        self.target_label.config(
            text=f"Assign → Tab {self.current_tab_idx + 1}, Subplot {self.current_subplot_idx + 1}"
        )
        
    def _update_assigned_list(self):
        """Update the assigned signals listbox"""
        self.assigned_listbox.delete(0, tk.END)
        
        tab = self.tabs[self.current_tab_idx]
        sp_config = tab.subplots.get(self.current_subplot_idx)
        
        if not sp_config:
            return
            
        for sig in sp_config.signals:
            if sig.csv_idx == -1:
                label = f"{sig.display_name or sig.signal_name} (Derived)"
            elif sig.csv_idx < len(self.csv_files):
                csv_name = os.path.splitext(os.path.basename(self.csv_files[sig.csv_idx]))[0]
                label = f"{sig.display_name or sig.signal_name} ({csv_name})"
            else:
                label = f"{sig.display_name or sig.signal_name} (C{sig.csv_idx + 1})"
                
            self.assigned_listbox.insert(tk.END, label)
            
        # Update mode toggle
        self.mode_var.set(sp_config.mode)
        
        # Update XY combo if in XY mode
        if sp_config.mode == "xy":
            self._update_xy_combo()
            self.xy_frame.pack(fill=tk.X)
        else:
            self.xy_frame.pack_forget()
            
        # Update subplot title
        self.subplot_title_var.set(sp_config.title)
        
    def _update_xy_combo(self):
        """Update X-axis signal combobox"""
        options = ["time"]
        
        tab = self.tabs[self.current_tab_idx]
        sp_config = tab.subplots.get(self.current_subplot_idx)
        
        if sp_config:
            for sig in sp_config.signals:
                key = make_signal_key(sig.csv_idx, sig.signal_name)
                options.append(key)
                
        self.xy_x_combo['values'] = options
        
        if sp_config and sp_config.x_signal_key:
            self.xy_x_var.set(sp_config.x_signal_key)
            
    def _update_ui_for_tab(self):
        """Update UI when tab changes"""
        if self.current_tab_idx >= len(self.tabs):
            return
            
        tab = self.tabs[self.current_tab_idx]
        self.rows_var.set(tab.rows)
        self.cols_var.set(tab.cols)
        
        # Reset subplot to 1 when changing tabs
        self.subplot_var.set(1)
        self.current_subplot_idx = 0
        
        self._update_assigned_list()
        self._update_target_label()
        self._update_plot()
        
    def _save_subplot_metadata(self, event=None):
        """Save subplot metadata from entry fields"""
        tab = self.tabs[self.current_tab_idx]
        if self.current_subplot_idx not in tab.subplots:
            tab.subplots[self.current_subplot_idx] = SubplotConfig()
            
        tab.subplots[self.current_subplot_idx].title = self.subplot_title_var.get()
        self._update_plot()
        
    # ========================================================================
    # Dialogs
    # ========================================================================
    
    def _show_properties_dialog(self, csv_idx: int, signal_name: str):
        """Show signal properties dialog"""
        key = make_signal_key(csv_idx, signal_name)
        props = self.signal_properties.get(key, {})
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Properties: {signal_name}")
        dialog.geometry("350x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Create form
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Display name
        ttk.Label(frame, text="Display Name:").grid(row=0, column=0, sticky="w", pady=5)
        name_var = tk.StringVar(value=props.get('display_name', signal_name))
        ttk.Entry(frame, textvariable=name_var).grid(row=0, column=1, sticky="ew", pady=5)
        
        # Scale
        ttk.Label(frame, text="Scale Factor:").grid(row=1, column=0, sticky="w", pady=5)
        scale_var = tk.DoubleVar(value=props.get('scale', 1.0))
        ttk.Entry(frame, textvariable=scale_var).grid(row=1, column=1, sticky="ew", pady=5)
        
        # Color
        ttk.Label(frame, text="Color:").grid(row=2, column=0, sticky="w", pady=5)
        color_var = tk.StringVar(value=props.get('color', SIGNAL_COLORS[0]))
        color_frame = ttk.Frame(frame)
        color_frame.grid(row=2, column=1, sticky="ew", pady=5)
        
        color_label = tk.Label(color_frame, bg=color_var.get(), width=5, height=1)
        color_label.pack(side=tk.LEFT, padx=5)
        
        def pick_color():
            color = colorchooser.askcolor(color_var.get())[1]
            if color:
                color_var.set(color)
                color_label.configure(bg=color)
                
        ttk.Button(color_frame, text="Choose...", command=pick_color).pack(side=tk.LEFT)
        
        # Line width
        ttk.Label(frame, text="Line Width:").grid(row=3, column=0, sticky="w", pady=5)
        width_var = tk.DoubleVar(value=props.get('width', 1.5))
        ttk.Spinbox(frame, from_=0.5, to=5, increment=0.5, 
                   textvariable=width_var).grid(row=3, column=1, sticky="ew", pady=5)
        
        # Time offset
        ttk.Label(frame, text="Time Offset (sec):").grid(row=4, column=0, sticky="w", pady=5)
        offset_var = tk.DoubleVar(value=props.get('time_offset', 0.0))
        ttk.Entry(frame, textvariable=offset_var).grid(row=4, column=1, sticky="ew", pady=5)
        
        # State signal checkbox
        state_var = tk.BooleanVar(value=props.get('is_state', False))
        ttk.Checkbutton(frame, text="State signal (step display)", 
                       variable=state_var).grid(row=5, column=0, columnspan=2, 
                                                sticky="w", pady=10)
        
        frame.columnconfigure(1, weight=1)
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        def apply():
            # Save properties
            self.signal_properties[key] = {
                'display_name': name_var.get(),
                'scale': scale_var.get(),
                'color': color_var.get(),
                'width': width_var.get(),
                'time_offset': offset_var.get(),
                'is_state': state_var.get(),
            }
            
            # Update assigned signal if present
            tab = self.tabs[self.current_tab_idx]
            sp_config = tab.subplots.get(self.current_subplot_idx)
            if sp_config:
                for sig in sp_config.signals:
                    if sig.csv_idx == csv_idx and sig.signal_name == signal_name:
                        sig.display_name = name_var.get()
                        sig.scale = scale_var.get()
                        sig.color = color_var.get()
                        sig.width = width_var.get()
                        sig.time_offset = offset_var.get()
                        sig.is_state = state_var.get()
                        break
            
            self._update_assigned_list()
            self._update_plot()
            dialog.destroy()
            
        ttk.Button(btn_frame, text="Apply", command=apply).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)
        
    def _show_signal_context_menu(self, event, csv_idx: int, signal_name: str):
        """Show right-click context menu for signal"""
        menu = tk.Menu(self.root, tearoff=0)
        
        is_assigned = self._is_signal_assigned(csv_idx, signal_name)
        sig_key = make_signal_key(csv_idx, signal_name)
        is_highlighted = sig_key in self.highlighted_signals
        
        # Assign/Remove
        if is_assigned:
            menu.add_command(label="✗ Remove from subplot", 
                           command=lambda: self._toggle_signal_assignment(csv_idx, signal_name))
        else:
            menu.add_command(label="✓ Assign to subplot",
                           command=lambda: self._toggle_signal_assignment(csv_idx, signal_name))
        
        menu.add_separator()
        
        # Highlight for multi-signal operations
        if is_highlighted:
            menu.add_command(label="★ Remove from selection",
                           command=lambda: self._toggle_highlight(csv_idx, signal_name))
        else:
            menu.add_command(label="☆ Select for A+B operation",
                           command=lambda: self._toggle_highlight(csv_idx, signal_name))
        
        menu.add_separator()
        
        # Single signal operations
        menu.add_command(label="📊 Properties...",
                        command=lambda: self._show_properties_dialog(csv_idx, signal_name))
        
        ops_menu = tk.Menu(menu, tearoff=0)
        ops_menu.add_command(label="Derivative (d/dt)",
                            command=lambda: self._compute_derived(csv_idx, signal_name, "derivative"))
        ops_menu.add_command(label="Integral (∫dt)",
                            command=lambda: self._compute_derived(csv_idx, signal_name, "integral"))
        ops_menu.add_command(label="Absolute |x|",
                            command=lambda: self._compute_derived(csv_idx, signal_name, "abs"))
        ops_menu.add_command(label="Square Root √x",
                            command=lambda: self._compute_derived(csv_idx, signal_name, "sqrt"))
        ops_menu.add_command(label="Negate -x",
                            command=lambda: self._compute_derived(csv_idx, signal_name, "negate"))
        menu.add_cascade(label="🧮 Single Signal Ops", menu=ops_menu)
        
        menu.tk_popup(event.x_root, event.y_root)
        
    def _toggle_highlight(self, csv_idx: int, signal_name: str):
        """Toggle highlight for multi-signal operations"""
        sig_key = make_signal_key(csv_idx, signal_name)
        
        if sig_key in self.highlighted_signals:
            self.highlighted_signals.remove(sig_key)
        else:
            self.highlighted_signals.append(sig_key)
            
        # Update count label
        self.highlight_count_label.config(text=str(len(self.highlighted_signals)))
        
        # Refresh tree to show highlight
        self._update_signal_tree()
        
    def _show_multi_ops_dialog(self):
        """Show multi-signal operations dialog"""
        if not self.highlighted_signals:
            messagebox.showinfo("Info", "No signals selected for operations.\n\n"
                              "Right-click signals and choose 'Select for operations'.")
            return
            
        dialog = tk.Toplevel(self.root)
        dialog.title("Multi-Signal Operations")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text=f"Selected signals: {len(self.highlighted_signals)}").pack()
        
        # Operation selector
        ttk.Label(frame, text="Operation:").pack(pady=10)
        op_var = tk.StringVar(value="add")
        ops = [("A + B", "add"), ("A - B", "sub"), ("A × B", "mul"), 
               ("A ÷ B", "div"), ("Norm", "norm"), ("Mean", "mean")]
        for label, val in ops:
            ttk.Radiobutton(frame, text=label, variable=op_var, value=val).pack(anchor=tk.W)
            
        # Result name
        ttk.Label(frame, text="Result Name:").pack(pady=10)
        name_var = tk.StringVar(value="result")
        ttk.Entry(frame, textvariable=name_var).pack(fill=tk.X)
        
        def compute():
            # Get signal data
            signals_data = []
            time_data = None
            
            for key in self.highlighted_signals:
                csv_idx, sig_name = parse_signal_key(key)
                if 0 <= csv_idx < len(self.data_tables):
                    df = self.data_tables[csv_idx]
                    if df is not None and sig_name in df.columns:
                        signals_data.append(df[sig_name].values)
                        if time_data is None:
                            time_col = self.time_columns.get(csv_idx, "Time")
                            time_data = df[time_col].values if time_col in df.columns else np.arange(len(df))
                            
            if len(signals_data) >= 2:
                result = calculate_multi_signal_operation(op_var.get(), signals_data)
                result_name = name_var.get()
                
                self.derived_signals[result_name] = {
                    'time': time_data,
                    'data': result,
                    'operation': op_var.get(),
                    'sources': self.highlighted_signals.copy()
                }
                
                self._update_signal_tree()
                messagebox.showinfo("Success", f"Created derived signal: {result_name}")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Need at least 2 signals with data")
                
        ttk.Button(frame, text="Compute", command=compute).pack(pady=20)
        
    def _show_link_dialog(self):
        """Show CSV linking dialog"""
        if len(self.csv_files) < 2:
            messagebox.showinfo("Info", "Need at least 2 CSVs to link.")
            return
            
        dialog = tk.Toplevel(self.root)
        dialog.title("Link CSV Files")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Select CSVs to link together:\n"
                 "(Same signal names will auto-assign together)").pack()
        
        # Checkboxes for each CSV
        csv_vars = []
        for idx, path in enumerate(self.csv_files):
            var = tk.BooleanVar()
            csv_vars.append(var)
            name = get_csv_display_name(path, self.csv_files)
            ttk.Checkbutton(frame, text=name, variable=var).pack(anchor=tk.W, pady=2)
            
        # Link name
        ttk.Label(frame, text="Group Name:").pack(pady=10)
        name_var = tk.StringVar(value=f"Link{len(self.links) + 1}")
        ttk.Entry(frame, textvariable=name_var).pack(fill=tk.X)
        
        def create_link():
            selected = [i for i, v in enumerate(csv_vars) if v.get()]
            if len(selected) < 2:
                messagebox.showwarning("Warning", "Select at least 2 CSVs")
                return
                
            self.links.append({
                'csv_indices': selected,
                'name': name_var.get()
            })
            dialog.destroy()
            
        ttk.Button(frame, text="Create Link", command=create_link).pack(pady=20)
        
    def _show_compare_dialog(self):
        """Show CSV comparison dialog"""
        if len(self.csv_files) < 2:
            messagebox.showinfo("Info", "Need at least 2 CSVs to compare.")
            return
            
        # Simple comparison - show in messagebox for now
        messagebox.showinfo("Compare CSVs", 
                          "CSV comparison feature.\n\n"
                          "Select CSVs in the sidebar and compare signals.")
                          
    def _show_time_column_dialog(self):
        """Show time column settings dialog"""
        if not self.csv_files:
            messagebox.showinfo("Info", "No CSVs loaded.")
            return
            
        dialog = tk.Toplevel(self.root)
        dialog.title("Time Column Settings")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Select which column to use as Time/X-axis for each CSV:").pack()
        
        combos = {}
        for idx, path in enumerate(self.csv_files):
            if idx >= len(self.data_tables):
                continue
                
            df = self.data_tables[idx]
            if df is None:
                continue
                
            row = ttk.Frame(frame)
            row.pack(fill=tk.X, pady=5)
            
            name = get_csv_display_name(path, self.csv_files)
            ttk.Label(row, text=name + ":", width=30, anchor=tk.W).pack(side=tk.LEFT)
            
            current = self.time_columns.get(idx, "Time")
            var = tk.StringVar(value=current)
            combo = ttk.Combobox(row, textvariable=var, values=list(df.columns), 
                                state="readonly")
            combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
            combos[idx] = var
            
        def apply():
            for idx, var in combos.items():
                self.time_columns[idx] = var.get()
            self._update_plot()
            dialog.destroy()
            
        ttk.Button(frame, text="Apply", command=apply).pack(pady=20)
        
    def _show_about(self):
        """Show about dialog"""
        messagebox.showinfo("About Signal Viewer Pro",
                          "Signal Viewer Pro v3.0 (Tkinter)\n\n"
                          "High-performance signal visualization tool.\n\n"
                          "Features:\n"
                          "• Multi-CSV loading\n"
                          "• Multi-tab, multi-subplot layouts\n"
                          "• Interactive time cursor\n"
                          "• Signal operations\n"
                          "• Session save/load\n"
                          "• Export to CSV/HTML/PNG")
                          
    # ========================================================================
    # Derived Signals
    # ========================================================================
    
    def _compute_derived(self, csv_idx: int, signal_name: str, operation: str):
        """Compute a derived signal"""
        if csv_idx < 0 or csv_idx >= len(self.data_tables):
            return
            
        df = self.data_tables[csv_idx]
        if df is None or signal_name not in df.columns:
            return
            
        time_col = self.time_columns.get(csv_idx, "Time")
        time_data = df[time_col].values if time_col in df.columns else np.arange(len(df))
        signal_data = df[signal_name].values
        
        result = calculate_derived_signal(operation, time_data, signal_data)
        result_name = f"{signal_name}_{operation}"
        
        self.derived_signals[result_name] = {
            'time': time_data,
            'data': result,
            'operation': operation,
            'source': signal_name
        }
        
        self._update_signal_tree()
        messagebox.showinfo("Success", f"Created: {result_name}")
        
    def _clear_highlights(self):
        """Clear highlighted signals"""
        self.highlighted_signals.clear()
        self.highlight_count_label.config(text="0")
        
    # ========================================================================
    # Annotations
    # ========================================================================
    
    def _add_annotation(self):
        """Add annotation at cursor position"""
        if self.cursor_x is None:
            messagebox.showinfo("Info", "Click on a plot first to set cursor position.")
            return
            
        text = simpledialog.askstring("Add Annotation", "Enter annotation text:",
                                     parent=self.root)
        if text:
            tab = self.tabs[self.current_tab_idx]
            if self.current_subplot_idx not in tab.subplots:
                tab.subplots[self.current_subplot_idx] = SubplotConfig()
                
            sp_config = tab.subplots[self.current_subplot_idx]
            
            # Get y-position from cursor click (use middle of plot)
            if self.current_subplot_idx < len(self.axes):
                ylim = self.axes[self.current_subplot_idx].get_ylim()
                y_pos = (ylim[0] + ylim[1]) / 2
            else:
                y_pos = 0
                
            sp_config.annotations.append(Annotation(
                x=self.cursor_x,
                y=y_pos,
                text=text
            ))
            
            self._update_plot()
            
    def _draw_annotations(self, ax: plt.Axes, sp_config: SubplotConfig):
        """Draw annotations on a subplot"""
        for ann in sp_config.annotations:
            ax.annotate(
                ann.text,
                xy=(ann.x, ann.y),
                xytext=(10, 10), textcoords='offset points',
                fontsize=8,
                color=ann.color,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#282828', 
                         edgecolor=ann.color, alpha=0.9),
                arrowprops=dict(arrowstyle='->', color=ann.color, lw=1)
            )
        
    # ========================================================================
    # Session/Template Management
    # ========================================================================
    
    def _save_session(self):
        """Save session to JSON file"""
        filepath = filedialog.asksaveasfilename(
            title="Save Session",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="signal_viewer_session.json"
        )
        
        if not filepath:
            return
            
        session = {
            'version': '3.0',
            'type': 'session',
            'csv_files': self.csv_files,
            'tabs': [
                {
                    'name': tab.name,
                    'rows': tab.rows,
                    'cols': tab.cols,
                    'subplots': {
                        str(k): {
                            'signals': [
                                {
                                    'csv_idx': s.csv_idx,
                                    'signal_name': s.signal_name,
                                    'color': s.color,
                                    'scale': s.scale,
                                    'width': s.width,
                                    'display_name': s.display_name,
                                    'time_offset': s.time_offset,
                                    'is_state': s.is_state,
                                }
                                for s in v.signals
                            ],
                            'title': v.title,
                            'caption': v.caption,
                            'mode': v.mode,
                            'x_signal_key': v.x_signal_key,
                        }
                        for k, v in tab.subplots.items()
                    }
                }
                for tab in self.tabs
            ],
            'derived_signals': self.derived_signals,
            'signal_properties': self.signal_properties,
            'time_columns': self.time_columns,
            'links': self.links,
            'theme': self.current_theme.name,
        }
        
        with open(filepath, 'w') as f:
            json.dump(session, f, indent=2, default=str)
            
        messagebox.showinfo("Success", "Session saved!")
        
    def _load_session(self):
        """Load session from JSON file"""
        filepath = filedialog.askopenfilename(
            title="Load Session",
            filetypes=[("JSON files", "*.json")]
        )
        
        if not filepath:
            return
            
        try:
            with open(filepath, 'r') as f:
                session = json.load(f)
                
            # Load CSVs
            self._clear_csvs()
            for csv_path in session.get('csv_files', []):
                if os.path.exists(csv_path):
                    self._load_csv(csv_path)
                    
            # Load tabs
            self.tabs.clear()
            for tab_data in session.get('tabs', []):
                tab = TabConfig(
                    name=tab_data.get('name', 'Tab'),
                    rows=tab_data.get('rows', 1),
                    cols=tab_data.get('cols', 1),
                )
                for sp_key, sp_data in tab_data.get('subplots', {}).items():
                    sp_config = SubplotConfig(
                        title=sp_data.get('title', ''),
                        caption=sp_data.get('caption', ''),
                        mode=sp_data.get('mode', 'time'),
                        x_signal_key=sp_data.get('x_signal_key', 'time'),
                    )
                    for sig_data in sp_data.get('signals', []):
                        sp_config.signals.append(SignalAssignment(**sig_data))
                    tab.subplots[int(sp_key)] = sp_config
                self.tabs.append(tab)
                
            # Load other settings
            self.derived_signals = session.get('derived_signals', {})
            self.signal_properties = session.get('signal_properties', {})
            self.time_columns = {int(k): v for k, v in session.get('time_columns', {}).items()}
            self.links = session.get('links', [])
            
            # Apply theme
            theme_name = session.get('theme', 'dark')
            self.current_theme = THEMES.get(theme_name, THEMES['dark'])
            self._apply_theme()
            
            # Update UI
            self._rebuild_tabs()
            self._update_signal_tree()
            self._update_ui_for_tab()
            
            messagebox.showinfo("Success", "Session loaded!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load session:\n{str(e)}")
            
    def _save_template(self):
        """Save layout template (without CSV file paths)"""
        filepath = filedialog.asksaveasfilename(
            title="Save Template",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="signal_viewer_template.json"
        )
        
        if not filepath:
            return
            
        template = {
            'version': '3.0',
            'type': 'template',
            'tabs': [
                {
                    'name': tab.name,
                    'rows': tab.rows,
                    'cols': tab.cols,
                    'subplots': {
                        str(k): {
                            'signal_names': [s.signal_name for s in v.signals],
                            'title': v.title,
                            'mode': v.mode,
                        }
                        for k, v in tab.subplots.items()
                    }
                }
                for tab in self.tabs
            ],
        }
        
        with open(filepath, 'w') as f:
            json.dump(template, f, indent=2)
            
        messagebox.showinfo("Success", "Template saved!")
        
    def _load_template(self):
        """Load layout template"""
        filepath = filedialog.askopenfilename(
            title="Load Template",
            filetypes=[("JSON files", "*.json")]
        )
        
        if not filepath:
            return
            
        try:
            with open(filepath, 'r') as f:
                template = json.load(f)
                
            if template.get('type') != 'template':
                messagebox.showwarning("Warning", "This is not a template file.")
                return
                
            # Apply template
            self.tabs.clear()
            for tab_data in template.get('tabs', []):
                tab = TabConfig(
                    name=tab_data.get('name', 'Tab'),
                    rows=tab_data.get('rows', 1),
                    cols=tab_data.get('cols', 1),
                )
                for sp_key, sp_data in tab_data.get('subplots', {}).items():
                    sp_config = SubplotConfig(
                        title=sp_data.get('title', ''),
                        mode=sp_data.get('mode', 'time'),
                    )
                    # Match signal names to loaded CSVs
                    for sig_name in sp_data.get('signal_names', []):
                        for csv_idx, df in enumerate(self.data_tables):
                            if df is not None and sig_name in df.columns:
                                color_idx = len(sp_config.signals) % len(SIGNAL_COLORS)
                                sp_config.signals.append(SignalAssignment(
                                    csv_idx=csv_idx,
                                    signal_name=sig_name,
                                    color=SIGNAL_COLORS[color_idx],
                                    display_name=sig_name
                                ))
                                break
                    tab.subplots[int(sp_key)] = sp_config
                self.tabs.append(tab)
                
            self._rebuild_tabs()
            self._update_ui_for_tab()
            messagebox.showinfo("Success", "Template applied!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template:\n{str(e)}")
            
    def _rebuild_tabs(self):
        """Rebuild tab notebook from self.tabs"""
        # Clear existing tabs
        for tab in self.tab_notebook.tabs():
            self.tab_notebook.forget(tab)
            
        # Recreate tabs
        for idx, tab in enumerate(self.tabs):
            tab_frame = ttk.Frame(self.tab_notebook)
            self.tab_notebook.add(tab_frame, text=tab.name)
            self._create_tab_figure(tab_frame, idx)
            
        self.current_tab_idx = 0
        
    # ========================================================================
    # Export Functions
    # ========================================================================
    
    def _export_csv(self):
        """Export signals to CSV"""
        filepath = filedialog.asksaveasfilename(
            title="Export to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        
        if not filepath:
            return
            
        # Collect all assigned signals
        export_data = {}
        tab = self.tabs[self.current_tab_idx]
        
        for sp_idx, sp_config in tab.subplots.items():
            for sig in sp_config.signals:
                if sig.csv_idx == -1:
                    if sig.signal_name in self.derived_signals:
                        ds = self.derived_signals[sig.signal_name]
                        export_data[sig.signal_name] = ds['data']
                        if 'Time' not in export_data:
                            export_data['Time'] = ds['time']
                elif 0 <= sig.csv_idx < len(self.data_tables):
                    df = self.data_tables[sig.csv_idx]
                    if df is not None and sig.signal_name in df.columns:
                        export_data[sig.signal_name] = df[sig.signal_name].values
                        if 'Time' not in export_data:
                            time_col = self.time_columns.get(sig.csv_idx, "Time")
                            export_data['Time'] = df[time_col].values if time_col in df.columns else np.arange(len(df))
                            
        if export_data:
            pd.DataFrame(export_data).to_csv(filepath, index=False)
            messagebox.showinfo("Success", f"Exported to {filepath}")
        else:
            messagebox.showwarning("Warning", "No signals to export.")
            
    def _export_html(self):
        """Export plot to HTML"""
        filepath = filedialog.asksaveasfilename(
            title="Export to HTML",
            defaultextension=".html",
            filetypes=[("HTML files", "*.html")]
        )
        
        if filepath:
            # For matplotlib, we save as PNG embedded in HTML
            import io
            import base64
            
            buf = io.BytesIO()
            self.figure.savefig(buf, format='png', dpi=150, 
                               facecolor=self.current_theme.plot_bg,
                               edgecolor='none', bbox_inches='tight')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Signal Viewer Pro - Export</title>
    <style>
        body {{ 
            background-color: {self.current_theme.bg}; 
            color: {self.current_theme.fg};
            font-family: 'Segoe UI', sans-serif;
            padding: 20px;
        }}
        h1 {{ color: {self.current_theme.accent}; }}
        img {{ max-width: 100%; }}
    </style>
</head>
<body>
    <h1>Signal Viewer Pro - Plot Export</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <img src="data:image/png;base64,{img_base64}" alt="Plot">
</body>
</html>"""
            
            with open(filepath, 'w') as f:
                f.write(html)
                
            messagebox.showinfo("Success", f"Exported to {filepath}")
            
    def _export_png(self):
        """Export plot to PNG"""
        filepath = filedialog.asksaveasfilename(
            title="Export to PNG",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")]
        )
        
        if filepath:
            self.figure.savefig(filepath, dpi=150,
                               facecolor=self.current_theme.plot_bg,
                               edgecolor='none', bbox_inches='tight')
            messagebox.showinfo("Success", f"Exported to {filepath}")
            
    # ========================================================================
    # Streaming
    # ========================================================================
    
    def _toggle_streaming(self):
        """Toggle CSV streaming mode"""
        if self.streaming_active:
            self.streaming_active = False
            self.stream_btn.config(text="▶ Stream")
        else:
            if not self.csv_files:
                messagebox.showinfo("Info", "No CSVs loaded for streaming.")
                return
                
            self.streaming_active = True
            self.stream_btn.config(text="⏹ Stop")
            
            # Start streaming thread
            self.streaming_thread = threading.Thread(target=self._streaming_loop, daemon=True)
            self.streaming_thread.start()
            
    def _streaming_loop(self):
        """Background thread for streaming CSV updates"""
        while self.streaming_active:
            try:
                self._refresh_csvs()
                self.root.after(0, self._update_plot)
            except Exception as e:
                print(f"Streaming error: {e}")
            time.sleep(0.5)  # Update every 500ms
            
    # ========================================================================
    # Theme and Misc
    # ========================================================================
    
    def _toggle_theme(self):
        """Toggle between dark and light theme"""
        if self.current_theme.name == "dark":
            self.current_theme = THEMES["light"]
        else:
            self.current_theme = THEMES["dark"]
        self._apply_theme()
        self._update_plot()
        
    def _toggle_link_axes(self):
        """Toggle linked axes"""
        self.link_axes = self.link_var.get()
        self._update_plot()
        
    def _toggle_cursor(self):
        """Toggle time cursor"""
        self.cursor_enabled = self.cursor_var.get()
        self._update_plot()
        
    def _clear_selection(self):
        """Clear current selection"""
        self.cursor_x = None
        self._update_plot()
        
    def _remove_current_tab(self):
        """Remove current tab"""
        if len(self.tabs) <= 1:
            messagebox.showinfo("Info", "Cannot remove the last tab.")
            return
            
        idx = self.current_tab_idx
        self.tabs.pop(idx)
        self.tab_notebook.forget(idx)
        
        self.current_tab_idx = max(0, idx - 1)
        self._update_ui_for_tab()


# ============================================================================
# Main Entry Point
# ============================================================================
def main():
    """Main entry point"""
    root = tk.Tk()
    
    # Set icon if available
    try:
        root.iconbitmap("assets/icon.ico")
    except:
        pass
        
    app = SignalViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

