"""Command line: read and export recordings without opening the app (scripts, CI, MATLAB).

    python cli.py info  flight.bin [--json]
    python cli.py export flight.bin --signals "ATT.Roll,ATT.Pitch" --out roll.csv [--t0 10 --t1 60]
    python cli.py export run.csv --out run.mat            # .mat: one variable per signal + Time
    python cli.py report --template "ArduPilot · Full review" --out reports/ logs/*.bin [--format pdf]
    python cli.py templates                                # the templates --template can name
    python cli.py check runs/*.csv --checks checks.json [--junit results.xml]   # pass / fail (CI)
    python cli.py compare golden.csv new.csv --tol-abs 0.5     # against a golden run (CI)
    python cli.py validate [--json] [--junit v.xml]        # the numerical validation, on this machine
    python cli.py objects flight.bin [--all] [--json]      # the map objects found, and why (L12)
    python cli.py compare-objects flight.bin --ref POS --objects "XKF1[0],XKF1[1]" --what position,attitude \
        --frame ned --csv errors.csv --stats stats.csv --map map.png --map-html map.html --report report.html \
        [--tolerance position=2m,attitude=1deg --junit r.xml] [--json]
    python cli.py compare-similar flight.bin [--leaf att.roll] [--ref truth] [--csv d.csv] [--json]
    python cli.py map flight.bin [--objects all] --out map.png|map.html

MATLAB:  status = system('python cli.py export flight.bin --out f.mat'); d = load('f.mat');
Exit code 0 = done, 1 = the file or a signal could not be read (the message says why).
compare-objects with --tolerance:  0 = every error within its tolerance, 1 = one is not, 2 = it could not be
compared (no such object, no reference velocity...); without --tolerance 0 = done.
check / compare:  0 = every check passed, 1 = a check failed, 2 = a check could not be made (a file or a
signal missing, a wrong checks file) - so a CI step fails on a broken limit and on broken data.
"""
import argparse
import json
import os
import re
import shutil
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
        tol = load_tolerances(a.tolerances, a.tol_abs, a.tol_pct, a.allow_outside, a.tol_time)
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


def cmd_cache(a) -> int:
    """What the app keeps on disk for speed, and clearing it (also: Settings > Disk space used).
    Run it with the app closed: an entry an open file reads from is skipped by the app, not here."""
    from svcore import csv_loader
    from app.common import UPLOAD_DIR
    from app.tiles import CACHE as TILES

    def size(path):
        return sum(os.path.getsize(os.path.join(d, f)) for d, _s, fs in os.walk(path) for f in fs
                   if os.path.isfile(os.path.join(d, f)))

    kinds = {"cache": csv_loader.CACHE_DIR, "uploads": UPLOAD_DIR, "tiles": TILES}
    what = list(kinds) if a.clear == ["all"] else (a.clear or [])
    for w in what:
        if w not in kinds:
            print(f"Unknown: {w} (cache, uploads, tiles or all)", file=sys.stderr)
            return 2
        before = size(kinds[w])
        shutil.rmtree(kinds[w], ignore_errors=True)
        print(f"cleared {w}: {before / 1048576:.1f} MB")
    for k, path in kinds.items():
        print(f"{k:8s} {size(path) / 1048576:10.1f} MB  {path}")
    return 0


