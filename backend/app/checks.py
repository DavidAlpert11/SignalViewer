"""
Checks from the command line (T57): pass / fail of recordings against limits, for test benches
and CI - the app's limits (T13, svcore/limits.py) without the window.

    signalviewer-cli check runs/*.csv --checks checks.json [--junit results.xml]
    signalviewer-cli check flight.bin --template "My limits"      # the limits saved in a template

A checks file:
    {"checks": [
      {"signal": "EngineTemp", "hi": 90},
      {"name": "Speed while cruising", "signal": "Speed", "lo": 20, "hi": 80,
       "during": {"state": "DriveMode", "value": "CRUISE"}},           # every CRUISE stretch
      {"signal": "ATT.Roll", "lo": -30, "hi": 30, "t0": 5, "t1": 120,
       "scale": 1, "offset": 0}
    ]}
`during.occurrence`: 1 = the first stretch, 2 = the second..., -1 = the last; left out = all.
Signal names as in the API (the unit may be left out). The values checked are scale * y + offset,
as plotted in the app.
"""
import contextlib
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import quoteattr

import numpy as np

from svcore.limits import check_limits
from svcore.naming import SignalNameError, resolve_signal_name


class ChecksError(ValueError):
    """The checks themselves are wrong (file, template) - nothing was checked."""


