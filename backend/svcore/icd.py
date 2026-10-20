"""T61: raw binary recordings described by a layout (an ICD - interface control document).

Many benches and test rigs record their packets as they come off the wire: a header (sync word,
packet id, length, maybe a time stamp) and a payload of fixed fields. A layout file says where
everything is; this module turns such a recording into signals named "<packet>.<field> [unit]".

A layout is a `<name>.icd.json` (or `.icd.yaml` when PyYAML is installed) file in the readers
folder (T60), so it works like any reader: the file dialog, drag & drop, Python, the command line.

    {
      "name": "Bench telemetry",
      "extensions": [".tlm"],
      "byte_order": "little",                        # or "big"; a field can override it
      "header": {
        "sync": "0xA55A",                            # bytes at the start of every packet (optional)
        "size": 8,                                   # header bytes before the payload
        "id": {"offset": 2, "type": "u8"},           # which packet this is (optional: one packet type)
        "length": {"offset": 3, "type": "u8"},       # payload bytes (optional: the packet's "size")
        "time": {"offset": 4, "type": "u32", "scale": 1e-6}   # optional; else a packet's "time" field
      },
      "packets": [
        {"id": 1, "name": "NAV", "size": 12, "time": "t_us", "time_scale": 1e-6,
         "fields": [
           {"name": "t_us", "offset": 0, "type": "u32"},
           {"name": "lat", "offset": 4, "type": "i32", "scale": 1e-7, "unit": "deg"},
           {"name": "mode", "offset": 8, "type": "u8", "enum": {"0": "IDLE", "1": "RUN"}},
           {"name": "armed", "offset": 9, "type": "u8", "bits": [0, 1]},   # [first bit, number of bits]
           {"name": "temp", "offset": 10, "type": "i16", "scale": 0.1, "offset_value": -40, "unit": "degC"}
         ]}
      ]
    }

Types: u8 i8 u16 i16 u32 i32 u64 i64 f32 f64. value = raw * scale + offset_value.
Without any time, a packet's samples are numbered (0, 1, 2 ...) and the report says so.
Damaged stretches (a wrong sync, an unknown id, a length that runs past the end) are skipped
byte by byte to the next sync and counted in the load report, never fatal.
"""
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

TYPES = {"u8": "u1", "i8": "i1", "u16": "u2", "i16": "i2", "u32": "u4", "i32": "i4",
         "u64": "u8", "i64": "i8", "f32": "f4", "f64": "f8"}


class LayoutError(ValueError):
    """The layout file itself is wrong (what and where is in the message)."""


def _int(v: Any, what: str) -> int:
    try:
        return int(v, 0) if isinstance(v, str) else int(v)
    except (TypeError, ValueError):
        raise LayoutError(f"{what} must be a whole number, not {v!r}.") from None


def _sync(v: Any, where: str) -> bytes:
    if v is None:
        return b""
    if isinstance(v, list):
        return bytes(_int(x, f"{where} sync byte") & 0xFF for x in v)
    s = str(v).strip().lower()
    s = s[2:] if s.startswith("0x") else s
    try:
        return bytes.fromhex(s if len(s) % 2 == 0 else "0" + s)
    except ValueError:
        raise LayoutError(f"{where}: sync must be hex such as \"0xA55A\" or a list of bytes.") from None


def _slot(d: Any, where: str, order: str) -> Optional[Dict[str, Any]]:
    """A header item / field: {offset, type, order, scale, add}."""
    if d is None:
        return None
    if not isinstance(d, dict) or "offset" not in d or "type" not in d:
        raise LayoutError(f"{where} needs \"offset\" and \"type\".")
    t = str(d["type"]).lower()
    if t not in TYPES:
        raise LayoutError(f"{where}: unknown type {d['type']!r} (use {' '.join(TYPES)}).")
    bo = str(d.get("byte_order", order)).lower()
    if bo not in ("little", "big"):
        raise LayoutError(f"{where}: byte_order must be \"little\" or \"big\".")
    return {"offset": _int(d["offset"], f"{where} offset"), "type": t, "size": int(TYPES[t][1]), "order": bo,
            "dtype": np.dtype(("<" if bo == "little" else ">") + TYPES[t]),
            "scale": float(d.get("scale", 1.0)), "add": float(d.get("offset_value", 0.0))}


