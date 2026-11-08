"""
Formula signals (N-09): "2*v0 - v1/95 + sin(v2)", evaluated SAFELY.

The UI replaces every signal reference with v0, v1, ... and sends the list of
signal ids. Here the text is parsed with Python's `ast` and only a closed set of
node types, operators and functions is accepted - there is no eval/exec, no
attribute access, no subscripts, no imports. Anything else is a clear error.

Variables:  v0..vN (signals, aligned in time onto v0's samples), t (time),
            pi, e.
Operators:  + - * / ** %, unary -, comparisons (> < >= <= == !=) give 1 / 0.
Functions:  abs sqrt exp log log10 sin cos tan asin acos atan atan2 sign floor
            ceil round min max clip where deriv integ smooth.
            deriv(x, 10) / integ(x, 10): of x's updates at 10 Hz (a slower signal logged fast);
            deriv(x, v1) / integ(x, v1): of the samples where v1 is 1 (a flag "x updated now").
"""

import ast
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from svcore.ops import FilterError, apply_filter, cumulative_trapezoid, moving_average, on_updates


class FormulaError(ValueError):
    pass


_BIN = {ast.Add: np.add, ast.Sub: np.subtract, ast.Mult: np.multiply, ast.Div: np.divide,
        ast.Pow: np.power, ast.Mod: np.mod}
_CMP = {ast.Gt: np.greater, ast.Lt: np.less, ast.GtE: np.greater_equal, ast.LtE: np.less_equal,
        ast.Eq: np.equal, ast.NotEq: np.not_equal}


def _funcs(t: np.ndarray, nan: str = "propagate"):
    def _updates(x, upd, op):
        """the second argument: a rate in Hz (a number) or a flag signal (1 where x updated)"""
        x = np.broadcast_to(np.asarray(x, dtype=np.float64), t.shape)
        try:
            if np.ndim(upd) == 0:
                return on_updates(t, x, op, hz=float(upd))
            return on_updates(t, x, op, flag=np.broadcast_to(np.asarray(upd, dtype=np.float64), t.shape))
        except ValueError as e:
            raise FormulaError(f"{'deriv' if op == 'derivative' else 'integ'}(): {e}") from None

    def deriv(x, upd=None):
        if upd is not None:
            return _updates(x, upd, "derivative")
        x = np.broadcast_to(np.asarray(x, dtype=np.float64), t.shape)
        with np.errstate(divide="ignore", invalid="ignore"):
            r = np.gradient(x, t)
        r[~np.isfinite(r)] = np.nan
        return r

    def integ(x, upd=None):
        if upd is not None:
            return _updates(x, upd, "integral")
        return cumulative_trapezoid(t, np.broadcast_to(np.asarray(x, dtype=np.float64), t.shape), nan)

    def where(c, a, b):
        r = np.where(np.asarray(c) != 0, a, b)
        if nan == "legacy":                              # before 1.23: a missing condition chose a
            return r
        return np.where(_missing(c), np.nan, r)

    def norm01(x):
        x = np.broadcast_to(np.asarray(x, dtype=np.float64), t.shape)
        lo, hi = np.nanmin(x), np.nanmax(x)
        return (x - lo) / (hi - lo) if hi > lo else np.zeros_like(x)

    def _filter(x, fc, kind):
        try:
            return apply_filter(t, np.broadcast_to(np.asarray(x, dtype=np.float64), t.shape), kind, float(fc))
        except FilterError as e:
            raise FormulaError(f"{kind}(): {e}") from None

    def lowpass(x, fc):
        return _filter(x, fc, "lowpass")

    def highpass(x, fc):
        return _filter(x, fc, "highpass")

    def smooth(x, n=10):
        return moving_average(np.broadcast_to(np.asarray(x, dtype=np.float64), t.shape), int(n))

    # Angles and attitude (flight logs). Quaternions: Hamilton, w first (PX4, ArduPilot);
    # Euler angles: aerospace order (yaw, then pitch, then roll), in DEGREES.
    def _f(*xs):
        return [np.asarray(x, dtype=np.float64) for x in xs]

    def q2roll(w, x, y, z):
        w, x, y, z = _f(w, x, y, z)
        return np.degrees(np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)))

    def q2pitch(w, x, y, z):
        w, x, y, z = _f(w, x, y, z)
        return np.degrees(np.arcsin(np.clip(2 * (w * y - z * x), -1.0, 1.0)))

    def q2yaw(w, x, y, z):
        w, x, y, z = _f(w, x, y, z)
        return np.degrees(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))

    def wrap180(a):
        return (np.asarray(a, dtype=np.float64) + 180.0) % 360.0 - 180.0

    def wrap360(a):
        return np.asarray(a, dtype=np.float64) % 360.0

    return {
        "deg": (np.degrees, 1), "rad": (np.radians, 1), "wrap180": (wrap180, 1), "wrap360": (wrap360, 1),
        "q2roll": (q2roll, 4), "q2pitch": (q2pitch, 4), "q2yaw": (q2yaw, 4),
        "abs": (np.abs, 1), "sqrt": (np.sqrt, 1), "exp": (np.exp, 1), "log": (np.log, 1), "log10": (np.log10, 1),
        "sin": (np.sin, 1), "cos": (np.cos, 1), "tan": (np.tan, 1), "asin": (np.arcsin, 1), "acos": (np.arccos, 1),
        "atan": (np.arctan, 1), "atan2": (np.arctan2, 2), "sign": (np.sign, 1), "floor": (np.floor, 1),
        "ceil": (np.ceil, 1), "round": (np.round, 1), "min": (np.minimum, 2), "max": (np.maximum, 2),
        "clip": (np.clip, 3), "where": (where, 3),
        "deriv": (deriv, (1, 2)), "integ": (integ, (1, 2)), "smooth": (smooth, (1, 2)),
        "lowpass": (lowpass, 2), "highpass": (highpass, 2), "norm01": (norm01, 1),
    }


