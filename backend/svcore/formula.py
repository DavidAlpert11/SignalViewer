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
"""

import ast
from typing import Dict, List, Tuple

import numpy as np

from svcore.ops import FilterError, apply_filter, cumulative_trapezoid, moving_average


class FormulaError(ValueError):
    pass


_BIN = {ast.Add: np.add, ast.Sub: np.subtract, ast.Mult: np.multiply, ast.Div: np.divide,
        ast.Pow: np.power, ast.Mod: np.mod}
_CMP = {ast.Gt: np.greater, ast.Lt: np.less, ast.GtE: np.greater_equal, ast.LtE: np.less_equal,
        ast.Eq: np.equal, ast.NotEq: np.not_equal}


def _funcs(t: np.ndarray):
    def deriv(x):
        x = np.broadcast_to(np.asarray(x, dtype=np.float64), t.shape)
        with np.errstate(divide="ignore", invalid="ignore"):
            r = np.gradient(x, t)
        r[~np.isfinite(r)] = np.nan
        return r

    def integ(x):
        return cumulative_trapezoid(t, np.broadcast_to(np.asarray(x, dtype=np.float64), t.shape))

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
        "clip": (np.clip, 3), "where": (lambda c, a, b: np.where(np.asarray(c) != 0, a, b), 3),
        "deriv": (deriv, 1), "integ": (integ, 1), "smooth": (smooth, (1, 2)),
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


def evaluate(expr: str, signals: List[Tuple[np.ndarray, np.ndarray]], align) -> Tuple[np.ndarray, np.ndarray]:
    """signals: [(time, data)] for v0..vN. Returns (time, values) on v0's samples inside the common overlap."""
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
        env[f"v{k}"] = np.asarray(ys[i0:i1], dtype=np.float64) if k == 0 else align(t, ts, ys)
    funcs = _funcs(t)

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
                return np.asarray(~_truth(v), dtype=np.float64)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BoolOp):
            parts = [_truth(ev(x)) for x in node.values]
            out = parts[0]
            for p in parts[1:]:
                out = np.logical_and(out, p) if isinstance(node.op, ast.And) else np.logical_or(out, p)
            return np.asarray(out, dtype=np.float64)
        if isinstance(node, ast.BinOp):
            return _BIN[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.Compare):
            left = ev(node.left)
            out = None
            for op, comp in zip(node.ops, node.comparators):
                right = ev(comp)
                r = _CMP[type(op)](left, right)
                out = r if out is None else np.logical_and(out, r)
                left = right
            return np.asarray(out, dtype=np.float64)
        if isinstance(node, ast.Call):
            return funcs[node.func.id][0](*[ev(a) for a in node.args])
        raise FormulaError("This kind of expression is not allowed.")

    with np.errstate(all="ignore"):
        r = ev(tree)
    r = np.broadcast_to(np.asarray(r, dtype=np.float64), t.shape).copy()
    r[~np.isfinite(r)] = np.nan
    return t, r
