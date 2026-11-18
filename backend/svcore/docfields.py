"""RE1: the values written into a report's text - `{{ max(Roll) }}`, `{{ rms(Roll - RollDes, when="Auto") }}`,
`{{ peak = max(Roll) }}` then `{{ peak * 2 :.1f }}`.

The app turns the signal names into v0, v1... (frontend/src/formulaRefs.ts, the same resolver as formulas) and
sends each field as {expr, sources, conds, assign, fmt}. Here every value is computed on ALL the samples of the
signal (or of the time window / the condition's stretches) - never on what a plot draws. Parsed with an AST
whitelist, like svcore/formula.py: never eval.
"""
import ast
import math
from typing import Callable, Dict, List, Optional, Tuple, cast

import numpy as np

from svcore.ops import compute_signal_stats

Signal = Tuple[np.ndarray, np.ndarray]

# a statistic of a signal (or of a formula of signals): name -> what it takes from the samples
AGGREGATES = ("min", "max", "mean", "rms", "std", "range", "first", "final", "samples", "duration", "tmax", "tmin",
              "absmax", "integral")
# plain arithmetic on numbers (min / max of numbers too: max(a, b) without a signal)
MATH: Dict[str, Callable[..., float]] = {"abs": abs, "sqrt": math.sqrt, "round": round, "floor": math.floor, "ceil": math.ceil,
        "log10": math.log10, "log": math.log, "exp": math.exp}
CONDS = ("stretches", "holds")              # a condition: how many stretches / how long it holds (s)
CONSTS = {"pi": math.pi, "e": math.e}
_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b, ast.Mod: lambda a, b: a % b,
        ast.FloorDiv: lambda a, b: a // b}


class FieldError(ValueError):
    pass


class Context:
    """What a field may read: signals by id (time as shown, all samples), whether one is a state, and a
    condition's stretches in a file."""
    def __init__(self, signal: Callable[[str], Signal], is_state: Callable[[str], bool],
                 condition: Callable[[dict, str], dict], derive: Callable[[str, List[Signal], List[bool]], Signal],
                 runs: List[str]):
        self.signal, self.is_state, self.condition, self.derive, self.runs = signal, is_state, condition, derive, runs


def _vars_in(node: ast.AST) -> List[int]:
    return sorted({int(n.id[1:]) for n in ast.walk(node) if isinstance(n, ast.Name) and n.id[:1] == "v" and n.id[1:].isdigit()})


class _Renumber(ast.NodeTransformer):
    def __init__(self, order: List[int]):
        self.map = {k: i for i, k in enumerate(order)}

    def visit_Name(self, node: ast.Name):
        if node.id[:1] == "v" and node.id[1:].isdigit():
            return ast.copy_location(ast.Name(id="v%d" % self.map[int(node.id[1:])], ctx=ast.Load()), node)
        return node


def _number(v) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise FieldError("A time window is two numbers in seconds, e.g. max(Roll, 10, 60).")
    return float(v)


def format_value(v, fmt: str = "") -> str:
    """A number as a report shows it: the user's format (".2f", ",d", ".1%"), else about four significant digits
    without exponents for everyday sizes."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if fmt:
        try:
            return format(v, fmt)
        except (ValueError, TypeError):
            raise FieldError("The format :%s does not fit a number - e.g. :.2f (2 decimals) or :.3g." % fmt) from None
    if isinstance(v, (int, np.integer)) or (isinstance(v, float) and v.is_integer() and abs(v) < 1e15):
        i = int(v)
        return f"{i:,}" if abs(i) >= 10000 else str(i)
    f = float(v)
    if not math.isfinite(f):
        return "—"
    a = abs(f)
    if a >= 1e7 or a < 1e-4:
        return f"{f:.4g}"
    d = max(0, 3 - int(math.floor(math.log10(a))))
    s = f"{f:.{d}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _mask_of(t: np.ndarray, intervals: List[List[float]]) -> np.ndarray:
    """Samples inside the condition's stretches (ends included)."""
    m = np.zeros(len(t), dtype=bool)
    for a, b in intervals:
        i0, i1 = np.searchsorted(t, a, "left"), np.searchsorted(t, b, "right")
        m[i0:i1] = True
    return m


