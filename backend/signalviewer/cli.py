"""Command line: read and export recordings without opening the app (scripts, CI, MATLAB).

    python cli.py info  flight.bin [--json]
    python cli.py export flight.bin --signals "ATT.Roll,ATT.Pitch" --out roll.csv [--t0 10 --t1 60]
    python cli.py export run.csv --out run.mat            # .mat: one variable per signal + Time
    python cli.py report --template "ArduPilot · Full review" --out reports/ logs/*.bin [--format pdf]
    python cli.py templates                                # the templates --template can name
    python cli.py check runs/*.csv --checks checks.json [--junit results.xml]   # pass / fail (CI)
    python cli.py compare golden.csv new.csv --tol-abs 0.5     # against a golden run (CI)
    python cli.py validate [--json] [--junit v.xml]        # the numerical validation, on this machine

MATLAB:  status = system('python cli.py export flight.bin --out f.mat'); d = load('f.mat');
Exit code 0 = done, 1 = the file or a signal could not be read (the message says why).
check / compare:  0 = every check passed, 1 = a check failed, 2 = a check could not be made (a file or a
signal missing, a wrong checks file) - so a CI step fails on a broken limit and on broken data.
"""
import argparse
import json
import re
import sys

import numpy as np

from . import load     # sends the readers' progress to stderr: stdout stays for results (--json, MATLAB jsondecode)


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


def cmd_check(a) -> int:
    """T57: limits as pass / fail, one line per check, an exit code for CI and optional JUnit XML."""
    import glob
    from app.checks import ChecksError, load_checks, run_checks, template_checks
    files = [f for pat in a.files for f in (sorted(glob.glob(pat)) or [pat])]
    if bool(a.checks) == bool(a.template):
        print("error: give --checks FILE.json or --template NAME (one of them).", file=sys.stderr)
        return 2
    try:
        fixed = load_checks(a.checks) if a.checks else None
        results = []
        for f in files:
            if fixed is None:
                try:
                    checks = template_checks(a.template, f)
                except ChecksError:
                    raise
                except Exception as e:              # the file itself: report it as an error, go on
                    msg = str(e) or e.__class__.__name__
                    results.append({"file": f, "error": msg, "results": [{"name": "(open the file)", "status": "error", "message": msg}]})
                    continue
            else:
                checks = fixed
            results.append(run_checks(f, checks))
    except ChecksError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    count = _print_results(results, a)
    return 2 if count["error"] else 1 if count["fail"] else 0


def _print_results(results, a, mark_extra=None) -> dict:
    rs = [r for f in results for r in f["results"]]
    count = {k: sum(r["status"] == k for r in rs) for k in ("pass", "fail", "error", "skipped", "info")}
    count["info"] -= sum(r["name"] == "(time alignment)" and r["status"] == "info" for r in rs)   # not a signal
    if a.junit:
        from app.checks import junit_xml
        with open(a.junit, "w", encoding="utf-8") as fh:
            fh.write(junit_xml(results))
    if a.json:
        print(json.dumps({"files": results, "count": count}, ensure_ascii=False))
        return count
    mark = {"pass": "PASS", "fail": "FAIL", "error": "ERROR", "skipped": "SKIP", "info": "     "}
    top = getattr(a, "top", None)
    for f in results:
        print(f["file"] + (f"  vs  {f['golden']}" if f.get("golden") else ""))
        always = [r for r in f["results"] if r["name"] == "(time alignment)"]        # C13: the shift is always said
        rest = [r for r in f["results"] if r["name"] != "(time alignment)"]
        shown = rest if not top else [r for r in rest if r["status"] in ("fail", "error")] or rest[:top]
        for r in always + (shown[:top] if top else shown):
            print(f"  {mark[r['status']]:5} {r['name']}" + (f"  - {r['message']}" if r.get("message") else ""))
        if top and len(rest) > len(shown[:top]):
            print(f"  ... {len(rest) - len(shown[:top])} more (--top 0 shows all)")
    print(f"{count['pass']} passed, {count['fail']} failed, {count['error']} errors, {count['skipped']} skipped"
          + (f", {count['info']} without a tolerance" if count["info"] else "")
          + (f"; JUnit XML: {a.junit}" if a.junit else ""))
    return count


def cmd_compare(a) -> int:
    """T58: each file against a golden run - the signals that differ most first."""
    import glob
    from app.checks import ChecksError, load_tolerances, run_compare
    files = [f for pat in a.files for f in (sorted(glob.glob(pat)) or [pat])]
    try:
        tol = load_tolerances(a.tolerances, a.tol_abs, a.tol_pct)
    except ChecksError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    names = [s.strip() for s in a.signals.split(",") if s.strip()] if a.signals else None
    results = [run_compare(a.golden, f, tol, names, a.align, a.align_on) for f in files]
    count = _print_results(results, a)
    return 2 if count["error"] else 1 if count["fail"] else 0


