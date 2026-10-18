"""
Signal Viewer - Flexible CSV Loader (large-file aware)
==========================================================
Handles various CSV formats: headers, delimiters, time columns.

Large-file support
------------------
* Fast path: multi-threaded Apache Arrow parser (if ``pyarrow`` is installed).
* Fallback: pandas C parser in chunks, converting each chunk to numeric arrays
  immediately, so the whole file never lives in memory as Python objects.
* Optional float32 storage for signals (``SV_FLOAT32=1``) - halves RAM.
  The time vector is always float64 to keep timestamp precision.
* Binary cache: big files are converted once to ``.npy`` files and later opened
  with memory-mapping (near-instant re-open, RAM is used only for what is read).
  Cache is keyed on path + size + mtime + import settings, so it never goes stale.
* Incremental append (``append_new_rows``): reads only the bytes added to the file
  since the last load - used by Smart Refresh and Streaming.

Environment variables
---------------------
SV_FLOAT32=1           store signals as float32
SV_CACHE=0             disable the binary cache
SV_CACHE_DIR=<path>    cache location (default: ~/.signalviewer_cache)
SV_CACHE_MIN_MB=<n>    only cache files larger than n MB (default 50)
"""

import logging
import hashlib
import csv
import io
import json
import os
import shutil
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from svcore.models import Run, Signal
from svcore.naming import get_csv_display_name

try:  # optional fast parser
    import pyarrow as pa
    import pyarrow.csv as pa_csv
    HAS_PYARROW = True
except Exception:  # pragma: no cover - depends on environment
    HAS_PYARROW = False


# =============================================================================
# PROGRESS / CANCEL (used by background jobs; no-op otherwise)
# =============================================================================

import threading as _threading

log = logging.getLogger("signalviewer").getChild(__name__)

_ctx = _threading.local()


class LoadCancelled(Exception):
    pass


def set_progress_context(report=None, cancelled=None):
    """report(fraction 0..1, phase str); cancelled() -> bool. Per thread."""
    _ctx.report, _ctx.cancelled = report, cancelled


def _progress(frac: float, phase: str = "read"):
    rep = getattr(_ctx, "report", None)
    if rep:
        rep(max(0.0, min(1.0, frac)), phase)
    can = getattr(_ctx, "cancelled", None)
    if can and can():
        raise LoadCancelled()


# =============================================================================
# CONFIG
# =============================================================================

SIGNAL_DTYPE = np.float32 if os.environ.get("SV_FLOAT32", "0") == "1" else np.float64
CACHE_ENABLED = os.environ.get("SV_CACHE", "1") != "0"
CACHE_DIR = os.environ.get("SV_CACHE_DIR", os.path.join(os.path.expanduser("~"), ".signalviewer", "cache"))
CACHE_MIN_BYTES = int(float(os.environ.get("SV_CACHE_MIN_MB", "50")) * 1024 * 1024)
CACHE_FORMAT_VERSION = 4   # v3: one column-major matrix file instead of one file per signal; v4: text columns
MAX_TEXT_STATES = int(os.environ.get("SV_MAX_TEXT_STATES", "1000"))   # more distinct texts: not a state column
CHUNK_ROWS = 500_000
DEFAULT_ENCODING = "utf-8-sig"  # strips the BOM Excel writes (otherwise "Time" -> "\ufeffTime")
TIME_NAMES = ("time", "t", "timestamp", "datetime", "time_s", "time[s]", "time (s)")


@dataclass
class CSVImportSettings:
    """Settings for CSV import"""
    has_header: bool = True
    header_row: int = 0  # 0-based row index for header (relative to after skip_rows)
    skip_rows: int = 0  # Rows to skip at start (before header)
    delimiter: Optional[str] = None  # None = auto-detect
    time_column: str = "Time"  # Name or index
    encoding: str = DEFAULT_ENCODING

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[Dict]) -> "CSVImportSettings":
        d = d or {}
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        s = cls(**known)
        if str(s.encoding).lower().replace("-", "") == "utf8":
            s.encoding = DEFAULT_ENCODING
        return s


# =============================================================================
# HELPERS
# =============================================================================

