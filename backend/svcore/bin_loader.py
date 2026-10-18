"""
ArduPilot DataFlash binary logs (.bin / .BIN) - fast, dependency-free reader.

Format (as written by ArduPilot, read the same way by pymavlink / Mission Planner):
    every message = 0xA3 0x95 <type byte> <payload>; the payload layout of each type is
    declared by an FMT message (type 128): Type, Length, Name, Format, Columns.
    Format characters:  b B h H i I q Q f d  (plain numbers)
                        c C e E  (x 0.01)     L  (lat/lon x 1e-7)     M  (flight mode, uint8)
                        n N Z    (text 4/16/64 chars - skipped)       a  (int16[32] - skipped)
    FMTU / UNIT / MULT messages (newer firmware) give each field its unit and multiplier, and
    mark the INSTANCE field ('#') of messages that several sensors share (IMU, GPS, BARO, BAT...).

How this reader stays fast without a per-message Python loop:
    1. FMT messages are found by their 3-byte header and validated (the declared length must
       match the format string), giving the length of every message type.
    2. Every position holding A3 95 <known type> is a candidate. Real messages form ONE chain
       (each message starts where the previous one ends); false candidates (the same bytes inside
       a payload) are dropped by following that chain with pointer doubling - O(n log n) numpy.
       A break in the chain (a corrupted / truncated block) resynchronises at the next candidate.
    3. Each message type is decoded at once with a numpy structured dtype.

Signals:   one per numeric field, named  "MSG.Field"  or  "MSG[instance].Field",  with the unit
           in brackets when the log says it ("GPS[0].Alt [m]"). Every message type keeps ITS OWN
           time vector (TimeUS, seconds since boot): IMU at 400 Hz and GPS at 5 Hz are not
           resampled onto each other. Formulas and compare align them in time as usual.
Live mode: append_new_messages() parses only the bytes written since the last read.
"""

import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from svcore.models import Run, Signal
from svcore.csv_loader import encode_text

HEAD1, HEAD2, FMT_TYPE = 0xA3, 0x95, 128
FMT_LEN = 89

# format char -> (numpy dtype, multiplier or None for "skip as signal")
_FMT = {
    "b": ("<i1", 1.0), "B": ("<u1", 1.0), "h": ("<i2", 1.0), "H": ("<u2", 1.0),
    "i": ("<i4", 1.0), "I": ("<u4", 1.0), "q": ("<i8", 1.0), "Q": ("<u8", 1.0),
    "f": ("<f4", 1.0), "d": ("<f8", 1.0), "M": ("<u1", 1.0),
    "c": ("<i2", 0.01), "C": ("<u2", 0.01), "e": ("<i4", 0.01), "E": ("<u4", 0.01),
    "L": ("<i4", 1e-7),
    "n": ("S4", None), "N": ("S16", None), "Z": ("S64", None), "a": ("(32,)<i2", None),
}
_SIZE = {k: np.dtype(v[0]).itemsize for k, v in _FMT.items()}
_SCALED = set("cCeEL")
_POW10 = set("210ABCDEFGI")                # multiplier ids that are powers of ten                       # the format char already applies the multiplier
_INSTANCE_NAMES = ("I", "Inst", "Instance")   # fallback when there is no FMTU
_TIME_FIELDS = (("TimeUS", 1e-6), ("TimeMS", 1e-3), ("TimeUs", 1e-6))
_SKIP_TYPES = {"FMT", "FMTU", "UNIT", "MULT", "PARM", "FILE"}   # metadata
_MAX_TEXTS = 1000                    # a text field with more distinct values is not a state

