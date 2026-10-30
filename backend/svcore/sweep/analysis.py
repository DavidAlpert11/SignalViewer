"""Beyond holding or not: several goals at once (Pareto front, a weighted score), which parameter
matters (main effects, importance), two parameters together (a map), and what to run next."""
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from svcore.sweep.evaluate import Prepared, _agg
from svcore.sweep.grid import Grid


# ----------------------------------------------------------------------------- several goals
def objectives(p: Prepared, objs: List[Dict], holds: np.ndarray, only_holding: bool = True):
    """objs: [{column, direction, weight}]. Worst case of each per set. Returns (pareto 0/1, score
    0..1 or NaN). A set is on the front when no other set is at least as good on every objective
    and better on one. The score is the weighted mean of each objective scaled 0 (worst set) .. 1."""
    n = p.n_sets
    if not objs:
        return None, None
    cols = []
    for o in objs:
        maximize = o.get("direction", "max") != "min"
        v = _agg(p, o["column"], "min" if maximize else "max")
        cols.append(v if maximize else -v)                      # bigger is better for all
    m = np.vstack(cols).T
    pool = np.where((holds.astype(bool) if only_holding else np.ones(n, bool)) & np.all(np.isfinite(m), axis=1))[0]
    front = np.zeros(n)
    sub = m[pool]
    for a, i in enumerate(pool):
        dom = np.all(sub >= sub[a], axis=1) & np.any(sub > sub[a], axis=1)
        if not dom.any():
            front[i] = 1
    score = np.full(n, np.nan)
    if len(pool):
        lo, hi = np.nanmin(sub, axis=0), np.nanmax(sub, axis=0)
        span = np.where(hi > lo, hi - lo, 1.0)
        w = np.array([float(o.get("weight", 1) or 0) for o in objs])
        w = w / w.sum() if w.sum() > 0 else np.full(len(objs), 1 / len(objs))
        score[pool] = ((sub - lo) / span) @ w
    return front, score


# ----------------------------------------------------------------------------- which parameter matters
def effects(p: Prepared, value: np.ndarray, holds: np.ndarray) -> Dict:
    """Per parameter and value: the mean, min and max of `value` (one per set) and the share of sets
    that hold; and each parameter's importance - the share of the spread of `value` its values
    explain (between-groups sum of squares over the total)."""
    g = Grid(p)
    out = []
    ok = np.isfinite(value)
    total = float(np.nansum((value[ok] - np.nanmean(value[ok])) ** 2)) if ok.any() else 0.0
    for j, c in enumerate(p.params):
        rows = []
        between = 0.0
        mu = np.nanmean(value[ok]) if ok.any() else np.nan
        for k, lv in enumerate(g.levels[j]):
            m = g.idx[:, j] == k
            v = value[m & ok]
            rows.append({"value": lv.item() if hasattr(lv, "item") else lv,
                         "mean": float(np.mean(v)) if len(v) else None, "min": float(np.min(v)) if len(v) else None,
                         "max": float(np.max(v)) if len(v) else None, "holding": float(np.mean(holds[m])) if m.any() else None,
                         "sets": int(m.sum())})
            if len(v):
                between += len(v) * (float(np.mean(v)) - mu) ** 2
        out.append({"param": c, "numeric": g.numeric[j], "levels": rows,
                    "importance": between / total if total > 0 else 0.0})
    return {"params": out}


def pair_map(p: Prepared, x: str, y: str, value: np.ndarray, holds: np.ndarray) -> Dict:
    """Two parameters against each other: per pair of values, the share of sets that hold and the
    best `value` among those that hold (over every value of the other parameters)."""
    g = Grid(p)
    jx, jy = p.params.index(x), p.params.index(y)
    nx, ny = len(g.levels[jx]), len(g.levels[jy])
    share = np.full((ny, nx), np.nan); best = np.full((ny, nx), np.nan); count = np.zeros((ny, nx), int)
    for s in range(p.n_sets):
        a, b = g.idx[s, jx], g.idx[s, jy]
        count[b, a] += 1
        share[b, a] = (0 if np.isnan(share[b, a]) else share[b, a]) + holds[s]
        if holds[s] and np.isfinite(value[s]):
            best[b, a] = value[s] if np.isnan(best[b, a]) else max(best[b, a], value[s])
    with np.errstate(invalid="ignore"):
        share = share / np.where(count > 0, count, np.nan)
    tolist = lambda a: [[None if not np.isfinite(v) else float(v) for v in r] for r in a]
    lv = lambda j: [v.item() if hasattr(v, "item") else v for v in g.levels[j]]
    return {"x": x, "y": y, "xs": lv(jx), "ys": lv(jy), "share": tolist(share), "best": tolist(best), "count": count.tolist()}


# ----------------------------------------------------------------------------- what to run next
KINDS = ("edge", "best", "disagree", "gaps", "missing")


