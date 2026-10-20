"""T60: file formats added by the user - a reader is a Python function in a .py file of the
readers folder (~/.signalviewer/readers), marked with the `reader` decorator (usable without an
import):

    @reader(extensions=[".kv"], name="Bench recorder")
    def read(path):
        ...
        return {"time": t, "signals": {"Speed [km/h]": speed, "RPM": rpm}}

What a reader returns (numpy arrays or lists):
    {"time": t, "signals": {name: values}}                  # one time for every signal
    {"signals": {name: (t, values)}}                        # a tuple: that signal's own time
    {"time": t, "signals": {...}, "labels": {"Mode": {0: "IDLE", 1: "RUN"}}}   # text values
Mixing both forms is fine; `None` means "not my file" and the built-in reader (if any) is used.

Only the user's own folder is read, as for the Python operations (never code from a session, a
template or a data file). Readers run inside the app: a reader that hangs holds that file's
opening; an exception is shown as the file's error with the line in the reader's file.
"""
import importlib.util
import os
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from svcore.models import Run, Signal

MARK = "_sv_reader"


def reader(extensions: Any = None, name: Optional[str] = None) -> Callable:
    """Mark a function `f(path)` as the reader of files with these extensions (".kv" or [".kv", ".log"])."""
    exts = [extensions] if isinstance(extensions, str) else list(extensions or [])

    def wrap(f: Callable) -> Callable:
        norm = sorted({("." + e.lstrip(".")).lower() for e in exts if str(e).strip(". ")})
        if not norm:
            raise ValueError(f"@reader on {f.__name__} needs extensions=[\".ext\"]")
        setattr(f, MARK, {"extensions": norm, "name": name or f.__name__.replace("_", " ")})
        return f
    return wrap


class ReaderError(Exception):
    pass


def _short(e: BaseException, path: str) -> str:
    """The error with the line of the user's file it came from."""
    line = None
    for fr in traceback.extract_tb(e.__traceback__):
        if os.path.abspath(fr.filename) == os.path.abspath(path):
            line = fr.lineno
    if isinstance(e, SyntaxError) and e.lineno:
        line = e.lineno
    msg = f"{type(e).__name__}: {e}"
    return f"{os.path.basename(path)}" + (f", line {line}" if line else "") + f": {msg}"


