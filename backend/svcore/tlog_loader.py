"""
MAVLink telemetry logs (.tlog) - what Mission Planner / QGroundControl / MAVProxy record from the
radio link: every MAVLink packet with an 8-byte big-endian receive time (microseconds, Unix time).

Message definitions (names, field order, types, units, enums) come from pymavlink's ArduPilot
dialect (a superset of common.xml); decoding is done here, per message type at once with numpy.

Signals:  "ATTITUDE.roll [rad]", "GPS_RAW_INT.lat [deg]" (degE7 -> deg, mV -> V, cm -> m...),
          arrays per element ("BATTERY_STATUS[0].voltages[1] [V]", unused cells -> NaN),
          enums with their names (GPS_RAW_INT.fix_type: GPS_FIX_TYPE_3D_FIX...), the flight mode by
          name (HEARTBEAT.custom_mode), HEARTBEAT.armed. Time = seconds from the first packet.
Messages from the ground station itself are left out; other components / vehicles get a tag:
          "ATTITUDE[c154].roll" (component 154), "ATTITUDE[s2].roll" (system 2).
Log panel: STATUSTEXT (with its real severity), mode changes, arm / disarm, PARAM_VALUE parameters.
Live mode: only the packets written since the last read are decoded.
"""
import os
import re
import struct
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from svcore.flightlog import FlightLogInfo, text_codes
from svcore.models import Run, Signal
from svcore.extras import missing

_NP = {"b": "i1", "B": "u1", "h": "<i2", "H": "<u2", "i": "<i4", "I": "<u4", "q": "<i8", "Q": "<u8",
       "f": "<f4", "d": "<f8", "c": "S1"}
UNIT_CONV = {"degE7": ("deg", 1e-7), "degE5": ("deg", 1e-5), "cdeg": ("deg", 0.01), "mV": ("V", 1e-3),
             "cA": ("A", 0.01), "cm": ("m", 0.01), "cm/s": ("m/s", 0.01), "mm": ("m", 1e-3), "mm/s": ("m/s", 1e-3),
             "dm": ("m", 0.1), "dm/s": ("m/s", 0.1), "cdegC": ("degC", 0.01), "c%": ("%", 0.01), "d%": ("%", 0.1),
             "mrad": ("rad", 1e-3), "mrad/s": ("rad/s", 1e-3), "cm/s/s": ("m/s/s", 0.01), "mm/s/s": ("m/s/s", 1e-3)}
_SKIP_FIELDS = {"time_boot_ms", "time_usec", "time_unix_usec", "time_boot_us"}
_SEVERITY = {0: "error", 1: "error", 2: "error", 3: "error", 4: "warning"}
_MAV_TYPE_VEHICLE = {1: "plane", 2: "copter", 3: "copter", 4: "copter", 13: "copter", 14: "copter", 15: "copter",
                     10: "rover", 11: "rover", 12: "sub", 19: "plane", 20: "plane", 21: "plane", 22: "plane"}
# PX4 custom_mode = main_mode << 16 | sub_mode << 24
_PX4_MAIN = {1: "MANUAL", 2: "ALTCTL", 3: "POSCTL", 4: "AUTO", 5: "ACRO", 6: "OFFBOARD", 7: "STABILIZED"}
_PX4_AUTO = {1: "READY", 2: "TAKEOFF", 3: "LOITER", 4: "MISSION", 5: "RTL", 6: "LAND", 8: "FOLLOW_TARGET", 9: "PRECLAND"}
_MAX_TEXTS = 1000


class TLogError(Exception):
    pass


_MAV = None


def _mav():
    global _MAV
    if _MAV is None:
        os.environ.setdefault("MAVLINK20", "1")
        try:
            from pymavlink.dialects.v20 import ardupilotmega as m
        except ImportError:
            raise TLogError(missing("Reading MAVLink telemetry logs (.tlog)", "mavlink")) from None
        _MAV = m
    return _MAV


_DT_CACHE: Dict[int, tuple] = {}


