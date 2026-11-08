"""
PX4 flight logs (.ulg / ULog), read with pyulog.

Signals:  "<topic>.<field>" ("vehicle_attitude.q[0]"), "<topic>[<instance>].<field>" when a topic is
          logged more than once (two GPS, several IMUs). Every topic keeps its own time
          (timestamp, seconds since boot). vehicle_status.nav_state / arming_state carry their names.
Log panel: logged messages with their level, navigation-mode changes, arm / disarm, parameters
          (initial value, every change, defaults when the log has them).
"""
import logging
import os
from typing import Any, Dict, Optional

import numpy as np

from svcore.flightlog import FlightLogInfo
from svcore.models import Run, Signal
from svcore.extras import missing

log = logging.getLogger("signalviewer").getChild(__name__)

# PX4 vehicle_status.nav_state (only the values that have kept their meaning across releases)
PX4_NAV = {0: "MANUAL", 1: "ALTCTL", 2: "POSCTL", 3: "AUTO_MISSION", 4: "AUTO_LOITER", 5: "AUTO_RTL",
           10: "ACRO", 12: "DESCEND", 13: "TERMINATION", 14: "OFFBOARD", 15: "STAB", 17: "AUTO_TAKEOFF",
           18: "AUTO_LAND", 19: "AUTO_FOLLOW_TARGET", 20: "AUTO_PRECLAND", 21: "ORBIT", 22: "AUTO_VTOL_TAKEOFF"}
PX4_ARMING = {1: "DISARMED", 2: "ARMED"}
GPS_FIX = {0: "NONE", 1: "NO_FIX", 2: "2D", 3: "3D", 4: "DGPS", 5: "RTK_FLOAT", 6: "RTK_FIXED"}
_LABELS = {("vehicle_status", "nav_state"): PX4_NAV, ("vehicle_status", "arming_state"): PX4_ARMING,
           ("vehicle_gps_position", "fix_type"): GPS_FIX, ("sensor_gps", "fix_type"): GPS_FIX}
_SKIP = {"timestamp", "timestamp_sample"}


class ULogError(Exception):
    pass


