"""
Health check of a flight log: the questions one asks of every log, answered with the moments
they concern, so a click takes the user there.

Every check looks for its data under the names ArduPilot (.bin), MAVLink (.tlog) and PX4 (.ulg)
use, runs only when the data is there, and takes its limits from the log's own parameters when it
has them (BATT_LOW_VOLT, FS_EKF_THRESH, MOT_PWM_MAX...). Each finding:
    {code, level: ok | warning | error, vals: {...}, t, spans: [[t0, t1]...], signals: [names]}
The UI turns code + vals into a sentence (English / Hebrew).
"""
import re
from typing import Dict, List, Optional, Tuple

import numpy as np

_NAME = re.compile(r"^([^.\[]+)(\[\d+\])?\.([^ ]+)(?: \[.*\])?$")


def _index(run) -> Dict[Tuple[str, str], List[str]]:
    """(message, field) -> signal names (all instances; not other components / systems)."""
    out: Dict[Tuple[str, str], List[str]] = {}
    for n in run.signals:
        m = _NAME.match(n)
        if m:
            out.setdefault((m.group(1), m.group(3)), []).append(n)
    return out


def _spans(t: np.ndarray, mask: np.ndarray, min_dur: float = 0.0, gap: float = 1.0, cap: int = 20):
    """Stretches of time where mask holds (closer than `gap` s merged, shorter than min_dur dropped)."""
    if not mask.any():
        return []
    m = mask.astype(np.int8)
    d = np.diff(np.r_[0, m, 0])
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1
    out = []
    for a, b in zip(t[starts], t[ends]):
        if out and a - out[-1][1] <= gap:
            out[-1][1] = float(b)
        else:
            out.append([float(a), float(b)])
    out = [s for s in out if s[1] - s[0] >= min_dur]
    return out[:cap]


class _Ctx:
    def __init__(self, run, params: Dict[str, float]):
        self.run, self.params, self.idx = run, params, _index(run)

    def find(self, alts) -> List[Tuple[str, np.ndarray, np.ndarray, float]]:
        """First alternative (message, [fields], scale) present -> [(name, t, y, scale)]."""
        for alt in alts:
            msg, fields = alt[0], alt[1]
            scale = alt[2] if len(alt) > 2 else 1.0
            got = []
            for f in fields:
                for n in self.idx.get((msg, f), []):
                    t, y = self.run.get_signal_data(n)
                    got.append((n, np.asarray(t, dtype=np.float64), np.asarray(y, dtype=np.float64) * scale, scale))
            if got:
                return got
        return []

    def p(self, *names, default=None):
        for n in names:
            v = self.params.get(n)
            if v is not None and v > 0:
                return float(v)
        return default


def _result(code, level, vals=None, t=None, spans=None, signals=None):
    return {"code": code, "level": level, "vals": vals or {}, "t": t, "spans": spans or [], "signals": signals or []}


def _r(v, nd=2):
    return None if v is None or not np.isfinite(v) else round(float(v), nd)


# ----------------------------------------------------------------------------- the checks
def check_vibration(c: _Ctx):
    sigs = c.find([("VIBE", ["VibeX", "VibeY", "VibeZ"]), ("VIBRATION", ["vibration_x", "vibration_y", "vibration_z"])])
    if not sigs:
        return None
    worst, wt, wn, spans = -1.0, None, None, []
    for n, t, y, _ in sigs:
        if not len(y) or not np.isfinite(y).any():
            continue
        k = int(np.nanargmax(y))
        if y[k] > worst:
            worst, wt, wn = float(y[k]), float(t[k]), n
        spans += _spans(t, y > 30, min_dur=0.5)
    if worst < 0:
        return None
    level = "error" if worst > 60 else "warning" if spans else "ok"
    return _result("vibration", level, {"max": _r(worst, 1), "axis": wn.split(".")[1].split(" ")[0] if wn else ""}, wt,
                   sorted(spans)[:20], [n for n, *_ in sigs])


def check_clipping(c: _Ctx):
    sigs = c.find([("VIBE", ["Clip", "Clip0", "Clip1", "Clip2"]), ("VIBRATION", ["clipping_0", "clipping_1", "clipping_2"])])
    if not sigs:
        return None
    total, first, spans = 0, None, []
    for n, t, y, _ in sigs:
        ok = np.isfinite(y)
        if ok.sum() < 2:
            continue
        tt, yy = t[ok], y[ok]
        inc = np.diff(yy) > 0
        total += int(max(0.0, yy[-1] - yy[0]))
        if inc.any():
            tf = float(tt[1:][inc][0])
            first = tf if first is None else min(first, tf)
            spans += _spans(tt[1:], inc, gap=2.0)
    level = "error" if total > 100 else "warning" if total > 0 else "ok"
    return _result("clipping", level, {"count": total}, first, sorted(spans)[:20], [n for n, *_ in sigs])


