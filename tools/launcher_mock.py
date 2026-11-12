"""A stand-in for the owner's farm launcher (W17), to try Launcher mode without a farm.

It does what a real launcher does with a study's round: reads each parameters file (XML or JSON), runs the
simulation for it and writes the result where the study's `results.glob` looks.

    python tools/launcher_mock.py --list params_files_A.txt --results results/{table} [--exe sim.exe]
                                  [--fail-rate 0.1] [--seed 1]

* --list      a list file of parameter files (one path per line; the study's {{params_files}})
* --results   the result folder; {table} is replaced by the run's table; one CSV row per run, named
              <run_id>.csv (inputs + outputs + run_id)
* --exe       run this program with the parameters file instead of the built-in toy drone model
              (backend/svcore/drone_model.py)
* --fail-rate this share of the runs fails on purpose: no result, a <run_id>.failed marker instead

The study's launcher block for it:
    "submit": ["python", "tools/launcher_mock.py", "--list", "{{params_files}}", "--results", "{{study_dir}}/results/{table}"],
    "submit_mode": "round", "results": {"glob": "results/{{table}}/{{run_id}}.csv"}, "status": {"failed_glob": "results/{{table}}/{{run_id}}.failed"}
"""
import argparse
import csv
import json
import os
import random
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))


def _number(v, key=""):
    if key in ("run_id", "table") or not isinstance(v, str):    # a run id of digits and an "e" is not a number
        return v
    try:
        f = float(v)
        return int(f) if f.is_integer() and "." not in str(v) else f
    except (TypeError, ValueError):
        return v


def read_params(path):
    """A parameters file as a flat dict: JSON keys, or XML leaf elements / name-value attributes."""
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            return {k: _number(v, k) for k, v in json.load(f).items()}
    out = {}
    for el in ET.parse(path).getroot().iter():
        if el.get("name") is not None and (el.get("value") is not None or (el.text or "").strip()):
            out[el.get("name")] = _number(el.get("value") if el.get("value") is not None else el.text.strip(), el.get("name"))
        elif len(el) == 0 and (el.text or "").strip():
            out[el.tag] = _number(el.text.strip(), el.tag)
    return out


GAINS = {"Kp": ("Kp", "P_gain"), "Ki": ("Ki", "I_gain"), "Kd": ("Kd", "D_gain")}


def toy(p):
    from svcore.drone_model import simulate
    g = {k: float(next(p[n] for n in names if n in p)) for k, names in GAINS.items()}
    out = simulate(p["table"], g["Kp"], g["Ki"], g["Kd"], wind=float(p.get("wind", 0)),
                   mass=None if "mass" not in p else float(p["mass"]),
                   filter_hz=None if "filter_hz" not in p else float(p["filter_hz"]))
    return {k: round(float(v), 6) for k, v in out.items()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--exe")
    ap.add_argument("--fail-rate", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    with open(a.list, encoding="utf-8") as f:
        files = [x.strip() for x in f if x.strip()]
    failed = 0
    for path in files:
        p = read_params(path)
        rid = str(p["run_id"])
        folder = a.results.replace("{table}", str(p.get("table", "")))
        os.makedirs(folder, exist_ok=True)
        if random.Random(f"{a.seed}|{rid}").random() < a.fail_rate:
            open(os.path.join(folder, rid + ".failed"), "w").close()
            failed += 1
            continue
        if a.exe:
            subprocess.run([a.exe, path], check=False)
            continue
        row = {k: v for k, v in p.items() if k not in ("table", "round")}
        row.update(toy(p))
        with open(os.path.join(folder, rid + ".csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row), lineterminator="\n")
            w.writeheader()
            w.writerow(row)
    print(f"launcher_mock: {len(files) - failed} runs done, {failed} failed on purpose")
    return 0


if __name__ == "__main__":
    sys.exit(main())
