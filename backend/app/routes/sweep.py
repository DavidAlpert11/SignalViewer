"""Sweeps (the run-envelope area): open a results table, describe its columns, and the shape of
the study for a set of roles (svcore/sweep.py). Tables stay here; the page gets descriptions,
counts and - later - what it draws."""
import csv
import json
import os
import time
import uuid
import weakref
from collections import OrderedDict
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from app.common import atomic_write, fail
from app.filecheck import SUPPORTED_EXTS
from app.routes.fs import EXAMPLES
from svcore import sweep
from svcore.sweep.encode import category_labels
from svcore.sweep.recordings import RecordingsError, find_recordings

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
    cells: Optional[List[Dict[str, Any]]] = None        # S2: values fixed by hand
    rowFilter: Optional[str] = None                     # S2: only the runs where it holds
    derived: Optional[List[Dict[str, Any]]] = None      # the new columns the filter may use


class QuestionReq(BaseModel):
    id: str
    question: Dict[str, Any]
    runs: bool = False                  # also every run (a line per run), not only per set
    columns: Optional[List[str]] = None  # runs: which columns (default: every used one)
    # 1.29 - what is drawn: every run up to `cap` (Settings, Most lines to draw; 0 = no cap, None = the default);
    # above it a sample of the runs the brush keeps (`select`: svcore/sweep/select.py), with these always in
    cap: Optional[int] = None
    select: Optional[Dict[str, Any]] = None    # runs: {filters, sets}; raw: {filters}
    pinned: Optional[int] = None               # runs: the open set
    picked: Optional[int] = None               # raw: the picked run (its row in the table)
    # above the cap: "density" (the default, owner 2026-11-17) - every run counted per cell of the picture, the
    # runs of sparse cells drawn one by one (svcore/sweep/density.py) - or "sample" (Settings)
    over: str = "density"
    axes: Optional[List[Dict[str, Any]]] = None     # density: the plot's axes in order, [{column, scale}]
    colour: Optional[Dict[str, Any]] = None         # density: {column} a text / flag column, or {sets: [code per set]}; {n}


class SetReq(BaseModel):
    id: str
    question: Dict[str, Any]
    set: int
    recordings: Optional[Dict[str, str]] = None   # M3: {folder, pattern} - each run's recording found by its row


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
    if req.cells or req.rowFilter:                       # S2: the table as the study edits it ("812 of 840")
        try:
            df = sweep.kept_runs(df, {"cells": req.cells, "rowFilter": req.rowFilter, "derived": req.derived})
        except (sweep.QuestionError, sweep.DerivedError):
            pass                                         # said by /evaluate, where the question is answered
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
    key = json.dumps([q.get("roles"), q.get("holdValues"), q.get("derived"), q.get("exclude"), q.get("cells"), q.get("rowFilter")],
                     sort_keys=True, default=str)
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
    # the last answer of this table, kept: the same question again (Parameter sets <-> All runs, owner
    # 2026-11-13: "it sometimes gets stuck" on big tables) is not worked out again - only the runs added
    t = _get(req.id)
    key = json.dumps(req.question, sort_keys=True, default=str)
    if t.get("ansPrep") is p and t.get("ansKey") == key:
        a = t["ans"]
    else:
        try:
            a = sweep.answer(p, req.question)
        except (sweep.QuestionError, sweep.DerivedError, ValueError) as e:
            fail(400, str(e))
        t["ans"], t["ansKey"], t["ansPrep"] = a, key, p
    out = {"counts": a["counts"], "conditions": a["conditions"], "sets": _enc(a["columns"], a["data"])}
    if p.new_holds:                     # new columns used as scenarios: their values, for the kept-values pickers
        out["newHolds"] = p.new_holds
    if req.runs:
        from svcore.sweep.select import run_mask
        cap = _cap(req.cap)
        sel = req.select or {}
        above = bool(cap and len(p.df) > cap)
        # the brush matters only above the cap (below it every run is sent and the page filters them itself)
        keep = run_mask(p, sel.get("filters"), sel.get("sets")) if above and (req.select is not None or req.over == "density") else None
        holds = a["data"]["#holds"]
        must = [req.pinned] if req.pinned is not None else None
        per_set = {"#set": np.arange(p.n_sets, dtype=float), "#holds": np.asarray(holds, dtype=float)}
        col = (lambda c: pd.Series(per_set[c][p.set_id]) if c in per_set else p.df[c])
        dens = None
        if above and req.over == "density" and keep is not None:
            codes = None
            per_set_codes = (req.colour or {}).get("sets")
            if per_set_codes is not None:                                     # a per-set colour (holds, a group)
                codes = np.asarray(per_set_codes, dtype=np.int64)[p.set_id]
            dens, idx = _density(p.df, col, keep, req, codes)
            if must:
                idx = np.union1d(idx, np.flatnonzero(np.isin(p.set_id, must))[:5000])
            r = {"index": idx, "sampled": False, "total": int(len(p.df))}
        else:
            r = sweep.run_rows(p, holds, cap, keep=keep, must_sets=must)
            idx = r["index"]
        names = req.columns or (p.params + p.holds + p.outputs)
        cols = [{"name": c, **_encode_part(p.df, c, idx), **_domain_of(p.df, c)} for c in names if c in p.df.columns]
        cols.append({"name": "#set", **sweep.encode(p.set_id[idx].astype(float))})
        cols.append({"name": "#row", **sweep.encode(p.row_id[idx].astype(float))})
        cols.append({"name": "#holds", **sweep.encode(np.asarray(holds)[p.set_id[idx]])})
        out["runs"] = {"columns": cols, "sampled": r["sampled"], "total": r["total"], "n": int(len(idx)), "cap": cap,
                       **({"kept": int(keep.sum())} if keep is not None else {}), **({"density": dens} if dens else {})}
    out["seconds"] = round(time.perf_counter() - t0, 3)
    return out


