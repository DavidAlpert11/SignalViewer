"""P1 (2026-11-12): a checker for Tacview text ACMI 2.2 - the rules of the published specification
(see svcore/acmi.py) plus the content that is valid syntax but crashed Tacview in the owner's file.

``check(text) -> list[str]``: empty = fine. Errors break a rule of the format; lines starting with
"warning:" are content worth a look (an object 13,000 km from the others, a jump of a kilometre in one
frame). Every file write_acmi makes is checked by its tests.

Rules (one per message):
- the two header lines (a UTF-8 BOM allowed): FileType=text/acmi/tacview, FileVersion=2.2;
- object ``0`` lines before the first frame, with an ISO 8601 ``ReferenceTime``;
- frame times finite, >= 0, strictly increasing;
- object lines ``<hex id>,<Prop>=<value>...``, the id not 0;
- ``T=`` with 3, 5, 6 or 9 fields and the same count for an id for its whole life;
- every non-empty field a plain decimal number (no nan / inf / exponent);
- absolute longitude within +-180, latitude within +-90, altitude within -500 ... 100,000 m;
- the first line of an id has every ``T=`` field, ``Type`` and ``Name`` (the model; without one Tacview
  draws its generic triangle shape);
- ``Color`` one of the seven the specification lists;
- an id never used again after ``-id``;
- warnings: an object more than 2,000 km from the first object; a step of more than 1 km between two
  frames of one object.
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

COLORS = {"Red", "Orange", "Yellow", "Green", "Cyan", "Blue", "Violet"}
_DEC = re.compile(r"^-?\d+(\.\d+)?$")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
_ID = re.compile(r"^[0-9a-fA-F]+$")
FAR_KM = 2000.0
JUMP_M = 1000.0


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a)))


def _props(rest: str) -> List[Tuple[str, str]]:
    """Comma-separated Prop=value pairs (a backslash escapes a comma)."""
    out, cur, esc = [], "", False
    for ch in rest:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            cur += ch
            esc = True
        elif ch == ",":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [(p.split("=", 1)[0], p.split("=", 1)[1] if "=" in p else "") for p in out if p]


def check(text: str) -> List[str]:
    errs: List[str] = []
    warns: List[str] = []
    lines = text.lstrip("\ufeff").split("\n")
    if len(lines) < 2 or lines[0].rstrip("\r") != "FileType=text/acmi/tacview" or lines[1].rstrip("\r") != "FileVersion=2.2":
        return ["the first two lines must be FileType=text/acmi/tacview and FileVersion=2.2"]
    ref_lat = ref_lon = 0.0
    ref_time = False
    frame: Optional[float] = None
    fields: Dict[str, int] = {}              # id -> its T= field count
    last: Dict[str, List[Optional[float]]] = {}   # id -> its last absolute lon, lat, alt
    names: Dict[str, str] = {}
    first_pos: Optional[Tuple[str, float, float]] = None
    far_named: set = set()
    removed: set = set()
    for no, raw in enumerate(lines[2:], start=3):
        line = raw.rstrip("\r")
        if not line or line.startswith("//"):
            continue
        if line.startswith("#"):
            try:
                t = float(line[1:])
            except ValueError:
                errs.append(f"line {no}: the frame time {line[1:]!r} is not a number")
                continue
            if not math.isfinite(t) or t < 0 or not _DEC.match(line[1:]):
                errs.append(f"line {no}: the frame time must be a plain number >= 0")
            elif frame is not None and t <= frame:
                errs.append(f"line {no}: frame times must increase ({t} after {frame})")
            if not ref_time and frame is None:
                errs.append("no ReferenceTime before the first frame")
            frame = t
            continue
        if line.startswith("-"):
            oid = line[1:]
            if oid not in fields:
                errs.append(f"line {no}: {oid} removed but never seen")
            removed.add(oid)
            continue
        oid, _, rest = line.partition(",")
        if not _ID.match(oid):
            errs.append(f"line {no}: the object id {oid!r} is not hexadecimal")
            continue
        props = _props(rest)
        if oid == "0":
            if frame is not None:
                continue                          # global events after the start are allowed
            for k, v in props:
                if k == "ReferenceTime":
                    ref_time = bool(_ISO.match(v))
                    if not ref_time:
                        errs.append(f"line {no}: ReferenceTime {v!r} is not ISO 8601 UTC")
                elif k == "ReferenceLatitude":
                    ref_lat = float(v) if _DEC.match(v) else 0.0
                elif k == "ReferenceLongitude":
                    ref_lon = float(v) if _DEC.match(v) else 0.0
            continue
        if int(oid, 16) == 0:
            errs.append(f"line {no}: an object id must not be 0")
            continue
        if frame is None:
            errs.append(f"line {no}: object {oid} before the first frame")
        if oid in removed:
            errs.append(f"line {no}: {oid} is used again after -{oid}")
            continue
        keys = dict(props)
        new = oid not in fields
        if new:
            if "T" not in keys:
                errs.append(f"line {no}: the first line of {oid} has no T=")
                continue
            if "Type" not in keys:
                errs.append(f"line {no}: the first line of {oid} has no Type")
            if "Name" not in keys:
                errs.append(f"line {no}: the first line of {oid} has no Name (the model)")
            names[oid] = keys.get("CallSign") or keys.get("Name") or oid
        if "Color" in keys and keys["Color"] not in COLORS:
            errs.append(f"line {no}: Color {keys['Color']!r} is not one of {', '.join(sorted(COLORS))}")
        if "T" not in keys:
            continue
        f = keys["T"].split("|")
        if len(f) not in (3, 5, 6, 9):
            errs.append(f"line {no}: T= has {len(f)} fields (3, 5, 6 or 9)")
            continue
        if new:
            fields[oid] = len(f)
            if any(x == "" for x in f):
                errs.append(f"line {no}: the first line of {oid} leaves a T= field empty")
        elif fields[oid] != len(f):
            errs.append(f"line {no}: {oid} changes from {fields[oid]} to {len(f)} T= fields")
        bad = [x for x in f if x and not _DEC.match(x)]
        if bad:
            errs.append(f"line {no}: {bad[0]!r} is not a plain decimal number")
            continue
        pos = last.setdefault(oid, [None, None, None])
        prev = list(pos)
        for q in range(3):
            if f[q]:
                pos[q] = float(f[q]) + (ref_lon if q == 0 else ref_lat if q == 1 else 0.0)
        lon, lat, alt = pos
        if lon is not None and not -180 <= lon <= 180:
            errs.append(f"line {no}: longitude {lon} of {names[oid]} is outside +-180")
        if lat is not None and not -90 <= lat <= 90:
            errs.append(f"line {no}: latitude {lat} of {names[oid]} is outside +-90")
        if alt is not None and not -500 <= alt <= 100_000:
            errs.append(f"line {no}: altitude {alt} m of {names[oid]} is outside -500 ... 100,000 m")
        if lat is None or lon is None:
            continue
        if first_pos is None:
            first_pos = (names[oid], lat, lon)
        elif oid not in far_named:
            d = _km(first_pos[1], first_pos[2], lat, lon)
            if d > FAR_KM:
                far_named.add(oid)
                warns.append(f"warning: {names[oid]} is {d:,.0f} km from {first_pos[0]}")
        if prev[0] is not None and prev[1] is not None:
            step = _km(prev[1], prev[0], lat, lon) * 1000
            if step > JUMP_M:
                warns.append(f"warning: {names[oid]} jumps {step:,.0f} m at t = {frame}")
    if not ref_time:
        errs.append("no ReferenceTime")
    return errs + warns[:50]