# Flight-mode names (ArduPilot's mode numbers per vehicle). The vehicle is read from the log's
# own start-up messages ("ArduCopter V4.5.7", "ArduPlane", "ArduRover", "ArduSub").
MODES = {
    "copter": {0: "STABILIZE", 1: "ACRO", 2: "ALT_HOLD", 3: "AUTO", 4: "GUIDED", 5: "LOITER", 6: "RTL",
               7: "CIRCLE", 9: "LAND", 11: "DRIFT", 13: "SPORT", 14: "FLIP", 15: "AUTOTUNE", 16: "POSHOLD",
               17: "BRAKE", 18: "THROW", 19: "AVOID_ADSB", 20: "GUIDED_NOGPS", 21: "SMART_RTL", 22: "FLOWHOLD",
               23: "FOLLOW", 24: "ZIGZAG", 25: "SYSTEMID", 26: "AUTOROTATE", 27: "AUTO_RTL", 28: "TURTLE"},
    "plane": {0: "MANUAL", 1: "CIRCLE", 2: "STABILIZE", 3: "TRAINING", 4: "ACRO", 5: "FBWA", 6: "FBWB",
              7: "CRUISE", 8: "AUTOTUNE", 10: "AUTO", 11: "RTL", 12: "LOITER", 13: "TAKEOFF", 14: "AVOID_ADSB",
              15: "GUIDED", 17: "QSTABILIZE", 18: "QHOVER", 19: "QLOITER", 20: "QLAND", 21: "QRTL",
              22: "QAUTOTUNE", 23: "QACRO", 24: "THERMAL", 25: "LOITER_ALT_QLAND", 26: "AUTOLAND"},
    "rover": {0: "MANUAL", 1: "ACRO", 3: "STEERING", 4: "HOLD", 5: "LOITER", 6: "FOLLOW", 7: "SIMPLE",
              8: "DOCK", 9: "CIRCLE", 10: "AUTO", 11: "RTL", 12: "SMART_RTL", 15: "GUIDED", 16: "INITIALISING"},
    "sub": {0: "STABILIZE", 1: "ACRO", 2: "ALT_HOLD", 3: "AUTO", 4: "GUIDED", 7: "CIRCLE", 9: "SURFACE",
            16: "POSHOLD", 19: "MANUAL", 20: "MOTOR_DETECT", 21: "SURFTRAK"},
}
EVENTS = {10: "ARMED", 11: "DISARMED", 15: "AUTO_ARMED", 17: "LAND_COMPLETE_MAYBE", 18: "LAND_COMPLETE",
          25: "SET_HOME", 28: "NOT_LANDED"}


_ERR_WORDS = re.compile(r"crash|emergency|critical|panic|fail|error|lost|terminat|thrust loss|ekf.*(variance|lane switch)", re.I)
_WARN_WORDS = re.compile(r"prearm|arm:|warn|unhealthy|glitch|timeout|bad |low|check|disabled|not ready|vibration|clipping", re.I)


def _f32(v) -> float:
    """A float32 parameter as written (0.15, not 0.15000000596)."""
    return float(f"{float(v):.7g}")


def message_level(text: str) -> str:
    """'error' / 'warning' / 'info' from the words of a log text (DataFlash MSG has no severity)."""
    if _ERR_WORDS.search(text):
        return "error"
    if _WARN_WORDS.search(text):
        return "warning"
    return "info"


def vehicle_of(texts) -> Optional[str]:
    for _t, txt in texts[:200]:
        low = txt.lower()
        for key, veh in (("arducopter", "copter"), ("ardupilot copter", "copter"), ("heli", "copter"),
                         ("arduplane", "plane"), ("ardurover", "rover"), ("rover", "rover"), ("ardusub", "sub")):
            if key in low:
                return veh
    return None


class BinFormatError(Exception):
    pass


