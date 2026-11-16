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
import re
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
            # 26.A3: in time (gaps, rate changes); a formula or a change saved before 1.23 ("legacy"):
            # on the samples, as it was
            return apply_filter(t, np.broadcast_to(np.asarray(x, dtype=np.float64), t.shape), kind, float(fc),
                                sampling="samples" if nan == "legacy" else "time")
        except FilterError as e:
            raise FormulaError(f"{kind}(): {e}") from None

    def lowpass(x, fc):
        return _filter(x, fc, "lowpass")

    def highpass(x, fc):
        return _filter(x, fc, "highpass")

    def smooth(x, n=10):
        return moving_average(np.broadcast_to(np.asarray(x, dtype=np.float64), t.shape), int(n))

    def smooth_s(x, seconds):
        """26.A3: a centred average over `seconds` (any sample rate; never across a gap)."""
        if not float(seconds) > 0:
            raise FormulaError("smooth_s(): the window must be above 0 s.")
        from svcore.analysis import time_moving_average     # (analysis imports this module)
        return time_moving_average(t, np.broadcast_to(np.asarray(x, dtype=np.float64), t.shape), float(seconds))

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
        "deriv": (deriv, (1, 2)), "integ": (integ, (1, 2)), "smooth": (smooth, (1, 2)), "smooth_s": (smooth_s, 2),
        "lowpass": (lowpass, 2), "highpass": (highpass, 2), "norm01": (norm01, 1),
    }


FUNCTION_NAMES = sorted(_funcs(np.zeros(1)).keys())


def _syntax_message(expr: str, e: SyntaxError) -> str:
    """RV11 (review B8): where the formula is wrong, as the user wrote it - the end ("x1 +": something missing) or the
    character (1-based) with the text up to it. Python's offset is 0 / past the end when the input ends too early."""
    text = expr.rstrip()
    off = e.offset or 0
    if off <= 0 or off > len(text) or "EOF" in (e.msg or "") or "never closed" in (e.msg or ""):
        tail = text[-20:]
        return f"The formula ends too early: something is missing after '{tail}' (a value, or a closing bracket)."
    before = expr[max(0, off - 20):off]
    return f"Syntax error at character {off}: '{before}' <- check what is just before here."


def syntax_message_for(text: str) -> Optional[str]:
    """The syntax message for the formula as the user typed it ({Signal name} and ^ kept in place, same length), or
    None when that text parses - so a position and a quote point into what is on the screen, not the rewritten form."""
    import re
    probe = re.sub(r"\{[^}]*\}", lambda m: "x" * len(m.group(0)), text).replace("^", "*")
    try:
        ast.parse(probe, mode="eval")
    except SyntaxError as e:
        return _syntax_message(text, e)
    return None


def _unknown_function(fn: ast.expr, funcs: dict) -> str:
    """RV11 (review B8): an unknown function by its name, with the closest known one."""
    import difflib
    if not isinstance(fn, ast.Name):
        return "Only a function's name can be called, e.g. sqrt(x)."
    near = difflib.get_close_matches(fn.id, list(funcs), n=1, cutoff=0.6)
    return f"Unknown function: {fn.id}()" + (f" - did you mean {near[0]}()?" if near else ". Use one of the listed functions.")


# ------------------------------------------------------------------ the one whitelist (FR7)
# Every formula of the app - a signal's (here), a Sweeps column's and a study's constraints (svcore/sweep/derived.py,
# svcore/sweeps_common.py) - is parsed and checked here; the others import it and only give values to what passed.

#: the functions of a Sweeps row formula (implemented in svcore/sweep/derived.py): numbers, and the conditions and
#: text of S1 - if (written `if(`, a keyword: read as `_if(`), where (if's older name), between, contains, text,
#: bins, rank, pct; col("a name with spaces") names a column.
ROW_FUNCTIONS = ("abs", "sqrt", "exp", "log", "log10", "sin", "cos", "tan", "atan2", "sign", "floor", "ceil", "round",
                 "min", "max", "clip", "isnan", "if", "where", "between", "contains", "text", "bins", "rank", "pct")
ROW_CONSTANTS = ("pi", "e", "nan", "inf", "True", "False")
_ROW_CALLS = frozenset(ROW_FUNCTIONS) - {"if"} | {"_if", "col"}
_STRINGS = re.compile(r"(\"[^\"]*\"|'[^']*')")


def _dunder(name: str) -> bool:
    return name.startswith("__") or name.endswith("__")


