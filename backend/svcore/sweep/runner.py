"""Running the sets from Sweeps (MF06), watched live (MF11).

A *run step* says how one run is made and read:

* ``template``  the command, its arguments written with placeholders: ``{name}`` is a parameter or a
  scenario column's value, ``{out}`` a file the run writes its results to, ``{run}`` the run's number,
  ``{workdir}`` the folder. The template is split into arguments FIRST (shlex), then each argument is
  filled in - a value never becomes a second argument or a shell command (no shell is used at all);
* ``parser``    where the results are: ``json`` (an object in ``{out}``), ``csv`` (the first row of
  ``{out}``, header = names) or ``stdout`` (lines ``name = value`` or ``name: value`` the run prints);
* ``outputs``   the result columns kept (missing: everything the parser finds);
* ``parallel``  how many at once, ``timeout`` seconds per run (none: 0).

Each run is a row of the results file (CSV, appended as runs finish): its parameters and scenario
values, its outputs, ``run_status`` (ok | error | timeout) and ``run_seconds``. A run whose row is
already in that file with status ok is not run again (stop and resume, and a cache across sessions).
The file is a results table: Sweeps opens or merges it like any other.

Live state per run job (counts by status, every finished run's outputs in order, the last failures
with the end of their messages) is read by the page while the job runs.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import shlex
import subprocess
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Any, Callable, Dict, List, Optional, Sequence

STATUS_COL, SECONDS_COL = "run_status", "run_seconds"
_FIELD = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.\- ]*)\}")
_KV = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.\-]*)\s*[:=]\s*(.+?)\s*$")


class RunError(ValueError):
    pass


def fill(template: str, values: Dict[str, Any], posix: Optional[bool] = None) -> List[str]:
    """The command's arguments for one run: split first, then each placeholder filled in."""
    px = (os.name != "nt") if posix is None else posix
    try:
        parts = shlex.split(template, posix=px)
    except ValueError as e:
        raise RunError(f"The command: {e}") from None
    if not px:                     # Windows: backslashes stay, the quotes around an argument go
        parts = [q[1:-1] if len(q) >= 2 and q[0] == q[-1] and q[0] in "\"'" else q for q in parts]
    if not parts:
        raise RunError("The command is empty.")

    def one(m: "re.Match[str]") -> str:
        k = m.group(1)
        if k not in values:
            raise RunError(f"The command names {{{k}}}, which is not a parameter, a scenario column, out, run or workdir.")
        v = values[k]
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return "" if v is None else str(v)
    return [_FIELD.sub(one, p) for p in parts]


def _number(s: Any) -> Any:
    if isinstance(s, (int, float)) or s is None:
        return s
    try:
        v = float(str(s).strip())
        return v if math.isfinite(v) else None
    except ValueError:
        return str(s).strip()


