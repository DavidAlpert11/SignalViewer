"""
Data store: every loaded file gets a STABLE id (never an index), and every signal
is addressed as "<run_id>/<signal name>". Removing or reloading a file therefore
never shifts other files' signals (the root cause of many 2.x bugs).
"""

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from svcore.csv_loader import CSVImportSettings, _read_head_lines, append_new_rows, detect_delimiter, load_csv
from svcore.mat_loader import load_mat
from svcore.bin_loader import BinFormatError, append_new_messages, load_bin
from svcore.tlog_loader import TLogError, append_tlog, load_tlog
from svcore.ulog_loader import ULogError, load_ulog
from svcore.mcap_loader import McapError, load_mcap
from svcore.hdf5_loader import Hdf5Error, load_hdf5
from svcore.models import Run
from svcore.analysis import DerivedDef, OpError, compute, is_discrete
from svcore.formula import evaluate as _evaluate_formula
from collections import OrderedDict
import json
import re

log = logging.getLogger("signalviewer").getChild(__name__)

DERIVED_ID = "derived"


def normalize_transform(spec: Optional[dict]) -> Optional[dict]:
    """Keep only meaningful parts; an all-default transform is no transform."""
    if not spec:
        return None
    out: dict = {}
    expr = str(spec.get("expr") or "").strip()
    if expr and expr != "x":
        out["expr"] = expr
    for k, default in (("scale", 1.0), ("offset", 0.0), ("dt", 0.0)):
        v = spec.get(k)
        if v is not None and v != "" and float(v) != default:
            out[k] = float(v)
    return out or None


def apply_transform(t, y, spec: dict):
    """y' = scale * f(x) + offset, t' = t + dt;  f is an expression in x (and t)."""
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if spec.get("expr"):
        expr = re.sub(r"\bx\b", "v0", spec["expr"])
        try:
            t2, y = _evaluate_formula(expr, [(t, y)], lambda tt, ts, ys: np.interp(tt, ts, ys))
        except ValueError as e:
            raise OpError(str(e)) from None
        t = t2
    if "scale" in spec or "offset" in spec:
        y = y * spec.get("scale", 1.0) + spec.get("offset", 0.0)
    if spec.get("dt"):
        t = t + spec["dt"]
    return t, y
WIDE = 300          # files with more signals than this skip per-signal work at load
TIME_SLACK = 2.0   # seconds: see new_files()
UPLOAD_DIR = os.path.join(os.path.expanduser("~"), ".signalviewer", "uploads")


@dataclass
class LoadedRun:
    id: str
    run: Run
    name: str
    load_report: Dict = field(default_factory=dict)
    stat: Optional[Tuple[int, int]] = None        # (size, mtime_ns) of the file as last read
    last_change: float = 0.0                      # time.time() when new data was last read (live mode)
    pending_stat: Optional[Tuple[int, int]] = None   # changed file seen once, waiting until it is stable


def _stat(path: str) -> Optional[Tuple[int, int]]:
    try:
        st = os.stat(path)
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


def run_format(run: Run) -> str:
    return (run.import_settings or {}).get("format") or "csv"


class LoadError(Exception):
    """A file that cannot be opened. `code` + `params` let the UI show the reason in its own
    language (the English message stays as the fallback)."""
    def __init__(self, message: str, code: Optional[str] = None, **params):
        super().__init__(message)
        self.code = code
        self.params = params


SUPPORTED_EXTS = (".csv", ".txt", ".tsv", ".dat", ".mat", ".bin", ".tlog", ".ulg", ".mcap", ".h5", ".hdf5")
TEXT_EXTS = (".csv", ".txt", ".tsv", ".dat")
_KIND_EXT = {"mat": ".mat", "ulg": ".ulg", "bin": ".bin", "hdf5": ".h5", "mcap": ".mcap"}
# the extensions a signature may have: HDF5 is also MATLAB v7.3 (T27)
_KIND_OK = {"mat": (".mat",), "hdf5": (".h5", ".hdf5", ".mat"), "ulg": (".ulg",), "bin": (".bin",), "mcap": (".mcap",)}


