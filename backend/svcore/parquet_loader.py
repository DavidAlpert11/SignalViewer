"""Parquet files (.parquet / .pq) - T40, read with pyarrow (already a dependency).

The time: the column the user chose (import settings), else the pandas index when the file was
written by pandas with a time / numeric index, else a column named like a time (time, t,
timestamp...) or the first date-time column; date-times become seconds from the first sample.
No time at all: the sample number. Numeric and true / false columns become signals; text and
categorical columns become states with their texts (up to MAX_STATES different values); other
types (lists, structs, binary) are listed as left out."""
import json
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from svcore.mat_loader import TIME_NAMES
from svcore.models import Run, Signal
from svcore.extras import missing

MAX_STATES = 1000


class ParquetError(Exception):
    pass


def _index_column(schema) -> Optional[str]:
    """The column pandas stored its index in (None: no pandas index / a plain range)."""
    md = schema.metadata or {}
    try:
        cols = json.loads(md[b"pandas"])["index_columns"]
    except (KeyError, ValueError, TypeError):
        return None
    return cols[0] if cols and isinstance(cols[0], str) else None


def _to_seconds(col) -> Optional[np.ndarray]:
    """A time column -> float seconds (date-times: from their first value). None: not a time."""
    import pyarrow as pa
    import pyarrow.compute as pc
    t = col.type
    if pa.types.is_timestamp(t) or pa.types.is_date(t) or pa.types.is_duration(t):
        ns = pc.cast(pc.cast(col, pa.timestamp("ns")) if not pa.types.is_duration(t) else pc.cast(col, pa.duration("ns")),
                     pa.int64()).to_numpy(zero_copy_only=False).astype(np.float64)
        return (ns - np.nanmin(ns)) * 1e-9 if not pa.types.is_duration(t) else ns * 1e-9
    if pa.types.is_integer(t) or pa.types.is_floating(t):
        return col.to_numpy(zero_copy_only=False).astype(np.float64)
    return None


def load_parquet(path: str, display_name: str, time_column: Optional[str] = None) -> Tuple[Optional[Run], Dict[str, Any]]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        raise ParquetError(missing("Reading Parquet", "parquet")) from None
    try:
        table = pq.read_table(path)
    except (OSError, pa.ArrowException, ValueError) as e:
        raise ParquetError(f"This is not a Parquet file, or it is damaged ({type(e).__name__}).") from None
    names: List[str] = list(table.schema.names)
    report: Dict[str, Any] = {}
    if not names or table.num_rows == 0:
        return None, report

    # the time column
    tname: Optional[str] = None
    if time_column and time_column in names:
        tname = time_column
    else:
        idx = _index_column(table.schema)
        if idx in names and _to_seconds(table.column(idx)) is not None:
            tname = idx
        else:
            by_name = [n for n in names if n.lower() in TIME_NAMES and _to_seconds(table.column(n)) is not None]
            dates = [n for n in names if pa.types.is_timestamp(table.column(n).type)]
            pick = by_name or dates
            tname = pick[0] if pick else None
    t = _to_seconds(table.column(tname)) if tname else None
    if t is None:
        t = np.arange(table.num_rows, dtype=np.float64)
        report["noTime"] = True
    keep = np.isfinite(t)
    order = np.argsort(t[keep], kind="stable") if np.any(np.diff(t[keep]) < 0) else None

    def finish(y: np.ndarray) -> np.ndarray:
        y = y[keep]
        return y[order] if order is not None else y

    tt = finish(t) if tname else t
    sigs: Dict[str, Signal] = {}
    left_out: List[str] = []
    for n in names:
        if n == tname or n.startswith("__index_level_"):
            continue
        col = table.column(n)
        typ = col.type
        labels = None
        if pa.types.is_dictionary(typ):
            col = col.cast(typ.value_type)
            typ = col.type
        if pa.types.is_boolean(typ) or pa.types.is_integer(typ) or pa.types.is_floating(typ) or pa.types.is_decimal(typ):
            y = col.cast(pa.float64()).to_numpy(zero_copy_only=False)
        elif pa.types.is_string(typ) or pa.types.is_large_string(typ):
            vals = col.to_pylist()
            uniq = sorted({v for v in vals if v is not None})
            if len(uniq) > MAX_STATES:
                left_out.append(f"{n} (text with {len(uniq)} different values)")
                continue
            code = {v: i for i, v in enumerate(uniq)}
            y = np.array([code[v] if v is not None else np.nan for v in vals], dtype=np.float64)
            labels = {i: v for v, i in code.items()}
        elif pa.types.is_timestamp(typ):
            y = _to_seconds(col)          # another date-time column: seconds from its first value
            if y is None:
                continue
        else:
            left_out.append(f"{n} ({typ})")
            continue
        sigs[n] = Signal(name=n, data=np.asarray(finish(np.asarray(y, dtype=np.float64)), dtype=np.float64),
                         labels=labels)
    if left_out:
        report["skipped"] = left_out
    if not sigs:
        return None, report
    run = Run(file_path=path, csv_display_name=display_name, time=tt)
    run.signals = sigs
    run.compute_metadata()
    run.import_settings = {"format": "parquet", **({"time_column": tname} if tname else {})}
    run.time_source = tname
    return run, report