def load_checks(path: str) -> List[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except OSError as e:
        raise ChecksError(f"Cannot read the checks file {path}: {e.strerror or e}.") from None
    except ValueError as e:
        raise ChecksError(f"The checks file {path} is not valid JSON: {e}.") from None
    items = d.get("checks") if isinstance(d, dict) else d
    if not isinstance(items, list) or not items:
        raise ChecksError(f'{path}: expected {{"checks": [ ... ]}} with at least one check.')
    for i, c in enumerate(items, 1):
        if not isinstance(c, dict) or not c.get("signal"):
            raise ChecksError(f"{path}: check {i} has no \"signal\".")
        if c.get("lo") is None and c.get("hi") is None:
            raise ChecksError(f"{path}: check {i} ({c['signal']}) has neither \"lo\" nor \"hi\".")
        dur = c.get("during")
        if dur is not None and (not isinstance(dur, dict) or not dur.get("state") or "value" not in dur):
            raise ChecksError(f"{path}: check {i}: \"during\" needs \"state\" and \"value\".")
    return items


def template_checks(template_ref: str, path: str) -> List[dict]:
    """The limits saved in a template, as checks for one file (the template matched to the file
    the way the app does). Each plotted signal with limits is a check, with its scale / offset."""
    from app import batch
    from app.store import Store
    from svcore import templates as tplm
    all_ = batch.all_templates()
    t = batch.find_template(template_ref, all_)
    e = tplm.expand(t, all_)
    st = Store()
    with contextlib.redirect_stdout(sys.stderr):
        st.open_file(os.path.abspath(path))
    runs = st.list()
    resolved = tplm.resolve(t, all_, tplm.auto_bind(e, runs), runs)
    out, seen = [], set()
    for tab in resolved["tabs"]:
        for p in tab["plots"]:
            for s in p["signals"]:
                lim = s.get("limits") or {}
                if lim.get("lo") is None and lim.get("hi") is None:
                    continue
                name = s["sig"].split("/", 1)[-1]
                key = (name, lim.get("lo"), lim.get("hi"), s.get("scale"), s.get("offset"))
                if key in seen:                       # the same signal and limits in two plots
                    continue
                seen.add(key)
                out.append({"signal": name, "lo": lim.get("lo"), "hi": lim.get("hi"),
                            "scale": s.get("scale") if s.get("scale") is not None else 1, "offset": s.get("offset") or 0})
    if not out:
        raise ChecksError(f'The template "{t.get("name")}" has no limits on the signals of {os.path.basename(path)} '
                          "(set them in the app: a signal's properties > Limits, then save the template).")
    return out


def _windows(store, run_id: str, names: List[str], c: dict, where: str) -> Tuple[List[Tuple[Optional[float], Optional[float]]], str]:
    """The time windows a check covers, and how to say them."""
    t0, t1 = c.get("t0"), c.get("t1")
    dur = c.get("during")
    if not dur:
        say = "" if t0 is None and t1 is None else f"{'start' if t0 is None else t0} – {'end' if t1 is None else t1} s"
        return [(t0, t1)], say
    from app.routes.data import _stretches
    state = resolve_signal_name(names, str(dur["state"]), where)
    sid = f"{run_id}/{state}"
    st, sy = store.signal(sid)
    value = dur["value"]
    if isinstance(value, str):
        labels = store.labels(sid) or {}
        hit = [k for k, v in labels.items() if str(v).casefold() == value.casefold()]
        if not hit:
            known = ", ".join(sorted({str(v) for v in labels.values()})[:12]) or "none - give the number"
            raise SignalNameError(f"{state} has no value {value!r} in {where} (its values: {known}).")
        value = hit[0]
    parts = [(a, b) for a, b, v in _stretches(sid, np.asarray(st, dtype=np.float64), sy, where=store) if v == float(value)]
    if t0 is not None or t1 is not None:                # both given: the stretches inside the window
        lo, hi = (-np.inf if t0 is None else t0), (np.inf if t1 is None else t1)
        parts = [(max(a, lo), min(b, hi)) for a, b in parts if b > lo and a < hi]
    occ = dur.get("occurrence")
    say = f"while {state} = {dur['value']}"
    if occ not in (None, "all"):
        k = int(occ) - 1 if int(occ) > 0 else len(parts) + int(occ)
        parts = [parts[k]] if 0 <= k < len(parts) else []
        say += f" (stretch {occ})"
    return parts, say


def run_checks(path: str, checks: List[dict]) -> Dict[str, Any]:
    """Every check on one file: {file, results: [{name, status: pass|fail|error|skipped, ...}]}."""
    from app.store import Store
    store = Store()
    where = os.path.basename(path)
    out: Dict[str, Any] = {"file": path, "results": []}
    try:
        with contextlib.redirect_stdout(sys.stderr):  # the readers print progress
            lr = store.open_file(os.path.abspath(path))
    except Exception as e:                           # unreadable: every check is an error
        msg = str(e) or e.__class__.__name__
        out["error"] = msg
        out["results"] = [{"name": c.get("name") or c["signal"], "status": "error", "message": msg} for c in checks]
        return out
    names = list(lr.run.signals.keys())
    for c in checks:
        res: Dict[str, Any] = {"name": c.get("name") or c["signal"], "lo": c.get("lo"), "hi": c.get("hi")}
        try:
            full = resolve_signal_name(names, str(c["signal"]), where)
            res["signal"] = full
            wins, say = _windows(store, lr.id, names, c, where)
            res["window"] = say
            if not c.get("name") and say:
                res["name"] = f"{c['signal']} {say}"
            if not wins:
                res.update(status="skipped", message=f"no stretch {say} in {where}")
                out["results"].append(res)
                continue
            t, y = store.signal(f"{lr.id}/{full}")
            t = np.asarray(t, dtype=np.float64)
            y = np.asarray(y, dtype=np.float64) * float(c.get("scale", 1) or 1) + float(c.get("offset", 0) or 0)
            parts = [check_limits(t, y, c.get("lo"), c.get("hi"),
                                  *((None, None) if a is None and b is None else
                                    (-np.inf if a is None else a, np.inf if b is None else b)))
                     for a, b in wins]
            failed = [p for p in parts if not p["pass"]]
            res["samples"] = sum(p["samples"] for p in parts)
            if not res["samples"]:
                res.update(status="skipped", message=f"{full} has no samples {say or 'in the file'}")
            elif failed:
                worst = max(failed, key=lambda p: abs(p["worst"]))
                res.update(status="fail", violations=sum(p["violations"] for p in failed),
                           timeOutside=sum(p["timeOutside"] for p in failed),
                           first=min(p["first"] for p in failed), worst=worst["worst"], worstT=worst["worstT"])
                side = "above hi" if worst["worst"] > 0 else "below lo"
                res["message"] = (f"{full}: {res['violations']} time(s) outside, first at {res['first']:.3f} s; "
                                  f"worst {abs(worst['worst']):.4g} {side} at {worst['worstT']:.3f} s")
            else:
                res["status"] = "pass"
        except (KeyError, ValueError) as e:          # a signal / state / value not in this file
            res.update(status="error", message=str(e))
        out["results"].append(res)
    return out


def junit_xml(files: List[Dict[str, Any]]) -> str:
    """JUnit XML: one testsuite per file, one testcase per check (CI shows it as test results)."""
    rows = ['<?xml version="1.0" encoding="UTF-8"?>']
    total = {k: 0 for k in ("tests", "failures", "errors", "skipped")}
    suites = []
    for f in files:
        rs = f["results"]
        n = {"tests": len(rs), "failures": sum(r["status"] == "fail" for r in rs),
             "errors": sum(r["status"] == "error" for r in rs), "skipped": sum(r["status"] == "skipped" for r in rs)}
        for k in total:
            total[k] += n[k]
        name = os.path.basename(f["file"])
        cases = []
        for r in rs:
            open_ = f'    <testcase classname={quoteattr(name)} name={quoteattr(r["name"])}'
            msg = quoteattr(r.get("message", ""))
            if r["status"] == "pass":
                cases.append(open_ + "/>")
            elif r["status"] == "fail":
                cases.append(open_ + f'>\n      <failure message={msg} type="limit"/>\n    </testcase>')
            elif r["status"] == "error":
                cases.append(open_ + f'>\n      <error message={msg}/>\n    </testcase>')
            else:
                cases.append(open_ + f'>\n      <skipped message={msg}/>\n    </testcase>')
        suites.append(f'  <testsuite name={quoteattr(name)} tests="{n["tests"]}" failures="{n["failures"]}" '
                      f'errors="{n["errors"]}" skipped="{n["skipped"]}">\n' + "\n".join(cases) + "\n  </testsuite>")
    rows.append(f'<testsuites name="signalviewer check" tests="{total["tests"]}" failures="{total["failures"]}" '
                f'errors="{total["errors"]}" skipped="{total["skipped"]}">')
    rows += suites + ["</testsuites>", ""]
    return "\n".join(rows)
