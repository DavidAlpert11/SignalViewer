"""Groups of parameter sets (MF00) - the unit every Sweeps tool reads and writes.

A group is a named set of parameter sets, either

* a **rule** - the same filters the page puts on its axes (``{column: {"kind": "ranges",
  "ranges": [[a, b], ...]}}`` or ``{"kind": "values", "values": [...]}``): live, it follows new
  results; or
* **frozen ids** - the sets' ids (see :func:`set_ids`): fixed, whatever comes in later.

Automatic groups (all, holds, Pareto, fails, error, suggested) are computed from the answer and
never saved. User groups live in the study (``view.groups`` in .svsweep, optional: an old study
opens with the automatic groups only).

A set's id is its parameter values, so it stays the same when the table is merged, re-sorted or
re-run: ``"p=2|k=0.1"`` - each parameter as ``name=value`` in the order given, numbers in their
shortest exact form, a missing value as empty.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np

SOURCES = ("auto", "user", "doe", "virtual", "cluster", "rerun")
AUTO = ("all", "holds", "pareto", "fails", "error", "suggested")


class GroupError(ValueError):
    """A group that cannot be used (an unknown source, a rule on no column, nothing to keep)."""


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (float, np.floating)):
        f = float(v)
        if math.isnan(f):
            return ""
        if f.is_integer():
            return str(int(f))
        return repr(f)
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    return str(v)


def set_id(params: Mapping[str, Any], order: Sequence[str]) -> str:
    """The id of one parameter set: its values, in the parameters' order."""
    return "|".join(f"{p}={_fmt(params.get(p))}" for p in order)


def set_ids(columns: Mapping[str, Sequence[Any]], order: Sequence[str]) -> List[str]:
    """The ids of every set, from its parameter columns (one value per set)."""
    if not order:
        return []
    n = len(columns[order[0]])
    return ["|".join(f"{p}={_fmt(columns[p][i])}" for p in order) for i in range(n)]


def _keeps(f: Mapping[str, Any], v: np.ndarray) -> np.ndarray:
    kind = f.get("kind")
    finite = np.isfinite(v)
    if kind == "values":
        # the page holds values as Float32 (its rule's values came from there): compare as Float32
        want = np.asarray(f.get("values", []), dtype=np.float32)
        return finite & np.isin(v.astype(np.float32), want)
    if kind == "ranges":
        m = np.zeros(v.shape, dtype=bool)
        for a, b in f.get("ranges", []):
            lo, hi = min(a, b), max(a, b)
            m |= (v >= lo) & (v <= hi)
        return finite & m
    raise GroupError(f"unknown filter kind {kind!r}")


def rule_mask(columns: Mapping[str, np.ndarray], rule: Mapping[str, Mapping[str, Any]], n: int) -> np.ndarray:
    """The sets a rule keeps: inside every filtered column (as the page's axes do). A filter on a
    column the answer no longer has is ignored, like on the page."""
    m = np.ones(n, dtype=bool)
    for name, f in rule.items():
        c = columns.get(name)
        if c is None:
            continue
        m &= _keeps(f, np.asarray(c, dtype=float))
    return m


def ids_mask(ids: Sequence[str], members: Iterable[str]) -> np.ndarray:
    want = set(members)
    return np.fromiter((i in want for i in ids), dtype=bool, count=len(ids))


def auto_masks(columns: Mapping[str, np.ndarray], n: int, suggested: Optional[Sequence[str]] = None,
               ids: Optional[Sequence[str]] = None) -> Dict[str, np.ndarray]:
    """The automatic groups from an answer's per-set columns (``#holds``, ``#pareto``,
    ``#complete``): *error* is a set with an output missing (not complete), *fails* a complete
    set that does not hold."""
    def flag(name: str, default: bool) -> np.ndarray:
        c = columns.get(name)
        if c is None:
            return np.full(n, default, dtype=bool)
        a = np.asarray(c, dtype=float)
        return np.isfinite(a) & (a > 0.5)

    holds = flag("#holds", False)
    complete = flag("#complete", True)
    out = {
        "all": np.ones(n, dtype=bool),
        "holds": holds,
        "pareto": flag("#pareto", False),
        "error": ~complete,
        "fails": complete & ~holds,
    }
    out["suggested"] = ids_mask(ids, suggested) if suggested is not None and ids is not None else np.zeros(n, dtype=bool)
    return out


def check(group: Mapping[str, Any]) -> None:
    """A saved group is usable: a known source, and a rule or ids (not both missing)."""
    if group.get("source") not in SOURCES:
        raise GroupError(f"unknown source {group.get('source')!r}")
    if group.get("source") == "auto":
        raise GroupError("automatic groups are not saved")
    if group.get("frozen"):
        if not isinstance(group.get("ids"), list):
            raise GroupError("a frozen group needs its ids")
    elif not isinstance(group.get("rule"), dict):
        raise GroupError("a live group needs its rule")


def mask(group: Mapping[str, Any], columns: Mapping[str, np.ndarray], ids: Sequence[str]) -> np.ndarray:
    """The sets of one user group in the current answer."""
    check(group)
    if group.get("frozen"):
        return ids_mask(ids, group["ids"])
    return rule_mask(columns, group["rule"], len(ids))


def combine(op: str, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Union, intersection or difference of two groups' masks."""
    if op == "union":
        return a | b
    if op == "intersect":
        return a & b
    if op == "minus":
        return a & ~b
    raise GroupError(f"unknown operation {op!r}")


def freeze(m: np.ndarray, ids: Sequence[str]) -> List[str]:
    """A mask as frozen ids (what the result of ∪ ∩ ∖ is saved as)."""
    return [ids[int(i)] for i in np.flatnonzero(m)]
