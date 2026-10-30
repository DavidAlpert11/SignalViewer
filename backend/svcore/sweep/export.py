"""The re-run list: chosen parameter sets x the must-hold-across combinations, as a CSV the run
envelope reads - the parameter columns, then the scenario columns, a row per run to make."""
import csv
from typing import Dict, List

import numpy as np

from svcore.sweep.evaluate import Prepared, _py


def rerun_rows(p: Prepared, sets: List[int], only_missing: bool = False) -> List[Dict]:
    combos = p.df[p.holds].iloc[np.unique(p.combo_id, return_index=True)[1]] if p.holds else None
    ok_run = p.df[p.outputs].notna().all(axis=1).to_numpy() if p.outputs else np.ones(len(p.df), dtype=bool)
    out: List[Dict] = []
    for si in sets:
        if not 0 <= si < p.n_sets:
            continue
        params = {c: _py(p.df[c].iloc[p.first_row[si]]) for c in p.params}
        if combos is None:
            out.append(params)
            continue
        if only_missing:                     # missing, or ran with an output left empty (it did not finish)
            m = (p.set_id == si) & ok_run
            ran = set(p.combo_id[m].tolist())
        else:
            ran = set()
        for cid, row in enumerate(combos.itertuples(index=False, name=None)):
            if cid in ran:
                continue
            out.append({**params, **{h: _py(v) for h, v in zip(p.holds, row)}})
    return out


def write_csv(path: str, rows: List[Dict], columns: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})
