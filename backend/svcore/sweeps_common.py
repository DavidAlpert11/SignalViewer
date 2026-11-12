"""W14: one parameter set for many sweep tables (the owner's example: several drones that must fly with the
same gains). The study file (svcore/study.py) says what each column of each table is:

* shared (S)   - in every table after the name mapping; ONE value is chosen for all tables;
* scenario (E) - this table only; the choice must hold for every active value of it;
* local (L)    - this table only; each table picks its own best value for it;
* output (Y)   - a result of the run.

For every candidate value s of S (only values that were run - no interpolation, that is W15's job):

1. feasible in t  iff some local choice l makes EVERY active scenario run (s, l, e) exist and meet C_t
   (a missing run is a failure with the reason "not run");
2. score_t(s)     = the aggregation over scenarios (worst case, or the mean) of J_t, for the best l*_t(s);
3. feasible for all iff feasible in every table (a value absent from a table is "not run in table k");
4. ranking: one objective shared by every table -> minimise the worst table; different objectives -> the
   Pareto front over (score_1 ... score_N); weights apply to min-max normalised scores.

Vectorised: per table one group-by over (S, L) of the active rows - a pass mask, a scenario-combination id
and J - then per S the best L. The reference with plain loops lives in the tests (test_sweeps_common.py).
"""
from __future__ import annotations

import ast
import difflib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from svcore import study as studies
from svcore.sweep.columns import describe
from svcore.sweep.derived import DerivedError, row_formula
from svcore.sweep.io import read_any


class StudyError(ValueError):
    """A study that cannot be answered as it is: the message says what to change."""


# ------------------------------------------------------------------ names: the mapping between tables

_GAIN = re.compile(r"^(?:k_?([pid])|([pid])_?gain|gain_?([pid])|([pid])_?coef)$")
_WORD = {"proportional": "p", "integral": "i", "derivative": "d"}


def normalise(name: str) -> str:
    """A column name reduced to what identifies it: lower case, no separators or units, PID gains as kp / ki / kd."""
    n = re.sub(r"\[.*?\]|\(.*?\)", "", name).strip().lower()
    for w, letter in _WORD.items():
        n = re.sub(rf"\b{w}\b", letter, n)
    n = re.sub(r"[\s\-\.]+", "_", n).strip("_")
    m = _GAIN.match(n)
    if m:
        return "k" + next(g for g in m.groups() if g)
    return n.replace("_", "")


def propose_mapping(columns: Dict[str, List[str]], threshold: float = 0.8) -> List[Dict[str, Any]]:
    """Pairs of similar names across tables -> one common name (the user confirms in the panel).

    The common name is the one most tables already use. First the same normalised name, then a similarity of
    the normalised names >= threshold. Returns [{table, column, name, score}] for every column renamed."""
    ids = list(columns)
    norm = {t: {c: normalise(c) for c in cols} for t, cols in columns.items()}
    # each normalised name -> the spellings used and in how many tables
    spell: Dict[str, Dict[str, int]] = {}
    for t in ids:
        for c, n in norm[t].items():
            spell.setdefault(n, {}).setdefault(c, 0)
            spell[n][c] += 1
    out: List[Dict[str, Any]] = []
    for t in ids:
        own = set(columns[t])
        for c in columns[t]:
            n = norm[t][c]
            cands: List[Tuple[float, str]] = []
            for n2, names in spell.items():
                score = 1.0 if n2 == n else difflib.SequenceMatcher(None, n, n2).ratio()
                if score < threshold:
                    continue
                for c2, k in names.items():
                    if c2 != c and c2 not in own:
                        cands.append((score + 0.01 * k, c2))
            if not cands:
                continue
            best_score, best = max(cands)
            # rename only towards the spelling more tables use (or the earlier table's, on a tie)
            mine = spell[n].get(c, 0)
            theirs = spell[normalise(best)].get(best, 0)
            if theirs > mine or (theirs == mine and _first_table(columns, best) < ids.index(t)):
                out.append({"table": t, "column": c, "name": best, "score": round(min(best_score, 1.0), 3)})
    return out


def _first_table(columns: Dict[str, List[str]], col: str) -> int:
    for i, cols in enumerate(columns.values()):
        if col in cols:
            return i
    return 1 << 30


# ------------------------------------------------------------------ reading the tables

