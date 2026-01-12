"""
Signal Viewer Pro v4.0 - State Management
=========================================
Simple, centralized state management.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import json


@dataclass
class SignalInfo:
    """Information about a single signal."""
    name: str
    csv_id: str
    color: Optional[str] = None
    display_name: Optional[str] = None
    scale: float = 1.0
    offset: float = 0.0
    line_width: float = 1.5
    visible: bool = True


@dataclass 
class CSVFile:
    """Information about a loaded CSV file."""
    id: str
    path: str
    name: str
    signals: List[str] = field(default_factory=list)
    time_column: Optional[str] = None
    row_count: int = 0
    
    
@dataclass
class LayoutConfig:
    """Subplot grid configuration."""
    rows: int = 1
    cols: int = 1


@dataclass
class CursorState:
    """Time cursor state."""
    x: Optional[float] = None
    visible: bool = True
    playing: bool = False


def get_initial_state() -> Dict[str, Any]:
    """Get the initial application state for dcc.Store components."""
    return {
        "csv_files": {},           # {csv_id: CSVFile dict}
        "assignments": {"0": []},  # {subplot_id: [signal_keys]}
        "layout": {"rows": 1, "cols": 1},
        "cursor": {"x": None, "visible": True, "playing": False},
        "settings": {
            "theme": "dark",
            "link_axes": True,
            "show_legend": True,
            "show_grid": True,
        },
        "signal_props": {},        # {signal_key: SignalInfo dict}
    }


def make_signal_key(csv_id: str, signal_name: str) -> str:
    """Create a unique key for a signal."""
    return f"{csv_id}:{signal_name}"


def parse_signal_key(key: str) -> tuple:
    """Parse a signal key into (csv_id, signal_name)."""
    parts = key.split(":", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "", key


def serialize_state(state: Dict) -> str:
    """Serialize state to JSON string."""
    return json.dumps(state, indent=2)


def deserialize_state(json_str: str) -> Dict:
    """Deserialize state from JSON string."""
    return json.loads(json_str)

