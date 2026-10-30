"""New columns (see svcore/sweep/__init__.py).

Per run   - a formula on the columns of the same row: "range_m / payload_kg", "abs(roll) * 2",
            "where(wind_mps > 4, range_m, nan)". A column whose name is not a plain identifier is
            written col("max roll [deg]"). Parsed with `ast` - a closed set of nodes and functions,
            no eval - the same rule as the signal formulas (svcore/formula.py).
Per set   - one value per parameter set: an operation (min, max, mean, median, p10, p90, std,
            spread, count, count_true) of a column over the runs of the set, optionally only those
            whose must-hold-across columns take given values ("min of range_m over scenario 2, 3").
"""
import ast
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


class DerivedError(ValueError):
    pass


_BIN = {ast.Add: np.add, ast.Sub: np.subtract, ast.Mult: np.multiply, ast.Div: np.divide,
        ast.Pow: np.power, ast.Mod: np.mod}
_CMP = {ast.Gt: np.greater, ast.Lt: np.less, ast.GtE: np.greater_equal, ast.LtE: np.less_equal,
        ast.Eq: np.equal, ast.NotEq: np.not_equal}
_FUN = {"abs": np.abs, "sqrt": np.sqrt, "exp": np.exp, "log": np.log, "log10": np.log10,
        "sin": np.sin, "cos": np.cos, "tan": np.tan, "atan2": np.arctan2, "sign": np.sign,
        "floor": np.floor, "ceil": np.ceil, "round": np.round, "min": np.fmin, "max": np.fmax,
        "clip": np.clip, "where": np.where, "isnan": np.isnan}
_CONST = {"pi": np.pi, "e": np.e, "nan": np.nan, "inf": np.inf}


def row_formula(df: pd.DataFrame, expr: str) -> np.ndarray:
    """Evaluate `expr` on every row of df; returns a float array."""
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise DerivedError(f"Formula: {e.msg}") from None

    def col(name: str) -> np.ndarray:
        if name not in df.columns:
            raise DerivedError(f"No column named {name!r}")
        s = df[name]
        if not pd.api.types.is_numeric_dtype(s):
            raise DerivedError(f"{name!r} is text - a formula needs numbers")
        return s.to_numpy(dtype=float)

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id in _CONST:
                return _CONST[n.id]
            return col(n.id)
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            with np.errstate(all="ignore"):
                return _BIN[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in _CMP:
            return _CMP[type(n.ops[0])](ev(n.left), ev(n.comparators[0])).astype(float)
        if isinstance(n, ast.BoolOp):
            vals = [ev(v) != 0 for v in n.values]
            r = vals[0]
            for v in vals[1:]:
                r = (r & v) if isinstance(n.op, ast.And) else (r | v)
            return np.asarray(r, dtype=float)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and not n.keywords:
            if n.func.id == "col" and len(n.args) == 1 and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                return col(n.args[0].value)
            if n.func.id in _FUN:
                with np.errstate(all="ignore"):
                    return _FUN[n.func.id](*[ev(a) for a in n.args])
            raise DerivedError(f"Unknown function: {n.func.id}")
        raise DerivedError("Only numbers, columns, + - * / ** %, comparisons, and/or and the listed functions")

    out = np.broadcast_to(np.asarray(ev(tree), dtype=float), (len(df),)).copy()
    out[~np.isfinite(out)] = np.nan
    return out


SET_OPS = ("min", "max", "mean", "median", "p10", "p90", "std", "spread", "count", "count_true")


def set_aggregate(values: pd.Series, set_id: np.ndarray, n_sets: int, op: str, mask: Optional[np.ndarray] = None) -> np.ndarray:
    """One value per set: `op` of `values` over the runs of each set (only where `mask`)."""
    if op not in SET_OPS:
        raise DerivedError(f"Unknown operation: {op}")
    v = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    sid = set_id
    if mask is not None:
        v, sid = v[mask], sid[mask]
    g = pd.Series(v).groupby(sid)
    if op == "min":
        r = g.min()
    elif op == "max":
        r = g.max()
    elif op == "mean":
        r = g.mean()
    elif op == "median":
        r = g.median()
    elif op == "p10":
        r = g.quantile(0.10)
    elif op == "p90":
        r = g.quantile(0.90)
    elif op == "std":
        r = g.std(ddof=0)
    elif op == "spread":
        r = g.max() - g.min()
    elif op == "count":
        r = g.count()
    else:
        r = g.apply(lambda x: float(np.nansum(x != 0)))
    out = np.full(n_sets, np.nan)
    out[r.index.to_numpy(dtype=int)] = r.to_numpy(dtype=float)
    return out


def hold_mask(df: pd.DataFrame, where: Optional[Dict[str, List]]) -> Optional[np.ndarray]:
    """Rows whose must-hold-across columns take the given values (None: every row)."""
    if not where:
        return None
    m = np.ones(len(df), dtype=bool)
    for c, vals in where.items():
        if c not in df.columns:
            raise DerivedError(f"No column named {c!r}")
        if vals:
            m &= df[c].isin(vals).to_numpy()
    return m