def _read_head_lines(filepath: str, n: int, encoding: str = DEFAULT_ENCODING, skip: int = 0) -> List[str]:
    lines = []
    with open(filepath, "r", encoding=encoding, errors="replace", newline="") as f:
        for i, line in enumerate(f):
            if i < skip:
                continue
            lines.append(line.rstrip("\r\n"))
            if len(lines) >= n:
                break
    return lines


def detect_delimiter(filepath: str, num_lines: int = 10, skip_rows: int = 0) -> str:
    """
    Auto-detect CSV delimiter. Whitespace is only chosen if no other delimiter appears,
    because header names frequently contain spaces ("Motor Speed").
    """
    try:
        lines = [l for l in _read_head_lines(filepath, num_lines, skip=skip_rows) if l.strip()]
        if not lines:
            return ","
        scores = {}
        for delim in [",", ";", "\t", "|"]:
            counts = [line.count(delim) for line in lines]
            if min(counts) > 0:
                # consistent counts across lines are a strong signal
                scores[delim] = min(counts) + (1000 if len(set(counts)) == 1 else 0)
        if scores:
            return max(scores, key=lambda d: scores[d])
        if all(" " in l.strip() for l in lines):
            return r"\s+"
        return ","
    except (OSError, UnicodeError, ValueError):     # unreadable head: the usual delimiter
        return ","


def _unique_names(names: List[str]) -> List[str]:
    """Make column names unique and non-empty."""
    seen: Dict[str, int] = {}
    out: list = []
    for i, n in enumerate(names):
        n = "" if n is None or (isinstance(n, float) and np.isnan(n)) else str(n).strip()
        n = n or f"Col{i}"
        if n in seen:
            seen[n] += 1
            n = f"{n}_{seen[n]}"
        else:
            seen[n] = 0
        out.append(n)
    return out


def _resolve_time_column(columns: List[str], wanted: Optional[str]) -> int:
    """Return the index of the time column (name, numeric index, or auto-detect)."""
    return _resolve_time_column_how(columns, wanted)[0]


def _resolve_time_column_how(columns: List[str], wanted: Optional[str]) -> Tuple[int, bool]:
    """(index, found_by_name): False when it fell back to the first column."""
    if wanted is not None and str(wanted) in columns:
        return columns.index(str(wanted)), True
    if wanted is not None and str(wanted).strip().isdigit():
        idx = int(str(wanted).strip())
        if 0 <= idx < len(columns):
            return idx, True
    lower = [c.lower().strip() for c in columns]
    for name in TIME_NAMES:
        if name in lower:
            return lower.index(name), True
    return 0, False


def _to_numeric_array(values, dtype) -> np.ndarray:
    """Convert a column (pandas Series / array-like) to a numeric numpy array (NaN for junk)."""
    if not isinstance(values, pd.Series):
        values = pd.Series(np.asarray(values))
    kind = values.dtype.kind
    if kind in "fiu":
        return values.to_numpy(dtype=dtype, na_value=np.nan)
    if kind == "b":
        return values.to_numpy().astype(dtype)
    return pd.to_numeric(values, errors="coerce").to_numpy(dtype=dtype, na_value=np.nan)


def encode_text(values, labels: Optional[Dict[int, str]] = None) -> Tuple[np.ndarray, Dict[int, str]]:
    """Text values -> float codes (empty -> NaN). Codes follow the order of first appearance and
    continue an existing {code: text} map (live mode adds the new texts at the end)."""
    s = pd.Series(np.asarray(values, dtype=object))
    s = s.map(lambda v: v.strip() if isinstance(v, str) else v)
    s = s.where(s.map(lambda v: isinstance(v, str) and v != ""), None)
    codes, uniques = pd.factorize(s, sort=False, use_na_sentinel=True)
    labels = dict(labels or {})
    rev = {v: k for k, v in labels.items()}
    nxt = (max(labels) + 1) if labels else 0
    remap = np.empty(len(uniques) + 1, dtype=np.float64)
    remap[-1] = np.nan                       # sentinel -1 -> NaN
    for i, u in enumerate(uniques):
        u = str(u)
        if u not in rev:
            rev[u], labels[nxt] = nxt, u
            nxt += 1
        remap[i] = rev[u]
    return remap[codes], labels


