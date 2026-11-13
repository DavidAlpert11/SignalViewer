"""W18: the smart-sweep demo - see the loop of W15 + W17 converge on your own PC, and what it saves compared
with running the whole grid.

The demo study (examples/smart_sweep_demo/demo.svstudy.json) holds the three drones of W14, a coarse start grid,
a fine search space and a ``launcher`` block that runs ``sim.py`` (a real program: a JSON parameters file in, one
CSV row out) on a local process pool. It runs in a work folder (``~/.signalviewer/smart_sweep_demo``), never in
the installed examples:

    round 1      the start grid (demo.start_grid values per axis x each drone's scenarios), reason "start"
    round 2..    W15's proposal (refine / boundary / gap), submitted through the launcher, collected
    stop         nothing left to propose, the best unchanged for two rounds (converged), or the round limit

The reference ("run everything") is the full fine grid computed once in-process with the closed-form model
(svcore/drone_model.py) and the same ranking code (svcore/sweeps_common.rank), cached next to the work study.
It is used only to measure - the gap to the full-grid optimum and the saving - never by the proposer.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import shutil
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from svcore import launcher as L
from svcore import study as studies
from svcore import loop, sweeps_common
from svcore.drone_model import simulate



def workdir(src_study: str) -> str:
    """Where a demo study runs: the app folder, one folder per demo study."""
    key = hashlib.sha1(os.path.abspath(src_study).encode("utf-8")).hexdigest()[:8]
    return os.path.join(os.path.expanduser("~"), ".signalviewer", "smart_sweep_demo", key)


def prepare(src_study: str, reset: bool = False) -> studies.Study:
    """The work copy of the demo (the study and its sim.py); reset = start again from nothing."""
    wd = workdir(src_study)
    target = os.path.join(wd, os.path.basename(src_study))
    if reset and os.path.isdir(wd):
        if loop.busy(studies.load(target)) if os.path.isfile(target) else False:
            raise L.LauncherError("The demo is running; wait for the round to finish before Reset.")
        shutil.rmtree(wd)
    if not os.path.isfile(target):
        os.makedirs(wd, exist_ok=True)
        src_dir = os.path.dirname(os.path.abspath(src_study))
        for name in os.listdir(src_dir):
            if name.endswith((".py", ".json")) and not name.startswith("reference"):
                shutil.copy2(os.path.join(src_dir, name), os.path.join(wd, name))
    s = studies.load(target)
    if s.demo is None:
        raise L.LauncherError(f"{src_study} has no demo block - it is not a smart-sweep demo study.")
    return s




# ------------------------------------------------------------------ the rounds




def measure(s: studies.Study) -> Dict[str, Any]:
    """After a round: the loop's point, plus the gap of the best found to the full-grid optimum (the demo's
    reference - measured with the noise-free model, so the gap is honest)."""
    point = loop.measure(s)
    if point["values"] is not None:
        ref = reference(s)
        true = true_score(s, point["values"])
        point["gap_pct"] = None if true is None else round(100 * (true - ref["score"]) / abs(ref["score"]), 4)
    return point








# ------------------------------------------------------------------ the reference: the whole fine grid

def _fine_axes(s: studies.Study) -> List[np.ndarray]:
    axes = []
    for p in s.shared:
        sp = s.search.params[p.name]
        if sp.values:
            axes.append(np.array(sorted(sp.values), float))
        else:
            assert sp.min is not None and sp.max is not None and sp.step
            n = int(round((sp.max - sp.min) / sp.step)) + 1
            axes.append(np.round(sp.min + sp.step * np.arange(n), 12))
    return axes


def reference(s: studies.Study) -> Dict[str, Any]:
    """The full fine grid, every run computed in-process (vectorised), ranked by the same code. Cached."""
    d = s.demo or studies.Demo()
    key = hashlib.sha1(json.dumps([studies.to_dict(s.search), [studies.to_dict(t) for t in s.tables], d.scenarios],
                                  sort_keys=True, default=str).encode("utf-8")).hexdigest()
    path = os.path.join(s.folder, d.reference)
    try:
        with open(path, encoding="utf-8") as f:
            cached = json.load(f)
        if cached.get("key") == key:
            return cached
    except (OSError, ValueError):
        pass
    t0 = time.perf_counter()
    names = [p.name for p in s.shared]
    grid = np.array(list(itertools.product(*_fine_axes(s))), float)
    frames = {}
    runs = 0
    for t in s.tables:
        sc = d.scenarios.get(t.id, {})
        combos = list(itertools.product(*sc.values())) or [()]
        g = np.repeat(grid, len(combos), axis=0)
        cc = np.tile(np.array(combos, dtype=float).reshape(len(combos), -1), (len(grid), 1))
        df = pd.DataFrame(g, columns=names)
        for i, k in enumerate(sc):
            df[k] = cc[:, i]
        kw = {k: df[k].to_numpy() for k in ("wind", "mass", "filter_hz") if k in df.columns}
        out = simulate(t.id, df[names[0]].to_numpy(), df[names[1]].to_numpy(), df[names[2]].to_numpy(), **kw)
        for k, v in out.items():
            df[k] = v
        df = df.rename(columns={c: o for o, c in t.rename.items()})
        frames[t.id] = df
        runs += len(df)
    rk = sweeps_common.rank(s, frames)
    best = next((x for x in rk["rows"] if x["feasible"]), None)
    if best is None:
        raise L.LauncherError("Nothing in the full grid holds in every table: loosen a constraint of the demo study.")
    ref = {"key": key, "score": float(best["score"]), "values": best["values"], "values_count": int(len(grid)),
           "runs": int(runs), "seconds": round(time.perf_counter() - t0, 3)}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ref, f)
    return ref


def true_score(s: studies.Study, values: Dict[str, Any]) -> Optional[float]:
    """The noise-free worst-table score of one value of S (to measure the found best honestly)."""
    d = s.demo or studies.Demo()
    names = [p.name for p in s.shared]
    frames = {}
    for t in s.tables:
        sc = d.scenarios.get(t.id, {})
        combos = list(itertools.product(*sc.values())) or [()]
        df = pd.DataFrame([{**{n: float(values[n]) for n in names}, **dict(zip(sc, c))} for c in combos])
        kw = {k: df[k].to_numpy(float) for k in ("wind", "mass", "filter_hz") if k in df.columns}
        out = simulate(t.id, df[names[0]].to_numpy(), df[names[1]].to_numpy(), df[names[2]].to_numpy(), **kw)
        frames[t.id] = df.assign(**out).rename(columns={c: o for o, c in t.rename.items()})
    rk = sweeps_common.rank(s, frames)
    row = rk["rows"][0] if rk["rows"] else None
    if row is None:
        return None
    if row["feasible"]:
        return float(row["score"])
    # truly infeasible (the noise let it through): its worst score anyway, so the gap is still a number
    scores = [p["score"] for p in row["tables"] if p["score"] is not None]
    return float(max(scores)) if scores else None


# ------------------------------------------------------------------ what the panel shows

def progress(s: studies.Study) -> Dict[str, Any]:
    """The /api/sweeps/demo/progress shape (tests/fixtures/sweeps/demo_progress.json): the loop's progress, plus
    the full grid's optimum and how many runs it would take, and the saving."""
    t0 = time.perf_counter()
    ref = reference(s)
    p = loop.progress(s)
    pts = p["points"]
    tol = float((s.demo or studies.Demo()).tolerance_pct)
    # the saving counts the runs up to the round that first reached the optimum (within the tolerance)
    hit = next((x for x in pts if x["gap_pct"] is not None and x["gap_pct"] <= tol), None)
    runs_done = (hit or (pts[-1] if pts else None) or {"runs": 0})["runs"]
    return {**p, "optimum": {"values": ref["values"], "score": ref["score"]},
            "full_grid": {"values": ref["values_count"], "runs": ref["runs"]},
            "saving": round(ref["runs"] / runs_done, 2) if runs_done else None,
            "tolerance_pct": tol, "seconds": round(time.perf_counter() - t0, 3)}


