"""The shape of a study for a set of roles: sets, combinations, what is missing."""
from typing import Dict, List

import numpy as np
import pandas as pd


def summary(df: pd.DataFrame, roles: Dict[str, str]) -> Dict:
    """How many parameter sets, how many combinations of the hold-across columns, and which sets
    miss a combination or have a run that gave no outputs."""
    params = [c for c in df.columns if roles.get(c) == "param"]
    holds = [c for c in df.columns if roles.get(c) == "hold"]
    outs = [c for c in df.columns if roles.get(c) == "output"]
    out: Dict = {"rows": int(len(df)), "params": params, "holds": holds, "outputs": outs}
    # group numbers, not joined strings: a million rows in well under a second
    def ids(cols):
        return df.groupby(cols, sort=False, dropna=False, observed=True).ngroup().to_numpy()
    combo_id = ids(holds) if holds else None
    # the combinations counted from their group numbers (as drop_duplicates would, a second pass saved)
    n_combos = (int(combo_id.max()) + 1 if len(combo_id) else 0) if combo_id is not None else 1
    out["combos"] = n_combos
    if not params:
        out.update(sets=0, complete=0, missing=0, duplicates=0, failedRuns=0)
        return out
    set_id = ids(params)
    n_sets = int(set_id.max()) + 1 if len(set_id) else 0
    counts = np.bincount(set_id, minlength=n_sets)
    if combo_id is not None:
        key = set_id.astype(np.int64) * n_combos + combo_id
        if n_sets * n_combos <= 50_000_000:          # a mark per (set, combination): no sort (np.unique took 0.6 s / 1M rows)
            seen = np.zeros(n_sets * n_combos, dtype=bool)
            seen[key] = True
            distinct = seen.reshape(n_sets, n_combos).sum(axis=1)
        else:
            distinct = np.bincount(np.unique(key) // n_combos, minlength=n_sets)
        complete = int((distinct == n_combos).sum())
        duplicates = int((counts > distinct).sum())
    else:
        complete, duplicates = n_sets, int((counts > 1).sum())
    failed = int(df[outs].isna().any(axis=1).sum()) if outs else 0     # a run with an output missing did not finish
    out.update(sets=n_sets, complete=complete, missing=n_sets - complete, duplicates=duplicates, failedRuns=failed)
    return out


def head(df: pd.DataFrame, n: int = 20) -> List[List]:
    """The first rows, JSON-safe (NaN as None)."""
    h = df.head(n).astype(object).where(pd.notna(df.head(n)), None)
    return [[v.item() if hasattr(v, "item") else v for v in row] for row in h.itertuples(index=False, name=None)]
