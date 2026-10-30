"""Runs that look wrong: an output far from what its neighbours gave in the same combination - most
often a run that broke, not physics. Robust: the distance from the neighbours' median, in units
of the median absolute distance over all runs of that output."""
from typing import Dict, List

import numpy as np

from svcore.sweep.evaluate import Prepared, _py
from svcore.sweep.grid import Grid


def suspects(p: Prepared, limit: float = 6.0, top: int = 200) -> List[Dict]:
    g = Grid(p)
    if p.n_sets < 3 or not p.outputs:
        return []
    k = max((len(g.neighbours(s)) for s in range(p.n_sets)), default=0)
    if k == 0:
        return []
    nb = np.full((p.n_sets, k), -1)
    for s in range(p.n_sets):
        for i, (t, _, _) in enumerate(g.neighbours(s)):
            nb[s, i] = t
    row_at = np.full((p.n_sets, max(1, p.n_combos)), -1)
    row_at[p.set_id, p.combo_id] = np.arange(len(p.df))
    out = []
    for col in p.outputs:
        v = np.asarray(p.df[col], dtype=float) if np.issubdtype(np.asarray(p.df[col]).dtype, np.number) else None
        if v is None:
            continue
        V = np.where(row_at >= 0, v[np.clip(row_at, 0, None)], np.nan)          # set x combination
        Vn = np.where(nb[:, :, None] >= 0, V[np.clip(nb, 0, None)], np.nan)      # set x neighbour x combination
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                med = np.nanmedian(Vn, axis=1)
        res = V - med
        ok = np.isfinite(res)
        if ok.sum() < 10:
            continue
        mad = 1.4826 * float(np.median(np.abs(res[ok] - np.median(res[ok]))))
        if mad <= 0:
            continue
        z = np.abs(res) / mad
        for s, c in zip(*np.where(z > limit)):
            r = int(row_at[s, c])
            out.append({"row": int(p.row_id[r]), "set": int(s), "column": col, "value": _py(v[r]),
                        "expected": _py(med[s, c]), "z": float(z[s, c]),
                        "where": {h: _py(p.df[h].iloc[r]) for h in p.holds}, "params": g.params_of(int(s))})
    out.sort(key=lambda x: -x["z"])
    return out[:top]
