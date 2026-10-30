"""Sweeps (the run-envelope area): open a results table, describe its columns, and the shape of
the study for a set of roles (svcore/sweep.py). Tables stay here; the page gets descriptions,
counts and - later - what it draws."""
import json
import os
import time
import uuid
from collections import OrderedDict
from typing import Any, Dict, List, Optional


from fastapi import APIRouter
from pydantic import BaseModel

from app.common import fail
from app.routes.fs import EXAMPLES
from svcore import sweep

router = APIRouter()

# open tables, the newest last; a few at most (a big table is hundreds of MB in memory)
_TABLES: "OrderedDict[str, Dict]" = OrderedDict()
MAX_TABLES = 3


class OpenReq(BaseModel):
    path: str


class SummaryReq(BaseModel):
    id: str
    roles: Dict[str, str]


class QuestionReq(BaseModel):
    id: str
    question: Dict[str, Any]
    runs: bool = False                  # also every run (a line per run), not only per set
    columns: Optional[List[str]] = None  # runs: which columns (default: every used one)


class SetReq(BaseModel):
    id: str
    question: Dict[str, Any]
    set: int


class ExportReq(BaseModel):
    id: str
    question: Dict[str, Any]
    sets: List[int]
    onlyMissing: bool = False
    path: str


def _get(tid: str) -> Dict:
    t = _TABLES.get(tid)
    if t is None:
        fail(404, "This table is no longer open - open it again.")
    _TABLES.move_to_end(tid)
    return t


@router.post("/api/sweep/open")
def sweep_open(req: OpenReq):
    path = os.path.abspath(os.path.expanduser(req.path))
    t0 = time.perf_counter()
    try:
        df = sweep.read_table(path)
    except sweep.SweepError as e:
        fail(400, str(e))
    except Exception as e:              # a parser's own message says what is wrong in the file
        fail(400, f"Could not read the table: {e}")
    cols = sweep.describe(df)
    tid = uuid.uuid4().hex[:12]
    _TABLES[tid] = {"df": df, "path": path}
    while len(_TABLES) > MAX_TABLES:
        _TABLES.popitem(last=False)
    roles = {c["name"]: c["role"] for c in cols}
    return {"id": tid, "path": path, "name": os.path.basename(path), "rows": int(len(df)), "columns": cols,
            "head": sweep.head(df), "summary": sweep.summary(df, roles), "seconds": round(time.perf_counter() - t0, 3)}


@router.post("/api/sweep/summary")
def sweep_summary(req: SummaryReq):
    bad = [r for r in req.roles.values() if r not in sweep.ROLES]
    if bad:
        fail(400, f"Unknown role: {bad[0]}")
    return sweep.summary(_get(req.id)["df"], req.roles)


@router.get("/api/sweep/example")
def sweep_example():
    p = os.path.abspath(os.path.join(EXAMPLES, "sweeps", "sweep_payload.csv"))
    if not os.path.isfile(p):
        fail(404, "The example table is not installed.")
    return {"path": p}


def _prepared(tid: str, q: Dict):
    """The prepared table for a question; kept while roles, kept values and new columns stay the
    same (a new goal or condition does not read the table again)."""
    t = _get(tid)
    key = json.dumps([q.get("roles"), q.get("holdValues"), q.get("derived")], sort_keys=True, default=str)
    if t.get("prepKey") != key:
        try:
            t["prep"] = sweep.prepare(t["df"], q)
        except (sweep.QuestionError, sweep.DerivedError) as e:
            fail(400, str(e))
        t["prepKey"] = key
    return t["prep"]


def _enc(meta, data):
    return [{**m, **sweep.encode(data[m["name"]])} for m in meta]


@router.post("/api/sweep/evaluate")
def sweep_evaluate(req: QuestionReq):
    t0 = time.perf_counter()
    p = _prepared(req.id, req.question)
    try:
        a = sweep.answer(p, req.question)
    except (sweep.QuestionError, sweep.DerivedError, ValueError) as e:
        fail(400, str(e))
    out = {"counts": a["counts"], "conditions": a["conditions"], "sets": _enc(a["columns"], a["data"])}
    if req.runs:
        r = sweep.run_rows(p, a["data"]["#holds"])
        idx = r["index"]
        names = req.columns or (p.params + p.holds + p.outputs)
        cols = [{"name": c, **sweep.encode(p.df[c].iloc[idx].reset_index(drop=True))} for c in names if c in p.df.columns]
        cols.append({"name": "#set", **sweep.encode(r["set"].astype(float))})
        cols.append({"name": "#holds", **sweep.encode(r["holds"])})
        out["runs"] = {"columns": cols, "sampled": r["sampled"], "total": r["total"], "n": int(len(idx))}
    out["seconds"] = round(time.perf_counter() - t0, 3)
    return out


@router.post("/api/sweep/set")
def sweep_set(req: SetReq):
    p = _prepared(req.id, req.question)
    try:
        return sweep.set_rows(p, req.question, req.set)
    except (sweep.QuestionError, ValueError) as e:
        fail(400, str(e))


@router.post("/api/sweep/export")
def sweep_export(req: ExportReq):
    p = _prepared(req.id, req.question)
    rows = sweep.rerun_rows(p, req.sets, req.onlyMissing)
    path = os.path.abspath(os.path.expanduser(req.path))
    try:
        sweep.write_csv(path, rows, p.params + p.holds)
    except OSError as e:
        fail(400, f"Could not write {path}: {e}")
    return {"path": path, "rows": len(rows)}
