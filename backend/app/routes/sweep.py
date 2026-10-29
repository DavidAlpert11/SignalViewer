"""Sweeps (the run-envelope area): open a results table, describe its columns, and the shape of
the study for a set of roles (svcore/sweep.py). Tables stay here; the page gets descriptions,
counts and - later - what it draws."""
import os
import time
import uuid
from collections import OrderedDict
from typing import Dict

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
