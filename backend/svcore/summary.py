"""M1: summarize runs - one row per recording, one number per *measure* (a signal by name and what to take of
it), plus parameters read from the file's name by a pattern. The Runs matrix shows them for the open runs
(define on one run, see the value at once) and hands the table to Sweeps; `cli.py summarize` applies the same
measures to a folder, one file at a time (the memory of one file).

A measure: {"name": "max roll", "signal": "ATT.Roll", "op": "max", "where": "", "t": None}
ops: max, min, mean, rms, std, range, first, final, at (the value at time t), argmax / argmin (when it peaks),
overshoot (% above the final value, of the step from the first), settle (s until it stays within 2 % of the
final value). `where`: a condition (Investigate's language) - only the samples where it holds."""
import os
import re
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

OPS = ("max", "min", "mean", "rms", "std", "range", "first", "final", "at", "argmax", "argmin", "overshoot", "settle")


class SummaryError(ValueError):
    pass


def take(t: np.ndarray, y: np.ndarray, op: str, at: Optional[float] = None) -> Optional[float]:
    """One number of a signal; None when there is nothing to take (no samples, all NaN)."""
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(y)
    t, y = t[ok], y[ok]
    if not len(y):
        return None
    if op == "max":
        return float(y.max())
    if op == "min":
        return float(y.min())
    if op == "mean":
        return float(y.mean())
    if op == "rms":
        return float(np.sqrt(np.mean(y * y)))
    if op == "std":
        return float(y.std())
    if op == "range":
        return float(y.max() - y.min())
    if op == "first":
        return float(y[0])
    if op == "final":
        return float(y[-1])
    if op == "argmax":
        return float(t[int(np.argmax(y))])
    if op == "argmin":
        return float(t[int(np.argmin(y))])
    if op == "at":
        if at is None or at < t[0] or at > t[-1]:
            return None
        return float(np.interp(at, t, y))
    if op in ("overshoot", "settle"):
        y0, yf = float(y[0]), float(y[-1])
        step = yf - y0
        if abs(step) < 1e-12:
            return None
        if op == "overshoot":
            peak = y.max() if step > 0 else y.min()
            return float(max(0.0, (peak - yf) / step * 100.0))
        out = np.flatnonzero(np.abs(y - yf) > 0.02 * abs(step))
        return float(t[out[-1] + 1] - t[0]) if len(out) and out[-1] + 1 < len(t) else (0.0 if not len(out) else None)
    raise SummaryError(f"Unknown measure '{op}' - use one of {', '.join(OPS)}.")


def name_pattern(pattern: str) -> Optional["re.Pattern[str]"]:
    """`kp_{kp}_wind_{wind}` -> a regex with one group per {name}, matched at the end of the file's name
    without its extension. No regex for the user to write."""
    pattern = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", pattern.strip())
    if not pattern:
        return None
    parts = re.split(r"\{([^}]+)\}", pattern)
    rx = "".join(f"(?P<{_group(p)}>.+?)" if i % 2 else re.escape(p) for i, p in enumerate(parts))
    return re.compile(rx + "$")


def _group(name: str) -> str:
    return "g_" + re.sub(r"\W", "_", name.strip()).encode("ascii", "backslashreplace").decode().replace("\\", "_")


def params_from_name(pattern: str, path: str) -> Dict[str, object]:
    """The pattern's values in the file's name (numbers as numbers); {} when it does not match."""
    rx = name_pattern(pattern)
    if rx is None:
        return {}
    m = rx.search(os.path.splitext(os.path.basename(path))[0])
    if not m:
        return {}
    names = re.findall(r"\{([^}]+)\}", pattern)
    out: Dict[str, object] = {}
    for n in names:
        v = m.group(_group(n))
        try:
            out[n.strip()] = float(v)
        except (TypeError, ValueError):
            out[n.strip()] = v
    return out


def measure_run(read: Callable[[str], Optional[Tuple[np.ndarray, np.ndarray]]], measures: Sequence[dict],
                where: Callable[[str], Optional[List[Tuple[float, float]]]] = lambda _w: None) -> Dict[str, object]:
    """{measure name: value | None} for one run. read(signal name) -> (t, y) or None (not in this file);
    where(condition) -> its stretches in this run (None: the condition cannot be read here)."""
    out: Dict[str, object] = {}
    for m in measures:
        name = str(m.get("name") or f"{m.get('op')} {m.get('signal')}")
        got = read(str(m.get("signal") or ""))
        if got is None:
            out[name] = None
            continue
        t, y = np.asarray(got[0], dtype=np.float64), np.asarray(got[1], dtype=np.float64)
        cond = str(m.get("where") or "").strip()
        if cond:
            iv = where(cond)
            if not iv:
                out[name] = None
                continue
            keep = np.zeros(len(t), bool)
            for a, b in iv:
                keep |= (t >= a) & (t <= b)
            t, y = t[keep], y[keep]
        out[name] = take(t, y, str(m.get("op") or "max"), m.get("t"))
    return out


