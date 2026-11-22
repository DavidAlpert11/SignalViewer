"""
MSG2 (owner, 2026-11-20): a message structure turns a byte stream into a recording - "define the structure of the
messages, the type of the variables and the messages there are, and the app turns it into a recording's signals;
or the app finds the repeating pattern and proposes a structure (header1, header2, length, checksum if any);
NMEA sentences with commas between the values, the number written as text; LSB / MSB".

A structure (a dict, saved as JSON - `.svmsg.json` - and in the session):

  binary   {"kind": "binary", "name": "...", "header": "AA55",
            "length": {"offset": 2, "add": 5} | null,        # frame length = that byte + add (null: by type / fixed)
            "type": {"offset": 3} | null,                    # the byte that tells the message (null: one message)
            "size": 13 | null,                               # every frame this long (no length byte, one length)
            "checksum": {"scheme": "sum8", "from": 2} | null,  # in the last 1 / 2 bytes (before the footer), over
                                                             # the bytes from `from` up to it
            "footer": "0D0A" | null,                         # fixed end bytes; without a length / size a message
                                                             # ends at its footer
            "messages": [{"id": 32, "name": "SETPOINT", "size": 13 | null, "fields": [
                {"name": "roll_cmd", "offset": 4, "type": "i16", "endian": "le", "scale": 0.01, "add": 0, "unit": "deg"},
                {"name": "armed", "offset": 11, "type": "u8", "bits": [0, 1]},       # bit 0, one bit long
                ...]}]}
  text     {"kind": "text", "name": "NMEA 0183", "start": "$", "sep": ",", "checksum": "nmea" | null,
            "end": "#" | null,                              # a sentence's end (default: the end of its line)
            "messages": [{"id": "GGA", "name": "GGA", "fields": [
                {"name": "time", "index": 1, "type": "hhmmss"},       # seconds of the day
                {"name": "lat", "index": 2, "type": "lat", "hemi": 3}, # ddmm.mmmm + N/S -> degrees
                {"name": "lon", "index": 4, "type": "lon", "hemi": 5},
                {"name": "sats", "index": 7, "type": "number"},
                {"name": "status", "index": 2, "type": "text"}, ...]}]}
           A sentence's id is its first field without the start ("GPGGA"); a message's id matches it whole or
           without the 2-letter talker ("GGA" matches GPGGA, GNGGA).

Field types (binary): u8 i8 u16 i16 u24 i24 u32 i32 u64 i64 f32 f64, ascii (text of "size" bytes - MSG8), endian "le" (LSB first) or "be" (MSB first);
value = raw * scale + add (after `bits`: [first bit, how many]). Text: number, int, text (text values), lat, lon
(ddmm.mmmm / dddmm.mmmm with the hemisphere field), hhmmss (s of the day), ddmmyy (days since 2000-01-01).

Every message counts (CLAUDE.md): a frame with a bad checksum is left out and counted; nothing is sampled.
"""
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from svcore import bytestream as bs

BIN_TYPES = {"u8": ("u", 1), "i8": ("i", 1), "u16": ("u", 2), "i16": ("i", 2), "u24": ("u", 3), "i24": ("i", 3),
             "u32": ("u", 4), "i32": ("i", 4), "u64": ("u", 8), "i64": ("i", 8), "f32": ("f", 4), "f64": ("f", 8)}
TEXT_TYPES = ("number", "int", "text", "lat", "lon", "hhmmss", "ddmmyy")


class ProtocolError(ValueError):
    """A structure that cannot be used - said so the engineer can fix it."""


# ------------------------------------------------------------------------------------------------ NMEA

def _f(name, index, type_="number", unit="", **kw):
    return {"name": name, "index": index, "type": type_, "unit": unit, **kw}


NMEA: Dict[str, Any] = {
    "kind": "text", "name": "NMEA 0183", "start": "$", "sep": ",", "checksum": "nmea",
    "messages": [
        {"id": "GGA", "name": "GGA", "fields": [
            _f("time", 1, "hhmmss", "s"), _f("lat", 2, "lat", "deg", hemi=3), _f("lon", 4, "lon", "deg", hemi=5),
            _f("fix", 6, "int"), _f("sats", 7, "int"), _f("hdop", 8), _f("alt", 9, "number", "m"), _f("geoid", 11, "number", "m")]},
        {"id": "RMC", "name": "RMC", "fields": [
            _f("time", 1, "hhmmss", "s"), _f("status", 2, "text"), _f("lat", 3, "lat", "deg", hemi=4),
            _f("lon", 5, "lon", "deg", hemi=6), _f("speed", 7, "number", "kn"), _f("course", 8, "number", "deg"),
            _f("date", 9, "ddmmyy", "d")]},
        {"id": "VTG", "name": "VTG", "fields": [
            _f("course", 1, "number", "deg"), _f("speed_kn", 5, "number", "kn"), _f("speed_kmh", 7, "number", "km/h")]},
        {"id": "GSA", "name": "GSA", "fields": [_f("mode", 2, "int"), _f("pdop", 15), _f("hdop", 16), _f("vdop", 17)]},
        {"id": "GSV", "name": "GSV", "fields": [_f("in_view", 3, "int")]},
        {"id": "GLL", "name": "GLL", "fields": [_f("lat", 1, "lat", "deg", hemi=2), _f("lon", 3, "lon", "deg", hemi=4),
                                                _f("time", 5, "hhmmss", "s"), _f("status", 6, "text")]},
        {"id": "ZDA", "name": "ZDA", "fields": [_f("time", 1, "hhmmss", "s"), _f("day", 2, "int"), _f("month", 3, "int"), _f("year", 4, "int")]},
    ]}