def sniff_kind(head: bytes) -> Optional[str]:
    """What a file is by its first bytes, for the formats that have a clear signature."""
    if head.startswith(b"MATLAB"):
        return "mat"
    if head.startswith(b"\x89HDF\r\n\x1a\n"):         # HDF5: .h5 / .hdf5, or a MATLAB v7.3 .mat
        return "hdf5"
    if head.startswith(b"\x89MCAP"):                  # ROS 2 / Foxglove recording
        return "mcap"
    if head.startswith(b"ULog\x01\x12\x35"):
        return "ulg"
    if head.startswith(b"\xa3\x95\x80"):          # ArduPilot DataFlash: starts with an FMT message
        return "bin"
    return None


def _text_with_zero_block(head: bytes) -> bool:
    """Text with a run of zero bytes in it (a file cut by a power loss, a half-finished copy)
    is still text: without the zeros it is printable lines. Real binary files are not (T33)."""
    rest = head.replace(b"\x00", b"")
    if len(rest) < 16 or b"\n" not in rest:
        return False
    printable = sum(1 for b in rest if b in (9, 10, 13) or 32 <= b < 127 or b >= 0xC2)
    return printable >= 0.95 * len(rest)


def check_file(path: str, settings: Optional[dict] = None) -> None:
    """Cheap checks BEFORE a loader runs, so the user is told what is wrong in plain words:
    unsupported type, empty file, a binary file with a text extension, or a known format
    with the wrong extension. Raises LoadError."""
    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)
    if ext not in SUPPORTED_EXTS:
        raise LoadError(f"Unsupported file type ({ext or 'no extension'}). Supported: "
                        + ", ".join(e[1:].upper() for e in SUPPORTED_EXTS) + ".",
                        "unsupported", ext=ext or "-", supported=", ".join(e[1:].upper() for e in SUPPORTED_EXTS))
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError as e:
        raise LoadError(f"The file cannot be read: {e.strerror or e}", "unreadable", reason=str(e.strerror or e)) from None
    if size == 0:
        raise LoadError("The file is empty.", "empty")
    kind = sniff_kind(head)
    if kind and ext not in _KIND_OK[kind]:
        raise LoadError(f"{name} looks like a {_KIND_EXT[kind]} file, but its extension is {ext}. "
                        f"Rename it to {_KIND_EXT[kind]} and open it again.", "wrongExt", ext=ext, real=_KIND_EXT[kind])
    if ext in TEXT_EXTS:
        enc = str((settings or {}).get("encoding") or "").lower().replace("-", "").replace("_", "")
        wide = enc.startswith(("utf16", "utf32")) or head.startswith((b"\xff\xfe", b"\xfe\xff"))
        if not wide and b"\x00" in head and not _text_with_zero_block(head):
            raise LoadError("This is a binary file, not text: it cannot be read as CSV.", "binaryText")


def _display_names(paths: List[str]) -> Dict[str, str]:
    """File name, plus parent folder when two files share a name."""
    names = {}
    base_count: Dict[str, int] = {}
    for p in paths:
        b = os.path.basename(p)
        base_count[b] = base_count.get(b, 0) + 1
    for p in paths:
        b = os.path.basename(p)
        names[p] = b if base_count[b] == 1 else f"{os.path.basename(os.path.dirname(p))}/{b}"
    return names