def check(measures: Sequence[dict]) -> None:
    for m in measures:
        if str(m.get("op")) not in OPS:
            raise SummaryError(f"Unknown measure '{m.get('op')}' - use one of {', '.join(OPS)}.")
        if not str(m.get("signal") or "").strip():
            raise SummaryError("Each measure needs a signal.")


def summarize_run(st, rid: str, measures: Sequence[dict], pattern: str) -> dict:
    """One open run's measures and name parameters (the app's Store or a script's) - also `cli.py summarize`, one file at a time."""
    from svcore.naming import resolve_signal_name
    lr = st.get(rid)
    names = list(lr.run.signals)

    def read(name: str):
        try:
            return st.signal(f"{rid}/{resolve_signal_name(names, name, lr.name)}")
        except (KeyError, ValueError):
            return None

    def where(text: str):
        got = st.evaluate_condition(text, run_ids=[rid]).get(rid) or {}
        return [tuple(iv) for iv in got.get("intervals") or []] or None
    return {"params": params_from_name(pattern, lr.run.file_path),
            "values": measure_run(read, measures, where)}


DATA_EXTS = (".csv", ".txt", ".tsv", ".mat", ".parquet", ".pq", ".h5", ".hdf5", ".bin", ".tlog", ".ulg", ".mcap")


MEASURES_FILE = "measures.json"


def read_measures(path: str) -> Tuple[List[dict], str]:
    """A measures file -> (measures, name pattern): a JSON list of measures, or {"measures": [...], "pattern": "..."}
    as the Runs matrix's *Save measures* writes it."""
    import json
    try:
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
    except (OSError, ValueError) as e:
        raise SummaryError(f"{os.path.basename(path)} cannot be read ({e}) - save the measures again from the Runs matrix.") from None
    measures = spec.get("measures", []) if isinstance(spec, dict) else spec
    pattern = str(spec.get("pattern") or "") if isinstance(spec, dict) else ""
    if not isinstance(measures, list) or not all(isinstance(m, dict) for m in measures):
        raise SummaryError(f"{os.path.basename(path)}: \"measures\" must be a list of {{name, signal, op}}.")
    check(measures)
    return measures, pattern


def folder_measures(folder: str) -> Optional[Tuple[List[dict], str]]:
    """FL1: the measures kept with a folder of recordings (its measures.json), or None - like checks.json beside a recording."""
    p = os.path.join(folder, MEASURES_FILE)
    return read_measures(p) if os.path.isfile(p) else None


def folder_files(paths: Sequence[str]) -> List[str]:
    """Files, glob patterns or folders (their recordings, by name) -> the recordings, in order."""
    import glob
    out: List[str] = []
    for x in paths:
        if os.path.isdir(x):
            out += sorted(p for p in glob.glob(os.path.join(x, "*")) if os.path.isfile(p) and p.lower().endswith(DATA_EXTS))
        else:
            out += sorted(glob.glob(x)) or [x]
    return out


def summarize_files(paths: Sequence[str], measures: Sequence[dict], pattern: str, open_file,
                    progress=lambda _f, _name: None, cancelled=lambda: False,
                    more: Optional[Callable[[object, str, str], Dict[str, Optional[float]]]] = None) -> Tuple[List[str], List[list], List[str]]:
    """M2: (columns, rows, skipped) for recordings that are NOT open - one at a time: open_file(path) -> (store,
    run id) reads it into a store of its own, it is measured and closed, so memory stays one file's (measured
    flat over 50 files of 2 M rows: tools/measure_summary_memory.py). A file that cannot be read is named in
    `skipped`, the rest go on. CC13: more(store, run id, path) -> more columns of the run (the requirements' verdicts)."""
    check(measures)
    got: List[dict] = []
    skipped: List[str] = []
    for i, path in enumerate(paths):
        if cancelled():
            break
        progress(i / max(1, len(paths)), os.path.basename(path))
        try:
            st, rid = open_file(path)
        except Exception as e:                        # noqa: BLE001 - any reader's failure: named, the rest go on
            skipped.append(f"{os.path.basename(path)}: {e}")
            continue
        try:
            r = summarize_run(st, rid, measures, pattern)
            extra = more(st, rid, path) if more else {}
        finally:
            st.remove(rid)
        got.append({"recording": os.path.abspath(path), **r["params"], **r["values"], **extra})
    cols: List[str] = []
    for r in got:
        cols += [k for k in r if k not in cols]
    return cols, [[r.get(c) for c in cols] for r in got], skipped