def _mid(g: Grid, j: int, a: int, b: int) -> Optional[float]:
    lv = g.levels[j]
    va, vb = float(lv[a]), float(lv[b])
    if va == vb:
        return None
    if va > 0 and vb > 0 and max(va, vb) / min(va, vb) >= 4:          # a log-spaced parameter
        return float(np.sqrt(va * vb))
    m = (va + vb) / 2
    return float(np.round(m, 10))


def suggest(p: Prepared, holds: np.ndarray, goal: Optional[np.ndarray], maximize: bool, partial: np.ndarray,
            kinds: List[str], budget: int = 40, seed: int = 0) -> Dict:
    """New parameter sets to run, each with why:
    edge     - between a set that holds and a neighbour that does not: where the limit really is
    best     - between the best holding sets and their neighbours: a better one in between?
    disagree - around sets that hold in some combinations but not all
    gaps     - far from every set run so far (the emptiest corners of the space)
    missing  - sets that miss a combination or have a run with no result: run those again
    Returned round-robin over the kinds asked for, up to `budget`, without repeats."""
    g = Grid(p)
    seen = set()
    for s in range(p.n_sets):
        seen.add(tuple(g.values.iloc[s].tolist()))
    pools: Dict[str, List[Dict]] = {k: [] for k in kinds}

    def add(kind: str, base: int, j: int, value, why: Dict):
        params = g.params_of(base)
        params[p.params[j]] = value
        key = tuple(params[c] for c in p.params)
        if key in seen:
            return
        seen.add(key)
        pools[kind].append({"params": params, "kind": kind, "from": int(base), **why})

    if "edge" in pools:
        for s in range(p.n_sets):
            if not holds[s]:
                continue
            for t, j, step in g.neighbours(s):
                if not holds[t]:
                    m = _mid(g, j, g.idx[s, j], g.idx[t, j])
                    if m is not None:
                        add("edge", s, j, m, {"param": p.params[j]})
    if "best" in pools and goal is not None:
        order = np.argsort(-goal if maximize else goal)
        top = [s for s in order if holds[s] and np.isfinite(goal[s])][:5]
        for s in top:
            for t, j, step in g.neighbours(s):
                m = _mid(g, j, g.idx[s, j], g.idx[t, j])
                if m is not None:
                    add("best", s, j, m, {"param": p.params[j]})
    if "disagree" in pools:
        for s in np.where(partial == 1)[0]:
            for t, j, step in g.neighbours(int(s)):
                m = _mid(g, j, g.idx[s, j], g.idx[t, j])
                if m is not None:
                    add("disagree", int(s), j, m, {"param": p.params[j]})
    if "gaps" in pools:
        rng = np.random.default_rng(seed)
        num = [j for j, n in enumerate(g.numeric) if n and len(g.levels[j]) > 1]
        if num:
            lo = np.array([float(g.levels[j][0]) for j in num]); hi = np.array([float(g.levels[j][-1]) for j in num])
            have = np.vstack([(g.values[p.params[j]].to_numpy(dtype=float) - lo[k]) / (hi[k] - lo[k]) for k, j in enumerate(num)]).T
            cand = rng.random((max(400, budget * 20), len(num)))
            picked = []
            for _ in range(budget):
                d = np.min(np.linalg.norm(cand[:, None, :] - (np.vstack([have] + picked) if picked else have)[None, :, :], axis=2), axis=1)
                i = int(np.argmax(d))
                picked.append(cand[i:i + 1])
                vals = lo + cand[i] * (hi - lo)
                base = int(rng.integers(p.n_sets))
                params = g.params_of(base)
                for k, j in enumerate(num):
                    params[p.params[j]] = float(np.round(vals[k], 6))
                key = tuple(params[c] for c in p.params)
                if key not in seen:
                    seen.add(key)
                    pools["gaps"].append({"params": params, "kind": "gaps", "from": base, "distance": float(d[i])})
    if "missing" in pools:
        incomplete = np.where(p.covered < p.n_combos)[0]
        failed = np.zeros(p.n_sets, bool)
        if p.outputs:
            bad = p.df[p.outputs].isna().any(axis=1).to_numpy()
            failed[np.unique(p.set_id[bad])] = True
        for s in sorted(set(incomplete.tolist()) | set(np.where(failed)[0].tolist())):
            pools["missing"].append({"params": g.params_of(int(s)), "kind": "missing", "from": int(s), "set": int(s)})
    out: List[Dict] = []
    i = 0
    while len(out) < budget and any(i < len(v) for v in pools.values()):
        for k in kinds:
            if i < len(pools[k]) and len(out) < budget:
                out.append(pools[k][i])
        i += 1
    return {"suggestions": out, "available": {k: len(v) for k, v in pools.items()}}
