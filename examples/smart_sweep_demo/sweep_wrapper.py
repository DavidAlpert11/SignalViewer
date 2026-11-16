"""A sweep wrapper: runs ONE simulation once per set of inputs and writes the sweep's rows.

Copy this file next to your own simulation and change one thing: the --sim command (or `run_one` below).
Your simulation keeps a simple contract - the same as sim.py here:

    input   one JSON file with every input of one run: {"run_id": "...", "Kp": 1.2, "wind": "gusty", ...,
            "out": "<the CSV file to write>"}
    output  that CSV file: a header and ONE row - the run's inputs and its outputs (and run_id).

Three ways to give the inputs (each run = one row = one JSON file):

    python sweep_wrapper.py --spec grid.txt  --out sweep.csv      # every combination of the values below
    python sweep_wrapper.py --inputs runs.csv --out sweep.csv     # a table: one row per run, a column per input
    python sweep_wrapper.py --list params_files.txt               # JSON files already written (what Signal Viewer
                                                                  # passes: {{params_files}}, one round of a study)

grid.txt - one input per line, MATLAB-style values:

    Kp:   0.5, 1, 2:0.5:4         # 0.5, 1, 2, 2.5, 3, 3.5, 4   (start:step:end; start:end = step 1)
    wind: 0, 5, 10
    mode: calm, gusty             # text values too

Options:
    --sim "COMMAND {params}"   how to run one simulation; {params} is replaced by the JSON file's path.
                               Default: sim.py beside this file, called in this process (fast, no Python needed
                               when Signal Viewer runs it: `SignalViewer.exe study wrap sweep_wrapper.py ...`).
                               e.g. --sim "python my_sim.py {params}"   --sim "matlab -batch run_one('{params}')"
    --set NAME=VALUE           a value given to every run (repeatable), e.g. --set table=A
    --out FILE                 the sweep's table: every row, appended (runs already in it are skipped - run the same
                               command again to finish an interrupted sweep)
    --workers N                runs at the same time (default 2)
    --dry-run                  print the runs, run nothing

Open the --out table in Signal Viewer (Sweeps) to see which inputs hold. Python 3.8+, standard library only.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import importlib.util
import itertools
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ the inputs

def parse_values(text: str) -> List[Any]:
    """'1, 2, 5, 8:0.1:9' -> [1, 2, 5, 8, 8.1, ..., 9]; 'calm, gusty' -> ['calm', 'gusty']."""
    out: List[Any] = []
    for part in (p.strip() for p in re.split(r"[,;]", text)):
        if not part:
            continue
        nums = part.split(":")
        if len(nums) in (2, 3) and all(_is_num(x) for x in nums):
            a, s, b = (float(nums[0]), 1.0, float(nums[1])) if len(nums) == 2 else (float(nums[0]), float(nums[1]), float(nums[2]))
            if s == 0 or (b - a) / s < 0:
                raise ValueError(f"'{part}': the step goes away from the end (start:step:end)")
            n = int((b - a) / s + 1e-9) + 1
            whole = all(re.fullmatch(r"[+-]?\d+", x.strip()) for x in nums)      # 1:3 -> 1, 2, 3 (not 1.0)
            out += [int(round(a + k * s)) if whole else round(a + k * s, 12) for k in range(n)]
        else:
            out.append(_num(part))
    return out


def _is_num(x: str) -> bool:
    try:
        float(x)
        return True
    except ValueError:
        return False


def _num(x: str) -> Any:
    if not _is_num(x):
        return x
    f = float(x)
    return int(f) if f.is_integer() and "e" not in x.lower() and "." not in x else f


def read_spec(path: str) -> List[Dict[str, Any]]:
    """Every combination of the spec's values, in the order written (the last line changes fastest)."""
    names, lists = [], []
    with open(path, encoding="utf-8-sig") as f:
        for i, line in enumerate(f, 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            name, sep, vals = line.partition(":")
            if not sep or not name.strip():
                raise ValueError(f"{path} line {i}: write 'name: values' (e.g. 'Kp: 1, 2, 5:0.5:8')")
            names.append(name.strip())
            lists.append(parse_values(vals))
            if not lists[-1]:
                raise ValueError(f"{path} line {i}: {name.strip()} has no values")
    return [dict(zip(names, combo)) for combo in itertools.product(*lists)]


def read_table(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k: _num(v) for k, v in row.items() if k} for row in csv.DictReader(f)]


