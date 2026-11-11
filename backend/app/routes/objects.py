"""
L12: map objects over REST (local, 127.0.0.1 only, like every route) - the same rules and numbers as the app's
dialogs, the Python API (signalviewer) and the command line: svcore/objects.py (detection, from the shared
table), svcore/objcompare.py (the comparison), svcore/similar.py (similar signals). /api/docs is the reference;
docs/api.md walks the whole process with curl.
"""
from typing import Dict, List, Optional

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.common import fail
from app.store import store

router = APIRouter()


class DetectRequest(BaseModel):
    runs: Optional[List[str]] = Field(None, description="Open files (run ids) to look in; absent: every open file except the derived one.")
    all: bool = Field(False, description="Also the objects *Add all* would not add (a local position with no origin, one in cm...).")


def _runs(ids: Optional[List[str]]) -> List[str]:
    if ids:
        for r in ids:
            if r not in store.runs:
                fail(404, f"No open file with id {r!r}.")
        return list(ids)
    return [r for r in store.runs if r != "derived"]


def _detect(rid: str) -> Dict:
    from svcore.objects import detect
    lr = store.get(rid)
    return detect([(f"{rid}/{n}", n) for n in lr.run.signals], rid, lr.name)


@router.post("/api/objects/detect")
def objects_detect(req: DetectRequest):
    """The map objects found in each file, best first - name, class, frame, origin, the signals of each role and
    why (rule, word, sub-group / paired group), as the app's suggestion bar and *Why?*."""
    from svcore.objects import addable
    out = []
    for rid in _runs(req.runs):
        d = _detect(rid)
        out.append({"run": rid, "name": store.get(rid).name,
                    "objects": [{**c, "addable": addable(c)} for c in d["candidates"] if req.all or addable(c)],
                    "incomplete": d["incomplete"], "nearMisses": d["nearMisses"]})
    return {"files": out}


class CompareRequest(BaseModel):
    runs: Optional[List[str]] = Field(None, description="The files the objects are in (several: an object named \"file:name\" where two files share a name); absent: every open file.")
    reference: str = Field(..., description="The reference object's name (as /api/objects/detect gives it), e.g. \"POS\".")
    objects: Optional[List[str]] = Field(None, description="The objects compared with it; absent: every other object.")
    what: List[str] = Field(["position", "velocity", "attitude"], description="Any of position, velocity, attitude.")
    frame: str = Field("ned", description="ned, enu, ecef, lla (north / east / up) or track (along / cross / up).")
    points: int = Field(2000, ge=0, le=200000, description="Values and errors decimated to about this many points each for display (0: none returned); the statistics are always on the full data.")
    csv: Optional[str] = Field(None, description="Also write the errors (full resolution, one time base) to this .csv file.")


def _objects(rids: List[str]):
    """One signal reader and the objects of several files - the Python API's naming (signalviewer._objects_of)."""
    cands = [(rid, c) for rid in rids for c in _detect(rid)["candidates"]]
    names = [c["name"] for _, c in cands]
    out = []
    for rid, c in cands:
        c = dict(c)
        if len(rids) > 1 and names.count(c["name"]) > 1:
            c["name"] = f"{store.get(rid).name}:{c['name']}"
        out.append(c)

    def sig(sid):
        t, y = store.signal(sid)
        return np.asarray(t, dtype=np.float64), np.asarray(y, dtype=np.float64)
    return sig, out


def _thin(t, y, n):
    if n <= 0:
        return None
    if len(t) > n:
        idx = np.unique(np.linspace(0, len(t) - 1, n).astype(int))
        t, y = t[idx], y[idx]
    f = lambda a: [None if not np.isfinite(v) else float(v) for v in a]
    return {"t": f(t), "y": f(y)}


@router.post("/api/objects/compare")
def objects_compare(req: CompareRequest):
    """*Compare objects…* (L8): each object against the reference - values and errors (decimated for display), the
    errors' statistics on the full data (rms, mean, max_abs, p95_abs, t_max_abs, samples), what was left out and why."""
    from svcore.objcompare import compare
    sig, objs = _objects(_runs(req.runs))
    try:
        res = compare(sig, objs, req.reference, req.objects, req.what, req.frame)
    except KeyError as e:
        fail(404, str(e.args[0] if e.args else e))
    except ValueError as e:
        fail(400, str(e))
    if req.csv:
        from app.routes.export import _check_target
        from signalviewer import Comparison
        path = _check_target(req.csv, ".csv")
        Comparison(res).to_csv(path)
    pack = lambda d: {q: {o: {c: _thin(t, y, req.points) for c, (t, y) in comps.items()} for o, comps in objs_.items()} for q, objs_ in d.items()}
    return {"reference": res["reference"], "frame": res["frame"], "stats": res["stats"], "reasons": res["reasons"],
            "left_out": res["left_out"], **({"values": pack(res["values"]), "errors": pack(res["errors"])} if req.points else {}),
            **({"csv": req.csv} if req.csv else {})}


class SimilarRequest(BaseModel):
    run: str = Field(..., description="The open file (run id).")
    loose: bool = Field(False, description="Also a segment 1-2 letters apart, or the same last name under different parents.")


@router.post("/api/objects/similar")
def objects_similar(req: SimilarRequest):
    """*Compare with similar…* (L9): the families of signals of one file whose names differ in one segment."""
    from svcore.similar import families
    if req.run not in store.runs:
        fail(404, f"No open file with id {req.run!r}.")
    run = store.get(req.run).run
    return {"families": families([(f"{req.run}/{n}", n) for n in run.signals], req.loose)}
