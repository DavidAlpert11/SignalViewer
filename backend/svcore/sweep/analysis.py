"""Beyond holding or not: several goals at once (Pareto front, a weighted score), two parameters
together (a map), and what to run next."""
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from svcore.sweep.evaluate import Prepared, _agg
from svcore.sweep.grid import Grid


# ----------------------------------------------------------------------------- several goals
def pareto_levels(m: np.ndarray, max_level: int = 10) -> np.ndarray:
    """Non-dominated sorting of the rows of m (bigger is better on every column): 1 = the Pareto front,
    2 = the front once the first is taken away, ... Two columns: a sort and a sweep per level
    (n log n); more: each row against the front found so far (rows sorted best-first). Rows past `max_level`
    fronts get max_level + 1 (deep levels say nothing more, and peeling them all is slow)."""
    n = len(m)
    level = np.zeros(n, dtype=int)
    left = np.arange(n)
    k = 1
    while len(left):
        if k > max_level:
            level[left] = max_level + 1
            break
        sub = m[left]
        if sub.shape[1] == 2:
            # by the first column (then the second) descending: a row is on the front when its second
            # is above every second seen so far (ties on both: both on the front)
            order = np.lexsort((-sub[:, 1], -sub[:, 0]))
            on = np.zeros(len(sub), bool)
            best = -np.inf
            prev = None
            for i in order:
                row = (sub[i, 0], sub[i, 1])
                if sub[i, 1] > best or row == prev:
                    on[i] = True
                    best = max(best, sub[i, 1])
                    prev = row
        else:
            # sorted best-first on every column: a row can only be dominated by one before it, and
            # whatever dominates it is dominated by (or is) a front row - so the front seen so far
            # is enough to compare with (n x front, not n x n)
            order = np.lexsort(tuple(-sub[:, j] for j in range(sub.shape[1] - 1, -1, -1)))
            on = np.zeros(len(sub), bool)
            front_rows = np.empty((0, sub.shape[1]))
            for i in order:
                x = sub[i]
                if len(front_rows) and np.any(np.all(front_rows >= x, axis=1) & np.any(front_rows > x, axis=1)):
                    continue
                on[i] = True
                front_rows = np.vstack([front_rows, x])
        level[left[on]] = k
        left = left[~on]
        k += 1
    return level


def objectives(p: Prepared, objs: List[Dict], holds: np.ndarray, only_holding: bool = True):
    """objs: [{column, direction, weight}]. Worst case of each per set. Returns (pareto 0/1, score
    0..1, Pareto level 1.., distance to the ideal 0..1 - NaN outside the pool). A set is on the front
    when no other set is at least as good on every objective and better on one. The score is the
    weighted mean of each objective scaled 0 (worst set) .. 1; the distance is from the point best on
    every objective, in the same scaled units (weighted), 0 = ideal; and the balanced choice (1 on
    the front's set closest to the ideal, every objective counted the same)."""
    n = p.n_sets
    if not objs:
        return None, None, None, None, None
    cols = []
    for o in objs:
        maximize = o.get("direction", "max") != "min"
        v = _agg(p, o["column"], "min" if maximize else "max")
        cols.append(v if maximize else -v)                      # bigger is better for all
    m = np.vstack(cols).T
    pool = np.where((holds.astype(bool) if only_holding else np.ones(n, bool)) & np.all(np.isfinite(m), axis=1))[0]
    front = np.zeros(n)
    level = np.full(n, np.nan)
    score = np.full(n, np.nan)
    dist = np.full(n, np.nan)
    knee = np.zeros(n)
    if len(pool):
        sub = m[pool]
        lv = pareto_levels(sub)
        level[pool] = lv
        front[pool[lv == 1]] = 1
        lo, hi = np.nanmin(sub, axis=0), np.nanmax(sub, axis=0)
        span = np.where(hi > lo, hi - lo, 1.0)
        w = np.array([float(o.get("weight", 1) or 0) for o in objs])
        w = w / w.sum() if w.sum() > 0 else np.full(len(objs), 1 / len(objs))
        scaled = (sub - lo) / span
        score[pool] = scaled @ w
        dist[pool] = np.sqrt(((1 - scaled) ** 2) @ w)
        # the balanced choice: on the front, the closest to the ideal with every objective counted
        # the same (the weights rank; "balanced" means none favoured)
        if len(objs) >= 2:
            eq = np.sqrt(((1 - scaled) ** 2).mean(axis=1))
            on = np.where(lv == 1)[0]
            knee[pool[on[np.argmin(eq[on])]]] = 1
    return front, score, level, dist, knee


def best_set(rank: np.ndarray, holds: np.ndarray) -> Optional[int]:
    """The set ranked first, else the first that holds, else none."""
    if np.isfinite(rank).any():
        return int(np.nanargmin(rank))
    h = np.where(holds == 1)[0]
    return int(h[0]) if len(h) else None


