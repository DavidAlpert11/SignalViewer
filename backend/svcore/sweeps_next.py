"""W15: the next runs to try - given a study (svcore/study.py), the next batch of candidate values of the shared
parameters S that most improves the choice of W14, inside the study's search space. Deterministic and
explainable (numpy / pandas only); every candidate carries its reason:

1. refine   - around the best feasible values: each axis at half the local step (the distance to the nearest
              value tried on that axis), and the midpoint between the best values;
2. boundary - between neighbouring feasible and infeasible values (where a constraint's margin changes sign);
3. gap      - values run in some tables but not in others (only the missing tables get runs);
   start    - nothing run yet: a coarse grid over the search space.

A batch is counted in candidate values of S (``next.batch``, default 20); each candidate expands to its runs
in every table - the table's active scenarios x its local values - so a batch of 20 is typically a few hundred
runs. Every run gets a stable ``run_id`` (a short hash of the study name, the round, the table and the values).
Pending proposals (history: pending / submitted) are never proposed again. Nothing left at the smallest step
-> ``exhausted`` (the CLI's exit 3).
"""
from __future__ import annotations

import datetime
import hashlib
import itertools
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from svcore import study as studies
from svcore.sweep.derived import DerivedError, row_formula
from svcore.sweeps_common import StudyError, TableData, load_tables, rank

Point = Tuple[float, ...]


# ------------------------------------------------------------------ the search space

class Space:
    """The allowed values per shared parameter: bounds, the smallest step (or a list), integer, log scale."""

    def __init__(self, s: studies.Study, names: Sequence[str], tried: np.ndarray):
        self.names = list(names)
        self.params: List[Dict[str, Any]] = []
        self.constraints = list(s.search.constraints)
        for k, n in enumerate(self.names):
            p = s.search.params.get(n) or studies.SearchParam()
            col = tried[:, k] if len(tried) else np.array([])
            lo = p.min if p.min is not None else (float(np.nanmin(col)) if len(col) else 0.0)
            hi = p.max if p.max is not None else (float(np.nanmax(col)) if len(col) else 1.0)
            vals = np.array(sorted(set(p.values)), float) if p.values else None
            step = p.step
            if vals is None and not step:
                u = np.unique(col)
                step = float(np.min(np.diff(u))) / 8 if len(u) > 1 else (hi - lo) / 64 or 1.0
            if p.integer and step:
                step = max(1.0, round(step))
            self.params.append({"lo": float(lo), "hi": float(hi), "step": float(step or 0), "values": vals,
                                "int": bool(p.integer), "log": bool(p.log) and lo > 0})

    def snap(self, x: np.ndarray) -> np.ndarray:
        """Each coordinate onto its allowed values (rounded to 12 digits so equal values compare equal)."""
        out = np.array(x, float, copy=True)
        for k, p in enumerate(self.params):
            v = out[..., k]
            if p["values"] is not None:
                idx = np.abs(v[..., None] - p["values"]).argmin(axis=-1)
                v = p["values"][idx]
            else:
                v = np.clip(v, p["lo"], p["hi"])
                if p["step"] > 0:
                    if p["log"]:
                        r = 1 + p["step"] / max(p["lo"], 1e-12)          # the step at the low end, as a ratio
                        v = p["lo"] * r ** np.round(np.log(v / p["lo"]) / np.log(r))
                    else:
                        v = p["lo"] + np.round((v - p["lo"]) / p["step"]) * p["step"]
                    v = np.clip(v, p["lo"], p["hi"])
                if p["int"]:
                    v = np.round(v)
            out[..., k] = np.round(v, 12)
        return out

    def norm(self, x: np.ndarray) -> np.ndarray:
        """0..1 per axis (log axes in log), for distances."""
        out = np.array(x, float, copy=True)
        for k, p in enumerate(self.params):
            lo, hi = p["lo"], p["hi"]
            if p["log"]:
                out[..., k] = (np.log(np.maximum(out[..., k], 1e-300)) - np.log(lo)) / max(np.log(hi) - np.log(lo), 1e-12)
            else:
                out[..., k] = (out[..., k] - lo) / max(hi - lo, 1e-12)
        return out

    def min_step(self, k: int) -> float:
        p = self.params[k]
        if p["values"] is not None:
            return float(np.min(np.diff(p["values"]))) if len(p["values"]) > 1 else 1.0
        return p["step"] or 1e-9

    def allowed(self, pts: np.ndarray) -> np.ndarray:
        """Inside the bounds and meeting the constraints on S itself."""
        ok = np.ones(len(pts), bool)
        for k, p in enumerate(self.params):
            ok &= (pts[:, k] >= p["lo"] - 1e-9) & (pts[:, k] <= p["hi"] + 1e-9)
        if self.constraints and len(pts):
            df = pd.DataFrame(pts, columns=self.names)
            for c in self.constraints:
                try:
                    ok &= row_formula(df, c) != 0
                except DerivedError as e:
                    raise StudyError(f"Search constraint '{c}': {e}") from None
        return ok

    def grid(self, per_axis: int) -> np.ndarray:
        axes = []
        for p in self.params:
            if p["values"] is not None:
                idx = np.unique(np.round(np.linspace(0, len(p["values"]) - 1, min(per_axis, len(p["values"])))).astype(int))
                axes.append(p["values"][idx])
            elif p["log"]:
                axes.append(np.geomspace(p["lo"], p["hi"], per_axis))
            else:
                axes.append(np.linspace(p["lo"], p["hi"], per_axis))
        return self.snap(np.array(list(itertools.product(*axes)), float))


