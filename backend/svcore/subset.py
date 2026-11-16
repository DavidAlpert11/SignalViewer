"""E1: a part of a recording as a new file - some signals, a time range or only where a condition holds,
as recorded or on one time base at a chosen rate. The plot's *Export CSV*, the *Export recording…* dialog
and `cli.py export` all write through here (one way to do it).

Resampling to a rate: values linearly, states (modes, gears, texts) held - the value in force, never
between two states - and, when the rate goes down, a zero-phase low-pass first (anti-alias, cut-off 0.4 x
the new rate) so a 400 Hz vibration does not come back as a slow wave at 10 Hz.

Formats: .csv, .parquet (pyarrow), .mat (scipy) and .h5 (h5py) - the app's own readers' dependencies; every
file opens again in the app with the same names and values. Beside it, `<file>.export.json` says what was
taken (source, signals, time, rate)."""
import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from svcore.analysis import align_to, hold_to
from svcore.atomic import atomic_path

FORMATS = (".csv", ".parquet", ".mat", ".h5")
MAX_ROWS = 50_000_000          # a typo in the rate (1e6 Hz over an hour) is said, not written


class SubsetError(ValueError):
    """Something the user has to change (no signals, a rate too high, an unknown format)."""


@dataclass
class Column:
    name: str
    t: np.ndarray
    y: np.ndarray
    state: bool = False        # held when resampled, never filtered
    unit: str = ""


@dataclass
class Subset:
    t: np.ndarray
    cols: Dict[str, np.ndarray]
    units: Dict[str, str] = field(default_factory=dict)
    segment: Optional[np.ndarray] = None       # the stretch each row belongs to (only-where-a-condition-holds)
    info: dict = field(default_factory=dict)   # what the sidecar says


def _f64(a) -> np.ndarray:
    return np.asarray(a, dtype=np.float64)


def _rate(t: np.ndarray) -> float:
    d = np.diff(t[np.isfinite(t)])
    d = d[d > 0]
    return float(1.0 / np.median(d)) if len(d) else 0.0


def _lowpass(t: np.ndarray, y: np.ndarray, rate: float) -> np.ndarray:
    """y low-passed (zero phase) for sampling at `rate` - only when its own rate is clearly higher."""
    fs = _rate(t)
    if fs <= rate * 1.25 or len(y) < 30 or not np.all(np.isfinite(y)):
        return y
    from scipy.signal import butter, sosfiltfilt
    sos = butter(4, min(0.4 * rate / (fs / 2), 0.99), output="sos")
    return sosfiltfilt(sos, y)


def _merged(ranges: Sequence[Tuple[float, float]], margin: float, lo: float, hi: float) -> List[Tuple[float, float]]:
    out: List[Tuple[float, float]] = []
    for a, b in sorted((min(a, b) - margin, max(a, b) + margin) for a, b in ranges):
        a, b = max(a, lo), min(b, hi)
        if b < a:
            continue
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def build(cols: Sequence[Column], timing: str = "first", rate: Optional[float] = None,
          t0: Optional[float] = None, t1: Optional[float] = None,
          ranges: Optional[Sequence[Tuple[float, float]]] = None, margin: float = 0.0,
          antialias: bool = True, from_zero: bool = False, alignment: str = "linear") -> Subset:
    """The table to write. timing: "first" - the first signal's own samples (the plot's Export CSV);
    "fastest" - the samples of the signal with the most in the range (as recorded); "rate" - one time base
    at `rate` Hz. ranges: keep only these stretches (+ margin), each row numbered by its stretch."""
    if not cols:
        raise SubsetError("No signals to export - choose at least one.")
    starts = [float(c.t[0]) for c in cols if len(c.t)]
    ends = [float(c.t[-1]) for c in cols if len(c.t)]
    if not starts:
        raise SubsetError("The chosen signals have no samples.")
    lo = min(starts) if t0 is None else min(t0, t1 if t1 is not None else t0)
    hi = max(ends) if t1 is None else max(t1, t0 if t0 is not None else t1)
    spans = [(lo, hi)] if ranges is None else _merged(ranges, max(0.0, margin), lo, hi)
    if not spans:
        raise SubsetError("The condition does not hold anywhere in the chosen time.")

    base = cols[0]
    if timing == "rate":
        if not rate or rate <= 0:
            raise SubsetError("Write the rate in Hz (a number above 0).")
        n = sum(int((b - a) * rate) + 1 for a, b in spans)
        if n > MAX_ROWS:
            raise SubsetError(f"{rate:g} Hz gives {n:,} rows - more than {MAX_ROWS:,}. Lower the rate or the time.")
        parts = [a + np.arange(int(np.floor((b - a) * rate + 1e-9)) + 1) / rate for a, b in spans]
    else:
        if timing == "fastest":
            def inside(c):
                return int(np.searchsorted(c.t, hi, "right") - np.searchsorted(c.t, lo, "left"))
            base = max(cols, key=inside)
        tb = _f64(base.t)
        parts = [tb[np.searchsorted(tb, a, "left"):np.searchsorted(tb, b, "right")] for a, b in spans]
    t = np.concatenate(parts) if parts else np.zeros(0)
    segment = np.concatenate([np.full(len(p), k + 1.0) for k, p in enumerate(parts)]) if ranges is not None else None

    out: Dict[str, np.ndarray] = {}
    units: Dict[str, str] = {}
    taken: set = set()
    for c in cols:
        name, k = c.name, 2
        while name in taken or name in ("Time", "Segment"):
            name = f"{c.name} ({k})"; k += 1
        taken.add(name)
        ts, ys = _f64(c.t), _f64(c.y)
        if c.state:
            out[name] = hold_to(t, ts, ys)
        elif timing != "rate" and c is base:
            out[name] = ys[np.searchsorted(ts, t)] if len(t) else np.zeros(0)   # its own samples, unchanged
        else:
            if timing == "rate" and antialias:
                ys = _lowpass(ts, ys, float(rate or 0))
            out[name] = align_to(t, ts, ys, alignment)
        if c.unit:
            units[name] = c.unit
    shown_t = t - t[0] if from_zero and len(t) else t
    info = {"timing": timing, **({"rate": rate, "antialias": bool(antialias)} if timing == "rate" else {}),
            "from": lo, "to": hi, **({"stretches": [list(s) for s in spans], "margin": margin} if ranges is not None else {}),
            "timeFromZero": bool(from_zero), "rows": int(len(t))}
    return Subset(shown_t, out, units, segment, info)


