"""New columns (see svcore/sweep/__init__.py).

Per run   - a formula on the columns of the same row: "range_m / payload_kg", "abs(roll) * 2",
            "if(wind_mps > 4, range_m, nan)". A column whose name is not a plain identifier is
            written col("max roll [deg]"). Parsed and checked by the one whitelist of svcore/formula.py
            (parse_rows: a closed set of nodes and functions, no eval, no name with __); here only the values.
            Conditions (S1): comparisons (also chained: 0 < x <= 5), and / or / not, if(cond, a, b),
            between(x, lo, hi), x in (1, 2) / not in; text: == "mild", in ("mild", "strong"),
            contains(name, "B"), text(x); a text result is a text column (if(wind > 8, "high", "low")).
            bins(x, [0, 5, 10]) -> categories "<0", "0–5", "5–10", "≥10"; rank(x) (1 = the smallest)
            and pct(x) (its percentile, 0-100) over the table's runs.
            A missing value (an empty cell) makes a comparison, if's choice and contains missing.
Per set   - one value per parameter set: an operation (min, max, mean, median, p10, p90, std,
            spread, count, count_true, share) of a column over the runs of the set, optionally only
            those whose must-hold-across columns take given values ("min of range_m over scenario 2, 3").
            count_true / share of a condition column: in how many / what share of its runs it held.
"""
import ast
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from svcore.formula import _BIN, _CMP, ROW_FUNCTIONS, FormulaError, bool_op, parse_rows


class DerivedError(ValueError):
    pass

_FUN: Dict[str, Callable[..., Any]] = {"abs": np.abs, "sqrt": np.sqrt, "exp": np.exp, "log": np.log, "log10": np.log10,
        "sin": np.sin, "cos": np.cos, "tan": np.tan, "atan2": np.arctan2, "sign": np.sign,
        "floor": np.floor, "ceil": np.ceil, "round": np.round, "min": np.fmin, "max": np.fmax,
        "clip": np.clip, "isnan": np.isnan}
# the functions of conditions and text (S1), handled by the evaluator itself
_OWN = ("if", "where", "between", "contains", "text", "bins", "rank", "pct")
FUNCTIONS = sorted(set(_FUN) | set(_OWN))
# the whitelist (svcore/formula.py) names the functions; here is what each does - the two lists are one
assert set(FUNCTIONS) == set(ROW_FUNCTIONS), "svcore.formula.ROW_FUNCTIONS and the row functions here differ"
_CONST = {"pi": np.pi, "e": np.e, "nan": np.nan, "inf": np.inf}


class _Text:
    """A text value per row (object array; None where missing) - kept apart from numbers so that
    arithmetic on text is a clear error, not a silent NaN."""
    __slots__ = ("v",)

    def __init__(self, v):
        self.v = v


def _fmt(x: float) -> str:
    return f"{x:g}"


