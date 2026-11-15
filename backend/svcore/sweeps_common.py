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
import os
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
    if not s.tables:
        raise StudyError("A study needs at least one table (one per system). Add a table.")
    out: List[TableData] = []
    for t in s.tables:
        files = s.table_files(t) if frames is None or t.id not in frames else []
        df = frames[t.id] if frames is not None and t.id in frames else read_table_files(files)
        if df.empty:
            raise StudyError(f"Table '{t.name or t.id}' has no rows (paths: {', '.join(t.paths) or 'none'}).")
        df = df.rename(columns=t.rename)
        roles = {**guessed_roles(df), **({"run_id": "ignore"} if "run_id" in df.columns else {}),   # the loop's own id
                 **{c: r for c, r in t.roles.items() if c in df.columns}}
        out.append(TableData(t, files, df, roles))
    shared = [p.name for p in s.shared] or (list(s.search.params) if len(out) == 1 else [])
    if not shared and len(out) == 1:       # one system (C1): what varies must be said - its scenarios are inputs too
        raise StudyError("Say which columns are the parameters (Set up - What varies): with one table every input "
                         "column could be a parameter or a scenario.")
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
        per: List[Dict[str, Any]] = []
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


# ------------------------------------------------------------------ C2: the tables by round, the set-up from a table

_ROUND = re.compile(r"round_(\d+)")
_ROWS: Dict[str, Tuple[int, int, int]] = {}      # path -> (mtime_ns, size, rows): each file counted once


def count_rows(path: str) -> int:
    """A file's rows, counted once per version of it (mtime and size) - polled with the loop's progress."""
    st = os.stat(path)
    hit = _ROWS.get(path)
    if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
        return hit[2]
    if path.lower().endswith((".csv", ".tsv", ".txt")):
        with open(path, "rb") as f:
            lines = sum(1 for line in f if line.strip())
        n = max(0, lines - 1)
    else:
        n = int(len(read_any(path)))
    _ROWS[path] = (st.st_mtime_ns, st.st_size, n)
    return n


def tables_by_round(s: studies.Study, since: Optional[float] = None) -> Dict[str, Any]:
    """Each table's files now, grouped by the round they belong to (`round_<k>` in the path; other files are the
    table's own, round None), with their rows. A file is *new* when it changed after `since` (seconds; default:
    when the study file was last saved). Also each round of the history with its runs' states."""
    if since is None:
        try:
            since = os.path.getmtime(s.path) if s.path else None
        except OSError:
            since = None
    tables = []
    for t in s.tables:
        rounds: Dict[Optional[int], List[Dict[str, Any]]] = {}
        for f in s.table_files(t):
            m = _ROUND.search(os.path.relpath(f, s.folder).replace("\\", "/"))
            k = int(m.group(1)) if m else None
            try:
                rows, mtime = count_rows(f), os.path.getmtime(f)
            except (OSError, ValueError) as e:
                rounds.setdefault(k, []).append({"path": f, "rows": None, "mtime": None, "new": False, "error": str(e)})
                continue
            rounds.setdefault(k, []).append({"path": f, "rows": rows, "mtime": mtime,
                                             "new": bool(since is not None and mtime > since)})
        out_rounds: List[Dict[str, Any]] = [
            {"round": k, "files": fs, "rows": sum(x["rows"] or 0 for x in fs), "new": any(bool(x["new"]) for x in fs)}
                      for k, fs in sorted(rounds.items(), key=lambda kv: (kv[0] is not None, kv[0] or 0))]
        tables.append({"id": t.id, "name": t.name or t.id, "paths": list(t.paths), "rounds": out_rounds,
                       "rows": sum(r["rows"] for r in out_rounds)})
    history = []
    for r in s.history:
        states = [p.state for p in r.proposals]
        history.append({"round": r.round, "date": r.date, "folder": r.folder, "runs": len(states),
                        "done": states.count("done"), "failed": states.count("failed"),
                        "pending": states.count("pending") + states.count("submitted")})
    return {"study": s.path, "folder": s.folder, "tables": tables, "history": history}