def slice_mask(p: Prepared, base: int, free: List[str]) -> np.ndarray:
    """The sets equal to `base` on every parameter but those in `free`: a map's slice through it."""
    g = Grid(p)
    fixed = [j for j, c in enumerate(p.params) if c not in free]
    if not fixed:
        return np.ones(p.n_sets, bool)
    return np.all(g.idx[:, fixed] == g.idx[base, fixed], axis=1)


def pair_map(p: Prepared, x: str, y: str, value: np.ndarray, holds: np.ndarray, only: Optional[np.ndarray] = None) -> Dict:
    """Two parameters against each other: per pair of values, the share of sets that hold and the
    best `value` among those that hold (over every value of the other parameters, or only the sets
    in `only` - a slice)."""
    g = Grid(p)
    jx, jy = p.params.index(x), p.params.index(y)
    nx, ny = len(g.levels[jx]), len(g.levels[jy])
    share = np.full((ny, nx), np.nan); best = np.full((ny, nx), np.nan); count = np.zeros((ny, nx), int)
    for s in range(p.n_sets):
        if only is not None and not only[s]:
            continue
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


def map_for(p: Prepared, a: Dict, q: Dict, x: str, y: str, rest: str = "all") -> Dict:
    """The map of two parameters for an answer, as the page and the report show it: per cell the
    share of sets that hold and the best goal among them (the smallest when minimizing; without a
    goal, none); `goal` / `direction` say which, `bestAt` the cell of the best set. rest "best": a slice through the best set - the other parameters at its values
    (`fixed`; None when no set holds, and then the map is over every value)."""
    d = a["data"]
    v = d["#goal"] if "#goal" in d else d["#holds"]
    mini = (q.get("goal") or {}).get("direction") == "min" and "#goal" in d
    only, fixed = None, None
    if rest == "best":
        b = best_set(d["#rank"], d["#holds"])
        if b is not None:
            from svcore.sweep.evaluate import _py
            only = slice_mask(p, b, [x, y])
            fixed = {c: _py(d[c][b]) for c in p.params if c not in (x, y)}
    m = pair_map(p, x, y, -v if mini else v, d["#holds"], only)       # pair_map keeps the largest
    if "#goal" not in d:
        m["best"] = [[None for _ in r] for r in m["best"]]                 # no goal: no number (it was the share, 1)
    elif mini:
        m["best"] = [[None if b is None else -b for b in r] for r in m["best"]]
    # where the best set is (rank 1), for its star on the map
    at = None
    b = best_set(d["#rank"], d["#holds"]) if "#goal" in d or np.isfinite(d["#rank"]).any() else None
    if b is not None:
        from svcore.sweep.evaluate import _py
        bx, by = _py(d[x][b]), _py(d[y][b])
        if bx in m["xs"] and by in m["ys"]:
            at = [m["xs"].index(bx), m["ys"].index(by)]
    return {**m, "rest": rest, "fixed": fixed, "goal": "#goal" in d, "direction": "min" if mini else "max", "bestAt": at}