FUNCTION_NAMES = sorted(_funcs(np.zeros(1)).keys())


def parse(expr: str, n_vars: int) -> ast.Expression:
    """Parse and validate; raises FormulaError with a readable message."""
    if not expr or not expr.strip():
        raise FormulaError("The formula is empty.")
    if len(expr) > 2000:
        raise FormulaError("The formula is too long.")
    try:
        tree = ast.parse(expr.replace("^", "**"), mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"Syntax error near position {e.offset or 0}.") from None
    allowed_names = {f"v{i}" for i in range(n_vars)} | {"t", "pi", "e"}
    funcs = _funcs(np.zeros(1))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Load, ast.operator, ast.unaryop, ast.cmpop)):
            if isinstance(node, ast.operator) and type(node) not in _BIN:
                raise FormulaError("Only + - * / ** % are allowed.")
            if isinstance(node, ast.unaryop) and not isinstance(node, (ast.USub, ast.UAdd, ast.Not)):
                raise FormulaError("Only unary minus is allowed.")
            if isinstance(node, ast.cmpop) and type(node) not in _CMP:
                raise FormulaError("Unsupported comparison.")
            continue
        if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Compare)):
            continue
        # conditions (svcore/conditions.py): a and b, a or b, not a - element by element
        if isinstance(node, (ast.BoolOp, ast.And, ast.Or, ast.Not)):
            continue
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
                raise FormulaError("Only numbers are allowed as constants.")
            continue
        if isinstance(node, ast.Name):
            if node.id not in allowed_names and node.id not in funcs:
                raise FormulaError(f"Unknown name: {node.id}")
            continue
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in funcs:
                raise FormulaError("Unknown function.")
            if node.keywords:
                raise FormulaError("Functions take positional arguments only.")
            arity = funcs[node.func.id][1]
            ok = len(node.args) in arity if isinstance(arity, tuple) else len(node.args) == arity
            if not ok:
                raise FormulaError(f"{node.func.id}() takes {arity if not isinstance(arity, tuple) else ' or '.join(map(str, arity))} argument(s).")
            continue
        raise FormulaError("This kind of expression is not allowed.")
    return tree


def _truth(v) -> np.ndarray:
    """A value as true / false: not zero and a number (a missing value is false)."""
    a = np.asarray(v, dtype=np.float64)
    return np.isfinite(a) & (a != 0)


def _missing(*vs) -> np.ndarray:
    """Where any of the values is missing (NaN)."""
    out = np.zeros((), dtype=bool)
    for v in vs:
        out = out | np.isnan(np.asarray(v, dtype=np.float64))
    return out