# ------------------------------------------------------------------ run ids, expansion

def run_id(study_name: str, round_no: int, table: str, values: Dict[str, Any]) -> str:
    key = "|".join([study_name, str(round_no), table] + [f"{k}={_fmt(values[k])}" for k in sorted(values)])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def _fmt(v: Any) -> str:
    if isinstance(v, (float, np.floating)):
        return repr(round(float(v), 12))
    return str(v)


def _py(v: Any) -> Any:
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    return v


def _table_runs(td: TableData) -> pd.DataFrame:
    """The active scenario x local combinations of a table (as the table itself has them)."""
    cols = td.scenarios + td.local
    if not cols:
        return pd.DataFrame(index=[0])
    df = td.df[cols]
    for col, vals in td.spec.drop.items():
        if col in df.columns:
            df = df[~df[col].isin(vals)]
    # every scenario combination with every local value (a local value tried in one scenario is tried in all)
    parts = []
    if td.scenarios:
        parts.append(df[td.scenarios].drop_duplicates().reset_index(drop=True))
    for c in td.local:
        parts.append(df[[c]].drop_duplicates().reset_index(drop=True))
    out = parts[0]
    for p in parts[1:]:
        out = out.merge(p, how="cross")
    return out


def _own_name(td: TableData, common: str) -> str:
    """The table's own column name for a common name (the reverse of the mapping)."""
    for own, c in td.spec.rename.items():
        if c == common:
            return own
    return common


# ------------------------------------------------------------------ the proposal

