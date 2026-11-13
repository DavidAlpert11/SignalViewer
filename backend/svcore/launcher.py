"""W17: run a study's rounds through the user's own launcher application (Launcher mode).

Signal Viewer does not replace the launcher, does not talk to the farm's scheduler and is never installed on
compute nodes. It speaks the launcher's language, all of it written in the study's ``launcher`` block:

    study --> one parameters file per run (params_template) --> the launcher (submit: sim.exe + params) --> farm
      ^                                                                                                 |
      +----------- results read from where the runs write them (results.glob, by run_id) <--------------+

* ``params_template`` (per table allowed) - one run's parameters file, `{{column}}` from the run's values
  (svcore/placeholders.py; escaped for .xml / .json); written as ``params_name`` (default
  ``{{table}}/{{run_id}}.xml`` / ``.json``) inside the round folder.
* ``submit`` - the launcher's command line as an argument list (never a shell), cwd = the round folder, output to
  ``round_<k>/submit.log``; ``submit_mode`` ``round`` = one command per table with ``{{params_files}}`` (a list
  file of that table's parameter files) and ``{{sim_exe}}``; ``run`` = one command per run with
  ``{{params_file}}`` and ``{{run_id}}``. Placeholders also: ``{{round_dir}}``, ``{{study_dir}}``, ``{{round}}``,
  ``{{table}}`` and ``{{study_cli}}`` (this program's study command line: ``SignalViewer.exe study`` in the
  Portable, ``python -m signalviewer.study`` from the sources).
* ``results`` - where a run's result appears (a glob relative to the study, with ``{{run_id}}`` / ``{{table}}``),
  its format (a CSV row, a CSV time series reduced by expressions, JSON with a key path per output) and an
  optional converter command (gets the path, prints one CSV row). A result is found by run_id, else by the run's
  input values; the same run twice counts once (reported).
* ``status`` - done = a result is present; a failure-marker glob; a timeout per round.
* ``local_workers`` - when set, the "launcher" is a local process pool of that size running the command per run
  on this PC: the same path, used by the smart-sweep demo (W18) and to try things without a farm.

What comes back is collected per round into ``round_<k>/collected_<table>.csv`` (the run's inputs, the outputs,
``run_id``): a table whose paths include ``next/round_*/collected_<table>.csv`` grows with each round.

Safety: the command comes only from the study file the user saved (the app shows it before the first run of a
session); values from tables or results never become commands; no shell.
"""
from __future__ import annotations

import concurrent.futures as cf
import glob
import io
import json
import multiprocessing
import os
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from svcore import placeholders as ph
from svcore import study as studies

SUBMIT_JSON = "submit.json"


class LauncherError(ValueError):
    """The launcher block cannot be used as it is: the message says what to change."""


