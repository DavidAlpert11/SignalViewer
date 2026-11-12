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

import datetime
import hashlib
import itertools
import json
import os
import shutil
import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from svcore import launcher as L
from svcore import study as studies
from svcore import sweeps_common, sweeps_next
from svcore.drone_model import simulate

PROGRESS = "demo_progress.json"
_LOCK = threading.Lock()
_RUN: Dict[str, threading.Thread] = {}
_STOP: Dict[str, bool] = {}


def workdir(src_study: str) -> str:
    """Where a demo study runs: the app folder, one folder per demo study."""
    key = hashlib.sha1(os.path.abspath(src_study).encode("utf-8")).hexdigest()[:8]
    return os.path.join(os.path.expanduser("~"), ".signalviewer", "smart_sweep_demo", key)


def prepare(src_study: str, reset: bool = False) -> studies.Study:
    """The work copy of the demo (the study and its sim.py); reset = start again from nothing."""
    wd = workdir(src_study)
    target = os.path.join(wd, os.path.basename(src_study))
    if reset and os.path.isdir(wd):
        if busy(wd):
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


def busy(wd: str) -> bool:
    th = _RUN.get(os.path.abspath(wd))
    return bool(th and th.is_alive())


def _extra(s: studies.Study) -> Dict[str, Any]:
    d = s.demo or studies.Demo()
    return {"sleep_ms": int(d.sleep_ms), "noise": float(d.noise), "seed": int(d.seed)}


# ------------------------------------------------------------------ the rounds

def start_round(s: studies.Study) -> Dict[str, Any]:
    """Round 1: the coarse start grid x each drone's scenarios (and local values)."""
    d = s.demo or studies.Demo()
    names = [p.name for p in s.shared]
    space = sweeps_next.Space(s, names, np.zeros((0, len(names))))
    grid = space.grid(int(d.start_grid))
    grid = grid[space.allowed(grid)]
    runs = []
    for t in s.tables:
        combos = list(itertools.product(*d.scenarios.get(t.id, {}).values())) or [()]
        keys = list(d.scenarios.get(t.id, {}))
        own = {c: o for o, c in t.rename.items()}
        for g in grid:
            for c in combos:
                vals = {own.get(n, n): float(v) for n, v in zip(names, g)}
                vals.update({k: (float(v) if isinstance(v, (int, float)) else v) for k, v in zip(keys, c)})
                runs.append(studies.Proposal(run_id=sweeps_next.run_id(s.name, 1, t.id, vals), table=t.id, values=vals,
                                             reason="start", state="pending"))
    s.history.append(studies.Round(round=1, date=datetime.datetime.now().isoformat(timespec="seconds"),
                                   folder=s.next.folder.replace("{{round}}", "1"), proposals=runs))
    studies.save(s)
    return {"round": 1, "candidates": len(grid), "runs": len(runs), "exhausted": False}


def propose(s: studies.Study) -> Dict[str, Any]:
    if not s.history:
        return start_round(s)
    r = sweeps_next.next_runs(s, write=True)
    return {"round": r["round"], "candidates": r["counts"]["candidates"], "runs": r["counts"]["runs"], "exhausted": r["exhausted"]}


def run_round(s: studies.Study, on_poll=None) -> Dict[str, Any]:
    """Propose the next round, run it on the local pool, wait, collect; record the progress point."""
    p = propose(s)
    if p["exhausted"]:
        return {**p, "code": 3}
    s = studies.load(s.path)
    L.submit(s, extra=_extra(s))
    code, st = L.wait(s, poll=0.2, on_poll=on_poll)
    s = studies.load(s.path)
    point = measure(s)
    _append_point(s, point)
    return {**p, "code": code, "status": st, "point": point}


def measure(s: studies.Study) -> Dict[str, Any]:
    """After a round: runs executed so far, the best found (as measured), its gap to the full-grid optimum."""
    done = sum(1 for r in s.history for p in r.proposals if p.state == "done")
    try:
        rk = sweeps_common.rank(s)
    except sweeps_common.StudyError:
        rk = {"rows": []}
    best = next((x for x in rk["rows"] if x["feasible"]), None)
    ref = reference(s)
    gap = None
    if best is not None:
        true = true_score(s, best["values"])
        gap = None if true is None else round(100 * (true - ref["score"]) / abs(ref["score"]), 4)
    return {"round": s.history[-1].round if s.history else 0, "runs": done,
            "best": None if best is None else float(best["score"]), "values": None if best is None else best["values"],
            "gap_pct": gap}


def _progress_path(s: studies.Study) -> str:
    return os.path.join(s.folder, PROGRESS)