def cmd_readers(a) -> int:
    """T60: the user's own file readers (the readers folder), or write the example reader."""
    from app import userreaders
    if a.example:
        print(userreaders.write_example())
        return 0
    if a.example_icd is not None:
        print(userreaders.write_example_icd()["layout"])
        if a.example_icd:                            # and a recording to open with it
            from svcore.icd import write_example_recording
            write_example_recording(a.example_icd)
            print(a.example_icd)
        return 0
    info = userreaders.listing()
    if a.json:
        print(json.dumps(info, ensure_ascii=False))
        return 0
    print(f"Readers folder: {info['folder']}")
    for r in info["readers"]:
        print(f"  {r['name']}  ({', '.join(r['extensions'])})  [{r['file']}]" + ("  binary layout" if r.get("kind") == "icd" else ""))
    for e in info["errors"]:
        print(f"  not loaded: {e['error']}")
    if not info["readers"] and not info["errors"]:
        print("  none yet - `readers --example` writes one to start from")
    return 1 if info["errors"] else 0


def _fmt(v: float) -> str:
    return "-" if not np.isfinite(v) else f"{v:.10g}"


def cmd_validate(a) -> int:
    """A4: the numerical validation cases (svcore/validation.py) on this installation: each one's
    expected value, what this build computes, and the tolerance. Exit code 0 = all within tolerance."""
    from svcore.validation import run_all
    rows = run_all()
    failed = [r for r in rows if not r["ok"]]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, default=float))
    else:
        for r in rows:
            unit = f" {r['unit']}" if r["unit"] else ""
            print(f"  {'PASS' if r['ok'] else 'FAIL'}  {r['id']}  {r['title']}")
            print(f"        expected {_fmt(r['expected'])}{unit}, measured {_fmt(r['measured'])}{unit}, "
                  f"error {_fmt(r['error'])} (tolerance {_fmt(r['tol'])})  - {r['reference']}")
        print(f"{len(rows) - len(failed)} passed, {len(failed)} failed")
    if a.junit:
        from app.checks import junit_xml
        res = [{"name": f"{r['id']} {r['title']}",
                "status": "pass" if r["ok"] else "fail",
                "message": f"expected {_fmt(r['expected'])}, measured {_fmt(r['measured'])}, tolerance {_fmt(r['tol'])}"}
               for r in rows]
        with open(a.junit, "w", encoding="utf-8") as fh:
            fh.write(junit_xml([{"file": "validation", "results": res}]))
    return 1 if failed else 0


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
    p = sub.add_parser("check", help="pass / fail against limits (exit code and JUnit XML for CI)",
                       description="Exit code: 0 all passed, 1 a check failed, 2 a check could not be made.")
    p.add_argument("files", nargs="+", help="data files (wildcards allowed)")
    p.add_argument("--checks", help="a .json checks file (see app/checks.py for the format)")
    p.add_argument("--template", help="use the limits saved in this template instead (name, id or .json)")
    p.add_argument("--junit", help="also write the results as JUnit XML (CI test results)")
    p.add_argument("--json", action="store_true", help="machine-readable results on stdout")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("compare", help="each file against a golden run (tolerances, exit code, JUnit XML)",
                       description="Without a tolerance the differences are listed and the exit code is 0. "
                                   "Exit code: 0 all within, 1 a signal outside its tolerance, 2 a comparison could not be made.")
    p.add_argument("golden", help="the reference run"); p.add_argument("files", nargs="+", help="runs to compare (wildcards allowed)")
    p.add_argument("--signals", help="comma-separated names (default: every signal both have)")
    p.add_argument("--tol-abs", type=float, help="allowed |difference| for every signal, in its unit")
    p.add_argument("--tol-pct", type=float, help="allowed difference in %% of the golden value")
    p.add_argument("--tolerances", help='a .json file: {"default": {"abs": .., "pct": ..}, "signals": {"Speed": {"abs": 1}, "Gear": {"skip": true}}}')
    p.add_argument("--align", help="line the runs up in time: auto (cross-correlation, like the app's Align) or seconds "
                                   "added to each run's time (a simulation from 0 s against a log from boot)")
    p.add_argument("--align-on", help="with --align auto: the golden signal to align on (default: the best-correlated)")
    p.add_argument("--top", type=int, default=10, help="lines per file when everything passes (0 = all); failures are always shown")
    p.add_argument("--junit", help="also write the results as JUnit XML"); p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_compare)
    p = sub.add_parser("readers", help="your own file readers (a format as a Python file in the readers folder)")
    p.add_argument("--example", action="store_true", help="write an example reader (.kv files) into the folder")
    p.add_argument("--example-icd", nargs="?", const="", metavar="RECORDING.tlm",
                   help="write an example binary layout (.icd.json, .tlm files) into the folder; with a path, also a recording for it")
    p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_readers)
    p = sub.add_parser("validate", help="the numerical validation: spectra, filters, statistics, compare, frames")
    p.add_argument("--json", action="store_true")
    p.add_argument("--junit", help="also write the results as JUnit XML")
    p.set_defaults(fn=cmd_validate)
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


if __name__ == "__main__":          # python -m signalviewer.cli ... (did nothing, silently, before A6)
    sys.exit(main())
