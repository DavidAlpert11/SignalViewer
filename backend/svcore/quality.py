"""26.U7: a per-signal data-quality summary of a recording - what to know before trusting its numbers.

  missing      samples with no value (NaN) - also a text column's empty cells
  gaps         time with no data: the same rule as spectra, statistics and filters (ops.isolated_gaps)
  duplicates   samples at the same time as the one before (a repeated time stamp)
  backwards    a time stamp earlier than the one before (the file was out of order; the CSV reader sorts
               it, and says so - counted here only when it is still so)
  rate changes the logging rate changing for a while (100 Hz, then 10 Hz) - a block median of the step,
               so jitter and single gaps are not changes

Signals that share one time vector (the columns of a CSV, the fields of one log message) are checked
for time once. Everything is O(n) and vectorised; a big log is checked in a background job."""
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from svcore.ops import isolated_gaps

RATE_JUMP = 1.8            # a block's step this many times longer / shorter than the previous one
MIN_BLOCK = 20             # samples per block (a rate is a median over at least this many steps)
MAX_CHANGES = 5


def time_quality(t: np.ndarray) -> Dict[str, Any]:
    """The checks of a time vector: rate (Hz), gaps, duplicates, backwards, rate changes."""
    t = np.asarray(t, dtype=np.float64)
    n = len(t)
    out: Dict[str, Any] = {"n": int(n), "rate": None, "gaps": 0, "gapTime": 0.0, "firstGap": None,
                           "duplicates": 0, "backwards": 0, "rateChanges": []}
    if n < 3:
        return out
    d = np.diff(t)
    fin = np.isfinite(d)
    out["duplicates"] = int(np.count_nonzero(d[fin] == 0))
    out["backwards"] = int(np.count_nonzero(d[fin] < 0))
    pos = d[fin & (d > 0)]
    if not len(pos):
        return out
    step = float(np.median(pos))
    out["rate"] = 1.0 / step if step > 0 else None
    dd = np.where(fin & (d > 0), d, step)
    gap = isolated_gaps(dd, step)
    if gap.any():
        idx = np.flatnonzero(gap)
        out.update(gaps=int(len(idx)), gapTime=float(dd[idx].sum()), firstGap=float(t[idx[0]]))
    # rate changes: medians of blocks of steps (gaps left out); a change must hold for two blocks
    good = np.flatnonzero(~gap & fin & (d > 0))
    blk = max(MIN_BLOCK, len(good) // 200)
    nb = len(good) // blk
    if nb >= 3:
        meds = np.median(dd[good[: nb * blk]].reshape(nb, blk), axis=1)
        starts = t[good[: nb * blk : blk]]
        cur = meds[0]
        changes: List[dict] = []
        for k in range(1, nb - 1):
            r = meds[k] / cur
            r2 = meds[k + 1] / cur
            if (r > RATE_JUMP and r2 > RATE_JUMP) or (r < 1 / RATE_JUMP and r2 < 1 / RATE_JUMP):
                changes.append({"t": float(starts[k]), "from": float(1.0 / cur), "to": float(1.0 / meds[k])})
                cur = meds[k]
                if len(changes) >= MAX_CHANGES:
                    break
        out["rateChanges"] = changes
    return out


def signal_quality(t: np.ndarray, y: np.ndarray, time_q: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One signal: its time's checks (given when its time vector was checked already) and its values'."""
    q = dict(time_q if time_q is not None else time_quality(t))
    y = np.asarray(y)
    miss = int(np.count_nonzero(np.isnan(y))) if y.dtype.kind == "f" else 0
    q["missing"] = miss
    q["missingPct"] = 100.0 * miss / len(y) if len(y) else 0.0
    q["allMissing"] = bool(len(y) and miss == len(y))
    return q


def issues(q: Dict[str, Any]) -> List[str]:
    """The kinds of problem a signal's summary shows (empty: nothing to say)."""
    return [k for k, bad in (("missing", q.get("missing")), ("gaps", q.get("gaps")), ("duplicates", q.get("duplicates")),
                             ("backwards", q.get("backwards")), ("rateChanges", q.get("rateChanges"))) if bad]


def run_quality(signals: Iterable[Tuple[str, np.ndarray, np.ndarray, bool]], progress=None, total: int = 0) -> Dict[str, Any]:
    """Every signal of a run: [{name, ...checks, issues}], and how many signals have each problem.
    Each item is (name, t, y, state): a state or event signal (a mode, a message, a text) is logged when
    it changes - its pauses, repeated times and rate are what it is, not problems; only its values count."""
    seen: Dict[int, Tuple[np.ndarray, Dict[str, Any]]] = {}
    rows: List[dict] = []
    count = {k: 0 for k in ("missing", "gaps", "duplicates", "backwards", "rateChanges")}
    for i, (name, t, y, state) in enumerate(signals):
        if state:
            tq: Dict[str, Any] = {**time_quality(t[:0]), "n": int(len(t)), "event": True}
        else:
            key = id(t)
            hit = seen.get(key)
            if hit is None or hit[0] is not t:
                hit = (t, time_quality(t))
                seen[key] = hit
            tq = hit[1]
        q = signal_quality(t, y, tq)
        q["issues"] = issues(q)
        for k in q["issues"]:
            count[k] += 1
        rows.append({"name": name, **q})
        if progress and total:
            progress((i + 1) / total, name)
    return {"signals": rows, "count": count, "checked": len(rows),
            "withIssues": sum(1 for r in rows if r["issues"])}
