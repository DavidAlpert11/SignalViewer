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
from svcore.mat_loader import MatNeedsExtra, load_mat
from svcore.can_loader import CAN_EXTS, CanError, load_can
from svcore.readers import ReaderError
from svcore.readers import read as user_read
from svcore.bin_loader import BinFormatError, append_new_messages, load_bin
from svcore.tlog_loader import TLogError, append_tlog, load_tlog
from svcore.ulog_loader import ULogError, load_ulog
from svcore.mcap_loader import McapError, load_mcap
from svcore.hdf5_loader import Hdf5Error, load_hdf5
from svcore.parquet_loader import ParquetError, load_parquet
from svcore.models import Run
from svcore import time_axis
from app import userreaders
from app.prefs import APP_DIR
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
    # the unit shown after a unit conversion ("deg" for a signal logged in rad): a label only
    unit = " ".join(str(spec.get("unit") or "").split())[:24]
    if unit:
        out["unit"] = unit
    return out or None


REF = re.compile(r"\{([^{}]+)\}")


def transform_refs(spec: Optional[dict]) -> List[str]:
    """Q89: the other signals an edit's expression reads - {Name}: of the same file; Q90:
    {@<run id>:Name}: of that one file (the interface shows it as {file:Name})."""
    out: List[str] = []
    for m in REF.finditer(str((spec or {}).get("expr") or "")):
        name = m.group(1).strip()
        if name not in out:
            out.append(name)
    return out


def ref_run(token: str) -> Optional[str]:
    """The file a reference names ({@<run id>:Name}), or None for the edited signal's own file."""
    if token.startswith("@") and ":" in token:
        return token[1:token.index(":")]
    return None


def apply_transform(t, y, spec: dict, ref=None):
    """y' = scale * f(x) + offset, t' = t + dt;  f is an expression in x (and t) and, Q89, of other
    signals of the same file written {Name}: `ref(name)` gives their (time, data) as read from the
    file (before any edit - so a group changed together sees the same values, and no edit can depend
    on another in a circle). They are interpolated onto x's time."""
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if spec.get("expr"):
        names = transform_refs(spec)
        sources = [(t, y)]
        for name in names:
            if ref is None:
                raise OpError(f"{name}: another signal can not be used here.")
            got = ref(name)
            if got is None:
                shown = name[name.index(":") + 1:] if name.startswith("@") and ":" in name else name
                raise OpError(f"{shown} is not a signal of this file." if not name.startswith("@")
                              else f"{shown}: its file is not open.")
            sources.append((np.asarray(got[0], dtype=np.float64), np.asarray(got[1], dtype=np.float64)))
        # {Name} first (a name may hold an x), then x itself
        expr = REF.sub(lambda m: f"v{names.index(m.group(1).strip()) + 1}", spec["expr"])
        expr = re.sub(r"\bx\b", "v0", expr)
        try:
            t2, y = _evaluate_formula(expr, sources, lambda tt, ts, ys: np.interp(tt, ts, ys))
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
UPLOAD_DIR = os.path.join(APP_DIR, "uploads")


# live mode, files rewritten as a whole (MAT, ULog, MCAP, HDF5, Parquet): read once unchanged for
# SETTLE_QUIET seconds, and at least every SETTLE_MAX seconds while they keep changing
SETTLE_QUIET = 0.4
SETTLE_MAX = 2.0

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


def _stat(path: str) -> Optional[Tuple[int, int]]:
    try:
        st = os.stat(path)
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


def run_format(run: Run) -> str:
    return (run.import_settings or {}).get("format") or "csv"


def _vkey(v) -> str:
    """A short text for a version tuple (F34: sent to the UI as a cache key)."""
    import hashlib
    return hashlib.sha1(repr(v).encode()).hexdigest()[:12]


class LoadError(Exception):
    """A file that cannot be opened. `code` + `params` let the UI show the reason in its own
    language (the English message stays as the fallback)."""
    def __init__(self, message: str, code: Optional[str] = None, **params):
        super().__init__(message)
        self.code = code
        self.params = params


SUPPORTED_EXTS = (".csv", ".txt", ".tsv", ".dat", ".mat", ".bin", ".tlog", ".ulg", ".mcap", ".h5", ".hdf5", ".parquet", ".pq",
                  ".asc", ".log")       # T40b: CAN logs (with a .dbc)
TEXT_EXTS = (".csv", ".txt", ".tsv", ".dat", ".asc", ".log")
_KIND_EXT = {"mat": ".mat", "ulg": ".ulg", "bin": ".bin", "hdf5": ".h5", "mcap": ".mcap", "parquet": ".parquet"}
# the extensions a signature may have: HDF5 is also MATLAB v7.3 (T27)
_KIND_OK = {"mat": (".mat",), "hdf5": (".h5", ".hdf5", ".mat"), "ulg": (".ulg",), "bin": (".bin",), "mcap": (".mcap",), "parquet": (".parquet", ".pq")}