def _header(name: str, unit: str) -> str:
    return (f"{name} [{unit}]" if unit and "[" not in name else name).replace(",", " ")


def mat_name(name: str, taken: set) -> str:
    """A valid, unique MATLAB variable name for a signal ("ATT.Roll [deg]" -> "ATT_Roll_deg")."""
    v = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_") or "signal"
    if not v[0].isalpha():
        v = "s_" + v
    v = v[:60]
    base, k = v, 2
    while v in taken:
        v = f"{base[:56]}_{k}"; k += 1
    taken.add(v)
    return v


def write(path: str, sub: Subset, meta: Optional[dict] = None, sidecar: bool = True) -> str:
    """Write the table as the path's extension says; returns the path. Written to a temporary file first,
    so a failed export never leaves half a file in place of a good one."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".hdf5":
        ext = ".h5"
    if ext not in FORMATS:
        raise SubsetError(f"Unknown format {ext or '(none)'} - use {', '.join(FORMATS)}.")
    names = list(sub.cols)
    extra = {"Segment": sub.segment} if sub.segment is not None else {}
    with atomic_path(path) as tmp:
        if ext == ".csv":
            header = ["Time"] + [_header(n, sub.units.get(n, "")) for n in names] + list(extra)
            with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
                f.write(",".join(header) + "\n")
                np.savetxt(f, np.column_stack([sub.t, *sub.cols.values(), *extra.values()]) if len(sub.t)
                           else np.zeros((0, len(header))), delimiter=",", fmt="%.10g")
        elif ext == ".parquet":
            import pyarrow as pa
            import pyarrow.parquet as pq
            fields = [pa.field("Time", pa.float64())] + [
                pa.field(n, pa.float64(), metadata={"unit": sub.units[n]} if n in sub.units else None) for n in names
            ] + [pa.field(n, pa.float64()) for n in extra]
            table = pa.Table.from_arrays([pa.array(sub.t)] + [pa.array(v) for v in sub.cols.values()]
                                         + [pa.array(v) for v in extra.values()], schema=pa.schema(fields))
            pq.write_table(table, tmp)
        elif ext == ".mat":
            from scipy.io import savemat
            taken = {"Time", "Segment"}
            data = {"Time": sub.t, **{mat_name(n, taken): v for n, v in sub.cols.items()}, **extra}
            with open(tmp, "wb") as f:
                savemat(f, data, do_compression=True)
        else:
            import h5py
            with h5py.File(tmp, "w") as f:
                f.create_dataset("Time", data=sub.t)
                for n, v in [*sub.cols.items(), *extra.items()]:
                    d = f.create_dataset(n.replace("/", "_"), data=v, compression="gzip")
                    if n in sub.units:
                        d.attrs["unit"] = sub.units[n]
    if sidecar:
        side = {**(meta or {}), **sub.info, "signals": [{"name": n, **({"unit": sub.units[n]} if n in sub.units else {})} for n in names]}
        with open(os.path.splitext(path)[0] + ".export.json", "w", encoding="utf-8") as f:
            json.dump(side, f, indent=1, ensure_ascii=False)
    return path


def from_store(store, signals: Sequence[dict], where: str = "", margin: float = 0.0, **opts) -> Subset:
    """The table from the open files (the app's Store): signals [{id, label?, scale?, offset?, tOffset?,
    unit?}] as shown; `where` a condition (Investigate's language) in the first signal's run - only its
    stretches are kept. opts: build()'s timing, rate, t0, t1, antialias, from_zero, alignment."""
    cols: List[Column] = []
    for s in signals:
        t, y = store.signal(s["id"])
        t = _f64(t) + float(s.get("tOffset") or 0)
        y = _f64(y) * float(s.get("scale", 1) or 1) + float(s.get("offset", 0) or 0)
        cols.append(Column(str(s.get("label") or s["id"].split("/", 1)[-1]), t, y, bool(store.is_state(s["id"])),
                           str(s.get("unit") or "")))
    ranges = None
    if where.strip() and signals:
        rid = signals[0]["id"].split("/", 1)[0]
        got = store.evaluate_condition(where, run_ids=[rid]).get(rid) or {}
        if got.get("missing"):
            raise SubsetError(f"The condition reads signals this file does not have: {', '.join(got['missing'])}.")
        if got.get("error"):
            raise SubsetError(str(got["error"]))
        ranges = [tuple(iv) for iv in got.get("intervals") or []]
        if not ranges:
            raise SubsetError("The condition does not hold anywhere in this file.")
    sub = build(cols, ranges=ranges, margin=margin, **opts)
    if ranges is not None:
        sub.info["where"] = where
    return sub
