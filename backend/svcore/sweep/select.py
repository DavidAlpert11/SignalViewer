"""What the brush selects, on the whole table (1.29): the axes' filters of All runs resolved on every kept
run, never on the runs drawn (a sample above the cap). Keep / Exclude, a group saved from the brush,
Export shown and the counts all come from here - one answer for each, whatever was drawn.

A selection description (JSON from the page):
    filters  {column: {kind: "ranges", ranges: [[a, b], ...]}
                    | {kind: "values", values: [number, ...]}        - a number column
                    | {kind: "labels", labels: [text, ...]}}         - a text column, by its labels
             filters on columns the prepared table does not have are ignored (as on the page)
    sets     [set index] - the sets the page shows (Show, keep / exclude steps, hidden groups:
             per set, exact on the page), or null for every set

Numbers are compared as the page compares them: as Float32, the bounds inclusive."""
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from svcore.sweep.encode import labels_of
from svcore.sweep.evaluate import Prepared


def _f32(s: pd.Series) -> np.ndarray:
    return pd.to_numeric(s, errors="coerce").to_numpy(dtype=np.float32, na_value=np.nan).astype(np.float64)


def column_mask(s: pd.Series, f: Dict[str, Any]) -> Optional[np.ndarray]:
    """The runs one filter keeps (None: a filter that keeps everything - an unknown kind)."""
    kind = f.get("kind")
    if kind == "labels":
        want = [str(x) for x in (f.get("labels") or [])]
        return labels_of(s).isin(want).fillna(False).to_numpy(dtype=bool)
    v = _f32(s)
    finite = np.isfinite(v)
    if kind == "values":
        want = np.asarray([float(x) for x in (f.get("values") or []) if x is not None], dtype=np.float64)
        return finite & np.isin(v, want)
    if kind == "ranges":
        m = np.zeros(len(v), dtype=bool)
        with np.errstate(invalid="ignore"):
            for a, b in f.get("ranges") or []:
                lo, hi = min(float(a), float(b)), max(float(a), float(b))
                m |= (v >= lo) & (v <= hi)
        return m & finite
    return None


def run_mask(p: Prepared, filters: Optional[Dict[str, Dict[str, Any]]], sets: Optional[List[int]] = None) -> np.ndarray:
    """1 for each kept run (a row of p.df) the description selects."""
    m = np.ones(len(p.df), dtype=bool)
    if sets is not None:
        ok = np.zeros(p.n_sets, dtype=bool)
        idx = np.asarray([int(i) for i in sets if 0 <= int(i) < p.n_sets], dtype=np.int64)
        ok[idx] = True
        m &= ok[p.set_id] if len(p.set_id) else m
    for name, f in (filters or {}).items():
        if name not in p.df.columns or not isinstance(f, dict):
            continue
        cm = column_mask(p.df[name], f)
        if cm is not None:
            m &= cm
    return m


def selection(p: Prepared, filters: Optional[Dict[str, Dict[str, Any]]], sets: Optional[List[int]] = None) -> Dict[str, Any]:
    """The runs and the parameter sets a description selects, of the whole table: the sets that have at
    least one selected run (as the lines on screen meant), the runs' rows in the table."""
    m = run_mask(p, filters, sets)
    chosen = np.unique(p.set_id[m]) if m.any() else np.zeros(0, dtype=np.int64)
    return {"mask": m, "sets": [int(x) for x in chosen], "rows": [int(x) for x in p.row_id[m]], "runs": int(m.sum())}
