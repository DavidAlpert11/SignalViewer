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
        raise ULogError("Reading PX4 logs needs the pyulog library (pip install pyulog).") from None
    try:
        u = ULog(path)
    except Exception as e:
        raise ULogError(f"Could not read the PX4 log: {e}") from None
    count: Dict[str, int] = {}
    for d in u.data_list:
        count[d.name] = count.get(d.name, 0) + 1
    sigs: Dict[str, tuple] = {}
    skipped = []
    for d in u.data_list:
        ts = np.asarray(d.data.get("timestamp", []), dtype=np.float64) * 1e-6
        keep = ts > 0                       # a zero time stamp: no time (some old PX4 topics have only zeros)
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
    for nm, v in sorted(u.initial_parameters.items()):
        fl.set_param(t0, nm, v, defaults.get(nm))
    for ts, nm, v in u.changed_parameters:
        fl.set_param(ts * 1e-6, nm, v)
    for m in u.logged_messages:
        lv = int(m.log_level)
        lv = lv - 48 if lv >= 48 else lv                 # stored as the character '0'..'7' (syslog levels)
        lvl = "error" if lv <= 3 else "warning" if lv == 4 else "info"
        fl.add_event(m.timestamp * 1e-6, "msg", str(m.message), lvl)
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
    return run, rep


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