def _csv_failure(path: str, s: CSVImportSettings) -> LoadError:
    """Why a text file could not be read, as precisely as a quick look at its first lines allows."""
    generic = LoadError("Could not read this file as CSV. Check the delimiter, header row and time column.", "csvFailed")
    try:
        skip = s.skip_rows or 0
        lines = [ln for ln in _read_head_lines(path, 60, s.encoding, skip=skip) if ln.strip()]
        if len(lines) <= 1:
            return LoadError("The file has a header row but no data rows.", "csvNoRows")
        delim = s.delimiter or detect_delimiter(path, skip_rows=skip)
        numeric = False
        for ln in lines[1:]:
            for cell in ln.rstrip("\r\n").split(delim):
                try:
                    float(cell.strip().replace(",", ".") if delim != "," else cell.strip())
                    numeric = True
                    break
                except ValueError:
                    continue
            if numeric:
                break
        if not numeric:
            return LoadError("No numeric values were found in this file.", "csvNoNumbers")
    except Exception:                   # only a better reason was looked for; the generic one stands
        log.debug("could not find a specific reason for %s", path, exc_info=True)
    return generic


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
        self._tcache: "OrderedDict[tuple, tuple]" = OrderedDict()
        self._discrete: Dict[str, bool] = {}

    # ------------------------------------------------------------------ files
    def open_file(self, path: str, settings: Optional[dict] = None) -> LoadedRun:
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            raise LoadError(f"File not found: {path}", "notFound")
        check_file(path, settings)
        ext = os.path.splitext(path)[1].lower()
        all_paths = [r.run.file_path for r in self.runs.values()] + [path]
        name = _display_names(all_paths)[path]
        report: Dict = {}
        if ext == ".mat":
            try:
                run, skipped = load_mat(path, name, (settings or {}).get("time_column"))
            except LoadError:
                raise
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
        elif ext in (".bin", ".tlog", ".ulg"):
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
        report.update(getattr(run, "load_report", None) or {})
        lr = LoadedRun(id=uuid.uuid4().hex[:8], run=run, name=name, load_report=report)
        lr.stat = _stat(path)
        with self._lock:
            self.runs[lr.id] = lr
            self.order.append(lr.id)
        return lr

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
                        fresh.last_change = time.time()
                        self.runs[rid] = fresh
                        return fresh, False
            lr = LoadedRun(id=uuid.uuid4().hex[:8], run=run, name=name, load_report=dict(run.load_report or {}))
            lr.last_change = time.time()
            self.runs[lr.id] = lr
            self.order.append(lr.id)
            return lr, True

    def remove(self, run_id: str):
        with self._lock:
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

    def reload(self, run_id: str) -> LoadedRun:
        lr = self.get(run_id)
        if lr.run.file_path.startswith("python:"):      # T39: no file behind it
            raise LoadError("This data was sent from Python: send it again to update it.", "pushed")
        settings = dict(lr.run.import_settings or {})
        settings.pop("format", None)
        fresh = self.open_file(lr.run.file_path, settings)
        with self._lock:  # keep the id (and therefore every signal reference)
            self.runs.pop(fresh.id)
            self.order.remove(fresh.id)
            fresh.run.time_offset = lr.run.time_offset
            fresh.run.description = lr.run.description
            fresh.id, fresh.name = lr.id, lr.name
            fresh.last_change = lr.last_change
            self.runs[lr.id] = fresh
        return fresh

    def poll_appends(self) -> List[str]:
        """Live mode: read what was added to the open files. Returns the ids that changed.
          * CSV: only the appended rows are parsed;
          * ArduPilot .bin: only the appended messages are decoded;
          * MAT (rewritten as a whole by MATLAB): reloaded once the file has stopped changing for
            one poll, so a half-written file is never read.
        A file that was re-saved from scratch (not appended) is reloaded. Problems (file locked
        while another program saves it, unreadable...) are kept in self.poll_errors for the UI
        instead of failing the whole poll."""
        changed = []
        self.poll_errors = {}
        now = time.time()
        for rid in list(self.order):
            lr = self.runs.get(rid)
            if lr is None or lr.run.file_path.startswith((UPLOAD_DIR + os.sep, "python:")):
                continue                                     # a copy / data sent from Python (T39): no file to follow
            st = _stat(lr.run.file_path)
            if st is None:
                self.poll_errors[rid] = "The file is no longer there."
                continue
            if st == lr.stat:
                continue                                     # cheap path: untouched since last read
            fmt = run_format(lr.run)
            try:
                if fmt in ("mat", "ulg", "mcap", "hdf5"):      # rewritten / closed as a whole: read when settled
                    if lr.pending_stat != st:                # changed: wait one poll for it to settle
                        lr.pending_stat = st
                        continue
                    n = -1
                elif fmt == "bin":
                    n = append_new_messages(lr.run)
                elif fmt == "tlog":
                    n = append_tlog(lr.run)
                else:
                    n = append_new_rows(lr.run)
            except Exception:              # any reader problem: reload the whole file instead -
                # correct, but slow for a big file on every poll, so it must be visible
                log.warning("live: reading the appended part of %s failed; reloading the whole file",
                            lr.run.file_path, exc_info=True)
                n = -1
            if n > 0:
                lr.last_change = now
                if fmt != "csv" or lr.run.byte_offset == st[0]:
                    lr.stat = st                    # (a CSV row still being written is read next time)
                changed.append(rid)
            elif n < 0:
                try:
                    fresh = self.reload(rid)
                    fresh.last_change = now
                    changed.append(rid)
                except Exception as e:          # e.g. locked while Excel saves: try again next poll
                    self.poll_errors[rid] = str(e) or e.__class__.__name__
            elif fmt != "csv" or lr.run.byte_offset == st[0]:
                lr.stat = st                    # nothing new and nothing half-written left to read
        return changed

    def activity(self) -> Dict[str, float]:
        """Seconds since each file last received new data in live mode (absent: never)."""
        now = time.time()
        return {rid: round(now - lr.last_change, 2) for rid, lr in self.runs.items() if lr.last_change}

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
            try:
                if _stat(lr.run.file_path) == lr.stat and lr.stat is not None:
                    out["unchanged"].append(rid)
                else:
                    self.reload(rid)
                    out["reloaded"].append(rid)
            except Exception as e:
                out["errors"].append({"id": rid, "name": lr.name, "message": str(e) or e.__class__.__name__})
        return out

    def new_files(self, since: float, known: Optional[set] = None) -> List[dict]:
        """Files that appeared (or were first written) after `since` in the folders of the open
        files and look like them (same extension and name pattern: run_012.csv -> run_013.csv;
        an ArduPilot 00000042.BIN -> 00000043.BIN). Used by live mode to offer / open new runs."""
        from app.patterns import name_pattern            # local import: no cycle at start-up
        open_paths = {os.path.normcase(os.path.abspath(lr.run.file_path)) for lr in self.runs.values()}
        folders: Dict[str, set] = {}
        for lr in self.runs.values():
            p = lr.run.file_path
            if p.startswith(UPLOAD_DIR + os.sep):
                continue
            folders.setdefault(os.path.dirname(os.path.abspath(p)), set()).add(name_pattern(os.path.basename(p)))
        found: list = []
        for folder, pats in folders.items():
            try:
                with os.scandir(folder) as it:
                    for e in it:
                        try:
                            if not e.is_file():
                                continue
                            full = os.path.abspath(e.path)
                            if os.path.normcase(full) in open_paths or (known and full in known):
                                continue
                            if name_pattern(e.name) not in pats:
                                continue
                            st = e.stat()
                            created = max(st.st_mtime, getattr(st, "st_birthtime", 0) or 0)
                            # file-system clocks are coarser than time.time() (a few ms on Linux,
                            # 2 s on FAT): a file written right after `since` can carry a time
                            # slightly before it, so allow some slack
                            if created >= since - TIME_SLACK and st.st_size > 0:
                                found.append({"path": full, "name": e.name, "size": st.st_size, "mtime": st.st_mtime})
                        except OSError:
                            continue
            except OSError:
                continue
        found.sort(key=lambda f: f["mtime"])
        return found

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
            self._refresh_derived(d)
            return d.time, d.data
        lr = self.get(run_id)
        if name not in lr.run.signals:
            raise KeyError(sig_id)
        raw = lr.run.get_signal_data(name)
        spec = self.transforms.get(sig_id)
        return self._transformed(sig_id, raw, spec) if spec else raw

    def _transformed(self, sig_id: str, raw, spec: dict):
        key = (sig_id, self._raw_version(sig_id), json.dumps(spec, sort_keys=True))
        hit = self._tcache.get(key)
        if hit is not None:
            self._tcache.move_to_end(key)
            return hit
        t, y = apply_transform(raw[0], raw[1], spec)
        self._tcache[key] = (t, y)
        while len(self._tcache) > 32:
            self._tcache.popitem(last=False)
        return t, y

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
                apply_transform(raw[0][:64], raw[1][:64], spec)      # fails fast on a bad expression
            clean[sid] = spec
        previous = {sid: self.transforms.get(sid) for sid in clean}
        with self._lock:
            for sid, spec in clean.items():
                if spec:
                    self.transforms[sid] = spec
                else:
                    self.transforms.pop(sid, None)
        return previous

    def _raw_version(self, sig_id: str):
        run_id = sig_id.partition("/")[0]
        lr = self.runs.get(run_id)
        return (run_id, lr.run.uid, lr.run.data_version, lr.run.time_offset) if lr else None

    def version(self, sig_id: str):
        """Changes whenever the signal's data changes (cache key)."""
        run_id, _, name = sig_id.partition("/")
        if run_id == DERIVED_ID:
            d = self.derived.get(name)
            return ("d", name, tuple(self.version(s) for s in d.sources)) if d else None
        base = self._raw_version(sig_id)
        spec = self.transforms.get(sig_id)
        return (base, json.dumps(spec, sort_keys=True)) if (base and spec) else base

    # -------------------------------------------------------------- derived
    def _refresh_derived(self, d: DerivedDef):
        versions = tuple(self.version(s) for s in d.sources)
        if d.data is not None and versions == d.source_versions:
            return
        if any(v is None for v in versions):
            raise KeyError("A source signal of this derived signal is no longer open.")
        d.time, d.data = compute(d.op, [self.signal(s) for s in d.sources], d.params)
        d.source_versions = versions

    def short_name(self, sig_id: str) -> str:
        run_id, _, name = sig_id.partition("/")
        if run_id == DERIVED_ID:
            return name
        lr = self.runs.get(run_id)
        # add the file name only when another open file has a signal with the same name
        clash = any(rid != run_id and name in o.run.signals for rid, o in self.runs.items())
        return f"{name} ({lr.name})" if lr and clash else name

    def add_derived(self, op: str, sources: List[str], params: dict, name: Optional[str] = None) -> DerivedDef:
        for s in sources:
            self.signal(s)  # validates ids (KeyError)
        d = DerivedDef(name="", op=op, sources=list(sources), params=dict(params or {}))
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
        df = getattr(lr.run, "_flightlog", None) if lr else None
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
        """Text values, or a numeric signal with a few whole-number levels (gear, mode number...)."""
        return bool(self.labels(sig_id)) or self.is_discrete(sig_id)

    def is_discrete(self, sig_id: str) -> bool:
        key = f"{sig_id}@{self.version(sig_id)}"
        if key not in self._discrete:
            try:
                self._discrete[key] = is_discrete(self.signal(sig_id)[1])
            except (KeyError, ValueError, TypeError):    # closed, or not numbers
                self._discrete[key] = False
        return self._discrete[key]

    def describe(self, lr: LoadedRun) -> dict:
        r = lr.run
        return {
            "id": lr.id,
            "name": lr.name,
            "path": r.file_path,
            "format": run_format(r) if run_format(r) in ("mat", "bin", "tlog", "ulg", "mcap", "hdf5") else "csv",
            **({"log": self._log_summary(r)} if self._log_summary(r) else {}),
            "samples": int(r.sample_count),
            "start": float(r.start_time) + float(r.time_offset or 0),
            "end": float(r.end_time) + float(r.time_offset or 0),
            "timeOffset": float(r.time_offset or 0),
            "importSettings": {k: v for k, v in (r.import_settings or {}).items()},
            # discrete detection reads every column: for wide files it is done on demand instead
            "signals": [{"id": f"{lr.id}/{n}", "name": n, **_rate_of(sg, r),
                         "discrete": True if sg.labels else (self.is_discrete(f"{lr.id}/{n}") if len(r.signals) <= WIDE else None),
                         **({"labels": {str(k): v for k, v in sg.labels.items()}} if sg.labels else {}),
                         **({"transform": self.transforms[f"{lr.id}/{n}"]} if f"{lr.id}/{n}" in self.transforms else {})}
                        for n, sg in r.signals.items()],
            "report": lr.load_report,
            "description": r.description or "",
            # dragged into a browser window: the app works on a COPY, edits to the original are not seen
            "copy": os.path.abspath(lr.run.file_path).startswith(UPLOAD_DIR + os.sep),
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
                         "valid": ok, "samples": n})
        return {"id": DERIVED_ID, "name": "Derived", "path": "", "format": "derived", "samples": 0,
                "start": 0, "end": 0, "timeOffset": 0, "importSettings": {}, "signals": sigs, "report": {}}

    def list(self) -> List[dict]:
        out = [self.describe(self.runs[i]) for i in self.order if i in self.runs]
        d = self.describe_derived()
        return out + ([d] if d else [])


store = Store()
