"""
Data store: every loaded file gets a STABLE id (never an index), and every signal
is addressed as "<run_id>/<signal name>". Removing or reloading a file therefore
never shifts other files' signals (the root cause of many 2.x bugs).
"""

import contextlib
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from svcore.csv_loader import CSVImportSettings, load_csv
from svcore.mat_loader import MatNeedsExtra, load_mat
from svcore.can_loader import CAN_EXTS, CanError, load_can
from svcore.readers import ReaderError
from svcore.readers import read as user_read
from svcore.bin_loader import BinFormatError, load_bin
from svcore.tlog_loader import TLogError, load_tlog
from svcore.ulog_loader import ULogError, load_ulog
from svcore.mcap_loader import McapError, load_mcap
from svcore.hdf5_loader import Hdf5Error, load_hdf5
from svcore.parquet_loader import ParquetError, load_parquet
from svcore.models import Run
from svcore import time_axis
from svcore import investigate as inv
# A1: parts moved to their own modules - imported back, so `from app.store import ...` keeps working
from app.filecheck import (LoadError, SUPPORTED_EXTS, TEXT_EXTS, _can_csv, _csv_failure, _display_names, _text_file,  # noqa: F401
                           _text_with_zero_block, check_file, sniff_kind)
from svcore.transforms import REF, apply_transform, normalize_transform, ref_run, transform_refs  # noqa: F401
from app.livewatch import SETTLE_MAX, SETTLE_QUIET, TIME_SLACK, UPLOAD_DIR, LiveWatcher, _stat, run_format  # noqa: F401
from app import userreaders
from svcore.analysis import HOLD_OPS, NAN_OPS, SAMPLING_OPS, DerivedDef, compute, is_discrete
from svcore.memcache import CACHE as MEMCACHE, own_bytes
from collections import OrderedDict
import contextlib
import json
import re

log = logging.getLogger("signalviewer").getChild(__name__)

DERIVED_ID = "derived"


WIDE = 300          # files with more signals than this skip per-signal work at load


# T46: file colours - the same palette as the traces (frontend TRACE_COLORS), in the same order
FILE_COLORS = ["#3D8BFD", "#2FBF9F", "#E5677A", "#9B7BFF", "#7CC35A", "#F07B3F", "#4FC3E8", "#D08CE8", "#B8A33A", "#FF8FB1"]
MAX_TAG = 4


def _tags():
    """A, B, ... Z, AA, AB, ... - as many as needed."""
    letters = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    yield from letters
    n = 0
    while True:
        a, b = divmod(n, 26)
        yield letters[a % 26] + letters[b]
        n += 1


@dataclass
class LoadedRun:
    id: str
    run: Run
    name: str
    load_report: Dict = field(default_factory=dict)
    stat: Optional[Tuple[int, int]] = None        # (size, mtime_ns) of the file as last read
    last_change: float = 0.0                      # time.time() when new data was last read (live mode)
    pending_stat: Optional[Tuple[int, int]] = None   # changed file seen once, waiting until it is stable
    pending_since: float = 0.0                    # when a rewritten-as-a-whole file started changing
    read_at: float = 0.0                          # time.time() when its data was last read from the disk


def _vkey(v) -> str:
    """A short text for a version tuple (F34: sent to the UI as a cache key)."""
    import hashlib
    return hashlib.sha1(repr(v).encode()).hexdigest()[:12]


def _rate_of(sg, run) -> dict:
    """T22: samples and mean sample rate (Hz) of a signal, from its own time vector (or the run's).
    O(1): the length and the two ends only - cheap even for very wide files."""
    t = sg.time if sg.time is not None else run.time
    k = len(t) if t is not None else 0
    if k < 2:
        return {"n": int(k)}
    span = float(t[-1]) - float(t[0])
    return {"n": int(k), "rate": float(f"{(k - 1) / span:.4g}")} if span > 0 and np.isfinite(span) else {"n": int(k)}


def spark(t: np.ndarray, y: np.ndarray, points: int = 40) -> Optional[dict]:
    """T22: a tiny picture of a whole signal for the file list: min and max of `points` equal
    slices (by sample), so spikes still show. None for an empty or all-NaN signal."""
    y = np.asarray(y, dtype=np.float64)
    k = len(y)
    if k == 0:
        return None
    if k <= points:
        lo = hi = y
    else:
        edges = np.linspace(0, k, points + 1).astype(np.int64)[:-1]
        f = np.isfinite(y)
        lo = np.minimum.reduceat(np.where(f, y, np.inf), edges)
        hi = np.maximum.reduceat(np.where(f, y, -np.inf), edges)
        lo[~np.isfinite(lo)] = np.nan
        hi[~np.isfinite(hi)] = np.nan
    if not np.isfinite(lo).any():
        return None
    r = lambda a: [None if not np.isfinite(v) else float(f"{v:.6g}") for v in a]
    return {"lo": r(lo), "hi": r(hi)}


