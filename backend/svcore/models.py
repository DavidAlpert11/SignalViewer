"""
Signal Viewer - Data Models
================================
Core data structures for runs and signals (derived signals: svcore/analysis.py DerivedDef).
"""

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np
import itertools
import os
import threading
import weakref

_RUN_UID = itertools.count(1)   # never reused (id() of a freed object can be)


@dataclass
class Signal:
    """Represents a single signal from a CSV"""
    name: str
    data: np.ndarray
    
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



class _LazyBudget:
    """How much of the lazily-read values stays in memory (SV_LAZY_MB, default 1536 MB): the
    least recently used ones are dropped beyond it and read from the file again when needed.
    (A reader still holding the array keeps it alive; only this cache lets go of it.)"""
    def __init__(self, limit: int):
        self.limit = limit
        self.total = 0
        self._items: "OrderedDict[int, tuple]" = OrderedDict()     # id -> (weakref, nbytes)
        self._lock = threading.RLock()

    def touch(self, sig: "LazySignal", nbytes: Optional[int] = None):
        with self._lock:
            key = id(sig)
            if nbytes is not None:
                old = self._items.pop(key, None)
                if old:
                    self.total -= old[1]
                self._items[key] = (weakref.ref(sig, self._gone(key)), nbytes)
                self.total += nbytes
            elif key in self._items:
                self._items.move_to_end(key)
            for k in list(self._items):
                if self.total <= self.limit or k == key:
                    break
                ref, nb = self._items.pop(k)
                self.total -= nb
                other = ref()
                if other is not None:
                    other._evict()

    def _gone(self, key: int):
        """The callback of a signal's weak reference: its entry goes when the signal does."""
        def cb(_ref: Any) -> None:
            self.forget(key)
        return cb

    def forget(self, key: int):
        with self._lock:
            old = self._items.pop(key, None)
            if old:
                self.total -= old[1]


LAZY_BUDGET = _LazyBudget(int(float(os.environ.get("SV_LAZY_MB", "1536")) * (1 << 20)))


class LazySignal(Signal):
    """A signal whose values stay in its file until first used (big ArduPilot logs): the time
    vector is in memory, `data` is read on first access and kept within LAZY_BUDGET. `source` is
    any object with read() -> ndarray, concat(other) and nbytes (svcore.bin_loader.LazyField).
    Setting `data` makes the values the signal's own (no longer read from the file)."""

    def __init__(self, name: str, time: np.ndarray, source: Any, labels: Optional[Dict[int, str]] = None):
        self._source = source
        self._cache: Optional[np.ndarray] = None
        super().__init__(name=name, data=None, time=time, labels=labels)  # type: ignore[arg-type]

    @property  # type: ignore[override]
    def data(self) -> np.ndarray:
        c = self._cache
        if c is None:
            c = self._source.read()
            self._cache = c
            LAZY_BUDGET.touch(self, c.nbytes)
        elif self._source is not None:
            LAZY_BUDGET.touch(self)
        return c

    @data.setter
    def data(self, value: np.ndarray):
        if value is None:                     # dataclass __init__
            return
        self._cache = value
        if self._source is not None:
            self._source = None
            LAZY_BUDGET.forget(id(self))

    @property
    def loaded(self) -> bool:
        return self._cache is not None

    def _evict(self):
        if self._source is not None:
            self._cache = None

    def extend(self, more: Any):
        """Live mode: values appended to the file (another lazy source of the same field)."""
        if self._source is None:
            self.data = np.concatenate([np.asarray(self._cache), more.read()])
            return
        self._source = self._source.concat(more)
        if self._cache is not None:
            self._cache = np.concatenate([self._cache, more.read()])
            LAZY_BUDGET.touch(self, self._cache.nbytes)


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

    # The column the time was read from, as the file names it (CSV / MAT / Parquet; None = not a
    # column, or not known), and signals the loader renamed -> their name in the file (a column
    # called "Time" that is not the time becomes "Time_2"). For the Time axis dialog.
    time_source: Optional[str] = None
    original_names: Dict[str, str] = field(default_factory=dict)

    # Loader bookkeeping (needed for correct reload / incremental append)
    import_settings: Dict[str, Any] = field(default_factory=dict)  # settings used to load
    delimiter: str = ","
    decimal: str = "."            # "," for a file written with a decimal comma (1,5)
    time_is_index: bool = False   # no time column: the row number is the time
    encoding: str = "utf-8-sig"
    source_columns: List[str] = field(default_factory=list)  # original column order (after rename of time col)
    byte_offset: int = 0          # file size (bytes) consumed so far - used for incremental append
    tail_sig: Optional[bytes] = None      # bytes just before byte_offset: detects a re-saved file
    seen_size: Optional[int] = None
    seen_mtime: Optional[float] = None
    content_fp: Optional[str] = None      # F34: fingerprint of the whole file when nothing is pending
    data_version: int = 0         # bumped whenever data changes (figure cache key)
    uid: int = field(default_factory=lambda: next(_RUN_UID))   # unique per loaded Run object
    # what the loader wants the user told (skipped columns, damaged parts...): sent with the run
    load_report: Dict[str, Any] = field(default_factory=dict)
    # F3: settings the file states itself, not as signals (MAT scalars / short texts, struct fields)
    file_params: Dict[str, Any] = field(default_factory=dict)
    # flight logs: the parsed log behind the signals (T36 - were attributes set from outside)
    _flightlog: Any = None        # parameters / events / health for the Log panel (.bin .tlog .ulg)
    _dataflash: Any = None        # .bin: formats and units, for live mode
    _tlog: Any = None             # .tlog: parser state, for live mode
    
    @property
    def signal_names(self) -> List[str]:
        return list(self.signals.keys())
    
    def signal_parts(self, signal_name: str) -> tuple:
        """(time as stored, data, time offset): the signal's time is time + offset. P1: callers that
        only look up a window or a moment shift the question by -offset and the answer by +offset,
        instead of copying the whole time vector (160 MB and ~45 ms for 20M samples) per request."""
        if signal_name not in self.signals:
            return np.array([]), np.array([]), 0.0
        sig = self.signals[signal_name]
        time = sig.time if sig.time is not None else self.time
        return time, sig.data, float((self.time_offset or 0.0) + (sig.time_offset or 0.0))

    def get_signal_data(self, signal_name: str) -> tuple:
        """Get (time, data) for a signal, with offsets applied"""
        time, data, total_offset = self.signal_parts(signal_name)
        if total_offset == 0.0:
            return time, data  # no copy (important for large / memory-mapped data)
        return time + total_offset, data
    
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
