"""Sweeps (the run-envelope area): a results table, one row per run - parameters and scenario
columns first, outputs last - read fast, its columns described and their roles guessed.

Not to be confused with svcore/envelope.py (many runs of ONE signal over time, the Monte-Carlo
view in Recordings). Here a run is a row of numbers, not a recording.

Reading a big table fast
------------------------
* CSV: Apache Arrow's multi-threaded parser (the same one csv_loader uses), every column at once;
  text columns become dictionary-encoded (a scenario name is stored once, not per row).
* The first read of a big file writes a Parquet copy (zstd) into the cache folder, keyed on path +
  size + mtime: reopening is a column read from a compressed binary file, not a parse.
* Parquet and Excel are read as they are (Excel through pandas: those files are small).

Roles
-----
param   - what we choose (a design parameter)
hold    - what we don't choose and must hold across (scenario, wind, seed...)
output  - a result of the run
id      - one value per row (a run number): not a parameter
ignore  - nothing to say: the same value in every run, or empty

Guess: the outputs are the trailing block - from the first column that looks like a measurement
(many distinct numbers) to the end; before it, grid-like columns are inputs, a name that says
scenario / case / seed... makes an input a `hold`. A constant column is `ignore` wherever it is.
The user corrects the guess once; the study keeps it.
"""
import hashlib
import os
import re
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    import pyarrow as pa
    import pyarrow.csv as pa_csv
    import pyarrow.parquet as pq
    HAVE_ARROW = True
except ImportError:                     # pragma: no cover - pyarrow is in requirements
    HAVE_ARROW = False

ROLES = ("param", "hold", "output", "id", "ignore")
SCALES = ("linear", "log", "category", "ordinal")

CACHE_DIR = os.path.join(os.environ.get("SV_CACHE_DIR") or os.path.join(os.path.expanduser("~"), ".signalviewer", "cache"), "sweeps")
CACHE_MIN_BYTES = int(float(os.environ.get("SV_SWEEP_CACHE_MIN_MB", "20")) * 1024 * 1024)

_HOLD_NAME = re.compile(r"scen|case|seed|weather|disturb|noise|wind|env(iron)?|condition|תרחיש|מקרה", re.I)
_ID_NAME = re.compile(r"(^|_)(run|id|index|idx|row)(_|$)|run_?id|^#$", re.I)


class SweepError(ValueError):
    pass


# ----------------------------------------------------------------------------- reading
def _cache_path(path: str) -> str:
    st = os.stat(path)
    key = hashlib.sha1(f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:20]
    return os.path.join(CACHE_DIR, key + ".parquet")


def _read_csv(path: str) -> pd.DataFrame:
    if not HAVE_ARROW:
        return pd.read_csv(path, sep=None, engine="python")
    from svcore.csv_loader import detect_delimiter
    delim = detect_delimiter(path)
    table = pa_csv.read_csv(
        path,
        read_options=pa_csv.ReadOptions(use_threads=True, block_size=8 << 20),
        parse_options=pa_csv.ParseOptions(delimiter=delim),
        convert_options=pa_csv.ConvertOptions(strings_can_be_null=True, auto_dict_encode=True, auto_dict_max_cardinality=4096),
    )
    return table.to_pandas(self_destruct=True)


