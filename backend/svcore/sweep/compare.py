"""Two studies of the same parameter sets (before and after a change): per set, each one's goal
and whether it holds, and what changed."""
from typing import Dict

import numpy as np

from svcore.sweep.evaluate import Prepared, _py


def compare(pa: Prepared, a: Dict, pb: Prepared, b: Dict) -> Dict:
    if pa.params != pb.params:
        raise ValueError("The two tables do not have the same parameter columns.")
    key = lambda p: [tuple(str(v) for v in r) for r in p.df[p.params].iloc[p.first_row].itertuples(index=False, name=None)]
    ka, kb = key(pa), key(pb)
    at_b = {k: i for i, k in enumerate(kb)}
    rows = []
    ga, gb = a["data"].get("#goal"), b["data"].get("#goal")
    ha, hb = a["data"]["#holds"], b["data"]["#holds"]
    for i, k in enumerate(ka):
        j = at_b.get(k)
        if j is None:
            continue
        r = {"params": {c: _py(pa.df[c].iloc[pa.first_row[i]]) for c in pa.params},
             "holdsA": bool(ha[i]), "holdsB": bool(hb[j])}
        if ga is not None and gb is not None:
            r["goalA"], r["goalB"] = _py(ga[i]), _py(gb[j])
            r["delta"] = _py(gb[j] - ga[i]) if np.isfinite(ga[i]) and np.isfinite(gb[j]) else None
        rows.append(r)
    changed = [r for r in rows if r["holdsA"] != r["holdsB"]]
    return {"matched": len(rows), "onlyA": len(ka) - len(rows), "onlyB": len(kb) - len(rows),
            "nowHold": sum(1 for r in changed if r["holdsB"]), "noLongerHold": sum(1 for r in changed if r["holdsA"]),
            "rows": rows}
