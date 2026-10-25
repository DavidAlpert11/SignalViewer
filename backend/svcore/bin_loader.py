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
Large logs (a 1-2 GB flight): the file is memory-mapped, not read into RAM; the header search runs
in 64 MB blocks (it used to build several arrays of 8 bytes per FILE byte - ~13 GB for 1.2 GB);
each message type's raw rows are freed as soon as its signals are made; fields that are float32 /
small integers in the log stay float32 in big logs (exactly the same values, half the memory).
Progress and cancel go through csv_loader's per-thread context (the jobs bar).
"""

import hashlib
import json
import os
import pickle
import re
import shutil
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from svcore.models import LazySignal, Run, Signal
from svcore.csv_loader import _progress, encode_text

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
_BLOCK = 1 << 26                     # bytes per block of the header search (64 MB)
_WORKERS = max(1, min(8, (os.cpu_count() or 1)))   # threads for the independent parts of a big read
_MMAP_MIN = 64 << 20                 # files at least this big are memory-mapped, not read into RAM
LAZY_MIN = int(float(os.environ.get("SV_BIN_LAZY_MB", "64")) * (1 << 20))   # bigger logs: values read when used
COMPACT_MIN = LAZY_MIN               # logs at least this big keep exact float32 fields as float32
_EAGER_TYPES = {"FMT", "FMTU", "UNIT", "MULT", "PARM", "FILE", "MSG", "MODE", "EV", "ERR"}   # always read at once
_LOSSLESS32 = set("fbBhHM")          # format chars whose values float32 holds exactly

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



def _gather(buf: np.ndarray, pos: np.ndarray, off: int, dt: str) -> np.ndarray:
    """One field of the messages starting at `pos`: its bytes only, as `dt`."""
    w = np.dtype(dt).itemsize
    pos = pos.astype(np.int64) + off
    if w <= 4:
        # an unaligned 1-byte-stride view of the file as `dt`: numpy gathers the values directly
        # (about twice as fast as copying byte rows for 2- and 4-byte fields - most of a log)
        view = np.ndarray(shape=(len(buf) - w + 1,), dtype=dt, buffer=buf, offset=0, strides=(1,))
        return view[pos]
    win = np.lib.stride_tricks.as_strided(buf, shape=(len(buf) - w + 1, w), strides=(1, 1), writeable=False)
    return np.ascontiguousarray(win[pos]).view(dt).reshape(-1)


class _BinSource:
    """The file a lazy log reads its values from, and how to tell that it is still the same file
    (the bytes just before the end of what was read - like live mode's rewrite check)."""
    def __init__(self, path: str):
        self.path = path
        self.byte_offset = 0
        self.tail_sig: Optional[bytes] = None

    def open(self) -> np.ndarray:
        try:
            with open(self.path, "rb") as f:
                size = f.seek(0, 2)
                if size < self.byte_offset:
                    raise OSError
                f.seek(max(0, self.byte_offset - 64))
                if f.read(min(64, self.byte_offset)) != (self.tail_sig or b""):
                    raise OSError
        except OSError:
            raise ValueError(f"{os.path.basename(self.path)} changed or is gone since it was opened: "
                             "refresh it (F5) to read it again.") from None
        return np.memmap(self.path, dtype=np.uint8, mode="r")


class LazyField:
    """Where one field's values are in the log: read when the signal is first used (big logs).
    Holds the positions of its messages in time order; the values are exactly what an eager read
    gives (same dtype, same multipliers applied the same way)."""
    __slots__ = ("src", "pos", "off", "dt", "out", "fmult", "mult")

    def __init__(self, src: _BinSource, pos: np.ndarray, off: int, dt: str, out, fmult: float, mult: float):
        self.src, self.pos, self.off, self.dt, self.out, self.fmult, self.mult = src, pos, off, dt, out, fmult, mult

    def __len__(self) -> int:
        return len(self.pos)

    @property
    def nbytes(self) -> int:
        return len(self.pos) * np.dtype(self.out).itemsize

    def read(self) -> np.ndarray:
        buf = self.src.open()
        try:
            y = _gather(buf, self.pos, self.off, self.dt).astype(self.out)
        finally:
            del buf                                   # unmapped: the file is not held open
        if self.fmult != 1.0:
            y *= self.fmult
        if self.mult != 1.0:
            y *= self.mult
        return y

    def concat(self, more: "LazyField") -> "LazyField":
        return LazyField(self.src, np.concatenate([self.pos, more.pos]), self.off, self.dt, self.out, self.fmult, self.mult)


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


def _find_heads(buf: np.ndarray, start: int, third: Optional[int] = None, report=None) -> np.ndarray:
    """Positions i >= start of A3 95 (followed by `third` when given), in blocks: a whole-file
    comparison made several full-size temporary arrays (GBs for a big log). The blocks are
    independent and numpy compares without the GIL: several cores work on them at once."""
    n = len(buf)
    blocks = [(i, min(n - 2, i + _BLOCK)) for i in range(start, n - 2, _BLOCK)]

    def scan(b):
        i, j = b
        hit = buf[i:j] == HEAD1
        hit &= buf[i + 1:j + 1] == HEAD2
        if third is not None:
            hit &= buf[i + 2:j + 2] == third
        return np.flatnonzero(hit).astype(np.int64) + i

    parts = []
    workers = min(_WORKERS, len(blocks))
    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(workers, thread_name_prefix="bin") as ex:
            for k, part in enumerate(ex.map(scan, blocks)):       # results in block order
                parts.append(part)
                if report:
                    report((k + 1) / len(blocks))
    else:
        for k, blk in enumerate(blocks):
            parts.append(scan(blk))
            if report:
                report((k + 1) / len(blocks))
    parts = [x for x in parts if len(x)]
    return np.concatenate(parts) if parts else np.empty(0, np.int64)


class MsgFormat:
    __slots__ = ("type", "length", "name", "fmt", "columns", "dtype", "offsets", "units", "mults", "instance")

    def __init__(self, typ: int, length: int, name: str, fmt: str, columns: List[str]):
        self.type, self.length, self.name, self.fmt, self.columns = typ, length, name, fmt, columns
        self.dtype = np.dtype([(f"f{k}", _FMT[ch][0]) for k, ch in enumerate(fmt)])
        self.offsets = [3 + sum(_SIZE[c] for c in fmt[:k]) for k in range(len(fmt))]   # from the header
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
        self.compact = False        # big log: exact float32 fields stay float32 (set by load_bin)
        self.lazy = False           # big log: numeric fields are read when first used (set by load_bin)
        self.src: Optional[_BinSource] = None

    # ------------------------------------------------------------------ framing
    def _lengths(self) -> np.ndarray:
        lut = np.zeros(256, dtype=np.int64)
        for t, f in self.formats.items():
            lut[t] = f.length
        return lut

    def _add_formats(self, buf: np.ndarray, at: np.ndarray):
        """The FMT messages at these positions (validated, so payload bytes that only look like
        one are ignored)."""
        n = len(buf)
        for i in at.tolist():
            if i + FMT_LEN > n:
                break
            f = _parse_fmt_payload(buf[i + 3:i + FMT_LEN].tobytes())
            if f is not None and f.type != FMT_TYPE:
                self.formats[f.type] = f

    def frame(self, buf: np.ndarray, start: int = 0, report=None) -> Tuple[np.ndarray, np.ndarray, int]:
        """Positions and types of the real messages in buf[start:]. Returns (pos, type, end) where
        end is the byte after the last COMPLETE message (a message cut by the end of the file is
        left for the next read). report(fraction): progress of the pass over the bytes."""
        empty = (np.empty(0, np.int64), np.empty(0, np.uint8), start)
        n = len(buf)
        if n - start < 3:
            return empty
        # ONE pass over the bytes finds every header; the FMT messages are among them
        cand = _find_heads(buf, start, None, report)
        if not len(cand):
            return empty
        third = buf[cand + 2]
        self._add_formats(buf, cand[third == FMT_TYPE])
        lut = self._lengths().astype(np.int32)
        ln = lut[third]                                  # 0: not a known type
        del third
        keep = (ln > 0) & (cand + ln <= n)               # (and a message cut by the end waits)
        cand, ln = cand[keep], ln[keep]
        del keep
        m = len(cand)
        if not m:
            return empty
        ends = cand + ln
        del ln
        # Real messages form one chain: each starts where the previous one ends, and the successor
        # of a candidate is the first candidate at or after its end (exactly the next message, or
        # the resynchronisation point after a damaged block). In a real log nearly every candidate
        # IS the next message, so the chain is long runs of consecutive candidates; only the breaks
        # (a header-like pair inside a payload, a damaged block) need a lookup, and the walk goes
        # from run to run - a few thousand steps instead of a walk over every message.
        brk = np.flatnonzero(ends[:-1] != cand[1:])      # k whose successor is not k + 1
        succ = np.searchsorted(cand, ends[brk])          # ... but this one (m: none)
        starts: List[int] = []
        stops: List[int] = []
        k, nb = 0, len(brk)
        while True:
            j = int(np.searchsorted(brk, k))
            r = int(brk[j]) if j < nb else m - 1         # the end of the run k is in
            starts.append(k)
            stops.append(r)
            if j >= nb:
                break
            k = int(succ[j])
            if k >= m:
                break
            if len(starts) > 1_000_000:
                raise BinFormatError("The log is too damaged to read.")
        del brk, succ
        mark = np.zeros(m + 1, dtype=np.int8)
        mark[starts] += 1                                # runs are disjoint and in order
        mark[np.asarray(stops) + 1] -= 1
        on = np.cumsum(mark[:m], dtype=np.int8).astype(bool)
        del mark
        st, sp = np.asarray(starts), np.asarray(stops)
        gaps = cand[st[1:]] - ends[sp[:-1]]              # bytes skipped to resynchronise
        skipped = int(gaps[gaps > 0].sum())
        self.corrupt_bytes += skipped
        if len(gaps) > 10000 and skipped > (n - start) // 2:
            raise BinFormatError("The log is too damaged to read.")
        pos = cand[on]
        end = int(ends[sp[-1]])
        if report:
            report(1.0)
        return pos, buf[pos + 2], end

    # ------------------------------------------------------------------ decode
    def lazy_type(self, f: "MsgFormat") -> bool:
        """Big logs: this message type's numeric fields are read when first used."""
        return self.lazy and f.name not in _EAGER_TYPES and not any(ch in "nNZ" for ch in f.fmt)

    def decode(self, buf: np.ndarray, pos: np.ndarray, types: np.ndarray) -> Dict[int, Any]:
        """{type: structured array of its messages} (in file order); for the lazy types of a big
        log, {type: positions of its messages} instead (nothing of them is copied yet)."""
        out: Dict[int, Any] = {}
        order = np.argsort(types, kind="stable")
        st, pt = types[order], pos[order]
        del order
        bounds = np.flatnonzero(np.diff(st.astype(np.int16))) + 1
        n = len(buf)
        for grp_pos, t in zip(np.split(pt, bounds), st[np.r_[0, bounds]] if len(st) else []):
            f = self.formats.get(int(t))
            if f is None or f.type == FMT_TYPE:
                continue
            width = f.length - 3
            if width <= 0 or n - width + 1 <= 0:
                continue
            if self.lazy_type(f):
                out[int(t)] = grp_pos
                continue
            # a (bytes x width) sliding view of the file: indexing it copies only n x width bytes.
            # Every message here is complete (frame() checked it), so its row lies inside the file.
            win = np.lib.stride_tricks.as_strided(buf, shape=(n - width + 1, width), strides=(1, 1), writeable=False)
            rows = win[grp_pos + 3]                                          # (n, width) uint8
            out[int(t)] = np.ascontiguousarray(rows).view(f.dtype).reshape(-1)
        self._metadata({t: a for t, a in out.items() if a.dtype.names})
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
    def signals(self, dec: Dict[int, Any], report=None, buf: Optional[np.ndarray] = None, base: int = 0) -> Dict[str, tuple]:
        """{signal name: (time [s], values float64[, {code: text}])} for every field of every timed
        message. Text fields and flight modes carry their texts. `dec` is emptied on the way: each
        message type's raw rows are freed once its signals are made (peak memory of big logs)."""
        out: Dict[str, tuple] = {}
        if self.vehicle is None:
            self.vehicle = vehicle_of(self.texts)
        self.collect_events({t: a for t, a in dec.items() if a.dtype.names})
        total = sum(a.nbytes for a in dec.values()) or 1
        done = 0
        lazy_jobs = []
        for t in list(dec):
            arr = dec.pop(t)
            f = self.formats[t]
            if f.name in _SKIP_TYPES or not len(arr):
                continue
            if arr.dtype.names:
                done += arr.nbytes
                self._emit(out, f, lambda k, a=arr: a[f"f{k}"], None, base)
                if report:
                    report(done / total)
            elif buf is not None:                       # lazy type: arr = its positions in buf
                lazy_jobs.append((f, arr))
        # lazy types read only their time / instance columns - independent of each other, and the
        # numpy work releases the GIL: spread over the cores (results merged in type order)
        def one(job):
            f, arr = job
            part: Dict[str, tuple] = {}
            self._emit(part, f, lambda k, p=arr, ff=f: _gather(buf, p, ff.offsets[k], _FMT[ff.fmt[k]][0]), arr, base)
            return part, arr.nbytes
        workers = min(_WORKERS, len(lazy_jobs))
        if workers > 1:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(workers, thread_name_prefix="bin") as ex:
                results = ex.map(one, lazy_jobs)
                for part, nb in results:
                    out.update(part)
                    done += nb
                    if report:
                        report(done / total)
        else:
            for job in lazy_jobs:
                part, nb = one(job)
                out.update(part)
                done += nb
                if report:
                    report(done / total)
        return out

    def _emit(self, out: Dict[str, tuple], f: "MsgFormat", col, pos: Optional[np.ndarray], base: int):
        """The signals of one message type. col(k): field k of all its messages (file order).
        pos: positions of its messages (lazy type: numeric fields become LazyFields)."""
        hit = next(((c, s) for c, s in _TIME_FIELDS if c in f.columns), None)
        if hit is None:
            return
        tcol, tscale = hit
        ti = f.columns.index(tcol)
        time = col(ti).astype(np.float64) * tscale
        inst = f.instance
        if inst is None:            # older logs: an obvious instance column (small integers)
            for nm in _INSTANCE_NAMES:
                if nm in f.columns:
                    k = f.columns.index(nm)
                    if f.fmt[k] in "bBhH" and len(np.unique(col(k)[:5000])) <= 16:
                        inst = k
                    break
        groups: List[Tuple[Optional[int], Any]] = [(None, slice(None))]
        if inst is not None:
            iv = col(inst)
            groups = [(int(v), iv == v) for v in np.unique(iv)]
        cols: Dict[int, np.ndarray] = {}
        for ival, sel in groups:
            tt = time[sel]
            order = None
            if len(tt) > 1 and np.any(np.diff(tt) < 0):
                order = np.argsort(tt, kind="stable")
                tt = tt[order]
            gpos = None
            if pos is not None:                                  # file positions in time order
                gpos = pos[sel] + base
                if order is not None:
                    gpos = gpos[order]
                if len(gpos) and int(gpos[-1 if order is None else gpos.argmax()]) < 2 ** 32 - (1 << 16):
                    gpos = gpos.astype(np.uint32)                # (a log under 4 GB: half the memory)
            gname = f.name if ival is None else f"{f.name}[{ival}]"
            for k, (ch, cname) in enumerate(zip(f.fmt, f.columns)):
                if k in (ti, inst) or not cname or ch == "a":
                    continue
                name0 = f"{gname}.{cname}"
                if ch in "nNZ":                        # text: a state signal with its texts as labels
                    raw_txt = [_cstr(v) for v in col(k)[sel].tolist()]
                    codes, labels = encode_text(raw_txt, self.text_labels.get(name0))
                    if not labels or len(labels) > _MAX_TEXTS:
                        continue
                    self.text_labels[name0] = labels
                    out[name0] = (tt, codes[order] if order is not None else codes, labels)
                    continue
                unit, mult = self._unit(f, k, ch) if (f.units and k < len(f.units)) else ("", 1.0)
                fmult = _FMT[ch][1] or 1.0                 # None only for text, handled above
                # big logs: values float32 holds exactly stay float32 (half the memory)
                otype = np.float32 if self.compact and ch in _LOSSLESS32 and mult == 1.0 else np.float64
                name = name0 + (f" [{unit}]" if unit else "")
                names: Optional[Dict[int, str]] = None      # numbers that mean a mode / an event
                if f.name == "MODE" and cname in ("Mode", "ModeNum") and self.vehicle in MODES:
                    names = MODES[self.vehicle]
                elif f.name == "EV" and cname == "Id":
                    names = EVENTS
                if gpos is not None and names is None and self.src is not None:
                    out[name] = (tt, LazyField(self.src, gpos, f.offsets[k], _FMT[ch][0], otype, fmult, mult))
                    continue
                if k not in cols:
                    cols[k] = col(k)
                y = cols[k][sel].astype(otype)
                if fmult != 1.0:
                    y *= fmult
                if mult != 1.0:
                    y *= mult                      # raw integer in a sub-unit (e.g. cm) -> unit
                if order is not None:
                    y = y[order]
                out[name] = (tt, y, names) if names else (tt, y)



# =============================================================================
# Run building
# =============================================================================

def _read(path: str, start: int = 0) -> np.ndarray:
    """The bytes from `start` on. A big read is memory-mapped: the OS pages it in and out as the
    passes go over it, instead of the whole log sitting in RAM next to what is decoded from it.
    (Live reads - the few bytes appended since the last poll - are plain reads, so the file is not
    kept mapped while the flight controller writes to it.)"""
    size = os.path.getsize(path)
    if size - start >= _MMAP_MIN:
        return np.memmap(path, dtype=np.uint8, mode="r", offset=start)
    with open(path, "rb") as f:
        if start:
            f.seek(start)
        return np.frombuffer(f.read(), dtype=np.uint8)


# ---------------------------------------------------------------------------- index cache
# A big log opened again (every start restores the last session) used to be read from scratch.
# Its index - the time vectors and where each message is in the file, NOT the values - is kept in
# the app's cache folder (the CSV cache's, with its size limits, cleaning and Settings button) and
# memory-mapped when the same file is opened again: near-instant, and almost no RAM until a signal
# is plotted. Used only when size, time stamp and a fingerprint of the bytes all match. Written
# only for a log that is not being written to (live files change every second).
INDEX_VERSION = 1
INDEX_QUIET_S = 60.0


def _index_dir(path: str, st: os.stat_result) -> Optional[str]:
    from svcore import csv_loader as cl
    if not cl.CACHE_ENABLED:
        return None
    fp = cl.content_fingerprint(path, st.st_size)
    raw = json.dumps([INDEX_VERSION, "bin", os.path.abspath(path), st.st_size, st.st_mtime_ns, fp])
    return os.path.join(cl.CACHE_DIR, "bin-" + hashlib.sha1(raw.encode()).hexdigest())


def _index_save(d: str, path: str, df: "DataFlash", sigs: Dict[str, tuple], end: int, report: dict):
    """Arrays shared by several signals (one time vector per message instance) are written once."""
    arrays: List[np.ndarray] = []
    ids: Dict[int, int] = {}

    def ref(a) -> int:
        k = id(a)
        if k not in ids:
            ids[k] = len(arrays)
            arrays.append(a)
        return ids[k]

    entries: List[tuple] = []
    for name, v in sigs.items():
        t, y = v[0], v[1]
        labels = v[2] if len(v) > 2 else None
        if isinstance(y, LazyField):
            entries.append((name, ref(t), "lazy", (ref(y.pos), y.off, y.dt, np.dtype(y.out).str, y.fmult, y.mult), labels))
        else:
            entries.append((name, ref(t), "data", ref(y), labels))
    src, df.src = df.src, None
    try:
        state = pickle.dumps({"df": df, "entries": entries, "end": end, "report": report}, protocol=4)
    finally:
        df.src = src

    def write():
        tmp = d + ".tmp"
        try:
            shutil.rmtree(tmp, ignore_errors=True)
            os.makedirs(tmp)
            for i, a in enumerate(arrays):
                np.save(os.path.join(tmp, f"a{i}.npy"), np.ascontiguousarray(a))
            with open(os.path.join(tmp, "state.pkl"), "wb") as f:
                f.write(state)
            with open(os.path.join(tmp, "meta.json"), "w", encoding="utf-8") as f:
                json.dump({"source": os.path.abspath(path), "kind": "bin-index", "arrays": len(arrays)}, f)
            shutil.rmtree(d, ignore_errors=True)
            os.replace(tmp, d)
            from svcore.csv_loader import prune_cache
            prune_cache(keep=d, source=os.path.abspath(path))
        except Exception as e:                 # a cache only: never fail the open for it
            print(f"[CACHE] Could not write the log index: {e}", flush=True)
            shutil.rmtree(tmp, ignore_errors=True)

    # the arrays are never changed in place (live mode replaces them), so writing them while the
    # user already works is safe - the open does not wait for the disk
    threading.Thread(target=write, daemon=True, name="bin-index").start()


def _index_load(d: str, path: str):
    meta = os.path.join(d, "meta.json")
    if not os.path.isfile(meta):
        return None
    try:
        with open(os.path.join(d, "state.pkl"), "rb") as f:
            state = pickle.load(f)                 # the app's own cache folder, written above
        with open(meta, encoding="utf-8") as f:
            n = json.load(f)["arrays"]
        arrays = [np.load(os.path.join(d, f"a{i}.npy"), mmap_mode="r") for i in range(n)]
        try:
            os.utime(meta)                         # last used (the cache's size limit)
        except OSError:
            pass
    except Exception as e:
        print(f"[CACHE] Damaged log index, reading the log instead: {e}", flush=True)
        shutil.rmtree(d, ignore_errors=True)
        return None
    df: DataFlash = state["df"]
    df.src = _BinSource(path)
    sigs: Dict[str, tuple] = {}
    for name, ti, kind, payload, labels in state["entries"]:
        t = arrays[ti]
        if kind == "lazy":
            pi, off, dt, out, fmult, mult = payload
            y: Any = LazyField(df.src, arrays[pi], off, dt, np.dtype(out), fmult, mult)
        else:
            y = arrays[payload]
        sigs[name] = (t, y, labels) if labels else (t, y)
    return df, sigs, state["end"], state["report"]


def load_bin(path: str, display_name: str) -> Tuple[Optional[Run], Dict]:
    """Returns (Run or None, load report). Reports progress and stops on cancel through
    csv_loader's context (the jobs bar)."""
    if not is_dataflash(path):
        raise BinFormatError("This is not an ArduPilot DataFlash log (.bin): it does not start with an FMT message.")
    st = os.stat(path)
    idx = _index_dir(path, st) if st.st_size >= LAZY_MIN else None
    hit = _index_load(idx, path) if idx else None
    if hit is not None:
        df, sigs, end, report = hit
        run = _make_run(path, display_name, sigs)
        run.import_settings = {"format": "bin"}
        run.byte_offset = end
        run._dataflash = df
        run._flightlog = df
        _remember(run, path)
        report = dict(report, fromCache=True)
        _progress(1.0, "decode")
        return run, report
    buf = _read(path)
    df = DataFlash()
    df.compact = len(buf) >= COMPACT_MIN
    df.lazy = len(buf) >= LAZY_MIN
    df.src = _BinSource(path) if df.lazy else None
    _progress(0.0, "read")
    pos, types, end = df.frame(buf, 0, lambda f: _progress(0.5 * f, "read"))
    dec = df.decode(buf, pos, types)
    del pos, types
    _progress(0.6, "decode")
    sigs = df.signals(dec, lambda f: _progress(0.6 + 0.35 * f, "decode"), buf=buf)
    del buf                                   # the file's bytes (a memory map) are released here
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
    if idx and df.lazy and time.time() - st.st_mtime >= INDEX_QUIET_S:
        _index_save(idx, path, df, sigs, end, report)
    _progress(1.0, "decode")
    return run, report


def _make_run(path: str, display_name: str, sigs: Dict[str, tuple]) -> Run:   # (t, y) or (t, y, labels)
    # the Run's own time vector: the longest stream (used only for metadata defaults)
    longest = max(sigs.values(), key=lambda v: len(v[0]))[0]
    run = Run(file_path=path, csv_display_name=display_name, time=longest)
    for name in sorted(sigs, key=_sort_key):
        t, y = sigs[name][:2]
        labels = sigs[name][2] if len(sigs[name]) > 2 else None
        run.signals[name] = _signal(name, t, y, labels)
    _metadata(run)
    return run


def _signal(name: str, t: np.ndarray, y, labels=None) -> Signal:
    if isinstance(y, LazyField):
        return LazySignal(name, t, y, dict(labels) if labels else None)
    return Signal(name=name, data=y, time=t, labels=dict(labels) if labels else None)


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
    df = getattr(run, "_dataflash", None)
    if df is not None and df.src is not None:         # lazy values: read only from this same file
        df.src.byte_offset, df.src.tail_sig = run.byte_offset, run.tail_sig


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
    buf = _read(path, run.byte_offset)
    pos, types, end = df.frame(buf, 0)
    if not len(pos):
        run.seen_size, run.seen_mtime = st.st_size, st.st_mtime
        return 0
    dec = df.decode(buf, pos, types)
    new = df.signals(dec, buf=buf, base=run.byte_offset)
    del buf
    added = 0
    for name, v in new.items():
        t, y = v[:2]
        labels = dict(v[2]) if len(v) > 2 and v[2] else None
        s = run.signals.get(name)
        if s is None:                                # a message type that starts later in the flight
            run.signals[name] = _signal(name, t, y, labels)
        elif isinstance(y, LazyField):               # big log: positions of the new values
            prev = s.time if s.time is not None else np.empty(0)
            if len(prev) and len(t) and t[0] < prev[-1]:
                return -1
            s.time = np.concatenate([prev, t])
            if isinstance(s, LazySignal):
                s.extend(y)
            else:
                s.data = np.concatenate([np.asarray(s.data), y.read()])
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