def row_formula(df: pd.DataFrame, expr: str) -> np.ndarray:
    """Evaluate `expr` on every row of df: a float array, or an object array of text (None missing)."""
    try:
        tree = parse_rows(expr)
    except FormulaError as e:
        raise DerivedError(f"Formula: {e}") from None
    n = len(df)

    def col(name: str):
        if name not in df.columns:
            raise DerivedError(f"No column named {name!r}")
        s = df[name]
        if pd.api.types.is_bool_dtype(s):
            return s.to_numpy(dtype=float)
        if not pd.api.types.is_numeric_dtype(s):
            a = s.astype(object).to_numpy()
            return _Text(np.array([None if (x is None or (isinstance(x, float) and np.isnan(x))) else str(x)
                                   for x in a], dtype=object))
        return s.to_numpy(dtype=float)

    def text_of(v) -> np.ndarray:
        """A text value as an object array of n rows."""
        if isinstance(v, _Text):
            return np.broadcast_to(np.asarray(v.v, dtype=object), (n,))
        raise DerivedError("Expected text here (a text column or \"quoted text\")")

    def num(v, what: str = "this") -> np.ndarray:
        if isinstance(v, _Text):
            raise DerivedError(f"{what} needs numbers, not text (compare text with == != or in)")
        return np.asarray(v, dtype=float)

    def missing(v) -> np.ndarray:
        if isinstance(v, _Text):
            return np.array([x is None for x in text_of(v)], dtype=bool)
        return np.isnan(np.asarray(v, dtype=float))

    def truth(v) -> np.ndarray:
        a = num(v, "A condition")
        return np.isfinite(a) & (a != 0)

    def compare(op, a, b) -> np.ndarray:
        if isinstance(a, _Text) or isinstance(b, _Text):
            if type(op) not in (ast.Eq, ast.NotEq):
                raise DerivedError("Text compares only with == and != (or in)")
            if not (isinstance(a, _Text) and isinstance(b, _Text)):
                raise DerivedError("Text compared with a number: put the number in quotes, or use text(x)")
            ta, tb = text_of(a), text_of(b)
            r = np.array([x == y for x, y in zip(ta, tb)], dtype=float)
            if isinstance(op, ast.NotEq):
                r = 1.0 - r
            return np.where(missing(a) | missing(b), np.nan, r)
        x, y = num(a), num(b)
        with np.errstate(all="ignore"):
            r = _CMP[type(op)](x, y).astype(float)
        return np.where(np.isnan(x) | np.isnan(y), np.nan, r)

    def member(v, items: ast.AST, negate: bool) -> np.ndarray:
        if not isinstance(items, (ast.Tuple, ast.List, ast.Set)):
            raise DerivedError("in takes a list of values: x in (1, 2) or name in (\"a\", \"b\")")
        vals = [ev(e) for e in items.elts]
        if isinstance(v, _Text):
            if not all(isinstance(x, _Text) for x in vals):
                raise DerivedError("A text column is compared with text values in quotes")
            want = {x for w in vals for x in np.atleast_1d(w.v).tolist()}
            r = np.array([x in want for x in text_of(v)], dtype=float)
        else:
            want_n = np.array([float(num(x)) for x in vals])
            r = np.isin(num(v), want_n).astype(float)
        if negate:
            r = 1.0 - r
        return np.where(missing(v), np.nan, r)

    def choose(c, a, b):
        cm = num(c, "if's condition")
        pick = np.broadcast_to(np.isfinite(cm) & (cm != 0), (n,))
        unknown = np.broadcast_to(np.isnan(cm), (n,))
        if isinstance(a, _Text) or isinstance(b, _Text):
            ta = text_of(a) if isinstance(a, _Text) else None
            tb = text_of(b) if isinstance(b, _Text) else None
            if ta is None and not np.all(np.isnan(num(a))) or tb is None and not np.all(np.isnan(num(b))):
                raise DerivedError("if(): both answers text, or both numbers")
            ta = ta if ta is not None else np.full(n, None, dtype=object)
            tb = tb if tb is not None else np.full(n, None, dtype=object)
            r = np.where(pick, ta, tb).astype(object)
            r[unknown] = None
            return _Text(r)
        r = np.where(pick, num(a), num(b)).astype(float)
        return np.where(unknown, np.nan, r)

    def bins(x, edges_node) -> _Text:
        if not isinstance(edges_node, (ast.List, ast.Tuple)) or len(edges_node.elts) < 1:
            raise DerivedError("bins(x, [0, 5, 10]): the edges as a list of numbers")
        edges = [float(num(ev(e))) for e in edges_node.elts]
        if any(b <= a for a, b in zip(edges, edges[1:])):
            raise DerivedError("bins(): the edges must grow (0, 5, 10)")
        labels = [f"<{_fmt(edges[0])}"] + [f"{_fmt(a)}–{_fmt(b)}" for a, b in zip(edges, edges[1:])] + [f"≥{_fmt(edges[-1])}"]
        v = np.broadcast_to(num(x), (n,))
        k = np.searchsorted(np.asarray(edges), v, side="right")
        out = np.array([labels[i] for i in k], dtype=object)
        out[np.isnan(v)] = None
        return _Text(out)

    def call(name: str, args: List[ast.AST]):
        def want(k):
            if len(args) != k:
                raise DerivedError(f"{name}() takes {k} argument(s)")
        if name == "col":
            if len(args) == 1 and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
                return col(args[0].value)
            raise DerivedError('col("column name") takes a name in quotes')
        if name in ("_if", "where"):                   # where(): the older name of if()
            want(3)
            return choose(ev(args[0]), ev(args[1]), ev(args[2]))
        if name == "between":
            want(3)
            x, lo, hi = (num(ev(a)) for a in args)
            with np.errstate(all="ignore"):
                r = ((x >= lo) & (x <= hi)).astype(float)
            return np.where(np.isnan(x), np.nan, r)
        if name == "contains":
            want(2)
            hay, needle = ev(args[0]), ev(args[1])
            if not isinstance(needle, _Text):
                raise DerivedError('contains(name, "B"): the text to find in quotes')
            nd = text_of(needle)
            return np.array([np.nan if h is None else float(str(w) in h) for h, w in zip(text_of(hay), nd)])
        if name == "text":
            want(1)
            v = ev(args[0])
            if isinstance(v, _Text):
                return v
            a = np.broadcast_to(num(v), (n,))
            return _Text(np.array([None if np.isnan(x) else _fmt(x) for x in a], dtype=object))
        if name == "bins":
            want(2)
            return bins(ev(args[0]), args[1])
        if name in ("rank", "pct"):
            want(1)
            s = pd.Series(np.broadcast_to(num(ev(args[0])), (n,)))
            return (s.rank(method="min") if name == "rank" else s.rank(pct=True) * 100.0).to_numpy(dtype=float)
        if name in _FUN:
            vals = [num(ev(a), f"{name}()") for a in args]
            try:
                with np.errstate(all="ignore"):
                    return _FUN[name](*vals)
            except TypeError:
                raise DerivedError(f"{name}(): wrong number of arguments") from None
        raise DerivedError(f"Unknown function: {'if' if name == '_if' else name}")

    def ev(nd):
        if isinstance(nd, ast.Expression):
            return ev(nd.body)
        if isinstance(nd, ast.Constant):
            if isinstance(nd.value, str):
                return _Text(nd.value)
            if isinstance(nd.value, (int, float)) and not isinstance(nd.value, bool):
                return float(nd.value)
            raise DerivedError("Only numbers and \"text\" are allowed as values")
        if isinstance(nd, ast.Name):
            if nd.id in _CONST:
                return _CONST[nd.id]
            if nd.id in ("True", "False"):
                return float(nd.id == "True")
            return col(nd.id)
        if isinstance(nd, ast.BinOp) and type(nd.op) in _BIN:
            with np.errstate(all="ignore"):
                return _BIN[type(nd.op)](num(ev(nd.left), "+ - * /"), num(ev(nd.right), "+ - * /"))
        if isinstance(nd, ast.UnaryOp):
            v = ev(nd.operand)
            if isinstance(nd.op, ast.Not):
                return np.where(missing(v), np.nan, (~truth(v)).astype(float))
            if isinstance(nd.op, (ast.USub, ast.UAdd)):
                return -num(v) if isinstance(nd.op, ast.USub) else num(v)
        if isinstance(nd, ast.Compare):
            left, out = ev(nd.left), None
            for op, comp in zip(nd.ops, nd.comparators):
                if isinstance(op, (ast.In, ast.NotIn)):
                    r = member(left, comp, isinstance(op, ast.NotIn))
                    right = None
                elif type(op) in _CMP:
                    right = ev(comp)
                    r = compare(op, left, right)
                else:
                    raise DerivedError("Unsupported comparison")
                out = r if out is None else np.where(np.isnan(out) | np.isnan(r), np.nan, (out != 0) & (r != 0)).astype(float)
                left = right
            return out
        if isinstance(nd, ast.BoolOp):
            # Kleene, as the signal formulas: missing unless a known side decides
            vals = [ev(v) for v in nd.values]
            return bool_op([truth(v) for v in vals], [missing(v) for v in vals], isinstance(nd.op, ast.And))
        if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name) and not nd.keywords:
            return call(nd.func.id, nd.args)
        raise DerivedError("Only numbers, \"text\", columns, + - * / ** %, comparisons, and / or / not, if() "
                           "and the listed functions")

    r = ev(tree)
    if isinstance(r, _Text):
        return np.broadcast_to(np.asarray(r.v, dtype=object), (n,)).copy()
    out = np.broadcast_to(np.asarray(r, dtype=float), (n,)).copy()
    out[~np.isfinite(out)] = np.nan
    return out


def is_text(values: np.ndarray) -> bool:
    """A formula's result is a text column."""
    return values.dtype == object


SET_OPS = ("min", "max", "mean", "median", "p10", "p90", "std", "spread", "count", "count_true", "share")


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
    elif op == "share":                                 # of the runs with a value, the share where it held (!= 0)
        r = g.apply(lambda x: float(np.mean(x.dropna() != 0)) if x.notna().any() else np.nan)
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
