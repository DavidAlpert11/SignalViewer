"""CC12: the automatic research for ANY file - the "Any data" profile. The flight-log health check (svcore/health.py)
is one profile among others, chosen for ArduPilot / MAVLink / PX4 logs; this one runs on every file, with no rules
written, and says what is worth a look. Conservative on purpose (a list full of findings is ignored):

  nonFinite     a numeric signal with NaN / Inf samples among its numbers (a division by zero, a lost sensor)
  oscillation   one frequency holds most of a signal's movement for many cycles (a limit cycle, a loop tuned too
                hot) - not noise (spread over all frequencies) and not a slow manoeuvre (a few cycles)
  tracking      a commanded / measured pair (svcore/reportparts.setpoint_pairs - Cmd / Pos, ATT.DesRoll / ATT.Roll):
                how far the measured value stays from its command (RMS, worst, the lasting offset)
  stepResponse  the command's steps: overshoot and settling (svcore/requirements), the worst of the first few
                (stepNoSettle: one of them never settles within 5 % of the step, or the measured value's own noise)
  rule          a user profile's rule (a JSON file in the profiles folder - the checks file's entries, applied to
                every file whose signals match)

Each finding as health.py's: {code, level: ok | warning | error, vals, t, spans: [[t0, t1]...], signals}."""
import glob
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from svcore import requirements as req
from svcore.reportparts import setpoint_pairs, span

MAX_OSC = 5
MAX_PAIRS = 8
STEPS_PER_PAIR = 3


def _r(v: float, nd: int = 3) -> float:
    return float(f"{v:.{nd}g}")


def _result(code, level, vals=None, t=None, spans=None, signals=None) -> Dict[str, Any]:
    return {"code": code, "level": level, "vals": vals or {}, "t": t, "spans": spans or [], "signals": signals or []}


def _numeric(run) -> List[Tuple[str, np.ndarray, np.ndarray]]:
    out = []
    for name, s in run.signals.items():
        if getattr(s, "labels", None):                         # a state with texts: not a number to judge
            continue
        t = s.time if s.time is not None else run.time
        if t is None:
            continue
        y = np.asarray(s.data)
        if y.dtype.kind not in "fiu" or len(y) != len(t) or len(y) < 20:
            continue
        out.append((name, np.asarray(t, dtype=np.float64) + float(getattr(s, "time_offset", 0.0) or 0.0)
                    + float(getattr(run, "time_offset", 0.0) or 0.0), y.astype(np.float64)))
    return out


def _runs(mask: np.ndarray) -> List[Tuple[int, int]]:
    d = np.diff(np.r_[False, mask, False].astype(np.int8))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def nonfinite(name: str, t: np.ndarray, y: np.ndarray) -> Optional[Dict[str, Any]]:
    """NaN / Inf among the numbers. A column empty at the start or the end (a sensor not yet / no longer there, an
    object of a table that appears later) is how the file is made, not a fault: only the holes inside count."""
    bad = ~np.isfinite(y)
    good = np.flatnonzero(~bad)
    if not len(good):
        return None
    bad[:good[0]] = False
    bad[good[-1] + 1:] = False
    n = int(bad.sum())
    if not n or n > 0.3 * len(y):                              # none inside, or mostly empty (a sparse column)
        return None
    spans = [[float(t[a]), float(t[min(b, len(t)) - 1])] for a, b in _runs(bad)][:20]
    first = float(t[np.flatnonzero(bad)[0]])
    return _result("nonFinite", "warning", {"n": n, "pct": _r(100 * n / len(y), 2), "sig": name}, first, spans, [name])