def next_runs(s: studies.Study, frames: Optional[Dict[str, pd.DataFrame]] = None, write: bool = False,
              round_no: Optional[int] = None) -> Dict[str, Any]:
    """The /api/sweeps/next-runs shape (tests/fixtures/sweeps/next_runs.json). write=True: the round's files
    in `next.folder`, the proposals appended to the study's history, the study saved (as `study next`)."""
    tds = load_tables(s, frames)
    S = tds[0].shared
    ranking = rank(s, frames)
    k = round_no if round_no is not None else (max((r.round for r in s.history), default=0) + 1)
    rows = ranking["rows"]
    pts = np.array([[float(r["values"][c]) for c in S] for r in rows], float) if rows else np.zeros((0, len(S)))
    space = Space(s, S, pts)
    pts = space.snap(pts) if len(pts) else pts
    feasible = np.array([r["feasible"] for r in rows], bool)
    rank_no = np.array([r["rank"] if r["rank"] is not None else 1 << 30 for r in rows], float)
    not_run = [[p["table"] for p in r["tables"] if p["status"] == "not_run"] for r in rows]
    # what is already taken: tried, and pending proposals
    pend = s.pending()
    pend_pts = {tuple(round(float(p.values.get(_own_name(td, c), p.values.get(c, np.nan))), 12) for c in S)
                for p in pend for td in tds if td.spec.id == p.table}
    taken = {tuple(x) for x in pts.tolist()} | pend_pts

    want = max(1, int(s.next.batch))
    mix = s.next.mix or {"refine": 0.5, "boundary": 0.3, "gap": 0.2}
    tot = sum(max(0.0, float(v)) for v in mix.values()) or 1.0
    quota = {r: int(round(want * max(0.0, float(mix.get(r, 0))) / tot)) for r in ("refine", "boundary", "gap")}
    cands: Dict[str, List[Tuple[Point, str, List[str]]]] = {"refine": [], "boundary": [], "gap": [], "start": []}

    if not len(pts):
        per = max(2, int(np.ceil(want ** (1 / max(len(S), 1)))))
        g = space.grid(per)
        cands["start"] = [(tuple(x), "a coarse grid to start from", []) for x in g[space.allowed(g)]]
    else:
        sense = 1.0 if ranking["mode"] == "pareto" or tds[0].spec.objective.sense == "min" else -1.0
        score = np.array([sense * r["score"] if r["score"] is not None else np.inf for r in rows], float)
        cands["refine"] = _refine(space, pts, feasible, rank_no, score)
        cands["boundary"] = _boundary(space, pts, feasible, rows, rank_no)
        cands["gap"] = [(tuple(pts[i]), "run in " + ", ".join(p["table"] for p in rows[i]["tables"] if p["status"] != "not_run")
                         + " but not in " + ", ".join(not_run[i]), not_run[i])
                        for i in np.argsort(rank_no, kind="stable") if not_run[i] and len(not_run[i]) < len(tds)
                        and tuple(pts[i]) not in pend_pts]

    chosen: List[Tuple[Point, str, str, List[str]]] = []
    seen = set()

    def take(reason: str, limit: int) -> None:
        for p, note, tables in cands[reason]:
            if limit <= 0 or len(chosen) >= want:
                return
            key = tuple(round(v, 12) for v in p)
            if reason != "gap" and (key in taken or key in seen):
                continue
            if reason == "gap" and key in seen:
                continue
            seen.add(key)
            chosen.append((key, reason, note, tables))
            limit -= 1

    if cands["start"]:
        take("start", want)
    else:
        for r in ("refine", "boundary", "gap"):
            take(r, quota[r])
        for r in ("refine", "boundary", "gap"):                 # a kind with too few fills from the others
            take(r, want - len(chosen))

    # the runs: each candidate in each table (a gap only in the tables that miss it)
    runs: List[Dict[str, Any]] = []
    for key, reason, note, tables in chosen:
        for td in tds:
            if reason == "gap" and td.spec.id not in tables:
                continue
            base = {_own_name(td, c): _py(v) for c, v in zip(S, key)}
            combos = _table_runs(td)
            for _, combo in combos.iterrows():
                vals = dict(base)
                for c, v in combo.items():
                    vals[_own_name(td, str(c))] = _py(v)
                runs.append({"run_id": run_id(s.name, k, td.spec.id, vals), "table": td.spec.id, "round": k,
                             "reason": reason if reason != "start" else "start", "values": vals})
    folder = s.next.folder.replace("{{round}}", str(k))
    out = {
        "study": s.name, "round": k, "written": False, "folder": folder, "files": [],
        "candidates": [{"values": {c: _py(v) for c, v in zip(S, key)}, "reason": reason, "note": note} for key, reason, note, _ in chosen],
        "runs": runs,
        "counts": {"candidates": len(chosen), "runs": len(runs),
                   **{r: sum(1 for c in chosen if c[1] == r) for r in ("refine", "boundary", "gap")}},
        "pending": len(pend), "exhausted": not chosen,
    }
    if write and chosen:
        out["files"] = write_round(s, tds, out)
        out["written"] = True
    return out