@dataclass
class TableData:
    spec: studies.TableSpec
    files: List[str]
    df: pd.DataFrame                       # the files one after another, columns renamed to the common names
    roles: Dict[str, str]                  # common column name -> role (explicit, else guessed)
    shared: List[str] = field(default_factory=list)
    scenarios: List[str] = field(default_factory=list)
    local: List[str] = field(default_factory=list)


def read_table_files(files: Sequence[str]) -> pd.DataFrame:
    parts = []
    for f in files:
        try:
            parts.append(read_any(f))
        except Exception as e:     # noqa: BLE001 - any reader error names the file
            raise StudyError(f"{f}: could not be read ({e}). Check the file, or take it out of the table's paths.") from None
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True, sort=False) if len(parts) > 1 else parts[0].reset_index(drop=True)


def guessed_roles(df: pd.DataFrame) -> Dict[str, str]:
    """The Sweeps area's own guess (svcore/sweep/columns.py) in the study's words."""
    out: Dict[str, str] = {}
    for c in describe(df):
        r = c["role"]
        out[c["name"]] = "output" if r == "output" else ("scenario" if r in ("param", "hold") else "ignore")
    return out


def load_tables(s: studies.Study, frames: Optional[Dict[str, pd.DataFrame]] = None) -> List[TableData]:
    """Each table of the study, read (or taken from `frames`, by table id), renamed and with its roles resolved."""
    if len(s.tables) < 2:
        raise StudyError("A study needs at least two tables (one per system). Add a table.")
    out: List[TableData] = []
    for t in s.tables:
        files = s.table_files(t) if frames is None or t.id not in frames else []
        df = frames[t.id] if frames is not None and t.id in frames else read_table_files(files)
        if df.empty:
            raise StudyError(f"Table '{t.name or t.id}' has no rows (paths: {', '.join(t.paths) or 'none'}).")
        df = df.rename(columns=t.rename)
        roles = {**guessed_roles(df), **{c: r for c, r in t.roles.items() if c in df.columns}}
        out.append(TableData(t, files, df, roles))
    shared = [p.name for p in s.shared]
    if not shared:                         # default: an input column in every table
        common = set.intersection(*[set(td.df.columns) for td in out])
        shared = [c for c in out[0].df.columns if c in common and all(td.roles.get(c) not in ("output", "ignore") for td in out)]
    if not shared:
        raise StudyError("No shared parameter: no input column is in every table. Map the names (e.g. P_gain -> Kp) "
                         "or mark the shared columns.")
    for td in out:
        miss = [c for c in shared if c not in td.df.columns]
        if miss:
            raise StudyError(f"Table '{td.spec.name or td.spec.id}' has no column {', '.join(miss)}. Map its name "
                             f"to the shared one (its columns: {', '.join(map(str, td.df.columns[:12]))}).")
        for c in shared:
            td.roles[c] = "shared"
        td.shared = shared
        td.scenarios = [c for c in td.df.columns if td.roles.get(c) == "scenario"]
        td.local = [c for c in td.df.columns if td.roles.get(c) == "local"]
    return out


# ------------------------------------------------------------------ expressions: pass masks and margins

def _parts(expr: str) -> List[str]:
    """A constraint split at its top-level `and` (each part reported on its own when it fails)."""
    try:
        tree = ast.parse(expr.strip(), mode="eval").body
    except SyntaxError as e:
        raise StudyError(f"Constraint '{expr}': {e.msg}.") from None
    if isinstance(tree, ast.BoolOp) and isinstance(tree.op, ast.And):
        return [ast.unparse(v) for v in tree.values]
    return [expr.strip()]


def _margin_expr(part: str) -> Optional[str]:
    """For `a < b` / `a > b` (and <=, >=): an expression whose positive value is by how much it is broken."""
    tree = ast.parse(part, mode="eval").body
    if isinstance(tree, ast.Compare) and len(tree.ops) == 1:
        lhs, rhs = ast.unparse(tree.left), ast.unparse(tree.comparators[0])
        if isinstance(tree.ops[0], (ast.Lt, ast.LtE)):
            return f"({lhs}) - ({rhs})"
        if isinstance(tree.ops[0], (ast.Gt, ast.GtE)):
            return f"({rhs}) - ({lhs})"
    return None


def _eval(df: pd.DataFrame, expr: str, what: str) -> np.ndarray:
    try:
        return row_formula(df, expr)
    except DerivedError as e:
        raise StudyError(f"{what} '{expr}': {e}") from None


