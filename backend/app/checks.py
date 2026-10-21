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

Against a golden run (T58):
    signalviewer-cli compare golden.csv new/*.csv --tol-pct 2 [--tolerances tol.json] [--junit r.xml]
"""
import contextlib
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape, quoteattr

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
            elif r["status"] == "info":
                cases.append(open_ + f'>\n      <system-out>{escape(r.get("message", ""))}</system-out>\n    </testcase>')
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


# --- T58: a run against a golden run -------------------------------------------------------

def load_tolerances(path: Optional[str], tol_abs: Optional[float], tol_pct: Optional[float],
                    allow_outside: Optional[float] = None) -> Dict[str, Any]:
    """{"default": {"abs": 0.5, "pct": 2}, "signals": {"Speed": {"abs": 1}, "Gear": {"skip": true}}}
    - the command line's --tol-abs / --tol-pct / --allow-outside are the default when given.
    T65: "outside_pct" (default 0) is the share of samples, in %, that may be outside the tolerance
    and still pass - a spike or a few samples at a step must not fail a run that otherwise matches."""
    d: Dict[str, Any] = {"default": {}, "signals": {}}
    if path:
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except OSError as e:
            raise ChecksError(f"Cannot read the tolerances file {path}: {e.strerror or e}.") from None
        except ValueError as e:
            raise ChecksError(f"The tolerances file {path} is not valid JSON: {e}.") from None
        if not isinstance(d, dict):
            raise ChecksError(f'{path}: expected {{"default": {{...}}, "signals": {{...}}}}.')
        d.setdefault("default", {}); d.setdefault("signals", {})
    dflt = dict(d.get("default") or {})
    if tol_abs is not None:
        dflt["abs"] = tol_abs
    if tol_pct is not None:
        dflt["pct"] = tol_pct
    if allow_outside is not None:
        dflt["outside_pct"] = allow_outside
    d["default"] = dflt
    return d


def _outside_allowed(tol: Dict[str, Any]) -> Optional[float]:
    """T65: the tolerance's "outside_pct" as a number from 0 to 100; ValueError says what is wrong."""
    v = tol.get("outside_pct")
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        x = float("nan")
    if not 0.0 <= x <= 100.0:
        raise ValueError(f"outside_pct is the share of samples allowed outside, from 0 to 100 (%), not {v!r}")
    return x


def _share(pct: float) -> str:
    """A share in % for a message: never "0.0" for samples that are outside (0.04 % of 50 000 is 20)."""
    if pct <= 0.0:
        return "0"
    if pct < 0.1:
        return f"{pct:.2g}"
    if 99.9 < pct < 100.0:                    # nor "100.0" while some samples are inside
        return "over 99.9"
    return f"{pct:.1f}"


def _align_auto(store, g, n, pairs: List[Tuple[str, str]]) -> Optional[Dict[str, Any]]:
    """C13: the time shift that lines `n` up with the golden run `g` - cross-correlation of the
    given (golden, run) pairs (the app's *Align* by signal), the best-correlated pair wins."""
    from svcore.sync import _xcorr_delta
    best = None
    for ga, nb in pairs:
        ta, ya = (np.asarray(x, dtype=np.float64) for x in store.signal(f"{g.id}/{ga}"))
        tb, yb = (np.asarray(x, dtype=np.float64) for x in store.signal(f"{n.id}/{nb}"))
        if not (np.nanstd(ya) > 0 and np.nanstd(yb) > 0):
            continue
        r = _xcorr_delta(ta, ya, tb, yb)
        if r and (best is None or r[1] > best["corr"]):
            best = {"seconds": float(r[0]), "corr": float(r[1]), "pair": [ga, nb]}
    return best


def run_compare(golden: str, path: str, tolerances: Dict[str, Any], signals: Optional[List[str]] = None,
                align: Optional[str] = None, align_on: Optional[str] = None) -> Dict[str, Any]:
    """Every signal of `path` that the golden run also has, compared with svcore/compare (the
    Compare panel's numbers: RMS / max |difference|, correlation; angles wrap). With a tolerance
    a signal passes when every sample is within it (or all but "outside_pct" % of them, T65);
    without one the row is information only.

    C13 - a simulation against a flight, two loggers, two formats:
      * names match with or without their unit ("ATT.Roll" in a .mat is "ATT.Roll [deg]" in a .bin);
        a tolerance entry {"as": "name in the run"} pairs differently named signals;
      * align: None (the times as recorded), a number of seconds added to the run's time, or "auto"
        (cross-correlation, like the app's *Align*; align_on names the golden signal to use, else
        the best-correlated of the compared signals). The shift used is the first result row."""
    from app.store import Store
    from svcore.compare import compare as compare_runs
    store = Store()
    out: Dict[str, Any] = {"file": path, "golden": golden, "results": []}
    try:
        with contextlib.redirect_stdout(sys.stderr):
            g = store.open_file(os.path.abspath(golden))
            n = store.open_file(os.path.abspath(path))
    except Exception as e:
        msg = str(e) or e.__class__.__name__
        out.update(error=msg, results=[{"name": "(open the files)", "status": "error", "message": msg}])
        return out
    gnames, nnames = list(g.run.signals.keys()), list(n.run.signals.keys())
    where = os.path.basename(golden)
    per: Dict[str, dict] = {}
    for key, v in (tolerances.get("signals") or {}).items():
        try:
            per[resolve_signal_name(gnames, key, where)] = v or {}
        except KeyError as e:                         # a tolerance for a signal the golden run lacks
            out["results"].append({"name": key, "status": "error", "message": f"tolerances: {e}"})
    def in_run(name: str) -> Optional[str]:
        """The run's signal for the golden signal `name`: {"as": ...} in the tolerances, the same name,
        or the same name without its unit - one match only, never a guess."""
        want = (per.get(name) or {}).get("as") or name
        try:
            return resolve_signal_name(nnames, str(want), os.path.basename(path))
        except KeyError:
            return None
    if signals:
        wanted = []
        for s in signals:
            try:
                wanted.append(resolve_signal_name(gnames, s, where))
            except KeyError as e:
                out["results"].append({"name": s, "status": "error", "message": str(e)})
    else:
        wanted = [x for x in gnames if in_run(x)]
    shift = 0.0
    if align not in (None, "", "none"):
        if str(align).lower() == "auto":
            if align_on:
                try:
                    on = resolve_signal_name(gnames, align_on, where)
                except KeyError as e:
                    out["results"].append({"name": "(time alignment)", "status": "error", "message": str(e)})
                    return out
                cand = [on]
            else:
                cand = [x for x in wanted if not (per.get(x) or {}).get("skip")]
            pairs = [(x, m) for x in cand for m in [in_run(x)] if m is not None]
            got = _align_auto(store, g, n, pairs[:12]) if pairs else None
            if got is None or got["corr"] < 0.5:
                out["results"].append({"name": "(time alignment)", "status": "error",
                                       "message": "could not align the runs in time"
                                       + (f" (best correlation {got['corr']:.2f} on {got['pair'][0]})" if got else "")
                                       + " - give --align SECONDS, or --align-on a signal that moves in both"})
                return out
            shift = got["seconds"]
            out["shift"] = {"method": "auto", **got}
            msg = f"{os.path.basename(path)} moved by {shift:+.3f} s (correlation {got['corr']:.3f} on {got['pair'][0]})"
        else:
            try:
                shift = float(align)
            except ValueError:
                out["results"].append({"name": "(time alignment)", "status": "error",
                                       "message": f"--align takes auto or a number of seconds, not {align!r}"})
                return out
            out["shift"] = {"method": "given", "seconds": shift}
            msg = f"{os.path.basename(path)} moved by {shift:+.3f} s (given)"
        out["results"].append({"name": "(time alignment)", "status": "info", "message": msg})
    rows = []
    for name in wanted:
        tol = {**tolerances.get("default", {}), **per.get(name, {})}
        if tol.get("skip"):
            continue
        res: Dict[str, Any] = {"name": name}
        try:
            allowed = _outside_allowed(tol)
        except ValueError as e:
            res.update(status="error", message=f"tolerances: {e}")
            rows.append(res)
            continue
        other = in_run(name)
        if other is None:
            res.update(status="error", message=f"{name} is in the golden run but not in {os.path.basename(path)}")
            rows.append(res)
            continue
        if other != name:
            res["as"] = other
        ta, ya = store.signal(f"{g.id}/{name}")
        tb, yb = store.signal(f"{n.id}/{other}")
        tb = np.asarray(tb, dtype=np.float64) + shift
        try:
            r = compare_runs([("g/" + name, np.asarray(ta, dtype=np.float64), np.asarray(ya, dtype=np.float64)),
                              ("n/" + name, np.asarray(tb, dtype=np.float64), np.asarray(yb, dtype=np.float64))],
                             "g/" + name, "linear", tol.get("abs"), tol.get("pct"))
        except (ValueError, IndexError) as e:
            res.update(status="error", message=str(e) or "no samples to compare")
            rows.append(res)
            continue
        m = r["rows"][0] if r["rows"] else {}
        if not m.get("valid"):
            res.update(status="skipped", message="fewer than two samples where both have data")
            rows.append(res)
            continue
        res.update({k: m.get(k) for k in ("rmsDiff", "rmsPct", "maxAbsDiff", "meanDiff", "correlation", "withinPct")})
        res["overlap"] = r["overlap"]
        say = f"RMS {m['rmsDiff']:.4g} ({m['rmsPct']:.2f} % of range), max |Δ| {m['maxAbsDiff']:.4g}, r {m['correlation']:.3f}"
        if "pass" in m:
            outside = 100.0 - float(m["withinPct"])
            ok = bool(m["pass"]) or (allowed is not None and outside <= allowed + 1e-9)
            res["status"] = "pass" if ok else "fail"
            res["outsidePct"] = outside
            if not m["pass"]:
                lim = " / ".join(x for x in (f"±{tol['abs']}" if tol.get("abs") is not None else "",
                                             f"±{tol['pct']} %" if tol.get("pct") is not None else "") if x)
                also = f", {allowed:g} % allowed" if allowed is not None else ""
                say = f"{_share(outside)} % of samples outside {lim}{also}; " + say
        else:
            res["status"] = "info"
        res["message"] = say
        rows.append(res)
    def rank(x: dict) -> float:                        # errors first, then the most different
        v = x.get("rmsPct")
        return -float(v) if v is not None else (-1e18 if x["status"] == "error" else 1.0)
    rows.sort(key=rank)
    out["results"] += rows
    return out