# ------------------------------------------------------------------------------------------------ checks

def check(proto: Dict) -> Dict:
    """The structure, tidied; anything wrong raises ProtocolError (what and where)."""
    if not isinstance(proto, dict) or proto.get("kind") not in ("binary", "text"):
        raise ProtocolError("A structure has \"kind\": \"binary\" or \"text\".")
    msgs = proto.get("messages")
    if not isinstance(msgs, list) or not msgs:
        raise ProtocolError("The structure has no messages: add at least one, with its fields.")
    names = set()
    for m in msgs:
        nm = str(m.get("name") or m.get("id") or "").strip()
        if not nm:
            raise ProtocolError("A message has no name.")
        if nm in names:
            raise ProtocolError(f"Two messages are named \"{nm}\".")
        names.add(nm)
        seen = set()
        for f in m.get("fields") or []:
            fn = str(f.get("name") or "").strip()
            if not fn:
                raise ProtocolError(f"{nm}: a field has no name.")
            if fn in seen:
                raise ProtocolError(f"{nm}: two fields are named \"{fn}\".")
            seen.add(fn)
            ty = f.get("type", "u8" if proto["kind"] == "binary" else "number")
            if str(f.get("formula") or "").strip():
                from svcore.formula import FormulaError, parse_rows
                try:
                    parse_rows(str(f["formula"]))
                except FormulaError as e:
                    raise ProtocolError(f"{nm}.{fn}: the formula: {e}.") from None
            if proto["kind"] == "binary":
                if ty == "ascii":
                    if not isinstance(f.get("size"), (int, float)) or not 1 <= int(f["size"]) <= 255:
                        raise ProtocolError(f"{nm}.{fn}: an ascii field says how many bytes it is (size 1-255).")
                elif ty not in BIN_TYPES:
                    raise ProtocolError(f"{nm}.{fn}: the type \"{ty}\" is not known (use {', '.join(BIN_TYPES)}, ascii).")
                if not isinstance(f.get("offset"), (int, float)) or f["offset"] < 0:
                    raise ProtocolError(f"{nm}.{fn}: give its offset - the byte it starts at, counted from 0 at the header.")
                if f.get("endian", "le") not in ("le", "be"):
                    raise ProtocolError(f"{nm}.{fn}: endian is \"le\" (LSB first) or \"be\" (MSB first).")
            else:
                if ty not in TEXT_TYPES:
                    raise ProtocolError(f"{nm}.{fn}: the type \"{ty}\" is not known (use {', '.join(TEXT_TYPES)}).")
                if not isinstance(f.get("index"), (int, float)) or f["index"] < 0:
                    raise ProtocolError(f"{nm}.{fn}: give its index - its place after the sentence's name (the name is 0).")
    if proto["kind"] == "binary":
        h = re.sub(r"[^0-9a-fA-F]", "", str(proto.get("header") or ""))
        if len(h) < 2 or len(h) % 2:
            raise ProtocolError("The header is one or more bytes in hex, e.g. AA55.")
        if proto.get("footer") not in (None, ""):
            f_ = re.sub(r"[^0-9a-fA-F]", "", str(proto["footer"]))
            if not f_ or len(f_) % 2:
                raise ProtocolError("The footer is one or more bytes in hex, e.g. 0D0A.")
        if not proto.get("length") and not proto.get("size") and not proto.get("footer") and not all(m.get("size") for m in msgs):
            raise ProtocolError("Say how long a message is: a length byte, one size for all, a size for each message, or a footer it ends with.")
        if len(msgs) > 1 and not proto.get("type"):
            raise ProtocolError("Several messages need the byte that tells them apart (\"type\").")
        cs = proto.get("checksum")
        if cs and cs.get("scheme") not in bs.SCHEMES:
            raise ProtocolError(f"Unknown checksum \"{cs.get('scheme')}\": use one of {', '.join(bs.SCHEMES)}.")
    return proto


# ------------------------------------------------------------------------------------------------ binary

