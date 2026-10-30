"""The question, answered per parameter set (see svcore/sweep/__init__.py).

A question (JSON from the page):
    roles        {column: param | hold | output | id | ignore}
    holdValues   {hold column: [values kept]}         - missing or empty: every value
    derived      [{name, kind: "row", expr} | {name, kind: "set", op, column, where}]
    goal         {column, direction: "max" | "min"} or null
    conditions   [{column, op: ">=" "<=" ">" "<" "==" "!=", value, mode: "all" | "atLeast" | "only",
                   k (atLeast), where (only: {hold column: [values]})}]
    outputAgg    {output column: mean | min | max | median | p10 | p90 | std | spread}   - default mean
    objectives   [{column, direction, weight}] - several goals: the Pareto front and a weighted score
    exclude      [table row]                  - runs left out (e.g. suspicious ones)

A parameter set holds when it ran every combination of the kept must-hold-across values and every
condition is met: "all" - in every combination, "atLeast" - in at least k, "only" - in every
combination of the given values. A condition on a per-set column is one value: met or not.

Worst case: for a ">=" condition or a goal to maximize, the smallest value over the combinations;
for "<=" or a goal to minimize, the largest. Margin: how far the worst case is inside the limit.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from svcore.sweep.derived import DerivedError, SET_OPS, hold_mask, row_formula, set_aggregate

_OPS = {">=": np.greater_equal, "<=": np.less_equal, ">": np.greater, "<": np.less, "==": np.equal, "!=": np.not_equal}
_LOWER_IS_WORSE = (">=", ">")


class QuestionError(ValueError):
    pass


@dataclass
class Prepared:
    df: pd.DataFrame                    # the kept rows, with the per-run new columns
    params: List[str]
    holds: List[str]
    outputs: List[str]
    set_id: np.ndarray                  # per kept row
    n_sets: int
    first_row: np.ndarray               # per set: a row of it (its parameter values)
    combo_id: np.ndarray                # per kept row
    n_combos: int
    covered: np.ndarray                 # per set: distinct combinations it ran
    row_id: np.ndarray = None           # per kept row: its row in the table (to leave runs out by row)
    set_cols: Dict[str, np.ndarray] = field(default_factory=dict)   # per-set new columns


def _ids(df: pd.DataFrame, cols: List[str]) -> np.ndarray:
    if not cols:
        return np.zeros(len(df), dtype=np.int64)
    return df.groupby(cols, sort=False, dropna=False, observed=True).ngroup().to_numpy().astype(np.int64)


def _distinct_per_set(set_id: np.ndarray, combo_id: np.ndarray, n_sets: int, n_combos: int, mask=None) -> np.ndarray:
    s, c = (set_id, combo_id) if mask is None else (set_id[mask], combo_id[mask])
    if not len(s):
        return np.zeros(n_sets, dtype=np.int64)
    pairs = np.unique(s * (n_combos + 1) + c)
    return np.bincount(pairs // (n_combos + 1), minlength=n_sets)


def prepare(table: pd.DataFrame, q: Dict) -> Prepared:
    roles: Dict[str, str] = q.get("roles") or {}
    params = [c for c in table.columns if roles.get(c) == "param"]
    holds = [c for c in table.columns if roles.get(c) == "hold"]
    outputs = [c for c in table.columns if roles.get(c) == "output"]
    if not params:
        raise QuestionError("Choose at least one parameter column.")
    df = table
    keep = hold_mask(df, {c: v for c, v in (q.get("holdValues") or {}).items() if c in holds and v})
    if keep is not None:
        df = df[keep]
    excluded = q.get("exclude") or []
    if excluded:                                          # runs left out by the user (suspicious ones)
        df = df[~df.index.isin(excluded)]
    row_id = df.index.to_numpy()
    df = df.reset_index(drop=True)
    derived = q.get("derived") or []
    new_cols = {}
    for d in derived:
        if d.get("kind") == "row":
            name = (d.get("name") or "").strip()
            if not name:
                raise QuestionError("A new column needs a name.")
            new_cols[name] = row_formula(df.assign(**new_cols) if new_cols else df, d.get("expr") or "")
    if new_cols:
        df = df.assign(**new_cols)
        outputs = outputs + [n for n in new_cols if n not in outputs]
    set_id = _ids(df, params)
    n_sets = int(set_id.max()) + 1 if len(set_id) else 0
    _, first_row = np.unique(set_id, return_index=True)
    combo_id = _ids(df, holds)
    n_combos = int(combo_id.max()) + 1 if len(combo_id) else 0
    covered = _distinct_per_set(set_id, combo_id, n_sets, n_combos)
    p = Prepared(df, params, holds, outputs, set_id, n_sets, first_row, combo_id, n_combos, covered, row_id=row_id)
    for d in derived:
        if d.get("kind") == "set":
            name, op, col = (d.get("name") or "").strip(), d.get("op"), d.get("column")
            if not name:
                raise QuestionError("A new column needs a name.")
            if col not in df.columns:
                raise QuestionError(f"No column named {col!r}")
            if op not in SET_OPS:
                raise QuestionError(f"Unknown operation: {op}")
            p.set_cols[name] = set_aggregate(df[col], set_id, n_sets, op, hold_mask(df, d.get("where")))
    return p


def _agg(p: Prepared, col: str, op: str) -> np.ndarray:
    if col in p.set_cols:
        return p.set_cols[col]
    return set_aggregate(p.df[col], p.set_id, p.n_sets, op)


def _condition(p: Prepared, c: Dict) -> Dict:
    col, op = c.get("column"), c.get("op")
    if op not in _OPS:
        raise QuestionError(f"Unknown comparison: {op}")
    try:
        limit = float(c.get("value"))
    except (TypeError, ValueError):
        raise QuestionError(f"{col}: the limit must be a number") from None
    lower_worse = op in _LOWER_IS_WORSE
    if col in p.set_cols:                                  # one value per set: met or not
        v = p.set_cols[col]
        with np.errstate(invalid="ignore"):
            ok = _OPS[op](v, limit) & np.isfinite(v)
        margin = (v - limit) if lower_worse else (limit - v) if op in ("<=", "<") else np.full(p.n_sets, np.nan)
        return {"ok": ok, "worst": v, "margin": margin, "passed": ok.astype(float), "needed": np.ones(p.n_sets)}
    if col not in p.df.columns:
        raise QuestionError(f"No column named {col!r}")
    vals = pd.to_numeric(p.df[col], errors="coerce").to_numpy(dtype=float)
    mode = c.get("mode") or "all"
    scope = hold_mask(p.df, c.get("where")) if mode == "only" else None
    with np.errstate(invalid="ignore"):
        row_ok = _OPS[op](vals, limit) & np.isfinite(vals)             # an empty output fails
    sid, ok_rows, v = (p.set_id, row_ok, vals) if scope is None else (p.set_id[scope], row_ok[scope], vals[scope])
    passed = np.bincount(sid, weights=ok_rows.astype(float), minlength=p.n_sets)
    rows = np.bincount(sid, minlength=p.n_sets).astype(float)
    if scope is None:
        expected, covered = p.n_combos, p.covered
    else:
        cid = p.combo_id[scope]
        expected = int(len(np.unique(cid)))
        covered = _distinct_per_set(p.set_id, p.combo_id, p.n_sets, p.n_combos, scope)
    if mode == "atLeast":
        k = int(c.get("k") or 0)
        ok = passed >= k
        needed = np.full(p.n_sets, float(k))
    else:
        ok = (covered == expected) & (passed == rows) & (rows > 0)
        needed = np.full(p.n_sets, float(expected))
    s = pd.Series(v).groupby(sid)
    worst_s = s.min() if lower_worse else s.max()
    worst = np.full(p.n_sets, np.nan)
    worst[worst_s.index.to_numpy(dtype=int)] = worst_s.to_numpy(dtype=float)
    if lower_worse:
        margin = worst - limit
    elif op in ("<=", "<"):
        margin = limit - worst
    else:
        margin = np.full(p.n_sets, np.nan)
    return {"ok": ok, "worst": worst, "margin": margin, "passed": passed, "needed": needed}


def answer(p: Prepared, q: Dict) -> Dict:
    """Per parameter set: its parameters, outputs (aggregated), new columns, each condition (worst,
    margin, passed), the goal, holds or not, its rank. Column arrays, one entry per set."""
    cols: Dict[str, np.ndarray] = {}
    meta: List[Dict] = []

    def add(name, values, group, **extra):
        cols[name] = values
        meta.append({"name": name, "group": group, **extra})

    for c in p.params:
        add(c, p.df[c].to_numpy()[p.first_row], "param")
    agg = q.get("outputAgg") or {}
    for c in p.outputs:
        op = agg.get(c, "mean")
        if op not in SET_OPS:
            op = "mean"
        add(c, _agg(p, c, op), "output", agg=op)
    for name, v in p.set_cols.items():
        add(name, v, "derived")
    complete = p.covered == p.n_combos
    holds = complete.copy()
    conds = []
    for i, c in enumerate(q.get("conditions") or []):
        r = _condition(p, c)
        holds &= r["ok"]
        label = f"{c.get('column')} {c.get('op')} {c.get('value')}"
        add(f"#c{i}.worst", r["worst"], "condition", condition=i, label=label, part="worst")
        add(f"#c{i}.margin", r["margin"], "condition", condition=i, label=label, part="margin")
        add(f"#c{i}.passed", r["passed"], "condition", condition=i, label=label, part="passed")
        conds.append({"label": label, "column": c.get("column"), "met": int(r["ok"].sum())})
    goal = q.get("goal") or None
    rank = np.full(p.n_sets, np.nan)
    if goal and goal.get("column"):
        gcol, maximize = goal["column"], goal.get("direction", "max") != "min"
        if gcol not in p.df.columns and gcol not in p.set_cols:
            raise QuestionError(f"No column named {gcol!r}")
        g = _agg(p, gcol, "min" if maximize else "max")
        add("#goal", g, "goal", column=gcol, direction="max" if maximize else "min")
        idx = np.where(holds & np.isfinite(g))[0]
        order = idx[np.argsort(-g[idx] if maximize else g[idx], kind="stable")]
        rank[order] = np.arange(1, len(order) + 1)
    # what tells nothing: a column with one value over all sets; an output with the same value
    # in every combination of each set (the scenarios do not move it)
    for m in meta:
        v = cols[m["name"]]
        if m["group"] in ("param", "output", "derived") and np.issubdtype(np.asarray(v).dtype, np.number):
            f = np.asarray(v, dtype=float)
            f = f[np.isfinite(f)]
            m["constant"] = bool(len(f) == 0 or f.min() == f.max())
        elif m["group"] == "param":
            m["constant"] = len(pd.unique(pd.Series(v).dropna())) <= 1
    for m in meta:
        if m["group"] == "output" and m["name"] in p.df.columns and p.holds:
            spread = set_aggregate(p.df[m["name"]], p.set_id, p.n_sets, "spread")
            m["flat"] = bool(np.nanmax(np.nan_to_num(spread, nan=0.0)) == 0) if len(spread) else False
    partial = np.zeros(p.n_sets)
    for m in meta:                                   # some combinations pass, not all: scenarios disagree
        if m.get("part") == "passed":
            ps, need = cols[m["name"]], p.n_combos
            partial = np.maximum(partial, ((ps > 0) & (ps < need)).astype(float))
    from svcore.sweep.analysis import objectives as _objectives
    from svcore.sweep.grid import Grid, stability
    front, score = _objectives(p, q.get("objectives") or [], holds)
    if front is not None:
        add("#pareto", front, "result")
        add("#score", score, "result")
    share, tol = stability(Grid(p), holds.astype(float))
    add("#neighbours", share, "result")
    add("#tolerance", tol, "result")
    add("#partial", partial, "result")
    add("#holds", holds.astype(float), "result")
    add("#complete", complete.astype(float), "result")
    add("#covered", p.covered.astype(float), "result")
    add("#rank", rank, "result")
    return {"columns": meta, "data": cols, "conditions": conds,
            "counts": {"sets": p.n_sets, "holding": int(holds.sum()), "complete": int(complete.sum()),
                       "combos": p.n_combos, "rows": int(len(p.df))}}


def set_rows(p: Prepared, q: Dict, set_index: int) -> Dict:
    """One parameter set: every run of it (its must-hold-across values and outputs) and, per
    condition, which runs break it - the "why does it fail"."""
    if not 0 <= set_index < p.n_sets:
        raise QuestionError("No such parameter set.")
    m = p.set_id == set_index
    sub = p.df[m]
    params = {c: _py(p.df[c].iloc[p.first_row[set_index]]) for c in p.params}
    keep = p.holds + p.outputs
    runs = [[_py(v) for v in row] for row in sub[keep].itertuples(index=False, name=None)]
    why = []
    for i, c in enumerate(q.get("conditions") or []):
        col, op, limit = c.get("column"), c.get("op"), float(c.get("value"))
        if col in p.set_cols:
            v = p.set_cols[col][set_index]
            if not (np.isfinite(v) and _OPS[op](v, limit)):
                why.append({"condition": i, "column": col, "broken": 1, "of": 1, "worst": _py(v), "where": None})
            continue
        scope = hold_mask(sub, c.get("where")) if (c.get("mode") == "only") else None
        s = sub if scope is None else sub[scope]
        vals = pd.to_numeric(s[col], errors="coerce").to_numpy(dtype=float)
        with np.errstate(invalid="ignore"):
            bad = ~(_OPS[op](vals, limit) & np.isfinite(vals))
        if bad.any():
            # the run to show: the worst value among the breaking runs, or a run with no result
            cand = np.where(bad & np.isfinite(vals))[0]
            if len(cand):
                j = int(cand[np.argmin(vals[cand])] if op in _LOWER_IS_WORSE else cand[np.argmax(vals[cand])])
            else:
                j = int(np.argmax(bad))
            why.append({"condition": i, "column": col, "broken": int(bad.sum()), "of": int(len(vals)),
                        "worst": _py(vals[j]), "noResult": not np.isfinite(vals[j]),
                        "where": {h: _py(s[h].iloc[j]) for h in p.holds}})
    missing = p.n_combos - int(p.covered[set_index])
    rec_cols = [c for c, r in (q.get("roles") or {}).items() if r == "recording" and c in sub.columns]
    per_run = [None if (x is None or x != x) else str(x) for x in sub[rec_cols[0]].tolist()] if rec_cols else []
    recordings = [x for x in per_run if x]
    return {"params": params, "columns": keep, "holds": p.holds, "runs": runs, "why": why, "missingCombos": missing,
            "rows": [int(x) for x in p.row_id[m]], "recordings": recordings, "recordingPerRun": per_run}


def run_rows(p: Prepared, holds_per_set: np.ndarray, max_rows: int = 200_000, seed: int = 0) -> Dict:
    """Every kept run (a sample when there are more than max_rows): the row's set and whether that
    set holds, for drawing a line per run."""
    n = len(p.df)
    idx = np.arange(n)
    sampled = n > max_rows
    if sampled:
        idx = np.sort(np.random.default_rng(seed).choice(n, max_rows, replace=False))
    return {"index": idx, "set": p.set_id[idx], "holds": holds_per_set[p.set_id[idx]], "sampled": sampled, "total": n}


def _py(v):
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else float(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if v is pd.NA or v is None:
        return None
    return v
