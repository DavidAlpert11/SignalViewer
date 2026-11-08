"""Shared by the API routes: data paths, response helpers, opening a file with remembered settings."""

import base64
import json
import logging
import os
from typing import List, NoReturn, Optional

import numpy as np
from fastapi import HTTPException

from app import prefs
from app.atomic import atomic_open, atomic_path, atomic_write  # noqa: F401  (O3: every save goes through these)
from app.store import LoadedRun, LoadError, _stat, store
from svcore.bin_loader import bin_signal_names


def _log_signal_names(path: str):
    # the same file already open and unchanged: its names, without reading the log again
    full = os.path.abspath(path)
    for lr in list(store.runs.values()):
        if os.path.normcase(os.path.abspath(lr.run.file_path)) == os.path.normcase(full) and lr.stat == _stat(full):
            return list(lr.run.signals)
    if path.lower().endswith(".bin"):
        return bin_signal_names(path)
    from svcore.tlog_loader import load_tlog
    from svcore.ulog_loader import load_ulog
    run, _ = (load_tlog if path.lower().endswith(".tlog") else load_ulog)(path, os.path.basename(path))
    return list(run.signals) if run else []


log = logging.getLogger("signalviewer").getChild(__name__)


APP_DIR = prefs.APP_DIR

UPLOAD_DIR = os.path.join(APP_DIR, "uploads")

AUTOSAVE = os.path.join(APP_DIR, "autosave.json")
SWEEP_AUTOSAVE = os.path.join(APP_DIR, "sweep_autosave.json")     # the Sweeps area's open studies


def read_autosave(path: str) -> dict:
    """{"state": the saved JSON or None}; a file that cannot be read is set aside, not overwritten by
    the next autosave (F29), and named in "damaged"."""
    if not os.path.isfile(path):
        return {"state": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {"state": json.load(f)}
    except (OSError, ValueError):       # unreadable or half-written: start clean, but say so in the log
        kept = path.replace(".json", ".damaged.json")
        try:
            os.replace(path, kept)
        except OSError:
            kept = path
        log.warning("autosave %s could not be read; starting without it (kept as %s)", path, kept, exc_info=True)
        return {"state": None, "damaged": kept}


def write_autosave(path: str, state) -> dict:
    with atomic_open(path) as f:          # O3 (each process its own temporary file, as before)
        json.dump(state, f)
    return {"ok": True}

SUPPORTED = (".csv", ".txt", ".tsv", ".dat", ".mat", ".bin", ".tlog", ".ulg", ".mcap", ".h5", ".hdf5", ".parquet", ".pq",
             ".asc", ".log")


def supported_now() -> tuple:
    """The built-in types + the extensions of the user's own readers (T60, read when asked)."""
    from app import userreaders
    return SUPPORTED + tuple(e for e in userreaders.extensions() if e not in SUPPORTED)



def b64(a: np.ndarray, dtype) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype=dtype).tobytes()).decode("ascii")



def y_reference(y: np.ndarray) -> float:
    """P3: the values are sent as float32 RELATIVE to this float64 reference (the middle of their
    range): float32 alone rounds 1.7e9 (a Unix time, a counter) to steps of 128 and an RTK track by up
    to 0.2 m - relative to the middle only the signal's own variation is rounded, ~1e-7 of it."""
    f = y[np.isfinite(y)]
    if not len(f):
        return 0.0
    mid = 0.5 * (float(f.min()) + float(f.max()))
    return mid if np.isfinite(mid) else 0.0



def fail(status: int, message: str) -> NoReturn:
    raise HTTPException(status_code=status, detail=message)



def open_paths(paths: list, settings: Optional[dict], report=None, cancelled=None) -> tuple:
    """P4: several files read at once (app/openmany.py: within the memory budget); (opened, errors) in
    the order asked, the files listed in that order. report(frac, phase): the overall progress;
    cancelled(): stop starting files. A cancellation raised inside a file is raised again here."""
    from app.openmany import Progress, open_many
    from svcore.csv_loader import set_progress_context
    prog = Progress(len(paths), report or (lambda f, p="": None))

    def one(p: str, i: int):
        set_progress_context(prog.file(i), cancelled)      # per thread: each file its share of the bar
        try:
            return open_with_prefs(p, settings)
        finally:
            prog.file(i)(1.0, "read")
            set_progress_context(None, None)
    with store.batch(paths):
        results = open_many(list(paths), one, cancelled or (lambda: False))
    opened: List[LoadedRun] = []
    errors: list = []
    for p, lr, err in results:
        if err is not None and err.__class__.__name__ in ("JobCancelled", "LoadCancelled"):
            raise err
        if err is None and lr is None:             # never started: cancelled meanwhile
            continue
        if isinstance(err, LoadError):
            errors.append(_load_error(p, err))
        elif isinstance(err, Exception):
            errors.append(unexpected_load_error(p, err))
        elif err is not None:                      # KeyboardInterrupt / SystemExit: not a file's fault
            raise err
        elif isinstance(lr, LoadedRun):
            opened.append(lr)
    store.order_as([lr.id for lr in opened])
    return [store.describe(lr) for lr in opened], errors     # described in order: tags A, B, C... follow it


def open_with_prefs(path: str, settings: Optional[dict]):
    """
    Explicit settings win (and are remembered for the folder). Otherwise auto-detection
    comes FIRST; the folder's remembered settings are used only when auto-detection does
    not recognise the file (it fails, or finds no time column by name). Applying them
    blindly would silently misread other files that live in the same folder.
    """
    lr: Optional[LoadedRun]
    if settings is not None:
        lr = store.open_file(path, settings)
        prefs.remember_import(path, settings)
    else:
        remembered = prefs.import_for(path)
        auto, auto_err = None, None
        try:
            auto = store.open_file(path, None)
        except LoadError as e:
            auto_err = e
        lr = auto
        # the LoadedRun's report (every format); only the CSV loader puts one on the Run itself - a
        # .bin / .tlog / .mat in a folder with remembered settings failed here after opening
        if remembered and (auto is None or not auto.load_report.get("timeByName", True)):
            try:
                alt = store.open_file(path, remembered)
                if auto is None or alt.load_report.get("timeByName"):
                    if auto is not None:
                        store.remove(auto.id)
                    lr = alt
                    lr.load_report["rememberedSettings"] = True
                else:
                    store.remove(alt.id)
            except LoadError:
                pass
        if lr is None:
            raise auto_err or LoadError("Could not read this file.")
    prefs.add_recent(path, "file")
    return lr



def unexpected_load_error(path: str, e: Exception) -> dict:
    """O2: a loader failed in a way it does not report itself (a bug, or damage nobody foresaw): say what
    happened and what to do, in the user's language (code "unexpected"); the traceback goes to the log."""
    logging.getLogger("signalviewer.files").warning("opening %s failed", path, exc_info=True)
    detail = f"{e.__class__.__name__}: {e}"[:200]
    return {"path": path, "code": "unexpected", "params": {"detail": detail},
            "message": f"The reader stopped on something it did not expect ({detail}) - the file may be damaged. "
                       "Try another copy of it; Help > Copy error details has what happened, for a report."}


def _load_error(path: str, e: Exception) -> dict:
    out: dict = {"path": path, "message": str(e)}
    if getattr(e, "code", None):
        out["code"] = getattr(e, "code", None)
        out["params"] = getattr(e, "params", {}) or {}
    return out