@dataclass
class _Checked:
    ok: np.ndarray            # the row meets every constraint
    first: np.ndarray         # index of the first broken part (-1 none)
    by: np.ndarray            # by how much that part is broken (nan unknown)
    parts: List[str]


def check(df: pd.DataFrame, constraints: Sequence[str]) -> _Checked:
    parts = [p for c in constraints for p in _parts(c)]
    n = len(df)
    ok = np.ones(n, bool)
    first = np.full(n, -1)
    by = np.full(n, np.nan)
    for k, p in enumerate(parts):
        holds = _eval(df, p, "Constraint") != 0
        broken = ~holds & ok
        first[broken] = k
        m = _margin_expr(p)
        if m is not None and broken.any():
            by[broken] = _eval(df.loc[broken], m, "Constraint")
        ok &= holds
    return _Checked(ok, first, by, parts)


# ------------------------------------------------------------------ the answer per table

def _key(df: pd.DataFrame, cols: Sequence[str], tol: Dict[str, float]) -> pd.DataFrame:
    """The values of `cols`, snapped to their matching tolerance (exact when 0)."""
    out = pd.DataFrame(index=df.index)
    for c in cols:
        v = df[c]
        t = tol.get(c, 0.0)
        if t and pd.api.types.is_numeric_dtype(v):
            v = (v / t).round() * t
        out[c] = v
    return out


@dataclass
class TableAnswer:
    """Per value of S in this table: status, score, the best local choice, the deciding scenario, the failure."""
    by_s: Dict[tuple, Dict[str, Any]]