def convert(f: Dict, v: np.ndarray) -> np.ndarray:
    """MSG8 (owner, 2026-11-22: "a variable of several bytes with a conversion formula, as on the other variables"):
    the field's formula on its raw value `x` (e.g. "x*0.01 - 40", "(x - 32) / 1.8", "where(x > 32767, x - 65536, x)")
    - the app's row formulas (svcore.formula's whitelist, no eval); no formula: scale and add."""
    expr = str(f.get("formula") or "").strip()
    if not expr:
        return v * float(f.get("scale", 1) or 1) + float(f.get("add", 0) or 0)
    import pandas as pd
    from svcore.sweep.derived import DerivedError, row_formula
    try:
        out = row_formula(pd.DataFrame({"x": np.asarray(v, dtype=np.float64)}), expr)
    except DerivedError as e:
        raise ProtocolError("%s: %s (x is the field's raw value)." % (f.get("name", "field"), str(e).replace("No column named", "unknown name"))) from None
    if out.dtype == object:
        raise ProtocolError("%s: the formula gives text - it must give a number." % f.get("name", "field"))
    return np.asarray(out, dtype=np.float64)


def field_size(f: Dict) -> int:
    """How many bytes a binary field takes."""
    if f.get("type") == "ascii":
        return int(f.get("size") or 1)
    return BIN_TYPES.get(f.get("type", "u8"), ("u", 1))[1]


def ascii_text(b: bytes) -> str:
    """MSG8: bytes as text - up to the first NUL, the trailing spaces off, a byte that is not a printable character as
    a dot (so the text stays one line and its length shows)."""
    b = b.split(b"\0", 1)[0]
    return "".join(chr(x) if 32 <= x < 127 or x >= 160 else "." for x in b).rstrip()


def ascii_values(raw: np.ndarray, at: np.ndarray, f: Dict) -> Tuple[np.ndarray, Dict[int, str], List[Optional[str]]]:
    """An ascii field of every frame: a code per text (a state, as a text column), the texts by code, and each frame's
    text (None past the stream's end)."""
    off, n = int(f["offset"]), int(f.get("size") or 1)
    data = np.asarray(raw, dtype=np.uint8).tobytes()
    texts: List[Optional[str]] = [ascii_text(data[a + off:a + off + n]) if a + off + n <= len(data) else None for a in at.tolist()]
    code: Dict[str, int] = {}
    for s_ in texts:
        if s_ is not None and s_ not in code:
            code[s_] = len(code)
    v = np.array([code[s_] if s_ is not None else np.nan for s_ in texts], dtype=np.float64)
    return v, {i: s_ for s_, i in code.items()}, texts


def _value(raw: np.ndarray, at: np.ndarray, f: Dict) -> np.ndarray:
    """One field of every frame: raw bytes at `at` (frame starts) + offset, as the field's type says."""
    kind, size = BIN_TYPES[f.get("type", "u8")]
    off = int(f["offset"])
    idx = at[:, None] + off + np.arange(size)[None, :]
    ok = idx[:, -1] < len(raw)
    by = np.zeros((len(at), size), dtype=np.uint8)
    by[ok] = raw[idx[ok]]
    if f.get("endian", "le") == "be":
        by = by[:, ::-1]
    if kind == "f":
        v = by.copy().view("<f4" if size == 4 else "<f8").reshape(-1).astype(np.float64)
    else:
        u = np.zeros(len(at), dtype=np.uint64)
        for k in range(size):
            u |= by[:, k].astype(np.uint64) << np.uint64(8 * k)
        if f.get("bits"):
            lo, n = int(f["bits"][0]), int(f["bits"][1])
            u = (u >> np.uint64(lo)) & np.uint64((1 << n) - 1)
            v = u.astype(np.float64)
        elif kind == "i":
            top = np.uint64(1) << np.uint64(8 * size - 1)
            v = np.where(u >= top, u.astype(np.float64) - float(1 << (8 * size)), u.astype(np.float64))
        else:
            v = u.astype(np.float64)
    v = convert(f, v)
    v[~ok] = np.nan
    return v