def load_folder(folder: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """[{name, extensions, file, fn}] and the files that could not be loaded (one broken file
    does not hide the others)."""
    found: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    if not os.path.isdir(folder):
        return found, errors
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith(".py") or fn.startswith((".", "_")):
            continue
        path = os.path.join(folder, fn)
        try:
            spec = importlib.util.spec_from_file_location(f"sv_user_reader_{len(found)}_{fn[:-3]}", path)
            if spec is None or spec.loader is None:
                raise ImportError("not a Python module")
            mod = importlib.util.module_from_spec(spec)
            mod.reader = reader            # type: ignore[attr-defined]   # usable without an import
            spec.loader.exec_module(mod)
        except Exception as e:
            errors.append({"file": fn, "error": _short(e, path)})
            continue
        for attr, f in vars(mod).items():
            meta = getattr(f, MARK, None)
            if callable(f) and meta and getattr(f, "__module__", None) == mod.__name__:
                found.append({**meta, "file": fn, "id": f"{fn}:{attr}", "fn": f, "path": path})
    return found, errors


def _vec(x: Any, what: str) -> np.ndarray:
    a = np.asarray(x, dtype=np.float64).ravel()
    if a.ndim != 1:
        raise ReaderError(f"{what} is not a list of numbers")
    return a


def to_run(result: Any, path: str, display_name: str, reader_name: str) -> Optional[Run]:
    """A reader's result as a Run (the same model every built-in reader fills)."""
    if result is None:
        return None
    if not isinstance(result, dict) or not isinstance(result.get("signals"), dict):
        raise ReaderError(f'The reader "{reader_name}" must return {{"signals": {{...}}}} (or None for "not my file").')
    t0 = _vec(result["time"], '"time"') if result.get("time") is not None else None
    order0 = None
    if t0 is not None and len(t0) > 1 and np.any(np.diff(t0) < 0):   # unsorted: sort, as the CSV reader does
        order0 = np.argsort(t0, kind="stable")
        t0 = t0[order0]
    labels = result.get("labels") or {}
    sigs: Dict[str, Signal] = {}
    for name, v in result["signals"].items():
        name = str(name)
        t: Optional[np.ndarray]
        if isinstance(v, tuple):                               # (time, values): its own time
            if len(v) != 2:
                raise ReaderError(f"{name}: a tuple must be (time, values).")
            t, y = _vec(v[0], f"the time of {name}"), _vec(v[1], name)
            if len(t) != len(y):
                raise ReaderError(f"{name} has {len(y)} values but its time has {len(t)}.")
            if len(t) > 1 and np.any(np.diff(t) < 0):
                o = np.argsort(t, kind="stable")
                t, y = t[o], y[o]
        else:                                                  # values on the file's "time"
            if t0 is None:
                raise ReaderError(f'{name}: give "time" for the file, or a tuple (time, values) for this signal.')
            t, y = None, _vec(v, name)
            if len(y) != len(t0):
                raise ReaderError(f"{name} has {len(y)} values but the time has {len(t0)}.")
            if order0 is not None:
                y = y[order0]
        lab = labels.get(name)
        sigs[name] = Signal(name=name, data=y, time=t,
                            labels={int(k): str(x) for k, x in lab.items()} if isinstance(lab, dict) else None)
    if not sigs:
        return None
    base = t0 if t0 is not None else max((x.time for x in sigs.values() if x.time is not None), key=len)
    run = Run(file_path=path, csv_display_name=display_name, time=base)
    run.signals = sigs
    run.compute_metadata()
    times = [s.time for s in sigs.values() if s.time is not None and len(s.time)]
    if times:
        run.start_time = min([run.start_time] + [float(x[0]) for x in times])
        run.end_time = max([run.end_time] + [float(x[-1]) for x in times])
    run.import_settings = {"format": "reader", "reader": reader_name}
    return run


def read(r: Dict[str, Any], path: str, display_name: str) -> Optional[Run]:
    try:
        result = r["fn"](path)
    except Exception as e:
        raise ReaderError(f'The reader "{r["name"]}" failed: {_short(e, r["path"])}') from None
    return to_run(result, path, display_name, r["name"])


EXAMPLE = '''"""An example reader for Signal Viewer (T60). Files ending in .kv, one line per moment:

    t=0.00 speed=3.2 rpm=1210 mode=IDLE
    t=0.01 speed=3.3 rpm=1215 mode=IDLE

Edit it for your own format, save, and open a file: Signal Viewer reads this folder each time.
Return {"time": t, "signals": {name: values}} - or (t, values) per signal - or None (not my file).
"""
import numpy as np


@reader(extensions=[".kv"], name="key=value lines")
def read_kv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            pairs = dict(p.split("=", 1) for p in line.split() if "=" in p)
            if "t" in pairs:
                rows.append(pairs)
    if not rows:
        return None
    t = np.array([float(r["t"]) for r in rows])
    names = [k for k in rows[0] if k != "t"]
    signals, labels = {}, {}
    for k in names:
        vals = [r.get(k) for r in rows]
        try:
            signals[k] = np.array([float(v) if v is not None else np.nan for v in vals])
        except ValueError:                                   # text: codes + their names
            texts = sorted({v for v in vals if v is not None})
            code = {s: i for i, s in enumerate(texts)}
            signals[k] = np.array([code.get(v, np.nan) for v in vals], dtype=float)
            labels[k] = {i: s for s, i in code.items()}
    return {"time": t, "signals": signals, "labels": labels}
'''