def cmd_sweep(a) -> int:
    """A run envelope's results table against a question: how many parameter sets hold in every
    must-hold-across combination, the best of them. Exit 0 when at least --min-holding hold, 1 when
    fewer, 2 when the table or the question cannot be read."""
    import json as _json
    import numpy as _np
    from svcore import sweep
    try:
        df = sweep.read_any(a.table)
        cols = sweep.describe(df)
        q: dict = {}
        if a.question:
            with open(a.question, encoding="utf-8") as f:
                doc = _json.load(f)
            if "question" in doc:                             # a study saved by the app (.svsweep)
                q = dict(doc["question"])
                q["roles"] = {c["name"]: c["role"] for c in doc.get("columns", [])}
                q["outputAgg"] = {}
            else:
                q = doc
        roles = {c["name"]: c["role"] for c in cols}
        roles.update(q.get("roles") or {})
        q["roles"] = roles
        p = sweep.prepare(df, q)
        ans = sweep.answer(p, q)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    d, n = ans["data"], ans["counts"]
    order = [i for i in _np.argsort(d["#rank"]) if _np.isfinite(d["#rank"][i])] or list(_np.where(d["#holds"] == 1)[0])
    best = [{**{c: (None if v != v else v) for c, v in ((c, d[c][i].item() if hasattr(d[c][i], "item") else d[c][i]) for c in p.params)},
             **({"goal": float(d["#goal"][i])} if "#goal" in d else {})} for i in order[: a.top]]
    if a.json:
        print(_json.dumps({"counts": n, "conditions": ans["conditions"], "best": best}, indent=2, default=str))
    else:
        print(f"{n['holding']} of {n['sets']} parameter sets hold in all {n['combos']} combinations "
              f"({n['sets'] - n['complete']} miss a combination)")
        for c in ans["conditions"]:
            print(f"  {c['label']}: met by {c['met']}")
        for i, b in enumerate(best, 1):
            print(f"  {i}. " + ", ".join(f"{k}={v}" for k, v in b.items()))
    return 0 if n["holding"] >= a.min_holding else 1


# ---- L12: map objects -----------------------------------------------------------------------------

def _clean(v):
    return None if v is None or (isinstance(v, float) and v != v) else v


def cmd_objects(a) -> int:
    rec = load(a.file)
    objs = rec.objects(all=a.all)
    if a.json:
        print(json.dumps({"file": rec.path, "objects": objs}, ensure_ascii=False, default=str))
        return 0
    print(f"{rec.name}: {len(objs)} object(s)")
    for o in objs:
        org = f", origin {o['origin']['via']} ({o['origin']['rule']})" if o["origin"] else ""
        why = o["why"]["class"].get("known") or o["why"]["class"].get("word") or "-"
        print(f"  {o['name']}: {o['cls']} ({why}), {o['frame'].upper()}{org}, attitude {o['attitude']}"
              + ("" if o["addable"] else "  [not added by Add all]"))
    return 0


_TOL_UNITS = {"position": ("m",), "velocity": ("m/s", "mps"), "attitude": ("deg", "°")}
_TOL_COMPS = {"position": None, "velocity": None, "attitude": None}      # None: every error component of it


def _tolerances(text: str) -> dict:
    """position=2m,attitude=1deg,velocity=0.5m/s -> {quantity: limit} (the unit may be left out)."""
    out = {}
    for part in filter(None, (x.strip() for x in text.split(","))):
        if "=" not in part:
            raise ValueError(f"A tolerance is quantity=value (got {part!r})")
        q, v = (x.strip() for x in part.split("=", 1))
        if q not in _TOL_UNITS:
            raise ValueError(f"A tolerance's quantity is position, velocity or attitude (got {q!r})")
        for u in _TOL_UNITS[q]:
            if v.lower().endswith(u):
                v = v[: -len(u)]
                break
        out[q] = float(v)
    return out