def frames_binary(data: bytes, proto: Dict, limit: Optional[int] = None) -> Tuple[List[Tuple[int, int, int, str]], Dict[str, Any]]:
    """The frames by a (checked) binary structure: [(start, length, message id, status)] - status "ok", "bad" (its
    checksum or footer does not match: left out of the recording and counted) or "unknown" (a type the structure has
    no message for) - and the counts. `limit`: stop after that many frames (the guided view's first frames)."""
    h = bytes.fromhex(re.sub(r"[^0-9a-fA-F]", "", str(proto["header"])))
    msgs = proto["messages"]
    toff = (proto.get("type") or {}).get("offset")
    by_id = {int(m["id"]) if toff is not None else 0: m for m in msgs}
    starts = [m.start() for m in re.finditer(re.escape(h), data)] if len(h) else []
    cs = proto.get("checksum")
    ft = bytes.fromhex(re.sub(r"[^0-9a-fA-F]", "", str(proto.get("footer") or "")))
    out: List[Tuple[int, int, int, str]] = []
    report: Dict[str, Any] = {"frames": 0, "bad": 0, "unknown": {}, "outside": 0}
    i, j = 0, 0
    n = len(data)
    while j < len(starts):
        p = starts[j]
        if p < i:
            j += 1
            continue
        if toff is not None:
            if p + toff >= n:
                break
            mid = data[p + toff]
        else:
            mid = 0
        m = by_id.get(mid)
        if proto.get("length"):
            lo = int(proto["length"]["offset"])
            L = data[p + lo] + int(proto["length"].get("add", 0)) if p + lo < n else -1
        elif (m or {}).get("size") or proto.get("size"):
            L = int((m or {}).get("size") or proto.get("size") or -1)
        else:                                             # no length: the message ends at its footer
            e_ = data.find(ft, p + len(h) + 1) if ft else -1
            L = e_ + len(ft) - p if e_ >= 0 else -1
        end = p + L
        good = L >= len(h) + 1 and end <= n
        if good and ft and data[end - len(ft):end] != ft:  # its end is not the footer: a broken frame
            report["bad"] += 1
            good = False
        if good and cs and not bs.checksum_ok(data[p:end - len(ft)], cs["scheme"], int(cs.get("from", 0))):
            nxt_ok = end == n or data[end:end + len(h)] == h
            report["bad"] += 1
            if nxt_ok:                                    # a frame whose end is right: its bytes were hit - skip it
                out.append((p, L, mid, "bad"))
                i = end
                j += 1
                continue
            good = False
        if not good:
            report["outside"] += 1
            j += 1
            continue
        report["frames"] += 1
        if m is None:
            report["unknown"][hex(mid)] = report["unknown"].get(hex(mid), 0) + 1
        out.append((p, L, mid, "ok" if m is not None else "unknown"))
        i = end
        j += 1
        if limit is not None and len(out) >= limit:
            break
    return out, report


def parse_binary(t: np.ndarray, raw: np.ndarray, proto: Dict) -> Dict:
    """The frames by the structure (its header, length / size, type, checksum) -> the fields as signals."""
    proto = check(proto)
    msgs = proto["messages"]
    toff = (proto.get("type") or {}).get("offset")
    by_id = {int(m["id"]) if toff is not None else 0: m for m in msgs}
    found, report = frames_binary(raw.tobytes(), proto)
    frames: Dict[int, List[int]] = {}
    for p, _L, mid, status in found:
        if status == "ok":
            frames.setdefault(mid, []).append(p)
    signals: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    labels: Dict[str, Dict[int, str]] = {}
    counts = {}
    for mid, ps in frames.items():
        m = by_id[mid]
        at = np.asarray(ps, dtype=np.int64)
        tm = t[at]
        name = str(m.get("name") or m.get("id"))
        counts[name] = len(at)
        for f in m.get("fields") or []:
            if f.get("type") == "ascii":                 # MSG8: text in a binary message - a state of its texts
                v, lab, _texts = ascii_values(raw, at, f)
                signals[f"{name}.{f['name']}"] = (tm, v)
                labels[f"{name}.{f['name']}"] = lab
                continue
            signals[f"{name}.{f['name']}"] = (tm, _value(raw, at, f))
            if f.get("labels"):
                labels[f"{name}.{f['name']}"] = {int(a): str(b) for a, b in f["labels"].items()}
    report["messages"] = counts
    seq = [(float(t[p]), str(by_id[mid].get("name") or by_id[mid].get("id")) if status == "ok" else "? 0x%02X" % mid)
           for p, _L, mid, status in found if status != "bad"]
    return {"signals": signals, "labels": labels, "report": report, "units": _units(msgs),
            "sequence": _sequence(seq, [str(m.get("name") or m.get("id")) for m in msgs])}


def _sequence(seq: List[Tuple[float, str]], names: List[str]) -> Tuple[np.ndarray, np.ndarray, Dict[int, str]]:
    """MSG7 (owner, 2026-11-22: "plot which messages passed, in order"): each message's time and which message it was -
    a code per name (the structure's messages first, in its order; types it does not describe after, "? 0x20"), the
    recording's `message` signal. Bad frames (checksum / footer) are not in it."""
    code: Dict[str, int] = {n: i for i, n in enumerate(dict.fromkeys(names))}
    for _t, n in seq:
        code.setdefault(n, len(code))
    order = np.argsort(np.array([x[0] for x in seq], dtype=np.float64), kind="stable") if seq else np.zeros(0, dtype=np.int64)
    tm = np.array([seq[i][0] for i in order], dtype=np.float64)
    y = np.array([code[seq[i][1]] for i in order], dtype=np.float64)
    seen = set(int(v) for v in y)
    return tm, y, {i: n for n, i in code.items() if i in seen}


def _units(msgs) -> Dict[str, str]:
    return {f"{m.get('name') or m.get('id')}.{f['name']}": str(f.get("unit") or "") for m in msgs for f in m.get("fields") or [] if f.get("unit")}


# ------------------------------------------------------------------------------------------------ text

def nmea_ok(line: str) -> Optional[bool]:
    """The `*HH` checksum (XOR of the characters between $ and *): True / False, None when the line has none."""
    if "*" not in line:
        return None
    body, _, hh = line[1:].partition("*")
    x = 0
    for c in body:
        x ^= ord(c)
    try:
        return x == int(hh[:2], 16)
    except ValueError:
        return False


