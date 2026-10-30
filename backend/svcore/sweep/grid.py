"""The parameter grid: each set's place on every parameter (the index of its value among the
values that parameter takes), and its neighbours - the sets one step away on one numeric
parameter, the same on all the others. What "near", "edge" and "stable" mean everywhere else."""
from typing import Dict, List, Tuple

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

    def neighbours(self, s: int) -> List[Tuple[int, int, int]]:
        """(set, parameter, step) one step away on one numeric parameter."""
        out = []
        base = list(self.idx[s])
        for j, num in enumerate(self.numeric):
            if not num:
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