def _after_fix(t, y, good):
    """Index from which the receiver first reached a good state (ignore the start-up search)."""
    k = np.flatnonzero(good)
    return int(k[0]) if len(k) else None


def check_gps(c: _Ctx):
    out = []
    sats = c.find([("GPS", ["NSats"]), ("GPS_RAW_INT", ["satellites_visible"]),
                   ("vehicle_gps_position", ["satellites_used"]), ("sensor_gps", ["satellites_used"])])
    for n, t, y, _ in sats[:1]:
        k = _after_fix(t, y, y >= 6)
        if k is None:
            out.append(_result("gpsSats", "error", {"min": _r(np.nanmax(y), 0)}, float(t[0]), [], [n]))
            continue
        tt, yy = t[k:], y[k:]
        bad = yy < 6
        j = int(np.nanargmin(yy))
        lvl = "error" if np.nanmin(yy) < 4 else "warning" if bad.any() else "ok"
        out.append(_result("gpsSats", lvl, {"min": _r(yy[j], 0)}, float(tt[j]), _spans(tt, bad, 0.5), [n]))
    hdop = c.find([("GPS", ["HDop"]), ("GPS_RAW_INT", ["eph"], 0.01), ("vehicle_gps_position", ["hdop"]), ("sensor_gps", ["hdop"])])
    for n, t, y, _ in hdop[:1]:
        ok = np.isfinite(y) & (y > 0) & (y < 99)
        k = _after_fix(t, y, ok & (y < 2))
        if k is None:
            continue
        tt, yy = t[k:], np.where(ok[k:], y[k:], np.nan)
        bad = yy > 2
        j = int(np.nanargmax(yy))
        out.append(_result("gpsHdop", "warning" if bad.any() else "ok", {"max": _r(yy[j], 2)}, float(tt[j]), _spans(tt, bad, 1.0), [n]))
    fix = c.find([("GPS", ["Status"]), ("GPS_RAW_INT", ["fix_type"]), ("vehicle_gps_position", ["fix_type"]), ("sensor_gps", ["fix_type"])])
    for n, t, y, _ in fix[:1]:
        k = _after_fix(t, y, y >= 3)
        if k is None:
            continue
        lost = y[k:] < 3
        sp = _spans(t[k:], lost, 0.2)
        out.append(_result("gpsFix", "error" if sp else "ok", {"n": len(sp)}, sp[0][0] if sp else None, sp, [n]))
    return out


def check_battery(c: _Ctx):
    sigs = c.find([("BAT", ["Volt"]), ("BATT", ["Volt"]), ("SYS_STATUS", ["voltage_battery"]),
                   ("battery_status", ["voltage_filtered_v", "voltage_v"])])
    if not sigs:
        return None
    n, t, y, _ = sigs[0]
    ok = np.isfinite(y) & (y > 0.5)
    if not ok.any():
        return None
    tt, yy = t[ok], y[ok]
    j = int(np.argmin(yy))
    low = c.p("BATT_LOW_VOLT", "BATT2_LOW_VOLT")
    crit = c.p("BATT_CRT_VOLT", "BATT2_CRT_VOLT")
    vals = {"min": _r(yy[j], 2), "start": _r(float(np.median(yy[:max(1, min(len(yy), 20))])), 2)}
    if crit and yy[j] < crit:
        return _result("battCrit", "error", {**vals, "limit": _r(crit, 2)}, float(tt[j]), _spans(tt, yy < crit, 0.5), [n])
    if low and yy[j] < low:
        return _result("battLow", "warning", {**vals, "limit": _r(low, 2)}, float(tt[j]), _spans(tt, yy < low, 0.5), [n])
    return _result("battOk", "ok", vals, float(tt[j]), [], [n])


def check_ekf(c: _Ctx):
    sigs = c.find([("XKF4", ["SV", "SP", "SH", "SM"]), ("NKF4", ["SV", "SP", "SH", "SM"]),
                   ("EKF_STATUS_REPORT", ["velocity_variance", "pos_horiz_variance", "pos_vert_variance", "compass_variance"])])
    if not sigs:
        return None
    thresh = c.p("FS_EKF_THRESH", default=0.8)
    worst, wt, wn, spans = -1.0, None, "", []
    for n, t, y, _ in sigs:
        if not len(y) or not np.isfinite(y).any():
            continue
        k = int(np.nanargmax(y))
        if y[k] > worst:
            worst, wt, wn = float(y[k]), float(t[k]), n
        spans += _spans(t, y > 0.5, 0.2)
    if worst < 0:
        return None
    level = "error" if worst >= thresh else "warning" if worst > 0.5 else "ok"
    return _result("ekf", level, {"max": _r(worst, 2), "which": wn.split(".")[1].split(" ")[0], "limit": _r(thresh, 2)},
                   wt, sorted(spans)[:20], [n for n, *_ in sigs])


