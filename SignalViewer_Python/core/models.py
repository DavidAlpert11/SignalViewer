"""
Signal Viewer Pro - Data Models
================================
Core data structures for runs, signals, and derived signals.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np
from enum import Enum


class SignalType(Enum):
    """Signal type classification"""
    NORMAL = "normal"
    STATE = "state"  # Discrete state signal (renders as transitions)


@dataclass
class Signal:
    """Represents a single signal from a CSV"""
    name: str
    data: np.ndarray
    signal_type: SignalType = SignalType.NORMAL
    
    # Display properties
    display_name: Optional[str] = None
    color: Optional[str] = None
    line_width: float = 1.5
    time_offset: float = 0.0  # Per-signal time offset
    
    @property
    def label(self) -> str:
        """Get display label"""
        return self.display_name or self.name
    
    def get_data_with_offset(self, time: np.ndarray) -> tuple:
        """Get time and data with offset applied"""
        return time + self.time_offset, self.data


@dataclass
class Run:
    """
    Represents a loaded CSV file (a "run" in SDI terminology).
    Contains time vector and all signals.
    """
    file_path: str
    csv_display_name: str  # Canonical name (may include parent folder)
    time: np.ndarray
    signals: Dict[str, Signal] = field(default_factory=dict)
    
    # Metadata
    sample_count: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    dt_mean: float = 0.0
    
    # Run-level settings
    run_name: Optional[str] = None
    description: Optional[str] = None
    time_offset: float = 0.0  # Per-run time offset
    
    @property
    def signal_names(self) -> List[str]:
        return list(self.signals.keys())
    
    def get_signal_data(self, signal_name: str) -> tuple:
        """Get (time, data) for a signal, with offsets applied"""
        if signal_name not in self.signals:
            return np.array([]), np.array([])
        
        sig = self.signals[signal_name]
        time_with_offset = self.time + self.time_offset + sig.time_offset
        return time_with_offset, sig.data
    
    def compute_metadata(self):
        """Compute metadata from time vector"""
        if len(self.time) > 0:
            self.sample_count = len(self.time)
            self.start_time = float(self.time[0])
            self.end_time = float(self.time[-1])
            if len(self.time) > 1:
                self.dt_mean = float(np.mean(np.diff(self.time)))


@dataclass
class DerivedSignal:
    """
    A signal computed from operations on other signals.
    Stored under a virtual "Derived" run.
    """
    name: str
    time: np.ndarray
    data: np.ndarray
    operation: str  # e.g., "derivative", "A + B", "norm(s1,s2)"
    source_signals: List[str] = field(default_factory=list)  # Source signal keys
    
    # Display properties
    display_name: Optional[str] = None
    color: Optional[str] = None
    line_width: float = 1.5
    
    @property
    def label(self) -> str:
        return self.display_name or self.name


@dataclass 
class SubplotConfig:
    """Configuration for a single subplot"""
    index: int
    mode: str = "time"  # "time" or "xy"
    
    # Time mode: list of signal keys
    assigned_signals: List[str] = field(default_factory=list)
    
    # X-Y mode: x signal and y signals
    x_signal: Optional[str] = None
    y_signals: List[str] = field(default_factory=list)
    xy_alignment: str = "linear"  # "linear" or "nearest"
    
    # Axis limits (None = auto)
    xlim: Optional[List[float]] = None  # [min, max] or None for auto
    ylim: Optional[List[float]] = None  # [min, max] or None for auto
    
    # Report settings (P0-10)
    title: str = ""          # Short title for subplot
    caption: str = ""        # Short caption 
    description: str = ""    # Multi-line description
    include_in_report: bool = True


@dataclass
class Tab:
    """Represents a view tab (SDI-like)"""
    id: str
    name: str
    layout_rows: int = 1
    layout_cols: int = 1
    subplots: List[SubplotConfig] = field(default_factory=list)
    active_subplot: int = 0
    is_compare_tab: bool = False  # True if this is a comparison result tab


@dataclass
class ViewState:
    """Complete view state (for session save/load)"""
    layout_rows: int = 1
    layout_cols: int = 1
    subplots: List[SubplotConfig] = field(default_factory=list)
    active_subplot: int = 0
    theme: str = "dark"
    cursor_time: Optional[float] = None
    cursor_enabled: bool = False
    cursor_show_all: bool = True  # Show values for all subplots or just active
    
    # Tab system (P1)
    tabs: List[Tab] = field(default_factory=list)
    active_tab: str = "main"  # Tab ID


# Signal key format: "run_idx:signal_name" or "-1:derived_name"
DERIVED_RUN_IDX = -1


def make_signal_key(run_idx: int, signal_name: str) -> str:
    """Create a signal key"""
    return f"{run_idx}:{signal_name}"


def parse_signal_key(key: str) -> tuple:
    """Parse signal key into (run_idx, signal_name)"""
    parts = key.split(":", 1)
    if len(parts) == 2:
        return int(parts[0]), parts[1]
    return -1, key

