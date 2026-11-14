"""W14 / W15: one parameter set for many sweep tables, and the next runs to try - the study file's
routes (svcore/study.py). Owned by lane L3; the shapes are the W0 contract (tests/fixtures/sweeps/,
backend/tests/test_study_contract.py)."""
import glob
import json
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.common import fail
from svcore import study as studies
from svcore import sweeps_common, sweeps_next

router = APIRouter()
FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "..", "tests", "fixtures", "sweeps")


class StudyReq(BaseModel):
    study_path: Optional[str] = None       # a saved .svstudy.json
    study: Optional[Dict[str, Any]] = None  # or the panel's study as it is now (unsaved edits); relative paths
                                           # are then read against study_path's folder (or `folder`)
    folder: Optional[str] = None
    write: bool = False                    # next-runs: write the round's files and the history (as `study next`)


def study_of(req: StudyReq) -> studies.Study:
    """The study a request names: its dict (with the saved file's place for relative paths) or the file."""
    try:
        if req.study is not None:
            base = req.study_path or (os.path.join(req.folder, "study" + studies.STUDY_SUFFIX) if req.folder else "")
            return studies.loads(json.dumps(req.study), os.path.abspath(base) if base else "")
        if req.study_path:
            return studies.load(req.study_path)
    except (OSError, ValueError) as e:
        fail(400, f"The study could not be read: {e}")
    fail(400, "No study: send study_path or study.")


def _fixture(name: str) -> dict:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


@router.post("/api/sweeps/common")
def common(req: StudyReq):
    """W14: the ranked table of the shared values (svcore/sweeps_common.py)."""
    s = study_of(req)
    try:
        return sweeps_common.rank(s)
    except sweeps_common.StudyError as e:
        fail(400, str(e))


@router.post("/api/sweeps/next-runs")
def next_runs(req: StudyReq):
    """W15: the next batch of candidate values of S, expanded to their runs; `write` also writes the round's
    files and the history into the saved study (as `study next`)."""
    s = study_of(req)
    if req.write and not s.path:
        fail(400, "Save the study first: the round's files are written next to it.")
    try:
        return sweeps_next.next_runs(s, write=req.write)
    except sweeps_common.StudyError as e:
        fail(400, str(e))


class MappingReq(BaseModel):
    paths: Dict[str, List[str]]            # table id -> its files (or globs), absolute


@router.post("/api/sweeps/mapping")
def mapping(req: MappingReq):
    """W14: the columns of each table, the names proposed to pair across tables, and the guessed roles."""
    cols: Dict[str, List[str]] = {}
    roles: Dict[str, Dict[str, str]] = {}
    for tid, paths in req.paths.items():
        files = sorted({f for p in paths for f in (glob.glob(p) if any(c in p for c in "*?[") else [p]) if os.path.isfile(f)})
        if not files:
            fail(400, f"Table {tid}: no file found ({', '.join(paths)}).")
        df = sweeps_common.read_table_files(files[:1])
        cols[tid] = [str(c) for c in df.columns]
        roles[tid] = sweeps_common.guessed_roles(df)
    return {"columns": cols, "roles": roles, "mapping": sweeps_common.propose_mapping(cols)}


class SaveReq(BaseModel):
    path: str
    study: Dict[str, Any]


@router.post("/api/sweeps/study/save")
def save_study(req: SaveReq):
    """W14: write the panel's study to a .svstudy.json (unknown keys kept)."""
    path = req.path if req.path.endswith(studies.STUDY_SUFFIX) else req.path + studies.STUDY_SUFFIX
    try:
        s = studies.loads(json.dumps(req.study), os.path.abspath(path))
        return {"path": studies.save(s)}
    except (OSError, ValueError) as e:
        fail(400, f"The study could not be saved: {e}")


@router.post("/api/sweeps/study/open")
def open_study(req: StudyReq):
    """W14: a saved study as the panel edits it (defaults filled in), with its path."""
    s = study_of(req)
    return {"path": s.path, "study": studies.to_dict(s)}


@router.get("/api/sweeps/study/tables")
def study_tables(study_path: str, since: Optional[float] = None):
    """C2: each table's files grouped by round (rows counted once per file version), and the history's rounds -
    the navigator's Tables, polled with the loop's progress. A demo study is listed from its work folder."""
    s = study_of(StudyReq(study_path=study_path))
    if s.demo is not None:
        from svcore import demo
        work = os.path.join(demo.workdir(s.path), os.path.basename(s.path))
        if os.path.isfile(work) and os.path.abspath(work) != os.path.abspath(s.path):
            s = study_of(StudyReq(study_path=work))
    return {**sweeps_common.tables_by_round(s, since), "demo_work": s.path if s.demo is not None else None}


class FromTableReq(BaseModel):
    id: Optional[str] = None               # an open table of the Sweeps area (/api/sweep/open)
    path: Optional[str] = None             # or a file
    roles: Optional[Dict[str, str]] = None  # the area's roles as set on the table (param / hold / output / ...)


@router.post("/api/sweeps/setup/from-table")
def setup_from_table(req: FromTableReq):
    """C2: *I have results* - the study's set-up guessed from a table: parameters (range, values seen),
    scenarios, outputs, and the study's `shared` / `search` / roles for it."""
    if req.id:
        from app.routes.sweep import _get
        df = _get(req.id)["df"]
    elif req.path:
        try:
            df = sweeps_common.read_table_files([os.path.abspath(os.path.expanduser(req.path))])
        except sweeps_common.StudyError as e:
            fail(400, str(e))
    else:
        fail(400, "No table: send the open table's id or a file's path.")
    return sweeps_common.setup_from_table(df, req.roles)


class RunsReq(StudyReq):
    table: str
    rows: List[int]


@router.post("/api/sweeps/common/runs")
def common_runs(req: RunsReq):
    """W14: the runs of one value in one table (row indices from /api/sweeps/common), as the table has them -
    what the panel shows when a ranked row is opened."""
    s = study_of(req)
    try:
        t = s.table(req.table)
        df = sweeps_common.read_table_files(s.table_files(t)).rename(columns=t.rename)
    except (KeyError, sweeps_common.StudyError) as e:
        fail(400, str(e))
    rows = [r for r in req.rows if 0 <= r < len(df)][:500]
    sub = df.iloc[rows]
    cols = [str(c) for c in sub.columns]
    return {"table": t.id, "columns": cols,
            "rows": [[None if (isinstance(v, float) and v != v) else (v.item() if hasattr(v, "item") else v) for v in r]
                     for r in sub.itertuples(index=False, name=None)]}


class ExportReq(StudyReq):
    path: str


@router.post("/api/sweeps/common/export")
def common_export(req: ExportReq):
    """W14: the ranked table as a CSV (one row per value, a group of columns per table)."""
    s = study_of(req)
    try:
        df = sweeps_common.to_csv_rows(sweeps_common.rank(s))
    except sweeps_common.StudyError as e:
        fail(400, str(e))
    path = req.path if req.path.lower().endswith(".csv") else req.path + ".csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return {"path": path, "rows": int(len(df))}