def _layout(cls):
    """numpy dtype of a message's (full, zero-extended) payload + per-field (name, count, kind)."""
    hit = _DT_CACHE.get(cls.id)
    if hit:
        return hit
    toks = re.findall(r"(\d*)([a-zA-Z])", cls.unpacker.format.lstrip("<"))
    fields, info = [], []
    for (cnt, ch), name in zip(toks, cls.ordered_fieldnames):
        n = int(cnt) if cnt else 1
        if ch == "s":
            fields.append((name, f"S{n}")); info.append((name, n, "text"))
        elif n > 1:
            fields.append((name, _NP[ch], (n,))); info.append((name, n, ch))
        else:
            fields.append((name, _NP[ch])); info.append((name, 1, ch))
    dt = np.dtype(fields)
    if dt.itemsize != cls.unpacker.size:
        raise TLogError(f"internal: {cls.msgname} layout mismatch")
    _DT_CACHE[cls.id] = (dt, info)
    return dt, info


def is_tlog(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(64)
        return len(head) >= 18 and head[8] in (0xFD, 0xFE)
    except OSError:
        return False


class TLogState:
    """What live mode needs to continue a .tlog: where reading stopped, the time base, who the vehicle is."""

    def __init__(self):
        self.offset = 0
        self.ts0: Optional[int] = None
        self.main: Optional[Tuple[int, int]] = None
        self.vehicle: Optional[str] = None
        self.autopilot: Optional[int] = None
        self.last_mode: Optional[int] = None
        self.last_armed: Optional[bool] = None
        self.text_labels: Dict[str, Dict[int, str]] = {}
        self.mode_labels: Dict[int, str] = {}
        self.flightlog = FlightLogInfo()
        self.bad_bytes = 0
        # (receive time [s from the first packet], autopilot boot time [s]) from messages that carry
        # time_boot_ms: the link between this log's clock and the autopilot's (.bin / .ulg) clock
        self.boot_t: List[np.ndarray] = []
        self.boot_b: List[np.ndarray] = []
        # boot clock -> this log's time: one entry per autopilot boot seen, D = boot time - receive time
        # (median, so it includes the typical radio delay). Messages that carry the autopilot's clock are
        # placed at boot time - D: their true moment, without the radio delay of each packet.
        self.boot_D: List[float] = []
        # A5: the boots in receive order - (receive time the boot was first seen, its D); a sample
        # belongs to the last boot that started at or before it was received. And the last boot's
        # newest boot time, so live mode can tell "the same boot, more data" from a reboot.
        self.boots: List[Tuple[float, float]] = []
        self.boot_last_tb: Optional[float] = None


def _scan(raw: bytes, start: int, st: TLogState):
    """Frames in raw[start:] -> {msgid: {(sys, comp): ([ts...], [payload...])}} and the end of the
    last complete frame. Bytes that do not start a frame are skipped (resynchronisation)."""
    mavmap = _mav().mavlink_map
    sizes = {k: c.unpacker.size for k, c in mavmap.items()}
    out: dict = defaultdict(lambda: defaultdict(lambda: ([], [])))
    n, i = len(raw), start
    unpack_ts = struct.Struct(">Q").unpack_from
    end = start
    while i + 18 <= n:
        magic = raw[i + 8]
        if magic == 0xFD:
            ln, inc = raw[i + 9], raw[i + 10]
            total = 8 + 10 + ln + 2 + (13 if inc & 1 else 0)
            sysid, comp = raw[i + 13], raw[i + 14]
            msgid = raw[i + 15] | (raw[i + 16] << 8) | (raw[i + 17] << 16)
            p0 = i + 18
        elif magic == 0xFE:
            ln = raw[i + 9]
            total = 8 + 6 + ln + 2
            sysid, comp, msgid = raw[i + 11], raw[i + 12], raw[i + 13]
            p0 = i + 14
        else:
            i += 1; st.bad_bytes += 1
            continue
        if i + total > n:
            break                                            # cut by the end of the file: next time
        nxt = i + total
        if nxt + 9 <= n and raw[nxt + 8] not in (0xFD, 0xFE):
            i += 1; st.bad_bytes += 1                        # not followed by a frame: not a frame
            continue
        size = sizes.get(msgid)
        if size is not None and ln <= size:
            ts = unpack_ts(raw, i)[0]
            g = out[msgid][(sysid, comp)]
            g[0].append(ts)
            p = raw[p0:p0 + ln]
            g[1].append(p if ln == size else p + bytes(size - ln))   # v2 drops trailing zeros
        i = nxt
        end = nxt
    return out, end


def _decode(frames, st: TLogState) -> Dict[str, tuple]:
    """Decoded frames -> {signal name: (t, values[, labels])}, and the Log panel's data."""
    m = _mav()
    mavmap = m.mavlink_map
    if st.ts0 is None:
        firsts = [min(g[0]) for byk in frames.values() for g in byk.values() if g[0]]
        if not firsts:
            return {}
        st.ts0 = min(firsts)
    # which system / component is the vehicle: its autopilot's heartbeats
    if st.main is None:
        hb = frames.get(0, {})
        votes: Counter = Counter()
        for key, (ts, pl) in hb.items():
            dt, _ = _layout(mavmap[0])
            arr = np.frombuffer(b"".join(pl), dtype=dt)
            votes[key] += int(np.sum(arr["autopilot"] != 8))          # 8: MAV_AUTOPILOT_INVALID (a GCS)
        if votes and votes.most_common(1)[0][1] > 0:
            st.main = votes.most_common(1)[0][0]
        else:
            allk = Counter({k: len(g[0]) for byk in frames.values() for k, g in byk.items() if k[0] != 255})
            st.main = allk.most_common(1)[0][0] if allk else (1, 1)
    gcs = set()
    for key, (ts, pl) in frames.get(0, {}).items():
        dt, _ = _layout(mavmap[0])
        arr = np.frombuffer(b"".join(pl), dtype=dt)
        if np.all(arr["autopilot"] == 8):
            gcs.add(key[0])
    gcs.discard(st.main[0])

    _learn_boot(frames, st)
    out: Dict[str, tuple] = {}
    fl = st.flightlog
    for msgid, byk in frames.items():
        cls = mavmap[msgid]
        dt, info = _layout(cls)
        units = getattr(cls, "fieldunits_by_name", {}) or {}
        enums = getattr(cls, "fieldenums_by_name", {}) or {}
        displays = getattr(cls, "fielddisplays_by_name", {}) or {}
        inst_field = getattr(cls, "instance_field", None)
        for (sysid, comp), (ts, pl) in byk.items():
            if sysid in gcs:
                continue
            tag = "" if (sysid, comp) == st.main else (f"[c{comp}]" if sysid == st.main[0] else f"[s{sysid}]")
            arr = np.frombuffer(b"".join(pl), dtype=dt)
            t = (np.asarray(ts, dtype=np.float64) - st.ts0) * 1e-6
            if tag == "" and st.boots:
                t = _boot_time(st, t, arr)
            if len(t) > 1 and np.any(np.diff(t) < 0):
                o = np.argsort(t, kind="stable"); t, arr = t[o], arr[o]
            name = cls.msgname
            if tag == "" and "time_boot_ms" in arr.dtype.names and len(t):
                k = max(1, len(t) // 4000)                     # a few thousand pairs are plenty
                st.boot_t.append(t[::k]); st.boot_b.append(arr["time_boot_ms"][::k].astype(np.float64) * 1e-3)
            if tag == "" and name in ("HEARTBEAT", "STATUSTEXT", "PARAM_VALUE"):
                _special(name, t, arr, st, out)
                if name != "HEARTBEAT":
                    continue
            groups: List[Tuple[Optional[int], Any]] = [(None, slice(None))]
            if inst_field and inst_field in arr.dtype.names and not tag:
                iv = arr[inst_field]
                groups = [(int(v), iv == v) for v in np.unique(iv)]
            for ival, sel in groups:
                tt = t[sel]
                a = arr[sel]
                base = f"{name}{tag}" + ("" if ival is None else f"[{ival}]")
                for fname, cnt, kind in info:
                    if fname in _SKIP_FIELDS or fname == inst_field and ival is not None:
                        continue
                    if name == "HEARTBEAT" and fname == "custom_mode":
                        continue                                           # added by _special, with names
                    col = a[fname]
                    if kind == "text":
                        txt = [v.split(b"\0", 1)[0].decode("latin-1", "replace").strip() for v in col.tolist()]
                        key = f"{base}.{fname}"
                        codes, labels = text_codes(txt, st.text_labels.get(key))
                        if labels and len(labels) <= _MAX_TEXTS:
                            st.text_labels[key] = labels
                            out[key] = (tt, codes, labels)
                        continue
                    unit = units.get(fname, "")
                    label, mult = UNIT_CONV.get(unit, (unit, 1.0))
                    lab_map = None
                    en = enums.get(fname)
                    if en and displays.get(fname) != "bitmask" and en in m.enums:
                        lab_map = {int(k): v.name for k, v in m.enums[en].items() if not v.name.endswith("_ENUM_END")}
                    cols = [col] if cnt == 1 else [col[:, k] for k in range(cnt)]
                    for k, c in enumerate(cols):
                        y = c.astype(np.float64)
                        if cnt > 1 and kind in "HI":                     # unused array slots
                            y[c == (0xFFFF if kind == "H" else 0xFFFFFFFF)] = np.nan
                        if mult != 1.0:
                            y = y * mult
                        nm = f"{base}.{fname}" + (f"[{k}]" if cnt > 1 else "") + (f" [{label}]" if label and not lab_map else "")
                        out[nm] = (tt, y, lab_map) if lab_map else (tt, y)
    fl.sort_events()
    return out


def _main_boot_arrays(frames, st: TLogState):
    """(receive time, boot time) of the vehicle's messages that carry time_boot_ms."""
    if st.ts0 is None:                       # nothing decoded yet
        return None
    mavmap = _mav().mavlink_map
    tr, tb = [], []
    for msgid, byk in frames.items():
        cls = mavmap[msgid]
        if "time_boot_ms" not in cls.fieldnames or st.main not in byk:
            continue
        ts, pl = byk[st.main]
        dt, _ = _layout(cls)
        arr = np.frombuffer(b"".join(pl), dtype=dt)
        tr.append((np.asarray(ts, dtype=np.float64) - st.ts0) * 1e-6)
        tb.append(arr["time_boot_ms"].astype(np.float64) * 1e-3)
    if not tr:
        return None
    return np.concatenate(tr), np.concatenate(tb)


REBOOT_DROP = 10.0       # s: the boot clock going back this much (and staying back) is a reboot
MAX_LATENCY = 60.0       # s: a boot time further than this from its receive time is not this boot's clock


def _boot_starts(tb: np.ndarray, start_max: float = -np.inf) -> List[int]:
    """Indices (in receive order) where a new boot starts: the boot clock goes back by more than
    REBOOT_DROP from the highest value of the current boot, and the next samples confirm it (one
    corrupted or very late packet is not a reboot). start_max: the current boot's highest boot time
    from before these samples (live mode)."""
    starts: List[int] = []
    n, i0, top = len(tb), 0, start_max
    while i0 < n:
        run_max = np.maximum.accumulate(np.concatenate([[top], tb[i0:]]))[:-1]
        cand = np.flatnonzero(tb[i0:] < run_max - REBOOT_DROP)
        found = None
        for c in cand.tolist():
            j = i0 + c
            nxt = tb[j + 1: j + 4]
            if not len(nxt) or np.all(nxt < run_max[c] - REBOOT_DROP):
                found = j
                break
        if found is None:
            break
        starts.append(found)
        i0, top = found, -np.inf
    return starts


def _learn_boot(frames, st: TLogState):
    """Find the autopilot's boots in these frames and D (boot time - receive time) for each.

    A boot is a stretch, in receive order, in which the boot clock only runs on; a reboot restarts
    it (_boot_starts). D is the median of boot time - receive time over the boot: one constant per
    boot, so every message that carries the boot clock keeps its exact spacing.

    Before A5 the boots were found by rounding D to whole seconds, assuming that the radio delay of
    one boot varies by well under a second. A real telemetry log (ArduPilot's own vtol.tlog) has
    delays from 0 to 4 s: that one boot became five "boots" a second apart, and about one sample in
    ten was moved by 1 to 3 s - and, re-sorted by the wrong time, ended up out of order."""
    got = _main_boot_arrays(frames, st)
    if got is None:
        return
    tr, tb = got
    ok = tb > 0
    tr, tb = tr[ok], tb[ok]
    if not len(tr):
        return
    o = np.argsort(tr, kind="stable")
    tr, tb = tr[o], tb[o]
    last_tb = st.boot_last_tb if st.boots else None           # live: the current boot's newest boot time
    cont = last_tb is not None
    starts = _boot_starts(tb, last_tb if last_tb is not None else -np.inf)
    edges = [0] + starts + [len(tr)]
    for k in range(len(edges) - 1):
        a, b = edges[k], edges[k + 1]
        if b - a < 3 and len(edges) > 2:
            continue                                         # a stray packet between reboots
        if k == 0 and cont:
            continue                                         # live: more of the boot already known
        D = float(np.median(tb[a:b] - tr[a:b]))
        st.boots.append((float(tr[a]), D))
        st.boot_D.append(D)
    newest = float(np.max(tb[starts[-1] if starts else 0:]))
    st.boot_last_tb = max(last_tb, newest) if (last_tb is not None and not starts) else newest


def _boot_time(st: TLogState, t_recv: np.ndarray, arr) -> np.ndarray:
    """The message's own time when it carries the autopilot's clock (time_boot_ms, or time_usec when
    that is boot time - not Unix time), else its receive time. Each sample uses the D of the boot it
    was received in, and the boot clock as long as it is within MAX_LATENCY of the receive time."""
    names = arr.dtype.names
    tb = None
    if "time_boot_ms" in names:
        tb = arr["time_boot_ms"].astype(np.float64) * 1e-3
    elif "time_usec" in names:
        tb = arr["time_usec"].astype(np.float64) * 1e-6       # boot time in some messages, Unix time in others
    if tb is None or not st.boots:
        return t_recv
    starts = np.array([b[0] for b in st.boots])
    Ds = np.array([b[1] for b in st.boots])
    k = np.clip(np.searchsorted(starts, t_recv, side="right") - 1, 0, len(Ds) - 1)
    Dk = Ds[k]
    good = (tb > 0) & (np.abs(tb - t_recv - Dk) < MAX_LATENCY)
    return np.where(good, tb - Dk, t_recv)


def _special(name, t, arr, st: TLogState, out):
    fl = st.flightlog
    if name == "STATUSTEXT":
        for tv, sev, txt in zip(t.tolist(), arr["severity"].tolist(), arr["text"].tolist()):
            s = txt.split(b"\0", 1)[0].decode("latin-1", "replace").strip()
            if s:
                fl.add_event(tv, "msg", s, _SEVERITY.get(int(sev), "info"))
    elif name == "PARAM_VALUE":
        for tv, pid, val in zip(t.tolist(), arr["param_id"].tolist(), arr["param_value"].tolist()):
            nm = pid.split(b"\0", 1)[0].decode("latin-1", "replace").strip()
            if nm:
                fl.set_param(tv, nm, val)
    elif name == "HEARTBEAT":
        if st.vehicle is None and len(arr):
            st.autopilot = int(arr["autopilot"][0])
            st.vehicle = "px4" if st.autopilot == 12 else _MAV_TYPE_VEHICLE.get(int(arr["type"][0]))
            fl.vehicle = st.vehicle
        cm = arr["custom_mode"].astype(np.int64)
        for v in np.unique(cm).tolist():
            st.mode_labels.setdefault(int(v), _mode_name(int(v), st))
        out["HEARTBEAT.custom_mode"] = (t, cm.astype(np.float64), dict(st.mode_labels))
        armed = (arr["base_mode"] & 128) != 0
        out["HEARTBEAT.armed"] = (t, armed.astype(np.float64), {0: "DISARMED", 1: "ARMED"})
        for tv, mv, av in zip(t.tolist(), cm.tolist(), armed.tolist()):
            if mv != st.last_mode:
                fl.add_event(tv, "mode", st.mode_labels.get(mv, f"Mode {mv}"), "info")
                st.last_mode = mv
            if av != st.last_armed:
                if st.last_armed is not None or av:
                    fl.add_event(tv, "event", "ARMED" if av else "DISARMED", "info")
                st.last_armed = av


def _mode_name(v: int, st: TLogState) -> str:
    if st.autopilot == 12:                                        # PX4
        main, sub = (v >> 16) & 0xFF, (v >> 24) & 0xFF
        nm = _PX4_MAIN.get(main, f"MODE {main}")
        if main == 4 and sub:
            nm += "." + _PX4_AUTO.get(sub, str(sub))
        return nm
    from svcore.bin_loader import MODES
    return MODES.get(st.vehicle or "", {}).get(v, f"Mode {v}")


def _read(path: str, start: int = 0) -> bytes:
    with open(path, "rb") as f:
        if start:
            f.seek(start)
        return f.read()


def load_tlog(path: str, display_name: str):
    if not is_tlog(path):
        raise TLogError("This is not a MAVLink telemetry log (.tlog).")
    raw = _read(path)
    st = TLogState()
    frames, end = _scan(raw, 0, st)
    sigs = _decode(frames, st)
    if not sigs:
        return None, {}
    longest = max(sigs.values(), key=lambda v: len(v[0]))[0]
    run = Run(file_path=path, csv_display_name=display_name, time=longest)
    for name in sorted(sigs):
        v = sigs[name]
        run.signals[name] = Signal(name=name, data=v[1], time=v[0], labels=dict(v[2]) if len(v) > 2 and v[2] else None)
    _finish(run, path, end, st)
    run.import_settings = {"format": "tlog"}
    rep = {"messages": len({n.split(".")[0] for n in sigs}), "vehicle": st.vehicle, "events": len(st.flightlog.events),
           "params": len(st.flightlog.param_first)}
    if st.bad_bytes:
        rep["corruptBytes"] = int(st.bad_bytes)
    return run, rep


def _finish(run: Run, path: str, end: int, st: TLogState):
    st.offset = end
    run._tlog = st
    run._flightlog = st.flightlog
    run.byte_offset = end
    stt = os.stat(path)
    run.seen_size, run.seen_mtime = stt.st_size, stt.st_mtime
    run.compute_metadata()
    times = [s.time for s in run.signals.values() if s.time is not None and len(s.time)]
    if times:
        run.start_time = float(min(t[0] for t in times))
        run.end_time = float(max(t[-1] for t in times))
        run.sample_count = int(max(len(t) for t in times))


def append_tlog(run: Run) -> int:
    """Live mode: decode the packets written since the last read (-1: rewritten -> reload)."""
    st: Optional[TLogState] = getattr(run, "_tlog", None)
    try:
        size = os.path.getsize(run.file_path)
    except OSError:
        return -1
    if st is None or size < st.offset:
        return -1
    if size == st.offset:
        return 0
    raw = _read(run.file_path, st.offset)
    frames, end = _scan(raw, 0, st)
    if not end:
        return 0
    sigs = _decode(frames, st)
    added = 0
    for name, v in sigs.items():
        t, y = v[0], v[1]
        labels = dict(v[2]) if len(v) > 2 and v[2] else None
        s = run.signals.get(name)
        if s is None:
            run.signals[name] = Signal(name=name, data=y, time=t, labels=labels)
        else:
            s.time = np.concatenate([s.time, t]); s.data = np.concatenate([np.asarray(s.data), y])
            if labels:
                s.labels = labels
        added += len(t)
    _finish(run, run.file_path, st.offset + end, st)
    return added
