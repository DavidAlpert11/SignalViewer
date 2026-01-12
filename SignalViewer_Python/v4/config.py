"""
Signal Viewer Pro v4.0 - Configuration
======================================
Central configuration for the application.
"""

# Application info
APP_TITLE = "Signal Viewer Pro"
APP_VERSION = "4.0"
APP_HOST = "127.0.0.1"
APP_PORT = 8050

# Theme colors
THEMES = {
    "dark": {
        "bg_primary": "#1a1a2e",
        "bg_secondary": "#16213e",
        "bg_card": "#1e2a4a",
        "bg_plot": "#0d1b2a",
        "text_primary": "#e8e8e8",
        "text_secondary": "#a0a0a0",
        "accent": "#4ea8de",
        "accent_secondary": "#f4a261",
        "grid": "#2a3f5f",
        "border": "#2a3f5f",
        "success": "#4ade80",
        "error": "#f87171",
    },
    "light": {
        "bg_primary": "#f8f9fa",
        "bg_secondary": "#ffffff",
        "bg_card": "#ffffff",
        "bg_plot": "#ffffff",
        "text_primary": "#212529",
        "text_secondary": "#6c757d",
        "accent": "#0d6efd",
        "accent_secondary": "#fd7e14",
        "grid": "#dee2e6",
        "border": "#dee2e6",
        "success": "#198754",
        "error": "#dc3545",
    }
}

# Signal colors for auto-assignment
SIGNAL_COLORS = [
    "#4ea8de",  # Blue
    "#f4a261",  # Orange
    "#4ade80",  # Green
    "#f87171",  # Red
    "#a78bfa",  # Purple
    "#fbbf24",  # Yellow
    "#2dd4bf",  # Teal
    "#f472b6",  # Pink
    "#818cf8",  # Indigo
    "#fb923c",  # Light Orange
]

# Layout constraints
MAX_ROWS = 4
MAX_COLS = 4
MAX_SIGNALS_PER_SUBPLOT = 10

# Performance settings
CACHE_MAX_SIZE = 20  # Maximum cached figures
DOWNSAMPLE_THRESHOLD = 10000  # Points above which to downsample
CHUNK_SIZE = 50000  # Rows per chunk for large CSV loading

# File settings
SUPPORTED_EXTENSIONS = [".csv", ".txt", ".tsv"]
MAX_FILE_SIZE_MB = 500

# UI settings
SIDEBAR_WIDTH = 320
MIN_PLOT_HEIGHT = 400
CURSOR_ANIMATION_INTERVAL = 100  # ms