def sniff_kind(head: bytes) -> Optional[str]:
    """What a file is by its first bytes, for the formats that have a clear signature."""
    if head.startswith(b"MATLAB"):
        return "mat"
    if head.startswith(b"\x89HDF\r\n\x1a\n"):         # HDF5: .h5 / .hdf5, or a MATLAB v7.3 .mat
        return "hdf5"
    if head.startswith(b"\x89MCAP"):                  # ROS 2 / Foxglove recording
        return "mcap"
    if head.startswith(b"PAR1"):                       # Parquet (T40)
        return "parquet"
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


def _can_csv(path: str) -> bool:
    """A .csv that is a CAN frame log (time,id,data) - opened with the .dbc, not as a table -
    only when a .dbc sits next to it."""
    d = os.path.dirname(path)
    try:
        if not any(f.lower().endswith(".dbc") for f in os.listdir(d)):
            return False
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            head = [h.strip().lower() for h in f.readline().split(",")]
    except OSError:
        return False
    return len(head) <= 6 and any(h in ("id", "can_id", "arbitration_id") for h in head) and any(h in ("data", "payload") for h in head)


def check_file(path: str, settings: Optional[dict] = None) -> None:
    """Cheap checks BEFORE a loader runs, so the user is told what is wrong in plain words:
    unsupported type, empty file, a binary file with a text extension, or a known format
    with the wrong extension. Raises LoadError."""
    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)
    own = ext not in SUPPORTED_EXTS and bool(userreaders.for_ext(ext))   # T60: a format of the user's
    if ext not in SUPPORTED_EXTS and not own:
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
    if own:                                        # the user's reader decides what its files look like
        return
    kind = sniff_kind(head)
    if kind and ext not in _KIND_OK[kind]:
        raise LoadError(f"{name} looks like a {_KIND_EXT[kind]} file, but its extension is {ext}. "
                        f"Rename it to {_KIND_EXT[kind]} and open it again.", "wrongExt", ext=ext, real=_KIND_EXT[kind])
    if ext in TEXT_EXTS:
        enc = str((settings or {}).get("encoding") or "").lower().replace("-", "").replace("_", "")
        wide = enc.startswith(("utf16", "utf32")) or head.startswith((b"\xff\xfe", b"\xfe\xff"))
        if not wide and b"\x00" in head and not _text_with_zero_block(head):
            raise LoadError("This is a binary file, not text: it cannot be read as CSV.", "binaryText")