# ------------------------------------------------------------------ one run

def sim_runner(command: Optional[str]) -> Callable[[str], None]:
    """How one simulation runs: the --sim command, else sim.py beside this file in this process."""
    if command:
        def run(params_path: str) -> None:
            args = [a.replace("{params}", params_path) for a in shlex.split(command, posix=os.name != "nt")]
            cp = subprocess.run(args, capture_output=True, text=True)
            if cp.returncode != 0:
                raise RuntimeError((cp.stderr or cp.stdout).strip()[-300:] or f"exit code {cp.returncode}")
        return run
    path = os.path.join(HERE, "sim.py")
    spec = importlib.util.spec_from_file_location("sweep_sim", path)
    if spec is None or spec.loader is None or not os.path.isfile(path):
        raise SystemExit(f"No --sim command and no sim.py beside {__file__}: say how to run one simulation.")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return lambda params_path: mod.run(params_path)


def run_one(sim: Callable[[str], None], params_path: str) -> Dict[str, Any]:
    """One run: the simulation reads its JSON file and writes its row where "out" says; the row comes back."""
    with open(params_path, encoding="utf-8") as f:
        out = json.load(f)["out"]
    sim(params_path)
    rows = read_table(out)
    if not rows:
        raise RuntimeError(f"the simulation wrote no row to {out}")
    return rows[-1]


# ------------------------------------------------------------------ the sweep

def done_ids(out: Optional[str]) -> set:
    if not out or not os.path.isfile(out):
        return set()
    return {str(r.get("run_id")) for r in read_table(out)}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--spec", help="a file of 'name: values' lines - every combination is run")
    src.add_argument("--inputs", help="a CSV table, one run per row")
    src.add_argument("--list", help="a file listing JSON parameter files, one per line")
    ap.add_argument("--sim", help='how to run one simulation, e.g. "python my_sim.py {params}"')
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE", help="a value given to every run")
    ap.add_argument("--out", help="the sweep's table (CSV): every row, appended")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    fixed = {}
    for kv in a.set:
        k, sep, v = kv.partition("=")
        if not sep:
            ap.error(f"--set {kv}: write NAME=VALUE")
        fixed[k.strip()] = _num(v.strip())

    if a.list:                                   # JSON files written by the app: run them as they are
        with open(a.list, encoding="utf-8") as f:
            files = [ln.strip() for ln in f if ln.strip()]
    else:
        rows = read_spec(a.spec) if a.spec else read_table(a.inputs)
        work = tempfile.mkdtemp(prefix="sweep_")
        skip = done_ids(a.out)
        files = []
        for i, row in enumerate(rows, 1):
            rid = str(row.get("run_id") or f"run_{i:04d}")
            if rid in skip:
                continue
            p = {**fixed, **row, "run_id": rid, "out": os.path.join(work, rid + ".csv")}
            path = os.path.join(work, rid + ".json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(p, f)
            files.append(path)
        if skip:
            print(f"{len(skip)} runs already in {a.out} - skipped")
    if a.dry_run:
        for path in files:
            with open(path, encoding="utf-8") as f:
                print(f.read().strip())
        return 0

    sim = sim_runner(a.sim)
    failed = 0
    rows_out: List[Dict[str, Any]] = []
    with cf.ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        futs = {ex.submit(run_one, sim, path): path for path in files}
        for k, fut in enumerate(cf.as_completed(futs), 1):
            try:
                rows_out.append(fut.result())
                if a.out:
                    _append(a.out, rows_out[-1])
            except Exception as e:                # noqa: BLE001 - one failed run does not stop the sweep
                failed += 1
                print(f"failed: {os.path.basename(futs[fut])}: {e}", file=sys.stderr)
            print(f"{k}/{len(files)} runs", flush=True)
    print(f"done: {len(rows_out)} rows" + (f" in {a.out}" if a.out else "") + (f", {failed} failed" if failed else ""))
    return 1 if failed else 0


def _append(path: str, row: Dict[str, Any]) -> None:
    """One row added to the sweep's table; a new column (an output seen first now) rewrites the header."""
    old = read_table(path) if os.path.isfile(path) else []
    cols = list(dict.fromkeys([*(old[0].keys() if old else []), *row.keys()]))
    if old and list(old[0].keys()) == cols:
        with open(path, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=cols, lineterminator="\n").writerow(row)
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows([*old, row])


if __name__ == "__main__":
    sys.exit(main())