def answer_table(td: TableData, tol: Dict[str, float]) -> TableAnswer:
    spec = td.spec
    df = td.df
    # the active rows: dropped scenario values left out
    active = np.ones(len(df), bool)
    for col, vals in spec.drop.items():
        if col in df.columns:
            active &= ~df[col].isin(vals).to_numpy()
    sub = df.loc[active]
    if sub.empty:
        raise StudyError(f"Table '{spec.name or spec.id}': every scenario value is left out.")
    chk = check(sub, spec.constraints)
    obj = spec.objective.expr.strip()
    if not obj:
        raise StudyError(f"Table '{spec.name or spec.id}' has no objective. Choose what to minimise or maximise.")
    sign = 1.0 if spec.objective.sense == "min" else -1.0
    j = sign * _eval(sub, obj, "Objective")                      # always minimised from here on
    S, L, E = td.shared, td.local, td.scenarios
    keys = _key(sub, S, tol)
    scen = sub[E] if E else pd.DataFrame(index=sub.index)
    # every active scenario combination of the table
    if E:
        combos = scen.drop_duplicates().reset_index(drop=True)
        cid = pd.MultiIndex.from_frame(scen).map({tuple(r): i for i, r in enumerate(combos.itertuples(index=False, name=None))}) \
            if len(E) > 1 else scen[E[0]].map({v: i for i, v in enumerate(combos[E[0]])})
        cid = np.asarray(cid, dtype=int)
    else:
        combos = pd.DataFrame(index=[0])
        cid = np.zeros(len(sub), int)
    n_combo = len(combos)
    frame = keys.reset_index(drop=True)
    for c in L:
        frame["__L_" + c] = sub[c].to_numpy()
    frame["__cid"] = cid
    frame["__ok"] = chk.ok
    frame["__j"] = np.where(chk.ok, j, np.nan)
    frame["__row"] = np.flatnonzero(active)
    frame["__first"] = chk.first
    frame["__by"] = chk.by
    lcols = ["__L_" + c for c in L]
    gcols = list(S) + lcols
    # one run per (S, L, scenario): duplicates (the same run twice) count once - the first
    frame = frame.drop_duplicates(subset=gcols + ["__cid"], keep="first").reset_index(drop=True)
    frame["__s"] = frame.groupby(list(S), sort=False, dropna=False).ngroup()
    frame["__g"] = frame.groupby(gcols, sort=False, dropna=False).ngroup()
    n_g = int(frame["__g"].max()) + 1
    g_s = frame.groupby("__g")["__s"].first().to_numpy()
    n = np.bincount(frame["__g"], minlength=n_g)                                  # scenarios run
    n_ok = np.bincount(frame["__g"], weights=frame["__ok"].astype(float), minlength=n_g)
    feasible = (n == n_combo) & (n_ok == n_combo)
    if spec.aggregate == "mean":
        score = np.bincount(frame["__g"], weights=np.nan_to_num(frame["__j"].to_numpy()), minlength=n_g) / np.maximum(n, 1)
    else:                                                                         # the worst case (J minimised)
        score = np.full(n_g, -np.inf)
        np.maximum.at(score, frame["__g"].to_numpy(), np.where(frame["__ok"], frame["__j"], -np.inf))
    rank_g = np.where(feasible, score, np.inf)
    # the deciding scenario per (S, L): the one with the worst J
    okf = frame[frame["__ok"]]
    worst_cid = np.full(n_g, -1)
    if len(okf):
        w = okf.sort_values("__j", ascending=False, kind="stable").drop_duplicates("__g")
        worst_cid[w["__g"].to_numpy()] = w["__cid"].to_numpy()
    # per S: the best local choice (lowest score among feasible), else the one that came closest
    n_bad = (n_combo - n) + (n - n_ok)
    groups = pd.DataFrame({"g": np.arange(n_g), "s": g_s, "r": rank_g, "bad": n_bad})
    best_g = groups.sort_values(["s", "r", "bad", "g"], kind="stable").drop_duplicates("s").set_index("s")["g"]
    first_bad = frame[~frame["__ok"]].sort_values(["__g", "__cid"], kind="stable").drop_duplicates("__g").set_index("__g")
    present = np.zeros((n_g, n_combo), bool)
    present[frame["__g"].to_numpy(), frame["__cid"].to_numpy()] = True
    runs_of = frame.groupby("__s")["__row"].agg(lambda x: sorted(int(v) for v in x))
    firsts = frame.drop_duplicates("__s").set_index("__s")
    gfirst = frame.drop_duplicates("__g").set_index("__g")
    by_s: Dict[tuple, Dict[str, Any]] = {}
    combo_rows = [{c: _py(v) for c, v in zip(E, r)} for r in combos[E].itertuples(index=False, name=None)] if E else [None]
    for sid, bg in best_g.items():
        f0 = firsts.loc[sid]
        skey = tuple(f0[c] for c in S)
        bg = int(bg)
        runs = runs_of.loc[sid]
        if feasible[bg]:
            lrow = gfirst.loc[bg] if L else None
            by_s[skey] = {"status": "pass", "score": float(sign * score[bg]),
                          "local": {c: _py(lrow["__L_" + c]) for c in L} if L and lrow is not None else None,
                          "worst": combo_rows[worst_cid[bg]] if E and agg_is_worst(spec) and worst_cid[bg] >= 0 else None,
                          "failed": None, "runs": runs, "_rank": float(score[bg])}
        else:
            if bg in first_bad.index:
                r = first_bad.loc[bg]
                k = int(r["__first"])
                failed = {"scenario": combo_rows[int(r["__cid"])], "constraint": chk.parts[k] if 0 <= k < len(chk.parts) else "",
                          "by": None if not np.isfinite(r["__by"]) else round(float(r["__by"]), 6)}
            else:
                miss = int(np.flatnonzero(~present[bg])[0])
                failed = {"scenario": combo_rows[miss], "constraint": "not run", "by": None}
            by_s[skey] = {"status": "fail", "score": None, "local": None, "worst": None, "failed": failed, "runs": runs, "_rank": np.inf}
    return TableAnswer(by_s)


def agg_is_worst(spec: studies.TableSpec) -> bool:
    return spec.aggregate != "mean"


def _py(v: Any) -> Any:
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


# ------------------------------------------------------------------ combining the tables

def _same_objective(s: studies.Study) -> bool:
    objs = {(t.objective.expr.replace(" ", ""), t.objective.sense) for t in s.tables}
    return len(objs) == 1


def combine_mode(s: studies.Study) -> str:
    if s.combine.mode in ("minworst", "pareto"):
        return s.combine.mode
    return "minworst" if _same_objective(s) else "pareto"


def pareto_mask(scores: np.ndarray) -> np.ndarray:
    """Rows of `scores` (all minimised) no other row dominates."""
    n = len(scores)
    keep = np.ones(n, bool)
    for i in range(n):
        if not keep[i]:
            continue
        dom = np.all(scores <= scores[i], axis=1) & np.any(scores < scores[i], axis=1)
        if dom.any():
            keep[i] = False
    return keep