# The most lines sent to draw (All runs, the Data step, a table's HTML page) when the page does not say
# (Settings: Most lines to draw); above it a sample. What the brush selects never comes from what was
# drawn: /api/sweep/select resolves it on every run (1.29).
RUNS_MAX = 200_000


def _cap(cap: Optional[int]) -> int:
    """The page's cap (0 = no cap), or the default."""
    return RUNS_MAX if cap is None else max(0, int(cap))


def _drawn(df: pd.DataFrame, cap: Optional[int]) -> pd.DataFrame:
    """The rows an HTML page of a table carries to draw: every one up to the cap, else a sample (in table order)."""
    from svcore.sweep.select import sample_rows
    return df.iloc[sample_rows(len(df), _cap(cap))]


# what is worked out once per version of a table - a text column's labels, a number column's domain - kept with
# the table object itself (a reload, a merge or a new question's prepared table is another object)
_PER_TABLE: Dict[int, Dict[Any, Any]] = {}


def _kept(df: pd.DataFrame, what: str, col: str, make) -> Any:
    k = id(df)
    if k not in _PER_TABLE:                      # dropped when the table is (so an id used again starts empty)
        _PER_TABLE[k] = {}
        weakref.finalize(df, _PER_TABLE.pop, k, None)
    c = _PER_TABLE[k]
    if (what, col) not in c:
        c[(what, col)] = make()
    return c[(what, col)]


def _domain_of(df: pd.DataFrame, col: str) -> Dict:
    """A number column's domain over the whole table (svcore/sweep/density.domain): the page builds its axis from
    it, so an axis is the same whatever runs were sent to draw (1.29)."""
    from svcore.sweep import density
    s = df[col]
    if not pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):
        return {}
    return {"domain": _kept(df, "domain", col, lambda: density.domain(s))}