def _aggregate(name: str, t: np.ndarray, y: np.ndarray, t0: Optional[float], t1: Optional[float],
               mask: Optional[np.ndarray]):
    t = np.asarray(t, dtype=np.float64)
    st = compute_signal_stats(t, y, t0, t1, mask)
    if not st:
        raise FieldError("No samples there (the window or the condition leaves none).")
    if name in ("min", "max", "mean", "rms", "std", "samples", "duration"):
        return st[name]
    if name == "range":
        return st["peak_to_peak"]
    if name == "absmax":
        return st["abs_max"]
    # the rest needs the selected samples themselves
    i0 = 0 if t0 is None else int(np.searchsorted(t, t0, "left"))
    i1 = len(t) if t1 is None else int(np.searchsorted(t, t1, "right"))
    ts, ys = t[i0:i1], np.asarray(y[i0:i1], dtype=np.float64)
    keep = np.isfinite(ys) if mask is None else np.isfinite(ys) & mask[i0:i1]
    ts, ys = ts[keep], ys[keep]
    if name == "first":
        return float(ys[0])
    if name == "final":
        return float(ys[-1])
    if name == "tmax":
        return float(ts[int(np.argmax(ys))])
    if name == "tmin":
        return float(ts[int(np.argmin(ys))])
    if name == "integral":                    # over time, the stretches outside the selection count 0
        if len(ts) < 2:
            return 0.0
        dt = np.diff(ts)
        if mask is not None:                  # do not bridge from one stretch to the next
            idx = np.nonzero(keep)[0]
            dt = np.where(np.diff(idx) == 1, dt, 0.0)
        return float(np.sum(dt * (ys[1:] + ys[:-1]) / 2))
    raise FieldError("Unknown statistic %s." % name)


def evaluate_fields(fields: List[dict], ctx: Context) -> List[dict]:
    """Every field in the document's order (a variable is defined before it is used). Each answer is
    {text} (a defined variable shows nothing) or {error} - one bad field never stops the others."""
    env: Dict[str, float] = {}
    out = []
    for f in fields:
        try:
            v = _evaluate_one(f, ctx, env)
            if f.get("assign"):
                env[str(f["assign"])] = v
                out.append({"text": "", "value": v})
            else:
                out.append({"text": format_value(v, str(f.get("fmt") or "")), "value": v if isinstance(v, (int, float)) else None})
        except FieldError as e:
            out.append({"error": str(e)})
        except KeyError as e:
            out.append({"error": "%s is not open." % str(e).strip("'\"")})
        except (ZeroDivisionError, OverflowError, ValueError) as e:
            out.append({"error": str(e) or "The value cannot be computed."})
    return out