def _read_text_columns(filepath, columns, names, skip_lines, delimiter, encoding, arrow: bool):
    """Second, narrow pass over the file for the columns that turned out to hold text: returns
    (row count, {name: object array}). Uses the same parser as the numeric pass, so the rows match."""
    if arrow and HAS_PYARROW and len(delimiter) == 1:
        enc = "utf8" if str(encoding).lower().replace("-", "").startswith("utf8") else encoding
        with open(filepath, "rb") as fh:
            data = fh.read()
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]
        table = pa_csv.read_csv(
            pa.BufferReader(data),
            read_options=pa_csv.ReadOptions(column_names=columns, skip_rows=skip_lines, encoding=enc, use_threads=True),
            parse_options=pa_csv.ParseOptions(delimiter=delimiter, invalid_row_handler=lambda row: "skip"),
            convert_options=pa_csv.ConvertOptions(include_columns=list(names),
                                                  column_types={n: pa.string() for n in names},
                                                  strings_can_be_null=True))
        return table.num_rows, {n: table.column(n).to_numpy(zero_copy_only=False) for n in names}
    engine = "python" if delimiter == r"\s+" else "c"
    df = pd.read_csv(filepath, sep=delimiter, header=None, names=columns, skiprows=skip_lines, usecols=list(names),
                     encoding=encoding, on_bad_lines="skip", engine=engine, index_col=False, dtype=str,
                     keep_default_na=False)
    return len(df), {n: df[n].to_numpy(dtype=object) for n in names}


def _split_line(line: str, delimiter: str) -> List[str]:
    """One header line -> its fields. The csv module is what pandas' Python engine uses for a
    one-character delimiter (same quoting rules), without building a DataFrame: 0.3 ms instead of
    ~190 ms for 5000 columns."""
    line = line.rstrip("\r\n")
    if delimiter == r"\s+":
        return line.split()
    if len(delimiter) == 1:
        return next(csv.reader([line], delimiter=delimiter), [])
    return pd.read_csv(io.StringIO(line), sep=delimiter, header=None, engine="python",
                       dtype=str, keep_default_na=False).iloc[0].tolist()


def _header_info(filepath: str, settings: CSVImportSettings, delimiter: str) -> Tuple[List[str], int]:
    """Returns (column names, number of physical lines to skip before the data)."""
    skip = int(settings.skip_rows or 0)
    if settings.has_header:
        hdr_line_idx = skip + int(settings.header_row or 0)
        lines = _read_head_lines(filepath, 1, settings.encoding, skip=hdr_line_idx)
        if not lines:
            return [], hdr_line_idx + 1
        return _unique_names(_split_line(lines[0], delimiter)), hdr_line_idx + 1
    lines = _read_head_lines(filepath, 1, settings.encoding, skip=skip)
    if not lines:
        return [], skip
    return [f"Col{i}" for i in range(len(_split_line(lines[0], delimiter)))], skip


# =============================================================================
# PARSERS
# =============================================================================

PART_BYTES = 64 * 1024 * 1024


