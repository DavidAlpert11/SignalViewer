"""Named conditions (investigation spec, step 2): the stretches of a file where an expression holds.

A condition is written like a formula, with the file's signals by name - `{Speed} > 12`,
`abs({Vz}) > 5 and {Mode} == "AUTO"` - and evaluated in every open file that has those signals,
so the same condition marks the same kind of moment in each run. Options:
  exit      another expression that ends a stretch (hysteresis: in above 1950, out below 1900);
  min_dur   stretches shorter than this (s) are left out;
  merge_gap stretches closer than this (s) are joined.
A stretch runs from the first sample where the condition holds to the first one where it no
longer does (the last sample of the file at the end).
"""
import re
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from svcore.formula import FUNCTION_NAMES, FormulaError, evaluate

Signal = Tuple[np.ndarray, np.ndarray]
# {any text}  or  a bare name (letters incl. Hebrew, digits, _ . [ ]) - as in the app's formulas
_TOKEN = re.compile(r'\{([^}]+)\}|([A-Za-z_\u0590-\u05FF][\w.\u0590-\u05FF\[\]]*)')
_KEEP = {"t", "pi", "e", "and", "or", "not"}
# {Mode} == "AUTO": a state's text compared - turned into its code in each file
_TEXT_CMP = re.compile(r'(\{[^}]+\}|[A-Za-z_\u0590-\u05FF][\w.\u0590-\u05FF\[\]]*)\s*(==|!=)\s*"([^"]*)"')
MAX_STRETCHES = 5000


class ConditionError(ValueError):
    pass


def names_in(text: str) -> List[str]:
    """The signal names a condition reads, in order."""
    out: List[str] = []
    for m in _TOKEN.finditer(_TEXT_CMP.sub(lambda mm: f"{mm.group(1)} {mm.group(2)} 0", text)):
        braced, bare = m.group(1), m.group(2)
        if bare:
            after = text[m.end():].lstrip()
            if bare in _KEEP or (after.startswith("(") and bare in FUNCTION_NAMES):
                continue
        nm = (braced or bare or "").strip()
        if nm and nm not in out:
            out.append(nm)
    return out


def resolve(text: str, labels: Callable[[str], Optional[Dict[str, str]]]) -> Tuple[str, List[str]]:
    """The condition as a formula of v0, v1... and the names in that order. `labels(name)` gives a
    state's texts (code -> text), for `{Mode} == "AUTO"`."""
    def text_code(m):
        nm = m.group(1).strip("{}").strip()
        lab = labels(nm) or {}
        hit = [k for k, v in lab.items() if v == m.group(3)] or [k for k, v in lab.items() if v.lower() == m.group(3).lower()]
        if not hit:
            raise ConditionError(f'{nm} has no state "{m.group(3)}" in this file.')
        return f"{m.group(1)} {m.group(2)} {hit[0]}"
    body = _TEXT_CMP.sub(text_code, text)
    names: List[str] = []

    def sub(m):
        braced, bare = m.group(1), m.group(2)
        if bare:
            after = body[m.end():].lstrip()
            if bare in _KEEP or (after.startswith("(") and bare in FUNCTION_NAMES):
                return m.group(0)
        nm = (braced or bare or "").strip()
        if nm not in names:
            names.append(nm)
        return f"v{names.index(nm)}"
    return _TOKEN.sub(sub, body), names


def stretches(t: np.ndarray, on: np.ndarray, off: Optional[np.ndarray] = None,
              min_dur: float = 0.0, merge_gap: float = 0.0) -> List[Tuple[float, float]]:
    """[(start, end)] where `on` holds - or, with `off`, from where `on` holds until `off` does."""
    t = np.asarray(t, dtype=np.float64)
    n = len(t)
    if n == 0:
        return []
    on = np.asarray(on, dtype=bool)
    end_t = lambda j: float(t[j]) if j < n else float(t[-1])         # noqa: E731
    out: List[Tuple[float, float]] = []
    if off is None:
        d = np.diff(np.r_[False, on, False].astype(np.int8))
        starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
        out = [(float(t[a]), end_t(b)) for a, b in zip(starts, ends)]
    else:
        on_i = np.flatnonzero(on)
        off_i = np.flatnonzero(np.asarray(off, dtype=bool))
        k = 0
        while k < len(on_i):
            a = int(on_i[k])
            j = np.searchsorted(off_i, a, "right")
            b = int(off_i[j]) if j < len(off_i) else n
            out.append((float(t[a]), end_t(b)))
            k = int(np.searchsorted(on_i, b, "left")) if b < n else len(on_i)
    if merge_gap > 0 and out:
        joined: List[Tuple[float, float]] = [out[0]]
        for sa, sb in out[1:]:
            if sa - joined[-1][1] <= merge_gap:
                joined[-1] = (joined[-1][0], sb)
            else:
                joined.append((sa, sb))
        out = joined
    if min_dur > 0:
        out = [(sa, sb) for sa, sb in out if sb - sa >= min_dur]
    return out


def evaluate_condition(text: str, read: Callable[[str], Optional[Signal]],
                       labels: Callable[[str], Optional[Dict[str, str]]], align,
                       exit_text: str = "", min_dur: float = 0.0, merge_gap: float = 0.0) -> dict:
    """The condition in one file. `read(name)` -> (time, data) as shown (None: not in this file)."""
    expr, names = resolve(text, labels)
    missing = [n for n in names if read(n) is None]
    if missing:
        return {"missing": missing}
    sigs: List[Signal] = [x for x in (read(n) for n in names) if x is not None]
    try:
        t, v = evaluate(expr, sigs, align)
        off = None
        if exit_text.strip():
            x_expr, x_names = resolve(exit_text, labels)
            x_missing = [n for n in x_names if read(n) is None]
            if x_missing:
                return {"missing": x_missing}
            xt, xv = evaluate(x_expr, [x for x in (read(n) for n in x_names) if x is not None], align)
            off = align(t, xt, xv) > 0.5 if len(xt) else np.zeros(len(t), bool)
    except FormulaError as e:
        raise ConditionError(str(e)) from None
    on = np.isfinite(v) & (v != 0)
    iv = stretches(t, on, off, float(min_dur or 0), float(merge_gap or 0))
    ranges = {}
    for n, (_ts, ys) in zip(names, sigs):
        y = np.asarray(ys, dtype=np.float64)
        y = y[np.isfinite(y)]
        if len(y):
            ranges[n] = [float(y.min()), float(y.max())]
    return {"intervals": [list(x) for x in iv[:MAX_STRETCHES]], "count": len(iv),
            "total": float(sum(b - a for a, b in iv)), "ranges": ranges, "cut": len(iv) > MAX_STRETCHES}
