"""What the brush selects, on the whole table (1.29): the axes' filters of All runs resolved on every kept
run, never on the runs drawn (a sample above the cap). Keep / Exclude, a group saved from the brush,
Export shown and the counts all come from here - one answer for each, whatever was drawn.

A selection description (JSON from the page):
    filters  {column: {kind: "ranges", ranges: [[a, b], ...]}
                    | {kind: "values", values: [number, ...]}        - a number column
                    | {kind: "labels", labels: [text, ...]}}         - a text column, by its labels
                                                                      (or "values": codes into its labels)
             filters on columns the prepared table does not have are ignored (as on the page)
    sets     [set index] - the sets the page shows (Show, keep / exclude steps, hidden groups:
             per set, exact on the page), or null for every set

Numbers are compared as the page compares them: as Float32, the bounds inclusive."""
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from svcore.sweep.encode import category_labels, labels_of
from svcore.sweep.evaluate import Prepared


def _f32(s: pd.Series) -> np.ndarray:
    return pd.to_numeric(s, errors="coerce").to_numpy(dtype=np.float32, na_value=np.nan).astype(np.float64)


def column_mask(s: pd.Series, f: Dict[str, Any]) -> Optional[np.ndarray]:
    """The runs one filter keeps (None: a filter that keeps everything - an unknown kind)."""
    kind = f.get("kind")
    if kind == "labels":
        labels = [str(x) for x in (f.get("labels") or [])]
        return labels_of(s).isin(labels).fillna(False).to_numpy(dtype=bool)
    if kind == "values" and not (pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)):
        # a text column by its codes (a filter made in All runs, read in Parameter sets without the runs on the
        # page, FT9): codes into the labels the server sends the page for that column - the same
        lab = category_labels(s)
        want_l = [lab[int(x)] for x in (f.get("values") or []) if x is not None and 0 <= int(x) < len(lab)]
        return labels_of(s).isin(want_l).fillna(False).to_numpy(dtype=bool)
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


def frame_mask(df: pd.DataFrame, filters: Optional[Dict[str, Dict[str, Any]]]) -> np.ndarray:
    """1 for each row of a table every filter keeps (the Data step's plot: the table as read)."""
    m = np.ones(len(df), dtype=bool)
    for name, f in (filters or {}).items():
        if name not in df.columns or not isinstance(f, dict):
            continue
        cm = column_mask(df[name], f)
        if cm is not None:
            m &= cm
    return m


def run_mask(p: Prepared, filters: Optional[Dict[str, Dict[str, Any]]], sets: Optional[List[int]] = None) -> np.ndarray:
    """1 for each kept run (a row of p.df) the description selects."""
    m = frame_mask(p.df, filters)
    if sets is not None and len(p.set_id):
        ok = np.zeros(p.n_sets, dtype=bool)
        idx = np.asarray([int(i) for i in sets if 0 <= int(i) < p.n_sets], dtype=np.int64)
        ok[idx] = True
        m &= ok[p.set_id]
    return m


def selection(p: Prepared, filters: Optional[Dict[str, Dict[str, Any]]], sets: Optional[List[int]] = None) -> Dict[str, Any]:
    """The runs and the parameter sets a description selects, of the whole table: the sets that have at
    least one selected run (as the lines on screen meant), the runs' rows in the table."""
    m = run_mask(p, filters, sets)
    chosen = np.unique(p.set_id[m]) if m.any() else np.zeros(0, dtype=np.int64)
    return {"mask": m, "sets": [int(x) for x in chosen], "rows": [int(x) for x in p.row_id[m]], "runs": int(m.sum())}


# a sample above the cap keeps this share for the lines the filters leave out: drawn faint, they show
# where the rest of the table is
BACKGROUND = 0.1


def sample_rows(n: int, cap: int, keep: Optional[np.ndarray] = None, first: Optional[np.ndarray] = None,
                must: Optional[np.ndarray] = None, seed: int = 0) -> np.ndarray:
    """Which of n rows to send to draw, sorted: every row up to `cap` (0 = no cap); above it the rows the
    filters keep first (`keep`; all of them when they fit, else a sample - `first` (row numbers, e.g. one
    run of each set) before the rest), plus a little background, plus `must` (the picked run, the open set)
    always."""
    if cap <= 0 or n <= cap:
        return np.arange(n)
    rng = np.random.default_rng(seed)
    kept = np.arange(n) if keep is None else np.flatnonzero(keep)
    other = np.zeros(0, dtype=np.int64) if keep is None else np.flatnonzero(~keep)
    bg = min(len(other), max(int(cap * BACKGROUND), cap - len(kept)))
    room = cap - bg
    if len(kept) > room:
        pre = kept if first is None else np.intersect1d(first, kept, assume_unique=True)
        if len(pre) >= room:
            kept = rng.choice(pre, room, replace=False)
        else:
            rest = np.setdiff1d(kept, pre, assume_unique=True)
            kept = np.concatenate([pre, rng.choice(rest, room - len(pre), replace=False)])
    parts = [kept, rng.choice(other, bg, replace=False) if bg else other[:0]]
    if must is not None and len(must):
        parts.append(np.asarray(must, dtype=np.int64))
    return np.unique(np.concatenate(parts).astype(np.int64))