def is_dataflash(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(3)
        return len(head) == 3 and head[0] == HEAD1 and head[1] == HEAD2 and head[2] == FMT_TYPE
    except OSError:
        return False


def _cstr(b: bytes) -> str:
    return b.split(b"\x00", 1)[0].decode("ascii", "replace").strip()


class MsgFormat:
    __slots__ = ("type", "length", "name", "fmt", "columns", "dtype", "units", "mults", "instance")

    def __init__(self, typ: int, length: int, name: str, fmt: str, columns: List[str]):
        self.type, self.length, self.name, self.fmt, self.columns = typ, length, name, fmt, columns
        self.dtype = np.dtype([(f"f{k}", _FMT[ch][0]) for k, ch in enumerate(fmt)])
        self.units: Optional[str] = None      # unit id per field (from FMTU)
        self.mults: Optional[str] = None
        self.instance: Optional[int] = None   # index of the instance field


def _parse_fmt_payload(p: bytes) -> Optional[MsgFormat]:
    typ, length = p[0], p[1]
    name, fmt, cols = _cstr(p[2:6]), _cstr(p[6:22]), _cstr(p[22:86])
    if not name or not re.fullmatch(r"[A-Za-z0-9_]{1,4}", name) or length < 3:
        return None
    if any(ch not in _FMT for ch in fmt):
        return None
    if 3 + sum(_SIZE[ch] for ch in fmt) != length:
        return None                           # not a real FMT (bytes that only look like one)
    columns = [c.strip() for c in cols.split(",")] if cols else []
    if len(columns) != len(fmt):
        return None
    return MsgFormat(typ, length, name, fmt, columns)


class DataFlash:
    """Formats + decoded messages of one log. Kept on the Run, so live mode can continue."""

    def __init__(self):
        self.formats: Dict[int, MsgFormat] = {FMT_TYPE: MsgFormat(FMT_TYPE, FMT_LEN, "FMT", "BBnNZ",
                                                                  ["Type", "Length", "Name", "Format", "Columns"])}
        self.unit_label: Dict[str, str] = {}
        self.mult_value: Dict[str, float] = {}
        self.fmtu: Dict[int, Tuple[str, str]] = {}
        self.texts: List[Tuple[float, str]] = []       # MSG messages (time, text)
        self.params: Dict[str, float] = {}             # last value of each parameter
        self.param_first: Dict[str, Tuple[float, float, Optional[float]]] = {}   # name -> (t, value, default)
        self.param_changes: Dict[str, List[Tuple[float, float]]] = {}            # name -> [(t, new value)]
        self.events: List[dict] = []                   # MSG / MODE / EV / ERR, in time order
        self._new_texts: List[Tuple[float, str]] = []
        self.corrupt_bytes = 0
        self.vehicle: Optional[str] = None
        self.text_labels: Dict[str, Dict[int, str]] = {}   # signal -> {code: text}, kept for live mode

    # ------------------------------------------------------------------ framing
    def _lengths(self) -> np.ndarray:
        lut = np.zeros(256, dtype=np.int64)
        for t, f in self.formats.items():
            lut[t] = f.length
        return lut

    def _scan_formats(self, buf: np.ndarray, raw: bytes):
        """All FMT messages anywhere in the buffer (validated, so payload bytes are ignored)."""
        n = len(buf)
        if n < FMT_LEN:
            return
        cand = np.flatnonzero((buf[:-2] == HEAD1) & (buf[1:-1] == HEAD2) & (buf[2:] == FMT_TYPE))
        for i in cand.tolist():
            if i + FMT_LEN > n:
                break
            f = _parse_fmt_payload(raw[i + 3:i + FMT_LEN])
            if f is not None and f.type != FMT_TYPE:
                self.formats[f.type] = f

    def frame(self, buf: np.ndarray, raw: bytes, start: int = 0) -> Tuple[np.ndarray, np.ndarray, int]:
        """Positions and types of the real messages in buf[start:]. Returns (pos, type, end) where
        end is the byte after the last COMPLETE message (a message cut by the end of the file is
        left for the next read)."""
        self._scan_formats(buf[start:], raw[start:])
        lut = self._lengths()
        n = len(buf)
        if n - start < 3:
            return np.empty(0, np.int64), np.empty(0, np.uint8), start
        b0, b1, b2 = buf[start:-2], buf[start + 1:-1], buf[start + 2:]
        cand = np.flatnonzero((b0 == HEAD1) & (b1 == HEAD2) & (lut[b2] > 0)) + start
        if not len(cand):
            return np.empty(0, np.int64), np.empty(0, np.uint8), start
        ln = lut[buf[cand + 2]]
        complete = cand + ln <= n
        cand, ln = cand[complete], ln[complete]
        m = len(cand)
        if not m:
            return np.empty(0, np.int64), np.empty(0, np.uint8), start
        # successor of each candidate = the candidate starting where it ends (m = none: chain break)
        ends = cand + ln
        j = np.searchsorted(cand, ends)
        ok = (j < m) & (cand[np.minimum(j, m - 1)] == ends)
        nxt = np.where(ok, j, m).astype(np.int64)
        nxt = np.append(nxt, m)                      # sink

        keep = np.zeros(m + 1, dtype=bool)
        k0 = 0
        resyncs = 0
        while k0 < m:
            path = _chain(nxt, k0, m)
            keep[path] = True
            last = int(path[-1]) if len(path) else k0
            stop = int(ends[last])
            # resynchronise: the next candidate that starts at or after the end of the chain
            k1 = int(np.searchsorted(cand, stop))
            if k1 >= m:
                break
            self.corrupt_bytes += int(cand[k1] - stop)
            k0 = k1
            resyncs += 1
            if resyncs > 10000:
                raise BinFormatError("The log is too damaged to read.")
        keep = keep[:m]
        pos = cand[keep]
        end = int(pos[-1] + lut[buf[pos[-1] + 2]]) if len(pos) else start
        return pos, buf[pos + 2], end

    # ------------------------------------------------------------------ decode
    def decode(self, buf: np.ndarray, pos: np.ndarray, types: np.ndarray) -> Dict[int, np.ndarray]:
        """{type: structured array of its messages} (in file order)."""
        out: Dict[int, np.ndarray] = {}
        maxw = max((f.length for f in self.formats.values()), default=3)
        pad = np.concatenate([buf, np.zeros(maxw, np.uint8)])     # rows near the end stay in bounds
        order = np.argsort(types, kind="stable")
        st, pt = types[order], pos[order]
        bounds = np.flatnonzero(np.diff(st.astype(np.int16))) + 1
        for grp_pos, t in zip(np.split(pt, bounds), st[np.r_[0, bounds]] if len(st) else []):
            f = self.formats.get(int(t))
            if f is None or f.type == FMT_TYPE:
                continue
            width = f.length - 3
            # a (bytes x width) sliding view of the file: indexing it copies only n x width bytes
            win = np.lib.stride_tricks.as_strided(pad, shape=(len(buf), width), strides=(1, 1), writeable=False)
            rows = win[grp_pos + 3]                                          # (n, width) uint8
            out[int(t)] = np.ascontiguousarray(rows).view(f.dtype).reshape(-1)
        self._metadata(out)
        return out

    def _metadata(self, dec: Dict[int, np.ndarray]):
        """UNIT / MULT / FMTU (units, multipliers, instance field), PARM and MSG text."""
        by_name = {self.formats[t].name: (self.formats[t], a) for t, a in dec.items() if t in self.formats}

        def field(name, col):
            f, a = by_name[name]
            return a[f"f{f.columns.index(col)}"] if col in f.columns else None

        if "UNIT" in by_name:
            ids, labels = field("UNIT", "Id"), field("UNIT", "Label")
            if ids is not None and labels is not None:
                for i, l in zip(ids.tolist(), labels.tolist()):
                    self.unit_label[chr(i) if isinstance(i, int) else _cstr(i)] = _cstr(l)
        if "MULT" in by_name:
            ids, mult = field("MULT", "Id"), field("MULT", "Mult")
            if ids is not None and mult is not None:
                for i, v in zip(ids.tolist(), mult.tolist()):
                    self.mult_value[chr(i) if isinstance(i, int) else _cstr(i)] = float(v)
        if "FMTU" in by_name:
            ft, uid, mid = field("FMTU", "FmtType"), field("FMTU", "UnitIds"), field("FMTU", "MultIds")
            if ft is not None and uid is not None and mid is not None:
                for t, u, m in zip(ft.tolist(), uid.tolist(), mid.tolist()):
                    self.fmtu[int(t)] = (_cstr(u), _cstr(m))
        for t, (u, m) in self.fmtu.items():
            f = self.formats.get(t)
            if f is not None and f.units is None:
                f.units, f.mults = u, m
                if "#" in u and u.index("#") < len(f.fmt):
                    f.instance = u.index("#")
        if "PARM" in by_name:
            # every PARM message: the full list at start-up, then one more whenever a value is set
            names, vals = field("PARM", "Name"), field("PARM", "Value")
            tus, dflt = field("PARM", "TimeUS"), field("PARM", "Default")
            if names is not None and vals is not None:
                ts = (tus.astype(np.float64) * 1e-6).tolist() if tus is not None else [0.0] * len(names)
                ds = dflt.tolist() if dflt is not None else [None] * len(names)
                for t, nm, v, d in zip(ts, names.tolist(), vals.tolist(), ds):
                    nm, v = _cstr(nm), _f32(v)
                    d = None if d is None or not np.isfinite(d) else _f32(d)
                    if nm not in self.param_first:
                        self.param_first[nm] = (t, v, d)
                    elif v != self.params.get(nm):
                        self.param_changes.setdefault(nm, []).append((t, v))
                    self.params[nm] = v
        self._new_texts = []
        if "MSG" in by_name:
            txt = field("MSG", "Message")
            tus = field("MSG", "TimeUS")
            if txt is not None:
                ts = (tus.astype(np.float64) * 1e-6).tolist() if tus is not None else [float("nan")] * len(txt)
                self._new_texts = [(t, _cstr(m)) for t, m in zip(ts, txt.tolist())]
                self.texts.extend(self._new_texts)

    def collect_events(self, dec: Dict[int, np.ndarray]):
        """Messages, flight-mode changes, events and errors of one decoded block -> self.events."""
        new: List[dict] = []
        for t, txt in self._new_texts:
            new.append({"t": t, "kind": "msg", "text": txt, "level": message_level(txt)})
        by_name = {self.formats[t].name: (self.formats[t], a) for t, a in dec.items() if t in self.formats}

        def col(name, *cands):
            f, a = by_name[name]
            for c in cands:
                if c in f.columns:
                    return a[f"f{f.columns.index(c)}"]
            return None

        if "MODE" in by_name:
            tus, mode = col("MODE", "TimeUS"), col("MODE", "Mode", "ModeNum")
            if tus is not None and mode is not None:
                names = MODES.get(self.vehicle or "", {})
                for t, m in zip((tus.astype(np.float64) * 1e-6).tolist(), mode.tolist()):
                    new.append({"t": t, "kind": "mode", "text": names.get(int(m), f"Mode {int(m)}"), "level": "info"})
        if "EV" in by_name:
            tus, ev = col("EV", "TimeUS"), col("EV", "Id")
            if tus is not None and ev is not None:
                for t, e in zip((tus.astype(np.float64) * 1e-6).tolist(), ev.tolist()):
                    new.append({"t": t, "kind": "event", "text": EVENTS.get(int(e), f"Event {int(e)}"), "level": "info"})
        if "ERR" in by_name:
            tus, sub, code = col("ERR", "TimeUS"), col("ERR", "Subsys"), col("ERR", "ECode")
            if tus is not None and sub is not None:
                codes = code.tolist() if code is not None else [None] * len(sub)
                for t, sb, ec in zip((tus.astype(np.float64) * 1e-6).tolist(), sub.tolist(), codes):
                    new.append({"t": t, "kind": "error", "level": "error",
                                "text": f"Error: subsystem {int(sb)}" + (f", code {int(ec)}" if ec is not None else "")
                                        + (" (cleared)" if ec == 0 else "")})
        new.sort(key=lambda e: e["t"])
        self.events.extend(new)

    def log_info(self) -> dict:
        """Parameters and events for the Log panel."""
        params = []
        for nm in sorted(self.param_first):
            t0, v0, d = self.param_first[nm]
            params.append({"name": nm, "value": self.params.get(nm, v0), "first": v0, "default": d,
                           "changes": [[t, v] for t, v in self.param_changes.get(nm, [])]})
        firmware = next((txt for _t, txt in self.texts[:60] if re.match(r"(Ardu\w+|Rover|Blimp|AntennaTracker)\b.*V?\d+\.\d+", txt)), None)
        return {"vehicle": self.vehicle, "firmware": firmware, "params": params, "events": self.events,
                "hasDefaults": any(p["default"] is not None for p in params)}

    # ------------------------------------------------------------------ units
    def _unit(self, f: "MsgFormat", k: int, ch: str) -> Tuple[str, float]:
        """(unit label, extra multiplier) of field k. ArduPilot's rule: value x multiplier = value
        in the unit. c/C/e/E/L already apply their multiplier; plain integers get the power-of-ten
        ones (cm -> m); anything else (floats with a multiplier, odd ones like 3.6) keeps its raw
        value WITHOUT a unit rather than showing a wrong one."""
        uid = f.units[k] if f.units else "-"
        mid = f.mults[k] if f.mults and k < len(f.mults) else "-"
        label = self.unit_label.get(uid, "")
        label = {"deglatitude": "deg", "deglongitude": "deg"}.get(label, label)
        if not label or uid in ("-", "#"):
            return "", 1.0
        if ch in _SCALED or mid in ("-", "?", "0"):
            return label, 1.0
        mult = self.mult_value.get(mid)
        if mult is None or mult == 0:
            return label, 1.0
        if ch in "bBhHiIqQ" and mid in _POW10:
            return label, mult
        return "", 1.0

    # ------------------------------------------------------------------ signals
    def signals(self, dec: Dict[int, np.ndarray]) -> Dict[str, tuple]:
        """{signal name: (time [s], values float64[, {code: text}])} for every field of every timed
        message. Text fields and flight modes carry their texts."""
        out: Dict[str, tuple] = {}
        if self.vehicle is None:
            self.vehicle = vehicle_of(self.texts)
        self.collect_events(dec)
        for t, arr in dec.items():
            f = self.formats[t]
            if f.name in _SKIP_TYPES or not len(arr):
                continue
            hit = next(((c, s) for c, s in _TIME_FIELDS if c in f.columns), None)
            if hit is None:
                continue
            tcol, tscale = hit
            ti = f.columns.index(tcol)
            time = arr[f"f{ti}"].astype(np.float64) * tscale
            inst = f.instance
            if inst is None:            # older logs: an obvious instance column (small integers)
                for nm in _INSTANCE_NAMES:
                    if nm in f.columns:
                        k = f.columns.index(nm)
                        if f.fmt[k] in "bBhH" and len(np.unique(arr[f"f{k}"][:5000])) <= 16:
                            inst = k
                        break
            groups: List[Tuple[Optional[int], Any]] = [(None, slice(None))]
            if inst is not None:
                iv = arr[f"f{inst}"]
                groups = [(int(v), iv == v) for v in np.unique(iv)]
            for ival, sel in groups:
                tt = time[sel]
                order = None
                if len(tt) > 1 and np.any(np.diff(tt) < 0):
                    order = np.argsort(tt, kind="stable")
                    tt = tt[order]
                base = f.name if ival is None else f"{f.name}[{ival}]"
                for k, (ch, col) in enumerate(zip(f.fmt, f.columns)):
                    if k in (ti, inst) or not col or ch == "a":
                        continue
                    name0 = f"{base}.{col}"
                    if ch in "nNZ":                        # text: a state signal with its texts as labels
                        raw_txt = [_cstr(v) for v in arr[f"f{k}"][sel].tolist()]
                        codes, labels = encode_text(raw_txt, self.text_labels.get(name0))
                        if not labels or len(labels) > _MAX_TEXTS:
                            continue
                        self.text_labels[name0] = labels
                        out[name0] = (tt, codes[order] if order is not None else codes, labels)
                        continue
                    y = arr[f"f{k}"][sel].astype(np.float64)
                    fmult = _FMT[ch][1]                  # None only for text, handled above
                    if fmult is not None and fmult != 1.0:
                        y *= fmult
                    unit = ""
                    if f.units and k < len(f.units):
                        unit, mult = self._unit(f, k, ch)
                        if mult != 1.0:
                            y *= mult                      # raw integer in a sub-unit (e.g. cm) -> unit
                    if order is not None:
                        y = y[order]
                    name = name0 + (f" [{unit}]" if unit else "")
                    names: Optional[Dict[int, str]] = None      # numbers that mean a mode / an event
                    if f.name == "MODE" and col in ("Mode", "ModeNum") and self.vehicle in MODES:
                        names = MODES[self.vehicle]
                    elif f.name == "EV" and col == "Id":
                        names = EVENTS
                    out[name] = (tt, y, names) if names else (tt, y)
        return out


def _chain(nxt: np.ndarray, k0: int, sink: int) -> np.ndarray:
    """Indices visited from k0 following nxt until the sink, by pointer doubling:
    P(r+1) = P(r) + J(r)[P(r)],  J(r+1) = J(r)[J(r)]  ->  O(n log n) vectorized, one jump table
    in memory at a time. (Successors always lie after their node, so the work is done on the
    part of the table from k0 on.)"""
    jump = nxt[k0:] - k0
    end = sink - k0
    jump[jump < 0] = end
    seen = np.zeros(len(jump), dtype=bool)
    seen[0] = True
    path = np.array([0], dtype=np.int64)
    while True:
        more = jump[path]
        more = more[more != end]
        if len(more):
            more = more[~seen[more]]
        if not len(more):
            break
        seen[more] = True
        path = np.concatenate([path, more])
        jump = jump[jump]
    return np.sort(path) + k0


# =============================================================================
# Run building
# =============================================================================

def _read(path: str, start: int = 0) -> Tuple[np.ndarray, bytes]:
    with open(path, "rb") as f:
        if start:
            f.seek(start)
        raw = f.read()
    return np.frombuffer(raw, dtype=np.uint8), raw


def load_bin(path: str, display_name: str) -> Tuple[Optional[Run], Dict]:
    """Returns (Run or None, load report)."""
    if not is_dataflash(path):
        raise BinFormatError("This is not an ArduPilot DataFlash log (.bin): it does not start with an FMT message.")
    buf, raw = _read(path)
    df = DataFlash()
    pos, types, end = df.frame(buf, raw, 0)
    dec = df.decode(buf, pos, types)
    sigs = df.signals(dec)
    if not sigs:
        return None, {}
    run = _make_run(path, display_name, sigs)
    run.import_settings = {"format": "bin"}
    run.byte_offset = end
    run._dataflash = df                       # formats / units for live mode
    run._flightlog = df                       # parameters / events for the Log panel
    _remember(run, path)
    report = {"messages": len({n.split(".")[0] for n in sigs}), "vehicle": df.vehicle,
              "params": len(df.params)}
    if df.corrupt_bytes:
        report["corruptBytes"] = int(df.corrupt_bytes)
    report["events"] = len(df.events)
    return run, report


def _make_run(path: str, display_name: str, sigs: Dict[str, tuple]) -> Run:   # (t, y) or (t, y, labels)
    # the Run's own time vector: the longest stream (used only for metadata defaults)
    longest = max(sigs.values(), key=lambda v: len(v[0]))[0]
    run = Run(file_path=path, csv_display_name=display_name, time=longest)
    for name in sorted(sigs, key=_sort_key):
        t, y = sigs[name][:2]
        labels = sigs[name][2] if len(sigs[name]) > 2 else None
        run.signals[name] = Signal(name=name, data=y, time=t, labels=dict(labels) if labels else None)
    _metadata(run)
    return run


def _sort_key(name: str):
    m = re.match(r"([^.\[]+)(?:\[(\d+)\])?\.(.*)", name)
    return (m.group(1), int(m.group(2) or -1), "") if m else (name, -1, "")


def _metadata(run: Run):
    run.compute_metadata()
    times = [t for s in run.signals.values() if (t := getattr(s, "time", None)) is not None and len(t)]
    if times:
        run.start_time = float(min(t[0] for t in times))
        run.end_time = float(max(t[-1] for t in times))
        run.sample_count = int(max(len(t) for t in times))


def _remember(run: Run, path: str):
    st = os.stat(path)
    run.seen_size, run.seen_mtime = st.st_size, st.st_mtime
    with open(path, "rb") as f:                       # bytes just before byte_offset: detects a rewrite
        f.seek(max(0, run.byte_offset - 64))
        run.tail_sig = f.read(min(64, run.byte_offset))


def append_new_messages(run: Run) -> int:
    """Live mode: decode only the bytes written since the last read. Returns the number of new
    samples (0: nothing new, -1: the file was rewritten / shrank -> the caller reloads it)."""
    path = run.file_path
    try:
        st = os.stat(path)
    except OSError:
        return -1
    if st.st_size == run.seen_size and st.st_mtime == run.seen_mtime:
        return 0
    if st.st_size < run.byte_offset:
        return -1
    with open(path, "rb") as f:
        f.seek(max(0, run.byte_offset - 64))
        if f.read(min(64, run.byte_offset)) != run.tail_sig:
            return -1
    df: Optional[DataFlash] = getattr(run, "_dataflash", None)
    if df is None:
        return -1
    if st.st_size - run.byte_offset < 3:
        run.seen_size, run.seen_mtime = st.st_size, st.st_mtime
        return 0
    buf, raw = _read(path, run.byte_offset)
    pos, types, end = df.frame(buf, raw, 0)
    if not len(pos):
        run.seen_size, run.seen_mtime = st.st_size, st.st_mtime
        return 0
    dec = df.decode(buf, pos, types)
    new = df.signals(dec)
    added = 0
    for name, v in new.items():
        t, y = v[:2]
        labels = dict(v[2]) if len(v) > 2 and v[2] else None
        s = run.signals.get(name)
        if s is None:                                # a message type that starts later in the flight
            run.signals[name] = Signal(name=name, data=y, time=t, labels=labels)
        else:
            if labels:
                s.labels = labels
            prev = s.time if s.time is not None else np.empty(0)
            if len(prev) and len(t) and t[0] < prev[-1]:
                return -1                            # time went back (new boot in the same file)
            s.time = np.concatenate([prev, t])
            s.data = np.concatenate([np.asarray(s.data), y])
        added += len(t)
    run.byte_offset += end
    _remember(run, path)
    _metadata(run)
    return added


def bin_signal_names(path: str) -> List[str]:
    """Signal names without decoding all the data (used to check a new run before switching to it)."""
    run, _ = load_bin(path, os.path.basename(path))
    return list(run.signals.keys()) if run else []
