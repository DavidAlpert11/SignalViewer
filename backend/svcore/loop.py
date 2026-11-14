"""The optimisation loop: Signal Viewer as the manager of the runs (owner, 2026-11-13).

    propose the next runs (W15)  ->  hand them to the program / launcher (W17)  ->  wait for the results to
    appear in their folder  ->  read them (collected per round)  ->  rank (W14)  ->  propose again ...

until nothing is left to propose, the best has not changed for two rounds (converged), or a round limit. The
same loop for every study that has a `launcher` block: the smart-sweep demo (its simulator on local workers),
your own program on this PC (`local_workers`), or your farm's launcher (the loop then waits for the farm's
results in the folder - Signal Viewer is still the one that decides what runs next).

Each finished round adds a point to `loop_progress.json` next to the study (runs done, the best found): the
panel draws the convergence from it, and a loop can be stopped and started again later from where it was.
"""
from __future__ import annotations

import datetime
import itertools
import json
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from svcore import launcher as L
from svcore import study as studies
from svcore import sweeps_common, sweeps_next

PROGRESS = "loop_progress.json"
_LOCK = threading.Lock()
_RUN: Dict[str, threading.Thread] = {}
_STOP: Dict[str, bool] = {}
Measure = Callable[[studies.Study], Dict[str, Any]]


def _key(s: studies.Study) -> str:
    return os.path.abspath(s.folder)


def busy(s: studies.Study) -> bool:
    th = _RUN.get(_key(s))
    return bool(th and th.is_alive())


# ------------------------------------------------------------------ one round

def start_names(s: studies.Study) -> List[str]:
    """The parameters a study varies: its shared ones, else (one system, nothing shared yet) its search space's."""
    return [p.name for p in s.shared] or list(s.search.params)


def start_round(s: studies.Study) -> Dict[str, Any]:
    """Round 1 of a study whose tables are still empty: a coarse grid (start.grid values per parameter) x each
    table's scenarios and local values as the study declares them (start.scenarios; older studies: demo.*)."""
    plan = s.start_plan() or studies.Start()
    if not s.tables:
        raise L.LauncherError("The study has no table yet: add a system (a table) for the runs to belong to.")
    names = start_names(s)
    if not names:
        raise L.LauncherError("The study varies no parameter yet: add one (its range) under Set up - What varies.")
    space = sweeps_next.Space(s, names, np.zeros((0, len(names))))
    grid = space.grid([plan.count(n) for n in names])
    grid = grid[space.allowed(grid)]
    runs = []
    for t in s.tables:
        sc = plan.scenarios.get(t.id, {})
        combos = list(itertools.product(*sc.values())) or [()]
        keys = list(sc)
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
    return {"round": 1, "candidates": int(len(grid)), "runs": len(runs), "exhausted": False}


def _tables_empty(s: studies.Study) -> bool:
    return all(not s.table_files(t) for t in s.tables)


def propose(s: studies.Study) -> Dict[str, Any]:
    """The next round: the start grid when nothing has been run yet (and the study says its start), else W15."""
    if not s.history and _tables_empty(s):
        if s.start_plan() is None:
            raise L.LauncherError("The tables have no runs yet: give the study a start (Set up - the start grid and the "
                                  "scenarios; in the file: start.grid and start.scenarios) or a first table of runs to begin from.")
        return start_round(s)
    r = sweeps_next.next_runs(s, write=True)
    return {"round": r["round"], "candidates": r["counts"]["candidates"], "runs": r["counts"]["runs"], "exhausted": r["exhausted"]}


def measure(s: studies.Study) -> Dict[str, Any]:
    """After a round: runs done so far and the best value found (no reference: the loop's own view)."""
    done = sum(1 for r in s.history for p in r.proposals if p.state == "done")
    try:
        rk = sweeps_common.rank(s)
    except sweeps_common.StudyError:
        rk = {"rows": []}
    best = next((x for x in rk["rows"] if x["feasible"]), None)
    return {"round": s.history[-1].round if s.history else 0, "runs": done,
            "best": None if best is None else float(best["score"]), "values": None if best is None else best["values"],
            "gap_pct": None, "at": time.time()}