def _text_file(path: str) -> bool:
    """A .tlog that is a TEXT table (a telemetry export with columns), not a MAVLink recording:
    read as CSV. A MAVLink .tlog starts with an 8-byte time stamp and binary packets."""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return False
    if not head or b"\x00" in head:
        return False
    try:
        text = head.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = head.decode("cp1252")
        except UnicodeDecodeError:
            return False
    printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in text) / max(1, len(text))
    return printable > 0.97 and "\n" in text and any(d in text for d in (",", ";", "\t", " "))


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
        self._discrete: Dict[str, Tuple[str, bool]] = {}     # signal id -> (version, discrete)
        # T46: every open data file has a colour and a short tag (A, B, C...) - kept by id, so a
        # reload / replace / live update keeps them; given when a file is first described
        self.marks: Dict[str, Dict[str, str]] = {}
        self._poll_lock = threading.Lock()
        self.poll_errors: Dict[str, str] = {}
        self.writing: List[str] = []              # live: rewritten-as-a-whole files still being written

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

    # ------------------------------------------------------------ conditions
    def evaluate_condition(self, text: str, exit_text: str = "", min_dur: float = 0.0, merge_gap: float = 0.0,
                           run_ids: Optional[List[str]] = None) -> Dict[str, dict]:
        """A named condition in every open file (or these): its stretches, as shown (offset, unit,
        edits applied). A file without the signals it reads says which ones are missing."""
        from svcore.analysis import align_to
        from svcore.conditions import ConditionError, evaluate_condition, names_in
        if not text.strip():
            raise LoadError("Write the condition, e.g. {Speed} > 12.")
        out: Dict[str, dict] = {}
        for rid in (run_ids or list(self.order)):
            lr = self.runs.get(rid)
            if lr is None or rid == DERIVED_ID:
                continue

            def read(name: str, rid=rid, lr=lr):
                if name in lr.run.signals:
                    return self.signal(f"{rid}/{name}")
                if name in self.derived:                       # a new signal made in Create signals
                    try:
                        return self.signal(f"{DERIVED_ID}/{name}")
                    except KeyError:
                        return None
                return None

            def labels(name: str, lr=lr):
                sg = lr.run.signals.get(name)
                return {str(k): v for k, v in (sg.labels or {}).items()} if sg is not None else None
            try:
                out[rid] = evaluate_condition(text, read, labels, lambda t, ts, ys: align_to(t, ts, ys, "nearest"),
                                              exit_text, min_dur, merge_gap)
            except ConditionError as e:
                out[rid] = {"error": str(e)}
            except KeyError as e:
                out[rid] = {"error": str(e).strip("'\"")}
        if not out and names_in(text):
            raise LoadError("No open file to look in.")
        return out

    # ------------------------------------------------------------ occurrences
    def occurrence_rows(self, runs: Dict[str, List[List[float]]], names: List[str]) -> List[dict]:
        """The occurrences table: one row per stretch (file, start, end) with max / min / mean of
        each named signal in it."""
        from svcore.occurrences import occurrence_stats
        rows: List[dict] = []
        for rid, iv in runs.items():
            lr = self.runs.get(rid)
            if lr is None:
                continue
            per = {}
            for n in names:
                if n in lr.run.signals:
                    t, y = self.signal(f"{rid}/{n}")
                    per[n] = occurrence_stats(t, y, iv)
            for k, (a, b) in enumerate(iv):
                rows.append({"rid": rid, "a": a, "b": b, "values": {n: v[k] for n, v in per.items()}})
        rows.sort(key=lambda r: (r["a"], r["rid"]))
        return rows

    def occurrence_windows(self, items: List[dict], align: str, pad: float) -> List[dict]:
        """The occurrences overlay: each item {sig, intervals} -> its stretches on one axis."""
        from svcore.occurrences import windows
        out = []
        for it in items:
            t, y = self.signal(str(it["sig"]))
            out.append({"sig": it["sig"], **windows(t, y, it.get("intervals") or [], align, pad)})
        return out

    def occurrence_differ(self, runs: Dict[str, List[List[float]]], top: int = 25) -> List[dict]:
        """What differs in the occurrences: every numeric signal of the files with stretches, ranked
        by how far its mean inside them is from outside, in units of its usual spread outside.
        Signals of the same name in several files are averaged (weighted by their time inside)."""
        from svcore.occurrences import differ_one
        acc: Dict[str, dict] = {}
        for rid, iv in runs.items():
            lr = self.runs.get(rid)
            if lr is None or not iv:
                continue
            for name, sg in lr.run.signals.items():
                if sg.labels:
                    continue
                try:
                    t, y = self.signal(f"{rid}/{name}")
                except (KeyError, ValueError):
                    continue
                r = differ_one(t, y, iv)
                if r is None or not np.isfinite(r[0]):
                    continue
                eff, mi, mo, share = r
                a = acc.setdefault(name, {"name": name, "w": 0.0, "eff": 0.0, "in": 0.0, "out": 0.0, "files": []})
                w = max(share, 1e-9)
                a["w"] += w; a["eff"] += eff * w; a["in"] += mi * w; a["out"] += mo * w
                a["files"].append(rid)
        items = [{"name": a["name"], "effect": a["eff"] / a["w"], "meanIn": a["in"] / a["w"], "meanOut": a["out"] / a["w"],
                  "up": a["in"] >= a["out"], "files": a["files"]} for a in acc.values()]
        items.sort(key=lambda x: -x["effect"])
        return items[:top]

    # ------------------------------------------------------------ what changed first / lag
    def first_changes(self, sig_ids: List[str], run_ids: List[str], a: float, b: float,
                      base: Optional[Tuple[float, float]] = None, k: float = 4.0, persist: int = 3) -> List[dict]:
        """Investigation step 4: for these signals (and every numeric signal of these files), when
        each first left its usual range around the event [a, b] - candidates in time order."""
        from svcore.firstchange import default_baseline, first_change
        base = base or default_baseline(a, b)
        ids = list(dict.fromkeys(sig_ids + [f"{rid}/{n}" for rid in run_ids if rid in self.runs for n in self.runs[rid].run.signals]))
        out: List[dict] = []
        for sid in ids:
            rid, _, name = sid.partition("/")
            lr = self.runs.get(rid)
            sg = lr.run.signals.get(name) if lr else None
            try:
                t, y = self.signal(sid)
            except (KeyError, ValueError):
                continue
            discrete = bool(sg is not None and (sg.labels or self.is_discrete(sid)))
            r = first_change(t, y, a, b, base, k, persist, discrete)
            out.append({"id": sid, "name": name, **r})
        changed = sorted([x for x in out if x["status"] == "changed"], key=lambda x: x["t"])
        return changed + [x for x in out if x["status"] != "changed"]

    def lag_between(self, a_id: str, b_id: str, t0: float, t1: float) -> dict:
        from svcore.firstchange import lag
        ta, ya = self.signal(a_id)
        tb, yb = self.signal(b_id)
        return lag(ta, ya, tb, yb, t0, t1)

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

    def poll_appends(self) -> List[str]:
        """Live mode: read what was added to the open files. Returns the ids that changed.
          * CSV: only the appended rows are parsed;
          * ArduPilot .bin: only the appended messages are decoded;
          * MAT (rewritten as a whole by MATLAB): reloaded once the file has stopped changing for
            one poll, so a half-written file is never read.
        A file that was re-saved from scratch (not appended) is reloaded. Problems (file locked
        while another program saves it, unreadable...) are kept in self.poll_errors for the UI
        instead of failing the whole poll."""
        # one poll at a time: a slow poll (a big file read again) must not be overtaken by the next
        if not self._poll_lock.acquire(blocking=False):
            return []
        try:
            return self._poll_appends()
        finally:
            self._poll_lock.release()

    def _poll_appends(self) -> List[str]:
        changed = []
        self.poll_errors = {}
        self.writing = []
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
                if fmt in ("mat", "ulg", "mcap", "hdf5", "parquet"):   # rewritten / closed as a whole
                    # Read it once it has been quiet for a moment - or, if it never stops changing
                    # (saved every second by a running program), every SETTLE_MAX seconds anyway: it
                    # used to wait for two equal polls, so a file saved often was never shown until
                    # the writing stopped. A read of a half-written file fails and is tried again.
                    if lr.pending_stat != st:
                        lr.pending_stat = st
                        lr.pending_since = lr.pending_since or now
                        lr.last_change = now                 # being written: live mode is not idle
                    quiet = now - st[1] / 1e9 >= SETTLE_QUIET
                    overdue = now - lr.pending_since >= SETTLE_MAX
                    if not (quiet or overdue):
                        self.writing.append(rid)
                        continue
                    try:
                        fresh = self.reload(rid)
                    except Exception as e:
                        if quiet:                            # settled but unreadable: say so
                            self.poll_errors[rid] = str(e) or e.__class__.__name__
                        else:                                # caught mid-write: next poll
                            self.writing.append(rid)
                        continue
                    fresh.last_change = now
                    fresh.pending_since = 0.0
                    changed.append(rid)
                    continue
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
            return self._refresh_derived(d)
        lr = self.get(run_id)
        if name not in lr.run.signals:
            raise KeyError(sig_id)
        raw = lr.run.get_signal_data(name)
        spec = self.transforms.get(sig_id)
        return self._transformed(sig_id, raw, spec) if spec and set(spec) - {"unit"} else raw   # (a unit alone: same values)

    def _transformed(self, sig_id: str, raw, spec: dict):
        key = (sig_id, self._raw_version(sig_id), self._ref_versions(sig_id, spec), json.dumps(spec, sort_keys=True))
        hit = self._tcache.get(key)
        if hit is not None:
            self._tcache.move_to_end(key)
            return hit
        t, y = apply_transform(raw[0], raw[1], spec, self._ref_reader(sig_id))
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
        spec = self.transforms.get(sig_id)
        return (base, self._ref_versions(sig_id, spec), json.dumps(spec, sort_keys=True)) if (base and spec) else base

    # -------------------------------------------------------------- derived
    def _refresh_derived(self, d: DerivedDef) -> Tuple[np.ndarray, np.ndarray]:
        """The derived signal's (time, data), computed again when a source changed."""
        versions = tuple(self.version(s) for s in d.sources)
        if d.time is not None and d.data is not None and versions == d.source_versions:
            return d.time, d.data
        if any(v is None for v in versions):
            raise KeyError("A source signal of this derived signal is no longer open.")
        t, y = compute(d.op, [self.signal(s) for s in d.sources], d.params)
        d.time, d.data, d.source_versions = t, y, versions
        return t, y

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
        """Text values, or a numeric signal with a few whole-number levels (gear, mode number...)."""
        return bool(self.labels(sig_id)) or self.is_discrete(sig_id)

    def is_discrete(self, sig_id: str) -> bool:
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
                         "valid": ok, "samples": n, "version": _vkey(self.version(f"{DERIVED_ID}/{name}"))})
        return {"id": DERIVED_ID, "name": "Derived", "path": "", "format": "derived", "samples": 0,
                "start": 0, "end": 0, "timeOffset": 0, "importSettings": {}, "signals": sigs, "report": {}}

    def list(self) -> List[dict]:
        out = [self.describe(self.runs[i]) for i in self.order if i in self.runs]
        d = self.describe_derived()
        return out + ([d] if d else [])


store = Store()
