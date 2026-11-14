"""
F3 - the parameters of a run, for every format, and two runs compared.

One source for "what was this run set to": the Log panel's Parameters, Compare's *two runs
compared* and Investigate's *Runs x conditions* all read it.

Where the values come from (the first that names a value wins, in this order):
  - ``log``:      a flight log's own parameters (ArduPilot PARM, MAVLink PARAM_VALUE, PX4) - the value
                  at the start of the log; the ones changed during it carry their changes;
  - ``file``:     settings the file states itself (MATLAB scalars, short texts, struct fields);
  - ``constant``: signals that hold one value the whole run (a payload, a gain, a seed) - only for
                  files with a modest number of signals (a log's thousand would cost time and say little);
  - ``name``:     numbers in the file name (``mass2.4``, ``wind=8``, ``run_012``).
"""

import math
import os
import re
from typing import Any, Dict, List, Optional, Union

import numpy as np

Value = Union[float, str]

_TOKEN = re.compile(r"^([A-Za-z][A-Za-z]*)[=]?(-?\d+(?:\.\d+)?)$")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def name_numbers(path: str) -> Dict[str, float]:
    """Numbers in a file name: "mc_mass2.4_wind=8_run_012" -> mass 2.4, wind 8, run 12."""
    ps: Dict[str, float] = {}
    stem = os.path.splitext(os.path.basename(path))[0]
    parts = [x for x in re.split(r"[_\s-]+", stem) if x]
    for i, part in enumerate(parts):
        m = _TOKEN.match(part)
        if m:
            ps[m.group(1)] = float(m.group(2))
        elif i + 1 < len(parts) and _NUMBER.fullmatch(parts[i + 1]) and part.isalpha():
            ps[part] = float(parts[i + 1])
    return ps


def constant_signals(run, wide: int = 300) -> Dict[str, float]:
    """Signals that hold one value the whole run (only already-read signals of a modest file)."""
    ps: Dict[str, float] = {}
    if len(run.signals) > wide:
        return ps
    for name, sg in run.signals.items():
        if sg.labels or not getattr(sg, "loaded", True):
            continue
        y = np.asarray(sg.data, dtype=np.float64)
        y = y[np.isfinite(y)]
        if len(y) > 1 and float(y.min()) == float(y.max()):
            ps[name] = float(y[0])
    return ps


def parameters(run, wide: int = 300) -> List[Dict[str, Any]]:
    """Every parameter of a run: {name, value, source[, last, changes, default]}, sorted by name."""
    out: Dict[str, Dict[str, Any]] = {}
    fl = getattr(run, "_flightlog", None)
    if fl is not None:
        for nm, (_t0, v0, d) in getattr(fl, "param_first", {}).items():
            row: Dict[str, Any] = {"name": nm, "value": float(v0), "source": "log"}
            ch = fl.param_changes.get(nm) if getattr(fl, "param_changes", None) else None
            if ch:
                row["changes"] = [[float(t), float(v)] for t, v in ch]
                row["last"] = float(fl.params.get(nm, v0))
            if d is not None:
                row["default"] = float(d)
            out[nm] = row
    for nm, v in (getattr(run, "file_params", None) or {}).items():
        out.setdefault(nm, {"name": nm, "value": v, "source": "file"})
    for nm, fv in constant_signals(run, wide).items():
        out.setdefault(nm, {"name": nm, "value": fv, "source": "constant"})
    for nm, fv in name_numbers(getattr(run, "file_path", "") or "").items():
        out.setdefault(nm, {"name": nm, "value": fv, "source": "name"})
    return [out[k] for k in sorted(out, key=str.lower)]


def numeric(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    """The numbers only (Runs x conditions draws them against each other)."""
    return {r["name"]: float(r["value"]) for r in rows if isinstance(r["value"], (int, float))}


def same(a: Optional[Value], b: Optional[Value], rel: float = 1e-6) -> bool:
    """Equal - numbers within a relative 1e-6 (a float32 parameter read twice is not "changed")."""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=rel, abs_tol=1e-12)
    return a == b


def compare(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Two runs' parameters, differences only: {differ, onlyA, onlyB, same (a count)}. A parameter
    changed during either run differs when its start or its end differs."""
    da = {r["name"]: r for r in a}
    db = {r["name"]: r for r in b}
    differ, only_a, only_b, n_same = [], [], [], 0
    for nm in sorted(set(da) | set(db), key=str.lower):
        ra, rb = da.get(nm), db.get(nm)
        if ra is None:
            only_b.append(rb)
            continue
        if rb is None:
            only_a.append(ra)
            continue
        end_a, end_b = ra.get("last", ra["value"]), rb.get("last", rb["value"])
        if same(ra["value"], rb["value"]) and same(end_a, end_b):
            n_same += 1
            continue
        row: Dict[str, Any] = {"name": nm, "a": ra["value"], "b": rb["value"], "source": ra["source"]}
        if "last" in ra or "last" in rb:
            row["aLast"], row["bLast"] = end_a, end_b
        if isinstance(ra["value"], (int, float)) and isinstance(rb["value"], (int, float)):
            row["delta"] = float(rb["value"]) - float(ra["value"])
        differ.append(row)
    return {"differ": differ, "onlyA": only_a, "onlyB": only_b, "same": n_same}
