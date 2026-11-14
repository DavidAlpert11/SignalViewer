"""
F1 - *The file*: the structure of any open recording, for the Log panel's place.

What the data has, never what a format is assumed to have:
  - groups: a log's message types (ArduPilot ``IMU[0]``, MAVLink ``ATTITUDE``, PX4 topics), an MCAP's
    topics, a MATLAB / HDF5 file's structs, a table's column prefixes (``Engine_``) - or none;
  - per group and per column: samples, mean rate, unit (``Name [unit]``), the time span, gaps (a step
    longer than 3 x the typical one), whether it is a state;
  - the time base: which column (or the row number / the log's clock) gives the time.

Cheap: only time vectors are read (never a lazy log's values), each distinct one once. The values at
the cursor are the existing /api/cursor's job (the UI sends a group's ids) - one way to do a thing.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_UNIT = re.compile(r"^(.*?)\s+\[([^\]]*)\]$")
LOGS = ("bin", "tlog", "ulg", "mcap")       # a group is a message type / topic: the part before the first "."
STRUCTS = ("mat", "hdf5")                   # a group is the struct path: everything before the last "."
GAP_FACTOR = 3.0


def split_unit(name: str) -> Tuple[str, Optional[str]]:
    """"ATT.Roll [deg]" -> ("ATT.Roll", "deg")."""
    m = _UNIT.match(name)
    return (m.group(1), m.group(2) or None) if m else (name, None)


def group_key(name: str, fmt: str, prefixes: Optional[set] = None) -> Tuple[str, str]:
    """(group, the column's name inside it)."""
    bare, _ = split_unit(name)
    if fmt in STRUCTS:
        i = bare.rfind(".")
    elif fmt in LOGS or "." in bare:
        i = bare.find(".")
    else:
        i = -1
    if i > 0:
        return bare[:i], bare[i + 1:]
    if prefixes:
        p = bare.split("_", 1)[0]
        if p in prefixes and p != bare:
            return p, bare[len(p) + 1:]
    return "", bare


def _table_prefixes(names: List[str]) -> set:
    """A table's column prefixes that organise it ("Engine_rpm", "Engine_temp" -> Engine): at least two
    columns each, and not every column its own group."""
    count: Dict[str, int] = {}
    for n in names:
        bare = split_unit(n)[0]
        if "_" in bare and "." not in bare:
            p = bare.split("_", 1)[0]
            if p:
                count[p] = count.get(p, 0) + 1
    return {p for p, k in count.items() if k >= 2}


def time_stats(t: Optional[np.ndarray]) -> Dict[str, Any]:
    """Samples, mean rate, span and gaps of one time vector."""
    if t is None or len(t) == 0:
        return {"n": 0}
    t = np.asarray(t, dtype=np.float64)
    n = len(t)
    out: Dict[str, Any] = {"n": int(n), "t0": float(t[0]), "t1": float(t[-1])}
    if n < 2:
        return out
    span = float(t[-1] - t[0])
    if span > 0 and np.isfinite(span):
        out["rate"] = float(f"{(n - 1) / span:.4g}")
    dt = np.diff(t)
    dt = dt[np.isfinite(dt)]
    if len(dt):
        typical = float(np.median(dt))
        if typical > 0:
            big = dt > GAP_FACTOR * typical
            k = int(big.sum())
            if k:
                out["gaps"] = k
                out["longestGap"] = float(f"{float(dt[big].max()):.6g}")
    return out


def _ends(run, name: str, stats_of) -> Tuple[Any, Any]:
    sg = run.signals[name]
    st = stats_of(sg.time if sg.time is not None else run.time)
    return st.get("t0"), st.get("t1")


def structure(run, fmt: str) -> Dict[str, Any]:
    """The structure of an open run: {format, timeBase, groups[{name, kind, columns[...], n, rate}], columns}."""
    names = list(run.signals)
    prefixes = _table_prefixes(names) if fmt not in LOGS and fmt not in STRUCTS else None
    cache: Dict[int, Dict[str, Any]] = {}

    def stats_of(t) -> Dict[str, Any]:
        key = id(t)
        if key not in cache:
            cache[key] = time_stats(t)
        return cache[key]

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for n in names:
        sg = run.signals[n]
        t = sg.time if sg.time is not None else run.time
        g, leaf = group_key(n, fmt, prefixes)
        _, unit = split_unit(n)
        st = stats_of(t)
        col: Dict[str, Any] = {"name": n, "field": leaf, **{k: st[k] for k in ("n", "rate", "gaps") if k in st}}
        if unit:
            col["unit"] = unit
        if sg.labels:
            col["state"] = True
        if sg.time is not None:
            col["ownTime"] = True
        groups.setdefault(g, []).append(col)
    kind = "message" if fmt in ("bin", "tlog", "ulg") else "topic" if fmt == "mcap" else \
        "struct" if fmt in STRUCTS else "prefix"
    out_groups = []
    for g in sorted(groups, key=lambda k: (k == "", k.lower())):
        cols = groups[g]
        sg0 = run.signals[cols[0]["name"]]
        st = stats_of(sg0.time if sg0.time is not None else run.time)
        # one clock for the group (a message, a topic) - by its samples and ends, not by object (a followed
        # file's appended columns are separate arrays of the same times): its rate is the group's
        sig = (st.get("n"), st.get("t0"), st.get("t1"))
        shared = all((c.get("n"), *_ends(run, c["name"], stats_of)) == sig for c in cols)
        row: Dict[str, Any] = {"name": g, "kind": kind if g else "columns", "columns": cols}
        if shared:
            row.update({k: st[k] for k in ("n", "rate", "gaps", "longestGap", "t0", "t1") if k in st})
        out_groups.append(row)
    src = getattr(run, "time_source", None)
    base: Dict[str, Any] = {"column": src} if src else {}
    if getattr(run, "time_is_index", False):
        base["index"] = True
    elif not src:
        base["clock"] = "log" if fmt in LOGS else "index"
    if run.time is not None and len(run.time):
        base.update({"start": float(run.start_time), "end": float(run.end_time)})
    own = len({id(run.signals[n].time) for n in names if run.signals[n].time is not None})
    return {"format": fmt, "timeBase": base, "groups": out_groups, "columns": len(names),
            "timeVectors": own + (1 if any(run.signals[n].time is None for n in names) else 0)}