def oscillation(name: str, t: np.ndarray, y: np.ndarray) -> Optional[Dict[str, Any]]:
    ok = np.isfinite(y) & np.isfinite(t)
    t, y = t[ok], y[ok]
    if len(t) < 64:
        return None
    dur = float(t[-1] - t[0])
    if dur <= 0 or np.mean(np.diff(y) != 0) < 0.5:             # held values (a setpoint, a counter): not a sensor
        return None
    n = int(min(1 << 16, max(256, len(t))))
    g = np.linspace(t[0], t[-1], n)
    v = np.interp(g, t, y)
    v = v - np.polyval(np.polyfit(g - g[0], v, 1), g - g[0])  # a trend is not an oscillation
    p = np.abs(np.fft.rfft(v * np.hanning(n))) ** 2
    f = np.fft.rfftfreq(n, d=dur / (n - 1))
    p[0] = 0
    total = float(p.sum())
    if total <= 0:
        return None
    fmin = 8.0 / dur                                           # at least 8 cycles in the run
    p[f < fmin] = 0
    k = int(np.argmax(p))
    if k == 0 or f[k] <= 0:
        return None
    share = float(p[max(0, k - 2):k + 3].sum() / total)       # the peak's band (the window spreads it over ~5 bins)
    amp = float(np.std(v)) * 2 * np.sqrt(2) * np.sqrt(share)  # peak-to-peak of the sine that carries that share
    if share < 0.6 or amp < 0.05 * span(y):
        return None
    return _result("oscillation", "warning", {"sig": name, "hz": _r(float(f[k])), "pp": _r(amp), "pct": round(100 * share)},
                   float(t[0]), [[float(t[0]), float(t[-1])]], [name])


def _steps(tc: np.ndarray, yc: np.ndarray, hold: float = 0.5) -> List[int]:
    """The command's steps: a jump of 20 % of its span in one sample, then held (within 2 % of the span) for `hold` s
    at least - a set point changed, not a pilot's stick or a noisy command."""
    sp = span(yc)
    d = np.abs(np.diff(yc))
    out = []
    for i in np.flatnonzero(d > 0.2 * sp):
        k = int(i) + 1
        j = np.searchsorted(tc, tc[k] + hold)
        if j >= len(tc) or j - k < 5:
            continue
        if np.max(np.abs(yc[k:j] - yc[k])) <= 0.02 * sp:
            out.append(k)
    return out


def _wrap(name: str, e: np.ndarray, sp: float) -> np.ndarray:
    """An angle in degrees that wraps (yaw, heading 0..360): 359 and 1 are 2 apart, not 358."""
    if sp > 300 and re.search(r"deg|yaw|head|hdg|course|azim", name, re.I):
        return (e + 180.0) % 360.0 - 180.0
    return e


def pair(cmd: Tuple[str, np.ndarray, np.ndarray], meas: Tuple[str, np.ndarray, np.ndarray]) -> List[Dict[str, Any]]:
    (nc, tc, yc), (nm, tm, ym) = cmd, meas
    okc, okm = np.isfinite(yc) & np.isfinite(tc), np.isfinite(ym) & np.isfinite(tm)
    tc, yc, tm, ym = tc[okc], yc[okc], tm[okm], ym[okm]
    inside = (tm >= tc[0]) & (tm <= tc[-1])
    if inside.sum() < 20 or len(tc) < 2:
        return []
    tm, ym = tm[inside], ym[inside]
    # the command as held (a command is in force until the next one - not a line drawn between two)
    i = np.clip(np.searchsorted(tc, tm, "right") - 1, 0, len(yc) - 1)
    ref = yc[i]
    sp = span(np.r_[yc, ym])
    e = _wrap(nm, ym - ref, sp)
    rms, worst = float(np.sqrt(np.mean(e ** 2))), int(np.argmax(np.abs(e)))
    tail = tm >= tm[-1] - 0.1 * (tm[-1] - tm[0])
    bias = float(np.mean(e[tail]))
    level = "warning" if rms > 0.2 * sp or abs(bias) > 0.05 * sp else "ok"
    out = [_result("tracking", level, {"meas": nm, "cmd": nc, "rms": _r(rms), "max": _r(abs(e[worst])), "bias": _r(bias),
                                         "pct": round(100 * rms / sp)}, float(tm[worst]), [], [nm, nc])]
    # the first steps: overshoot and settling (5 % of the step) until the next step
    st = _steps(tc, yc)
    res = []
    sp = span(yc)
    for k in st[:STEPS_PER_PAIR]:
        a = tc[k]
        # until the command moves again (the next step, a ramp): what follows answers another command
        moved = np.flatnonzero(np.abs(yc[k:] - yc[k]) > 0.02 * sp)
        b = tc[k + moved[0]] if len(moved) else tc[-1]
        w = (tm >= a) & (tm < b)
        if w.sum() < 10:
            continue
        target = float(yc[k])
        y0 = float(yc[k - 1])                                   # the step is the command's: from its last value
        if abs(target - y0) < 0.2 * sp:
            continue
        tw, yw = tm[w], ym[w]
        if abs(float(yw[0]) - y0) > 0.1 * abs(target - y0):   # still on its way from the step before: not a step
            continue                                             # response that can be read
        # the measured value's own noise sets the smallest band that can be settled in (a noisy sensor is not a loop
        # that never settles): 5 % of the step, or three times the noise in the window's last quarter
        q = yw[tw >= tw[0] + 0.75 * (tw[-1] - tw[0])]
        noise = float(np.std(np.diff(q))) / np.sqrt(2) if len(q) > 3 else 0.0
        try:
            os_ = req.overshoot(np.r_[tw[0], tw], np.r_[y0, yw], target, 1e9)
            se = req.settle(tw, yw, target, max(abs(target - y0) * 0.05, 3 * noise), 1e9)
        except req.RequirementError:
            continue
        res.append((float(a), os_["value"] or 0.0, se["value"], os_["at"]))
    if res:
        a, osv, sev, at = max(res, key=lambda r: (r[1], r[2] if r[2] is not None else np.inf))
        never = any(r[2] is None for r in res)
        level = "warning" if osv > 25 or never else "ok"
        vals = {"meas": nm, "n": len(res), "os": _r(osv)}
        if not never:
            vals["settle"] = _r(max(r[2] for r in res))
        # a step it never settles after (within 5 % or its own noise) is said as such - its own sentence
        out.append(_result("stepNoSettle" if never else "stepResponse", level, vals, at if at is not None else a, [[a, a]], [nm, nc]))
    return out