def start_background(s: studies.Study, action: str, max_rounds: Optional[int] = None) -> None:
    loop.start_background(s, action, max_rounds, measure_fn=measure)


def run_until(s: studies.Study, max_rounds: Optional[int] = None, on_round=None) -> int:
    return loop.run_until(s, max_rounds, on_round, measure_fn=measure)


def copy_to(src_study: str, folder: str) -> str:
    """Make the demo your own: its study and its program, copied into `folder` (a new or empty folder), with
    nothing run yet - open it in Sweeps -> Common parameters, change the program, run the loop."""
    os.makedirs(folder, exist_ok=True)
    if any(not n.startswith(".") for n in os.listdir(folder)):
        raise L.LauncherError(f"{folder} is not empty: choose a new or empty folder for the copy.")
    src_dir = os.path.dirname(os.path.abspath(src_study))
    for name in os.listdir(src_dir):
        if name.endswith((".py", ".json")) and not name.startswith("reference"):
            shutil.copy2(os.path.join(src_dir, name), os.path.join(folder, name))
    return os.path.join(folder, os.path.basename(src_study))


def sentence(p: Dict[str, Any]) -> str:
    """The one-sentence result (English; the panel has its own en / he text from the same numbers)."""
    pts = [x for x in p["points"] if x["gap_pct"] is not None]
    if not pts:
        return "No value holds in every drone yet."
    hit = next((x for x in pts if x["gap_pct"] <= p["tolerance_pct"]), None)
    last = hit or pts[-1]
    within = hit is not None
    head = (f"Found the full-grid optimum within {p['tolerance_pct']:g} %" if within
            else f"The best found is {last['gap_pct']:.2f} % from the full-grid optimum")
    return (f"{head} after {last['runs']:,} runs - the full grid needs {p['full_grid']['values']:,} x "
            f"{p['full_grid']['runs'] // max(p['full_grid']['values'], 1)} = {p['full_grid']['runs']:,} runs "
            f"(≈ {p['saving']:.0f}× fewer).")




