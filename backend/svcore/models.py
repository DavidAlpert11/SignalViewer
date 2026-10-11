"""
Signal Viewer - Data Models
================================
Core data structures for runs, signals, and derived signals.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np
from enum import Enum
import itertools

_RUN_UID = itertools.count(1)   # never reused (id() of a freed object can be)


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
    # Own time vector (ArduPilot logs: every message type has its own rate). None = the run's time.
    time: Optional[np.ndarray] = None
    # Text values (states such as "IDLE" / "ARMED", flight-mode names): the data holds integer
    # codes and this maps code -> text. None = an ordinary numeric signal.
    labels: Optional[Dict[int, str]] = None

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

    # Loader bookkeeping (needed for correct reload / incremental append)
    import_settings: Dict[str, Any] = field(default_factory=dict)  # settings used to load
    delimiter: str = ","
    encoding: str = "utf-8-sig"
    source_columns: List[str] = field(default_factory=list)  # original column order (after rename of time col)
    byte_offset: int = 0          # file size (bytes) consumed so far - used for incremental append
    tail_sig: Optional[bytes] = None      # bytes just before byte_offset: detects a re-saved file
    seen_size: Optional[int] = None
    seen_mtime: Optional[float] = None
    data_version: int = 0         # bumped whenever data changes (figure cache key)
    uid: int = field(default_factory=lambda: next(_RUN_UID))   # unique per loaded Run object
    
    @property
    def signal_names(self) -> List[str]:
        return list(self.signals.keys())
    
    def get_signal_data(self, signal_name: str) -> tuple:
        """Get (time, data) for a signal, with offsets applied"""
        if signal_name not in self.signals:
            return np.array([]), np.array([])
        
        sig = self.signals[signal_name]
        time = sig.time if sig.time is not None else self.time
        total_offset = (self.time_offset or 0.0) + (sig.time_offset or 0.0)
        if total_offset == 0.0:
            return time, sig.data  # no copy (important for large / memory-mapped data)
        return time + total_offset, sig.data
    
    def compute_metadata(self):
        """Compute metadata from time vector"""
        n = len(self.time)
        self.sample_count = n
        if n > 0:
            self.start_time = float(self.time[0])
            self.end_time = float(self.time[-1])
            # O(1) memory: np.mean(np.diff(t)) allocates a full copy of the time vector
            self.dt_mean = (self.end_time - self.start_time) / (n - 1) if n > 1 else 0.0
        else:
            self.start_time = self.end_time = self.dt_mean = 0.0
        self.data_version += 1


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
    mode: str = "time"  # "time", "xy", or "fft"
    
    # Time mode: list of signal keys
    assigned_signals: List[str] = field(default_factory=list)
    
    # X-Y mode: x signal and y signals
    x_signal: Optional[str] = None
    y_signals: List[str] = field(default_factory=list)
    xy_alignment: str = "linear"  # "linear" or "nearest"
    
    # FFT mode settings
    fft_window: str = "hanning"  # "hanning", "hamming", "blackman", "none"
    fft_log_scale: bool = True   # Log scale for magnitude
    
    # Axis limits (None = auto)
    xlim: Optional[List[float]] = None  # [min, max] or None for auto
    ylim: Optional[List[float]] = None  # [min, max] or None for auto
    
    # Report settings (P0-10)
    title: str = ""          # Short title for subplot
    caption: str = ""        # Short caption 
    description: str = ""    # Multi-line description
    include_in_report: bool = True


def subplot_from_dict(sp_data: Dict[str, Any], default_index: int = 0) -> "SubplotConfig":
    """Build a SubplotConfig from a (session / tab-store) dict, restoring ALL fields."""
    return SubplotConfig(
        index=sp_data.get("index", default_index),
        mode=sp_data.get("mode", "time"),
        assigned_signals=list(sp_data.get("assigned_signals", []) or []),
        x_signal=sp_data.get("x_signal"),
        y_signals=list(sp_data.get("y_signals", []) or []),
        xy_alignment=sp_data.get("xy_alignment", "linear") or "linear",
        fft_window=sp_data.get("fft_window", "hanning") or "hanning",
        fft_log_scale=sp_data.get("fft_log_scale", True),
        xlim=sp_data.get("xlim"),
        ylim=sp_data.get("ylim"),
        title=sp_data.get("title", "") or "",
        caption=sp_data.get("caption", "") or "",
        description=sp_data.get("description", "") or "",
        include_in_report=sp_data.get("include_in_report", True),
    )


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
    
    # Dual cursor mode (measurement)
    cursor2_time: Optional[float] = None
    cursor_mode: str = "single"  # "single" or "dual"
    
    # Region selection
    region_enabled: bool = False
    region_start: Optional[float] = None
    region_end: Optional[float] = None
    
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
        try:
            return int(parts[0]), parts[1]
        except ValueError:
            pass  # signal names may contain ':' with no numeric prefix
    return -1, key