def _points(s: studies.Study) -> List[Dict[str, Any]]:
    try:
        with open(_progress_path(s), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _append_point(s: studies.Study, point: Dict[str, Any]) -> None:
    pts = [p for p in _points(s) if p["round"] != point["round"]] + [point]
    with open(_progress_path(s), "w", encoding="utf-8") as f:
        json.dump(pts, f)


def converged(points: List[Dict[str, Any]]) -> bool:
    """The best unchanged for two rounds after it was found (the proposer's own rule: no reference)."""
    if len(points) < 3:
        return False
    a, b, c = points[-3:]
    return a["values"] is not None and a["values"] == b["values"] == c["values"]


def run_until(s: studies.Study, max_rounds: Optional[int] = None, on_round=None) -> int:
    """Rounds until nothing is left (3), converged (0), some runs failed (4 - it goes on), the limit (0)."""
    limit = max_rounds or (s.demo.max_rounds if s.demo else 12)
    code = 0
    wd = os.path.abspath(s.folder)
    _STOP[wd] = False
    while (s.history[-1].round if s.history else 0) < limit and not _STOP.get(wd):
        out = run_round(s)
        s = studies.load(s.path)
        if on_round:
            on_round(out)
        if out["code"] == 3:
            return 3
        code = out["code"] if out["code"] in (4, 5) else code
        if converged(_points(s)):
            return 0
    return code


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
    """The /api/sweeps/demo/progress shape (tests/fixtures/sweeps/demo_progress.json)."""
    t0 = time.perf_counter()
    ref = reference(s)
    pts = _points(s)
    k = s.history[-1].round if s.history else 0
    states = [p.state for r in s.history for p in r.proposals]
    running_now = busy(s.folder) or L.running(s)
    live = {"done": states.count("done"), "running": states.count("submitted") + (states.count("pending") if running_now else 0),
            "failed": states.count("failed")}
    if running_now and s.history:
        try:
            st = L.status(s, collect=False, save=False)
            live = {"done": live["done"] - sum(1 for p in s.history[-1].proposals if p.state == "done") + st["counts"]["done"],
                    "running": st["counts"]["submitted"], "failed": live["failed"] + st["counts"]["failed"]}
        except L.LauncherError:
            pass
    feas = {}
    try:
        for row in sweeps_common.rank(s)["rows"]:
            feas[tuple(sorted(row["values"].items()))] = row["feasible"]
    except sweeps_common.StudyError:
        pass
    names = [p.name for p in s.shared]
    tried, seen = [], set()
    for r in s.history:
        for p in r.proposals:
            t = next((x for x in s.tables if x.id == p.table), None)
            own = {c: o for o, c in (t.rename.items() if t else [])}
            v = {n: p.values.get(own.get(n, n)) for n in names}
            key = tuple(sorted(v.items()))
            if key in seen:
                continue
            seen.add(key)
            tried.append({"values": v, "round": r.round, "feasible": bool(feas.get(key, False))})
    last = pts[-1] if pts else None
    tol = float((s.demo or studies.Demo()).tolerance_pct)
    # the saving counts the runs up to the round that first reached the optimum (within the tolerance)
    hit = next((p for p in pts if p["gap_pct"] is not None and p["gap_pct"] <= tol), None)
    runs_done = (hit or last or {"runs": 0})["runs"]
    return {"study": s.name, "round": k, "running": running_now, "converged": converged(pts),
            "exhausted": bool(pts and pts[-1].get("exhausted")),
            "runs": live,
            "points": [{"round": p["round"], "runs": p["runs"], "best": p["best"], "gap_pct": p["gap_pct"]} for p in pts],
            "best": None if not last or last["values"] is None else {"values": last["values"], "score": last["best"]},
            "optimum": {"values": ref["values"], "score": ref["score"]},
            "full_grid": {"values": ref["values_count"], "runs": ref["runs"]},
            "tried": tried, "axes": names,
            "saving": round(ref["runs"] / runs_done, 2) if runs_done else None,
            "tolerance_pct": tol,
            "seconds": round(time.perf_counter() - t0, 3)}


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


def start_background(s: studies.Study, action: str, max_rounds: Optional[int] = None) -> None:
    """The panel's Next round / Run until converged: in a thread, polled through progress()."""
    wd = os.path.abspath(s.folder)
    with _LOCK:
        if busy(wd):
            raise L.LauncherError("A round is already running.")

        def job() -> None:
            st = studies.load(s.path)
            if action == "next":
                out = run_round(st)
                if out.get("code") == 3:
                    _mark_exhausted(st)
            else:
                if run_until(st, max_rounds) == 3:
                    _mark_exhausted(studies.load(s.path))

        th = threading.Thread(target=job, daemon=True, name="smart-sweep-demo")
        _RUN[wd] = th
        th.start()


def stop(s: studies.Study) -> None:
    _STOP[os.path.abspath(s.folder)] = True


def _mark_exhausted(s: studies.Study) -> None:
    pts = _points(s)
    if pts:
        pts[-1]["exhausted"] = True
        with open(_progress_path(s), "w", encoding="utf-8") as f:
            json.dump(pts, f)