def parse(kind: str, out_path: str, stdout: str) -> Dict[str, Any]:
    """The run's results as {name: value}."""
    if kind == "json":
        with open(out_path, encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            raise RunError("the results file is not a JSON object")
        return {str(k): _number(v) for k, v in d.items() if not isinstance(v, (dict, list))}
    if kind == "csv":
        with open(out_path, newline="", encoding="utf-8") as f:
            row = next(csv.DictReader(f), None)
        if row is None:
            raise RunError("the results file has no row")
        return {k: _number(v) for k, v in row.items() if k}
    if kind == "stdout":
        out = {}
        for line in stdout.splitlines():
            m = _KV.match(line)
            if m:
                out[m.group(1)] = _number(m.group(2))
        if not out:
            raise RunError("the run printed no 'name = value' line")
        return out
    raise RunError(f"Unknown parser: {kind}")


def key_of(run: Dict[str, Any], names: Sequence[str]) -> str:
    def f(v: Any) -> str:
        v = _number(v)
        return f"{v:.6g}" if isinstance(v, float) else str(v)
    return "|".join(f"{k}={f(run.get(k))}" for k in names)


class Live:
    """What the page reads while the runs go."""

    def __init__(self, total: int):
        self.lock = threading.Lock()
        self.total = total
        self.counts = {"ok": 0, "error": 0, "timeout": 0, "cached": 0, "running": 0}
        self.rows: List[Dict[str, Any]] = []          # finished runs, in order: inputs, outputs, status
        self.failures: List[Dict[str, Any]] = []      # the last 20: run, status, message tail
        self.path = ""

    def to_dict(self, since: int = 0) -> Dict[str, Any]:
        with self.lock:
            return {"total": self.total, "counts": dict(self.counts), "path": self.path,
                    "rows": self.rows[since:since + 2000], "next": min(len(self.rows), since + 2000),
                    "failures": list(self.failures)}


def run_all(runs: List[Dict[str, Any]], spec: Dict[str, Any], live: Live,
            report: Callable[[float, str], None], cancelled: Callable[[], bool]) -> Dict[str, Any]:
    """Every run (each {column: value}), ``parallel`` at a time; rows appended to ``results``."""
    template = str(spec.get("template") or "")
    workdir = os.path.abspath(os.path.expanduser(str(spec.get("workdir") or ".")))
    parser = str(spec.get("parser") or "json")
    outputs = [str(o) for o in spec.get("outputs") or []]
    parallel = max(1, min(64, int(spec.get("parallel") or 1)))
    timeout = float(spec.get("timeout") or 0) or None
    results = os.path.abspath(os.path.expanduser(str(spec.get("results") or os.path.join(workdir, "sweep_runs.csv"))))
    if not os.path.isdir(workdir):
        raise RunError(f"No folder {workdir}")
    inputs = list(runs[0].keys()) if runs else []
    scratch = os.path.join(workdir, ".signalviewer_runs")
    os.makedirs(scratch, exist_ok=True)
    ext = {"json": ".json", "csv": ".csv"}.get(parser, ".txt")
    fill(template, {**{k: 0 for k in inputs}, "out": "x", "run": 0, "workdir": workdir})   # a wrong name: before any run

    # resume: the runs already ok in the results file
    done_ok, header = set(), None
    if os.path.isfile(results):
        with open(results, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            header = r.fieldnames
            for row in r:
                if row.get(STATUS_COL) == "ok":
                    done_ok.add(key_of(row, inputs))
    live.path = results
    write_lock = threading.Lock()
    cols: List[str] = list(header) if header else []

    def write(row: Dict[str, Any]) -> None:
        nonlocal cols
        with write_lock:
            if not cols:
                cols = inputs + (outputs or [k for k in row if k not in inputs and k not in (STATUS_COL, SECONDS_COL)]) + [STATUS_COL, SECONDS_COL]
                with open(results, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(cols)
            with open(results, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(["" if row.get(c) is None else row.get(c) for c in cols])

    def one(i: int, run: Dict[str, Any]) -> Dict[str, Any]:
        out_path = os.path.join(scratch, f"run_{i}{ext}")
        if os.path.exists(out_path):
            os.remove(out_path)
        args = fill(template, {**run, "out": out_path, "run": i, "workdir": workdir})
        t0 = time.time()
        status, msg, res = "ok", "", {}
        try:
            p = subprocess.Popen(args, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except OSError as e:
            return {**run, STATUS_COL: "error", SECONDS_COL: 0.0, "_msg": f"could not start {args[0]}: {e}"}
        while True:
            try:
                so, se = p.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                if cancelled() or (timeout and time.time() - t0 > timeout):
                    p.kill()
                    so, se = p.communicate()
                    status = "cancelled" if cancelled() else "timeout"
                    msg = "stopped" if status == "cancelled" else f"longer than {timeout:g} s"
                    break
        if status == "ok":
            if p.returncode != 0:
                status, msg = "error", f"exit code {p.returncode}: {(se or so or '').strip()[-400:]}"
            else:
                try:
                    res = parse(parser, out_path, so or "")
                    if outputs:
                        missing = [o for o in outputs if o not in res]
                        if missing:
                            status, msg = "error", f"no {', '.join(missing)} in the results"
                        res = {o: res.get(o) for o in outputs}
                except (OSError, ValueError, RunError) as e:
                    status, msg = "error", f"reading the results: {e}"
        return {**run, **res, STATUS_COL: status, SECONDS_COL: round(time.time() - t0, 3), "_msg": msg}

    todo = []
    for i, run in enumerate(runs):
        if key_of(run, inputs) in done_ok:
            with live.lock:
                live.counts["cached"] += 1
        else:
            todo.append((i, run))
    finished = live.counts["cached"]
    report(finished / max(1, len(runs)), "running")
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        pending: Dict[Future, int] = {}
        it = iter(todo)
        while True:
            while len(pending) < parallel and not cancelled():
                nxt = next(it, None)
                if nxt is None:
                    break
                pending[ex.submit(one, *nxt)] = nxt[0]
                with live.lock:
                    live.counts["running"] = len(pending)
            if not pending:
                break
            ready, _ = wait(list(pending), return_when=FIRST_COMPLETED)
            for fu in ready:
                i = pending.pop(fu)
                row = fu.result()
                msg = row.pop("_msg", "")
                if row[STATUS_COL] != "cancelled":
                    write(row)
                finished += 1
                with live.lock:
                    st = row[STATUS_COL]
                    if st in live.counts:
                        live.counts[st] += 1
                    live.counts["running"] = len(pending)
                    live.rows.append({**row, "run": i})
                    if st not in ("ok", "cancelled"):
                        live.failures = (live.failures + [{"run": i, "status": st, "message": msg[-400:],
                                                          "inputs": {k: row.get(k) for k in inputs}}])[-20:]
            try:
                report(finished / max(1, len(runs)), "running")
            except Exception:                                  # cancelled: stop scheduling, finish the running ones
                pass
    with live.lock:
        live.counts["running"] = 0
    return {"path": results, **live.to_dict(0)["counts"], "total": len(runs)}