# ----------------------------------------------------------------------------- what to run next
KINDS = ("edge", "best", "disagree", "gaps", "missing", "robust")


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
            kinds: List[str], budget: int = 40, seed: int = 0, focus: Optional[List[str]] = None,
            score: Optional[np.ndarray] = None, rank: Optional[np.ndarray] = None,
            robust: Optional[Dict[str, Dict]] = None, split: str = "equal",
            shares: Optional[Dict[str, int]] = None) -> Dict:
    """New parameter sets to run, each with why:
    edge     - between a set that holds and a neighbour that does not: where the limit really is
    best     - between the best holding sets and their neighbours: a better one in between?
    disagree - around sets that hold in some combinations but not all
    gaps     - far from every set run so far (the emptiest corners of the space)
    missing  - sets that miss a combination or have a run with no result: run those again
    robust   - the ends of the tolerance of the best sets on each robust parameter: is it robust?
    Returned round-robin over the kinds asked for, up to `budget`, without repeats. How the budget
    is shared (`split`, owner 2026-11-02): equal - in turns; proportional - by how many each kind
    has; manual - `shares` sets each kind's number (their sum may be under the budget).
    focus: the parameters to explore (S06) - only they move, the others stay at the set's values
    (gaps: at the best set's); None: all of them. score (two objectives or more) picks the best
    sets instead of the goal. With none of focus / score / rank / robust the answer is as before."""
    g = Grid(p)
    only = None if focus is None else {p.params.index(c) for c in focus if c in p.params}
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
            for t, j, step in g.neighbours(s, only):
                if not holds[t]:
                    m = _mid(g, j, g.idx[s, j], g.idx[t, j])
                    if m is not None:
                        add("edge", s, j, m, {"param": p.params[j]})
    if "best" in pools and (goal is not None or score is not None):
        if score is not None:                                   # several objectives: the weighted score
            order, val = np.argsort(-np.nan_to_num(score, nan=-np.inf)), score
        else:
            assert goal is not None
            order, val = np.argsort(-goal if maximize else goal), goal
        top = [s for s in order if holds[s] and np.isfinite(val[s])][:5]
        for s in top:
            for t, j, step in g.neighbours(s, only):
                m = _mid(g, j, g.idx[s, j], g.idx[t, j])
                if m is not None:
                    add("best", s, j, m, {"param": p.params[j]})
    if "disagree" in pools:
        for s in np.where(partial == 1)[0]:
            for t, j, step in g.neighbours(int(s), only):
                m = _mid(g, j, g.idx[s, j], g.idx[t, j])
                if m is not None:
                    add("disagree", int(s), j, m, {"param": p.params[j]})
    if "gaps" in pools:
        rng = np.random.default_rng(seed)
        num = [j for j, n in enumerate(g.numeric) if n and len(g.levels[j]) > 1 and (only is None or j in only)]
        anchor = None if only is None or rank is None else best_set(rank, holds)
        if num:
            lo = np.array([float(g.levels[j][0]) for j in num]); hi = np.array([float(g.levels[j][-1]) for j in num])
            have = np.vstack([(g.values[p.params[j]].to_numpy(dtype=float) - lo[k]) / (hi[k] - lo[k]) for k, j in enumerate(num)]).T
            cand = rng.random((max(400, budget * 20), len(num)))
            picked: List[np.ndarray] = []
            for _ in range(budget):
                d = np.min(np.linalg.norm(cand[:, None, :] - (np.vstack([have] + picked) if picked else have)[None, :, :], axis=2), axis=1)
                i = int(np.argmax(d))
                picked.append(cand[i:i + 1])
                vals = lo + cand[i] * (hi - lo)
                base = anchor if anchor is not None else int(rng.integers(p.n_sets))
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
    if "robust" in pools and robust:
        from svcore.sweep.grid import tolerance_band
        ranked = [int(s) for s in np.argsort(rank) if np.isfinite(rank[s])] if rank is not None else []
        top = (ranked or [int(s) for s in np.where(holds == 1)[0]])[:5]
        for s in top:
            for name, tol in robust.items():
                if name not in p.params:
                    continue
                j = p.params.index(name)
                if not g.numeric[j] or (only is not None and j not in only):
                    continue
                cur = float(g.levels[j][g.idx[s, j]])
                for v in tolerance_band(g, j, s, tol):
                    if abs(v - cur) > 1e-12:
                        add("robust", s, j, float(np.round(v, 10)), {"param": name})
    # the budget shared in turns: one set of each kind, then a second of each... - a kind that has
    # no more leaves its turn to the others; with a small budget the first kinds asked get the one
    cap = allocate({k: len(pools[k]) for k in kinds}, kinds, budget, split, shares)
    out: List[Dict] = []
    r = 0
    while any(r < cap[k] for k in kinds):
        for kind in kinds:
            if r < cap[kind]:
                out.append(pools[kind][r])
        r += 1
    taken = {k: sum(1 for x in out if x["kind"] == k) for k in pools}
    return {"suggestions": out, "available": {k: len(v) for k, v in pools.items()}, "taken": taken, "budget": budget, "split": split}


def allocate(available: Dict[str, int], kinds: List[str], budget: int, split: str = "equal",
             shares: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    """How many sets of each kind: equal - in turns (a kind with no more leaves its turn to the
    others; with a small budget the first kinds asked get one); proportional - by what each kind
    has (largest remainders), what one cannot fill going to the others in turns; manual - the
    numbers given, each at most what that kind has, together at most the budget."""
    n = {k: 0 for k in kinds}
    if split == "manual":
        left = budget
        for k in kinds:
            n[k] = max(0, min(int((shares or {}).get(k, 0)), available[k], left))
            left -= n[k]
        return n
    if split == "proportional":
        total = sum(available[k] for k in kinds)
        if total:
            want = {k: budget * available[k] / total for k in kinds}
            # at least one of every kind that found any (while the budget lasts)
            n = {k: min(available[k], max(int(want[k]), 1 if available[k] and budget >= len(kinds) else 0)) for k in kinds}
            while sum(n.values()) > budget:
                k = max(kinds, key=lambda x: n[x])
                n[k] -= 1
            for k in sorted(kinds, key=lambda k: -(want[k] - int(want[k]))):
                if sum(n.values()) < budget and n[k] < available[k]:
                    n[k] += 1
    while sum(n.values()) < budget and any(n[k] < available[k] for k in kinds):
        for k in kinds:
            if n[k] < available[k] and sum(n.values()) < budget:
                n[k] += 1
    return n
