"""
The Investigate panel's computations (conditions, occurrences, what changed first, its clusters and
chain, "find similar", the lag between two signals) as pure functions over the open files.

A1 (2026-11-07): moved out of app/store.py. They see the files only through a `Source` - a signal
getter and the names / state texts of each open file - so they can be tested without a Store
(tests/test_investigate.py) and the Store keeps one-line methods that build the Source.
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np

Labels = Optional[Dict[int, str]]


@dataclass
class Source:
    """What the investigation reads. `signal(id)` gives (time, values) as shown (offset, unit, edits
    applied) and raises KeyError / ValueError when it cannot; `signals(run_id)` the run's signal
    names with their state texts (None when the file is not open); `discrete(id)` whether a signal
    takes a few whole values; `derived` the new signals made in Create signals (by name, read as
    "derived/<name>"); `runs` the open data files in order."""
    signal: Callable[[str], Tuple[np.ndarray, np.ndarray]]
    signals: Callable[[str], Optional[Dict[str, Labels]]]
    discrete: Callable[[str], bool] = lambda _sid: False
    derived: Iterable[str] = field(default_factory=list)
    runs: List[str] = field(default_factory=list)
    derived_run: str = "derived"


class InvestigateError(ValueError):
    """Something the user has to change (no condition written, no file to look in)."""


# ------------------------------------------------------------------ conditions
def evaluate_condition(src: Source, text: str, exit_text: str = "", min_dur: float = 0.0, merge_gap: float = 0.0,
                       run_ids: Optional[List[str]] = None) -> Dict[str, dict]:
    """A named condition in every open file (or these): its stretches, as shown. A file without the
    signals it reads says which ones are missing."""
    from svcore.analysis import align_to
    from svcore.conditions import ConditionError, evaluate_condition as evaluate, names_in
    if not text.strip():
        raise InvestigateError("Write the condition, e.g. {Speed} > 12.")
    derived = set(src.derived)
    out: Dict[str, dict] = {}
    for rid in (run_ids or list(src.runs)):
        names = src.signals(rid) if rid != src.derived_run else None
        if names is None:
            continue

        def read(name: str, rid=rid, names=names):
            if name in names:
                return src.signal(f"{rid}/{name}")
            if name in derived:                                # a new signal made in Create signals
                try:
                    return src.signal(f"{src.derived_run}/{name}")
                except KeyError:
                    return None
            return None

        def labels(name: str, names=names):
            if name not in names:
                return None
            return {str(k): v for k, v in (names[name] or {}).items()}
        try:
            out[rid] = evaluate(text, read, labels, lambda t, ts, ys: align_to(t, ts, ys, "nearest"), exit_text, min_dur, merge_gap)
        except ConditionError as e:
            out[rid] = {"error": str(e)}
        except KeyError as e:
            out[rid] = {"error": str(e).strip("'\"")}
    if not out and names_in(text):
        raise InvestigateError("No open file to look in.")
    return out


# ------------------------------------------------------------------ occurrences
def occurrence_rows(src: Source, runs: Dict[str, List[List[float]]], names: List[str]) -> List[dict]:
    """The occurrences table: one row per stretch (file, start, end) with max / min / mean of each
    named signal in it."""
    from svcore.occurrences import occurrence_stats
    rows: List[dict] = []
    for rid, iv in runs.items():
        have = src.signals(rid)
        if have is None:
            continue
        per = {}
        for n in names:
            if n in have:
                t, y = src.signal(f"{rid}/{n}")
                per[n] = occurrence_stats(t, y, iv)
        for k, (a, b) in enumerate(iv):
            rows.append({"rid": rid, "a": a, "b": b, "values": {n: v[k] for n, v in per.items()}})
    rows.sort(key=lambda r: (r["a"], r["rid"]))
    return rows


def occurrence_windows(src: Source, items: List[dict], align: str, pad: float) -> List[dict]:
    """The occurrences overlay: each item {sig, intervals} -> its stretches on one axis."""
    from svcore.occurrences import windows
    out = []
    for it in items:
        t, y = src.signal(str(it["sig"]))
        out.append({"sig": it["sig"], **windows(t, y, it.get("intervals") or [], align, pad)})
    return out


def occurrence_differ(src: Source, runs: Dict[str, List[List[float]]], top: int = 25) -> List[dict]:
    """What differs in the occurrences: every numeric signal of the files with stretches, ranked by
    how far its mean inside them is from outside, in units of its usual spread outside. Signals of
    the same name in several files are averaged (weighted by their time inside)."""
    from svcore.occurrences import differ_one
    acc: Dict[str, dict] = {}
    for rid, iv in runs.items():
        have = src.signals(rid)
        if have is None or not iv:
            continue
        for name, labels in have.items():
            if labels:
                continue
            try:
                t, y = src.signal(f"{rid}/{name}")
            except (KeyError, ValueError):
                continue
            r = differ_one(t, y, iv)
            if r is None or not np.isfinite(r[0]):
                continue
            eff, mi, mo, share = r
            a = acc.setdefault(name, {"name": name, "w": 0.0, "eff": 0.0, "in": 0.0, "out": 0.0, "files": []})
            w = max(share, 1e-9)
            a["w"] += w; a["eff"] += eff * w; a["in"] += mi * w; a["out"] += mo * w
            a["files"].append(rid)
    items = [{"name": a["name"], "effect": a["eff"] / a["w"], "meanIn": a["in"] / a["w"], "meanOut": a["out"] / a["w"],
              "up": a["in"] >= a["out"], "files": a["files"]} for a in acc.values()]
    items.sort(key=lambda x: -x["effect"])
    return items[:top]


# ------------------------------------------------------------------ what changed first / lag
def _state_like(src: Source, sid: str) -> bool:
    """A state (texts) or a signal of a few whole values - its own value is the condition."""
    rid, _, name = sid.partition("/")
    have = src.signals(rid)
    if have is None or name not in have:
        return False
    return bool(have[name] or src.discrete(sid))


def first_changes(src: Source, sig_ids: List[str], run_ids: List[str], a: float, b: float,
                  base: Optional[Tuple[float, float]] = None, k: float = 4.0, persist: int = 3) -> List[dict]:
    """Investigation step 4: for these signals (and every numeric signal of these files), when each
    first left its usual range around the event [a, b] - candidates in time order."""
    from svcore.firstchange import default_baseline, first_change, fit_baseline
    fit = base is None                      # the default one is fitted to each signal's data
    base = base or default_baseline(a, b)
    more = [f"{rid}/{n}" for rid in run_ids for n in (src.signals(rid) or {})]
    out: List[dict] = []
    for sid in dict.fromkeys(sig_ids + more):
        name = sid.partition("/")[2]
        try:
            t, y = src.signal(sid)
        except (KeyError, ValueError):
            continue
        own = fit_baseline(base, a, float(np.min(t))) if fit and len(t) else base
        r = first_change(t, y, a, b, own, k, persist, _state_like(src, sid))
        out.append({"id": sid, "name": name, "base": [float(own[0]), float(own[1])], **r})
    changed = sorted([x for x in out if x["status"] == "changed"], key=lambda x: x["t"])
    return changed + [x for x in out if x["status"] != "changed"]


def change_clusters(src: Source, items: List[dict], a: float, b: float, refs: List[str], k: float = 4.0,
                    persist: int = 3, event: Optional[str] = None, shape_top: int = 30) -> dict:
    """Q130 / Q131 on `first_changes`' items: each changed one scored (its parts kept - no black box),
    the changes in clusters, the clusters by their best member. `refs`: the reference runs (the
    other open files) - a signal of the same name changing there too is marked and comes last in its
    cluster. `event`: the signal the event is in (default: the most unusual inside the span)."""
    from svcore.firstchange import clusters, lag, score_of, score_parts
    live = [x for x in items if x["status"] == "changed" and not x.get("skip")]
    names = {x["name"] for x in live}
    in_ref: Dict[str, List[str]] = {}
    for rid in refs:
        have = src.signals(rid)
        if have is None:
            continue
        sigs = [f"{rid}/{n}" for n in have if n in names]
        for r in first_changes(src, sigs, [], a, b, None, k, persist):
            if r["status"] == "changed":
                in_ref.setdefault(r["name"], []).append(rid)
    start = min((x["base"][1] for x in live), default=a)
    if event is None and live:
        pick = suggest_condition(src, [x["id"] for x in items if x.get("status") != "nodata"], a, b)
        event = pick.get("id")
    n = max(1, len(live) - 1)
    for x in live:
        later = sum(1 for o in live if o is not x and o["t"] > x["t"])
        x["parts"] = score_parts(x, a, start, x["name"] in in_ref, None, later / n, k)
        x["inRef"] = in_ref.get(x["name"], [])
    # the shape against the event signal: only for the likeliest (a lag each is not free)
    ev = None
    if event:
        try:
            ev = src.signal(event)
        except (KeyError, ValueError):
            ev = None
    if ev is not None:
        L = b - a
        for x in sorted(live, key=lambda x: -score_of(x["parts"]))[:shape_top]:
            if x["id"] == event:
                continue
            try:
                tx, yx = src.signal(x["id"])
            except (KeyError, ValueError):
                continue
            # room on both sides of the two changes (a window ending at the event's step made the
            # largest shift, with almost no overlap, look best)
            pad = max(L, a - start)
            r = lag(tx, yx, ev[0], ev[1], start - pad, b + pad, max_lag=pad)
            lg, rr = r.get("lag"), r.get("r")
            if (r.get("status") == "ok" and not r.get("weak") and not r.get("ambiguous")
                    and isinstance(lg, float) and isinstance(rr, float) and lg > 0):
                x["parts"]["shape"] = abs(rr)
                x["leadsEvent"] = lg
    for x in live:
        x["score"] = score_of(x["parts"])
    cl = clusters(live, a, b, start)
    by = {x["id"]: x for x in live}
    if event in by:
        by[event]["isEvent"] = True             # the event's own signal: shown, never "the likely first"
    for c in cl:
        c["ids"].sort(key=lambda i: (i == event, bool(by[i]["inRef"]), -by[i]["score"]))
        c["best"] = max((by[i]["score"] for i in c["ids"] if i != event), default=0.0)
    cl.sort(key=lambda c: -c["best"])
    return {"clusters": cl, "event": event, "chain": chain(src, cl, by, event, a, b, start)}


def chain(src: Source, cl: List[dict], by: Dict[str, dict], event: Optional[str], a: float, b: float, start: float,
          nodes_max: int = 8) -> dict:
    """Q134: who leads whom among the clusters' best members (and the event's signal): the lag of
    each pair, an edge A -> B only when B follows A clearly (a positive lag, no near-equal second
    peak, a match of 0.5 or more) and A changed first. "Leads", never "causes"."""
    from svcore.firstchange import lag
    picks = []
    for c in cl[:nodes_max]:
        best = next((i for i in c["ids"] if i != event and not by[i]["inRef"]), None) or next((i for i in c["ids"] if i != event), None)
        if best:
            picks.append(best)
    if event in by and event not in picks:
        picks.append(event)
    picks.sort(key=lambda i: by[i]["t"])
    sig: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    for i in picks:
        try:
            sig[i] = src.signal(i)
        except (KeyError, ValueError):
            pass
    L = b - a
    pad = max(L, a - start)
    edges = []
    for j, p in enumerate(picks):
        for q in picks[j + 1:]:
            if p not in sig or q not in sig or by[q]["t"] <= by[p]["t"]:
                continue
            r = lag(sig[p][0], sig[p][1], sig[q][0], sig[q][1], start - pad, b + pad, max_lag=pad)
            lg, rr = r.get("lag"), r.get("r")
            if (r.get("status") == "ok" and not r.get("weak") and not r.get("ambiguous")
                    and isinstance(lg, float) and isinstance(rr, float) and lg > 0 and abs(rr) >= 0.5):
                edges.append({"a": p, "b": q, "lag": lg, "r": rr})
    home = {i: c["first"] for c in cl for i in c["ids"]}
    return {"nodes": [{"id": i, "t": by[i]["t"], "cluster": home.get(i)} for i in picks], "edges": edges}


def suggest_condition(src: Source, sig_ids: List[str], a: float, b: float) -> dict:
    """"Find similar": of these signals, the one most unusual inside the selection [a, b] (its usual
    level read before it, as for "what changed first"), and a condition that finds stretches like
    it. States are left out: their own value is the condition."""
    import re
    from svcore.firstchange import default_baseline, fit_baseline, selection_change
    base = default_baseline(a, b)
    best: Optional[dict] = None
    for sid in dict.fromkeys(sig_ids):
        if _state_like(src, sid):
            continue
        try:
            t, y = src.signal(sid)
        except (KeyError, ValueError):
            continue
        r = selection_change(t, y, a, b, fit_baseline(base, a, float(np.min(t))) if len(t) else base)
        if r and np.isfinite(r["score"]) and (best is None or r["score"] > best["score"]):
            best = {"id": sid, "name": sid.partition("/")[2], **r}
    if best is None:
        return {"id": None}
    ref = best["name"] if re.match(r"^[A-Za-z_][\w.]*$", best["name"]) else "{" + best["name"] + "}"
    th = np.format_float_positional(float(f"{best['threshold']:.4g}"), trim="-")
    return {"id": best["id"], "name": best["name"], "up": best["up"], "score": best["score"],
            "text": f"{ref} {'>' if best['up'] else '<'} {th}"}


def lag_between(src: Source, a_id: str, b_id: str, t0: float, t1: float) -> dict:
    """How much later signal b follows signal a over [t0, t1] (cross-correlation)."""
    from svcore.firstchange import lag
    ta, ya = src.signal(a_id)
    tb, yb = src.signal(b_id)
    return lag(ta, ya, tb, yb, t0, t1)


# ------------------------------------------------------------------ the run at a glance / runs x conditions
def overview(src: Source, r, run_id: str, rows: Optional[List[str]] = None, wide: int = 300) -> dict:
    """Investigation step 7: a run's phases (its mode / phase signal) and automatic flags - stuck and
    saturated signals, gaps in the recording, spikes. `r` is the file's Run; files with more than
    `wide` signals are scanned on their first `wide` only (said in the result)."""
    from svcore import overview as ov
    names = list(r.signals)
    ph_name = ov.phase_signal([(n, bool(r.signals[n].labels)) for n in names])
    run_end = float(r.end_time + (r.time_offset or 0))
    phases: List[dict] = []
    if ph_name:
        t, y = src.signal(f"{run_id}/{ph_name}")
        phases = ov.phases(t, y, {str(k): v for k, v in (r.signals[ph_name].labels or {}).items()}, run_end)
    flags: List[dict] = []
    flags += ov.gaps(np.asarray(r.time) + float(r.time_offset or 0))
    scanned = 0
    for n in names[:wide]:
        sg = r.signals[n]
        if sg.labels or not getattr(sg, "loaded", True):
            continue
        try:
            t, y = src.signal(f"{run_id}/{n}")
        except (KeyError, ValueError):
            continue
        scanned += 1
        flags += ov.scan(n, t, y, src.discrete(f"{run_id}/{n}"))
    # rows the user put in the strip: each named state signal's stretches of one value
    row_out: Dict[str, List[dict]] = {}
    for n in rows or []:
        row_sig = r.signals.get(n)
        if row_sig is None:
            continue
        try:
            t, y = src.signal(f"{run_id}/{n}")
        except (KeyError, ValueError):
            continue
        row_out[n] = ov.phases(t, y, {str(k): v for k, v in (row_sig.labels or {}).items()}, run_end)[:5000]
    return {"phaseSignal": ph_name, "phases": phases, "rows": row_out, "flags": ov.rank(flags),
            "start": float(r.start_time + (r.time_offset or 0)), "end": run_end,
            "scanned": scanned, "partial": len(names) > wide}



def run_params(r, wide: int = 300) -> Dict[str, float]:
    """Investigation step 5: what tells a run apart - signals that hold one value the whole run (a
    payload, a gain, a seed) and numbers in its file name ("mass2.4", "wind=8", "run_012")."""
    import os
    import re
    token = re.compile(r"^([A-Za-z][A-Za-z]*)[=]?(-?\d+(?:\.\d+)?)$")
    ps: Dict[str, float] = {}
    stem = os.path.splitext(os.path.basename(r.file_path))[0]
    parts = [x for x in re.split(r"[_\s-]+", stem) if x]
    for i, part in enumerate(parts):
        m = token.match(part)
        if m:
            ps[m.group(1)] = float(m.group(2))
        elif i + 1 < len(parts) and re.fullmatch(r"-?\d+(?:\.\d+)?", parts[i + 1]) and part.isalpha():
            ps[part] = float(parts[i + 1])
    if len(r.signals) <= wide:
        for name, sg in r.signals.items():
            if sg.labels or not getattr(sg, "loaded", True):
                continue
            y = np.asarray(sg.data, dtype=np.float64)
            y = y[np.isfinite(y)]
            if len(y) > 1 and float(y.min()) == float(y.max()):
                ps[name] = float(y[0])
    return ps
