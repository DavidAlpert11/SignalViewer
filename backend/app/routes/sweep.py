"""Sweeps (the run-envelope area): open a results table, describe its columns, and the shape of
the study for a set of roles (svcore/sweep.py). Tables stay here; the page gets descriptions,
counts and - later - what it draws."""
import csv
import json
import os
import time
import uuid
from collections import OrderedDict
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from app.common import SWEEP_AUTOSAVE, atomic_open, atomic_path, atomic_write, fail, read_autosave, write_autosave
from app.routes.fs import EXAMPLES
from svcore import sweep

router = APIRouter()

# open tables, the newest last; a few at most (a big table is hundreds of MB in memory). Since the
# Data step keeps each table of a study apart (2026-11-02) a study holds several; the page drops the
# ones it closes (/api/sweep/drop), and the least recently used go first when there are too many.
_TABLES: "OrderedDict[str, Dict]" = OrderedDict()
MAX_TABLES = 12


class OpenReq(BaseModel):
    path: str


class SummaryReq(BaseModel):
    id: str
    roles: Dict[str, str]
    holdValues: Optional[Dict[str, List[Any]]] = None   # only the runs of these condition values


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
    extra: List[Dict[str, Any]] = []     # [{params, holds}]: a set for some condition values only (Split by)


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


def _register(df, path: str, name: str, t0: float, recipe: Optional[Dict] = None):
    cols = sweep.describe(df)
    tid = uuid.uuid4().hex[:12]
    recipe = recipe if recipe is not None else ({"path": path} if path else {})
    _TABLES[tid] = {"df": df, "path": path, "stat": _stat(path) if path else None, "recipe": recipe,
                    "stats": {f: _stat(f) for f in sweep.recipe_files(recipe)}}
    while len(_TABLES) > MAX_TABLES:
        _TABLES.popitem(last=False)
    roles = {c["name"]: c["role"] for c in cols}
    return {"id": tid, "path": path, "name": name, "rows": int(len(df)), "columns": cols, "recipe": recipe,
            "head": sweep.head(df), "summary": sweep.summary(df, roles), "seconds": round(time.perf_counter() - t0, 3)}


def _recipe(t: Dict) -> Dict:
    """How a table was made: a merged table's recipe, or its file with what was merged into it in place."""
    r = t.get("recipe") or {}
    if "merge" in r:
        return r
    return {"path": t.get("path") or "", "merged": [{"path": m["path"], "keys": m["keys"], "prefer": m["prefer"]} for m in t.get("merged", [])]}


@router.post("/api/sweep/summary")
def sweep_summary(req: SummaryReq):
    bad = [r for r in req.roles.values() if r not in sweep.ROLES]
    if bad:
        fail(400, f"Unknown role: {bad[0]}")
    df = _get(req.id)["df"]
    total = int(len(df))
    holds = {c: v for c, v in (req.holdValues or {}).items() if v and req.roles.get(c) == "hold" and c in df.columns}
    if holds:                                            # the runs the conditions' values keep ("640 of 1,922")
        from svcore.sweep.derived import hold_mask
        keep = hold_mask(df, holds)
        if keep is not None:
            df = df[keep]
    return {**sweep.summary(df, req.roles), "rowsAll": total}


@router.get("/api/sweep/example")
def sweep_example():
    """The example (a drone's roll controller tuned over wind, payload and gusts) and its second,
    finer sweep - to try merging."""
    p = os.path.abspath(os.path.join(EXAMPLES, "sweeps", "drone_tuning.csv"))
    if not os.path.isfile(p):
        fail(404, "The example table is not installed.")
    return {"path": p, "refine": p.replace("drone_tuning.csv", "drone_tuning_refine.csv")}


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
        cols.append({"name": "#row", **sweep.encode(p.row_id[idx].astype(float))})
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
    rows = sweep.rerun_rows(p, req.sets, req.onlyMissing) if req.sets else []
    # Split by: sets chosen for one value of a condition - their parameters x the combinations with it
    for x in req.extra:
        rows += sweep.rerun_rows_for(p, x.get("params") or {}, x.get("holds") or {})
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
    rest: str = "all"                    # the other parameters: "all" their values, or "best" - at the best set's