def is_ulog(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(7) == b"ULog\x01\x12\x35"
    except OSError:
        return False


def load_ulog(path: str, display_name: str):
    if not is_ulog(path):
        raise ULogError("This is not a PX4 flight log (.ulg).")
    try:
        from pyulog import ULog
    except ImportError:
        raise ULogError(missing("Reading PX4 logs (.ulg)", "px4")) from None
    try:
        u = ULog(path)
    except Exception as e:
        # pyulog reads the definitions at the start first; damage there leaves nothing to decode
        raise ULogError(f"The PX4 log is damaged where its message definitions are (at the start of the file), "
                        f"so nothing in it can be read ({e}). Copy the log from the vehicle again, or open "
                        "another copy of it.") from None
    count: Dict[str, int] = {}
    for d in u.data_list:
        count[d.name] = count.get(d.name, 0) + 1
    sigs: Dict[str, tuple] = {}
    skipped = []
    t_hi = _time_end(u)
    bad_times = 0
    for d in u.data_list:
        ts = np.asarray(d.data.get("timestamp", []), dtype=np.float64) * 1e-6
        keep = ts > 0                       # a zero time stamp: no time (some old PX4 topics have only zeros)
        out = _damaged_times(ts, keep, t_hi)            # O2: time stamps only damage can have
        if out.any():
            bad_times += int(out.sum())
            keep &= ~out
        if not keep.any():
            skipped.append(d.name)
            continue
        idx = np.flatnonzero(keep)
        if not keep.all():
            ts = ts[idx]
        order = np.argsort(ts, kind="stable") if np.any(np.diff(ts) < 0) else None
        if order is not None:
            ts = ts[order]
            idx = idx[order]
        sel = None if (keep.all() and order is None) else idx
        base = d.name if count[d.name] == 1 else f"{d.name}[{d.multi_id}]"
        for field, col in d.data.items():
            if field in _SKIP or field.startswith("_padding"):
                continue
            y = np.asarray(col, dtype=np.float64)
            if sel is not None:
                y = y[sel]
            sigs[f"{base}.{field}"] = (ts, y, _LABELS.get((d.name, field)))
    if not sigs:
        return None, {}

    fl = FlightLogInfo()
    fl.vehicle = "px4"
    info = u.msg_info_dict
    ver = info.get("ver_sw_release") or info.get("ver_sw", "")
    fl.firmware = "PX4 " + (_release(ver) if isinstance(ver, int) else str(ver)[:10]) + (f" · {info['ver_hw']}" if info.get("ver_hw") else "")
    defaults: Dict[str, Any] = {}
    try:
        if u.has_default_parameters:
            defaults = u.get_default_parameters(1) or u.get_default_parameters(0) or {}
    except Exception:                   # optional extra: the log opens without default values
        log.debug("PX4 default parameters not read", exc_info=True)
        defaults = {}
    t0 = u.start_timestamp * 1e-6
    bad_params = 0
    # O2: a damaged parameter / message (bytes where a number should be) is left out, not the whole log
    for nm, v in sorted(u.initial_parameters.items()):
        try:
            fl.set_param(t0, nm, v, defaults.get(nm))
        except (TypeError, ValueError):
            bad_params += 1
    for ts, nm, v in u.changed_parameters:
        try:
            fl.set_param(ts * 1e-6, nm, v)
        except (TypeError, ValueError):
            bad_params += 1
    bad_texts = 0
    for m in u.logged_messages:
        try:
            lv = int(m.log_level)
            lv = lv - 48 if lv >= 48 else lv             # stored as the character '0'..'7' (syslog levels)
            lvl = "error" if lv <= 3 else "warning" if lv == 4 else "info"
            fl.add_event(m.timestamp * 1e-6, "msg", str(m.message), lvl)
        except (TypeError, ValueError):
            bad_texts += 1
    _state_events(sigs, fl)
    fl.sort_events()

    longest = max(sigs.values(), key=lambda v: len(v[0]))[0]
    run = Run(file_path=path, csv_display_name=display_name, time=longest)
    for name in sorted(sigs):
        t, y, lab = sigs[name]
        run.signals[name] = Signal(name=name, data=y, time=t, labels=dict(lab) if lab else None)
    run.compute_metadata()
    times = [sigs[n][0] for n in sigs]                  # the same arrays the signals got
    run.start_time = float(min(t[0] for t in times))
    run.end_time = float(max(t[-1] for t in times))
    run.sample_count = int(max(len(t) for t in times))
    run.import_settings = {"format": "ulg"}
    run._flightlog = fl
    rep = {"messages": len(count), "vehicle": "px4", "events": len(fl.events), "params": len(fl.param_first)}
    if skipped:
        rep["skipped"] = [f"{n} (no time stamps)" for n in skipped]
    if getattr(u, "file_corruption", False):
        rep["corruptBytes"] = 1
        rep["damaged"] = True               # pyulog does not say how much it skipped: say only that it did
    if bad_times:
        rep["badTimestamps"] = bad_times
    if bad_params:
        rep["damagedParams"] = bad_params
    if bad_texts:
        rep["damagedTexts"] = bad_texts
    return run, rep


def _time_end(u) -> float:
    """O2: the latest time [s] a sample of this log can have - its last message. A damaged header can
    make that absurd: then where the topics' own time stamps (all but the highest 0.1% of each) end,
    plus a minute. (No lower bound: PX4 stamps some topics before logging starts - a state published
    at boot keeps its boot time stamp.)"""
    ends = []
    for d in u.data_list:
        ts = np.asarray(d.data.get("timestamp", []), dtype=np.float64)
        ts = ts[ts > 0]
        if len(ts) >= 10:
            ends.append(float(np.percentile(ts, 99.9)) * 1e-6)
    hi = float(getattr(u, "last_timestamp", 0) or 0) * 1e-6
    bulk = max(ends) if ends else hi
    if not hi or hi < bulk or hi > bulk + 3600:
        hi = bulk + 60
    return hi


def _damaged_times(ts: np.ndarray, valid: np.ndarray, t_hi: float) -> np.ndarray:
    """O2: the samples of one topic whose time stamp a damaged block made: after the log's end; a lone
    sample far out of step with both neighbours (a flipped bit in an otherwise steady series); and a
    topic that has only zero time stamps (no time) except a few - those few."""
    bad = valid & (ts > t_hi)
    idx = np.flatnonzero(valid & ~bad)
    if 0 < len(idx) < 4 and len(ts) >= 100 * len(idx):
        bad[idx] = True
        return bad
    if len(idx) >= 3:
        v = ts[idx]
        steps = np.diff(v)
        tol = max(1.0, 100 * float(np.median(np.abs(steps)))) if len(steps) else 1.0
        prev, cur, nxt = v[:-2], v[1:-1], v[2:]
        lone = (prev <= nxt) & ((cur < prev - tol) | (cur > nxt + tol))
        bad[idx[1:-1][lone]] = True
    return bad


def _release(v: int) -> str:
    """ver_sw_release 0xAABBCCTT -> 'vAA.BB.CC'."""
    return f"v{(v >> 24) & 0xFF}.{(v >> 16) & 0xFF}.{(v >> 8) & 0xFF}"


def _state_events(sigs, fl: FlightLogInfo):
    nav = sigs.get("vehicle_status.nav_state")
    if nav:
        t, y, _ = nav
        prev = None
        for tv, v in zip(t.tolist(), y.tolist()):
            if v != prev:
                fl.add_event(tv, "mode", PX4_NAV.get(int(v), f"nav_state {int(v)}"), "info")
                prev = v
    arm = sigs.get("vehicle_status.arming_state")
    if arm:
        t, y, _ = arm
        prev = None
        for tv, v in zip(t.tolist(), y.tolist()):
            armed = int(v) == 2
            if prev is not None and armed != prev or prev is None and armed:
                fl.add_event(tv, "event", "ARMED" if armed else "DISARMED", "info")
            prev = armed
