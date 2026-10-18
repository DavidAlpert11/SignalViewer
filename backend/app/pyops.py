"""T31: the user's own Python operations - the server side.

The code runs in ONE worker process (svcore/pyworker.py), started on first use: a crash or an
endless loop there is stopped and the worker restarted, and the app keeps working. Only .py files
in the folder the user chose run (owner's decision, 2026-10-15); a session or a template stores the
operation's NAME ("file.py:function") and its parameters, never code."""
import logging
import multiprocessing as mp
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app import prefs
from svcore import analysis, pyworker
from svcore.analysis import OpError

log = logging.getLogger("signalviewer").getChild(__name__)

DEFAULT_DIR = os.path.join(prefs.APP_DIR, "operations")
TIMEOUT = float(os.environ.get("SV_PYOPS_TIMEOUT", "120"))     # seconds one run may take
LIST_TIMEOUT = 60.0

_lock = threading.Lock()
_proc: Optional[Any] = None
_conn: Optional[Any] = None


def folder() -> str:
    chosen = prefs._read("settings.json", {}).get("pyopsDir")
    return chosen if isinstance(chosen, str) and chosen.strip() else DEFAULT_DIR


def set_folder(path: Optional[str]) -> str:
    """Use another folder (None: the default). Remembered in settings.json; the worker restarts."""
    new = os.path.abspath(os.path.expanduser(path)) if path else None
    if new and not os.path.isdir(new):
        raise ValueError(f"Not a folder: {new}")
    with prefs._lock:
        s = prefs._read("settings.json", {})
        if new:
            s["pyopsDir"] = new
        else:
            s.pop("pyopsDir", None)
        prefs._write("settings.json", s)
    stop()
    return folder()


def stop() -> None:
    """Stop the worker: the next use starts a new one, which reads the files again (Reload)."""
    with _lock:
        _kill()


def _kill() -> None:
    global _proc, _conn
    if _proc is not None:
        try:
            _proc.kill()
            _proc.join(2)
        except Exception:                # already gone
            log.debug("stopping the Python worker", exc_info=True)
    if _conn is not None:
        try:
            _conn.close()
        except OSError:
            pass
    _proc, _conn = None, None


def _call(msg: tuple, timeout: float) -> Any:
    global _proc, _conn
    with _lock:
        if _proc is None or not _proc.is_alive():
            _kill()
            ctx = mp.get_context("spawn")             # the same on every OS; nothing of the server is copied
            parent, child = ctx.Pipe()
            _proc = ctx.Process(target=pyworker.main, args=(child, folder()), daemon=True,
                                name="signalviewer-python-operations")
            _proc.start()
            child.close()
            _conn = parent
        assert _conn is not None
        try:
            _conn.send(msg)
            if not _conn.poll(timeout):
                _kill()
                raise OpError(f"The Python operation took longer than {timeout:g} s and was stopped.")
            return _conn.recv()
        except (EOFError, BrokenPipeError, ConnectionResetError):
            if _proc is not None:
                _proc.join(2)                         # gone: wait for its exit code
            code = _proc.exitcode if _proc is not None else None
            _kill()
            raise OpError(f"The Python operation crashed the worker process (exit code {code}); "
                          "it was restarted.") from None


def listing() -> Dict[str, Any]:
    d = folder()
    try:
        res = _call(("list",), LIST_TIMEOUT)
    except OpError as e:                 # a file that loops while loading
        return {"folder": d, "default": d == DEFAULT_DIR, "exists": os.path.isdir(d), "ops": [],
                "errors": [{"file": "", "error": str(e)}]}
    return {"folder": d, "default": d == DEFAULT_DIR, "exists": os.path.isdir(d), **res}


def run(op_id: str, signals: List[Tuple[np.ndarray, np.ndarray]], args: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    sig = [(np.asarray(t, dtype=np.float64), np.asarray(y, dtype=np.float64)) for t, y in signals]
    res = _call(("run", op_id, sig, args), TIMEOUT)
    if res[0] == "err":
        raise OpError(res[1])
    return res[1], res[2]


EXAMPLE = '''"""Your own Signal Viewer operations (Create signals > Python).

Every function marked with @operation is listed in the app. It gets the time t and the signal(s)
as numpy arrays (several inputs: aligned onto the first one's time) and the parameters you set,
and returns y (one value per time) - or (t, y) for a new time base. Edit, save, then press Reload.
The code runs in its own process: an error is shown, it cannot take the app down.
"""
import numpy as np


@operation(name="Despike", params={"limit": 3.0})
def despike(t, y, limit=3.0):
    """Samples further than `limit` standard deviations from the median become gaps."""
    med = np.nanmedian(y)
    std = np.nanstd(y) or 1.0
    out = y.copy()
    out[np.abs(y - med) > limit * std] = np.nan
    return out


@operation(name="Scaled difference (A - B) x k", inputs=2, params={"k": 1.0})
def scaled_difference(t, a, b, k=1.0):
    """B is aligned onto A's time first."""
    return (a - b) * k


@operation(name="Resample", params={"rate_hz": 10.0})
def resample(t, y, rate_hz=10.0):
    """A new, even time base at rate_hz."""
    t2 = np.arange(t[0], t[-1], 1.0 / rate_hz)
    return t2, np.interp(t2, t, y)
'''


def write_example() -> str:
    d = folder()
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "example_operations.py")
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            f.write(EXAMPLE)
    stop()
    return p


# the analysis engine runs op "py" through this (svcore must not import app)
analysis.PY_RUNNER = run
