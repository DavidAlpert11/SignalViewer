"""Compare runs: similarity, the comparison table, time shift, sync suggestions."""

import asyncio
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.common import atomic_write, fail
from app.routes.data import _windowed
from app.store import store
from svcore.compare import auto_shift
from svcore.compare import compare as compare_runs
from svcore.ops import compute_signal_stats
from svcore.sync import suggest as sync_suggest_fn
from svcore import tolerances as tolmod

router = APIRouter()




# =============================================================================
# COMPARE (phase 4)
# =============================================================================

class CompareRequest(BaseModel):
    signals: List[str]               # the same signal in several runs
    baseline: str = "mean"           # a signal id from `signals`, or "mean"
    alignment: str = "linear"
    tolAbs: Optional[float] = None
    tolPct: Optional[float] = None
    tolTime: Optional[float] = None  # 1.21: seconds a run may be early / late (Simulink Data Inspector)
    windows: Optional[Dict[str, List[float]]] = None    # T10b: per run [t0, t1] - compared on time since t0
    trace: int = 0                   # U5: > 0 - each run's difference over time (about this many points) with the band
    tolerances: Optional[Dict[str, Any]] = None   # 26.U5: cli compare's tolerances file (replaces tolAbs / tolPct / tolTime)


def _tolerances(req) -> Dict[str, Any]:
    """26.U5: the request's tolerances - the file's format, or the older one-tolerance fields."""
    try:
        return tolmod.parse(req.tolerances) if req.tolerances is not None else tolmod.from_fields(req.tolAbs, req.tolPct, req.tolTime)
    except ValueError as e:
        fail(400, f"Tolerances: {e}.")


def _judged(r: Dict[str, Any], t: Dict[str, Any]) -> Dict[str, Any]:
    """compare_runs' result with each row's pass by the tolerance rule (outside_pct, skip) - as cli compare."""
    for row in r["rows"]:
        if not row.get("valid"):
            continue
        ok, outside = tolmod.judge(row, t)
        if ok is None:
            row.pop("pass", None)
        else:
            row["pass"], row["outsidePct"] = ok, outside
    r["tol"] = t
    return r



@router.post("/api/compare")
def compare(req: CompareRequest):
    try:
        series = [(sid, *_windowed(sid, req.windows)) for sid in req.signals]
        base = req.baseline if req.baseline in req.signals else req.signals[0]
        t = tolmod.for_signal(_tolerances(req), base.split("/", 1)[-1])     # the row's name is the baseline's
        lim = (t.get("abs"), t.get("pct"), t.get("time")) if not t.get("skip") else (None, None, None)
        return _judged(compare_runs(series, req.baseline, req.alignment, lim[0], lim[1], tol_time=lim[2],
                                    trace=min(max(req.trace, 0), 4000)), t)
    except KeyError:
        fail(404, "One of the chosen signals is no longer open.")
    except ValueError as e:
        fail(400, str(e))
    except IndexError:
        fail(400, "A run has no samples of this signal inside its segment.")



class CompareAllRequest(BaseModel):
    points: int = 50_000              # per signal; the similarity list asks for fewer
    runs: List[str]
    baselineRun: str = "mean"        # a run id, or "mean"
    alignment: str = "linear"
    tolAbs: Optional[float] = None
    tolPct: Optional[float] = None
    tolTime: Optional[float] = None
    windows: Optional[Dict[str, List[float]]] = None    # T10b: per run [t0, t1] - compared on time since t0
    tolerances: Optional[Dict[str, Any]] = None   # 26.U5: cli compare's tolerances file (replaces tolAbs / tolPct / tolTime)