def check_motors(c: _Ctx, vehicle: Optional[str]):
    if vehicle not in (None, "copter"):
        return []
    sigs = c.find([("RCOU", ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"]),
                   ("SERVO_OUTPUT_RAW", [f"servo{i}_raw" for i in range(1, 9)])])
    motors = [s for s in sigs if len(s[2]) > 10 and 900 < np.nanmedian(s[2]) < 2100 and np.nanstd(s[2]) > 5]
    if len(motors) < 3:
        return []
    motors = motors[:8]
    pmax = c.p("MOT_PWM_MAX", default=None) or max(float(np.nanmax(s[2])) for s in motors)
    pmin = c.p("MOT_PWM_MIN", default=1000.0)
    out, spans, first = [], [], None
    for n, t, y, _ in motors:
        sp = _spans(t, y >= pmax - 0.02 * (pmax - pmin), 0.3)
        spans += sp
        if sp:
            first = sp[0][0] if first is None else min(first, sp[0][0])
    out.append(_result("motorsSat", "warning" if spans else "ok", {"n": len(spans)}, first, sorted(spans)[:20], [n for n, *_ in motors]))
    # imbalance while flying: every motor's average over the time all motors are clearly spinning
    t0 = motors[0][1]
    ys = [np.interp(t0, t, y) for _n, t, y, _ in motors]
    fly = np.all([y > pmin + 0.15 * (pmax - pmin) for y in ys], axis=0)
    if fly.sum() > 20:
        means = [float(np.mean(y[fly])) for y in ys]
        spread = max(means) - min(means)
        hi = int(np.argmax(means))
        level = "warning" if spread > 0.1 * (pmax - pmin) else "ok"
        out.append(_result("motorsBalance", level, {"spread": _r(spread, 0), "motor": hi + 1,
                                                     "means": [_r(m, 0) for m in means]}, None, [], [n for n, *_ in motors]))
    return out


def check_vcc(c: _Ctx):
    sigs = c.find([("POWR", ["Vcc"]), ("POWER_STATUS", ["Vcc"])])
    if not sigs:
        return None
    n, t, y, _ = sigs[0]
    ok = np.isfinite(y) & (y > 1)
    if not ok.any():
        return None
    tt, yy = t[ok], y[ok]
    bad = (yy < 4.75) | (yy > 5.4)
    j = int(np.argmin(yy))
    level = "error" if yy.min() < 4.5 else "warning" if bad.any() else "ok"
    return _result("vcc", level, {"min": _r(yy.min(), 2), "max": _r(yy.max(), 2)}, float(tt[j]), _spans(tt, bad, 0.2), [n])


def check_log_errors(events: List[dict], off: float = 0.0):
    events = [{**e, "t": e["t"] + off} for e in events]
    errs = [e for e in events if e["level"] == "error"]
    warns = [e for e in events if e["level"] == "warning"]
    if errs:
        return _result("logErrors", "error", {"n": len(errs), "first": errs[0]["text"][:80]}, errs[0]["t"],
                       [[e["t"], e["t"]] for e in errs[:20]])
    if warns:
        return _result("logWarnings", "warning", {"n": len(warns), "first": warns[0]["text"][:80]}, warns[0]["t"],
                       [[e["t"], e["t"]] for e in warns[:20]])
    return _result("logClean", "ok", {})


def health(run) -> Optional[dict]:
    fl = getattr(run, "_flightlog", None)
    params = dict(fl.params) if fl else {}
    vehicle = fl.vehicle if fl else None
    c = _Ctx(run, params)
    found = []
    for r in (check_vibration(c), check_clipping(c), *check_gps(c), check_battery(c), check_ekf(c),
              *check_motors(c, vehicle), check_vcc(c),
              check_log_errors(fl.events, float(run.time_offset or 0.0)) if fl else None):
        if r:
            found.append(r)
    if not found:
        return None
    rank = {"error": 0, "warning": 1, "ok": 2}
    found.sort(key=lambda r: rank[r["level"]])
    return {"findings": found, "errors": sum(r["level"] == "error" for r in found),
            "warnings": sum(r["level"] == "warning" for r in found)}
