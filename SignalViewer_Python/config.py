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
        bg="#0d1117",  # GitHub dark - professional, easy on eyes
        card="#161b22",  # Subtle elevation for cards
        card_header="#21262d",  # Clear header distinction
        text="#e6edf3",  # Highly readable soft white
        muted="#8b949e",  # Perfect for secondary text
        border="#30363d",  # Subtle borders, not harsh
        input_bg="#0d1117",  # Consistent with background
        plot_bg="#0d1117",  # Seamless plot integration
        paper_bg="#161b22",  # Plotly plot background
        grid="#21262d",  # Visible but not distracting
        checkbox_border="#30363d",  # Consistent borders
        checkbox_bg="#161b22",  # Matches card
        accent="#58a6ff",  # GitHub blue - modern, accessible
        button_bg="#238636",  # Success green for primary actions
        button_text="#ffffff",  # High contrast button text
    ),
    "light": ThemeColors(
        bg="#ffffff",  # Pure white background
        card="#f6f8fa",  # GitHub light card
        card_header="#f0f3f6",  # Subtle header
        text="#24292f",  # Dark, readable text
        muted="#57606a",  # Better muted
        border="#d0d7de",  # Light borders
        input_bg="#ffffff",
        plot_bg="#ffffff",
        paper_bg="#f6f8fa",
        grid="#d8dee4",  # Very light grid
        checkbox_border="#d0d7de",
        checkbox_bg="#ffffff",
        accent="#0969da",  # GitHub blue
        button_bg="#2da44e",  # Modern green
        button_text="#ffffff",
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

