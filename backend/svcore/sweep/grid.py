"""The parameter grid: each set's place on every parameter (the index of its value among the
values that parameter takes), and its neighbours - the sets one step away on one numeric
parameter, the same on all the others. What "near", "edge" and "stable" mean everywhere else."""
import itertools
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from svcore.sweep.evaluate import Prepared


class Grid:
    def __init__(self, p: Prepared):
        self.p = p
        vals = p.df[p.params].iloc[p.first_row].reset_index(drop=True)
        self.values = vals                                   # one row per set
        self.numeric: List[bool] = []
        self.levels: List[np.ndarray] = []
        idx = np.zeros((p.n_sets, len(p.params)), dtype=np.int64)
        for j, c in enumerate(p.params):
            col = vals[c]
            num = pd.api.types.is_numeric_dtype(col) and not pd.api.types.is_bool_dtype(col)
            self.numeric.append(bool(num))
            lv = np.unique(col.to_numpy(dtype=float)) if num else np.array(sorted(col.astype(str).unique()))
            self.levels.append(lv)
            key = col.to_numpy(dtype=float) if num else col.astype(str).to_numpy()
            idx[:, j] = np.searchsorted(lv, key)
        self.idx = idx
        self.at: Dict[Tuple, int] = {tuple(r): i for i, r in enumerate(idx.tolist())}

    def neighbours(self, s: int, only: Optional[Set[int]] = None) -> List[Tuple[int, int, int]]:
        """(set, parameter, step) one step away on one numeric parameter (of `only`, when given)."""
        out = []
        base = list(self.idx[s])
        for j, num in enumerate(self.numeric):
            if not num or (only is not None and j not in only):
                continue
            for step in (-1, 1):
                k = base[j] + step
                if 0 <= k < len(self.levels[j]):
                    nb = base.copy(); nb[j] = k
                    t = self.at.get(tuple(nb))
                    if t is not None:
                        out.append((t, j, step))
        return out

    def params_of(self, s: int) -> Dict:
        from svcore.sweep.evaluate import _py
        return {c: _py(self.values[c].iloc[s]) for c in self.p.params}


def stability(g: Grid, holds: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Per set: the share of its neighbours that also hold, and how many steps it can move on every
    numeric parameter, either way, and still hold - the smallest over them: its tolerance (0: a step
    anywhere can break it; the edge of the grid counts as the end of what is known)."""
    n = g.p.n_sets
    share = np.full(n, np.nan)
    tol = np.full(n, np.nan)
    for s in range(n):
        nb = g.neighbours(s)
        if nb:
            share[s] = float(np.mean([holds[t] for t, _, _ in nb]))
        if not holds[s]:
            continue
        steps = []
        for j, num in enumerate(g.numeric):
            if not num or len(g.levels[j]) < 2:
                continue
            for d in (-1, 1):
                if not 0 <= g.idx[s][j] + d < len(g.levels[j]):
                    continue                                 # the edge of the grid: nothing known beyond
                k, cur = 0, list(g.idx[s])
                while True:
                    cur[j] += d
                    t = g.at.get(tuple(cur))
                    if t is None or not holds[t]:
                        break
                    k += 1
                steps.append(k)
        if steps:
            tol[s] = float(min(steps))
    return share, tol


# ----------------------------------------------------------------------------- robust to a parameter
def tolerance_levels(g: Grid, j: int, s: int, tol: Dict) -> List[int]:
    """The levels of numeric parameter j within the tolerance of set s's value: {"mode": "pct" |
    "abs" | "steps", "value": v}. Its own level always."""
    k = int(g.idx[s, j])
    lv = g.levels[j].astype(float)
    mode, v = tol.get("mode", "pct"), abs(float(tol.get("value", 0) or 0))
    if mode == "steps":
        n = int(round(v))
        return list(range(max(0, k - n), min(len(lv) - 1, k + n) + 1))
    x = lv[k]
    d = abs(x) * v / 100 if mode == "pct" else v
    return [i for i in range(len(lv)) if abs(lv[i] - x) <= d * (1 + 1e-9)]


def tolerance_band(g: Grid, j: int, s: int, tol: Dict) -> Tuple[float, float]:
    """The values at the ends of set s's tolerance on parameter j."""
    lv = g.levels[j].astype(float)
    k = int(g.idx[s, j])
    mode, v = tol.get("mode", "pct"), abs(float(tol.get("value", 0) or 0))
    if mode == "steps":
        n = int(round(v))
        return float(lv[max(0, k - n)]), float(lv[min(len(lv) - 1, k + n)])
    d = abs(lv[k]) * v / 100 if mode == "pct" else v
    return float(lv[k] - d), float(lv[k] + d)


def robustness(g: Grid, holds: np.ndarray, goal: Optional[np.ndarray], maximize: bool, robust: Dict[str, Dict]):
    """Per set, over the sets within the tolerance of each robust parameter (the others the same):
    whether all of them hold, the goal's worst case among them, and how many other sets that is (0:
    the tolerance falls between the grid's values - nothing measured, run the edges: next runs'
    'robust'). Only numeric parameters can have a tolerance."""
    p = g.p
    js = [p.params.index(c) for c in robust if c in p.params and g.numeric[p.params.index(c)]]
    n = p.n_sets
    rh = np.zeros(n); rg = np.full(n, np.nan); seen = np.zeros(n)
    for s in range(n):
        base = list(g.idx[s])
        choices = [tolerance_levels(g, j, s, robust[p.params[j]]) for j in js]
        ok, worst, count = bool(holds[s]), (goal[s] if goal is not None else np.nan), 0
        for combo in itertools.product(*choices):
            cur = base.copy()
            for j, k in zip(js, combo):
                cur[j] = k
            t = g.at.get(tuple(cur))
            if t is None or t == s:
                continue
            count += 1
            ok = ok and bool(holds[t])
            if goal is not None and np.isfinite(goal[t]):
                worst = goal[t] if not np.isfinite(worst) else (min(worst, goal[t]) if maximize else max(worst, goal[t]))
        rh[s] = float(ok); rg[s] = worst; seen[s] = count
    return rh, rg, seen