def parse_layout(d: Dict[str, Any], where: str = "layout") -> Dict[str, Any]:
    """Check a layout and put it in the form decode() uses. Raises LayoutError naming the item."""
    if not isinstance(d, dict):
        raise LayoutError(f"{where}: expected an object with \"packets\".")
    order = str(d.get("byte_order", "little")).lower()
    if order not in ("little", "big"):
        raise LayoutError(f"{where}: byte_order must be \"little\" or \"big\".")
    h = d.get("header") or {}
    hsize = _int(h.get("size", 0), f"{where} header size")
    header: Dict[str, Any] = {"sync": _sync(h.get("sync"), f"{where} header"), "size": hsize,
              "id": _slot(h.get("id"), f"{where} header id", order),
              "length": _slot(h.get("length"), f"{where} header length", order),
              "length_includes_header": bool(h.get("length_includes_header", False)),
              "time": _slot(h.get("time"), f"{where} header time", order)}
    for k in ("id", "length"):
        if header[k] and header[k]["type"].startswith("f"):
            raise LayoutError(f"{where}: header {k} must be an integer type.")
    for k in ("id", "length", "time"):
        s = header[k]
        if s and s["offset"] + s["size"] > hsize:
            raise LayoutError(f"{where}: header {k} (offset {s['offset']}, {s['type']}) does not fit in a "
                              f"{hsize}-byte header.")
    if header["sync"] and len(header["sync"]) > hsize:
        raise LayoutError(f"{where}: the sync is longer than the header.")
    pk = d.get("packets")
    if not isinstance(pk, list) or not pk:
        raise LayoutError(f"{where}: \"packets\" must list at least one packet.")
    packets: Dict[int, Dict[str, Any]] = {}
    for i, p in enumerate(pk, 1):
        pw = f"{where} packet {p.get('name') or i}"
        if not isinstance(p, dict) or not p.get("name"):
            raise LayoutError(f"{where} packet {i} has no \"name\".")
        pid = _int(p.get("id", 0), f"{pw} id")
        if header["id"] is None and len(pk) > 1:
            raise LayoutError(f"{where}: several packets need an \"id\" in the header.")
        if pid in packets:
            raise LayoutError(f"{pw}: id {pid} is used twice.")
        fields = []
        names = set()
        for j, f in enumerate(p.get("fields") or [], 1):
            fw = f"{pw} field {f.get('name') or j}"
            s = _slot(f, fw, order)
            assert s is not None
            name = str(f.get("name") or "")
            if not name or name in names:
                raise LayoutError(f"{fw}: every field needs a name of its own.")
            names.add(name)
            bits = f.get("bits")
            if bits is not None:
                if not (isinstance(bits, list) and len(bits) == 2):
                    raise LayoutError(f"{fw}: bits must be [first bit, number of bits].")
                b0, nb = _int(bits[0], f"{fw} bits"), _int(bits[1], f"{fw} bits")
                if s["type"].startswith("f") or b0 < 0 or nb < 1 or b0 + nb > 8 * s["size"]:
                    raise LayoutError(f"{fw}: bits {bits} do not fit in a {s['type']}.")
                s["bits"] = (b0, nb)
            enum = f.get("enum")
            s.update(name=name, unit=str(f.get("unit") or ""),
                     labels={_int(k, f"{fw} enum key"): str(v) for k, v in enum.items()} if isinstance(enum, dict) else None)
            fields.append(s)
        if not fields:
            raise LayoutError(f"{pw} has no fields.")
        size = _int(p["size"], f"{pw} size") if p.get("size") is not None else max(x["offset"] + x["size"] for x in fields)
        for x in fields:
            if x["offset"] + x["size"] > size:
                raise LayoutError(f"{pw} field {x['name']}: offset {x['offset']} + {x['size']} bytes is past the "
                                  f"packet's {size} bytes.")
        tname = p.get("time")
        if tname is not None and tname not in names:
            raise LayoutError(f"{pw}: its time field {tname!r} is not one of its fields.")
        packets[pid] = {"id": pid, "name": str(p["name"]), "size": size, "fields": fields,
                        "time": tname, "time_scale": float(p.get("time_scale", 1.0))}
    exts = d.get("extensions") or []
    exts = [exts] if isinstance(exts, str) else exts
    return {"name": str(d.get("name") or where), "extensions": sorted({("." + str(e).lstrip(".")).lower() for e in exts}),
            "header": header, "packets": packets}