def run_round(s: studies.Study, on_poll=None, measure_fn: Optional[Measure] = None) -> Dict[str, Any]:
    """Propose, hand the runs over (the launcher block: a local pool or your launcher), wait for their results
    in the folder, collect them; record the progress point."""
    p = propose(s)
    if p["exhausted"]:
        return {**p, "code": 3}
    s = studies.load(s.path)
    L.submit(s)
    code, st = L.wait(s, poll=0.2, on_poll=on_poll)
    s = studies.load(s.path)
    if not st["counts"]["done"]:
        log = os.path.join(L.round_dir(s, s.history[-1]), "submit.log")
        try:
            with open(log, encoding="utf-8", errors="replace") as f:
                tail = "".join(f.readlines()[-6:]).strip()
        except OSError:
            tail = ""
        raise L.LauncherError(f"No run of round {st['round']} gave a result in the results folder "
                              f"({s.launcher.results.glob}). The command's output ({log}) ends with:\n{tail or '(nothing)'}")
    point = (measure_fn or measure)(s)
    append_point(s, point)
    return {**p, "code": code, "status": st, "point": point}


# ------------------------------------------------------------------ the progress file

def progress_path(s: studies.Study) -> str:
    return os.path.join(s.folder, PROGRESS)


def points(s: studies.Study) -> List[Dict[str, Any]]:
    try:
        with open(progress_path(s), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def append_point(s: studies.Study, point: Dict[str, Any]) -> None:
    pts = [p for p in points(s) if p["round"] != point["round"]] + [point]
    with open(progress_path(s), "w", encoding="utf-8") as f:
        json.dump(pts, f)


def mark(s: studies.Study, **flags: Any) -> None:
    pts = points(s)
    if pts:
        pts[-1].update(flags)
        with open(progress_path(s), "w", encoding="utf-8") as f:
            json.dump(pts, f)


def converged(pts: List[Dict[str, Any]]) -> bool:
    """The best unchanged for two rounds after it was found (the proposer's own rule: no reference)."""
    if len(pts) < 3:
        return False
    a, b, c = pts[-3:]
    return a["values"] is not None and a["values"] == b["values"] == c["values"]


def run_until(s: studies.Study, max_rounds: Optional[int] = None, on_round=None, measure_fn: Optional[Measure] = None) -> int:
    """Rounds until nothing is left (3), converged (0), stopped (0), the limit (0); runs that failed (4) or a round
    that timed out (5) are said, and the loop goes on."""
    limit = max_rounds or (s.demo.max_rounds if s.demo else 12)
    code = 0
    _STOP[_key(s)] = False
    start = s.history[-1].round if s.history else 0
    while (s.history[-1].round if s.history else 0) - start < limit and not _STOP.get(_key(s)):
        out = run_round(s, measure_fn=measure_fn)
        s = studies.load(s.path)
        if on_round:
            on_round(out)
        if out["code"] == 3:
            mark(s, exhausted=True)
            return 3
        code = out["code"] if out["code"] in (4, 5) else code
        if converged(points(s)):
            return 0
    return code


def start_background(s: studies.Study, action: str, max_rounds: Optional[int] = None, measure_fn: Optional[Measure] = None) -> None:
    """The panel's Next round / Run until converged, in a thread; the panel polls progress()."""
    with _LOCK:
        if busy(s):
            raise L.LauncherError("A round is already running.")
        if not s.launcher.submit:
            raise L.LauncherError("The study has no launcher command yet: say how one run (or one round) is started "
                                  "- your program, or your launcher - in the panel's Runs section.")

        def job() -> None:
            st = studies.load(s.path)
            try:
                if action == "next":
                    _STOP[_key(st)] = False
                    out = run_round(st, measure_fn=measure_fn)
                    if out.get("code") == 3:
                        mark(studies.load(s.path), exhausted=True)
                else:
                    run_until(st, max_rounds, measure_fn=measure_fn)
            except Exception as e:      # noqa: BLE001 - shown in the panel, not lost in a thread
                ERRORS[_key(st)] = str(e)

        ERRORS.pop(_key(s), None)
        th = threading.Thread(target=job, daemon=True, name="sweep-loop")
        _RUN[_key(s)] = th
        th.start()


ERRORS: Dict[str, str] = {}


def stop(s: studies.Study) -> None:
    """Stop after the round that is running (its runs finish; nothing new is sent)."""
    _STOP[_key(s)] = True


def reset(s: studies.Study) -> None:
    """Forget the loop's progress file (the rounds and their results stay where they are)."""
    try:
        os.remove(progress_path(s))
    except OSError:
        pass


# ------------------------------------------------------------------ what the panel shows

def live_counts(s: studies.Study) -> Dict[str, int]:
    states = [p.state for r in s.history for p in r.proposals]
    running_now = busy(s) or L.running(s)
    live = {"done": states.count("done"), "running": states.count("submitted") + (states.count("pending") if running_now else 0),
            "failed": states.count("failed")}
    if running_now and s.history:
        try:
            st = L.status(s, collect=False, save=False)
            live = {"done": live["done"] - sum(1 for p in s.history[-1].proposals if p.state == "done") + st["counts"]["done"],
                    "running": st["counts"]["submitted"], "failed": live["failed"] + st["counts"]["failed"]}
        except L.LauncherError:
            pass
    return live


def tried(s: studies.Study) -> List[Dict[str, Any]]:
    """Every value of the shared parameters proposed so far, with its round and whether it holds everywhere."""
    feas: Dict[tuple, bool] = {}
    try:
        for row in sweeps_common.rank(s)["rows"]:
            feas[tuple(sorted(row["values"].items()))] = row["feasible"]
    except sweeps_common.StudyError:
        pass
    names = [p.name for p in s.shared]
    out, seen = [], set()
    for r in s.history:
        for p in r.proposals:
            t = next((x for x in s.tables if x.id == p.table), None)
            own = {c: o for o, c in (t.rename.items() if t else [])}
            v = {n: p.values.get(own.get(n, n)) for n in names}
            key = tuple(sorted(v.items()))
            if key in seen:
                continue
            seen.add(key)
            out.append({"values": v, "round": r.round, "feasible": bool(feas.get(key, False)), "state": p.state})
    return out


def progress(s: studies.Study) -> Dict[str, Any]:
    """The /api/sweeps/loop/progress shape: the rounds so far, the runs now, the best, every value tried."""
    pts = points(s)
    last = pts[-1] if pts else None
    running_now = busy(s) or L.running(s)
    reason = ("running" if running_now else "exhausted" if last and last.get("exhausted") else "converged" if converged(pts)
              else "error" if _key(s) in ERRORS else "stopped" if pts else "")
    return {"study": s.name, "round": s.history[-1].round if s.history else 0, "running": running_now,
            "converged": converged(pts), "exhausted": bool(last and last.get("exhausted")), "state": reason,
            "error": ERRORS.get(_key(s), ""),
            "runs": live_counts(s),
            "points": [{"round": p["round"], "runs": p["runs"], "best": p["best"], "gap_pct": p.get("gap_pct")} for p in pts],
            "best": None if not last or last["values"] is None else {"values": last["values"], "score": last["best"]},
            "tried": tried(s), "axes": [p.name for p in s.shared],
            "launcher": {"command": list(s.launcher.submit), "mode": "run" if s.launcher.local_workers else s.launcher.submit_mode,
                         "local_workers": s.launcher.local_workers, "results": s.launcher.results.glob}}
