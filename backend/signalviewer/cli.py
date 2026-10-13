"""Command line: read and export recordings without opening the app (scripts, CI, MATLAB).

    python cli.py info  flight.bin [--json]
    python cli.py export flight.bin --signals "ATT.Roll,ATT.Pitch" --out roll.csv [--t0 10 --t1 60]
    python cli.py export run.csv --out run.mat            # .mat: one variable per signal + Time

MATLAB:  status = system('python cli.py export flight.bin --out f.mat'); d = load('f.mat');
Exit code 0 = done, 1 = the file or a signal could not be read (the message says why).
"""
import argparse
import contextlib
import json
import re
import sys

import numpy as np

from . import load as _load


def load(path):
    """The readers print progress to stdout; keep stdout for results (--json, MATLAB jsondecode)."""
    with contextlib.redirect_stdout(sys.stderr):
        return _load(path)


def _mat_name(name: str, taken: set) -> str:
    """A valid, unique MATLAB variable name for a signal ("ATT.Roll [deg]" -> "ATT_Roll_deg")."""
    v = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_") or "signal"
    if not v[0].isalpha():
        v = "s_" + v
    v = v[:60]
    base, k = v, 2
    while v in taken:
        v = f"{base[:56]}_{k}"; k += 1
    taken.add(v)
    return v


def cmd_info(a) -> int:
    rec = load(a.file)
    rows = []
    for n in rec.signals:
        t, y = rec.signal(n)
        rows.append({"name": n, "samples": int(len(t)),
                     "start": float(t[0]) if len(t) else None, "end": float(t[-1]) if len(t) else None})
    if a.json:
        print(json.dumps({"file": rec.path, "name": rec.name, "signals": rows}, ensure_ascii=False))
    else:
        print(f"{rec.name}: {len(rows)} signals")
        for r in rows:
            span = f"{r['start']:.3f} .. {r['end']:.3f} s" if r["samples"] else "empty"
            print(f"  {r['name']}  ({r['samples']} samples, {span})")
    return 0


def cmd_export(a) -> int:
    rec = load(a.file)
    names = [s.strip() for s in a.signals.split(",") if s.strip()] if a.signals else None
    t, cols = rec.table(names, a.t0, a.t1, a.alignment)
    out = a.out
    if out.lower().endswith(".mat"):
        from scipy.io import savemat
        taken = {"Time"}
        data = {"Time": t, **{_mat_name(n, taken): v for n, v in cols.items()}}
        savemat(out, data, do_compression=True)
    elif out.lower().endswith(".csv"):
        header = ["Time"] + [n.replace(",", " ") for n in cols]
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            f.write(",".join(header) + "\n")
            np.savetxt(f, np.column_stack([t, *cols.values()]), delimiter=",", fmt="%.10g")
    else:
        raise ValueError("--out must end with .csv or .mat")
    print(f"{out}: {len(t)} rows, {len(cols)} signals")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="signalviewer", description="Read and export recordings (Signal Viewer).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("info", help="list the signals of a file")
    p.add_argument("file"); p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(fn=cmd_info)
    p = sub.add_parser("export", help="write signals to .csv or .mat on one time base")
    p.add_argument("file"); p.add_argument("--out", required=True, help="target .csv or .mat")
    p.add_argument("--signals", help="comma-separated names (default: all); the first sets the time base")
    p.add_argument("--t0", type=float); p.add_argument("--t1", type=float)
    p.add_argument("--alignment", default="linear", choices=["linear", "nearest"], help="how other signals meet the time base (as in the app)")
    p.set_defaults(fn=cmd_export)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (KeyError, ValueError, OSError) as e:
        print(f"error: {e.args[0] if e.args else e}", file=sys.stderr)
        return 1
    except Exception as e:                       # the readers' LoadError: say what happened
        if e.__class__.__name__ == "LoadError":
            print(f"error: {e}", file=sys.stderr)
            return 1
        raise