def _density(base: pd.DataFrame, col, keep: np.ndarray, req: "QuestionReq", codes: Optional[np.ndarray]):
    """Every run counted per cell of the picture (svcore/sweep/density.parallel) for the page's axes and colour;
    the rows to draw one by one. A column: `col(name)` -> Series."""
    from svcore.sweep import density
    axes, specs = [], []
    for a in req.axes or []:
        name = str(a.get("column") or "")
        try:
            s = col(name)
        except KeyError:
            continue
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            ax = density.axis_cells(_kept(base, "domain", name, lambda: density.domain(s)), a.get("scale") or "linear")
        else:
            ax = density.axis_cells({}, "category", _kept(base, "labels", name, lambda: category_labels(s)))
        axes.append({"column": name, **ax})
        specs.append({"column": name, "centers": ax["centers"]})
    series, n_series = codes, int((req.colour or {}).get("n") or 1)
    cname = (req.colour or {}).get("column")
    if series is None and cname:
        try:
            cs = col(cname)
            labs = _kept(base, "labels", cname, lambda: category_labels(cs))
            series = density.cells(cs, {"labels": labs})                  # its last code: no value
            n_series = len(labs) + 1
        except KeyError:
            series = None
    if series is None:
        n_series = 1
    keepn = np.asarray(keep, dtype=bool)
    r = density.parallel({a["column"]: col(a["column"]) for a in axes}, axes, keepn, series, n_series)
    return ({"axes": specs, "pairs": r["pairs"], "series": n_series, "sparseAt": r["sparseAt"], "sparse": int(len(r["sparse"]))},
            np.asarray(r["sparse"], dtype=np.int64))


def _encode_part(df: pd.DataFrame, col: str, idx: np.ndarray) -> Dict:
    """Some rows of a column, encoded; a text column's labels from the whole column, worked out once per table
    version (a brush above the cap asks for new rows at every change)."""
    s = df[col]
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
        return sweep.encode(s.iloc[idx].reset_index(drop=True))
    return sweep.encode(s.iloc[idx].reset_index(drop=True), labels=_kept(df, "labels", col, lambda: category_labels(s)))


class SelectReq(BaseModel):
    id: str
    question: Dict[str, Any]
    filters: Dict[str, Dict[str, Any]] = {}   # the axes' filters on run columns (svcore/sweep/select.py)
    sets: Optional[List[int]] = None          # the sets the page shows (None: all)


@router.post("/api/sweep/select")
def sweep_select(req: SelectReq):
    """What the brush of All runs selects, on the whole table: its parameter sets (for Keep / Exclude, a
    group) and how many runs."""
    from svcore.sweep.select import selection
    p = _prepared(req.id, req.question)
    r = selection(p, req.filters, req.sets)
    return {"sets": r["sets"], "runs": r["runs"], "total": int(len(p.df))}


class RunChartsReq(BaseModel):
    id: str
    question: Dict[str, Any]
    filters: Dict[str, Dict[str, Any]] = {}   # the brush on the runs' columns (svcore/sweep/select.py)
    sets: Optional[List[int]] = None          # the sets the chart shows (the keep / exclude steps, its group)
    colour: Optional[Dict[str, Any]] = None   # the series: {column} a text column, or {sets: [code per set], n}
    hist: Optional[Dict[str, Any]] = None     # {column, bins}
    box: Optional[Dict[str, Any]] = None      # {column}
    corr: Optional[Dict[str, Any]] = None     # {columns, method}: the matrix - coefficients, histograms, the cells' points
    scatter: Optional[Dict[str, Any]] = None  # {x, y, xScale, yScale, size?, colourValue?}
    history: Optional[Dict[str, Any]] = None  # {column, direction?}: the runs in table order, and the best so far


