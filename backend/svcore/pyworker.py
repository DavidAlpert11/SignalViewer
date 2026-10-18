"""T31: the worker process that runs the user's own Python operations.

Only .py files in the folder the user chose are loaded (never code from a session or a template);
they run HERE, in a separate process, so a bug, a crash or an endless loop in them cannot take the
app down - the server kills and restarts this process (app/pyops.py).

A file declares operations with the `operation` decorator (available without an import):

    @operation(name="Despike", params={"limit": 3.0})
    def despike(t, y, limit=3.0):
        ...
        return y                # same length as t - or (t2, y2) for a new time base

    @operation(name="Scaled difference", inputs=2, params={"k": 1.0})
    def scaled_diff(t, a, b, k=1.0):     # b is aligned onto a's time (linear)
        return (a - b) * k

Protocol on the pipe: ("list",) -> {"ops": [...], "errors": [...]};
("run", op_id, [(t, y), ...], args) -> ("ok", t, y) | ("err", message)."""
import importlib.util
import inspect
import os
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

MARK = "_sv_operation"


def operation(name: Any = None, inputs: int = 1, params: Optional[Dict[str, Any]] = None, doc: Optional[str] = None):
    """Mark a function as an operation the app lists. Also usable bare: @operation."""
    def wrap(f: Callable) -> Callable:
        setattr(f, MARK, {"name": name if isinstance(name, str) and name else f.__name__.replace("_", " ").capitalize(),
                          "inputs": max(1, int(inputs)), "params": dict(params or {}),
                          "doc": (doc or inspect.getdoc(f) or "").strip()})
        return f
    if callable(name):                    # @operation without arguments
        f, name = name, None
        return wrap(f)
    return wrap


def load(folder: str) -> Tuple[Dict[str, Callable], List[Dict[str, str]]]:
    """Every operation in the folder's .py files ("file.py:function" -> function), and the files
    that could not be loaded with the reason. One broken file does not hide the others."""
    ops: Dict[str, Callable] = {}
    errors: List[Dict[str, str]] = []
    if not os.path.isdir(folder):
        return ops, errors
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith(".py") or fn.startswith((".", "_")):
            continue
        path = os.path.join(folder, fn)
        try:
            spec = importlib.util.spec_from_file_location(f"sv_user_ops_{len(ops)}_{fn[:-3]}", path)
            if spec is None or spec.loader is None:
                raise ImportError("not a Python module")
            mod = importlib.util.module_from_spec(spec)
            mod.operation = operation      # type: ignore[attr-defined]   # usable without an import
            spec.loader.exec_module(mod)
        except Exception as e:
            errors.append({"file": fn, "error": _short(e, path)})
            continue
        for attr, f in vars(mod).items():
            if callable(f) and hasattr(f, MARK) and getattr(f, "__module__", None) == mod.__name__:
                ops[f"{fn}:{attr}"] = f
    return ops, errors


def _short(e: BaseException, path: Optional[str] = None) -> str:
    """'ValueError: bad input (my_ops.py line 12)' - the user's own line, not the app's."""
    where = ""
    for fr in reversed(traceback.extract_tb(e.__traceback__) if path else []):
        if os.path.abspath(fr.filename) == os.path.abspath(path or ""):
            where = f" ({os.path.basename(fr.filename)} line {fr.lineno})"
            break
    if isinstance(e, SyntaxError) and e.lineno:     # its str() already carries "(file, line n)"
        return f"{type(e).__name__}: {e.msg} ({os.path.basename(e.filename or path or '')} line {e.lineno})"
    return f"{type(e).__name__}: {e}{where}"


def describe(ops: Dict[str, Callable]) -> List[Dict[str, Any]]:
    out = []
    for op_id, f in ops.items():
        meta = getattr(f, MARK)
        out.append({"id": op_id, "name": meta["name"], "inputs": meta["inputs"], "doc": meta["doc"],
                    "params": {k: v for k, v in meta["params"].items() if isinstance(v, (int, float, str, bool))}})
    return out


def _coerce(value: Any, default: Any) -> Any:
    """A parameter from the UI in the type of its default (the UI sends numbers / text)."""
    try:
        if isinstance(default, bool):
            return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "on")
        if isinstance(default, int):
            return int(float(value))
        if isinstance(default, float):
            return float(value)
        if isinstance(default, str):
            return str(value)
    except (TypeError, ValueError):
        raise ValueError(f"parameter value {value!r} is not a {type(default).__name__}") from None
    return value


def run(ops: Dict[str, Callable], op_id: str, signals: List[Tuple[np.ndarray, np.ndarray]],
        args: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    f = ops.get(op_id)
    if f is None:
        raise LookupError(f"The Python operation {op_id} is not in your operations folder "
                          "(Create signals > Python shows the folder).")
    meta = getattr(f, MARK)
    if len(signals) != meta["inputs"]:
        raise ValueError(f"{meta['name']} needs {meta['inputs']} signal(s), got {len(signals)}.")
    t = np.asarray(signals[0][0], dtype=np.float64)
    ys = [np.asarray(signals[0][1], dtype=np.float64)]
    for ts, y in signals[1:]:            # the other inputs on the first one's time
        ys.append(np.interp(t, np.asarray(ts, dtype=np.float64), np.asarray(y, dtype=np.float64),
                            left=np.nan, right=np.nan))
    kwargs = {k: _coerce(args.get(k, d), d) for k, d in meta["params"].items()}
    res = f(t.copy(), *[y.copy() for y in ys], **kwargs)
    if isinstance(res, tuple) and len(res) == 2:
        t2, y2 = res
    else:
        t2, y2 = t, res
    t2 = np.asarray(t2, dtype=np.float64).ravel()
    y2 = np.asarray(y2, dtype=np.float64).ravel()
    if len(t2) != len(y2) or not len(y2):
        raise ValueError(f"{meta['name']} returned {len(y2)} values for {len(t2)} times "
                         "(return y with one value per time, or (t, y)).")
    return t2, y2


def main(conn, folder: str) -> None:
    """The worker's loop (multiprocessing target)."""
    ops, errors = load(folder)
    while True:
        try:
            msg = conn.recv()
        except (EOFError, OSError):
            return                         # the app went away
        try:
            if msg[0] == "list":
                conn.send({"ops": describe(ops), "errors": errors})
            elif msg[0] == "run":
                _, op_id, signals, args = msg
                try:
                    t, y = run(ops, op_id, signals, args or {})
                    conn.send(("ok", t, y))
                except Exception as e:
                    path = getattr(ops.get(op_id), "__globals__", {}).get("__file__")   # the user's file
                    conn.send(("err", f"{op_id}: {_short(e, path)}"))
            else:
                conn.send(("err", f"unknown request {msg[0]!r}"))
        except (BrokenPipeError, OSError):
            return