def _parse_pyarrow(filepath, columns, skip_lines, delimiter, encoding, stats: Optional[Dict] = None) -> Dict[str, np.ndarray]:
    """
    Arrow's multi-threaded parser, run on ~64 MB parts of the file cut at line breaks.
    Between parts we report progress and honour cancel, without losing Arrow's speed
    (its streaming reader is single-threaded and ~15x slower). Raises on anything
    unusual; load_csv then falls back to the pandas parser.
    """
    if len(delimiter) != 1:
        raise ValueError("needs a single-character delimiter")
    enc = "utf8" if str(encoding).lower().replace("-", "").startswith("utf8") else encoding
    parse_opts = pa_csv.ParseOptions(delimiter=delimiter, invalid_row_handler=lambda row: "skip")
    total = max(1, os.path.getsize(filepath))
    parts: Dict[str, List[np.ndarray]] = {c: [] for c in columns}
    float_types = {c: pa.float64() for c in columns}
    first = True
    carry = b""
    with open(filepath, "rb") as fh:
        while True:
            block = fh.read(PART_BYTES)
            if not block and not carry:
                break
            data = carry + block
            if block:
                cut = data.rfind(b"\n")
                if cut < 0:               # one enormous line: keep reading
                    carry = data
                    continue
                data, carry = data[: cut + 1], data[cut + 1:]
            else:
                carry = b""
            if first and data.startswith(b"\xef\xbb\xbf"):
                data = data[3:]
            read_opts = pa_csv.ReadOptions(column_names=columns, skip_rows=skip_lines if first else 0,
                                           encoding=enc, use_threads=True, block_size=1 << 24)
            first = False
            if not data or data.isspace():      # (not data.strip(): that copies the whole 64 MB part)
                continue
            try:
                table = _arrow_part(data, read_opts, parse_opts, float_types)
            except pa.ArrowInvalid:
                # a damaged part (power loss, bad copy): bytes that are not valid text make Arrow fail
                # even in its bad-row handler. Repair ONLY this part and read it again; healthy parts
                # never pay for the repair (T33).
                fixed = _repair_text_bytes(data, enc)
                if fixed == data:
                    raise
                table = _arrow_part(fixed, read_opts, parse_opts, float_types)
                if stats is not None:
                    stats["damagedText"] = True
            for ci, name in enumerate(columns):
                col = table.column(ci)          # by index: lookup by name is O(columns) each
                t = col.type
                if pa.types.is_integer(t) or pa.types.is_floating(t) or pa.types.is_boolean(t):
                    parts[name].append(col.cast(pa.float64()).to_numpy(zero_copy_only=False))
                elif pa.types.is_null(t):
                    parts[name].append(np.full(len(col), np.nan))
                else:   # text in this part (header remnants, junk values) -> coerce
                    parts[name].append(_to_numeric_array(col.to_pandas(), np.float64))
            del table
            _progress(fh.tell() / total, "read")
    return {c: (np.concatenate(v) if v else np.array([], dtype=np.float64)) for c, v in parts.items()}


def _arrow_part(data: bytes, read_opts, parse_opts, float_types):
    """One part with Arrow. Fast path: every column float64 (no type inference, no casts);
    a part with text in it (header remnants, junk) is re-read with inference."""
    try:
        return pa_csv.read_csv(pa.BufferReader(data), read_options=read_opts, parse_options=parse_opts,
                               convert_options=pa_csv.ConvertOptions(column_types=float_types,
                                                                     strings_can_be_null=True))
    except pa.ArrowInvalid:
        return pa_csv.read_csv(pa.BufferReader(data), read_options=read_opts, parse_options=parse_opts)


def _repair_text_bytes(data: bytes, encoding: str) -> bytes:
    """Damaged text -> readable text: NUL bytes (what a file cut by a power loss is padded with)
    are dropped and bytes that are not valid in the encoding become U+FFFD. The damaged row is
    then skipped or its value becomes NaN, like any other bad row, instead of failing the file."""
    data = data.replace(b"\x00", b"")
    if str(encoding).lower().replace("-", "").replace("_", "") in ("utf8", "utf8sig"):
        return data.decode("utf-8", errors="replace").encode("utf-8")
    return data


def _parse_pandas_chunked(filepath, columns, skip_lines, delimiter, encoding) -> Dict[str, np.ndarray]:
    """Chunked pandas parse: memory stays bounded by one chunk of Python objects."""
    parts: Dict[str, List[np.ndarray]] = {c: [] for c in columns}
    engine = "python" if delimiter == r"\s+" else "c"
    kwargs = dict(sep=delimiter, header=None, names=columns, skiprows=skip_lines,
                  encoding=encoding, encoding_errors="replace", on_bad_lines="skip", chunksize=CHUNK_ROWS,
                  engine=engine, index_col=False)
    total = max(1, os.path.getsize(filepath))
    with open(filepath, "rb") as fh:
        for chunk in pd.read_csv(fh, **kwargs):
            for c in columns:
                parts[c].append(_to_numeric_array(chunk[c], np.float64))
            _progress(fh.tell() / total, "read")
    return {c: (np.concatenate(v) if v else np.array([], dtype=np.float64)) for c, v in parts.items()}