def _num(s: str, ty: str, hemi: str = "") -> float:
    s = s.strip()
    if not s:
        return math.nan
    try:
        if ty in ("lat", "lon"):
            d = 2 if ty == "lat" else 3
            v = float(s[:d]) + float(s[d:]) / 60.0
            return -v if hemi.strip().upper() in ("S", "W") else v
        if ty == "hhmmss":
            return int(s[0:2]) * 3600 + int(s[2:4]) * 60 + float(s[4:])
        if ty == "ddmmyy":
            import datetime as _dt
            return float((_dt.date(2000 + int(s[4:6]), int(s[2:4]), int(s[0:2])) - _dt.date(2000, 1, 1)).days)
        return float(s)
    except (ValueError, IndexError):
        return math.nan


def sentences(text: str, start: str = "$", end: Optional[str] = None) -> List[Tuple[int, str]]:
    """(position, sentence) of each sentence: from a start character to the end of its line (or the next start), or
    to `end` when the structure gives one (the end itself left out)."""
    out = []
    if end:
        for m in re.finditer(re.escape(start) + r"(.*?)" + re.escape(end), text, re.S):
            out.append((m.start(), (start + m.group(1)).strip()))
        return out
    for m in re.finditer(re.escape(start) + r"[^\r\n" + re.escape(start) + r"]*", text):
        out.append((m.start(), m.group(0).strip()))
    return out


def parse_text(text: str, proto: Dict, times: Optional[np.ndarray] = None) -> Dict:
    """Sentences by the structure -> the fields as signals. The time of a sentence: its first character's time in the
    byte stream when there is one (`times`), else its own time field (hhmmss, the last one seen for a sentence that
    has none), else its place in the file."""
    proto = check(proto)
    start, sep = str(proto.get("start") or "$"), str(proto.get("sep") or ",")
    msgs = proto["messages"]
    by_id = {str(m["id"]).upper(): m for m in msgs}
    report: Dict[str, Any] = {"sentences": 0, "bad": 0, "unknown": {}, "noTime": 0}
    rows: Dict[str, List[Tuple[float, List[str]]]] = {}
    seq: List[Tuple[float, str]] = []
    last_t: Optional[float] = None
    day0: Optional[float] = None
    day = 0.0
    for pos, line in sentences(text, start, proto.get("end") or None):
        report["sentences"] += 1
        if proto.get("checksum") == "nmea" and nmea_ok(line) is False:
            report["bad"] += 1
            continue
        body = line[len(start):].split("*")[0]
        parts = body.split(sep)
        sid = parts[0].strip().upper()
        m = by_id.get(sid) or by_id.get(sid[2:])
        if m is None:
            report["unknown"][sid] = report["unknown"].get(sid, 0) + 1
            if times is not None:
                seq.append((float(times[min(pos, len(times) - 1)]), "? " + sid))
            elif last_t is not None:
                seq.append((last_t, "? " + sid))
            continue
        if times is not None:
            tt = float(times[min(pos, len(times) - 1)])
        else:
            own = next((f for f in m.get("fields") or [] if f.get("type") == "hhmmss"), None)
            tod = _num(parts[int(own["index"])], "hhmmss") if own and int(own["index"]) < len(parts) else math.nan
            if not math.isnan(tod):
                if day0 is None:
                    day0 = tod
                if last_t is not None and tod + day - day0 < last_t - 43200:     # past midnight
                    day += 86400.0
                tt = tod + day - day0
                last_t = tt
            elif last_t is not None:
                tt = last_t
            else:
                report["noTime"] += 1
                continue
        rows.setdefault(str(m.get("name") or m["id"]), []).append((tt, parts))
        seq.append((tt, str(m.get("name") or m["id"])))
    signals: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    labels: Dict[str, Dict[int, str]] = {}
    counts = {}
    for m in msgs:
        name = str(m.get("name") or m["id"])
        rs = rows.get(name)
        if not rs:
            continue
        counts[name] = len(rs)
        tm = np.array([r[0] for r in rs], dtype=np.float64)
        for f in m.get("fields") or []:
            ix, ty = int(f["index"]), f.get("type", "number")
            col = [r[1][ix] if ix < len(r[1]) else "" for r in rs]
            key = f"{name}.{f['name']}"
            if ty == "text":
                vals = sorted({c.strip() for c in col if c.strip()})
                code = {v: i for i, v in enumerate(vals)}
                signals[key] = (tm, np.array([code.get(c.strip(), np.nan) for c in col], dtype=np.float64))
                labels[key] = {i: v for v, i in code.items()}
                continue
            hemi = f.get("hemi")
            y = np.array([_num(c, ty, r[1][int(hemi)] if hemi is not None and int(hemi) < len(r[1]) else "")
                          for c, r in zip(col, rs)], dtype=np.float64)
            signals[key] = (tm, convert(f, y))
    report["messages"] = counts
    return {"signals": signals, "labels": labels, "report": report, "units": _units(msgs),
            "sequence": _sequence(seq, [str(m.get("name") or m["id"]) for m in msgs])}