def study_cli() -> List[str]:
    """How this program's own study command line is started (a frozen Portable has no python of its own)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "study"]
    return [sys.executable, "-m", "signalviewer.study"]


# ------------------------------------------------------------------ the round and its files

def get_round(s: studies.Study, k: Optional[int] = None) -> studies.Round:
    if not s.history:
        raise LauncherError("The study has no round yet. Propose the next runs first (study next / Suggest next runs).")
    if k is None:
        return s.history[-1]
    for r in s.history:
        if r.round == k:
            return r
    raise LauncherError(f"The study has no round {k} (rounds: {', '.join(str(r.round) for r in s.history)}).")


def round_dir(s: studies.Study, r: studies.Round) -> str:
    return os.path.join(s.folder, r.folder or s.next.folder.replace("{{round}}", str(r.round)))


def _template(s: studies.Study, table: studies.TableSpec) -> Tuple[str, str]:
    """The parameters template of a table (its own, else the launcher's) and the format it is escaped for."""
    L = s.launcher
    for text, file in ((table.params_template, table.params_template_file), (L.params_template, L.params_template_file)):
        if text:
            fmt = "json" if text.lstrip().startswith(("{", "[")) else "xml" if text.lstrip().startswith("<") else "raw"
            return text, fmt
        if file:
            path = file if os.path.isabs(file) else os.path.join(s.folder, file)
            try:
                with open(path, encoding="utf-8") as f:
                    return f.read(), ph.fmt_for(path)
            except OSError as e:
                raise LauncherError(f"The parameters template {path} could not be read ({e}).") from None
    raise LauncherError("The launcher block has no params_template: take one real parameters file of your launcher, "
                        "replace its values with {{column}} placeholders and set it as the template.")


def _sim_exe(s: studies.Study, table: studies.TableSpec) -> str:
    exe = table.sim_exe or s.launcher.sim_exe
    return exe if not exe or os.path.isabs(exe) else os.path.join(s.folder, exe)


def _base_values(s: studies.Study, rdir: str, k: int, table: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # a demo study's settings are placeholders too ({{sleep_ms}}, {{noise}}, {{seed}}: W18)
    demo = {"sleep_ms": int(s.demo.sleep_ms), "noise": float(s.demo.noise), "seed": int(s.demo.seed)} if s.demo else {}
    return {"round_dir": rdir, "study_dir": s.folder, "round": k, "table": table, **demo, **(extra or {})}


def write_params(s: studies.Study, r: studies.Round, extra: Optional[Dict[str, Any]] = None) -> Dict[str, List[Tuple[studies.Proposal, str]]]:
    """One parameters file per run of the round (pending and failed ones), and a list file per table.
    Returns table -> [(proposal, absolute path)]."""
    rdir = round_dir(s, r)
    out: Dict[str, List[Tuple[studies.Proposal, str]]] = {}
    for t in s.tables:
        mine = [p for p in r.proposals if p.table == t.id and p.state in ("pending", "failed", "submitted")]
        if not mine:
            continue
        text, fmt = _template(s, t)
        name_pat = s.launcher.params_name or ("{{table}}/{{run_id}}" + {"json": ".json", "xml": ".xml"}.get(fmt, ".txt"))
        paths = []
        for p in mine:
            vals = ph.run_values({**_base_values(s, rdir, r.round, t.id, extra), "sim_exe": _sim_exe(s, t), **p.values},
                                 p.run_id, t.id, r.round)
            rel = ph.render(name_pat, vals, "raw", "params_name")
            path = os.path.join(rdir, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(ph.render(text, vals, fmt, f"the parameters template of table {t.id}"))
            paths.append((p, path))
        with open(os.path.join(rdir, f"params_files_{t.id}.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("".join(path + "\n" for _, path in paths))
        out[t.id] = paths
    return out


# ------------------------------------------------------------------ running commands

def _run_command(args: Sequence[str], cwd: str, log: str) -> int:
    """One command, no shell, output appended to the log. The study command line itself runs in this
    process when it is the program asked for (a pool worker already has it loaded)."""
    cli = study_cli()
    with open(log, "a", encoding="utf-8") as lf:
        lf.write(f"$ {' '.join(args)}\n")
        lf.flush()
        if list(args[:len(cli)]) == cli:
            from contextlib import redirect_stderr, redirect_stdout
            from signalviewer.study import main as study_main
            old = os.getcwd()
            try:
                os.chdir(cwd)
                with redirect_stdout(lf), redirect_stderr(lf):
                    try:
                        return int(study_main(list(args[len(cli):])) or 0)
                    except SystemExit as e:
                        return int(e.code or 0) if isinstance(e.code, int) else 1
                    except Exception as e:   # noqa: BLE001 - a run that crashes is a failed run, logged
                        lf.write(f"failed: {e}\n")
                        return 1
            finally:
                os.chdir(old)
        try:
            return subprocess.run(list(args), cwd=cwd, stdout=lf, stderr=subprocess.STDOUT, shell=False).returncode
        except OSError as e:
            lf.write(f"could not start: {e}\n")
            return 127


def _pool_job(args: List[str], cwd: str, log: str) -> int:
    return _run_command(args, cwd, log)


_RUNNING: Dict[str, threading.Thread] = {}       # round folder -> its local pool, while it runs


def running(s: studies.Study, k: Optional[int] = None) -> bool:
    try:
        rdir = round_dir(s, get_round(s, k))
    except LauncherError:
        return False
    th = _RUNNING.get(os.path.abspath(rdir))
    return bool(th and th.is_alive())


def submit(s: studies.Study, k: Optional[int] = None, wait: bool = False, extra: Optional[Dict[str, Any]] = None,
           dry_run: bool = False, on_done: Optional[Callable[[], None]] = None) -> Dict[str, Any]:
    """Write the round's parameter files and run the launcher command (or the local pool). The /api shape
    (tests/fixtures/sweeps/launcher_submit.json). dry_run: the files and the exact command, nothing run."""
    r = get_round(s, k)
    rdir = round_dir(s, r)
    os.makedirs(rdir, exist_ok=True)
    L = s.launcher
    if not L.submit:
        raise LauncherError("The launcher block has no submit command: set it to your launcher's command line, "
                            "e.g. [\"C:/Tools/launcher.exe\", \"--exe\", \"{{sim_exe}}\", \"--list\", \"{{params_files}}\"].")
    files = write_params(s, r, extra)
    lists = {"study_cli": study_cli()}
    mode = "run" if L.local_workers else L.submit_mode
    jobs: List[Tuple[List[str], studies.Proposal | None, str]] = []
    for t in s.tables:
        if t.id not in files:
            continue
        base = {**_base_values(s, rdir, r.round, t.id, extra), "sim_exe": _sim_exe(s, t),
                "params_files": os.path.join(rdir, f"params_files_{t.id}.txt")}
        if mode == "round":
            jobs.append((ph.render_args(L.submit, base, lists), None, t.id))
        else:
            for p, path in files[t.id]:
                jobs.append((ph.render_args(L.submit, {**base, "params_file": path, "run_id": p.run_id}, lists), p, t.id))
    log = os.path.join(rdir, "submit.log")
    shown = jobs[0][0] if jobs else []
    out = {"study": s.name, "round": r.round, "mode": mode, "command": shown, "cwd": os.path.relpath(rdir, s.folder).replace(os.sep, "/"),
           "params_files": [os.path.relpath(pth, rdir).replace(os.sep, "/") for v in files.values() for _, pth in v],
           "submitted": sum(len(v) for v in files.values()), "log": os.path.relpath(log, s.folder).replace(os.sep, "/"),
           "exit_code": None, "needs_confirm": False}
    if dry_run or not jobs:
        return out
    record = {"started": time.time(), "mode": mode, "commands": [j[0] for j in jobs], "exit_codes": {}, "finished": None}
    in_jobs = {id(j[1]) for j in jobs}
    for prop in r.proposals:
        if id(prop) in in_jobs or (mode == "round" and prop.table in files):
            prop.state = "submitted"
    _write_record(rdir, record)
    if s.path:
        studies.save(s)

    def finish(codes: Dict[str, int]) -> None:
        record["exit_codes"] = codes
        record["finished"] = time.time()
        _write_record(rdir, record)
        if on_done:
            on_done()

    if L.local_workers:
        workers = max(1, int(L.local_workers))

        def pool() -> None:
            codes: Dict[str, int] = {}
            ctx = multiprocessing.get_context("spawn")       # the same on every OS; safe from a server thread
            with cf.ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as ex:
                futs = {ex.submit(_pool_job, a, rdir, log): (p.run_id if p else tid) for a, p, tid in jobs}
                for f in cf.as_completed(futs):
                    try:
                        codes[futs[f]] = f.result()
                    except Exception:                         # noqa: BLE001 - a worker that died: that run failed
                        codes[futs[f]] = 1
            finish(codes)

        th = threading.Thread(target=pool, daemon=True, name=f"study-pool-{r.round}")
        _RUNNING[os.path.abspath(rdir)] = th
        th.start()
        if wait:
            th.join()
        out["exit_code"] = 0
        return out
    codes = {}
    for a, job_p, tid in jobs:
        codes[job_p.run_id if job_p else tid] = _run_command(a, rdir, log)
    finish(codes)
    out["exit_code"] = max(codes.values()) if codes else 0
    return out


def _write_record(rdir: str, rec: Dict[str, Any]) -> None:
    tmp = os.path.join(rdir, SUBMIT_JSON + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f)
    os.replace(tmp, os.path.join(rdir, SUBMIT_JSON))


def _read_record(rdir: str) -> Dict[str, Any]:
    try:
        with open(os.path.join(rdir, SUBMIT_JSON), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ------------------------------------------------------------------ results

def read_small_csvs(files: Sequence[str]) -> pd.DataFrame:
    """Many small CSV files (one row each) as one table, fast: the texts joined under their header and parsed
    once (5 000 files in well under a second). Files with another header are parsed as their own group."""
    groups: Dict[str, List[str]] = {}
    for f in files:
        try:
            with open(f, encoding="utf-8-sig") as fh:
                text = fh.read()
        except OSError:
            continue
        head, _, body = text.partition("\n")
        if not body.strip():
            continue
        groups.setdefault(head.strip(), []).append(body if body.endswith("\n") else body + "\n")
    parts = [pd.read_csv(io.StringIO(h + "\n" + "".join(bodies))) for h, bodies in groups.items()]
    return pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()


def _result_glob(s: studies.Study, table: str, run_id: str) -> str:
    pat = ph.render(s.launcher.results.glob, {"run_id": run_id, "table": table}, "raw", "results.glob")
    return pat if os.path.isabs(pat) else os.path.join(s.folder, pat)


def _matches(s: studies.Study, table: str, run_id: str, path: str) -> bool:
    import fnmatch
    return fnmatch.fnmatch(os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(_result_glob(s, table, run_id))))


def _parse_result(s: studies.Study, path: str, rdir: str) -> Dict[str, Any]:
    """One run's outputs from its result file, in the results block's format."""
    R = s.launcher.results
    if R.converter:
        args = ph.render_args(R.converter, {"path": path}, {"study_cli": study_cli()}, "results.converter")
        cp = subprocess.run(args, cwd=rdir, capture_output=True, text=True, shell=False)
        if cp.returncode != 0:
            raise LauncherError(f"The converter failed on {path}: {cp.stderr.strip()[:200]}")
        df = pd.read_csv(io.StringIO(cp.stdout))
        return df.iloc[-1].to_dict() if len(df) else {}
    if R.format == "json":
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        out = {}
        for name, keys in (R.json_keys or {}).items():
            v: Any = d
            for k in keys.split("."):
                v = v[int(k)] if isinstance(v, list) else v[k]
            out[name] = v
        return out if R.json_keys else {k: v for k, v in d.items() if not isinstance(v, (dict, list))}
    if R.format in ("csv_series", "loader"):
        if R.format == "loader":                    # any file the app reads (.bin, .mat, .csv…), one time base
            from signalviewer import load
            df = load(path).to_dataframe()
        else:
            df = pd.read_csv(path)
        return {name: _reduce(df, expr) for name, expr in (R.reduce or {}).items()}
    df = pd.read_csv(path)
    return df.iloc[-1].to_dict() if len(df) else {}


_REDUCERS: Dict[str, Callable[[pd.Series], float]] = {
    "max": lambda x: float(x.max()), "min": lambda x: float(x.min()), "mean": lambda x: float(x.mean()),
    "last": lambda x: float(x.iloc[-1]), "first": lambda x: float(x.iloc[0]), "std": lambda x: float(x.std()),
    "absmax": lambda x: float(x.abs().max()), "rms": lambda x: float((x ** 2).mean() ** 0.5)}


def _reduce(df: pd.DataFrame, expr: str) -> float:
    """`max(x)`, `absmax(roll)`, `last(t)`… - one reducer of one column of a time series."""
    import re
    m = re.fullmatch(r"\s*(\w+)\(\s*([^()]+?)\s*\)\s*", expr)
    if not m or m.group(1) not in _REDUCERS or m.group(2) not in df.columns:
        raise LauncherError(f"results.reduce '{expr}': write reducer(column), reducer one of {', '.join(_REDUCERS)}, "
                            f"column one of {', '.join(map(str, df.columns[:10]))}.")
    return _REDUCERS[m.group(1)](pd.to_numeric(df[m.group(2)], errors="coerce"))


def status(s: studies.Study, k: Optional[int] = None, collect: bool = True, save: bool = True) -> Dict[str, Any]:
    """Each run of the round: done (a result found), failed (a marker, or its command failed), submitted, or
    missing (the round timed out). Collects what came back into collected_<table>.csv and marks the
    proposals in the history. The /api shape (tests/fixtures/sweeps/launcher_status.json)."""
    r = get_round(s, k)
    rdir = round_dir(s, r)
    rec = _read_record(rdir)
    codes = rec.get("exit_codes") or {}
    timeout = s.launcher.status.timeout_s
    timed_out = bool(timeout and rec.get("started") and not rec.get("finished") and time.time() - rec["started"] > timeout)
    tables = {t.id: t for t in s.tables}
    # results by table: one listing per table, not one glob per run (thousands of runs in a folder)
    hits_of: Dict[str, List[str]] = {}
    for tid in {p.table for p in r.proposals}:
        ids = {p.run_id for p in r.proposals if p.table == tid}
        n = len(next(iter(ids)))
        for f in glob.glob(_result_glob(s, tid, "*")):
            if f.endswith(".tmp"):
                continue
            name = os.path.relpath(f, s.folder)
            for i in range(len(name) - n + 1):
                if name[i:i + n] in ids and _matches(s, tid, name[i:i + n], f):
                    hits_of.setdefault(name[i:i + n], []).append(f)
                    break
    runs, dup = [], 0
    rows: Dict[str, List[Dict[str, Any]]] = {}
    pending_by_values: List[studies.Proposal] = []
    for p in r.proposals:
        hits = hits_of.get(p.run_id, [])
        marker = s.launcher.status.failed_glob and glob.glob(os.path.join(s.folder, ph.render(
            s.launcher.status.failed_glob, {"run_id": p.run_id, "table": p.table}, "raw", "status.failed_glob")))
        if hits:
            dup += len(hits) - 1
            state, res = "done", sorted(hits)[0]
        elif marker or (p.run_id in codes and codes[p.run_id] != 0):
            state, res = "failed", None
        elif p.state == "pending" and not rec:
            state, res = "pending", None
        else:
            # one command per run (run mode) and that command is done: nothing more will come for it
            ended = rec.get("mode") == "run" and p.run_id in codes and rec.get("finished") and time.time() - rec["finished"] > 2
            state, res = ("missing" if timed_out or ended else "submitted"), None
            pending_by_values.append(p)
        runs.append({"run_id": p.run_id, "table": p.table, "state": state, "result": res and os.path.relpath(res, s.folder).replace(os.sep, "/")})
        if state in ("done", "failed"):
            p.state = state
        if state == "done" and collect:
            rows.setdefault(p.table, []).append((p, res))     # type: ignore[arg-type]
    # not found by run_id: by the run's input values (a launcher that names its results its own way)
    if pending_by_values:
        for tid in {p.table for p in pending_by_values}:
            pat = _result_glob(s, tid, "*")
            files = [f for f in glob.glob(pat) if not f.endswith(".tmp")]
            if not files or s.launcher.results.format != "csv_row":
                continue
            allrows = read_small_csvs(files)
            for p in [q for q in pending_by_values if q.table == tid]:
                m = pd.Series(True, index=allrows.index)
                for c, v in p.values.items():
                    if c not in allrows.columns:
                        m &= False
                        break
                    m &= (pd.to_numeric(allrows[c], errors="coerce") - float(v)).abs() < 1e-9 if isinstance(v, (int, float)) else allrows[c].astype(str) == str(v)
                if m.any():
                    dup += int(m.sum()) - 1
                    p.state = "done"
                    entry = next(x for x in runs if x["run_id"] == p.run_id)
                    entry["state"] = "done"
                    if collect:
                        rows.setdefault(tid, []).append((p, allrows[m].iloc[0].to_dict()))   # type: ignore[arg-type]
    if collect:
        _collect(s, r, rdir, rows, tables)
    counts = {k2: sum(1 for x in runs if x["state"] == k2) for k2 in ("submitted", "done", "failed", "missing")}
    if save and s.path:
        studies.save(s)
    finished = counts["submitted"] == 0 and not any(x["state"] == "pending" for x in runs)
    return {"study": s.name, "round": r.round, "counts": counts, "runs": runs, "duplicates": dup,
            "timed_out": timed_out, "finished": finished}


def _collect(s: studies.Study, r: studies.Round, rdir: str, rows: Dict[str, List[Any]], tables: Dict[str, studies.TableSpec]) -> None:
    """The round's results, one CSV per table: the run's inputs (as proposed), its outputs, run_id."""
    for tid, items in rows.items():
        csv_files = [res for _, res in items if isinstance(res, str) and s.launcher.results.format == "csv_row"
                     and not s.launcher.results.converter]
        fast = read_small_csvs(csv_files) if csv_files else pd.DataFrame()
        by_id = {str(x): i for i, x in enumerate(fast["run_id"])} if "run_id" in fast.columns else {}
        out = []
        for p, res in items:
            if isinstance(res, dict):
                outputs = res
            elif p.run_id in by_id:
                outputs = fast.iloc[by_id[p.run_id]].to_dict()
            else:
                outputs = _parse_result(s, res, rdir)
            # the inputs are the run's own (as proposed); a result that echoes them under other names (Kp for
            # P_gain) must not add a second copy of the column
            echo = set(p.values) | set(tables[tid].rename.values()) | set(tables[tid].rename)
            out.append({**{k: v for k, v in outputs.items() if k not in echo}, **p.values, "run_id": p.run_id})
        df = pd.DataFrame(out)
        path = os.path.join(rdir, f"collected_{tid}.csv")
        tmp = path + ".tmp"
        df.to_csv(tmp, index=False, lineterminator="\n")
        os.replace(tmp, path)


def wait(s: studies.Study, k: Optional[int] = None, timeout: Optional[float] = None, poll: float = 0.5,
         on_poll: Optional[Callable[[Dict[str, Any]], None]] = None) -> Tuple[int, Dict[str, Any]]:
    """Until every run of the round is done or failed: 0 all done, 4 some failed, 5 timed out."""
    t0 = time.time()
    limit = timeout if timeout is not None else s.launcher.status.timeout_s
    while True:
        st = status(s, k)
        if on_poll:
            on_poll(st)
        if st["timed_out"]:
            return 5, st
        if st["finished"] and not running(s, k):
            st = status(s, k)
            return (4 if st["counts"]["failed"] or st["counts"]["missing"] else 0), st
        if limit and time.time() - t0 > limit:
            return 5, st
        time.sleep(poll)
