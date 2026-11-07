"""
Changes made ON a signal (not new signals): scale, offset, a time shift and an expression in x (and
t, and Q89 / Q90 other signals written {Name} or {@<run id>:Name}) - applied every time the signal
is read. A1 (2026-11-07): moved out of app/store.py, which still exports these names.
"""
import re
from typing import List, Optional

import numpy as np

from svcore.analysis import OpError
from svcore.formula import evaluate as _evaluate_formula


def normalize_transform(spec: Optional[dict]) -> Optional[dict]:
    """Keep only meaningful parts; an all-default transform is no transform."""
    if not spec:
        return None
    out: dict = {}
    expr = str(spec.get("expr") or "").strip()
    if expr and expr != "x":
        out["expr"] = expr
    for k, default in (("scale", 1.0), ("offset", 0.0), ("dt", 0.0)):
        v = spec.get(k)
        if v is not None and v != "" and float(v) != default:
            out[k] = float(v)
    # the unit shown after a unit conversion ("deg" for a signal logged in rad): a label only
    unit = " ".join(str(spec.get("unit") or "").split())[:24]
    if unit:
        out["unit"] = unit
    return out or None


REF = re.compile(r"\{([^{}]+)\}")


def transform_refs(spec: Optional[dict]) -> List[str]:
    """Q89: the other signals an edit's expression reads - {Name}: of the same file; Q90:
    {@<run id>:Name}: of that one file (the interface shows it as {file:Name})."""
    out: List[str] = []
    for m in REF.finditer(str((spec or {}).get("expr") or "")):
        name = m.group(1).strip()
        if name not in out:
            out.append(name)
    return out


def ref_run(token: str) -> Optional[str]:
    """The file a reference names ({@<run id>:Name}), or None for the edited signal's own file."""
    if token.startswith("@") and ":" in token:
        return token[1:token.index(":")]
    return None


def apply_transform(t, y, spec: dict, ref=None):
    """y' = scale * f(x) + offset, t' = t + dt;  f is an expression in x (and t) and, Q89, of other
    signals of the same file written {Name}: `ref(name)` gives their (time, data) as read from the
    file (before any edit - so a group changed together sees the same values, and no edit can depend
    on another in a circle). They are interpolated onto x's time."""
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if spec.get("expr"):
        names = transform_refs(spec)
        sources = [(t, y)]
        for name in names:
            if ref is None:
                raise OpError(f"{name}: another signal can not be used here.")
            got = ref(name)
            if got is None:
                shown = name[name.index(":") + 1:] if name.startswith("@") and ":" in name else name
                raise OpError(f"{shown} is not a signal of this file." if not name.startswith("@")
                              else f"{shown}: its file is not open.")
            sources.append((np.asarray(got[0], dtype=np.float64), np.asarray(got[1], dtype=np.float64)))
        # {Name} first (a name may hold an x), then x itself
        expr = REF.sub(lambda m: f"v{names.index(m.group(1).strip()) + 1}", spec["expr"])
        expr = re.sub(r"\bx\b", "v0", expr)
        try:
            t2, y = _evaluate_formula(expr, sources, lambda tt, ts, ys: np.interp(tt, ts, ys))
        except ValueError as e:
            raise OpError(str(e)) from None
        t = t2
    if "scale" in spec or "offset" in spec:
        y = y * spec.get("scale", 1.0) + spec.get("offset", 0.0)
    if spec.get("dt"):
        t = t + spec["dt"]
    return t, y
