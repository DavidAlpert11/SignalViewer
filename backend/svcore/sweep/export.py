"""The re-run list: chosen parameter sets x the must-hold-across combinations, as a CSV the run
envelope reads - the parameter columns, then the scenario columns, a row per run to make."""
import csv
import os
import json
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


def _same(a, b) -> bool:
    """one value, as a number or as text (1 and 1.0 alike)"""
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def rerun_rows_for(p: Prepared, params: Dict, holds: Dict) -> List[Dict]:
    """A parameter set given by its values, for the combinations of the conditions with these values
    only (a split condition's value): one row per such combination."""
    out_params = {c: params.get(c) for c in p.params}
    if not p.holds:
        return [out_params]
    combos = p.df[p.holds].iloc[np.unique(p.combo_id, return_index=True)[1]]
    out: List[Dict] = []
    for row in combos.itertuples(index=False, name=None):
        vals = dict(zip(p.holds, row))
        if all(_same(_py(vals.get(k)), v) for k, v in holds.items() if k in vals):
            out.append({**out_params, **{h: _py(v) for h, v in vals.items()}})
    return out


def write_csv(path: str, rows: List[Dict], columns: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})


def _num_or_text(v):
    """A plain Python value (numpy's scalars would be written as np.int64(5)); NaN -> None."""
    if hasattr(v, "item"):
        v = v.item()
    if v is None or (isinstance(v, float) and v != v):
        return None
    return v


def write_rows(path: str, rows: List[Dict], columns: List[str]) -> None:
    """A run list in the format its name says (S17): .csv, .tsv (to paste in a spreadsheet), .json
    (a list of objects), .m (a MATLAB struct array, runs(i).name) or .py (a Python list of dicts) -
    for a simulation script to read without a CSV parser."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        with open(path, "w", encoding="utf-8") as f:
            json.dump([{c: _num_or_text(r.get(c)) for c in columns} for r in rows], f, indent=1, ensure_ascii=False)
    elif ext == ".m":
        def m(v):
            v = _num_or_text(v)
            if v is None:
                return "NaN"
            if isinstance(v, str):
                return "'" + v.replace("'", "''") + "'"
            return repr(float(v)) if isinstance(v, float) else str(v)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"% {len(rows)} runs - runs(i).<column>\n")
            f.write("runs = struct( ...\n")
            f.write(", ...\n".join(f"  '{c}', {{{', '.join(m(r.get(c)) for r in rows)}}}" for c in columns))
            f.write(");\n")
    elif ext == ".py":
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {len(rows)} runs - a list of dicts\nruns = [\n")
            for r in rows:
                f.write("    " + repr({c: _num_or_text(r.get(c)) for c in columns}) + ",\n")
            f.write("]\n")
    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=columns, delimiter="\t" if ext == ".tsv" else ",")
            w.writeheader()
            for r in rows:
                w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})