def compare_table(ca: "CompareAllRequest", progress=None) -> list:
    """Every signal name present in AT LEAST TWO of the chosen files: the spread between
    files (mean, std), the differences against the baseline (RMS, max, mean, std of the
    difference, correlation, tolerance) and per-file statistics over the common time range."""
    from collections import OrderedDict
    from svcore.naming import without_unit
    # C13: a signal matches across files by its name, with or without its unit ("ATT.Roll" in a
    # simulation's .mat, "ATT.Roll [deg]" in the flight log) when that bare name is one signal in each
    # file; "sigs" says which signal of each file a row is (the name shown is the baseline's)
    present: "OrderedDict[str, Dict[str, str]]" = OrderedDict()
    for rid in ca.runs:
        names_of = list(store.get(rid).run.signals.keys())
        bare_count: Dict[str, int] = {}
        for nm in names_of:
            bare_count[without_unit(nm)] = bare_count.get(without_unit(nm), 0) + 1
        for nm in names_of:
            key = without_unit(nm) if bare_count[without_unit(nm)] == 1 else nm
            present.setdefault(key, {})[rid] = nm
    groups = [g for g in present.values() if len(g) >= 2]
    tol = _tolerances(ca)
    out: list = []
    for k, sigs in enumerate(groups):
        rids = list(sigs)
        name = sigs.get(ca.baselineRun) or sigs[rids[0]]
        ids = [f"{rid}/{sigs[rid]}" for rid in rids]
        base = f"{ca.baselineRun}/{sigs[ca.baselineRun]}" if ca.baselineRun in rids else "mean"
        tkey = tolmod.entry_key(tol, name)
        stol = tolmod.for_signal(tol, name, tkey)
        lim = (stol.get("abs"), stol.get("pct"), stol.get("time")) if not stol.get("skip") else (None, None, None)
        try:
            r = _judged(compare_runs([(sid, *_windowed(sid, ca.windows)) for sid in ids], base, ca.alignment, lim[0], lim[1],
                                     int(max(2_000, min(ca.points, 200_000))), tol_time=lim[2]), stol)
        except (ValueError, IndexError) as e:       # IndexError: no sample inside a run's segment
            out.append({"name": name, "runs": rids, "sigs": sigs, "error": str(e) or "No samples in the segment."})
            continue
        lo, hi = r["overlap"]
        files: List[Dict[str, Any]] = []
        for rid, sid in zip(rids, ids):
            t, y = _windowed(sid, ca.windows)
            st = compute_signal_stats(t, y, lo, hi)
            files.append({"run": rid, "mean": st.get("mean"), "std": st.get("std"), "min": st.get("min"),
                          "max": st.get("max"), "rms": st.get("rms")})
        diffs = [{"run": x["id"].split("/")[0], **{kk: x.get(kk) for kk in
                  ("rmsDiff", "rmsPct", "matchPct", "maxAbsDiff", "meanDiff", "stdDiff", "correlation", "withinPct", "pass", "outsidePct")}}
                 for x in r["rows"] if x.get("valid")]
        worst = max((x for x in r["rows"] if x.get("valid")), key=lambda x: x["rmsPct"], default=None)
        means = [f["mean"] for f in files if f["mean"] is not None]
        stds = [f["std"] for f in files if f["std"] is not None]
        out.append({
            "name": name, "runs": rids, "sigs": sigs, "baseline": "mean" if base == "mean" else ca.baselineRun,
            "meanSpread": (max(means) - min(means)) if means else None,
            "stdSpread": (max(stds) - min(stds)) if stds else None,
            "worstRmsDiff": max((d["rmsDiff"] for d in diffs), default=None),
            "worstRmsPct": max((d["rmsPct"] for d in diffs), default=None),
            "matchPct": min((d["matchPct"] for d in diffs), default=None),          # the least similar file
            "profile": worst.get("profile") if worst else None,                     # where it diverges
            "worstMaxAbs": max((d["maxAbsDiff"] for d in diffs), default=None),
            "minCorrelation": min((d["correlation"] for d in diffs), default=None),
            "pass": all(d["pass"] for d in diffs if d.get("pass") is not None) if any(d.get("pass") is not None for d in diffs) else None,
            # 26.U5: the tolerance this signal is judged by, and the entry of its own (None: the default)
            "tol": stol, "tolKey": tkey, "skipped": bool(stol.get("skip")),
            "files": files, "diffs": diffs,
        })
        if progress:
            progress((k + 1) / max(1, len(groups)), name)
    out.sort(key=lambda x: -(x.get("worstRmsPct") or -1))
    return out



@router.post("/api/compare/all")
async def compare_all(req: CompareAllRequest):
    try:
        return {"signals": await asyncio.to_thread(compare_table, req)}
    except KeyError:
        fail(404, "One of the chosen files is no longer open.")



class ShiftRequest(BaseModel):
    base: str
    other: str



@router.post("/api/compare/shift")
def compare_shift(req: ShiftRequest):
    try:
        return {"shift": auto_shift(store.signal(req.base), store.signal(req.other))}
    except KeyError:
        fail(404, "One of the chosen signals is no longer open.")



class SyncRequest(BaseModel):
    ref: str                       # the reference file (its time stays)
    other: str                     # the file to move
    refSignal: Optional[str] = None     # optional: a signal pair to correlate (names)
    otherSignal: Optional[str] = None
    feature: Optional[dict] = None      # with the pair: align a recognised moment {kind, levelPct, occurrence}
    maxLag: Optional[float] = None      # with the pair: search only within +-maxLag s of the current alignment



@router.post("/api/sync/suggest")
async def sync_suggest(req: SyncRequest):
    """Ways to align two recordings of the same flight (boot clock, matching events, signal
    correlation), each with the time offset to give the other file."""
    a, b = store.runs.get(req.ref), store.runs.get(req.other)
    if a is None or b is None:
        fail(404, "File is no longer open.")
    cands = await asyncio.to_thread(sync_suggest_fn, a.run, b.run, req.refSignal, req.otherSignal, req.feature, req.maxLag)
    return {"candidates": cands}


# =============================================================================
# 26.U5: the tolerances file (the format `signalviewer-cli compare --tolerances` reads)
# =============================================================================

class TolFile(BaseModel):
    path: str
    tolerances: Optional[Dict[str, Any]] = None


@router.post("/api/compare/tolerances/load")
def tolerances_load(req: TolFile):
    import json
    path = os.path.abspath(os.path.expanduser(req.path))
    try:
        with open(path, encoding="utf-8-sig") as f:
            d = json.load(f)
    except OSError as e:
        fail(400, f"Cannot read the tolerances file {path}: {e.strerror or e}.")
    except ValueError as e:
        fail(400, f"The tolerances file {path} is not valid JSON: {e}.")
    try:
        return {"path": path, "tolerances": tolmod.parse(d)}
    except ValueError as e:
        fail(400, f"{os.path.basename(path)}: {e}.")


@router.post("/api/compare/tolerances/save")
def tolerances_save(req: TolFile):
    import json
    from app.routes.export import _check_target
    try:
        t = tolmod.parse(req.tolerances)
    except ValueError as e:
        fail(400, f"Tolerances: {e}.")
    path = _check_target(req.path, ".json")
    atomic_write(path, json.dumps(t, indent=2, ensure_ascii=False) + "\n", "utf-8", "")
    return {"path": path}