def cmd_compare_objects(a) -> int:
    import signalviewer as sv
    recs = [load(f) for f in a.files]
    what = [w.strip() for w in a.what.split(",") if w.strip()]
    objs = [o.strip() for o in re.split(r",(?![^\[]*\])", a.objects) if o.strip()] if a.objects else None
    try:
        tol = _tolerances(a.tolerance) if a.tolerance else {}
        cmp = sv.compare_objects(recs if len(recs) > 1 else recs[0], reference=a.ref, objects=objs, what=what, frame=a.frame)
    except (KeyError, ValueError) as e:
        print(f"error: {e.args[0] if e.args else e}", file=sys.stderr)
        return 2
    if a.csv:
        cmp.to_csv(a.csv)
    if a.stats:
        cmp.to_csv(a.stats, "stats")
    if a.mat:
        cmp.to_mat(a.mat)
    rec0 = recs[0]
    if a.map:
        sv.map_image(rec0, path=a.map)
    if a.map_html:
        sv.map_html(rec0, path=a.map_html)
    if a.report:
        sv.report(rec0, a.report, compare=cmp)
    # pass / fail: every error component of a quantity within its tolerance (largest |error| over the run)
    results = []
    for q, lim in tol.items():
        if q in cmp.reasons:
            results.append({"name": f"{q} vs {a.ref}", "status": "error", "message": cmp.reasons[q]})
            continue
        for obj in dict.fromkeys(r["object"] for r in cmp.raw["stats"] if r["qty"] == q):      # in the order given
            rows = [r for r in cmp.raw["stats"] if r["qty"] == q and r["object"] == obj and r["max_abs"] is not None]
            worst = max(rows, key=lambda r: r["max_abs"]) if rows else None
            ok = worst is not None and worst["max_abs"] <= lim
            results.append({"name": f"{obj} {q} vs {a.ref}", "status": "pass" if ok else "fail",
                            "message": f"max |{worst['comp']}| = {worst['max_abs']:.6g} (tolerance {lim:g})" if worst else "no data"})
    if a.junit:
        from app.checks import junit_xml
        with open(a.junit, "w", encoding="utf-8") as fh:
            fh.write(junit_xml([{"file": ",".join(a.files), "results": results}]))
    stats = [{k: _clean(v) for k, v in r.items()} for r in cmp.raw["stats"]]
    if a.json:
        print(json.dumps({"reference": a.ref, "frame": a.frame, "stats": stats, "reasons": cmp.reasons, "left_out": cmp.left_out,
                          "checks": results}, ensure_ascii=False))
    else:
        print(f"against {a.ref} ({a.frame.upper()}):")
        for r in stats:
            print(f"  {r['object']:<16} {r['comp']:<20} rms {r['rms']:.6g}  max {r['max_abs']:.6g} at {r['t_max_abs']:.3f} s" if r["rms"] is not None
                  else f"  {r['object']:<16} {r['comp']:<20} no data")
        for q, why in cmp.reasons.items():
            print(f"  {q}: not compared - {why}")
        for q, outs in cmp.left_out.items():
            for x in outs:
                print(f"  {q}: {x['why']}")
        for r in results:
            print(f"  [{r['status'].upper()}] {r['name']}: {r['message']}")
    if any(r["status"] == "error" for r in results):
        return 2
    return 1 if any(r["status"] == "fail" for r in results) else 0


def cmd_compare_similar(a) -> int:
    import signalviewer as sv
    from svcore.similar import reference_of
    rec = load(a.file)
    fams = [f for f in sv.similar(rec, loose=a.loose) if not a.leaf or f["leaf"].endswith(a.leaf)]
    out = []
    frames = []
    for f in fams:
        ref = next((m for m in f["members"] if a.ref and m["seg"] == a.ref), None) or reference_of(f)
        if f["unitsDiffer"]:
            out.append({"leaf": f["leaf"], "how": f["how"], "reference": ref["name"], "stats": [], "note": "units differ - not subtracted"})
            continue
        df = sv.compare_signals(rec, [m["name"] for m in f["members"]], reference=ref["name"])
        frames.append(df)
        out.append({"leaf": f["leaf"], "how": f["how"], "reference": ref["name"], "stats": [{k: _clean(v) for k, v in s.items()} for s in df.attrs["stats"]]})
    if a.csv and frames:
        import pandas as pd
        pd.concat([d.set_index("Time") for d in frames], axis=1).reset_index().to_csv(a.csv, index=False, encoding="utf-8-sig")
    if a.json:
        print(json.dumps({"file": rec.path, "families": out}, ensure_ascii=False))
    else:
        print(f"{rec.name}: {len(out)} famil{'y' if len(out) == 1 else 'ies'} of similar signals")
        for f in out:
            print(f"  {f['leaf']} ({f['how']}) - reference {f['reference']}" + (f": {f['note']}" if f.get("note") else ""))
            for s in f["stats"]:
                print(f"    {s['signal']}: rms {s['rms']:.6g}, max {s['max_abs']:.6g}")
    return 0


def cmd_map(a) -> int:
    import signalviewer as sv
    rec = load(a.file)
    objs = None if a.objects in (None, "all") else [o.strip() for o in re.split(r",(?![^\[]*\])", a.objects) if o.strip()]
    html = a.out.lower().endswith(".html")
    if a.three_d:                               # 1.26: the map seen in 3D
        path = sv.scene_html(rec, objs, a.out, a.theme) if html else sv.scene_image(rec, objs, a.out, a.theme)
    else:
        path = sv.map_html(rec, objs, a.out, a.theme) if html else sv.map_image(rec, objs, a.out, a.theme)
    print(path)
    return 0