class ClustersReq(BaseModel):
    id: str
    question: Dict[str, Any]
    columns: List[str]                    # parameters and / or per-set result columns
    sets: Optional[List[int]] = None      # a group's sets; missing: all
    method: str = "kmeans"                # kmeans | hierarchical | som | mds
    k: int = 3
    seed: int = 0
    som: List[int] = [6, 6]


@router.post("/api/sweep/clusters")
def sweep_clusters(req: ClustersReq):
    """MF09: clusters / PCA / MDS / SOM of a group's sets on the chosen columns (numeric only)."""
    from svcore.sweep import clusters
    p, a = _answer(req.id, req.question)
    idx = np.arange(p.n_sets) if req.sets is None else np.asarray([i for i in req.sets if 0 <= i < p.n_sets], dtype=np.int64)
    cols: Dict[str, Any] = {}
    for c in req.columns:
        if c in p.params:
            v = pd.to_numeric(pd.Series(p.df[c].to_numpy()[p.first_row]), errors="coerce").to_numpy(dtype=float)
        elif c in a["data"]:
            v = np.asarray(a["data"][c], dtype=float)
        else:
            fail(400, f"No column named {c!r}")
        cols[c] = v[idx]
    try:
        r = clusters.analyse(cols, req.method, req.k, req.seed, req.som)
    except clusters.ClusterError as e:
        fail(400, str(e))
    return {**r, "sets": idx.tolist()}


@router.post("/api/sweep/map")
def sweep_map(req: MapReq):
    p, a = _answer(req.id, req.question)
    if req.x is None or req.y is None or req.x not in p.params or req.y not in p.params or req.x == req.y:
        fail(400, "Choose two different parameters.")
    return sweep.map_for(p, a, req.question, req.x, req.y, req.rest)


class SuggestReq(BaseModel):
    id: str
    question: Dict[str, Any]
    kinds: List[str]
    budget: int = 40
    focus: Optional[List[str]] = None    # S06: the parameters to explore (None: all)
    split: str = "equal"                 # equal | proportional | manual: how the budget is shared
    shares: Optional[Dict[str, int]] = None   # manual: each kind's number


@router.post("/api/sweep/suggest")
def sweep_suggest(req: SuggestReq):
    p, a = _answer(req.id, req.question)
    kinds = [k for k in req.kinds if k in sweep.KINDS]
    goal = req.question.get("goal") or {}
    d = a["data"]
    several = len(req.question.get("objectives") or []) >= 2
    return sweep.suggest(p, d["#holds"], d.get("#goal"), goal.get("direction", "max") != "min",
                         d["#partial"], kinds, max(1, min(2000, req.budget)), focus=req.focus,
                         score=d.get("#score") if several else None, rank=d["#rank"],
                         robust=req.question.get("robust") or None,
                         split=req.split if req.split in ("equal", "proportional", "manual") else "equal", shares=req.shares)


class SuggestExportReq(BaseModel):
    id: str
    question: Dict[str, Any]
    params: List[Dict[str, Any]]
    path: str                            # .csv / .tsv / .json / .m / .py: the format (S17)
    combos: bool = True                  # every set x every combination; False: the sets alone


@router.post("/api/sweep/suggest/export")
def sweep_suggest_export(req: SuggestExportReq):
    """New parameter sets x every kept combination of the must-hold-across columns, as a run list."""
    p = _prepared(req.id, req.question)
    combos = p.df[p.holds].drop_duplicates().to_dict("records") if p.holds and req.combos else [{}]
    rows = [{**ps, **cb} for ps in req.params for cb in combos]
    path = os.path.abspath(os.path.expanduser(req.path))
    try:
        sweep.write_rows(path, rows, p.params + (p.holds if req.combos else []))
    except OSError as e:
        fail(400, f"Could not write {path}: {e}")
    return {"path": path, "rows": len(rows)}


