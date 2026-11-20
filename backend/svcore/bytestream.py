"""
MSG1 (owner, 2026-11-19): messages in a byte stream - a serial link, a radio, a bus recorded byte by byte.

"Signals of messages that repeat: header1, header2, sometimes the size or the type, then the details and at the end
sometimes a checksum" - found by itself, every byte counted (CLAUDE.md: no point left out):

  input     one signal holding the stream byte by byte (t, 0..255), or several column signals byte_0..byte_N - one
            message per row, a missing value = no byte - joined row by row into one stream
  header    the 2-byte pair that recurs and frames best (the top pairs by count are tried)
  length    how a frame's length is known - a length byte at offset 2..4 (frame length = byte + a constant, in most
            frames), else the type byte (each type one length), else one fixed length
  type      the byte at offset 2..4 (not the length) with few values (<= 32) that best decides the length
  checksum  the last 1 or 2 bytes: sum8, xor8, -sum8, ~sum8 (over the frame with or without the header), CRC-16
            CCITT-FALSE, CRC-16 Modbus, Fletcher-16 (UBX) - the scheme that matches >= 80 % of the clean frames
  walk      from header to header with the length; a frame that does not end on a header (nor at the end) and fails
            its checksum is a broken frame: the walk resyncs to the next header (counted, its bytes counted as lost)

A link recorded both ways in one signal: the last source is the direction of each byte (a column beside it, e.g.
dir = TX / RX) and `dir` the value whose bytes are decoded - each direction is its own stream.

Everything can be forced (`header`, `length`, `type`, `checksum`). Pure: arrays in, dicts out.
"""
import hashlib
import re
from collections import Counter, OrderedDict
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

MAX_TYPES = 32
SCHEMES_1 = ("sum8", "xor8", "negsum8", "notsum8")
SCHEMES_2 = ("crc16ccitt", "crc16modbus", "fletcher16")
SCHEMES = SCHEMES_1 + SCHEMES_2


class StreamError(ValueError):
    """Not a byte stream, or no message framing in it - said so the engineer knows what to try."""


# ------------------------------------------------------------------------------------------------ the stream

def join_stream(signals: Sequence[Tuple[np.ndarray, np.ndarray]]) -> Tuple[np.ndarray, np.ndarray]:
    """One signal -> its bytes; several (one column per byte) -> row by row, a missing value skipped. Returns (t, b)."""
    if not signals:
        raise StreamError("Choose the signal that holds the bytes (or the byte columns, one message per row).")
    if len(signals) == 1:
        t, y = (np.asarray(a, dtype=np.float64) for a in signals[0])
        ok = np.isfinite(y) & np.isfinite(t)
        t, y = t[ok], y[ok]
    else:
        t0 = np.asarray(signals[0][0], dtype=np.float64)
        cols = []
        for t, y in signals:
            t, y = np.asarray(t, dtype=np.float64), np.asarray(y, dtype=np.float64)
            if len(t) != len(t0) or not np.array_equal(t, t0):
                y = np.interp(t0, t, y, left=np.nan, right=np.nan) if len(t) > 1 else np.full(len(t0), np.nan)
                # a column on other samples: the nearest is not a byte of this row - only exact times count
                y[~np.isin(t0, t)] = np.nan
            cols.append(y)
        m = np.column_stack(cols)                       # rows x columns, in column order
        ok = np.isfinite(m) & np.isfinite(t0)[:, None]
        y = m[ok]                                       # row-major: row by row, column by column
        t = np.broadcast_to(t0[:, None], m.shape)[ok]
    if len(y) < 8:
        raise StreamError("Too few bytes (%d) to find messages in." % len(y))
    if np.any(np.abs(y - np.round(y)) > 1e-6) or y.min() < 0 or y.max() > 255:
        raise StreamError("Not a byte stream: its values are not whole numbers 0..255 (min %g, max %g)." % (y.min(), y.max()))
    return t, np.round(y).astype(np.uint8)