def looks_text(raw: np.ndarray) -> Optional[str]:
    """The start character when the bytes are sentences of printable text (NMEA-like), else None."""
    if not len(raw):
        return None
    s = raw[: 20000]
    printable = np.mean(((s >= 32) & (s < 127)) | (s == 10) | (s == 13))
    if printable < 0.97:
        return None
    text = s.tobytes().decode("ascii", "replace")
    for c in "$!#>":
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if lines and sum(1 for ln in lines if ln.lstrip().startswith(c)) >= 0.8 * len(lines) and text.count(",") >= len(lines):
            return c
    return None


# ------------------------------------------------------------------------------------------------ from a stream

def stream_of(signals: Sequence[Tuple[np.ndarray, np.ndarray]], params: Optional[Dict] = None) -> Tuple[np.ndarray, np.ndarray]:
    params = params or {}
    if params.get("dir") not in (None, ""):
        signals = bs.one_direction(signals, params["dir"])
    return bs.join_stream(signals)


def parse(signals: Sequence[Tuple[np.ndarray, np.ndarray]], proto: Dict, params: Optional[Dict] = None) -> Dict:
    """A byte stream (one signal, columns, or one direction of a signal with a direction column) by a structure."""
    t, raw = stream_of(signals, params)
    out = parse_text(raw.tobytes().decode("latin-1"), proto, t) if proto.get("kind") == "text" else parse_binary(t, raw, proto)
    # MSG7: the messages the user left out of the recording - their values not made, counted (still in `message`)
    skip = {str(x) for x in (params or {}).get("skip") or []}
    if skip:
        out["signals"] = {k: v for k, v in out["signals"].items() if k.split(".", 1)[0] not in skip}
        out["report"]["skipped"] = {k: v for k, v in (out["report"].get("messages") or {}).items() if k in skip}
    return out


# ------------------------------------------------------------------------------------------------ suggesting

def _rough(v: np.ndarray) -> float:
    """How much a value jumps from one message to the next, against its spread (0 = smooth, ~1 = noise)."""
    v = v[np.isfinite(v)]
    if len(v) < 8:
        return 1.0
    spread = float(np.percentile(v, 95) - np.percentile(v, 5))
    if spread <= 0:
        return 0.0 if np.all(v == v[0]) else 1.0
    return float(np.median(np.abs(np.diff(v)))) / spread


def _guess_fields(raw: np.ndarray, at: np.ndarray, first: int, last: int) -> List[Dict]:
    """The payload bytes first..last (inclusive, from the frame's start) as fields, guessed from how they move
    from one message to the next: a 32-bit float, a 32-bit integer (its top bytes only a sign), a 16-bit value LSB or
    MSB first - whichever reads smooth - signed when it crosses zero, a counter, flags, else a byte."""
    out: List[Dict] = []

    def val(f):
        with np.errstate(invalid="ignore", over="ignore"):
            return _value(raw, at, f)

    def u8(j):
        return val({"type": "u8", "offset": j})

    def moves(j):                                       # a byte that takes many values
        return len(np.unique(u8(j))) > 8

    def counter(j):
        v = u8(j)
        return len(v) > 8 and float(np.mean(np.diff(v) % 256 == 1)) > 0.9

    j = first
    while j <= last:
        best: Optional[Dict] = None
        if counter(j):                                  # a sequence number: one byte, +1 each message
            out.append({"name": "counter", "type": "u8", "offset": j})
            j += 1
            continue
        if j + 3 <= last:
            for en in ("le", "be"):
                v = val({"type": "f32", "offset": j, "endian": en})
                big = np.nanmax(np.abs(v)) if np.isfinite(v).all() else np.inf
                if np.isfinite(v).all() and big < 1e7 and len(np.unique(v)) > 3 and _rough(v) < 0.2 \
                        and np.all((v == 0) | (np.abs(v) > 1e-6)):
                    best = {"type": "f32", "offset": j, "endian": en}
                    break
            if best is None:
                for en, lo, hi in (("le", j, j + 3), ("be", j + 3, j)):
                    tops = [u8(j + 2), u8(j + 3)] if en == "le" else [u8(j), u8(j + 1)]
                    # the top two bytes hardly move (a sign, or a large value that changes slowly)
                    still = all(len(np.unique(x)) <= 2 for x in tops) and not all(len(np.unique(x)) == 1 and int(x[0]) not in (0, 255) for x in tops)
                    v = val({"type": "i32", "offset": j, "endian": en})
                    if still and moves(lo) and _rough(v) < 0.05:
                        neg = bool((tops[0 if en == "be" else 1] >= 0x80).any())
                        best = {"type": "i32" if neg or bool((tops[1 if en == "le" else 0] == 255).any()) else "u32", "offset": j, "endian": en}
                        break
        if best is None and j + 1 <= last:
            cands = []
            for en in ("le", "be"):
                lo, hi = (j, j + 1) if en == "le" else (j + 1, j)
                f = {"type": "u16", "offset": j, "endian": en}
                u = val(f)
                # crosses zero (both ends), or sits just below it
                signed = bool(((u >= 0xC000).any() and (u < 0x4000).any()) or (u >= 0xC000).all())
                if signed:
                    f["type"] = "i16"
                cands.append((_rough(val(f)), f, lo, hi))
            # the byte order: the high byte changes less often than the low one (then the smoother reading)
            changes = lambda b: int(np.count_nonzero(np.diff(u8(b))))
            right = [c for c in cands if changes(c[3]) < changes(c[2])] or cands
            r, f, lo, hi = min(right, key=lambda x: x[0])
            # a real 16-bit value: its low byte moves a lot and alone it is not smooth (it wraps); a byte next to a
            # nearly constant one (flags, a status) is two bytes
            wraps = bool(np.any(np.abs(np.diff(u8(lo))) > 128))
            two_bytes = len(np.unique(u8(hi))) <= 3 and _rough(u8(lo)) < 0.05 and not wraps
            if r < 0.05 and moves(lo) and not two_bytes:
                best = f
        if best is None:
            v = u8(j)
            d = np.diff(v) % 256
            uniq = len(np.unique(v))
            name = "b%d" % j
            if len(v) > 8 and np.mean(d == 1) > 0.9:
                name = "counter"
            elif 2 <= uniq <= 4 and np.all(v <= 15):
                name = "flags"
            out.append({"name": name, "type": "u8", "offset": j})
            j += 1
            continue
        best["name"] = "value_%d" % j
        out.append(best)
        j += BIN_TYPES[best["type"]][1]
    names: Dict[str, int] = {}
    for f in out:                                         # unique names (two counters...)
        n = str(f["name"])
        names[n] = names.get(n, 0) + 1
        if names[n] > 1:
            f["name"] = "%s_%d" % (n, names[n])
    return out