def read_layout(path: str) -> Dict[str, Any]:
    where = os.path.basename(path)
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise LayoutError(f"Cannot read {where}: {e.strerror or e}.") from None
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml                      # optional: JSON layouts need nothing
        except ImportError:
            raise LayoutError(f"{where}: YAML layouts need PyYAML (pip install pyyaml), or write the layout as .icd.json.") from None
        try:
            d = yaml.safe_load(text)
        except Exception as e:
            raise LayoutError(f"{where} is not valid YAML: {e}") from None
    else:
        try:
            d = json.loads(text)
        except ValueError as e:
            raise LayoutError(f"{where} is not valid JSON: {e}.") from None
    lay = parse_layout(d, where)
    if not lay["extensions"]:
        raise LayoutError(f"{where}: give \"extensions\" (e.g. [\".tlm\"]) - the files this layout reads.")
    return lay


def _values(raw: np.ndarray, starts: np.ndarray, s: Dict[str, Any]) -> np.ndarray:
    """One field / header item for every packet at once (starts: where each packet's bytes begin)."""
    idx = starts[:, None] + (s["offset"] + np.arange(s["size"]))[None, :]
    v = np.ascontiguousarray(raw[idx]).view(s["dtype"]).ravel()
    if "bits" in s:
        b0, nb = s["bits"]
        v = (v.astype(np.uint64) >> np.uint64(b0)) & np.uint64((1 << nb) - 1)
    return v.astype(np.float64)


def _hval(buf: bytes, pos: int, s: Dict[str, Any]) -> int:
    """One integer header item of the packet at pos (in the scan loop: plain bytes are much faster
    than a numpy call per packet)."""
    a = pos + s["offset"]
    return int.from_bytes(buf[a:a + s["size"]], s["order"], signed=s["type"].startswith("i"))


def _frames(raw: np.ndarray, lay: Dict[str, Any]) -> Tuple[Dict[int, List[int]], Dict[str, int]]:
    """Where each packet's payload starts, by packet id; and what had to be skipped."""
    h, packets = lay["header"], lay["packets"]
    n = len(raw)
    sync = h["sync"]
    hsize = h["size"]
    out: Dict[int, List[int]] = {pid: [] for pid in packets}
    bad = {"bytesSkipped": 0, "unknownIds": 0, "cutOff": 0}
    only = next(iter(packets.values())) if len(packets) == 1 else None
    if sync:
        sb = np.frombuffer(sync, dtype=np.uint8)
        if n < len(sb):
            return out, bad
        cand = np.ones(n - len(sb) + 1, dtype=bool)
        for k, b in enumerate(sb):
            cand &= raw[k:n - len(sb) + 1 + k] == b
        cands = np.flatnonzero(cand).tolist()
    else:
        cands = None
    buf = raw.tobytes()
    if not sync and not h["id"] and not h["length"] and only is not None:   # fixed records: no loop
        rec = hsize + only["size"]
        k = n // rec
        out[only["id"]] = list(range(0, k * rec, rec))
        if n - k * rec:
            bad["cutOff"] += 1
            bad["bytesSkipped"] += n - k * rec
        return out, bad
    pos, ci = 0, 0
    while pos + hsize <= n:
        if cands is not None:                       # the next sync at or after pos
            while ci < len(cands) and cands[ci] < pos:
                ci += 1
            if ci == len(cands):
                bad["bytesSkipped"] += n - pos
                break
            if cands[ci] > pos:
                bad["bytesSkipped"] += cands[ci] - pos
                pos = cands[ci]
            if pos + hsize > n:
                bad["cutOff"] += 1
                break
        pid = _hval(buf, pos, h["id"]) if h["id"] else (only["id"] if only else 0)
        p = packets.get(pid)
        if h["length"]:
            ln = _hval(buf, pos, h["length"])
            if h["length_includes_header"]:
                ln -= hsize
        else:
            ln = p["size"] if p else -1
        if p is None or ln < p["size"]:
            if p is None:
                bad["unknownIds"] += 1
            if cands is None:                       # no sync to look for: nothing to resync on
                bad["bytesSkipped"] += n - pos
                break
            pos += 1
            continue
        if pos + hsize + ln > n:
            bad["cutOff"] += 1
            bad["bytesSkipped"] += n - pos
            break
        out[pid].append(pos)
        pos += hsize + ln
    return out, bad


