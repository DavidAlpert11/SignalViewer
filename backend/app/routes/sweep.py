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
        df = sweep.read_any(path)       # a table, or a folder of statistics files
    except sweep.SweepError as e:
        fail(400, str(e))
    except Exception as e:              # a parser's own message says what is wrong in the file
        fail(400, f"Could not read the table: {e}")
    return _register(df, path, os.path.basename(path.rstrip("/\\")), t0)


def _register(df, path: str, name: str, t0: float):
    cols = sweep.describe(df)
    tid = uuid.uuid4().hex[:12]
    _TABLES[tid] = {"df": df, "path": path, "stat": _stat(path) if path else None}
    while len(_TABLES) > MAX_TABLES:
        _TABLES.popitem(last=False)
    roles = {c["name"]: c["role"] for c in cols}
    return {"id": tid, "path": path, "name": name, "rows": int(len(df)), "columns": cols,
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
    key = json.dumps([q.get("roles"), q.get("holdValues"), q.get("derived"), q.get("exclude")], sort_keys=True, default=str)
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


class RowsReq(BaseModel):
    name: str
    columns: List[str]
    rows: List[List[Any]]


@router.post("/api/sweep/open-rows")
def sweep_open_rows(req: RowsReq):
    """A table from another part of the app (Runs x conditions): no file."""
    t0 = time.perf_counter()
    try:
        df = sweep.from_rows(req.columns, req.rows)
    except sweep.SweepError as e:
        fail(400, str(e))
    return _register(df, "", req.name, t0)


def _answer(req_id: str, q: Dict):
    p = _prepared(req_id, q)
    try:
        return p, sweep.answer(p, q)
    except (sweep.QuestionError, sweep.DerivedError, ValueError) as e:
        fail(400, str(e))


def _value(a: Dict, q: Dict):
    """The number a map or an effect is about: the goal's worst case, else the share holding."""
    return a["data"]["#goal"] if "#goal" in a["data"] else a["data"]["#holds"]


class MapReq(BaseModel):
    id: str
    question: Dict[str, Any]
    x: Optional[str] = None
    y: Optional[str] = None


@router.post("/api/sweep/effects")
def sweep_effects(req: MapReq):
    p, a = _answer(req.id, req.question)
    return sweep.effects(p, _value(a, req.question), a["data"]["#holds"])


@router.post("/api/sweep/map")
def sweep_map(req: MapReq):
    p, a = _answer(req.id, req.question)
    if req.x not in p.params or req.y not in p.params or req.x == req.y:
        fail(400, "Choose two different parameters.")
    v = _value(a, req.question)
    goal = req.question.get("goal") or {}
    if goal.get("direction") == "min":
        v = -v                                             # "best" is the largest of what is shown
    m = sweep.pair_map(p, req.x, req.y, v, a["data"]["#holds"])
    if goal.get("direction") == "min":
        m["best"] = [[None if x is None else -x for x in r] for r in m["best"]]
    return m


class SuggestReq(BaseModel):
    id: str
    question: Dict[str, Any]
    kinds: List[str]
    budget: int = 40


@router.post("/api/sweep/suggest")
def sweep_suggest(req: SuggestReq):
    p, a = _answer(req.id, req.question)
    kinds = [k for k in req.kinds if k in sweep.KINDS]
    goal = req.question.get("goal") or {}
    return sweep.suggest(p, a["data"]["#holds"], a["data"].get("#goal"), goal.get("direction", "max") != "min",
                         a["data"]["#partial"], kinds, max(1, min(2000, req.budget)))


class SuggestExportReq(BaseModel):
    id: str
    question: Dict[str, Any]
    params: List[Dict[str, Any]]
    path: str


@router.post("/api/sweep/suggest/export")
def sweep_suggest_export(req: SuggestExportReq):
    """New parameter sets x every kept combination of the must-hold-across columns, as a run list."""
    p = _prepared(req.id, req.question)
    combos = p.df[p.holds].drop_duplicates().to_dict("records") if p.holds else [{}]
    rows = [{**ps, **cb} for ps in req.params for cb in combos]
    path = os.path.abspath(os.path.expanduser(req.path))
    try:
        sweep.write_csv(path, rows, p.params + p.holds)
    except OSError as e:
        fail(400, f"Could not write {path}: {e}")
    return {"path": path, "rows": len(rows)}


@router.post("/api/sweep/suspects")
def sweep_suspects(req: QuestionReq):
    q = {**req.question, "exclude": []}                    # look at every run, the left-out ones too
    return {"suspects": sweep.suspects(_prepared(req.id, q))}


class CompareReq(BaseModel):
    a: QuestionReq
    b: QuestionReq


@router.post("/api/sweep/compare")
def sweep_compare(req: CompareReq):
    pa, a = _answer(req.a.id, req.a.question)
    pb, b = _answer(req.b.id, req.b.question)
    try:
        return sweep.compare(pa, a, pb, b)
    except ValueError as e:
        fail(400, str(e))


class TextReq(BaseModel):
    path: str
    text: Optional[str] = None


@router.post("/api/sweep/save-text")
def sweep_save_text(req: TextReq):
    """A study (.svsweep) or a report (.html) the page made."""
    path = os.path.abspath(os.path.expanduser(req.path))
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(req.text or "")
    except OSError as e:
        fail(400, f"Could not write {path}: {e}")
    return {"path": path}


@router.post("/api/sweep/load-text")
def sweep_load_text(req: TextReq):
    path = os.path.abspath(os.path.expanduser(req.path))
    try:
        with open(path, encoding="utf-8") as f:
            return {"path": path, "text": f.read()}
    except OSError as e:
        fail(400, f"Could not read {path}: {e}")


# ----------------------------------------------------------------------------- following the file
@router.post("/api/sweep/reload")
def sweep_reload(req: OpenReq):
    """Read the table of an open study again (the file changed): the same id, so the study's question
    and view stay; the page asks its question again."""
    t = _get(req.path)                                     # here `path` carries the table id
    if not t.get("path"):
        fail(400, "This table did not come from a file.")
    t0 = time.perf_counter()
    try:
        df = sweep.read_any(t["path"])
    except Exception as e:
        fail(400, f"Could not read the table again: {e}")
    t["df"], t["prepKey"], t["prep"] = df, None, None
    t["stat"] = _stat(t["path"])
    cols = sweep.describe(df)
    return {"id": req.path, "path": t["path"], "name": os.path.basename(t["path"].rstrip("/\\\\")), "rows": int(len(df)),
            "columns": cols, "head": sweep.head(df), "summary": sweep.summary(df, {c["name"]: c["role"] for c in cols}),
            "seconds": round(time.perf_counter() - t0, 3)}


def _stat(path: str):
    """What says a table changed: its size and time - for a folder, of every table file in it."""
    try:
        if os.path.isdir(path):
            return [(n, os.stat(os.path.join(path, n)).st_mtime_ns, os.stat(os.path.join(path, n)).st_size)
                    for n in sorted(os.listdir(path)) if n.lower().endswith(sweep.io.TABLE_EXTS)]
        st = os.stat(path)
        return [st.st_mtime_ns, st.st_size]
    except OSError:
        return None


@router.get("/api/sweep/changed")
def sweep_changed(id: str):
    t = _get(id)
    if not t.get("path"):
        return {"changed": False}
    now = _stat(t["path"])
    if "stat" not in t:
        t["stat"] = now
    return {"changed": now is not None and now != t["stat"], "missing": now is None}


# ----------------------------------------------------------------------------- templates
TEMPLATES = os.path.join(os.path.expanduser("~"), ".signalviewer", "sweep_templates")


class TemplateReq(BaseModel):
    name: str
    template: Optional[Dict[str, Any]] = None


def _tpl_path(name: str) -> str:
    safe = "".join(ch for ch in name.strip() if ch not in '\\\\/:*?"<>|').strip() or "template"
    return os.path.join(TEMPLATES, safe + ".json")


@router.get("/api/sweep/templates")
def sweep_templates():
    out = []
    if os.path.isdir(TEMPLATES):
        for n in sorted(os.listdir(TEMPLATES)):
            if n.endswith(".json"):
                try:
                    with open(os.path.join(TEMPLATES, n), encoding="utf-8") as f:
                        out.append(json.load(f))
                except (OSError, ValueError):
                    continue
    return {"templates": out, "folder": TEMPLATES}


@router.post("/api/sweep/templates/save")
def sweep_template_save(req: TemplateReq):
    os.makedirs(TEMPLATES, exist_ok=True)
    tpl = {**(req.template or {}), "name": req.name.strip()}
    with open(_tpl_path(req.name), "w", encoding="utf-8") as f:
        json.dump(tpl, f, indent=1)
    return sweep_templates()


@router.post("/api/sweep/templates/delete")
def sweep_template_delete(req: TemplateReq):
    p = _tpl_path(req.name)
    if os.path.isfile(p):
        os.remove(p)
    return sweep_templates()