class Store:
    def __init__(self):
        self._lock = threading.RLock()
        self.runs: Dict[str, LoadedRun] = {}
        self.order: List[str] = []
        self.derived: Dict[str, DerivedDef] = {}
        # Changes made ON a signal itself (not new signals): {sig_id: {"expr", "scale", "offset", "dt"}}.
        # Applied every time the signal is read, so plots, cursor, stats, compare, reports and
        # exports all see the same values. The file's data is never modified.
        self.transforms: Dict[str, dict] = {}
        self._discrete: Dict[str, Tuple[str, bool]] = {}     # signal id -> (version, discrete)
        # T46: every open data file has a colour and a short tag (A, B, C...) - kept by id, so a
        # reload / replace / live update keeps them; given when a file is first described
        self.marks: Dict[str, Dict[str, str]] = {}
        self.live = LiveWatcher(self)             # live mode: what was added to the open files (A1)
        self._pending: set = set()                # P4: files of a batch being opened at once (their names)
        # 26.A5: how a numeric signal is read between its samples, by signal NAME (every file), as the
        # user corrected it: "state" (held - the value in force) or "value" (interpolated); absent =
        # detected (is_discrete). Kept in the workspace (ws.readAs) and sent here (/api/read_as).
        self.read_as: Dict[str, str] = {}

    # ------------------------------------------------------------------ files
    def open_file(self, path: str, settings: Optional[dict] = None) -> LoadedRun:
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            raise LoadError(f"File not found: {path}", "notFound")
        check_file(path, settings)
        # the file as it was when the read began: a file still growing while it is read is "newer on
        # the disk" afterwards, so the next refresh reads the rest (taken after the read, it looked
        # unchanged and a refresh read nothing new until the writing stopped)
        before = _stat(path)
        ext = os.path.splitext(path)[1].lower()
        with self._lock:                          # P4: the other files of the batch count for the names too
            all_paths = [r.run.file_path for r in self.runs.values()] + sorted(self._pending - {path}) + [path]
        name = _display_names(all_paths)[path]
        report: Dict = {}
        run = None
        for r in userreaders.for_ext(ext):          # T60: the user's readers first; None = not theirs
            try:
                run = user_read(r, path, name)
            except ReaderError as e:
                raise LoadError(str(e), "readerFailed") from None
            if run is not None:
                report["reader"] = r["name"]
                break
        if run is not None:
            pass
        elif ext not in SUPPORTED_EXTS:
            names = ", ".join(r["name"] for r in userreaders.for_ext(ext))
            raise LoadError(f"Your reader ({names}) found nothing to read in {os.path.basename(path)}.", "readerEmpty")
        elif ext in CAN_EXTS or (ext == ".csv" and _can_csv(path)):     # T40b: CAN bus logs + .dbc
            try:
                run, rep = load_can(path, name, [userreaders.folder()])
            except CanError as e:
                raise LoadError(str(e), "badCan") from None
            if run is None:
                ids = ", ".join(list(rep.get("unknownIds", {}))[:8])
                raise LoadError(f"None of the CAN ids in {os.path.basename(path)} are in the .dbc files ({', '.join(rep.get('dbc', []))})"
                                + (f"; the log has {ids}." if ids else "."), "badCan")
            report.update(rep)
        elif ext == ".mat":
            try:
                run, skipped = load_mat(path, name, (settings or {}).get("time_column"))
            except LoadError:
                raise
            except MatNeedsExtra as e:              # its own code: "badMat" would show "damaged" instead
                raise LoadError(str(e), "needsExtra") from None
            except Exception as e:
                if e.__class__.__name__ == "LoadCancelled":
                    raise
                raise LoadError("This is not a valid MATLAB .mat file, or it is damaged.", "badMat") from None
            if run is None:
                raise LoadError("No numeric vectors found in this MAT file.", "matNoData")
            if not run.signals and (getattr(run, "load_report", None) or {}).get("cutOff"):
                raise LoadError("This .mat file is cut off before its first complete signal "
                                "(MATLAB stopped while saving, or the copy is incomplete).", "badMat")
            report["skipped"] = skipped
        elif ext in (".parquet", ".pq"):                # T40
            try:
                run, rep = load_parquet(path, name, (settings or {}).get("time_column"))
            except ParquetError as e:
                raise LoadError(str(e), "badParquet") from None
            if run is None:
                why = "; ".join((rep.get("skipped") or [])[:4])
                raise LoadError("No numeric columns found in this file" + (f" (left out: {why})." if why else "."),
                                "noSignals")
            report.update(rep)
        elif ext in (".mcap", ".h5", ".hdf5"):         # T27
            loader2 = load_mcap if ext == ".mcap" else load_hdf5
            try:
                run, rep = loader2(path, name)
            except (McapError, Hdf5Error) as e:
                raise LoadError(str(e), "badMcap" if ext == ".mcap" else "badHdf5") from None
            if run is None:
                why = "; ".join((rep.get("skipped") or [])[:4])
                raise LoadError("No time series found in this file" + (f" (left out: {why})." if why else "."),
                                "noSignals")
            report.update(rep)
        elif ext in (".bin", ".tlog", ".ulg") and not (ext == ".tlog" and _text_file(path)):
            loader = {".bin": load_bin, ".tlog": load_tlog, ".ulg": load_ulog}[ext]
            try:
                run, rep = loader(path, name)
            except (BinFormatError, TLogError, ULogError) as e:
                raise LoadError(str(e)) from None
            if run is None:
                raise LoadError("No timed numeric data found in this flight log.", "logNoData")
            report.update(rep)
        else:
            s = CSVImportSettings.from_dict(settings or {})
            run = load_csv(path, all_paths, s)
            if run is None:
                raise _csv_failure(path, s)
        if not run.signals:
            raise LoadError("The file has no numeric signal columns.", "noSignals")
        # the time in the unit the user chose (Time axis dialog): kept in the import settings, so a
        # refresh, live mode and a saved session read it the same way
        scale = time_axis.scale_of(settings, "time_scale")
        own_scale = time_axis.scale_of(settings, "own_time_scale")
        if (scale != 1.0 or own_scale != 1.0) and run_format(run) in time_axis.TIME_SCALE_FORMATS:
            time_axis.apply_scales(run, scale, own_scale)
            run.import_settings = dict(run.import_settings or {})
            for k, v in (("time_scale", scale), ("own_time_scale", own_scale)):
                if v != 1.0:
                    run.import_settings[k] = v
        report.update(getattr(run, "load_report", None) or {})
        lr = LoadedRun(id=uuid.uuid4().hex[:8], run=run, name=name, load_report=report)
        lr.stat = before
        lr.read_at = time.time()
        with self._lock:
            self.runs[lr.id] = lr
            self.order.append(lr.id)
        return lr

    @contextlib.contextmanager
    def batch(self, paths: List[str]):
        """P4: files opened at once - each file's name knows the others (two log.bin from different
        folders are named by their folders, as one after the other); afterwards `order_as`."""
        full = {os.path.abspath(p) for p in paths}
        with self._lock:
            self._pending |= full
        try:
            yield
        finally:
            with self._lock:
                self._pending -= full

    def order_as(self, ids: List[str]) -> None:
        """P4: the files of a batch listed in the order asked, not the order they finished in."""
        with self._lock:
            want = [i for i in ids if i in self.order]
            slots = sorted(self.order.index(i) for i in want)
            for k, i in zip(slots, want):
                self.order[k] = i

    def add_pushed(self, name: str, run: Run, replace: bool = True) -> Tuple[LoadedRun, bool]:
        """T39: data sent from Python. With replace, a pushed run of the same name keeps its id
        (plots and derived signals follow the new data). Returns (run, is_new)."""
        with self._lock:
            if replace:
                for rid in self.order:
                    old = self.runs.get(rid)
                    if old and old.run.file_path == run.file_path:
                        fresh = LoadedRun(id=rid, run=run, name=old.name, load_report=dict(run.load_report or {}))
                        fresh.run.time_offset = old.run.time_offset
                        fresh.run.description = old.run.description
                        fresh.last_change = fresh.read_at = time.time()
                        self.runs[rid] = fresh
                        return fresh, False
            lr = LoadedRun(id=uuid.uuid4().hex[:8], run=run, name=name, load_report=dict(run.load_report or {}))
            lr.last_change = lr.read_at = time.time()
            self.runs[lr.id] = lr
            self.order.append(lr.id)
            return lr, True

    def mark(self, run_id: str) -> Dict[str, str]:
        """The file's colour and tag: the first free tag (A..Z, then AA...) and the least used
        colour of the open files."""
        with self._lock:
            m = self.marks.get(run_id)
            if m is None:
                live = [self.marks[i] for i in self.order if i in self.marks and i in self.runs]
                tags = {x["tag"] for x in live}
                tag = next(t for t in _tags() if t not in tags)
                used = {c: sum(1 for x in live if x["color"].upper() == c) for c in FILE_COLORS}
                color = min(FILE_COLORS, key=lambda c: (used[c], FILE_COLORS.index(c)))
                m = self.marks[run_id] = {"tag": tag, "color": color}
            return m

    def set_mark(self, run_id: str, tag: Optional[str] = None, color: Optional[str] = None) -> None:
        m = dict(self.mark(run_id))
        if tag is not None:
            tag = " ".join(tag.split())[:MAX_TAG]
            if tag:
                m["tag"] = tag
        if color is not None and re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            m["color"] = color.upper()
        self.marks[run_id] = m

    def remove(self, run_id: str):
        with self._lock:
            for k in [k for k in self._discrete if k.startswith(run_id + "/")]:
                self._discrete.pop(k, None)
            self.marks.pop(run_id, None)
            self.runs.pop(run_id, None)
            if run_id in self.order:
                self.order.remove(run_id)

    def replace_path(self, run_id: str, path: str) -> LoadedRun:
        """Point an open file at another file (same id, same import settings), so every
        plot that uses its signals keeps working (D-06)."""
        lr = self.get(run_id)
        settings = dict(lr.run.import_settings or {})
        settings.pop("format", None)
        fresh = self.open_file(path, settings)
        with self._lock:
            self.runs.pop(fresh.id)
            self.order.remove(fresh.id)
            fresh.run.time_offset = lr.run.time_offset
            fresh.run.description = lr.run.description
            fresh.id = lr.id
            fresh.name = os.path.basename(path)
            self.runs[lr.id] = fresh
        return fresh

    def set_description(self, run_id: str, text: str):
        self.get(run_id).run.description = text

    def rename(self, run_id: str, name: str):
        self.get(run_id).name = name

    def set_time_offset(self, run_id: str, offset: float):
        self.get(run_id).run.time_offset = float(offset)

    # ------------------------------------------------------------ the investigation (A1: svcore/investigate.py)
    def _source(self) -> "inv.Source":
        """The open files as the investigation reads them: signals as shown, names and state texts."""
        def signals(rid: str):
            lr = self.runs.get(rid)
            return None if lr is None else {n: sg.labels for n, sg in lr.run.signals.items()}
        return inv.Source(signal=self.signal, signals=signals, discrete=self.is_discrete, derived=list(self.derived),
                          runs=list(self.order), derived_run=DERIVED_ID)

    def evaluate_condition(self, text: str, exit_text: str = "", min_dur: float = 0.0, merge_gap: float = 0.0,
                           run_ids: Optional[List[str]] = None) -> Dict[str, dict]:
        try:
            return inv.evaluate_condition(self._source(), text, exit_text, min_dur, merge_gap, run_ids)
        except inv.InvestigateError as e:
            raise LoadError(str(e)) from None

    def occurrence_rows(self, runs: Dict[str, List[List[float]]], names: List[str]) -> List[dict]:
        return inv.occurrence_rows(self._source(), runs, names)

    def occurrence_windows(self, items: List[dict], align: str, pad: float) -> List[dict]:
        return inv.occurrence_windows(self._source(), items, align, pad)

    def occurrence_differ(self, runs: Dict[str, List[List[float]]], top: int = 25) -> List[dict]:
        return inv.occurrence_differ(self._source(), runs, top)

    def overview(self, run_id: str, rows: Optional[List[str]] = None) -> dict:
        return inv.overview(self._source(), self.get(run_id).run, run_id, rows, WIDE)

    def run_params(self, run_ids: Optional[List[str]] = None) -> Dict[str, Dict[str, float]]:
        return {rid: inv.run_params(self.runs[rid].run, WIDE) for rid in (run_ids or list(self.order))
                if rid in self.runs and rid != DERIVED_ID}

    def first_changes(self, sig_ids: List[str], run_ids: List[str], a: float, b: float,
                      base: Optional[Tuple[float, float]] = None, k: float = 4.0, persist: int = 3) -> List[dict]:
        return inv.first_changes(self._source(), sig_ids, run_ids, a, b, base, k, persist)

    def change_clusters(self, items: List[dict], a: float, b: float, refs: List[str], k: float = 4.0,
                        persist: int = 3, event: Optional[str] = None, shape_top: int = 30) -> dict:
        return inv.change_clusters(self._source(), items, a, b, refs, k, persist, event, shape_top)

    def suggest_condition(self, sig_ids: List[str], a: float, b: float) -> dict:
        return inv.suggest_condition(self._source(), sig_ids, a, b)

    def lag_between(self, a_id: str, b_id: str, t0: float, t1: float) -> dict:
        return inv.lag_between(self._source(), a_id, b_id, t0, t1)

    # ------------------------------------------------------------ time axis
    def time_axis_info(self, lr: "LoadedRun", candidates: bool = False) -> dict:
        """What the Time axis dialog may change in this file, and how it is set now (with
        `candidates`, the columns that can become the time - not in every file description: a
        file can have thousands)."""
        r = lr.run
        fmt = run_format(r)
        st = r.import_settings or {}
        pushed = r.file_path.startswith("python:")
        can_column = fmt in time_axis.TIME_COLUMN_FORMATS and not pushed
        return {
            "canColumn": can_column,
            "canScale": fmt in time_axis.TIME_SCALE_FORMATS and not pushed,
            "column": r.time_source,
            "columnUnit": time_axis.unit_from_name(r.time_source or ""),
            "scale": time_axis.scale_of(st, "time_scale"),
            "ownScale": time_axis.scale_of(st, "own_time_scale"),
            "offset": float(r.time_offset or 0.0),
            "ownTimes": sum(1 for sg in r.signals.values() if sg.time is not None),
            # signals that can become the time: numbers on the main time (not text, not on a time
            # of their own) - shown by their name in the app, chosen by their name in the file
            **({"candidates": [n for n, sg in r.signals.items() if sg.time is None and not sg.labels] if can_column else []}
               if candidates else {}),
            "sorted": bool((lr.load_report or {}).get("sorted")),
        }

    def check_time_axis(self, run_id: str, column: Optional[str]) -> dict:
        """Before a change: what the column would look like as the time, and which of the file's
        new signals and edits compute against time (their meaning changes with the axis)."""
        lr = self.get(run_id)
        info = self.time_axis_info(lr, candidates=True)
        out: dict = {"info": info}
        if column:
            sg = lr.run.signals.get(column)
            if sg is None or sg.time is not None or sg.labels:
                raise LoadError(f"{column} can not be the time of this file (it is not a numeric column on the file's time).")
            out["column"] = time_axis.analyze(np.asarray(sg.data), lr.run.original_names.get(column, column))
            out["brokenDerived"] = [n for n, d in self.derived.items() if f"{run_id}/{column}" in d.sources]
        out.update(self._time_dependent(run_id))
        return out

    def _time_dependent(self, run_id: str) -> dict:
        """New signals (and edits) of this file computed against time: derivative, integral,
        filters (a cut-off in Hz), expressions with deriv / integ / lowpass / highpass / t, and the
        user's Python operations (they may). Followed through signals made from signals."""
        timed = re.compile(r"\b(deriv|integ|lowpass|highpass|t)\b")

        def is_timed(d: DerivedDef) -> bool:
            if d.op in ("derivative", "integral", "lowpass", "highpass", "vecsmooth", "py"):
                return True
            return d.op == "expr" and bool(timed.search(str(d.params.get("text") or d.params.get("expr") or "")))

        mine: Dict[str, bool] = {}

        def belongs(name: str, seen: frozenset = frozenset()) -> bool:
            if name in mine:
                return mine[name]
            d = self.derived.get(name)
            if d is None or name in seen:
                return False
            hit = any(src.startswith(run_id + "/") or (src.startswith(DERIVED_ID + "/")
                      and belongs(src.split("/", 1)[1], seen | {name})) for src in d.sources)
            mine[name] = hit
            return hit

        derived = [n for n, d in self.derived.items() if belongs(n) and is_timed(d)]
        edits = [sid.split("/", 1)[1] for sid, spec in self.transforms.items()
                 if sid.startswith(run_id + "/") and (spec.get("dt") or timed.search(str(spec.get("expr") or "")))]
        return {"timedDerived": derived, "timedEdits": edits}

    def set_time_axis(self, run_id: str, column: Optional[str], scale: float, own_scale: float,
                      offset: float, times: Optional[List[float]] = None) -> dict:
        """Change the file's time: another column (CSV / MAT / Parquet), a scale (the unit) and the
        offset. The file is read again in its place; signals made from it follow by themselves.
        Returns the file, the settings before (for Undo) and `times` (positions on the old axis:
        cursor, zoom, notes) on the new one - None where the rows moved."""
        lr = self.get(run_id)
        info = self.time_axis_info(lr)
        before = {"column": info["column"], "scale": info["scale"], "ownScale": info["ownScale"], "offset": info["offset"]}
        settings = dict(lr.run.import_settings or {})
        settings.pop("format", None)
        # the column by its name in the app, or (Undo: the old time is a signal now, perhaps
        # renamed) by its name in the file
        target = None
        if column:
            col = str(column)
            if col in lr.run.signals:
                target = lr.run.original_names.get(col, col)
            elif col in lr.run.original_names.values() or col == info["column"]:
                target, col = col, next((n for n, o in lr.run.original_names.items() if o == col), col)
            else:
                raise LoadError(f"{col} is not a column of this file.")
        changes_column = target is not None and target != info["column"]
        if changes_column:
            if not info["canColumn"]:
                raise LoadError("The time of this file comes from the file itself; only its offset can be changed.")
            sg = lr.run.signals.get(col)
            if sg is None or sg.time is not None or sg.labels:
                raise LoadError(f"{col} can not be the time of this file (it is not a numeric column on the file's time).")
            settings["time_column"] = target
        for key, val in (("time_scale", scale), ("own_time_scale", own_scale)):
            v = float(val)
            if not np.isfinite(v) or v <= 0:
                raise LoadError("The scale must be a positive number (a negative one would turn time backwards).")
            if v != 1.0 and not info["canScale"]:
                raise LoadError("The time of this file comes from the file itself in seconds; only its offset can be changed.")
            if v == 1.0:
                settings.pop(key, None)
            else:
                settings[key] = v
        old_time, old_offset = np.asarray(lr.run.time), float(lr.run.time_offset or 0.0)
        old_sorted = bool((lr.load_report or {}).get("sorted"))
        fresh = self._read_again(lr, settings, offset=float(offset))
        new_sorted = bool((fresh.load_report or {}).get("sorted"))
        same_rows = not changes_column or (not old_sorted and not new_sorted)
        mapped = time_axis.map_times(old_time, old_offset, np.asarray(fresh.run.time), float(fresh.run.time_offset or 0.0),
                                     same_rows, list(times or []))
        return {"run": self.describe(fresh), "before": before, "times": mapped}

    def reload(self, run_id: str) -> LoadedRun:
        lr = self.get(run_id)
        if lr.run.file_path.startswith("python:"):      # T39: no file behind it
            raise LoadError("This data was sent from Python: send it again to update it.", "pushed")
        settings = dict(lr.run.import_settings or {})
        settings.pop("format", None)
        return self._read_again(lr, settings)

    def _read_again(self, lr: "LoadedRun", settings: dict, offset: Optional[float] = None) -> "LoadedRun":
        """Read an open file again with these import settings, in its place: the same id (and
        therefore every signal reference), name, description and - unless given - time offset."""
        fresh = self.open_file(lr.run.file_path, settings)
        with self._lock:  # keep the id (and therefore every signal reference)
            self.runs.pop(fresh.id)
            self.order.remove(fresh.id)
            fresh.run.time_offset = lr.run.time_offset if offset is None else float(offset)
            fresh.run.description = lr.run.description
            fresh.id, fresh.name = lr.id, lr.name
            fresh.last_change = lr.last_change
            self.runs[lr.id] = fresh
        if run_format(fresh.run) == "csv":
            from svcore.csv_loader import prune_cache
            prune_cache(source=os.path.abspath(fresh.run.file_path))   # its copy as it was: no longer read
        return fresh

    # live mode (A1: app/livewatch.py)
    def poll_appends(self) -> List[str]:
        return self.live.poll_appends()

    def activity(self) -> Dict[str, float]:
        return self.live.activity()

    def reload_all(self, progress=None, cancelled=None) -> Dict[str, list]:
        """Read every open file again (refresh all). Files dragged in as copies are skipped (they
        cannot follow the original). Returns {"reloaded": [...], "unchanged": [...], "errors": [...]}."""
        out: Dict[str, list] = {"reloaded": [], "unchanged": [], "errors": [], "skipped": []}
        ids = [rid for rid in self.order if rid in self.runs]
        for i, rid in enumerate(ids):
            if cancelled and cancelled():
                break
            lr = self.runs.get(rid)
            if lr is None:
                continue
            if lr.run.file_path.startswith((UPLOAD_DIR + os.sep, "python:")):   # copies, data sent from Python
                out["skipped"].append(rid)
                continue
            if progress:
                progress(i / max(1, len(ids)), lr.name)
                # the loader's own progress, inside this file's share of the bar
                from svcore.csv_loader import set_progress_context
                set_progress_context(lambda f, _ph, i=i, nm=lr.name: progress((i + f) / max(1, len(ids)), nm), cancelled)
            try:
                if _stat(lr.run.file_path) == lr.stat and lr.stat is not None:
                    out["unchanged"].append(rid)
                else:
                    self.reload(rid)
                    out["reloaded"].append(rid)
            except Exception as e:
                out["errors"].append({"id": rid, "name": lr.name, "message": str(e) or e.__class__.__name__})
        return out

    def newer_on_disk(self) -> Dict[str, float]:
        return self.live.newer_on_disk()

    def new_files(self, since: float, known: Optional[set] = None) -> List[dict]:
        return self.live.new_files(since, known)

    # the watcher's state, where callers (and tests) have always looked for it
    @property
    def poll_errors(self) -> Dict[str, str]:
        return self.live.poll_errors

    @property
    def writing(self) -> List[str]:
        return self.live.writing

    @property
    def _poll_lock(self) -> threading.Lock:
        return self.live.lock

    # ---------------------------------------------------------------- lookups
    def get(self, run_id: str) -> LoadedRun:
        lr = self.runs.get(run_id)
        if lr is None:
            raise KeyError(run_id)
        return lr

    def signal(self, sig_id: str) -> Tuple[np.ndarray, np.ndarray]:
        """Time (with run offset) and data for "<run_id>/<name>" or "derived/<name>"."""
        run_id, _, name = sig_id.partition("/")
        if run_id == DERIVED_ID:
            d = self.derived.get(name)
            if d is None:
                raise KeyError(sig_id)
            return self._refresh_derived(d)
        lr = self.get(run_id)
        if name not in lr.run.signals:
            raise KeyError(sig_id)
        raw = lr.run.get_signal_data(name)
        spec = self.transforms.get(sig_id)
        return self._transformed(sig_id, raw, spec) if spec and set(spec) - {"unit"} else raw   # (a unit alone: same values)

    def signal_parts(self, sig_id: str) -> Tuple[np.ndarray, np.ndarray, float]:
        """P1: (time, data, offset) with signal(sig_id) == (time + offset, data) - the run's time offset
        NOT applied, so a lookup (a plot window, the cursor, statistics) costs no copy of the time
        vector. A changed signal (transform) or a derived one: its own time, offset 0."""
        run_id, _, name = sig_id.partition("/")
        if run_id != DERIVED_ID:
            lr = self.get(run_id)
            if name not in lr.run.signals:
                raise KeyError(sig_id)
            spec = self.transforms.get(sig_id)
            if not (spec and set(spec) - {"unit"}):
                t, y, off = lr.run.signal_parts(name)
                return t, y, off
        t, y = self.signal(sig_id)
        return t, y, 0.0

    def _transformed(self, sig_id: str, raw, spec: dict):
        # P2: the shared memory cache (bytes, locked; the private OrderedDict raced: a KeyError from
        # it read as "signal missing" when two requests came at once)
        key = ("transform", sig_id, self._raw_version(sig_id), self._ref_versions(sig_id, spec), json.dumps(spec, sort_keys=True))
        hit = MEMCACHE.get(key)
        if hit is not None:
            return hit
        t, y = apply_transform(raw[0], raw[1], spec, self._ref_reader(sig_id))
        MEMCACHE.drop(lambda k: k[0] == "transform" and k[1] == sig_id and k != key)   # an older version
        return MEMCACHE.put(key, (t, y), "transform", nbytes=own_bytes((t, y), [raw[0]]))

    def set_transforms(self, specs: Dict[str, Optional[dict]]) -> Dict[str, Optional[dict]]:
        """Set (or clear, with None) transforms; validates every one first. Returns the previous ones."""
        clean = {}
        for sid, spec in specs.items():
            run_id, _, name = sid.partition("/")
            if run_id == DERIVED_ID or run_id not in self.runs or name not in self.runs[run_id].run.signals:
                raise KeyError(sid)
            spec = normalize_transform(spec)
            if spec:
                raw = self.runs[run_id].run.get_signal_data(name)
                n = None if transform_refs(spec) else 64     # with other signals: all of x (they may start later)
                apply_transform(raw[0][:n], raw[1][:n], spec, self._ref_reader(sid))   # fails fast on a bad expression
            clean[sid] = spec
        previous = {sid: self.transforms.get(sid) for sid in clean}
        with self._lock:
            for sid, spec in clean.items():
                if spec:
                    self.transforms[sid] = spec
                else:
                    self.transforms.pop(sid, None)
        return previous

    def _ref_reader(self, sig_id: str):
        """Q89 / Q90: the reader of the other signals an edit of `sig_id` names, as read (raw):
        {Name} from its own file, {@<run id>:Name} from that file."""
        own = sig_id.partition("/")[0]

        def read(token: str):
            rid = ref_run(token) or own
            name = token[token.index(":") + 1:] if ref_run(token) else token
            lr = self.runs.get(rid)
            if lr is None and ref_run(token):
                # like a derived signal whose source file was closed: not shown, never made up
                raise KeyError(f"{name}: its file is no longer open.")
            if lr is None or name not in lr.run.signals:
                return None
            return lr.run.get_signal_data(name)
        return read

    def _ref_versions(self, sig_id: str, spec: Optional[dict]):
        """Q90: the data versions of the OTHER files an edit reads - part of its cache key, so a
        reload of such a file (live mode) recomputes it."""
        own = sig_id.partition("/")[0]
        rids = sorted({r for r in (ref_run(tk) for tk in transform_refs(spec)) if r and r != own})
        return tuple(self._raw_version(f"{r}/") for r in rids)

    def _raw_version(self, sig_id: str):
        run_id = sig_id.partition("/")[0]
        lr = self.runs.get(run_id)
        return (run_id, lr.run.uid, lr.run.data_version, lr.run.time_offset) if lr else None

    def version(self, sig_id: str):
        """Changes whenever the signal's data changes (cache key)."""
        run_id, _, name = sig_id.partition("/")
        if run_id == DERIVED_ID:
            d = self.derived.get(name)
            return ("d", name, d.serial, tuple(self.version(s) for s in d.sources)) if d else None
        base = self._raw_version(sig_id)
        fix = self.read_as.get(name)
        if base and fix is not None:                  # 26.A5: read another way -> what is made from it changes
            base = (*base, fix)
        spec = self.transforms.get(sig_id)
        return (base, self._ref_versions(sig_id, spec), json.dumps(spec, sort_keys=True)) if (base and spec) else base

    # -------------------------------------------------------------- derived
    def _refresh_derived(self, d: DerivedDef) -> Tuple[np.ndarray, np.ndarray]:
        """The derived signal's (time, data), computed again when a source changed."""
        versions = tuple(self.version(s) for s in d.sources)
        # P2: kept in the shared memory cache (bounded in bytes) - computed again when pushed out
        key = ("derived", d.name, d.serial, versions)
        hit = MEMCACHE.get(key)
        if hit is not None:
            return hit
        if any(v is None for v in versions):
            raise KeyError("A source signal of this derived signal is no longer open.")
        rep: dict = {}
        t, y = compute(d.op, [self.signal(s) for s in d.sources], d.params, [self.is_state(s) for s in d.sources], rep)
        d.report = rep
        MEMCACHE.drop(lambda k: k[0] == "derived" and k[1] == d.name and k != key)
        return MEMCACHE.put(key, (t, y), "derived", nbytes=own_bytes((t, y), [self.signal_parts(s)[0] for s in d.sources]))

    def short_name(self, sig_id: str) -> str:
        run_id, _, name = sig_id.partition("/")
        if run_id == DERIVED_ID:
            return name
        lr = self.runs.get(run_id)
        # add the file name only when another open file has a signal with the same name
        clash = any(rid != run_id and name in o.run.signals for rid, o in self.runs.items())
        return f"{name} ({lr.name})" if lr and clash else name

    def add_derived(self, op: str, sources: List[str], params: dict, name: Optional[str] = None,
                    legacy: bool = False) -> DerivedDef:
        """legacy: a recipe restored from a session / autosave. C3: an operation with a missing-data
        policy always stores it explicitly - a new recipe "propagate", a restored one WITHOUT `nan`
        (saved before 1.23) "legacy", so its numbers stay what they were; Undo and Clear re-send the
        listed params, which carry it. C2b: the same for `hold` (an operation that aligns sources) -
        new true, restored without it false (a state source interpolated as before 1.23)."""
        for s in sources:
            self.signal(s)  # validates ids (KeyError)
        params = dict(params or {})
        if op in NAN_OPS and "nan" not in params:
            params["nan"] = "legacy" if legacy else "propagate"
        if op in HOLD_OPS and "hold" not in params:
            params["hold"] = not legacy     # C2b: saved before 1.23 -> the old alignment, old numbers
        if op in SAMPLING_OPS and "sampling" not in params:
            params["sampling"] = "samples" if legacy else "time"   # 26.A3: likewise
        d = DerivedDef(name="", op=op, sources=list(sources), params=params)
        base = (name or "").strip() or d.formula(self.short_name)
        base = base.replace("/", "∕")  # "/" separates run id and name in signal ids
        final, k = base, 2
        while final in self.derived:
            final, k = f"{base} ({k})", k + 1
        d.name = final
        self._refresh_derived(d)       # compute now so errors surface immediately
        with self._lock:
            self.derived[final] = d
        return d

    def remove_derived(self, name: str):
        with self._lock:
            self.derived.pop(name, None)

    def rename_derived(self, old: str, new: str) -> str:
        """A derived signal's new name, in place (its place in the list kept): the signals made from
        it now name it so - their sources, and the {name} in a formula's text. Returns the name
        given ("/" is replaced: it separates the run id and the name in signal ids)."""
        new = new.strip().replace("/", "∕")
        if not new:
            raise ValueError("The name is empty.")
        with self._lock:
            if old not in self.derived:
                raise KeyError(old)
            if new == old:
                return new
            if new in self.derived:
                raise ValueError(f"A signal named \"{new}\" already exists - choose another name.")
            items = list(self.derived.items())
            self.derived.clear()
            for name, d in items:
                if name == old:
                    d.name = new
                    name = new
                d.sources = [f"{DERIVED_ID}/{new}" if x == f"{DERIVED_ID}/{old}" else x for x in d.sources]
                text = d.params.get("text") if isinstance(d.params, dict) else None
                if isinstance(text, str) and "{" + old + "}" in text:
                    d.params = {**d.params, "text": text.replace("{" + old + "}", "{" + new + "}")}
                self.derived[name] = d
        return new

    def invalidate_derived(self, op: Optional[str] = None) -> List[str]:
        """F34: recompute these derived signals on their next read (op None = all) - for the
        Python operations, whose code can change while their sources do not."""
        hit = []
        with self._lock:
            for name, d in self.derived.items():
                if op is None or d.op == op:
                    d.invalidate()
                    hit.append(name)
        return hit

    @staticmethod
    def _log_summary(run: Run) -> Optional[dict]:
        """Counts for files that carry a flight log's parameters / events (ArduPilot .bin).
        None for every other file, so nothing log-related appears for them."""
        df = getattr(run, "_flightlog", None)
        if df is None or not (df.param_first or df.events):
            return None
        return {"params": len(df.param_first), "events": len(df.events),
                "errors": sum(1 for e in df.events if e["level"] == "error"),
                "warnings": sum(1 for e in df.events if e["level"] == "warning")}

    def log_info(self, run_id: str) -> Optional[dict]:
        lr = self.runs.get(run_id)
        if lr is None:
            return None
        df = getattr(lr.run, "_flightlog", None)
        if df is None:
            return None
        info = df.log_info()
        info["timeOffset"] = float(lr.run.time_offset or 0.0)
        return info

    def labels(self, sig_id: str) -> Optional[Dict[int, str]]:
        run_id, _, name = sig_id.partition("/")
        lr = self.runs.get(run_id)
        sg = lr.run.signals.get(name) if lr else None
        return sg.labels if sg is not None else None

    def is_state(self, sig_id: str) -> bool:
        """Text values, or a numeric signal with a few whole-number levels (gear, mode number...) - or
        what the user said it is (26.A5; texts are always states)."""
        return bool(self.labels(sig_id)) or self.is_discrete(sig_id)

    def set_read_as(self, names: Dict[str, str]) -> None:
        """26.A5: the user's corrections, all of them (the workspace's map replaces the old one)."""
        clean = {str(k): v for k, v in (names or {}).items() if v in ("state", "value")}
        with self._lock:
            self.read_as = clean

    def is_discrete(self, sig_id: str) -> bool:
        """A numeric signal read as a state: the user's correction for its name, else detected."""
        fix = self.read_as.get(sig_id.partition("/")[2])
        if fix is not None and not sig_id.startswith(DERIVED_ID + "/"):
            return fix == "state"
        return self.detected_discrete(sig_id)

    def detected_discrete(self, sig_id: str) -> bool:
        # one entry per signal, for its current version: keyed by version it gained an entry per
        # signal on every live update (a slow leak over a long live session)
        # the same loaded file and the same edit: rows appended in live mode do not turn a signal
        # into a state one or back - re-testing every signal on every live update (up to 200k
        # samples each, for files of up to WIDE signals) cost more than a second per poll
        run_id, _, _name = sig_id.partition("/")
        lr = self.runs.get(run_id)
        ver = repr((lr.run.uid, json.dumps(self.transforms.get(sig_id), sort_keys=True)) if lr is not None
                   else self.version(sig_id))
        hit = self._discrete.get(sig_id)
        if hit is None or hit[0] != ver:
            try:
                val = is_discrete(self.signal(sig_id)[1])
            except (KeyError, ValueError, TypeError):    # closed, or not numbers
                val = False
            hit = self._discrete[sig_id] = (ver, val)
        return hit[1]

    def describe(self, lr: LoadedRun) -> dict:
        r = lr.run
        return {
            "id": lr.id,
            "name": lr.name,
            "path": r.file_path,
            "format": run_format(r) if run_format(r) in ("mat", "bin", "tlog", "ulg", "mcap", "hdf5", "parquet") else "csv",
            **({"log": self._log_summary(r)} if self._log_summary(r) else {}),
            "samples": int(r.sample_count),
            "version": f"{r.uid}.{r.data_version}",                # F34: changes whenever the data does
            "start": float(r.start_time) + float(r.time_offset or 0),
            "end": float(r.end_time) + float(r.time_offset or 0),
            "timeOffset": float(r.time_offset or 0),
            **self.mark(lr.id),                                  # T46: "tag", "color"
            "importSettings": {k: v for k, v in (r.import_settings or {}).items()},
            "timeAxis": self.time_axis_info(lr),
            # discrete detection reads every column: for wide files it is done on demand instead
            "signals": [{"id": f"{lr.id}/{n}", "name": n, **_rate_of(sg, r),
                         # (a big log's values not read yet: on demand too - describing must not read them all)
                         "discrete": True if sg.labels else (self.is_discrete(f"{lr.id}/{n}")
                                                             if len(r.signals) <= WIDE and getattr(sg, "loaded", True) else None),
                         **({"labels": {str(k): v for k, v in sg.labels.items()}} if sg.labels else {}),
                         **({"transform": self.transforms[f"{lr.id}/{n}"]} if f"{lr.id}/{n}" in self.transforms else {})}
                        for n, sg in r.signals.items()],
            "report": lr.load_report,
            "description": r.description or "",
            # dragged into a browser window: the app works on a COPY, edits to the original are not seen
            "copy": os.path.abspath(lr.run.file_path).startswith(UPLOAD_DIR + os.sep),
            # Q123: when the version shown was saved to the disk (the file list shows it) and when the
            # app read it
            **({"fileTime": lr.stat[1] / 1e9} if lr.stat else {}),
            **({"readAt": lr.read_at} if lr.read_at else {}),
        }

    def describe_derived(self) -> Optional[dict]:
        if not self.derived:
            return None
        sigs = []
        for name, d in self.derived.items():
            try:
                t, _ = self.signal(f"{DERIVED_ID}/{name}")
                ok, n = True, len(t)
            except (KeyError, ValueError):     # a source was closed / the formula fails now
                ok, n = False, 0
            sigs.append({"id": f"{DERIVED_ID}/{name}", "name": name, "discrete": False, "op": d.op,
                         "sources": d.sources, "params": d.params, "formula": d.formula(self.short_name),
                         "valid": ok, "samples": n, "version": _vkey(self.version(f"{DERIVED_ID}/{name}")),
                         **({"quality": d.report} if ok and d.report else {})})
        return {"id": DERIVED_ID, "name": "Derived", "path": "", "format": "derived", "samples": 0,
                "start": 0, "end": 0, "timeOffset": 0, "importSettings": {}, "signals": sigs, "report": {}}

    def list(self) -> List[dict]:
        out = [self.describe(self.runs[i]) for i in self.order if i in self.runs]
        d = self.describe_derived()
        return out + ([d] if d else [])


store = Store()