def read_table(path: str, use_cache: bool = True) -> pd.DataFrame:
    """The whole table. Big CSVs go through (and later come from) a Parquet copy in the cache."""
    if not os.path.isfile(path):
        raise SweepError(f"File not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext in (".parquet", ".pq"):
        return pd.read_parquet(path)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    big = use_cache and HAVE_ARROW and os.path.getsize(path) >= CACHE_MIN_BYTES
    if big:
        cp = _cache_path(path)
        if os.path.isfile(cp):
            try:
                return pd.read_parquet(cp)
            except Exception:           # a half-written copy: read the CSV again
                os.remove(cp)
    df = _read_csv(path)
    if df.shape[1] == 0 or df.shape[0] == 0:
        raise SweepError("The table is empty.")
    if big:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            tmp = _cache_path(path) + ".part"
            pq.write_table(pa.Table.from_pandas(df, preserve_index=False), tmp, compression="zstd")
            os.replace(tmp, _cache_path(path))
        except OSError:
            pass                        # no room for the copy: the table still opens
    return df


# ----------------------------------------------------------------------------- describing
def _is_number(s: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)


def describe_column(s: pd.Series, rows: int) -> Dict:
    """What the guess (and the UI) needs: kind, how many distinct values, range, missing, constant."""
    n_missing = int(s.isna().sum())
    vals = s.dropna()
    nunique = int(vals.nunique())
    info: Dict = {"name": str(s.name), "kind": "number" if _is_number(s) else "text",
                  "distinct": nunique, "missing": n_missing,
                  "constant": nunique <= 1, "empty": n_missing > 0.9 * rows}
    if info["kind"] == "number" and nunique:
        info["min"] = float(vals.min())
        info["max"] = float(vals.max())
        info["integer"] = bool(np.all(np.mod(vals.to_numpy(dtype=float), 1) == 0))
    if nunique <= 50:
        u = vals.unique()
        try:
            u = sorted(u)
        except TypeError:
            u = sorted(map(str, u))
        info["values"] = [v.item() if hasattr(v, "item") else v for v in u]
    return info


def _grid_like(c: Dict, rows: int) -> bool:
    """An input sits on a few values that repeat across many runs."""
    return c["distinct"] <= max(12, min(200, rows // 20))


def guess_scale(c: Dict) -> str:
    if c["kind"] == "text":
        return "category"
    if c["distinct"] <= 12 and c.get("integer"):
        return "ordinal"
    lo, hi = c.get("min"), c.get("max")
    if lo is not None and lo > 0 and hi / lo >= 1000:
        return "log"
    return "linear"


def guess_roles(cols: List[Dict], rows: int) -> List[str]:
    """See the module docstring: outputs are the trailing block from the first measurement-like column."""
    first_out = len(cols)
    for i, c in enumerate(cols):
        if c["constant"] or c["empty"]:
            continue
        if c["kind"] == "number" and not _grid_like(c, rows) and not _ID_NAME.search(c["name"]):
            first_out = i
            break
    roles = []
    for i, c in enumerate(cols):
        if c["constant"] or c["empty"]:
            roles.append("ignore")
        elif c["distinct"] == rows and rows > 50 and (_ID_NAME.search(c["name"]) or c.get("integer") or c["kind"] == "text"):
            roles.append("id")
        elif i >= first_out:
            roles.append("output")
        elif _HOLD_NAME.search(c["name"]):
            roles.append("hold")
        else:
            roles.append("param")
    return roles


def describe(df: pd.DataFrame) -> List[Dict]:
    rows = len(df)
    cols = [describe_column(df[c], rows) for c in df.columns]
    for c, role in zip(cols, guess_roles(cols, rows)):
        c["role"] = role
        c["scale"] = guess_scale(c)
    return cols


# ----------------------------------------------------------------------------- the shape of the study
def summary(df: pd.DataFrame, roles: Dict[str, str]) -> Dict:
    """How many parameter sets, how many combinations of the hold-across columns, and which sets
    miss a combination or have a run that gave no outputs."""
    params = [c for c in df.columns if roles.get(c) == "param"]
    holds = [c for c in df.columns if roles.get(c) == "hold"]
    outs = [c for c in df.columns if roles.get(c) == "output"]
    out: Dict = {"rows": int(len(df)), "params": params, "holds": holds, "outputs": outs}
    n_combos = int(df[holds].drop_duplicates().shape[0]) if holds else 1
    out["combos"] = n_combos
    if not params:
        out.update(sets=0, complete=0, missing=0, duplicates=0, failedRuns=0)
        return out
    # group numbers, not joined strings: a million rows in well under a second
    def ids(cols):
        return df.groupby(cols, sort=False, dropna=False, observed=True).ngroup().to_numpy()
    set_id = ids(params)
    n_sets = int(set_id.max()) + 1 if len(set_id) else 0
    counts = np.bincount(set_id, minlength=n_sets)
    if holds:
        combo_id = ids(holds)
        pairs = np.unique(set_id.astype(np.int64) * (n_combos + 1) + combo_id)
        distinct = np.bincount(pairs // (n_combos + 1), minlength=n_sets)
        complete = int((distinct == n_combos).sum())
        duplicates = int((counts > distinct).sum())
    else:
        complete, duplicates = n_sets, int((counts > 1).sum())
    failed = int(df[outs].isna().any(axis=1).sum()) if outs else 0     # a run with an output missing did not finish
    out.update(sets=n_sets, complete=complete, missing=n_sets - complete, duplicates=duplicates, failedRuns=failed)
    return out


def head(df: pd.DataFrame, n: int = 20) -> List[List]:
    """The first rows, JSON-safe (NaN as None)."""
    h = df.head(n).astype(object).where(pd.notna(df.head(n)), None)
    return [[v.item() if hasattr(v, "item") else v for v in row] for row in h.itertuples(index=False, name=None)]