def profiles_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".signalviewer", "profiles")


def user_profiles(folder: Optional[str] = None) -> List[Dict[str, Any]]:
    """The user's profiles: every *.json in the folder - {"name", "match": ["regex", ...], "checks": [...]} - those
    that cannot be read are listed with their error (said, not dropped)."""
    out = []
    for p in sorted(glob.glob(os.path.join(folder or profiles_dir(), "*.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            if not isinstance(d, dict) or not isinstance(d.get("checks"), list):
                raise ValueError('expected {"name": ..., "checks": [...]}')
            for i, c in enumerate(d["checks"], 1):
                bad = req.validate(c)
                if bad:
                    raise ValueError(f"check {i}: {bad}")
            out.append({"name": d.get("name") or os.path.splitext(os.path.basename(p))[0], "path": p,
                        "match": [str(m) for m in d.get("match") or []], "checks": d["checks"]})
        except (OSError, ValueError) as e:
            out.append({"name": os.path.basename(p), "path": p, "error": str(e), "checks": []})
    return out


def matches(profile: Dict[str, Any], names: List[str]) -> bool:
    """A profile applies when each of its `match` patterns finds a signal (none given: every file)."""
    pats = profile.get("match") or []
    return all(any(re.search(p, n, re.I) for n in names) for p in pats)


def scan(run, pairs: bool = True) -> List[Dict[str, Any]]:
    """The "Any data" profile on one run. pairs=False: no commanded / measured analysis - a flight log's own profile
    judges its loops by the vehicle's rules (a pilot's stick is not a step to settle after)."""
    sigs = _numeric(run)
    found: List[Dict[str, Any]] = []
    for name, t, y in sigs:
        r = nonfinite(name, t, y)
        if r:
            found.append(r)
    osc = [r for r in (oscillation(n, t, y) for n, t, y in sigs) if r]
    osc.sort(key=lambda r: -r["vals"]["pct"])
    found += osc[:MAX_OSC]
    by = {n: (n, t, y) for n, t, y in sigs}
    for p in [] if not pairs else setpoint_pairs([f"r/{n}" for n in by])[:MAX_PAIRS]:
        c, m = p["setpoint"][2:], p["measured"][2:]
        found += pair(by[c], by[m])
    return found