def decode(lay: Dict[str, Any], path: str) -> Dict[str, Any]:
    """A recording -> the reader result of svcore/readers.py: {"signals": {name: (t, y)}, "labels"}."""
    raw = np.fromfile(path, dtype=np.uint8)
    frames, bad = _frames(raw, lay)
    h = lay["header"]
    signals: Dict[str, Any] = {}
    labels: Dict[str, Dict[int, str]] = {}
    numbered = []
    for pid, starts_l in frames.items():
        if not starts_l:
            continue
        p = lay["packets"][pid]
        hs = np.asarray(starts_l, dtype=np.int64)
        ps = hs + h["size"]
        vals = {f["name"]: _values(raw, ps, f) for f in p["fields"]}
        if p["time"]:
            t = vals[p["time"]] * p["time_scale"]
        elif h["time"]:
            t = _values(raw, hs, h["time"]) * h["time"]["scale"] + h["time"]["add"]
        else:
            t = np.arange(len(hs), dtype=np.float64)
            numbered.append(p["name"])
        for f in p["fields"]:
            if f["name"] == p["time"]:
                continue
            nm = f"{p['name']}.{f['name']}" + (f" [{f['unit']}]" if f["unit"] else "")
            y = vals[f["name"]]
            if not f["labels"]:
                y = y * f["scale"] + f["add"]
            else:
                labels[nm] = f["labels"]
            signals[nm] = (t, y)
    return {"signals": signals, "labels": labels,
            "report": {"packets": {lay["packets"][k]["name"]: len(v) for k, v in frames.items() if v},
                       **{k: v for k, v in bad.items() if v}, **({"numbered": numbered} if numbered else {})}}


EXAMPLE = {
    "name": "Example bench telemetry",
    "extensions": [".tlm"],
    "byte_order": "little",
    "header": {"sync": "0xA55A", "size": 4, "id": {"offset": 2, "type": "u8"}, "length": {"offset": 3, "type": "u8"}},
    "packets": [
        {"id": 1, "name": "NAV", "size": 14, "time": "t_us", "time_scale": 1e-6, "fields": [
            {"name": "t_us", "offset": 0, "type": "u32"},
            {"name": "alt", "offset": 4, "type": "i32", "scale": 0.01, "unit": "m"},
            {"name": "speed", "offset": 8, "type": "u16", "scale": 0.01, "unit": "m/s"},
            {"name": "mode", "offset": 10, "type": "u8", "enum": {"0": "IDLE", "1": "CLIMB", "2": "CRUISE"}},
            {"name": "armed", "offset": 11, "type": "u8", "bits": [0, 1]},
            {"name": "temp", "offset": 12, "type": "i16", "scale": 0.1, "unit": "degC"}]},
        {"id": 2, "name": "PWR", "size": 8, "time": "t_us", "time_scale": 1e-6, "fields": [
            {"name": "t_us", "offset": 0, "type": "u32"},
            {"name": "volt", "offset": 4, "type": "u16", "scale": 0.001, "unit": "V", "byte_order": "big"},
            {"name": "amp", "offset": 6, "type": "i16", "scale": 0.01, "unit": "A"}]},
    ],
}


def write_example_recording(path: str, seconds: float = 20.0) -> None:
    """A recording for EXAMPLE: NAV at 50 Hz, PWR at 10 Hz, one damaged stretch in the middle."""
    import struct
    rng = np.random.default_rng(3)
    out = bytearray()
    for k in range(int(seconds * 50)):
        t = k / 50
        us = int(t * 1e6)
        mode = 0 if t < 2 else 1 if t < 8 else 2
        alt = 0.0 if t < 2 else min(120.0, (t - 2) * 20)
        out += b"\xa5\x5a" + bytes([1, 14]) + struct.pack("<IiHBBh", us, int(alt * 100), int((5 + 10 * (mode == 2)) * 100),
                                                         mode, 1 if t >= 1 else 0, int((25 + (t % 100) * 0.2 + rng.normal(0, 0.1)) * 10))
        if k % 5 == 0:
            out += b"\xa5\x5a" + bytes([2, 8]) + struct.pack("<I", us) + struct.pack(">H", int((16.8 - (t % 100) * 0.02) * 1000)) \
                + struct.pack("<h", int((2 + 8 * (mode > 0)) * 100))
        if k == int(seconds * 25):
            out += b"\x00\x13\x37\xa5"                         # noise on the wire: skipped, counted
    with open(path, "wb") as f:
        f.write(out)
