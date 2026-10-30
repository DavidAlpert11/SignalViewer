"""Describing the columns and guessing their roles and scales (see svcore/sweep/__init__.py)."""
import re
from typing import Dict, List

import numpy as np
import pandas as pd

ROLES = ("param", "hold", "output", "id", "ignore")
SCALES = ("linear", "log", "category", "ordinal")

_HOLD_NAME = re.compile(r"scen|case|seed|weather|disturb|noise|wind|env(iron)?|condition|תרחיש|מקרה", re.I)
_ID_NAME = re.compile(r"(^|_)(run|id|index|idx|row)(_|$)|run_?id|^#$", re.I)


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