def evaluate(expr: str, signals: List[Tuple[np.ndarray, np.ndarray]], align,
             holds: Optional[Sequence[bool]] = None, nan: str = "propagate",
             report: Optional[Dict] = None) -> Tuple[np.ndarray, np.ndarray]:
    """signals: [(time, data)] for v0..vN. Returns (time, values) on v0's samples inside the common overlap.
    holds: per signal, True for a state signal - aligned with the value in force (C2), not by `align`.

    nan (C3): "propagate" (default) - a comparison, `not`, `where` with a missing value is missing, and
    `and` / `or` are missing unless the other side decides (false and ? = false, true or ? = true);
    integ() is unknown from a gap on. "skip": the same, but integ() bridges gaps. "legacy": the rules
    before 1.23 (a comparison with a missing value false, so `!=` true; integ() counts a gap as 0).
    report (optional): "infinite" - how many values were infinite (1/0...) and are now missing."""
    strict = nan != "legacy"
    if not signals:
        raise FormulaError("Use at least one signal in the formula.")
    tree = parse(expr, len(signals))
    t0 = np.asarray(signals[0][0], dtype=np.float64)
    lo = max(float(s[0][0]) for s in signals)
    hi = min(float(s[0][-1]) for s in signals)
    if hi <= lo:
        raise FormulaError("The signals in the formula do not overlap in time.")
    i0, i1 = np.searchsorted(t0, lo, "left"), np.searchsorted(t0, hi, "right")
    t = t0[i0:i1]
    env: Dict[str, object] = {"t": t, "pi": np.pi, "e": np.e}
    for k, (ts, ys) in enumerate(signals):
        held = holds is not None and k < len(holds) and holds[k]
        if k == 0:
            v0 = np.asarray(ys[i0:i1], dtype=np.float64)
            if held:                                       # a blank sample of a state: the last value holds
                from svcore.analysis import ffill_state
                v0 = ffill_state(np.asarray(ys, dtype=np.float64))[i0:i1]
            env["v0"] = v0
        elif held:
            from svcore.analysis import hold_to
            env[f"v{k}"] = hold_to(t, ts, ys)
        else:
            env[f"v{k}"] = align(t, ts, ys)
    funcs = _funcs(t, nan)

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name):
            return env[node.id] if node.id in env else None
        if isinstance(node, ast.UnaryOp):
            v = ev(node.operand)
            if isinstance(node.op, ast.Not):
                r = np.asarray(~_truth(v), dtype=np.float64)
                return np.where(_missing(v), np.nan, r) if strict else r
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BoolOp):
            vals = [ev(x) for x in node.values]
            parts = [_truth(v) for v in vals]
            out = parts[0]
            for p in parts[1:]:
                out = np.logical_and(out, p) if isinstance(node.op, ast.And) else np.logical_or(out, p)
            res = np.asarray(out, dtype=np.float64)
            if strict:                                   # Kleene: unknown unless a known side decides
                unknown = _missing(*vals)
                if isinstance(node.op, ast.And):
                    decided = np.zeros((), dtype=bool)
                    for v, p in zip(vals, parts):
                        decided = decided | (~_missing(v) & ~p)      # a known false
                else:
                    decided = np.zeros((), dtype=bool)
                    for p in parts:
                        decided = decided | p                        # a known true
                res = np.where(unknown & ~decided, np.nan, res)
            return res
        if isinstance(node, ast.BinOp):
            return _BIN[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.Compare):
            left = ev(node.left)
            out = None
            for op, comp in zip(node.ops, node.comparators):
                right = ev(comp)
                r = np.asarray(_CMP[type(op)](left, right), dtype=np.float64)
                if strict:
                    r = np.where(_missing(left, right), np.nan, r)
                out = r if out is None else (np.where(_missing(out, r), np.nan, np.logical_and(out, r)).astype(np.float64)
                                             if strict else np.logical_and(out, r))
                left = right
            return np.asarray(out, dtype=np.float64)
        if isinstance(node, ast.Call):
            return funcs[node.func.id][0](*[ev(a) for a in node.args])
        raise FormulaError("This kind of expression is not allowed.")

    with np.errstate(all="ignore"):
        r = ev(tree)
    r = np.broadcast_to(np.asarray(r, dtype=np.float64), t.shape).copy()
    inf = np.isinf(r)
    if inf.any() and report is not None:              # C3: not silent - the result says how many
        report["infinite"] = int(inf.sum())
    r[inf] = np.nan
    return t, r