def check(tree: ast.AST, *, rows: bool, names: Optional[set] = None, funcs: Optional[dict] = None) -> None:
    """The whitelist. Raises FormulaError for anything else - attributes, subscripts, lambdas, keyword arguments,
    any name with __ - whichever formula it is.
    rows=False (a signal formula): the names v0..vN, t, pi, e (`names`) and `funcs` with their arity.
    rows=True (a Sweeps row formula): any other name is a column; text in quotes; x in (a, b); lists for in / bins."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and _dunder(node.id):
            raise FormulaError(f"Names with __ are not allowed: {node.id}")
        if isinstance(node, (ast.Expression, ast.Load, ast.operator, ast.unaryop, ast.cmpop)):
            if isinstance(node, ast.operator) and type(node) not in _BIN:
                raise FormulaError("Only + - * / ** % are allowed.")
            if isinstance(node, ast.unaryop) and not isinstance(node, (ast.USub, ast.UAdd, ast.Not)):
                raise FormulaError("Only unary minus is allowed.")
            if isinstance(node, ast.cmpop) and type(node) not in _CMP and not (rows and isinstance(node, (ast.In, ast.NotIn))):
                raise FormulaError("Unsupported comparison.")
            continue
        if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Compare)):
            continue
        # conditions (svcore/conditions.py): a and b, a or b, not a - element by element
        if isinstance(node, (ast.BoolOp, ast.And, ast.Or, ast.Not)):
            continue
        if isinstance(node, ast.Constant):
            if rows and isinstance(node.value, str):
                continue
            if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
                raise FormulaError("Only numbers are allowed as constants." if not rows else "Only numbers and \"text\" are allowed as values.")
            continue
        if isinstance(node, ast.Name):
            if rows:
                continue                                           # a column (or a constant): its value is the table's
            if node.id not in (names or set()) and node.id not in (funcs or {}):
                raise FormulaError(f"Unknown name: {node.id}")
            continue
        if rows and isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            continue                                               # x in (1, 2), bins(x, [0, 5, 10])
        if isinstance(node, ast.Call):
            known = _ROW_CALLS if rows else (funcs or {})
            if not isinstance(node.func, ast.Name) or node.func.id not in known:
                if rows and isinstance(node.func, ast.Name):
                    raise FormulaError(f"Unknown function: {'if' if node.func.id == '_if' else node.func.id}")
                raise FormulaError(_unknown_function(node.func, dict.fromkeys(known)))
            if node.keywords:
                raise FormulaError("Functions take positional arguments only.")
            if not rows and funcs is not None:
                arity = funcs[node.func.id][1]
                ok = len(node.args) in arity if isinstance(arity, tuple) else len(node.args) == arity
                if not ok:
                    raise FormulaError(f"{node.func.id}() takes {arity if not isinstance(arity, tuple) else ' or '.join(map(str, arity))} argument(s).")
            continue
        raise FormulaError("This kind of expression is not allowed.")


def parse(expr: str, n_vars: int) -> ast.Expression:
    """Parse and validate a signal formula; raises FormulaError with a readable message."""
    if not expr or not expr.strip():
        raise FormulaError("The formula is empty.")
    if len(expr) > 2000:
        raise FormulaError("The formula is too long.")
    try:
        tree = ast.parse(expr.replace("^", "**"), mode="eval")
    except SyntaxError as e:
        raise FormulaError(_syntax_message(expr, e)) from None
    check(tree, rows=False, names={f"v{i}" for i in range(n_vars)} | {"t", "pi", "e"}, funcs=_funcs(np.zeros(1)))
    return tree


def _if_calls(expr: str) -> str:
    """`if(` is a Python keyword: written as the function `_if(` (outside quoted text)."""
    parts = _STRINGS.split(expr)
    return "".join(p if i % 2 else re.sub(r"\bif\s*\(", "_if(", p) for i, p in enumerate(parts))


def parse_rows(expr: str) -> ast.Expression:
    """Parse and validate a Sweeps row formula (a column, a constraint, an objective) through the whitelist."""
    if not expr or not expr.strip():
        raise FormulaError("it is empty")
    if len(expr) > 2000:
        raise FormulaError("The formula is too long.")
    try:
        tree = ast.parse(_if_calls(expr.strip()), mode="eval")
    except SyntaxError as e:
        raise FormulaError(e.msg) from None
    check(tree, rows=True)
    return tree


def split_and(expr: str) -> List[str]:
    """A row condition split at its top-level `and` (each part reported on its own), checked by the whitelist."""
    body = parse_rows(expr).body
    if isinstance(body, ast.BoolOp) and isinstance(body.op, ast.And):
        return [ast.unparse(v) for v in body.values]
    return [expr.strip()]


def margin_of(part: str) -> Optional[str]:
    """For `a < b` / `a > b` (and <=, >=): an expression whose positive value is by how much it is broken."""
    body = parse_rows(part).body
    if isinstance(body, ast.Compare) and len(body.ops) == 1:
        lhs, rhs = ast.unparse(body.left), ast.unparse(body.comparators[0])
        if isinstance(body.ops[0], (ast.Lt, ast.LtE)):
            return f"({lhs}) - ({rhs})"
        if isinstance(body.ops[0], (ast.Gt, ast.GtE)):
            return f"({rhs}) - ({lhs})"
    return None


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


def bool_op(parts: Sequence[np.ndarray], missing: Optional[Sequence[np.ndarray]], is_and: bool) -> np.ndarray:
    """and / or of truth arrays (1.0 / 0.0). With `missing` (one mask per part) it is Kleene's: unknown (NaN) unless
    a known side decides - a known false for and, a true for or. Shared by the signal formulas and the Sweeps columns."""
    out = parts[0]
    for p in parts[1:]:
        out = (out & p) if is_and else (out | p)
    res = np.asarray(out, dtype=np.float64)
    if missing is None:
        return res
    unknown = np.zeros((), dtype=bool)
    decided = np.zeros((), dtype=bool)
    for p, m in zip(parts, missing):
        unknown = unknown | m
        decided = decided | ((~m & ~p) if is_and else p)
    return np.where(unknown & ~decided, np.nan, res)


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
            return bool_op([_truth(v) for v in vals], [_missing(v) for v in vals] if strict else None, isinstance(node.op, ast.And))
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