def suggest(signals: Sequence[Tuple[np.ndarray, np.ndarray]], params: Optional[Dict] = None) -> Dict:
    """A structure proposed from the stream: NMEA (or any `$…,…*HH` text) when the bytes are sentences, else the
    framing found (header, length, type, checksum) with each message's payload as guessed fields."""
    params = params or {}
    t, raw = stream_of(signals, params)
    start = looks_text(raw)
    if start:
        text = raw.tobytes().decode("latin-1")
        ids: Dict[str, int] = {}
        for _p, line in sentences(text, start):
            sid = line[len(start):].split("*")[0].split(",")[0].strip().upper()
            ids[sid] = ids.get(sid, 0) + 1
        known = {str(m["id"]): m for m in NMEA["messages"]}
        msgs: List[Dict] = []
        for sid, _n in sorted(ids.items(), key=lambda x: -x[1]):
            m = known.get(sid) or known.get(sid[2:])
            if m is not None and all(x["id"] != m["id"] for x in msgs):
                msgs.append(m)
            elif m is None:
                # an unknown sentence: its fields by place, numbers where they read as numbers
                sample = [line for _p, line in sentences(text, start)
                          if line[len(start):].split(",")[0].strip().upper() == sid][:20]
                parts = [s_[len(start):].split("*")[0].split(",") for s_ in sample]
                width = max(len(p) for p in parts)
                fields = []
                for i in range(1, width):
                    col = [p[i] for p in parts if i < len(p) and p[i].strip()]
                    is_num = col and all(re.fullmatch(r"[-+]?\d+(\.\d*)?", c.strip()) for c in col)
                    fields.append(_f("f%d" % i, i, "number" if is_num else "text"))
                msgs.append({"id": sid, "name": sid, "fields": fields})
        has_cs = any(nmea_ok(line) is not None for _p, line in sentences(text[:5000], start))
        return {"kind": "text", "name": "NMEA 0183" if start == "$" else "Text sentences", "start": start, "sep": ",",
                "checksum": "nmea" if has_cs else None, "messages": msgs}
    r = bs.decode(signals, params)
    rule, toff = r["rule"], r["typeOffset"]
    proto: Dict = {"kind": "binary", "name": "Found in the stream", "header": r["header"].replace(" ", ""),
                   "length": {"offset": rule["off"], "add": rule["add"]} if rule["how"] == "length" else None,
                   "type": {"offset": toff} if toff is not None else None,
                   "size": rule["len"] if rule["how"] == "fixed" else None,
                   "checksum": None if not r["checksum"] else {"scheme": r["checksum"]["scheme"],
                                                                "from": 2 if r["checksum"]["over"].startswith("without") else 0},
                   "messages": []}
    k = r["ckLen"]
    m = r["messages"]
    ok = m["ok"]
    # a footer: the same last 1 or 2 bytes in (nearly) every message - then a checksum may sit just before it
    data = r["raw"].tobytes()
    ends = [data[int(p_) + int(L_) - 2: int(p_) + int(L_)] for p_, L_ in zip(m["start"], m["len"])]
    foot = b""
    if not r["checksum"] and len(ends) >= 4:
        for size in (2, 1):
            tails = [e[-size:] for e in ends]
            v, c = max(((x, tails.count(x)) for x in set(tails)), key=lambda z: z[1])
            if c >= 0.95 * len(tails):
                foot = v
                break
    if foot:
        proto["footer"] = foot.hex().upper()
        frames_ = [data[int(p_): int(p_) + int(L_) - len(foot)] for p_, L_ in zip(m["start"], m["len"])][:400]
        best = None
        for scheme in bs.SCHEMES:
            for skip in (2, 0):
                f = float(np.mean([bs.checksum_ok(fr, scheme, skip) for fr in frames_]))
                if f >= 0.8 and (best is None or f > best[2]):
                    best = (scheme, skip, f)
        if best:
            proto["checksum"] = {"scheme": best[0], "from": best[1]}
            k = 1 if best[0] in bs.SCHEMES_1 else 2
        k += len(foot)
    used = [o for o in (rule.get("off") if rule["how"] == "length" else None, toff) if o is not None]
    first = max([1] + used) + 1
    for x in sorted(r["types"], key=lambda x: x["type"]):
        sel = ((m["type"] == x["type"]) if toff is not None else np.ones(len(m["t"]), dtype=bool)) & ok
        L = x["lengths"][0]
        at = m["start"][sel & (m["len"] == L)]
        fields = _guess_fields(r["raw"], at, first, L - k - 1) if len(at) else []
        msg = {"id": x["type"] if toff is not None else 0, "name": "MSG_%02X" % x["type"] if toff is not None else "MSG",
               "fields": fields}
        if rule["how"] == "type":
            msg["size"] = L
        proto["messages"].append(msg)
    return proto


