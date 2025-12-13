"""
Signal Viewer Pro - Configuration and Constants
================================================
Centralized configuration for colors, themes, and app settings.
"""

from dataclasses import dataclass, field
from typing import Dict, List

# =============================================================================
# Signal Colors - Distinct palette for multiple traces
# =============================================================================
SIGNAL_COLORS: List[str] = [
    "#2E86AB",  # Blue
    "#A23B72",  # Magenta
    "#F18F01",  # Orange
    "#C73E1D",  # Red
    "#3B1F2B",  # Dark purple
    "#95C623",  # Lime green
    "#5E60CE",  # Indigo
    "#4EA8DE",  # Sky blue
    "#48BFE3",  # Cyan
    "#64DFDF",  # Teal
    "#72EFDD",  # Mint
    "#80FFDB",  # Aqua
    "#E63946",  # Coral red
    "#F4A261",  # Sandy orange
    "#2A9D8F",  # Sea green
]

# =============================================================================
# Theme Definitions
# =============================================================================
@dataclass
class ThemeColors:
    """Color scheme for a theme"""
    bg: str
    card: str
    card_header: str
    text: str
    muted: str
    border: str
    input_bg: str
    plot_bg: str
    paper_bg: str
    grid: str
    checkbox_border: str
    checkbox_bg: str
    accent: str
    button_bg: str
    button_text: str


THEMES: Dict[str, ThemeColors] = {
    "dark": ThemeColors(
        bg="#1a1a2e",
        card="#16213e",
        card_header="#0f3460",
        text="#e8e8e8",
        muted="#aaa",
        border="#333",
        input_bg="#2a2a3e",
        plot_bg="#1a1a2e",
        paper_bg="#16213e",
        grid="#444",
        checkbox_border="#666",
        checkbox_bg="#2a2a3e",
        accent="#4ea8de",
        button_bg="#0f3460",
        button_text="#e8e8e8",
    ),
    "light": ThemeColors(
        bg="#f0f2f5",
        card="#ffffff",
        card_header="#e3e7eb",
        text="#1a1a2e",
        muted="#5a6268",
        border="#ced4da",
        input_bg="#ffffff",
        plot_bg="#ffffff",
        paper_bg="#fafbfc",
        grid="#dee2e6",
        checkbox_border="#495057",
        checkbox_bg="#ffffff",
        accent="#2E86AB",
        button_bg="#e3e7eb",
        button_text="#1a1a2e",
    ),
}

# =============================================================================
# Application Constants
# =============================================================================
APP_TITLE = "Signal Viewer Pro"
APP_HOST = "127.0.0.1"
APP_PORT = 8050
APP_URL = f"http://{APP_HOST}:{APP_PORT}"

# Column naming
TIME_COLUMN = "Time"
DERIVED_CSV_IDX = -1  # Special index for derived signals

# Layout limits
MAX_ROWS = 4
MAX_COLS = 4
MAX_SUBPLOTS = MAX_ROWS * MAX_COLS

# File handling
TEMP_DIR = "temp"
SESSION_FILE_PREFIX = "signal_viewer_session"

# Plot modes
MODE_TIME = "time"
MODE_XY = "xy"

# =============================================================================
# Store Keys (for dcc.Store components)
# =============================================================================
class StoreKeys:
    """Centralized store ID constants"""
    CSV_FILES = "store-csv-files"
    ASSIGNMENTS = "store-assignments"
    LAYOUTS = "store-layouts"
    THEME = "store-theme"
    SELECTED_SUBPLOT = "store-selected-subplot"
    SELECTED_TAB = "store-selected-tab"
    NUM_TABS = "store-num-tabs"
    DERIVED = "store-derived"
    SIGNAL_PROPS = "store-signal-props"
    LINKS = "store-links"
    CONTEXT_SIGNAL = "store-context-signal"
    LINK_AXES = "store-link-axes"
    HIGHLIGHTED = "store-highlighted"
    REFRESH_TRIGGER = "store-refresh-trigger"
    SEARCH_FILTERS = "store-search-filters"
    CURSOR_X = "store-cursor-x"
    SUBPLOT_MODES = "store-subplot-modes"


# =============================================================================
# Operation Types
# =============================================================================
SINGLE_OPERATIONS = [
    {"label": "∂ Derivative", "value": "derivative"},
    {"label": "∫ Integral", "value": "integral"},
    {"label": "|x| Absolute", "value": "abs"},
    {"label": "√x Square Root", "value": "sqrt"},
    {"label": "-x Negate", "value": "negate"},
]

MULTI_OPERATIONS = [
    {"label": "A + B", "value": "add"},
    {"label": "A - B", "value": "sub"},
    {"label": "A × B", "value": "mul"},
    {"label": "A ÷ B", "value": "div"},
    {"label": "||signals|| Norm", "value": "norm"},
    {"label": "Mean", "value": "mean"},
]


def get_theme_colors(theme_name: str) -> ThemeColors:
    """Get theme colors by name, defaulting to dark theme"""
    return THEMES.get(theme_name, THEMES["dark"])


def get_theme_dict(theme_name: str) -> Dict[str, str]:
    """Get theme colors as dictionary (for legacy compatibility)"""
    theme = get_theme_colors(theme_name)
    return {
        "bg": theme.bg,
        "card": theme.card,
        "card_header": theme.card_header,
        "text": theme.text,
        "muted": theme.muted,
        "border": theme.border,
        "input_bg": theme.input_bg,
        "plot_bg": theme.plot_bg,
        "paper_bg": theme.paper_bg,
        "grid": theme.grid,
        "checkbox_border": theme.checkbox_border,
        "checkbox_bg": theme.checkbox_bg,
        "accent": theme.accent,
        "button_bg": theme.button_bg,
        "button_text": theme.button_text,
    }