def setup_from_table(df: pd.DataFrame, roles: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """*I have results*: the study's set-up guessed from one table - what varies (the parameters, their range and
    the values seen), the scenarios (the conditions held per run, their values) and the outputs. `roles` are the
    Sweeps area's own (param / hold / output / id / ignore / recording), as set on the open table; missing ones
    are guessed."""
    cols = {c["name"]: c for c in describe(df)}
    role = {n: (roles or {}).get(n, c["role"]) for n, c in cols.items()}
    params, scenarios, outputs, other = [], [], [], []
    for n, c in cols.items():
        r = role[n]
        if r == "param":
            item: Dict[str, Any] = {"name": n, "kind": c["kind"], "distinct": c["distinct"], "values": c.get("values")}
            if c["kind"] == "number":
                item.update(min=c.get("min"), max=c.get("max"), integer=bool(c.get("integer")), log=c["scale"] == "log")
            params.append(item)
        elif r == "hold":
            scenarios.append({"name": n, "kind": c["kind"], "distinct": c["distinct"], "values": c.get("values")})
        elif r == "output":
            outputs.append(n)
        else:
            other.append(n)
    numeric = [p for p in params if p["kind"] == "number"]
    search = {p["name"]: {"min": p["min"], "max": p["max"], "integer": p["integer"], "log": p["log"]} for p in numeric}
    study_roles = {**{p["name"]: "shared" for p in numeric}, **{x["name"]: "scenario" for x in scenarios},
                   **{n: "output" for n in outputs},
                   **{n: "ignore" for n in other + [p["name"] for p in params if p["kind"] != "number"]}}
    return {"rows": int(len(df)), "params": params, "scenarios": scenarios, "outputs": outputs, "other": other,
            "shared": [{"name": p["name"]} for p in numeric], "search": {"params": search}, "roles": study_roles}


def report_html(s: studies.Study, result: Optional[Dict[str, Any]], labels: Dict[str, str], lang: str = "en",
                top: int = 20) -> str:
    """C10: one report of a study - its set-up, each table's goal, the shared answer (the best `top` values with
    each table's verdict) and the rounds run. A self-contained page (no script, no network); `labels` are the
    page's words in the user's language, sent by the UI (a missing one falls back to its key)."""
    import html as _h

    def L(k: str, **kw: Any) -> str:
        text = labels.get(k, k)
        for a, b in kw.items():
            text = text.replace("{" + a + "}", str(b))
        return _h.escape(text)

    def e(x: Any) -> str:
        return _h.escape("" if x is None else (f"{x:.6g}" if isinstance(x, float) else str(x)))

    out = [f'<!doctype html><html lang="{e(lang)}" dir="{"rtl" if lang == "he" else "ltr"}"><head><meta charset="utf-8">',
           f"<title>{e(s.name or L('title'))}</title><style>"
           "body{font:14px/1.45 system-ui,sans-serif;margin:24px auto;max-width:980px;padding:0 16px;color:#1d232b;background:#fff}"
           "h1{font-size:22px}h2{font-size:17px;margin-top:28px}table{border-collapse:collapse;margin:8px 0}"
           "th,td{border:1px solid #d5d9e0;padding:3px 8px;text-align:start;font-variant-numeric:tabular-nums}"
           "th{background:#f2f4f7}.pass{color:#1f7a3d}.fail{color:#b42318}.muted{color:#667085}"
           "</style></head><body>",
           f"<h1>{e(s.name) or L('title')}</h1>"]
    # the set-up: what varies, the constraints on it, the start grid
    out.append(f"<h2>{L('setup')}</h2><table><tr><th>{L('param')}</th><th>min</th><th>max</th><th>{L('step')}</th></tr>")
    names = [p.name for p in s.shared] or list(s.search.params)
    for n in names:
        sp = s.search.params.get(n)
        out.append(f"<tr><td>{e(n)}</td><td>{e(sp.min if sp else None)}</td><td>{e(sp.max if sp else None)}</td>"
                   f"<td>{e(sp.step if sp else None)}</td></tr>")
    out.append("</table>")
    if s.search.constraints:
        out.append(f"<p>{L('constraints')}: <code>{e('; '.join(s.search.constraints))}</code></p>")
    # each table: its goal
    out.append(f"<h2>{L('tables')}</h2><table><tr><th></th><th>{L('table')}</th><th>{L('goal')}</th><th>{L('limits')}</th>"
               f"<th>{L('over')}</th></tr>")
    for t in s.tables:
        goal = f"{'min' if t.objective.sense == 'min' else 'max'} {t.objective.expr}" if t.objective.expr else ""
        out.append(f"<tr><td>{e(t.id)}</td><td>{e(t.name or t.id)}</td><td><code>{e(goal)}</code></td>"
                   f"<td><code>{e('; '.join(t.constraints))}</code></td><td>{e(t.aggregate)}</td></tr>")
    out.append("</table>")
    # the shared answer
    out.append(f"<h2>{L('answer')}</h2>")
    if not result or not result.get("rows"):
        out.append(f"<p class='muted'>{L('noAnswer')}</p>")
    else:
        c = result["counts"]
        out.append(f"<p>{L('holds', n=c['feasible'], of=c['values'])}</p><table><tr><th>#</th>"
                   + "".join(f"<th>{e(k)}</th>" for k in result["shared"])
                   + "".join(f"<th>{e(t['id'])}</th>" for t in result["tables"]) + "</tr>")
        for r in result["rows"][:top]:
            cells = "".join(f"<td>{e(r['values'].get(k))}</td>" for k in result["shared"])
            for p in r["tables"]:
                v = e(p["score"]) if p["status"] == "pass" else L("notRun") if p["status"] == "not_run" else L("fails")
                cells += f"<td class='{e(p['status'])}'>{v}</td>"
            out.append(f"<tr><td>{e(r['rank'] or '')}</td>{cells}</tr>")
        out.append("</table>")
        if len(result["rows"]) > top:
            out.append(f"<p class='muted'>{L('more', n=len(result['rows']) - top)}</p>")
    # the rounds
    out.append(f"<h2>{L('rounds')}</h2>")
    if not s.history:
        out.append(f"<p class='muted'>{L('noRounds')}</p>")
    else:
        out.append(f"<table><tr><th>{L('round')}</th><th>{L('date')}</th><th>{L('runs')}</th><th>{L('done')}</th></tr>")
        for rd in s.history:
            done = sum(1 for p in rd.proposals if p.state == "done")
            out.append(f"<tr><td>{rd.round}</td><td>{e(rd.date)}</td><td>{len(rd.proposals)}</td><td>{done}</td></tr>")
        out.append("</table>")
    out.append("</body></html>")
    return "\n".join(out)