@router.post("/api/sweep/run-charts")
def sweep_run_charts(req: RunChartsReq):
    """The Charts of All runs on every run (1.29, FT6): when the page has only some of the runs (above the cap) its
    histogram counts, box statistics and correlations come from here, and a scatter of every run - counted per cell,
    the sparse cells' runs one by one (CLAUDE.md: no point is ever left out of a picture)."""
    from svcore.sweep import density
    from svcore.sweep.select import run_mask
    p, a = _answer(req.id, req.question)
    holds = np.asarray(a["data"]["#holds"], dtype=float)
    per_set = {"#set": np.arange(p.n_sets, dtype=float), "#holds": holds}

    def col(c: str) -> pd.Series:
        if c in per_set:
            return pd.Series(per_set[c][p.set_id])
        if c not in p.df.columns:
            fail(400, f"No column named {c!r}")
        return p.df[c]

    def num(c: str, m: np.ndarray) -> np.ndarray:
        return pd.to_numeric(col(c)[m], errors="coerce").to_numpy(dtype=np.float32, na_value=np.nan).astype(np.float64)

    scope = run_mask(p, None, req.sets)                 # the runs the chart is about (its extent)
    keep = run_mask(p, req.filters, req.sets)           # ... and of those, the ones the brush keeps
    series, n_ser = np.zeros(len(p.df), dtype=np.int64), 1
    cs = req.colour or {}
    if cs.get("sets") is not None:
        series, n_ser = np.asarray(cs["sets"], dtype=np.int64)[p.set_id], int(cs.get("n") or 1)
    elif cs.get("column"):
        labs = _kept(p.df, "labels", cs["column"], lambda: category_labels(col(cs["column"])))
        series, n_ser = density.cells(col(cs["column"]), {"labels": labs}), len(labs) + 1
    out: Dict[str, Any] = {"kept": int(keep.sum()), "total": int(len(p.df)), "series": n_ser}

    def text(c: str) -> bool:
        s = col(c)
        return not pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s)

    if req.hist:
        c, bins = req.hist["column"], int(req.hist.get("bins") or 30)
        if text(c):
            labs = _kept(p.df, "labels", c, lambda: category_labels(col(c)))
            v = density.cells(col(c), {"labels": labs})[keep].astype(float)
            v[v >= len(labs)] = np.nan
            lo, hi, bins = -0.5, len(labs) - 0.5, max(1, len(labs))
        else:
            ext = num(c, scope)
            ext = ext[np.isfinite(ext)]
            lo, hi = (float(ext.min()), float(ext.max())) if len(ext) else (0.0, 1.0)
            if lo == hi:
                lo, hi = lo - 0.5, hi + 0.5
            v = num(c, keep)
        out["hist"] = {"lo": lo, "hi": hi, "bins": bins, "counts": density.histogram(v, lo, hi, bins, series[keep], n_ser)}
    if req.box:
        v, sk = num(req.box["column"], keep), series[keep]
        out["box"] = [density.box(v[sk == k]) for k in range(n_ser)]
        ext = v[np.isfinite(v)]
        out["boxRange"] = [float(ext.min()), float(ext.max())] if len(ext) else [0.0, 1.0]
    if req.corr:
        names = [c for c in req.corr.get("columns") or [] if not text(c)][:8]
        vals = [num(c, keep) for c in names]
        out["corr"] = {"columns": names, "coef": density.correlation(vals, req.corr.get("method") or "pearson")}
        hists, ranges = [], []
        for v in vals:
            f = v[np.isfinite(v)]
            lo, hi = (float(f.min()), float(f.max())) if len(f) else (0.0, 1.0)
            if lo == hi:
                lo, hi = lo - 0.5, hi + 0.5
            ranges.append([lo, hi])
            hists.append(density.histogram(v, lo, hi, 12, np.zeros(len(v), dtype=np.int64), 1)[0])
        out["corr"].update(hists=hists, ranges=ranges, cells=[[None] * len(names) for _ in names])
        for i in range(len(names)):                     # the points of each cell below the diagonal... drawn above it
            for j in range(len(names)):
                if i >= j:
                    continue
                ax = {"edges": np.linspace(ranges[j][0], ranges[j][1], 41).tolist()}
                ay = {"edges": np.linspace(ranges[i][0], ranges[i][1], 41).tolist()}
                g = density.grid2d(col(names[j])[keep].reset_index(drop=True), col(names[i])[keep].reset_index(drop=True),
                                   ax, ay, np.ones(int(keep.sum()), bool), series[keep], n_ser, max_sparse=1500)
                sp = g["sparse"]
                out["corr"]["cells"][i][j] = {"x": g["x"], "y": g["y"], "s": g["s"], "n": g["n"], "k": 40,
                                              "px": vals[j][sp].tolist(), "py": vals[i][sp].tolist(), "ps": series[keep][sp].tolist()}
    if req.history:
        from svcore.decimate import minmax_decimate
        v = num(req.history["column"], keep)
        v = v[np.isfinite(v)]
        k = np.arange(len(v), dtype=np.float64)
        hx, hy = minmax_decimate(k, v, 2000) if len(v) > 4000 else (k, v)   # every peak kept, as a time plot
        h: Dict[str, Any] = {"n": int(len(v)), "x": hx.tolist(), "y": hy.tolist()}
        d = req.history.get("direction")
        if d in ("max", "min") and len(v):
            best = np.maximum.accumulate(v) if d == "max" else np.minimum.accumulate(v)
            bx, by = minmax_decimate(k, best, 2000) if len(v) > 4000 else (k, best)
            h.update(bx=bx.tolist(), by=by.tolist())
        out["history"] = h
    if req.scatter:
        sc = req.scatter
        xs, ys = col(sc["x"]), col(sc["y"])
        axes = []
        for name, s, scale in ((sc["x"], xs, sc.get("xScale") or "linear"), (sc["y"], ys, sc.get("yScale") or "linear")):
            if text(name):
                axes.append(density.axis_cells({}, "category", _kept(p.df, "labels", name, lambda s=s: category_labels(s))))
            else:
                dom = _kept(p.df, "domain", name, lambda s=s: density.domain(s))
                cut = dict(density.axis_cells(dom, scale))
                if scale not in ("category", "ordinal"):     # a scatter's cells: finer than an axis's
                    lo, hi = dom.get("loPos" if scale == "log" else "lo", 0.0), dom.get("hi", 1.0)
                    if hi == lo:
                        lo, hi = lo - 0.5, hi + 0.5
                    e = np.geomspace(lo, hi, 121) if scale == "log" and lo > 0 else np.linspace(lo, hi, 121)
                    cut = {"edges": e.tolist(), "centers": ((e[:-1] + e[1:]) / 2).tolist()}
                axes.append(cut)
        g = density.grid2d(xs, ys, axes[0], axes[1], keep, series, n_ser)
        sp = g["sparse"]

        def at(c: Optional[str]):
            if not c:
                return None
            if text(c):
                labs = _kept(p.df, "labels", c, lambda: category_labels(col(c)))
                return density.cells(col(c), {"labels": labs})[sp].astype(float).tolist()
            return pd.to_numeric(col(c).iloc[sp], errors="coerce").to_numpy(dtype=float, na_value=np.nan).tolist()
        out["scatter"] = {"x": g["x"], "y": g["y"], "s": g["s"], "n": g["n"], "cells": g["cells"],
                          "cx": axes[0]["centers"], "cy": axes[1]["centers"],
                          "points": {"x": at(sc["x"]), "y": at(sc["y"]), "s": series[sp].tolist(), "size": at(sc.get("size")),
                                     "c": at(sc.get("colourValue"))}}
    return _jsonable(out)


def _jsonable(o: Any) -> Any:
    """NaN / inf as null (JSON has neither); numpy numbers as Python's."""
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, np.integer):
        return int(o)
    return o


@router.post("/api/sweep/set")
def sweep_set(req: SetReq):
    p = _prepared(req.id, req.question)
    try:
        out = sweep.set_rows(p, req.question, req.set)
    except (sweep.QuestionError, ValueError) as e:
        fail(400, str(e))
    folder = (req.recordings or {}).get("folder", "").strip()
    if folder and not out["recordings"]:
        # no recording column: found from the run's row in the folder, only now (nothing read ahead)
        roles = req.question.get("roles") or {}
        id_col = next((c for c, r in roles.items() if r == "id" and c in p.df.columns), None)
        try:
            per_run, wanted = find_recordings(p.df[p.set_id == req.set], id_col, folder,
                                              (req.recordings or {}).get("pattern", ""), SUPPORTED_EXTS)
        except RecordingsError as e:
            fail(400, str(e))
        out.update(recordingPerRun=per_run, recordings=[x for x in per_run if x], notFound=wanted[:20])
    return out


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
