"""Command line: read and export recordings without opening the app (scripts, CI, MATLAB).

    python cli.py info  flight.bin [--json]
    python cli.py export flight.bin --signals "ATT.Roll,ATT.Pitch" --out roll.csv [--t0 10 --t1 60]
    python cli.py export run.csv --out run.mat            # .mat: one variable per signal + Time
    python cli.py report --template "ArduPilot · Full review" --out reports/ logs/*.bin [--format pdf]
    python cli.py templates                                # the templates --template can name

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


def cmd_report(a) -> int:
    """One report per file from a template (the same matching and drawing as the app)."""
    import glob
    from app.batch import batch_reports
    files = [f for pat in a.files for f in (sorted(glob.glob(pat)) or [pat])]    # Windows shells do not expand *
    res = batch_reports(a.template, files, a.out, a.format, a.lang, a.theme, a.title,
                        log=lambda m: print(m, file=sys.stderr))
    made = [r for r in res if r.get("report")]
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"{len(made)} of {len(res)} reports in {a.out}")
    return 0 if made else 1


def cmd_templates(a) -> int:
    from app.batch import all_templates
    rows = [{"id": t.get("id"), "name": t.get("name"), "builtin": bool(t.get("builtin")),
             "auto": bool(t.get("generator"))} for t in all_templates()]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False))
    else:
        for r in rows:
            print(f"  {r['name']}  [{r['id']}]" + ("  (made from the files in the app: not for reports)" if r["auto"] else ""))
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
    p = sub.add_parser("report", help="one report per file from a template (batch)")
    p.add_argument("files", nargs="+", help="data files (wildcards allowed)")
    p.add_argument("--template", required=True, help="template name, id, or a .json file (see: templates)")
    p.add_argument("--out", required=True, help="folder for the reports")
    p.add_argument("--format", default="html", choices=["html", "pdf", "docx"])
    p.add_argument("--lang", default="en", choices=["en", "he"]); p.add_argument("--theme", default="light", choices=["light", "dark"])
    p.add_argument("--title", help="report title (default: file name · template name)")
    p.add_argument("--json", action="store_true", help="machine-readable summary on stdout")
    p.set_defaults(fn=cmd_report)
    p = sub.add_parser("templates", help="list the templates (built-in and yours)")
    p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_templates)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except BrokenPipeError:                      # output piped into `head` & co. and closed early
        return 0
    except (KeyError, ValueError, OSError) as e:
        print(f"error: {e.args[0] if e.args else e}", file=sys.stderr)
        return 1
    except Exception as e:                       # the readers' LoadError: say what happened
        if e.__class__.__name__ == "LoadError":
            print(f"error: {e}", file=sys.stderr)
            return 1
        raise