def _evaluate_one(f: dict, ctx: Context, env: Dict[str, float]):
    text = str(f.get("expr") or "").strip()
    if not text:
        raise FieldError("Write a value between {{ and }}, e.g. {{ max(Roll) }}.")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        raise FieldError("This value cannot be read: %s" % (f.get("text") or text)) from None
    sources: List[str] = list(f.get("sources") or [])
    conds: Dict[str, dict] = dict(f.get("conds") or {})

    def run_of(node: Optional[ast.AST]) -> str:
        ids = [sources[k] for k in _vars_in(node)] if node is not None else []
        rid = next((s.partition("/")[0] for s in ids if not s.startswith("derived/")), None)
        if rid:
            return rid
        data = [r for r in ctx.runs if r != "derived"]
        if len(data) == 1:
            return data[0]
        raise FieldError("More than one file is open - name a signal of the file, e.g. stretches(\"Auto\", Roll).")

    def window(args: List[ast.expr], kws: Dict[str, ast.expr]):
        t0 = t1 = None
        if len(args) == 3:
            t0, t1 = _number(ev(args[1])), _number(ev(args[2]))
        elif len(args) != 1:
            raise FieldError("A statistic takes a signal, and optionally a time window: max(Roll) or max(Roll, 10, 60).")
        return t0, t1

    def condition(name, rid: str) -> dict:
        if not isinstance(name, str):
            raise FieldError('A condition is named in quotes: when="Auto".')
        c = conds.get(name)
        if c is None:
            raise FieldError('There is no condition named "%s" (Investigate panel).' % name)
        if c.get("error"):
            raise FieldError(str(c["error"]))
        r = ctx.condition(c, rid)
        if r.get("missing"):
            raise FieldError('The condition "%s" reads %s, not in this file.' % (name, ", ".join(r["missing"])))
        if r.get("error"):
            raise FieldError(str(r["error"]))
        if r.get("cut"):
            raise FieldError('The condition "%s" has more stretches than can be counted here.' % name)
        return r

    def series(node: ast.AST) -> Tuple[Signal, str]:
        ks = _vars_in(node)
        if not ks:
            raise FieldError("A statistic needs a signal, e.g. max(Roll).")
        ids = [sources[k] for k in ks]
        if isinstance(node, ast.Name):                    # one signal: its own samples, untouched
            return ctx.signal(ids[0]), ids[0]
        local = _Renumber(ks).visit(ast.fix_missing_locations(ast.Expression(body=cast(ast.expr, node))))
        sigs = [ctx.signal(i) for i in ids]
        return ctx.derive(ast.unparse(local), sigs, [ctx.is_state(i) for i in ids]), ids[0]

    def ev(node: ast.AST):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float, str)) and not isinstance(node.value, bool):
                return node.value
            raise FieldError("Only numbers and quoted names are allowed.")
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            if node.id in CONSTS:
                return CONSTS[node.id]
            if node.id[:1] == "v" and node.id[1:].isdigit():
                raise FieldError("A signal gives many values - take one: max(%s), mean(...), final(...)."
                                 % (f.get("names") or {}).get(node.id, "signal"))
            raise FieldError('"%s" is not a defined value. Define it first: {{ %s = max(Roll) }}.' % (node.id, node.id))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else +v
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            return _BIN[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fn = node.func.id
            kws = {k.arg: k.value for k in node.keywords if k.arg}
            unknown = set(kws) - {"when"}
            if unknown:
                raise FieldError("Unknown option %s= (only when=\"<condition>\")." % sorted(unknown)[0])
            if fn in AGGREGATES and node.args and _vars_in(node.args[0]):
                (t, y), sid = series(node.args[0])
                t0, t1 = window(node.args, kws)
                mask = None
                if "when" in kws:
                    r = condition(ev(kws["when"]), run_of(node.args[0]))
                    mask = _mask_of(np.asarray(t, dtype=np.float64), r.get("intervals") or [])
                return _aggregate(fn, t, y, t0, t1, mask)
            if fn in CONDS:
                if not node.args:
                    raise FieldError('Name the condition: %s("Auto").' % fn)
                r = condition(ev(node.args[0]), run_of(node.args[1] if len(node.args) > 1 else None))
                return int(r.get("count", 0)) if fn == "stretches" else float(r.get("total", 0.0))
            if kws:
                raise FieldError("when= goes with a statistic of a signal, e.g. mean(Speed, when=\"Auto\").")
            if fn in ("min", "max") and node.args:
                return (min if fn == "min" else max)(ev(a) for a in node.args)
            if fn in MATH:
                return MATH[fn](*[ev(a) for a in node.args])
            if fn in AGGREGATES:
                raise FieldError("%s(...) needs a signal, e.g. %s(Roll)." % (fn, fn))
            raise FieldError("Unknown function %s(). Statistics: %s." % (fn, ", ".join(AGGREGATES)))
        raise FieldError("This kind of expression is not allowed in a report value.")

    with np.errstate(all="ignore"):
        v = ev(tree)
    if isinstance(v, (np.floating, np.integer)):
        v = v.item()
    return v