def _vertex(x0: float, line_pts: np.ndarray, line_score: np.ndarray, line_ok: np.ndarray, k: int) -> Optional[float]:
    """Where the parabola through the best value and its feasible neighbours on one axis has its minimum."""
    xs = line_pts[:, k]
    left = np.flatnonzero((xs < x0) & line_ok)
    right = np.flatnonzero((xs > x0) & line_ok)
    if not len(left) or not len(right):
        return None
    a = left[np.argmax(xs[left])]
    b = right[np.argmin(xs[right])]
    c = np.flatnonzero(xs == x0)[0]
    x = np.array([xs[a], x0, xs[b]])
    y = np.array([line_score[a], line_score[c], line_score[b]])
    den = (x[0] - x[1]) * (x[0] - x[2]) * (x[1] - x[2])
    A = (x[2] * (y[1] - y[0]) + x[1] * (y[0] - y[2]) + x[0] * (y[2] - y[1])) / den
    B = (x[2] ** 2 * (y[0] - y[1]) + x[1] ** 2 * (y[2] - y[0]) + x[0] ** 2 * (y[1] - y[2])) / den
    if not np.isfinite(A) or A <= 0:
        return None
    return float(np.clip(-B / (2 * A), x[0], x[2]))


def _refine(space: Space, pts: np.ndarray, feasible: np.ndarray, rank_no: np.ndarray,
            score: Optional[np.ndarray] = None) -> List[Tuple[Point, str, List[str]]]:
    """Around the best feasible values: the parabola's minimum on each axis of the best one, each axis +/- half
    the local step, then midpoints of the best."""
    out: List[Tuple[Point, str, List[str]]] = []
    order = [i for i in np.argsort(rank_no, kind="stable") if feasible[i]]
    if not order:
        return out
    d = len(space.names)
    for i in order[:8]:
        p = pts[i]
        for k in range(d):
            same = np.all(np.delete(pts, k, axis=1) == np.delete(p, k), axis=1)
            line = np.unique(pts[same, k])
            if i == order[0] and score is not None:
                v = _vertex(p[k], pts[same], score[same], feasible[same], k)
                if v is not None:
                    q = p.copy()
                    q[k] = v
                    q = space.snap(q[None, :])[0]
                    if not np.allclose(q, p) and space.allowed(q[None, :])[0]:
                        out.append((tuple(q), f"the parabola through the best value and its two neighbours on {space.names[k]} has its minimum here", []))
            for sgn in (-1, 1):
                nb = line[line > p[k]] if sgn > 0 else line[line < p[k]]
                if len(nb):
                    far = nb.min() if sgn > 0 else nb.max()
                    h = abs(far - p[k]) / 2
                else:                                               # the edge of what was tried: as far as the other side
                    other = line[line != p[k]]
                    h = (abs(other - p[k]).min() / 2) if len(other) else space.min_step(k) * 4
                if h < space.min_step(k) * 0.999:
                    h = space.min_step(k)
                q = p.copy()
                q[k] = p[k] + sgn * h
                q = space.snap(q[None, :])[0]
                if not np.allclose(q, p) and space.allowed(q[None, :])[0]:
                    out.append((tuple(q), f"refine around rank {int(rank_no[i])}: {space.names[k]} {'+' if sgn > 0 else '-'}{h:g}", []))
    best = [pts[i] for i in order[:4]]
    for a, b in itertools.combinations(best, 2):
        q = space.snap(((a + b) / 2)[None, :])[0]
        if space.allowed(q[None, :])[0]:
            out.append((tuple(q), "between two of the best values", []))
    # the closest moves of the best first: rank, then the order made
    return out


