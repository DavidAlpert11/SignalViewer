"""Signal Viewer from Python - the same readers as the app, without the window or the server.

    import signalviewer as sv
    rec = sv.load("flight.bin")            # .csv .mat .bin .tlog .ulg
    rec.signals                            # names
    t, y = rec.signal("ATT.Roll")          # numpy arrays (each signal keeps its own time);
                                           # the unit may be left out: "ATT.Roll [deg]"
    df = rec.to_dataframe(["ATT.Roll", "ATT.Pitch"], t0=10, t1=60)   # one time base (pandas)
    sv.show(t, {"roll": y}, name="from a script")   # into the open app (see push_client)

From MATLAB or a shell, use the command line instead: `python cli.py --help`.
"""
import os as _os
import sys as _sys
from typing import Dict, List, Optional, Sequence, Tuple

# T56: installed with pip, the app's own modules (app, svcore), its UI and the examples live in
# signalviewer/_core; from the source folder they are next to this package (backend/).
_CORE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_core")
if _os.path.isdir(_CORE) and _CORE not in _sys.path:
    _sys.path.insert(0, _CORE)

import numpy as np

from app.store import Store
from svcore.analysis import align_to
from svcore.naming import resolve_signal_name

from .push_client import show

__all__ = ["load", "Recording", "show"]


class Recording:
    """One file, read the way the app reads it (same auto-detection, same signal names)."""

    def __init__(self, store: Store, run_id: str):
        self._store, self._id = store, run_id
        lr = store.get(run_id)
        self.name: str = lr.name
        self.path: str = lr.run.file_path
        self.report: Dict = dict(lr.load_report)

    @property
    def signals(self) -> List[str]:
        return list(self._store.get(self._id).run.signals.keys())

    def signal(self, name: str) -> Tuple[np.ndarray, np.ndarray]:
        """(time, values) of one signal, by its name in the app - or without its unit, in any
        case ("ATT.Roll" for "ATT.Roll [deg]") when that is one signal. A name that is not raises
        KeyError with the closest names."""
        full = resolve_signal_name(self.signals, name, self.name)
        t, y = self._store.signal(f"{self._id}/{full}")
        return np.asarray(t, dtype=np.float64), np.asarray(y, dtype=np.float64)

    def table(self, names: Optional[Sequence[str]] = None, t0: Optional[float] = None,
              t1: Optional[float] = None, alignment: str = "linear") -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Signals on ONE time base - the first signal's, inside [t0, t1], full resolution -
        exactly like "Export CSV" in the app. Returns (time, {name: values})."""
        names = list(names) if names else self.signals
        if not names:
            raise ValueError("No signals to put in the table.")
        t_base, y0 = self.signal(names[0])
        i0 = 0 if t0 is None else int(np.searchsorted(t_base, t0, "left"))
        i1 = len(t_base) if t1 is None else int(np.searchsorted(t_base, t1, "right"))
        t = t_base[i0:i1]
        cols = {names[0]: y0[i0:i1]}
        for n in names[1:]:
            ts, ys = self.signal(n)
            cols[n] = np.asarray(align_to(t, ts, ys, alignment), dtype=np.float64)
        return t, cols

    def to_dataframe(self, names: Optional[Sequence[str]] = None, t0: Optional[float] = None,
                     t1: Optional[float] = None, alignment: str = "linear"):
        """`table()` as a pandas DataFrame with a "Time" column."""
        import pandas as pd
        t, cols = self.table(names, t0, t1, alignment)
        return pd.DataFrame({"Time": t, **cols})

    def __repr__(self) -> str:
        return f"<Recording {self.name!r}: {len(self.signals)} signals>"


def load(path: str, settings: Optional[dict] = None) -> Recording:
    """Read a file. `settings` are the CSV import options of the app's Import dialog
    (e.g. {"delimiter": ";", "time_column": "t"}); usually not needed."""
    store = Store()
    lr = store.open_file(path, settings)
    return Recording(store, lr.id)