def _utf8_streams() -> None:
    """The output is UTF-8 everywhere: a Windows console or pipe defaults to the ANSI code page (cp1252), where
    printing a name like "Δnorth" or a Hebrew word fails ("charmap codec can't encode") and --json writes
    nothing. Python 3.7+ can switch the streams in place."""
    for st in (sys.stdout, sys.stderr):
        enc = (getattr(st, "encoding", None) or "").lower().replace("-", "")
        if enc != "utf8" and hasattr(st, "reconfigure"):
            try:
                st.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):        # a stream that cannot change (already written to): leave it
                pass


def main(argv=None) -> int:
    _utf8_streams()
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
    p.add_argument("--tol-time", type=float, help="seconds a run may be early or late (the golden value's band is its "
                   "lowest / highest within +-TOL_TIME, as the Simulink Data Inspector)")
    p.add_argument("--allow-outside", type=float, metavar="PCT",
                   help="share of samples (%%) that may be outside the tolerance and still pass (default 0: every sample)")
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
    p = sub.add_parser("cache", help="disk space the app uses for speed (CSV cache, log indexes, dropped-file copies, map tiles) and clearing it")
    p.add_argument("--clear", nargs="+", metavar="WHAT", help="cache, uploads, tiles - or all")
    p.set_defaults(fn=cmd_cache)
    p = sub.add_parser("sweep", help="a run envelope's results table: which parameter sets hold in every scenario (exit code for CI)")
    p.add_argument("table", help="the results table (CSV, Parquet, Excel) or a folder of them")
    p.add_argument("--question", help="a JSON question, or a study saved by the app (.svsweep)")
    p.add_argument("--top", type=int, default=5, help="how many of the best sets to list")
    p.add_argument("--min-holding", type=int, default=1, help="exit 1 when fewer sets hold")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_sweep)
    p = sub.add_parser("objects", help="the map objects found in a file, and why (L12)")
    p.add_argument("file"); p.add_argument("--all", action="store_true", help="also those Add all would not add")
    p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_objects)
    p = sub.add_parser("compare-objects", help="objects against a reference: values, errors, statistics (exit code with --tolerance)")
    p.add_argument("files", nargs="+", help="one file, or several (an object named file:name where two share a name)")
    p.add_argument("--ref", required=True, help="the reference object, e.g. POS")
    p.add_argument("--objects", help='the objects compared, e.g. "XKF1[0],XKF1[1]" (default: every other one)')
    p.add_argument("--what", default="position,velocity,attitude", help="any of position, velocity, attitude")
    p.add_argument("--frame", default="ned", choices=["ned", "enu", "ecef", "lla", "track"])
    p.add_argument("--csv", help="the errors, full resolution, one time base"); p.add_argument("--stats", help="the statistics as CSV")
    p.add_argument("--mat", help="errors, values and statistics as .mat")
    p.add_argument("--map", help="the objects' map as PNG"); p.add_argument("--map-html", help="the offline map page")
    p.add_argument("--report", help="a report (.html / .pdf / .docx) with the map and the errors")
    p.add_argument("--tolerance", help="pass / fail, e.g. position=2m,attitude=1deg,velocity=0.5m/s (largest |error|)")
    p.add_argument("--junit", help="the pass / fail as JUnit XML"); p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_compare_objects)
    p = sub.add_parser("compare-similar", help="families of similar signals (nav1 / nav2, XKF1[0] / XKF1[1]) and their differences")
    p.add_argument("file"); p.add_argument("--leaf", help="only families whose leaf ends so, e.g. att.roll")
    p.add_argument("--ref", help="the reference segment, e.g. truth (default: a truth-class one, else the first)")
    p.add_argument("--loose", action="store_true", help="also the looser matches"); p.add_argument("--csv", help="values and differences")
    p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_compare_similar)
    p = sub.add_parser("map", help="the map of a file's objects: a picture (.png / .svg) or the offline page (.html)")
    p.add_argument("file"); p.add_argument("--objects", default="all", help='"all" or names, e.g. "POS,GPS[0]"')
    p.add_argument("--out", required=True); p.add_argument("--theme", default="light", choices=["light", "dark"])
    p.add_argument("--3d", dest="three_d", action="store_true", help="the map seen in 3D (terrain, models with attitude)")
    p.set_defaults(fn=cmd_map)
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