def _boundary(space: Space, pts: np.ndarray, feasible: np.ndarray, rows: List[Dict[str, Any]],
              rank_no: np.ndarray) -> List[Tuple[Point, str, List[str]]]:
    """Midpoints between a feasible value and its nearest infeasible neighbours (the constraint's edge)."""
    out: List[Tuple[Point, str, List[str]]] = []
    fi = [i for i in np.argsort(rank_no, kind="stable") if feasible[i]]
    bad = np.flatnonzero(~feasible & np.array([all(p["status"] != "not_run" for p in r["tables"]) for r in rows], bool)) if rows else np.array([], int)
    if not fi or not len(bad):
        return out
    n = space.norm(pts)
    for i in fi:
        dist = np.linalg.norm(n[bad] - n[i], axis=1)
        for j in bad[np.argsort(dist, kind="stable")[:3]]:
            q = space.snap(((pts[i] + pts[j]) / 2)[None, :])[0]
            if np.allclose(q, pts[i]) or np.allclose(q, pts[j]) or not space.allowed(q[None, :])[0]:
                continue
            why = next((f"{p['table']}: {p['failed']['constraint']}" for p in rows[j]["tables"] if p["status"] == "fail" and p["failed"]), "fails")
            out.append((tuple(q), f"the edge between rank {int(rank_no[i])} and a value that fails ({why})", []))
    return out


# ------------------------------------------------------------------ writing a round

def write_round(s: studies.Study, tds: List[TableData], prop: Dict[str, Any]) -> List[str]:
    """One file per table in the round's folder (the table's own input columns + run_id, reason, round), the
    proposals in the study's history (pending), the study saved."""
    k = prop["round"]
    folder = os.path.join(s.folder, prop["folder"])
    os.makedirs(folder, exist_ok=True)
    files = []
    ext = ".xlsx" if s.next.format == "xlsx" else ".csv"
    for td in tds:
        mine = [r for r in prop["runs"] if r["table"] == td.spec.id]
        if not mine:
            continue
        df = pd.DataFrame([{**r["values"], "run_id": r["run_id"], "reason": r["reason"], "round": k} for r in mine])
        if s.next.columns:
            df = df[[c for c in s.next.columns if c in df.columns]]
        path = os.path.join(folder, f"{td.spec.id}{ext}")
        if ext == ".xlsx":
            df.to_excel(path, index=False)
        else:
            df.to_csv(path, index=False, lineterminator="\n")
        files.append(os.path.relpath(path, s.folder).replace(os.sep, "/"))
    s.history.append(studies.Round(round=k, date=datetime.datetime.now().isoformat(timespec="seconds"), folder=prop["folder"],
                                   proposals=[studies.Proposal(run_id=r["run_id"], table=r["table"], values=r["values"],
                                                               reason=r["reason"], state="pending") for r in prop["runs"]]))
    if s.path:
        studies.save(s)
    return files


def mark_done(s: studies.Study, frames: Optional[Dict[str, pd.DataFrame]] = None) -> Dict[str, int]:
    """Proposals whose run is now in its table (by run_id if the table has that column, else by its values)
    become done. Returns the counts per state."""
    tds = {td.spec.id: td for td in load_tables(s, frames)}
    for r in s.history:
        for p in r.proposals:
            if p.state not in ("pending", "submitted"):
                continue
            td = tds.get(p.table)
            if td is None:
                continue
            df = td.df
            if "run_id" in df.columns and (df["run_id"].astype(str) == p.run_id).any():
                p.state = "done"
                continue
            m = np.ones(len(df), bool)
            for c, v in p.values.items():
                col = td.spec.rename.get(c, c)
                if col not in df.columns:
                    m[:] = False
                    break
                m &= np.isclose(pd.to_numeric(df[col], errors="coerce").to_numpy(float), float(v), rtol=0, atol=1e-9) \
                    if isinstance(v, (int, float)) else (df[col].astype(str) == str(v)).to_numpy()
            if m.any():
                p.state = "done"
    counts: Dict[str, int] = {}
    for r in s.history:
        for p in r.proposals:
            counts[p.state] = counts.get(p.state, 0) + 1
    return counts
