"""T40b: CAN databases (.dbc) and decoding CAN frames into signals - our own code (MIT), so no
LGPL library is needed (ROADMAP T40, option B).

What is read from a .dbc: messages (BO_), their signals (SG_: start bit, length, byte order,
signed, factor, offset, unit, multiplexing M / m<k>), value names (VAL_) and float signals
(SIG_VALTYPE_). Comments, attributes and environment variables are not needed to decode and are
skipped. Extended (29-bit) ids are marked in a .dbc by bit 31 of the id.

Decoding works on all frames of one message id at once (numpy), for classic CAN and CAN FD
payloads up to 64 bytes.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

EXTENDED = 0x80000000

_BO = re.compile(r"^BO_\s+(\d+)\s+(\w+)\s*:\s*(\d+)\s+(\S+)")
_SG = re.compile(r'^SG_\s+(\w+)\s*(M|m\d+M?)?\s*:\s*(\d+)\|(\d+)@([01])([+-])\s*'
                 r'\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)\s*\[\s*([^|]*?)\s*\|\s*([^\]]*?)\s*\]\s*"([^"]*)"')
_VAL = re.compile(r'^VAL_\s+(\d+)\s+(\w+)\s+(.*);\s*$')
_VALTYPE = re.compile(r"^SIG_VALTYPE_\s+(\d+)\s+(\w+)\s*:\s*([0-3])\s*;")
_PAIR = re.compile(r'(-?\d+)\s+"([^"]*)"')


class DbcError(ValueError):
    pass


def parse_dbc(text: str, where: str = "the .dbc") -> Dict[int, Dict[str, Any]]:
    """{frame id (29-bit ids with EXTENDED set, as in the file): {name, dlc, signals: [...]}}."""
    msgs: Dict[int, Dict[str, Any]] = {}
    cur: Optional[Dict[str, Any]] = None
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith("BO_ "):
            m = _BO.match(line)
            if not m:
                raise DbcError(f"{where}, line {no}: a message (BO_) that cannot be read: {line[:80]}")
            cur = {"id": int(m.group(1)), "name": m.group(2), "dlc": int(m.group(3)), "signals": []}
            msgs[cur["id"]] = cur
        elif line.startswith("SG_ "):
            m = _SG.match(line)
            if not m or cur is None:
                raise DbcError(f"{where}, line {no}: a signal (SG_) that cannot be read: {line[:80]}")
            mux = m.group(2) or ""
            try:
                factor, offset = float(m.group(7)), float(m.group(8))
            except ValueError:
                raise DbcError(f"{where}, line {no}: factor / offset are not numbers.") from None
            length = int(m.group(4))
            if not 1 <= length <= 64:
                raise DbcError(f"{where}, line {no}: {m.group(1)} has {length} bits (1 to 64).")
            cur["signals"].append({
                "name": m.group(1), "start": int(m.group(3)), "length": length,
                "intel": m.group(5) == "1", "signed": m.group(6) == "-", "factor": factor, "offset": offset,
                "unit": m.group(11).strip(), "float": None, "labels": None,
                "mux_switch": mux.startswith("M"), "mux": int(mux[1:].rstrip("M")) if mux.startswith("m") else None,
            })
        elif line.startswith("VAL_ "):
            m = _VAL.match(line)
            if m and int(m.group(1)) in msgs:
                for s in msgs[int(m.group(1))]["signals"]:
                    if s["name"] == m.group(2):
                        s["labels"] = {int(k): v for k, v in _PAIR.findall(m.group(3))}
        elif line.startswith("SIG_VALTYPE_ "):
            m = _VALTYPE.match(line)
            if m and int(m.group(1)) in msgs:
                for s in msgs[int(m.group(1))]["signals"]:
                    if s["name"] == m.group(2) and m.group(3) in ("1", "2"):
                        s["float"] = 32 if m.group(3) == "1" else 64
    for msg in msgs.values():                  # VECTOR__INDEPENDENT_SIG_MSG holds unplaced signals
        msg["skip"] = msg["name"] == "VECTOR__INDEPENDENT_SIG_MSG"
    if not any(not m["skip"] for m in msgs.values()):
        raise DbcError(f"{where} has no messages (BO_).")
    return msgs


def frame_key(can_id: int, extended: bool) -> int:
    """The key parse_dbc uses for a frame seen on the bus."""
    return (can_id & 0x1FFFFFFF) | EXTENDED if extended else can_id & 0x7FF


def last_byte(s: Dict[str, Any]) -> int:
    """The last payload byte the signal uses (a shorter frame does not carry it)."""
    if s["intel"]:
        return (s["start"] + s["length"] - 1) // 8
    be = 8 * (s["start"] // 8) + (7 - s["start"] % 8)
    return (be + s["length"] - 1) // 8


def _raw_bits(data: np.ndarray, s: Dict[str, Any]) -> np.ndarray:
    """The signal's raw bits for every frame (data: N x bytes, uint8) as uint64."""
    n, width = data.shape
    length = s["length"]
    if s["intel"]:
        lsb = s["start"]
        b0, b1 = lsb // 8, (lsb + length - 1) // 8
        shift = lsb % 8
        order = range(b1, b0 - 1, -1)                    # most significant byte first
    else:
        be = 8 * (s["start"] // 8) + (7 - s["start"] % 8)  # Motorola: MSB, counted from the first bit sent
        b0, b1 = be // 8, (be + length - 1) // 8
        shift = 7 - (be + length - 1) % 8
        order = range(b0, b1 + 1)
    if b1 >= width:
        return np.full(n, np.nan)                        # the frame is shorter than the signal
    if b1 - b0 + 1 <= 8:
        acc = np.zeros(n, dtype=np.uint64)
        for b in order:
            acc = (acc << np.uint64(8)) | data[:, b].astype(np.uint64)
        acc >>= np.uint64(shift)
        if length < 64:
            acc &= np.uint64((1 << length) - 1)
        return acc
    out = np.empty(n, dtype=np.uint64)                   # 9 bytes (a long, unaligned signal): exact ints
    mask = (1 << length) - 1
    for i in range(n):
        v = 0
        for b in order:
            v = (v << 8) | int(data[i, b])
        out[i] = (v >> shift) & mask
    return out


def decode_signal(data: np.ndarray, s: Dict[str, Any]) -> np.ndarray:
    raw = _raw_bits(data, s)
    if raw.dtype != np.uint64:
        return raw
    if s["float"] == 32 and s["length"] == 32:
        with np.errstate(invalid="ignore"):              # bit patterns that are NaN stay NaN
            v = raw.astype(np.uint32).view(np.float32).astype(np.float64)
    elif s["float"] == 64 and s["length"] == 64:
        v = raw.view(np.float64).copy()
    elif s["signed"]:
        length = s["length"]
        if length == 64:
            v = raw.view(np.int64).astype(np.float64)
        else:
            half = np.uint64(1 << (length - 1))
            v = raw.astype(np.float64) - np.where(raw >= half, float(1 << length), 0.0)
    else:
        v = raw.astype(np.float64)
    if s["labels"]:
        return v                                         # value names go with the raw value
    return v * s["factor"] + s["offset"]


def decode_message(msg: Dict[str, Any], t: np.ndarray, data: np.ndarray,
                   lens: Optional[np.ndarray] = None) -> List[Tuple[str, np.ndarray, np.ndarray, Any]]:
    """[(name, time, values, labels)] for one message's frames (t: N, data: N x bytes, lens: the
    real length of each frame - a signal past it is NaN, not the zero padding)."""
    out = []
    lens = lens if lens is not None else np.full(len(t), data.shape[1])
    switch = next((s for s in msg["signals"] if s["mux_switch"]), None)
    muxv = decode_signal(data, switch) if switch is not None else None
    for s in msg["signals"]:
        tt, dd, ll = t, data, lens
        if s["mux"] is not None and muxv is not None:
            keep = muxv == s["mux"]
            if not keep.any():
                continue
            tt, dd, ll = t[keep], data[keep], lens[keep]
        y = decode_signal(dd, s)
        short = ll <= last_byte(s)
        if short.any():
            y = np.where(short, np.nan, y)
        name = f"{msg['name']}.{s['name']}" + (f" [{s['unit']}]" if s["unit"] else "")
        out.append((name, tt, y, s["labels"]))
    return out
