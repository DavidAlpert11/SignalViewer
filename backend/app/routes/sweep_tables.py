"""Sweeps (the run-envelope area), its tables after they are open (split out of app/routes/sweep.py, UX5.5): following
the file, merging and exporting runs, goals side by side, the raw rows, the autosave and the Data step's tables
(combine, build, drop, values, a formula's preview, export). The open tables themselves are app/routes/sweep.py's."""
import csv
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from app.common import SWEEP_AUTOSAVE, atomic_path, atomic_write, fail, read_autosave, write_autosave
from app.routes.sweep import (_answer, _cap, _density, _domain_of, _drawn, _encode_part, _get, OpenReq, _prepared,
                              QuestionReq, _recipe, _register, _stat, _TABLES, _value)
from svcore import sweep

router = APIRouter()


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
    select: Optional[Dict[str, Any]] = None   # or the runs a selection selects ({filters, sets}: /api/sweep/select)
    path: str


@router.post("/api/sweep/export-rows")
def sweep_export_rows(req: ExportRowsReq):
    """The runs on screen after the filters - every column of the table, as it was read."""
    t = _get(req.id)
    if req.select is not None:
        from svcore.sweep.select import selection
        p = _prepared(req.id, req.question)
        rows = sorted(selection(p, req.select.get("filters") or {}, req.select.get("sets"))["rows"])
    elif req.rows is not None:
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
    """Every column of every run up to the cap, for a parallel plot of the raw results - before any role or
    goal. Above the cap a sample of the runs the filters keep (`select.filters`) with a little background,
    the picked run always in; `kept` is how many runs of the whole table the filters keep."""
    from svcore.sweep.select import frame_mask, sample_rows
    t = _get(req.id)
    df = t["df"]
    cap = _cap(req.cap)
    filters = (req.select or {}).get("filters")
    keep = frame_mask(df, filters) if filters else None
    must = np.flatnonzero(df.index.to_numpy() == req.picked)[:1] if req.picked is not None else None
    dens = None
    if cap and len(df) > cap and req.over == "density":      # every run counted, the sparse ones drawn (FT5)
        dens, idx = _density(df, lambda c: df[c], keep if keep is not None else np.ones(len(df), bool), req, None)
        if must is not None:
            idx = np.union1d(idx, must)
    else:
        idx = sample_rows(len(df), cap, keep if cap and len(df) > cap else None, None, must)
    names = [c for c in (req.columns or list(df.columns)) if c in df.columns]
    cols = [{"name": c, **_encode_part(df, c, idx), **_domain_of(df, c)} for c in names]
    cols.append({"name": "#row", **sweep.encode(df.index.to_numpy()[idx].astype(float))})
    return {"columns": cols, "n": int(len(idx)), "total": int(len(df)), "sampled": dens is None and len(idx) < len(df), "cap": cap,
            "kept": int(keep.sum()) if keep is not None else int(len(df)), **({"density": dens} if dens else {})}


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
    full = _get(req.id)["df"]
    # rank() / pct() are of the whole table; any other formula needs only the first run
    uses = " ".join([req.expr] + [str(d.get("expr") or "") for d in req.derived])
    df = (full if re.search(r"\b(rank|pct)\s*\(", uses) else full.head(1)).copy()
    try:
        for d in req.derived:
            if d.get("kind") == "row" and d.get("name") and d.get("expr"):
                df[d["name"]] = row_formula(df, d["expr"])
        r = row_formula(df, req.expr)
    except DerivedError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:              # numpy's own complaint (a wrong number of arguments...)
        return {"ok": False, "error": f"Formula: {e}"}
    if r.dtype == object:               # a text column (S1): its first value, and that it is text
        return {"ok": True, "value": None if r[0] is None else str(r[0]), "text": True}
    v = float(r[0])
    return {"ok": True, "value": None if not np.isfinite(v) else v}


class ExportTableReq(BaseModel):
    id: str
    path: str
    format: str = "csv"                  # csv | parquet | xlsx | html (the parallel plot, interactive, the data inside)
    title: str = ""
    axes: List[str] = []
    labels: Dict[str, str] = {}
    view: Dict[str, Any] = {}            # html: {colorBy, filters, zoom} - the plot as it was on screen
    question: Optional[Dict[str, Any]] = None   # S2c: the table as the study's recipe edits it (+ the recipe beside it)
    recipe: Optional[Dict[str, Any]] = None     # what to write in <file>.recipe.json (how the table was made)
    cap: Optional[int] = None                   # html: the most runs in the page (Settings; 0 = all), a sample above it


@router.post("/api/sweep/export-table")
def sweep_export_table(req: ExportTableReq):
    """A table of the Data step as a file: CSV, Parquet, Excel - as the study edits it when a question is
    given, with the recipe in a JSON file beside it - or an HTML page with its parallel plot."""
    from app import sweep_report
    if req.format not in ("csv", "parquet", "xlsx", "html"):
        fail(400, "Unknown export format.")
    ext = "." + req.format
    path = os.path.abspath(os.path.expanduser(req.path))
    if not path.lower().endswith(ext):
        path += ext
    df = _get(req.id)["df"]
    if req.question is not None and req.format != "html":
        try:
            df = sweep.table_as_edited(df, req.question)
        except (sweep.QuestionError, sweep.DerivedError) as e:
            fail(400, str(e))
    if req.format == "xlsx" and len(df) > 1_048_575:
        fail(400, f"Excel holds at most 1,048,575 rows; this table has {len(df):,} - export it as CSV or Parquet.")
    if req.format == "xlsx":
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            fail(400, "Excel export needs the openpyxl package (pip install openpyxl) - or export the table as CSV or Parquet.")
    try:
        if req.format != "html":
            with atomic_path(path) as tmp:
                if req.format == "csv":
                    df.to_csv(tmp, index=False)
                elif req.format == "parquet":
                    df.to_parquet(tmp, index=False)
                else:
                    df.to_excel(tmp, index=False, engine="openpyxl")
            if req.recipe is not None:
                atomic_write(path + ".recipe.json", json.dumps(req.recipe, indent=1, default=str))
            return {"path": path, "rows": int(len(df))}
        df = _drawn(df, req.cap)
        names = [c for c in (req.axes or list(df.columns)) if c in df.columns]
        a = sweep_report.plot_data(df, names)
        with open(path, "w", encoding="utf-8") as f:
            f.write(sweep_report._html(a, {"axes": names, "plotOnly": True, "title": req.title, "labels": req.labels,
                                            "init": sweep_report.init_view(a, req.view)}, []))
    except OSError as e:
        fail(400, f"Could not write {path}: {e}")
    return {"path": path, "rows": int(len(df))}