def rank(s: studies.Study, frames: Optional[Dict[str, pd.DataFrame]] = None) -> Dict[str, Any]:
    """The ranked table (the /api/sweeps/common shape, tests/fixtures/sweeps/common.json)."""
    t0 = time.perf_counter()
    tds = load_tables(s, frames)
    S = tds[0].shared
    tol = {p.name: float(p.tolerance or 0) for p in s.shared}
    answers = [answer_table(td, tol) for td in tds]
    values = list(dict.fromkeys(k for a in answers for k in a.by_s))
    try:
        values.sort()
    except TypeError:
        pass
    mode = combine_mode(s)
    rows: List[Dict[str, Any]] = []
    for v in values:
        per = []
        for td, a in zip(tds, answers):
            r = a.by_s.get(v)
            if r is None:
                per.append({"table": td.spec.id, "status": "not_run", "score": None, "local": None, "worst": None,
                            "failed": {"scenario": None, "constraint": "not run", "by": None}, "runs": [], "_rank": np.inf})
            else:
                per.append({"table": td.spec.id, **r})
        rows.append({"values": {c: _py(x) for c, x in zip(S, v)}, "feasible": all(p["status"] == "pass" for p in per),
                     "rank": None, "pareto": False, "score": None, "tables": per})
    feas = [r for r in rows if r["feasible"]]
    if feas:
        sc = np.array([[p["_rank"] for p in r["tables"]] for r in feas], dtype=float)      # minimised
        lo, hi = sc.min(axis=0), sc.max(axis=0)
        norm = (sc - lo) / np.where(hi > lo, hi - lo, 1.0)
        w = np.array([float(s.combine.weights.get(td.spec.id, 1.0)) for td in tds])
        if mode == "minworst":
            key = sc.max(axis=1)
            sign = 1.0 if tds[0].spec.objective.sense == "min" else -1.0
            for r, k in zip(feas, key):
                r["score"] = float(sign * k)
            front = key == key.min()
        else:
            front = pareto_mask(sc)
            key = (norm * w).sum(axis=1) / max(w.sum(), 1e-12)
            for r, k in zip(feas, key):
                r["score"] = round(float(k), 6)
        order = sorted(range(len(feas)), key=lambda i: (not front[i], float(key[i])))
        for k, i in enumerate(order):
            feas[i]["rank"] = k + 1
            feas[i]["pareto"] = bool(front[i]) if mode == "pareto" else bool(front[i])
    for r in rows:
        for p in r["tables"]:
            p.pop("_rank", None)
    rows.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0))
    mapping = [{"table": t.id, "column": c, "name": n, "score": 1.0, "confirmed": True} for t in s.tables for c, n in t.rename.items()]
    return {
        "study": s.name, "mode": mode, "shared": S,
        "tables": [{"id": td.spec.id, "name": td.spec.name or td.spec.id, "files": td.files, "rows": int(len(td.df)),
                    "objective": td.spec.objective.expr, "sense": td.spec.objective.sense} for td in tds],
        "mapping": mapping,
        "rows": rows,
        "counts": {"values": len(rows), "feasible": len(feas)},
        "seconds": round(time.perf_counter() - t0, 4),
    }


def to_csv_rows(result: Dict[str, Any]) -> pd.DataFrame:
    """The ranked table flattened for a CSV export: one row per value of S, a group of columns per table."""
    out = []
    for r in result["rows"]:
        row: Dict[str, Any] = {"rank": r["rank"], **r["values"], "feasible": r["feasible"], "pareto": r["pareto"], "score": r["score"]}
        for p in r["tables"]:
            t = p["table"]
            row[f"{t}:status"] = p["status"]
            row[f"{t}:score"] = p["score"]
            for k, v in (p["local"] or {}).items():
                row[f"{t}:{k}"] = v
            row[f"{t}:worst"] = ", ".join(f"{k}={v}" for k, v in (p["worst"] or {}).items())
            f = p["failed"]
            row[f"{t}:failed"] = "" if not f else (f["constraint"] + ("" if f["by"] is None else f" by {f['by']:g}")
                                                  + ("" if not f["scenario"] else " at " + ", ".join(f"{k}={v}" for k, v in f["scenario"].items())))
        out.append(row)
    return pd.DataFrame(out)