class TextReq(BaseModel):
    path: str
    text: Optional[str] = None


@router.post("/api/sweep/save-text")
def sweep_save_text(req: TextReq):
    """A study (.svsweep) or a report (.html) the page made."""
    path = os.path.abspath(os.path.expanduser(req.path))
    try:
        atomic_write(path, req.text or "")        # O3: a study saved again is replaced whole or not at all
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
    recipe = _recipe(t)
    if not sweep.recipe_files(recipe):
        fail(400, "This table did not come from a file.")
    t0 = time.perf_counter()
    try:
        df = sweep.build(recipe)                           # the tables merged into it, again, the same way
    except Exception as e:
        fail(400, f"Could not read the table again: {e}")
    t["df"], t["prepKey"], t["prep"] = df, None, None
    t["stats"] = {f: _stat(f) for f in sweep.recipe_files(recipe)}
    if t.get("path"):
        t["stat"] = _stat(t["path"])
    for m in t.get("merged", []):
        m["stat"] = _stat(m["path"])
    cols = sweep.describe(df)
    return {"id": req.path, "path": t.get("path", ""), "name": os.path.basename((t.get("path") or "").rstrip("/\\\\")), "rows": int(len(df)),
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
    files = sweep.recipe_files(_recipe(t))
    if not files:
        return {"changed": False}
    stats = t.setdefault("stats", {})
    changed, missing = False, False
    for f in files:
        now = _stat(f)
        if f not in stats:
            stats[f] = now
        missing = missing or now is None
        changed = changed or (now is not None and now != stats[f])
    return {"changed": changed, "missing": missing}


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
            # a save in progress writes a hidden ".<name>.<pid>.tmp.json" first (app/atomic.py): not a template
            if n.endswith(".json") and not n.startswith("."):
                try:
                    with open(os.path.join(TEMPLATES, n), encoding="utf-8") as f:
                        out.append(json.load(f))
                except (OSError, ValueError):
                    continue
    return {"templates": out, "folder": TEMPLATES}


TEMPLATE_KIND = "signalviewer-sweep-template"


def _tpl_write(name: str, tpl: Dict[str, Any]) -> None:
    with atomic_open(_tpl_path(name)) as f:
        json.dump({**tpl, "kind": TEMPLATE_KIND, "name": name.strip(), "saved": time.strftime("%Y-%m-%d %H:%M")}, f, indent=1)


@router.post("/api/sweep/templates/save")
def sweep_template_save(req: TemplateReq):
    _tpl_write(req.name, req.template or {})
    return sweep_templates()


class TemplateFileReq(BaseModel):
    name: Optional[str] = None
    path: str


@router.post("/api/sweep/templates/export")
def sweep_template_export(req: TemplateFileReq):
    """A template to a file of its own - to send to a colleague, keep with a project."""
    src = _tpl_path(req.name or "")
    if not os.path.isfile(src):
        fail(404, f"No template named {req.name!r}.")
    path = os.path.abspath(os.path.expanduser(req.path))
    try:
        with open(src, encoding="utf-8") as f:
            atomic_write(path, f.read())
    except OSError as e:
        fail(400, f"Could not write {path}: {e}")
    return {"path": path}


@router.post("/api/sweep/templates/import")
def sweep_template_import(req: TemplateFileReq):
    """A template from a file (exported here, by a colleague): kept under its name, or that name
    with (2), (3)... when one is taken."""
    path = os.path.abspath(os.path.expanduser(req.path))
    try:
        with open(path, encoding="utf-8") as f:
            tpl = json.load(f)
    except (OSError, ValueError) as e:
        fail(400, f"Could not read {path}: {e}")
    if not isinstance(tpl, dict) or not isinstance(tpl.get("columns"), list) or not isinstance(tpl.get("question"), dict):
        fail(400, f"{os.path.basename(path)} is not a Sweeps template.")
    base = (req.name or tpl.get("name") or os.path.splitext(os.path.basename(path))[0]).strip()
    name, k = base, 2
    while os.path.isfile(_tpl_path(name)):
        name, k = f"{base} ({k})", k + 1
    _tpl_write(name, tpl)
    return {**sweep_templates(), "name": name}


@router.post("/api/sweep/templates/delete")
def sweep_template_delete(req: TemplateReq):
    p = _tpl_path(req.name)
    if os.path.isfile(p):
        os.remove(p)
    return sweep_templates()



# ----------------------------------------------------------------------------- merging, exporting runs
class MergeReq(BaseModel):
    id: str
    path: str
    keys: List[str] = []
    prefer: str = "new"


@router.post("/api/sweep/merge")
def sweep_merge(req: MergeReq):
    """Another results table into this study (a second sweep, finer somewhere): the rows of both."""
    t = _get(req.id)
    path = os.path.abspath(os.path.expanduser(req.path))
    t0 = time.perf_counter()
    try:
        more = sweep.read_any(path)
        df, added, replaced = sweep.merge(t["df"], more, req.keys, req.prefer,
                                          os.path.basename(t.get("path") or "1"), os.path.basename(path))
    except Exception as e:
        fail(400, f"Could not merge {os.path.basename(path)}: {e}")
    t["df"], t["prepKey"], t["prep"] = df, None, None
    t.setdefault("merged", []).append({"path": path, "keys": req.keys, "prefer": req.prefer, "stat": _stat(path)})
    cols = sweep.describe(df)
    return {"id": req.id, "path": t.get("path", ""), "name": "", "rows": int(len(df)), "columns": cols, "head": sweep.head(df),
            "summary": sweep.summary(df, {c["name"]: c["role"] for c in cols}), "seconds": round(time.perf_counter() - t0, 3),
            "added": added, "replaced": replaced, "sources": [os.path.basename(t.get("path") or "")] + [os.path.basename(m["path"]) for m in t["merged"]]}


class ExportRowsReq(BaseModel):
    id: str
    question: Dict[str, Any]
    sets: Optional[List[int]] = None     # every run of these parameter sets
    rows: Optional[List[int]] = None     # or these runs (rows of the table)
    path: str


@router.post("/api/sweep/export-rows")
def sweep_export_rows(req: ExportRowsReq):
    """The runs on screen after the filters - every column of the table, as it was read."""
    t = _get(req.id)
    if req.rows is not None:
        rows = sorted(set(req.rows))
    else:
        p = _prepared(req.id, req.question)
        keep = set(req.sets or [])
        rows = sorted(int(r) for r, s in zip(p.row_id, p.set_id) if int(s) in keep)
    path = os.path.abspath(os.path.expanduser(req.path))
    try:
        t["df"].loc[rows].to_csv(path, index=False)
    except (OSError, KeyError) as e:
        fail(400, f"Could not write {path}: {e}")
    return {"path": path, "rows": len(rows)}


class ExportSetsReq(BaseModel):
    id: str
    question: Dict[str, Any]
    sets: List[int]                      # in the order of the table on screen
    columns: List[str]                   # the answer's columns, in order
    labels: Dict[str, str] = {}          # a column's name on screen
    path: str


@router.post("/api/sweep/export-sets")
def sweep_export_sets(req: ExportSetsReq):
    """The table of sets as shown - a row per parameter set, the columns chosen, in its order - to
    use elsewhere (the sets that hold, as the next step's input). Holds is written as 1 / 0."""
    from app import sweep_report
    p, a = _answer(req.id, req.question)
    n = len(a["data"]["#holds"])
    cols = [c for c in req.columns if c in a["data"]]
    bad = [s for s in req.sets if not 0 <= s < n]
    if bad:
        fail(400, f"No parameter set {bad[0]} in this answer (it has {n}); the table changed - export again.")
    path = os.path.abspath(os.path.expanduser(req.path))

    def cell(c: str, i: int):
        v = sweep_report._value(a, c, i)
        if c == "#holds":
            return int(v == 1)
        return "" if isinstance(v, float) and not np.isfinite(v) else v
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow([req.labels.get(c, c) for c in cols])
            for i in req.sets:
                w.writerow([cell(c, i) for c in cols])
    except OSError as e:
        fail(400, f"Could not write {path}: {e}")
    return {"path": path, "rows": len(req.sets)}


# ----------------------------------------------------------------------------- the report
class ReportReq(BaseModel):
    id: str
    question: Dict[str, Any]
    format: str                          # html | docx | pdf | csv
    path: str
    title: str = ""
    subtitle: str = ""
    notes: str = ""
    lang: str = "en"
    sections: List[Dict[str, Any]] = []  # [{title, items}] - the question, the process, in the user's language
    summary: List[List[Any]] = []        # [[what, value]]
    labels: Dict[str, str] = {}          # a column's name on screen, and a few headings (#answer, #best...)
    columns: List[str] = []              # the table's columns
    axes: List[str] = []                 # the plot's axes
    shown: Optional[List[int]] = None    # the sets on screen after the filters
    rows: Optional[List[int]] = None     # the table's sets, in its order (S04: only those that hold, sorted)
    top: int = 25
    include: Dict[str, bool] = {}
    mapX: Optional[str] = None
    mapY: Optional[str] = None
    maps: Optional[List[Dict[str, Any]]] = None   # S05: every map on screen [{x, y, rest}] (else mapX / mapY)
    iterations: Optional[List[Dict[str, Any]]] = None   # S08: [{n, label, sets, holding, best}] - each merge an iteration
    scatters: Optional[List[Dict[str, Any]]] = None     # S11: every point plot on screen [{x, y}]
    only: Optional[List[int]] = None                     # S14: the plot alone of only these sets
    style: Optional[Dict[str, Any]] = None              # S12: the plots' style (colour map, point size, grid...)
    colorBy: Optional[str] = None                        # the colour column of the plots
    raw: bool = False                    # plot: the raw table's runs instead of the parameter sets


@router.post("/api/sweep/report")
def sweep_report(req: ReportReq):
    from app import sweep_report
    from app.report import ReportNeedsExtra
    ext = {"html": ".html", "docx": ".docx", "pdf": ".pdf", "csv": ".csv", "plot": ".html"}.get(req.format)
    if not ext:
        fail(400, "Unknown report format.")
    path = os.path.abspath(os.path.expanduser(req.path))
    if not path.lower().endswith(ext):
        path += ext
    if req.raw:                                        # the raw results' plot: the table's runs, no question
        df = _get(req.id)["df"]
        if len(df) > 50_000:
            df = df.sample(50_000, random_state=0)
        names = [c for c in (req.axes or list(df.columns)) if c in df.columns]
        try:
            atomic_write(path, sweep_report._html(sweep_report.plot_data(df, names), {**req.model_dump(), "axes": names, "plotOnly": True}, []))
        except OSError as e:
            fail(400, f"Could not write {path}: {e}")
        return {"path": path, "size": os.path.getsize(path)}
    p, a = _answer(req.id, req.question)
    body = {**req.model_dump(), "path": path}       # (the report is built into a temporary file below, O3)
    if (req.include or {}).get("provenance", True):
        L = req.labels or {}
        body["sections"] = [*(req.sections or []), {"title": L.get("#provenance", "Where it comes from"), "items": provenance(req.id)}]
    try:
        with atomic_path(path) as tmp:
            sweep_report.build(p, req.question, a, {**body, "path": tmp})
    except ReportNeedsExtra as e:
        fail(400, str(e))
    except OSError as e:
        fail(400, f"Could not write {path}: {e}")
    return {"path": path, "size": os.path.getsize(path)}


def provenance(tid: str) -> List[str]:
    """Where the answer comes from (S08): each table read - its size, time and SHA-256, so the same
    file can be found again - and the app's version."""
    import hashlib
    from app.version import __version__
    t = _TABLES.get(tid) or {}
    paths = sweep.recipe_files(_recipe(t)) if t else []
    out = []
    for path in [x for x in paths if x]:
        try:
            if os.path.isdir(path):
                n = len([f for f in os.listdir(path) if f.lower().endswith(sweep.io.TABLE_EXTS)])
                out.append(f"{path} - a folder of {n} tables")
                continue
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            st = os.stat(path)
            out.append(f"{path} - {st.st_size:,} bytes, {time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))}, SHA-256 {h.hexdigest()}")
        except OSError as e:
            out.append(f"{path} - could not be read now: {e.strerror or e}")
    out.append(f"Signal Viewer {__version__}")
    return out


# ----------------------------------------------------------------------------- goals side by side
class VariantsReq(BaseModel):
    id: str
    question: Dict[str, Any]
    variants: List[Dict[str, Any]]       # each: {goal, conditions, combine, objectives}


@router.post("/api/sweep/variants")
def sweep_variants(req: VariantsReq):
    """Several goals asked of the same sets, side by side: how many hold under each, the best goal
    value, and how robust the holding sets are (the share of their neighbours that hold too)."""
    out: List[Dict[str, Any]] = []
    for v in req.variants:
        q = {**req.question, "goal": v.get("goal"), "conditions": v.get("conditions") or [],
             "combine": v.get("combine") or "and", "objectives": v.get("objectives") or []}
        p = _prepared(req.id, q)
        try:
            a = sweep.answer(p, q)
        except (sweep.QuestionError, sweep.DerivedError, ValueError) as e:
            out.append({"error": str(e)}); continue
        d = a["data"]
        h = d["#holds"] == 1
        best = None
        if "#goal" in d and np.isfinite(d["#rank"]).any():
            i = int(np.nanargmin(d["#rank"]))
            best = {"value": float(d["#goal"][i]), "params": {c: sweep.evaluate._py(d[c][i]) for c in p.params},
                    "score": float(d["#score"][i]) if "#score" in d and np.isfinite(d["#score"][i]) else None}
        nb = d["#neighbours"][h]
        out.append({"holding": int(h.sum()), "sets": a["counts"]["sets"], "best": best,
                    "robust": float(np.nanmean(nb)) if h.any() and np.isfinite(nb).any() else None,
                    "tolerance": float(np.nanmax(d["#tolerance"])) if h.any() and np.isfinite(d["#tolerance"]).any() else None,
                    "conditions": a["conditions"]})
    return {"variants": out}


# ----------------------------------------------------------------------------- the raw results
@router.get("/api/sweep/rows")
def sweep_rows(id: str, offset: int = 0, limit: int = 100, sort: Optional[str] = None, desc: bool = False):
    """A page of the table as it was read (the first step: the raw results)."""
    df = _get(id)["df"]
    if sort and sort in df.columns:
        df = df.sort_values(sort, ascending=not desc, kind="stable")
    page = df.iloc[max(0, offset): max(0, offset) + max(1, min(1000, limit))]
    return {"total": int(len(df)), "offset": offset, "columns": [str(c) for c in df.columns],
            "rows": sweep.head(page, len(page)), "index": [int(i) for i in page.index]}


@router.post("/api/sweep/raw")
def sweep_raw(req: QuestionReq):
    """Every column of every run (a sample above 200 000), for a parallel plot of the raw results -
    before any role or goal."""
    df = _get(req.id)["df"]
    idx = np.arange(len(df))
    sampled = len(df) > 200_000
    if sampled:
        idx = np.sort(np.random.default_rng(0).choice(len(df), 200_000, replace=False))
    names = [c for c in (req.columns or list(df.columns)) if c in df.columns]
    cols = [{"name": c, **sweep.encode(df[c].iloc[idx].reset_index(drop=True))} for c in names]
    cols.append({"name": "#row", **sweep.encode(df.index.to_numpy()[idx].astype(float))})
    return {"columns": cols, "n": int(len(idx)), "total": int(len(df)), "sampled": sampled}


class UnmergeReq(BaseModel):
    id: str
    path: str


@router.post("/api/sweep/unmerge")
def sweep_unmerge(req: UnmergeReq):
    """Take a merged table out of the study again: the study is read again from its first table and
    the tables still merged into it."""
    t = _get(req.id)
    merged = [m for m in t.get("merged", []) if m["path"] != os.path.abspath(req.path)]
    if len(merged) == len(t.get("merged", [])):
        fail(404, "That table is not merged into this study.")
    t0 = time.perf_counter()
    try:
        df = sweep.read_any(t["path"])
        for m in merged:
            df, _, _ = sweep.merge(df, sweep.read_any(m["path"]), m["keys"], m["prefer"],
                                   os.path.basename(t["path"]), os.path.basename(m["path"]))
    except Exception as e:
        fail(400, f"Could not read the tables again: {e}")
    t["df"], t["prepKey"], t["prep"], t["merged"] = df, None, None, merged
    cols = sweep.describe(df)
    return {"id": req.id, "path": t["path"], "name": "", "rows": int(len(df)), "columns": cols, "head": sweep.head(df),
            "summary": sweep.summary(df, {c["name"]: c["role"] for c in cols}), "seconds": round(time.perf_counter() - t0, 3),
            "added": 0, "replaced": 0, "sources": [os.path.basename(t["path"])] + [os.path.basename(m["path"]) for m in merged]}


# ----------------------------------------------------------------------------- autosave
@router.get("/api/sweep/autosave")
def sweep_autosave_get():
    """The studies open when the app last ran (their .svsweep documents), to open them again."""
    return read_autosave(SWEEP_AUTOSAVE)


@router.post("/api/sweep/autosave")
def sweep_autosave_put(state: Dict[str, Any]):
    return write_autosave(SWEEP_AUTOSAVE, state)


# ----------------------------------------------------------------------------- the Data step's tables
class CombineReq(BaseModel):
    ids: List[str]
    names: List[str]
    how: str = "concat"                  # concat (rows added) | join (on key columns)
    keys: List[str] = []
    source: str = ""                     # a column with each row's table name ("" = none)
    dedupe: bool = False
    name: str = ""
    preview: bool = False                # only what it would give: rows, columns some tables lack


@router.post("/api/sweep/combine")
def sweep_combine(req: CombineReq):
    """Tables of a study merged into a NEW table (the owner's Data step, 2026-11-02); the tables
    merged stay as they were."""
    if req.how not in ("concat", "join"):
        fail(400, "Unknown kind of merge.")
    ts = [_get(i) for i in req.ids]
    parts = [t["df"] for t in ts]
    if req.preview:
        return sweep.combine_preview(parts, req.names, req.how, req.keys, req.source, req.dedupe)
    t0 = time.perf_counter()
    try:
        df = sweep.combine(parts, req.names, req.how, req.keys, req.source, req.dedupe)
    except sweep.SweepError as e:
        fail(400, str(e))
    recipe = {"merge": {"parts": [_recipe(t) for t in ts], "names": req.names, "how": req.how, "keys": req.keys,
                        "source": req.source, "dedupe": req.dedupe}}
    return _register(df, "", req.name or f"merged ({len(ts)} tables)", t0, recipe)


class BuildReq(BaseModel):
    recipe: Dict[str, Any]
    name: str = ""


@router.post("/api/sweep/build")
def sweep_build(req: BuildReq):
    """A table made again from its recipe (a saved study's merged table)."""
    t0 = time.perf_counter()
    try:
        df = sweep.build(req.recipe)
    except Exception as e:
        fail(400, f"Could not make the merged table again: {e}")
    path = req.recipe.get("path", "") if "merge" not in req.recipe else ""
    return _register(df, path, req.name or os.path.basename(path.rstrip("/\\\\")), t0, req.recipe)


@router.post("/api/sweep/drop")
def sweep_drop(req: OpenReq):
    """A table closed on the page: its memory back (`path` carries the table id)."""
    _TABLES.pop(req.path, None)
    return {"ok": True}


class ValuesReq(BaseModel):
    id: str
    column: str
    limit: int = 5000


@router.post("/api/sweep/values")
def sweep_values(req: ValuesReq):
    """A column's values and how many runs have each (a condition's full list, with a search)."""
    df = _get(req.id)["df"]
    if req.column not in df.columns:
        fail(404, f"No column named {req.column!r}.")
    vc = df[req.column].value_counts(dropna=True, sort=False)
    try:
        vc = vc.sort_index()
    except TypeError:
        pass
    vals = [[k.item() if hasattr(k, "item") else k, int(n)] for k, n in vc.items()]
    return {"values": vals[: max(1, req.limit)], "total": len(vals), "numeric": bool(pd.api.types.is_numeric_dtype(df[req.column]))}


class FormulaReq(BaseModel):
    id: str
    expr: str
    derived: List[Dict[str, Any]] = []   # the new columns before it (a formula may use them)


@router.post("/api/sweep/formula-preview")
def sweep_formula_preview(req: FormulaReq):
    """A new column's value in the first run, or what is wrong with the formula - as it is typed."""
    from svcore.sweep.derived import DerivedError, row_formula
    df = _get(req.id)["df"].head(1).copy()
    try:
        for d in req.derived:
            if d.get("kind") == "row" and d.get("name") and d.get("expr"):
                df[d["name"]] = row_formula(df, d["expr"])
        v = float(row_formula(df, req.expr)[0])
    except DerivedError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:              # numpy's own complaint (a wrong number of arguments...)
        return {"ok": False, "error": f"Formula: {e}"}
    return {"ok": True, "value": None if not np.isfinite(v) else v}


class ExportTableReq(BaseModel):
    id: str
    path: str
    format: str = "csv"                  # csv | html (the parallel plot, interactive, the data inside)
    title: str = ""
    axes: List[str] = []
    labels: Dict[str, str] = {}
    view: Dict[str, Any] = {}            # html: {colorBy, filters, zoom} - the plot as it was on screen


@router.post("/api/sweep/export-table")
def sweep_export_table(req: ExportTableReq):
    """A table of the Data step as a file: CSV, or an HTML page with its parallel plot."""
    from app import sweep_report
    if req.format not in ("csv", "html"):
        fail(400, "Unknown export format.")
    ext = "." + req.format
    path = os.path.abspath(os.path.expanduser(req.path))
    if not path.lower().endswith(ext):
        path += ext
    df = _get(req.id)["df"]
    try:
        if req.format == "csv":
            df.to_csv(path, index=False)
            return {"path": path, "rows": int(len(df))}
        if len(df) > 50_000:
            df = df.sample(50_000, random_state=0)
        names = [c for c in (req.axes or list(df.columns)) if c in df.columns]
        a = sweep_report.plot_data(df, names)
        with open(path, "w", encoding="utf-8") as f:
            f.write(sweep_report._html(a, {"axes": names, "plotOnly": True, "title": req.title, "labels": req.labels,
                                            "init": sweep_report.init_view(a, req.view)}, []))
    except OSError as e:
        fail(400, f"Could not write {path}: {e}")
    return {"path": path, "rows": int(len(df))}