# =============================================================================
# CACHE
# =============================================================================

def _cache_key(filepath: str, size: int, mtime: float, settings: CSVImportSettings) -> str:
    raw = json.dumps([CACHE_FORMAT_VERSION, os.path.abspath(filepath), size, mtime,
                      settings.to_dict(), np.dtype(SIGNAL_DTYPE).str], sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()


def _cache_load(key: str) -> Optional[Dict]:
    d = os.path.join(CACHE_DIR, key)
    meta_path = os.path.join(d, "meta.json")
    if not os.path.isfile(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        meta["time"] = np.load(os.path.join(d, "time.npy"), mmap_mode="r")
        names = meta["signals"]
        if names:
            # column-major: every signal is one contiguous column (fast, no copies)
            mat = np.load(os.path.join(d, "signals.npy"), mmap_mode="r")
            meta["signal_arrays"] = {name: mat[:, i] for i, name in enumerate(names)}
        else:
            meta["signal_arrays"] = {}
        return meta
    except Exception as e:
        print(f"[CACHE] Corrupt cache entry {key}, ignoring: {e}", flush=True)
        shutil.rmtree(d, ignore_errors=True)
        return None


def _cache_store(key: str, meta: Dict, time: np.ndarray, sigs: Dict[str, np.ndarray]) -> bool:
    """Time vector + ONE matrix (samples x signals, Fortran order) per file. Thousands of
    columns used to mean thousands of files, slow to reopen and hard on file limits."""
    d = os.path.join(CACHE_DIR, key)
    tmp = d + ".tmp"
    try:
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp, exist_ok=True)
        np.save(os.path.join(tmp, "time.npy"), time)
        names = list(sigs.keys())
        if names:
            dtype = np.dtype(np.result_type(*[sigs[n].dtype for n in names]))
            # Fortran order = the columns one after another: write them sequentially
            # (several times faster than filling a fresh memory map).
            with open(os.path.join(tmp, "signals.npy"), "wb") as fh:
                np.lib.format.write_array_header_2_0(
                    fh, {"descr": np.lib.format.dtype_to_descr(dtype), "fortran_order": True,
                         "shape": (len(time), len(names))})
                for n in names:
                    fh.write(memoryview(np.ascontiguousarray(sigs[n], dtype=dtype)))   # no copy
        with open(os.path.join(tmp, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(dict(meta, signals=names), f)
        shutil.rmtree(d, ignore_errors=True)
        os.replace(tmp, d)
        return True
    except Exception as e:
        print(f"[CACHE] Could not write cache: {e}", flush=True)
        shutil.rmtree(tmp, ignore_errors=True)
        return False


def clear_cache():
    shutil.rmtree(CACHE_DIR, ignore_errors=True)


# =============================================================================
# PUBLIC API
# =============================================================================

def preview_csv(
    filepath: str,
    settings: Optional[CSVImportSettings] = None,
    max_rows: int = 20,
) -> Tuple[List[List[str]], List[str]]:
    """Preview CSV file without full loading (reads only the first lines)."""
    settings = settings or CSVImportSettings()
    delimiter = settings.delimiter or detect_delimiter(filepath, skip_rows=settings.skip_rows or 0)
    try:
        lines = [l for l in _read_head_lines(filepath, max_rows, settings.encoding,
                                             skip=settings.skip_rows or 0) if l.strip()]
        if not lines:
            return [], []
        rows = [_split_line(l, delimiter) for l in lines]
        if settings.has_header:
            h = int(settings.header_row or 0)
            if 0 <= h < len(rows):
                return rows[h + 1:], _unique_names(rows[h])
        return rows, [f"Col{i}" for i in range(len(rows[0]))]
    except Exception as e:
        print(f"[ERROR] Preview failed: {e}")
        return [], []


def load_csv(
    filepath: str,
    all_paths: List[str],
    settings: Optional[CSVImportSettings] = None,
) -> Optional[Run]:
    """
    Load CSV file into a Run object.

    Returns:
        Run object or None if failed
    """
    if not os.path.isfile(filepath):
        print(f"[ERROR] File not found: {filepath}")
        return None

    if isinstance(settings, dict):
        settings = CSVImportSettings.from_dict(settings)
    settings = settings or CSVImportSettings()

    try:
        st = os.stat(filepath)
        file_size, file_mtime = st.st_size, st.st_mtime  # read BEFORE parsing (append safety)
        delimiter = settings.delimiter or detect_delimiter(filepath, skip_rows=settings.skip_rows or 0)
        columns, skip_lines = _header_info(filepath, settings, delimiter)
        if not columns:
            print(f"[ERROR] Empty CSV: {filepath}")
            return None

        time_idx, time_by_name = _resolve_time_column_how(columns, settings.time_column)

        # Rename time column to "Time" (rename a colliding non-time "Time" column first)
        source_columns = list(columns)
        if source_columns[time_idx] != "Time" and "Time" in source_columns:
            source_columns[source_columns.index("Time")] = "Time_2"
        source_columns[time_idx] = "Time"
        source_columns = _unique_names(source_columns)

        use_cache = CACHE_ENABLED and file_size >= CACHE_MIN_BYTES
        key = _cache_key(filepath, file_size, file_mtime, settings) if use_cache else None
        cached = _cache_load(key) if key is not None else None

        if cached is not None:
            time_array = cached["time"]
            signal_arrays = cached["signal_arrays"]
            text_labels = {n: {int(k): v for k, v in l.items()} for n, l in (cached.get("labels") or {}).items()}
            print(f"[CACHE] Opened memory-mapped cache for {os.path.basename(filepath)}", flush=True)
        else:
            arrays = None
            used_arrow = False
            parse_stats: Dict = {}
            if HAS_PYARROW:
                try:
                    arrays = _parse_pyarrow(filepath, source_columns, skip_lines, delimiter, settings.encoding,
                                            parse_stats)
                    used_arrow = True
                except LoadCancelled:
                    raise
                except Exception as e:
                    print(f"[LOAD] Arrow parser not usable for this file ({e}); using pandas", flush=True)
            if arrays is None:
                arrays = _parse_pandas_chunked(filepath, source_columns, skip_lines, delimiter, settings.encoding)

            time_array = np.asarray(arrays.pop("Time"), dtype=np.float64)
            # columns where no value is a number: text (states such as "IDLE" / "ARMED")
            text_cols = [n for n, a in arrays.items() if a.size and np.isnan(a).all()]
            text_labels = {}
            text_skipped: List[str] = []
            if text_cols:
                try:
                    nrows, texts = _read_text_columns(filepath, source_columns, text_cols, skip_lines, delimiter,
                                                      settings.encoding, used_arrow)
                    if nrows != len(time_array):
                        raise ValueError("row count differs between passes")
                    for n in text_cols:
                        codes, labels = encode_text(texts[n])
                        if 0 < len(labels) <= MAX_TEXT_STATES:
                            arrays[n], text_labels[n] = codes, labels
                        elif labels:
                            text_skipped.append(n)
                except LoadCancelled:
                    raise
                except Exception as e:
                    print(f"[LOAD] Text columns not read ({e})", flush=True)
            valid = np.isfinite(time_array)
            need_filter = not valid.all()
            load_report: dict = {"droppedRows": int((~valid).sum()), "sorted": False, "skippedColumns": [],
                           "textColumns": sorted(text_labels)}
            if text_skipped:
                load_report["tooManyTexts"] = text_skipped
            if parse_stats.get("damagedText"):
                load_report["damagedText"] = True
            if need_filter:
                time_array = time_array[valid]

            # Time must be sorted for interpolation / searchsorted / cursor
            order = None
            if len(time_array) > 1 and np.any(np.diff(time_array) < 0):
                print("[LOAD] Time column is not monotonic - sorting rows", flush=True)
                order = np.argsort(time_array, kind="stable")
                load_report["sorted"] = True
                time_array = time_array[order]

            signal_arrays = {}
            for name in list(arrays.keys()):
                a = arrays.pop(name)
                if need_filter:
                    a = a[valid]
                if order is not None:
                    a = a[order]
                if a.size == 0 or np.isnan(a).all():
                    load_report["skippedColumns"].append(name)
                    continue  # text column - skip instead of creating an all-NaN signal
                signal_arrays[name] = a.astype(SIGNAL_DTYPE, copy=False)

            if key is not None and len(time_array):
                _progress(1.0, "cache")
                if _cache_store(key, {"delimiter": delimiter, "labels": {n: {str(k): v for k, v in l.items()}
                                                                          for n, l in text_labels.items()}},
                                time_array, signal_arrays):
                    reopened = _cache_load(key)  # switch to mmap -> frees the RAM copy
                    if reopened is not None:
                        time_array, signal_arrays = reopened["time"], reopened["signal_arrays"]

        if len(time_array) == 0:
            print(f"[ERROR] No valid time data: {filepath}")
            return None

        run = Run(
            file_path=filepath,
            csv_display_name=get_csv_display_name(filepath, all_paths),
            time=time_array,
        )
        for name, data in signal_arrays.items():
            run.signals[name] = Signal(name=name, data=data, labels=text_labels.get(name))

        run.import_settings = settings.to_dict()
        run.load_report = load_report if cached is None else {"fromCache": True}
        run.load_report["timeByName"] = bool(time_by_name)
        run.delimiter = delimiter
        run.encoding = settings.encoding
        run.source_columns = source_columns
        run.byte_offset = file_size
        remember_tail(run)
        run.compute_metadata()

        print(f"[OK] Loaded {run.csv_display_name}: {run.sample_count:,} samples, "
              f"{len(run.signals)} signals ({_fmt_bytes(_run_nbytes(run))})")
        return run

    except LoadCancelled:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to load {filepath}: {e}")
        import traceback
        traceback.print_exc()
        return None


TAIL = 256      # bytes before the read position used to tell "appended" from "re-saved"


def _read_tail(path: str, offset: int) -> bytes:
    with open(path, "rb") as f:
        f.seek(max(0, offset - TAIL))
        return f.read(min(TAIL, offset))


def remember_tail(run: Run) -> None:
    """Fingerprint of the bytes already read + the file's state, after a load or an append."""
    try:
        run.tail_sig = _read_tail(run.file_path, run.byte_offset)
        st = os.stat(run.file_path)
        run.seen_size, run.seen_mtime = st.st_size, st.st_mtime
    except OSError:
        pass


def append_new_rows(run: Run, max_bytes: int = 256 * 1024 * 1024) -> int:
    """
    Read only rows appended to the file since the last load / append.

    Returns:
        number of rows appended (0 = nothing new),
        -1 if the file shrank / was rewritten / has out-of-order time (caller should full-reload).
    """
    path = run.file_path
    if not os.path.isfile(path):
        return 0
    st = os.stat(path)
    size, mtime = st.st_size, st.st_mtime
    if size < run.byte_offset or not run.source_columns:
        return -1
    prev_size, prev_mtime = getattr(run, "seen_size", None), getattr(run, "seen_mtime", None)
    if size == prev_size and mtime == prev_mtime and size == run.byte_offset:
        return 0                                      # untouched
    # Re-saved (e.g. by Excel)? The bytes we already read must still be there. A size-only
    # check missed saves that keep the size, and read a larger re-save as "appended rows".
    tail = getattr(run, "tail_sig", None)
    if tail is not None and _read_tail(path, run.byte_offset) != tail:
        return -1
    if size == run.byte_offset:
        run.seen_size, run.seen_mtime = size, mtime   # touched but not changed
        return 0

    with open(path, "rb") as f:
        f.seek(run.byte_offset)
        raw = f.read(min(size - run.byte_offset, max_bytes))
    last_nl = raw.rfind(b"\n")
    stable = size == prev_size and mtime == prev_mtime
    if last_nl < 0 or (last_nl < len(raw) - 1 and stable and raw[last_nl + 1:].strip()):
        if not stable:
            run.seen_size, run.seen_mtime = size, mtime   # a writer may be mid-line: look again next time
            return 0
        raw = raw + b"\n"            # unchanged for a whole poll: the last row has no newline (typed by hand)
        complete_to = size
    else:
        raw = raw[: last_nl + 1]
        complete_to = None

    enc = "utf-8" if str(run.encoding).lower().startswith("utf") else run.encoding
    text = raw.decode(enc, errors="replace")
    if not text.strip():
        run.byte_offset += len(raw)
        return 0

    cols_new = _parse_appended(raw, text, run)
    t_new = cols_new.get("Time", np.array([]))
    valid = np.isfinite(t_new)
    t_new = t_new[valid]
    if len(t_new) == 0:
        run.byte_offset += len(raw)
        return 0
    if (len(run.time) and t_new[0] < run.time[-1]) or np.any(np.diff(t_new) < 0):
        return -1  # out-of-order data: safest is a full reload

    run.time = np.concatenate([np.asarray(run.time), t_new])
    for name, sig in run.signals.items():
        if name in cols_new:
            new_vals = np.asarray(cols_new[name], dtype=sig.data.dtype)[valid]
        else:
            new_vals = np.full(len(t_new), np.nan, dtype=sig.data.dtype)
        # concatenate also detaches from a read-only memory map
        sig.data = np.concatenate([np.asarray(sig.data), new_vals])
    run.byte_offset = complete_to if complete_to is not None else run.byte_offset + len(raw)
    remember_tail(run)
    run.compute_metadata()
    return int(len(t_new))


def _parse_appended(raw: bytes, text: str, run: Run) -> Dict[str, np.ndarray]:
    """Parse appended rows -> {column: float64 array}. Arrow when possible (many times
    faster for wide files), pandas otherwise."""
    cols = run.source_columns
    texts = {c for c in cols if c in run.signals and run.signals[c].labels is not None}

    def encoded(out):                 # text columns -> codes, continuing each signal's own map
        for c in texts:
            if c in out:
                out[c], run.signals[c].labels = encode_text(out[c], run.signals[c].labels)
        return out

    if HAS_PYARROW and len(run.delimiter) == 1:
        try:
            table = pa_csv.read_csv(
                pa.BufferReader(raw),
                read_options=pa_csv.ReadOptions(column_names=cols, use_threads=True),
                parse_options=pa_csv.ParseOptions(delimiter=run.delimiter, invalid_row_handler=lambda r: "skip"),
                convert_options=pa_csv.ConvertOptions(column_types={c: (pa.string() if c in texts else pa.float64()) for c in cols},
                                                      strings_can_be_null=True))
            return encoded({c: table.column(i).to_numpy(zero_copy_only=False) for i, c in enumerate(cols)})
        except Exception:               # Arrow refused these rows: pandas below reads them
            log.debug("live: Arrow could not parse the appended rows; using pandas", exc_info=True)
    engine = "python" if run.delimiter == r"\s+" else "c"
    df = pd.read_csv(io.StringIO(text), sep=run.delimiter, header=None, names=cols,
                     on_bad_lines="skip", engine=engine, index_col=False, dtype={c: str for c in texts})
    if df.empty:
        return {}
    return encoded({c: (df[c].to_numpy(dtype=object) if c in texts else _to_numeric_array(df[c], np.float64)) for c in cols})


def reload_csv(run: Run, all_paths: List[str]) -> Optional[Run]:
    """
    Reload a run from disk with the SAME import settings it was originally loaded with,
    preserving user-level run properties (custom name, offset, description).
    """
    settings = CSVImportSettings.from_dict(run.import_settings) if run.import_settings else CSVImportSettings()
    new_run = load_csv(run.file_path, all_paths, settings)
    if new_run is not None:
        copy_run_user_properties(run, new_run)
    return new_run


def copy_run_user_properties(src: Run, dst: Run):
    """Carry user-edited run properties over to a freshly loaded Run."""
    dst.run_name = src.run_name
    dst.description = src.description
    dst.time_offset = src.time_offset
    if src.csv_display_name and src.file_path == dst.file_path:
        dst.csv_display_name = src.csv_display_name  # keep a user rename


def _run_nbytes(run: Run) -> int:
    return int(np.asarray(run.time).nbytes + sum(np.asarray(s.data).nbytes for s in run.signals.values()))


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