# ------------------------------------------------------------------------------------------------ a recording

def to_run(name: str, file_path: str, out: Dict):
    """The parsed fields as a recording (each field with its message's own times)."""
    from svcore.models import Run, Signal
    sig = out["signals"]
    if not sig:
        rep = out.get("report") or {}
        raise ProtocolError("No message matched the structure (%s)." % ", ".join(
            "%s: %s" % (k, v) for k, v in rep.items() if k in ("frames", "sentences", "bad", "unknown") and v) or "nothing found")
    seq = out.get("sequence")
    alls = np.unique(np.concatenate([t for t, _y in sig.values()] + ([seq[0]] if seq is not None and len(seq[0]) else [])))
    run = Run(file_path=file_path, csv_display_name=name, time=alls)
    if seq is not None and len(seq[0]):                 # MSG7: which message passed when (its name: a state)
        run.signals["message"] = Signal(name="message", data=seq[1], time=seq[0], labels=seq[2])
    for k_, (t, y) in sig.items():
        unit = out.get("units", {}).get(k_)
        nm = f"{k_} [{unit}]" if unit else k_
        run.signals[nm] = Signal(name=nm, data=np.asarray(y, dtype=np.float64), time=np.asarray(t, dtype=np.float64),
                                 labels=out.get("labels", {}).get(k_))
    run.compute_metadata()
    run.load_report = {"messages": out.get("report")}
    return run


def load_nmea(path: str, name: str):
    """A raw NMEA file (.nmea): its sentences by the NMEA structure, the time from their own time fields."""
    with open(path, "rb") as fh:
        text = fh.read().decode("latin-1")
    out = parse_text(text, NMEA)
    return to_run(name, path, out), out["report"]


def from_icd(layout: Dict) -> Dict:
    """An ICD layout (T61, svcore/icd.py - binary files with a time field of their own) as a structure, so the one
    description serves a recorded stream too: the sync -> the header, the id -> the type byte, the payload length ->
    the length byte (frame = header + payload), the packets' fields at their offset after the header; `enum` ->
    labels, `offset_value` -> add. The ICD's own time fields are kept as ordinary fields (a stream has receive times)."""
    h = layout.get("header") or {}
    size = int(h.get("size", 0) or 0)
    sync = str(h.get("sync") or "").replace("0x", "").replace("0X", "")
    big = str(layout.get("byte_order", "little")).lower().startswith("b")
    out: Dict[str, Any] = {"kind": "binary", "name": str(layout.get("name") or "ICD"), "header": sync,
                           "type": {"offset": int(h["id"]["offset"])} if h.get("id") else None,
                           "length": {"offset": int(h["length"]["offset"]), "add": size} if h.get("length") else None,
                           "checksum": None, "messages": []}
    for p in layout.get("packets") or []:
        fields = []
        for f in p.get("fields") or []:
            g: Dict[str, Any] = {"name": f["name"], "offset": int(f.get("offset", 0)) + size, "type": f.get("type", "u8"),
                                 "endian": ("be" if (f.get("byte_order") or ("big" if big else "little")).startswith("b") else "le")}
            for a, b in (("scale", "scale"), ("offset_value", "add"), ("unit", "unit"), ("bits", "bits"), ("enum", "labels")):
                if f.get(a) is not None:
                    g[b] = f[a]
            fields.append(g)
        m: Dict[str, Any] = {"id": int(p.get("id", 0)), "name": str(p.get("name") or p.get("id")), "fields": fields}
        if not h.get("length") and p.get("size"):
            m["size"] = size + int(p["size"])
        out["messages"].append(m)
    return out