def is_byte_like(y: np.ndarray) -> bool:
    """A quick look before trying (the report's scan): whole numbers 0..255 with at least 8 different values."""
    y = np.asarray(y, dtype=np.float64)
    y = y[np.isfinite(y)]
    if len(y) < 32 or y.min() < 0 or y.max() > 255:
        return False
    s = y[:: max(1, len(y) // 20000)]
    return bool(np.all(np.abs(s - np.round(s)) < 1e-6) and len(np.unique(s)) >= 8)


# ------------------------------------------------------------------------------------------------ checksums

def _crc_table(poly: int, reflected: bool) -> List[int]:
    tab = []
    for i in range(256):
        if reflected:
            c = i
            for _ in range(8):
                c = (c >> 1) ^ poly if c & 1 else c >> 1
        else:
            c = i << 8
            for _ in range(8):
                c = ((c << 1) ^ poly) if c & 0x8000 else c << 1
        tab.append(c & 0xFFFF)
    return tab


_CCITT = _crc_table(0x1021, False)
_MODBUS = _crc_table(0xA001, True)


def crc16_ccitt(data: bytes) -> int:
    c = 0xFFFF
    for x in data:
        c = ((c << 8) & 0xFFFF) ^ _CCITT[((c >> 8) ^ x) & 0xFF]
    return c


def crc16_modbus(data: bytes) -> int:
    c = 0xFFFF
    for x in data:
        c = (c >> 8) ^ _MODBUS[(c ^ x) & 0xFF]
    return c


def fletcher16(data: bytes) -> Tuple[int, int]:
    a = b = 0
    for x in data:
        a = (a + x) & 0xFF
        b = (b + a) & 0xFF
    return a, b


def checksum_ok(frame: bytes, scheme: str, skip: int) -> bool:
    """Does the frame's tail hold `scheme` over frame[skip:-k]? (CRC-16 CCITT big-endian, Modbus little-endian,
    Fletcher-16 as UBX: ck_a then ck_b.)"""
    k = 1 if scheme in SCHEMES_1 else 2
    if len(frame) < skip + k + 1:
        return False
    body, tail = frame[skip:len(frame) - k], frame[len(frame) - k:]
    if scheme == "sum8":
        return sum(body) & 0xFF == tail[0]
    if scheme == "negsum8":
        return (-sum(body)) & 0xFF == tail[0]
    if scheme == "notsum8":
        return (~sum(body)) & 0xFF == tail[0]
    if scheme == "xor8":
        x = 0
        for v in body:
            x ^= v
        return x == tail[0]
    if scheme == "crc16ccitt":
        c = crc16_ccitt(body)
        return tail[0] == c >> 8 and tail[1] == c & 0xFF
    if scheme == "crc16modbus":
        c = crc16_modbus(body)
        return tail[0] == c & 0xFF and tail[1] == c >> 8
    a, b = fletcher16(body)
    return tail[0] == a and tail[1] == b


# ------------------------------------------------------------------------------------------------ framing

def parse_options(params: Dict) -> Dict:
    """`header AA55`, `length 2`, `type 3`, `checksum sum8` (from a report's options or the op's params)."""
    out: Dict = {}
    h = params.get("header")
    if h not in (None, ""):
        s = re.sub(r"[^0-9a-fA-F]", "", str(h).replace("0x", ""))
        if len(s) != 4:
            raise StreamError("A header is two bytes in hex, e.g. AA55 (got \"%s\")." % h)
        out["header"] = (int(s[:2], 16), int(s[2:], 16))
    for k in ("length", "type"):
        v = params.get(k)
        if v not in (None, ""):
            if str(v).lower() in ("none", "no", "-1"):
                out[k] = -1
            else:
                out[k] = int(float(v))
    c = params.get("checksum")
    if c not in (None, ""):
        c = str(c).lower().replace("-", "").replace("_", "")
        if c not in SCHEMES and c not in ("none", "no"):
            raise StreamError("Unknown checksum \"%s\": use one of %s or none." % (params.get("checksum"), ", ".join(SCHEMES)))
        out["checksum"] = None if c in ("none", "no") else c
    return out


def _starts(b: np.ndarray, h: Tuple[int, int]) -> np.ndarray:
    """Every place the header pair starts (overlaps of a repeated byte, AA AA AA, kept apart)."""
    p = np.flatnonzero((b[:-1] == h[0]) & (b[1:] == h[1]))
    if h[0] == h[1] and len(p) > 1:
        keep = [int(p[0])]
        for x in p[1:]:
            if x >= keep[-1] + 2:
                keep.append(int(x))
        p = np.asarray(keep)
    return p


def _mode(a: np.ndarray) -> Tuple[int, float]:
    if not len(a):
        return 0, 0.0
    v, c = np.unique(a, return_counts=True)
    i = int(np.argmax(c))
    return int(v[i]), float(c[i]) / len(a)


def _frame_rule(b: np.ndarray, P: np.ndarray, force: Dict) -> Optional[Dict]:
    """How long the frames are, from the gaps between headers that sit close together (most frames back to back)."""
    if len(P) < 4:
        return None
    d = np.diff(P)
    near = d <= max(8, 3 * int(np.median(d)))           # the gaps around a dropout / junk do not vote
    Pn, dn = P[:-1][near], d[near]
    if len(dn) < 3:
        return None
    best: Optional[Dict] = None
    lo = force.get("length")
    offs = [lo] if lo is not None and lo >= 0 else ([] if lo == -1 else [2, 3, 4])
    for o in offs:
        ok = Pn + o < len(b)
        if ok.sum() < 3:
            continue
        v = b[Pn[ok] + o].astype(int)
        c, f = _mode(dn[ok] - v)
        # a length byte counts the payload (or the frame): the frame is it plus the header / checksum, never less
        if not 2 <= c <= 16 and c != 0:
            continue
        # frames all of one length: any constant byte "fits" - the length byte is the first that fits (nearly) as well
        if f >= 0.7 and (best is None or f > best["fit"] + 0.02):
            best = {"how": "length", "off": o, "add": c, "fit": f}
    if best and best["fit"] >= 0.9:
        return best
    to = force.get("type")
    for o in ([to] if to is not None and to >= 0 else [2, 3, 4]):
        ok = Pn + o < len(b)
        v = b[Pn[ok] + o].astype(int)
        vals = np.unique(v)
        if len(vals) < 2 or len(vals) > MAX_TYPES:
            continue
        lens = {int(x): _mode(dn[ok][v == x])[0] for x in vals}
        f = float(np.mean([dn[ok][i] == lens[int(v[i])] for i in range(len(v))]))
        if f >= 0.7 and (best is None or f > best["fit"] + 0.05):
            best = {"how": "type", "off": o, "lens": lens, "fit": f}
    L, f = _mode(dn)
    if L >= 3 and f >= 0.7 and (best is None or f > best["fit"] + 0.05):
        best = {"how": "fixed", "len": L, "fit": f}
    return best


def _len_at(b: np.ndarray, p: int, rule: Dict) -> int:
    if rule["how"] == "fixed":
        return int(rule["len"])
    if p + rule["off"] >= len(b):
        return -1
    v = int(b[p + rule["off"]])
    if rule["how"] == "length":
        return v + int(rule["add"])
    return int(rule["lens"].get(v, -1))


def _walk(b: np.ndarray, P: np.ndarray, rule: Dict, h: Tuple[int, int], check: Optional[Tuple[str, int]], maxlen: int):
    """From header to header. Returns the frames [(start, length, ok)], resyncs, bytes outside frames."""
    n = len(b)
    raw = b.tobytes()
    frames: List[Tuple[int, int, Optional[bool]]] = []
    resyncs, outside = 0, 0
    j, i = 0, 0                                         # j: the next header index at or after i
    while True:
        while j < len(P) and P[j] < i:
            j += 1
        if j >= len(P):
            outside += n - i
            break
        p = int(P[j])
        outside += p - i
        L = _len_at(b, p, rule)
        end = p + L
        good = 3 <= L <= maxlen and end <= n
        if good:
            on_header = end == n or (end + 1 < n and b[end] == h[0] and b[end + 1] == h[1]) or end + 1 == n
            ok = checksum_ok(raw[p:end], check[0], check[1]) if check else None
            if on_header or ok:
                frames.append((p, L, ok))
                i = end
                continue
        resyncs += 1                                    # a broken frame: its bytes up to the next header are lost
        i = p + 1
        outside += 1
    return frames, resyncs, outside


def _find_checksum(raw: bytes, frames: Sequence[Tuple[int, int]], rule: Dict) -> Optional[Tuple[str, int, float]]:
    """The checksum that matches most of the (clean) frames, >= 80 %; skip = 0 (with the header) or 2 (without)."""
    if len(frames) < 4:
        return None
    sample = frames[:: max(1, len(frames) // 400)]
    best = None
    for scheme in SCHEMES:
        for skip in (2, 0):
            f = float(np.mean([checksum_ok(raw[p:p + L], scheme, skip) for p, L in sample]))
            if f >= 0.8 and (best is None or f > best[2] + 1e-9):
                best = (scheme, skip, f)
    return best


def _type_off(b: np.ndarray, frames, rule: Dict, force: Dict) -> Optional[int]:
    """The type byte: offset 2..4, not the length byte, few values (<= 32), best deciding the length; with one
    length for all, the offset with the most values (still few). None: no type byte."""
    if force.get("type") is not None:
        return None if force["type"] < 0 else int(force["type"])
    if rule["how"] == "type":
        return int(rule["off"])
    st = np.array([p for p, _L, _ok in frames])
    ln = np.array([L for _p, L, _ok in frames])
    if len(st) < 3:
        return None
    best, score = None, (-1.0, 0)
    for o in (2, 3, 4):
        if rule["how"] == "length" and o == rule["off"]:
            continue
        if np.any(ln <= o + 1):                        # inside the frame and before its checksum
            continue
        v = b[st + o].astype(int)
        vals = np.unique(v)
        if len(vals) < 2 or len(vals) > MAX_TYPES:
            continue
        lens = {int(x): _mode(ln[v == x])[0] for x in vals}
        f = float(np.mean(ln == np.array([lens[int(x)] for x in v])))
        if (f, -len(vals)) > score and f >= 0.9:
            best, score = o, (f, -len(vals))
    return best


_CACHE: "OrderedDict[str, Dict]" = OrderedDict()


def one_direction(signals: Sequence[Tuple[np.ndarray, np.ndarray]], value) -> List[Tuple[np.ndarray, np.ndarray]]:
    """The bytes whose direction (the last source, on the same samples) is `value`."""
    if len(signals) < 2:
        raise StreamError("A direction needs two signals: the bytes and the direction of each byte.")
    (td, yd) = (np.asarray(a, dtype=np.float64) for a in signals[-1])
    out = []
    for t, y in signals[:-1]:
        t, y = np.asarray(t, dtype=np.float64), np.asarray(y, dtype=np.float64)
        if len(td) == len(t) and np.array_equal(td, t):
            d = yd
        else:                                           # the direction column's value at each byte's time (held)
            i = np.clip(np.searchsorted(td, t, "right") - 1, 0, len(td) - 1)
            d = yd[i]
        keep = np.isclose(d, float(value))
        if not keep.any():
            raise StreamError("No byte has the direction %s." % value)
        out.append((t[keep], y[keep]))
    return out


def directions(yd: np.ndarray) -> List[float]:
    """The values of a direction column worth splitting on (2..4 of them)."""
    v = np.unique(np.asarray(yd, dtype=np.float64)[np.isfinite(yd)])
    return [float(x) for x in v] if 2 <= len(v) <= 4 else []


def decode(signals: Sequence[Tuple[np.ndarray, np.ndarray]], params: Optional[Dict] = None) -> Dict:
    """The messages in a byte stream and what characterises them. Raises StreamError when there are none."""
    params = params or {}
    if params.get("dir") not in (None, ""):
        signals = one_direction(signals, params["dir"])
    t, b = join_stream(signals)
    key = hashlib.sha1(b.tobytes() + t.tobytes() + repr(sorted((k, str(v)) for k, v in params.items()
                                                             if k in ("header", "length", "type", "checksum", "dir"))).encode()).hexdigest()
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    force = parse_options(params)
    n = len(b)
    raw = b.tobytes()
    if "header" in force:
        cands = [force["header"]]
    else:
        code = b[:-1].astype(np.int64) * 256 + b[1:]
        cnt = np.bincount(code, minlength=65536)
        top = np.argsort(cnt)[::-1][:20]
        cands = [(int(c) >> 8, int(c) & 0xFF) for c in top if cnt[c] >= 4]
    best = None
    for h in cands:
        P = _starts(b, h)
        rule = _frame_rule(b, P, force)
        if not rule:
            continue
        maxlen = 1024 if rule["how"] == "length" else 4 * int(max(rule.get("lens", {}).values() or [rule.get("len", 8)]))
        frames, _r, _o = _walk(b, P, rule, h, None, maxlen)
        covered = sum(L for _p, L, _ok in frames)
        # the pair that frames most of the stream; on a tie (the same frames shifted by a byte) the one whose frames
        # carry a checksum - the true start
        sc = covered / n * rule["fit"]
        if sc >= 0.3:
            cs = _find_checksum(raw, [(p, L) for p, L, _ok in frames], rule)
            sc *= 1 + (cs[2] if cs else 0)
        if best is None or sc > best[0] + 1e-9:
            best = (sc, h, P, rule, maxlen)
    if best is None or best[0] < 0.3:
        raise StreamError("No repeating messages found: no 2-byte header frames the stream (give one: header AA55).")
    _sc, h, P, rule, maxlen = best
    first, _r, _o = _walk(b, P, rule, h, None, maxlen)
    if "checksum" in force:
        cs = force["checksum"]
        check = None
        if cs:
            fs = [(p, L) for p, L, _ok in first]
            f1 = np.mean([checksum_ok(raw[p:p + L], cs, 2) for p, L in fs[:400]]) if fs else 0
            f0 = np.mean([checksum_ok(raw[p:p + L], cs, 0) for p, L in fs[:400]]) if fs else 0
            check = (cs, 2 if f1 >= f0 else 0)
    else:
        found = _find_checksum(raw, [(p, L) for p, L, _ok in first], rule)
        check = (found[0], found[1]) if found else None
    frames, resyncs, outside = _walk(b, P, rule, h, check, maxlen)
    if not frames:
        raise StreamError("No complete message in the stream.")
    toff = _type_off(b, frames, rule, force)
    st = np.array([p for p, _L, _ok in frames], dtype=np.int64)
    ln = np.array([L for _p, L, _ok in frames], dtype=np.int64)
    ok = np.array([True if v is None else v for _p, _L, v in frames], dtype=bool)
    ty = b[st + toff].astype(np.int64) if toff is not None else np.zeros(len(st), dtype=np.int64)
    tm = t[st]
    out = {"bytes": n, "header": "%02X %02X" % h, "framing": _rule_text(rule), "rule": rule,
           "typeOffset": toff, "checksum": None if not check else {"scheme": check[0], "over": "without the header" if check[1] else "with the header"},
           "messages": {"t": tm, "type": ty, "len": ln, "ok": ok, "start": st},
           "count": int(len(st)), "errors": int((~ok).sum()) if check else 0, "resyncs": int(resyncs), "outside": int(outside),
           "inFrames": int(ln.sum()), "raw": b,
           "ckLen": 0 if not check else (1 if check[0] in SCHEMES_1 else 2)}
    out.update(characterise(tm, ty, ln, ok, bool(check)))
    _CACHE[key] = out
    while len(_CACHE) > 8:
        _CACHE.popitem(last=False)
    return out


def _rule_text(rule: Dict) -> str:
    if rule["how"] == "length":
        return "length byte at offset %d (frame = byte %s %d)" % (rule["off"], "+" if rule["add"] >= 0 else "−", abs(rule["add"]))
    if rule["how"] == "type":
        return "each type has its own length (type byte at offset %d)" % rule["off"]
    return "fixed length %d bytes" % rule["len"]


def characterise(tm: np.ndarray, ty: np.ndarray, ln: np.ndarray, ok: np.ndarray, checked: bool) -> Dict:
    """Per type: count, share, lengths, rate, period and jitter, first / last, checksum errors; the order (the
    repeating sequence, else the commonest transitions); the largest gaps between messages."""
    n = len(tm)
    types: List[Dict] = []
    for v in np.unique(ty):
        m = ty == v
        tt = tm[m]
        d = np.diff(tt)
        span = float(tt[-1] - tt[0]) if len(tt) > 1 else 0.0
        types.append({"type": int(v), "count": int(m.sum()), "share": float(m.sum()) / n,
                      "lengths": sorted(int(x) for x in np.unique(ln[m])),
                      "rate": (len(tt) - 1) / span if span > 0 else None,
                      "period": float(np.median(d)) if len(d) else None, "jitter": float(np.std(d)) if len(d) > 1 else None,
                      "maxInterval": float(d.max()) if len(d) else None,
                      "first": float(tt[0]), "last": float(tt[-1]), "errors": int((~ok[m]).sum()) if checked else 0})
    types.sort(key=lambda x: -int(x["count"]))
    order: Dict = {"period": None, "sequence": [], "fit": None, "transitions": []}
    if len(np.unique(ty)) > 1 and n >= 4:
        for p in range(1, min(400, n // 2) + 1):
            f = float(np.mean(ty[p:] == ty[:-p]))
            if f >= 0.9:
                order.update(period=p, sequence=[int(x) for x in ty[:p]], fit=f)
                break
        tr = Counter(zip(ty[:-1].tolist(), ty[1:].tolist()))
        order["transitions"] = [{"from": int(a), "to": int(c), "count": int(k)} for (a, c), k in tr.most_common(8)]
    gaps = []
    if n > 2:
        d = np.diff(tm)
        med = float(np.median(d))
        for i in np.argsort(d)[::-1][:5]:
            if med > 0 and d[i] > 5 * med:
                gaps.append({"from": float(tm[i]), "to": float(tm[i + 1]), "dt": float(d[i])})
        gaps.sort(key=lambda g: g["from"])
    return {"types": types, "order": order, "gaps": gaps,
            "duration": float(tm[-1] - tm[0]) if n > 1 else 0.0}


# ------------------------------------------------------------------------------------------------ as signals

WHATS = ("type", "length", "ok", "interval", "count", "latency")


def messages_signal(signals: Sequence[Tuple[np.ndarray, np.ndarray]], params: Dict) -> Tuple[np.ndarray, np.ndarray]:
    """The derived operation `messages`: one quantity at the messages' times (their first byte's).
    type / length / ok (1 = checksum good) / interval (s since the last message of the same type) / count (so far)."""
    what = params.get("what", "type")
    if what not in WHATS:
        raise StreamError("Unknown message quantity \"%s\": use one of %s." % (what, ", ".join(WHATS)))
    if what == "latency":
        return latency_signal(signals, params)
    r = decode(signals, params)
    m = r["messages"]
    t = np.asarray(m["t"], dtype=np.float64)
    if what == "type":
        y = m["type"].astype(np.float64)
    elif what == "length":
        y = m["len"].astype(np.float64)
    elif what == "ok":
        y = m["ok"].astype(np.float64)
    elif what == "count":
        y = np.arange(1, len(t) + 1, dtype=np.float64)
    else:
        y = np.full(len(t), np.nan)
        for v in np.unique(m["type"]):
            idx = np.flatnonzero(m["type"] == v)
            y[idx[1:]] = np.diff(t[idx])
    return t, y


def link_sides(signals: Sequence[Tuple[np.ndarray, np.ndarray]], params: Dict) -> Tuple[Dict, Dict]:
    """The two directions of a link: one signal + its direction column (params dir = TX's code, rxdir = RX's), or two
    signals, TX then RX (params link)."""
    keep = {k: params[k] for k in ("header", "checksum") if params.get(k)}
    if params.get("rxdir") not in (None, ""):
        return decode(signals, {**keep, "dir": params["dir"]}), decode(signals, {**keep, "dir": params["rxdir"]})
    if len(signals) != 2:
        raise StreamError("A reply's latency needs both directions: the TX and the RX signal, or the bytes and their direction.")
    return decode([signals[0]], keep), decode([signals[1]], keep)


def latency_signal(signals: Sequence[Tuple[np.ndarray, np.ndarray]], params: Dict) -> Tuple[np.ndarray, np.ndarray]:
    """Each answered request's reply latency (s), at the request's time - every pair type in one signal."""
    a, b = link_sides(signals, params)
    e = exchange(a, b)
    t = np.array([x for p_ in e["pairs"] for x in p_["t"]], dtype=np.float64)
    y = np.array([x for p_ in e["pairs"] for x in p_["lat"]], dtype=np.float64)
    if not len(t):
        raise StreamError("No message here answers another (no request / reply pairs found between the two directions).")
    o = np.argsort(t, kind="stable")
    return t[o], y[o]


def messages_name(n: List[str], p: Dict) -> str:
    src = n[0] if len(n) == 1 else "%s…%s" % (n[0], n[-1]) if n else "?"
    return "%s(%s)" % ({"type": "msg_type", "length": "msg_len", "ok": "msg_ok", "interval": "msg_interval",
                        "count": "msg_count", "latency": "reply_latency"}.get(str(p.get("what")), "messages"), src)


# ------------------------------------------------------------------------------------------------ both ways

def _payload(r: Dict, i: int) -> np.ndarray:
    """Message i's bytes after the header and its length / type bytes, before the checksum."""
    m = r["messages"]
    st, L = int(m["start"][i]), int(m["len"][i])
    first = 2 + sum(1 for o in (r["rule"].get("off") if r["rule"]["how"] == "length" else None, r["typeOffset"]) if o is not None)
    return r["raw"][st + first: st + L - r["ckLen"]]


def _echo(ra: Dict, ia: np.ndarray, rb: Dict, ib: np.ndarray) -> Optional[Tuple[int, int, float]]:
    """A byte of the request echoed in its reply (a sequence number, an id): (offset in the request's payload,
    offset in the reply's, share of the pairs it holds for) when >= 80 %."""
    if len(ia) < 2:
        return None
    pa = [_payload(ra, int(i)) for i in ia]
    pb = [_payload(rb, int(j)) for j in ib]
    na, nb = min(len(x) for x in pa), min(len(x) for x in pb)
    best = None
    for j in range(min(na, 8)):
        # an id / a sequence number takes many values - a byte that hardly moves (the high byte of a slow value,
        # a constant) matches by itself
        if len({int(x[j]) for x in pa}) < min(16, max(1, len(pa) // 2)):
            continue
        for k in range(min(nb, 8)):
            f = float(np.mean([x[j] == y[k] for x, y in zip(pa, pb)]))
            if f >= 0.8 and (best is None or f > best[2]):
                best = (j, k, f)
    return best


def exchange(ra: Dict, rb: Dict, names: Tuple[str, str] = ("TX", "RX"), timeout: float = 0.5) -> Dict:
    """Two directions of one link: which message answers which (owner, 2026-11-19: "a handshake, answers, reply
    packets"), how fast, what went unanswered, retries; the handshake and where it repeats.

    A reply type y (in the other direction) answers a request type x when the messages of x are mostly (>= 50 %)
    followed by a y within `timeout`, about as many (0.5..1.5 per request), and either a byte of the request comes
    back in the reply (a sequence number / id, >= 80 %) - then each request is paired with the reply that echoes it -
    or x is rare (<= 10 messages, a handshake's) and always answered. Streaming types (sent on their own clock) have
    no reply."""
    sides = [(ra, rb, names[0], names[1]), (rb, ra, names[1], names[0])]
    pairs: List[Dict] = []
    for A, B, na, nb in sides:
        # a type that answers in one direction is not a request in the other (and the reverse)
        replies = {(p_["to"], p_["reply"]) for p_ in pairs}
        requests = {(p_["from"], p_["request"]) for p_ in pairs}
        ta, tb = A["messages"]["t"], B["messages"]["t"]
        tya, tyb = A["messages"]["type"], B["messages"]["type"]
        if A["typeOffset"] is None or B["typeOffset"] is None:
            continue
        used_y: set = set()
        for x in sorted(np.unique(tya).tolist(), key=lambda v: int((tya == v).sum())):
            if (na, x) in replies:
                continue
            ia = np.flatnonzero(tya == x)
            best = None
            for y in np.unique(tyb).tolist():
                if y in used_y or (nb, y) in requests:
                    continue
                iy = np.flatnonzero(tyb == y)
                ratio = len(iy) / len(ia)
                if not 0.5 <= ratio <= 1.5:
                    continue
                k = np.searchsorted(tb[iy], ta[ia], "right")
                has = k < len(iy)
                lat = np.full(len(ia), np.inf)
                lat[has] = tb[iy[k[has]]] - ta[ia][has]
                got = lat <= timeout
                frac = float(got.mean())
                if frac < 0.5:
                    continue
                echo = _echo(A, ia[got], B, iy[k[got]])
                rare = len(ia) <= 10 and frac == 1.0
                if not echo and not rare:
                    continue
                score = (round(echo[2], 2) if echo else 0, frac, -float(np.median(lat[got])))
                if best is None or score > best[0]:
                    best = (score, y, echo)
            if best:
                used_y.add(best[1])
                pairs.append(_pair(A, B, na, nb, int(x), int(best[1]), best[2], timeout))
    out: Dict = {"pairs": pairs, "timeout": timeout}
    out.update(_sessions(ra, rb, names, pairs))
    return out


def _pair(A: Dict, B: Dict, na: str, nb: str, x: int, y: int, echo, timeout: float) -> Dict:
    ta, tb = A["messages"]["t"], B["messages"]["t"]
    ia = np.flatnonzero(A["messages"]["type"] == x)
    iy = np.flatnonzero(B["messages"]["type"] == y)
    ida = [int(_payload(A, int(i))[echo[0]]) if echo else None for i in ia]
    idy = [int(_payload(B, int(j))[echo[1]]) if echo else None for j in iy]
    taken = np.zeros(len(iy), dtype=bool)
    lat: List[float] = []
    at: List[float] = []
    unanswered: List[float] = []
    retries: List[float] = []
    waiting: Dict = {}                                   # id -> time of the last request still unanswered
    retried: List[float] = []
    for n, i in enumerate(ia):
        t = float(ta[i])
        key = ida[n] if echo else None
        if echo and key in waiting and t - waiting[key] <= 2 * timeout:
            retries.append(t)
            retried.append(waiting.pop(key))
        # the same request sent again before an answer came: the answer is the later copy's
        again = echo and any(ida[m] == key and float(ta[ia[m]]) - t <= timeout for m in range(n + 1, min(n + 4, len(ia))))
        k0 = int(np.searchsorted(tb[iy], t, "right"))
        hit = None
        for k in range(k0, len(iy)):
            if tb[iy[k]] - t > timeout:
                break
            if not taken[k] and (not echo or idy[k] == key):
                hit = k
                break
        if hit is not None and again:
            nxt = min(float(ta[ia[m]]) for m in range(n + 1, min(n + 4, len(ia))) if ida[m] == key)
            if tb[iy[hit]] > nxt:
                hit = None
        if hit is None:
            unanswered.append(t)
            if echo:
                waiting[key] = t
            continue
        taken[hit] = True
        waiting.pop(key, None)
        lat.append(float(tb[iy[hit]]) - t)
        at.append(t)
    la = np.asarray(lat)
    return {"from": na, "to": nb, "request": x, "reply": y, "requests": int(len(ia)), "replies": int(len(la)),
            "how": ("id" if echo else "next"), "echo": None if not echo else {"request": echo[0], "reply": echo[1]},
            "unanswered": [u for u in unanswered if u not in retried], "retried": retried, "retries": retries,
            "orphans": [float(tb[iy[k]]) for k in range(len(iy)) if not taken[k]],
            "latency": None if not len(la) else {"mean": float(la.mean()), "p95": float(np.percentile(la, 95)),
                                                 "max": float(la.max()), "tmax": at[int(np.argmax(la))], "min": float(la.min())},
            "t": at, "lat": lat}


def _sessions(ra: Dict, rb: Dict, names: Tuple[str, str], pairs: List[Dict]) -> Dict:
    """The handshake: the rare messages of both directions (<= 10 each, not the steady traffic) in time order,
    grouped where they come close together; the first group opens the link, a later one is a reconnect."""
    ev = []
    for r, nm in ((ra, names[0]), (rb, names[1])):
        if r["typeOffset"] is None:
            continue
        for x in r["types"]:
            if x["count"] <= 10:
                m = r["messages"]["type"] == x["type"]
                ev += [(float(t), nm, int(x["type"])) for t in r["messages"]["t"][m]]
    ev.sort()
    groups: List[List] = []
    for e in ev:
        if groups and e[0] - groups[-1][-1][0] <= 1.0:
            groups[-1].append(e)
        else:
            groups.append([e])
    groups = [g for g in groups if len(g) >= 2]
    return {"handshake": [{"t": g[0][0], "steps": [{"dir": d, "type": ty, "t": t} for t, d, ty in g]} for g in groups]}

