"""N8: Tacview's text ACMI (2.2) - the objects of a map / 3D view, for users who know Tacview.

The format, as Tacview's published specification describes it ("ACMI flight recordings 2.2",
raia-software-inc.gitbook.io/tacview/technical-documentation/acmi-telemetry-file-format), checked
2026-11-10:

- UTF-8 (a BOM recommended), lines ended by LF; the first two lines are mandatory:
  ``FileType=text/acmi/tacview`` and ``FileVersion=2.2``.
- Object ``0`` holds the global properties (``ReferenceTime`` - ISO 8601 UTC -, ``ReferenceLongitude``
  / ``ReferenceLatitude`` added to every object's longitude / latitude, ``DataSource``, ``DataRecorder``,
  ``RecordingTime``, ``Title``, ``Comments``...).
- ``#<seconds>`` starts a frame, in seconds from ``ReferenceTime``.
- ``<id>,<Property>=<value>,...`` - the id hexadecimal, no prefix, not 0. Text values escape a comma
  with a backslash; line breaks are not written here (replaced by a space).
- ``T=Longitude|Latitude|Altitude|Roll|Pitch|Yaw`` (the 6-field form): degrees, metres above sea level;
  roll positive to the right, pitch positive nose-up, yaw clockwise from true north.
- ``-<id>`` removes an object (it left the recording).
- ``Type`` tags joined by ``+`` (``Air+FixedWing``, ``Air+Rotorcraft``, ``Sea+Watercraft``,
  ``Ground+Vehicle``, ``Weapon+Missile``); ``Color`` one of Red, Orange, Yellow, Green, Cyan, Blue,
  Violet (Yellow and Cyan since Tacview 1.8.8).

Everything here is plain numbers in, text out (no store): the route gathers each object's signals.
"""
from __future__ import annotations

import colorsys
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, TypedDict

import numpy as np

HEADER = "FileType=text/acmi/tacview\nFileVersion=2.2\n"

# the app's object kinds -> Tacview's type tags (Tacview has no UAV tag: a fixed-wing UAV is a plane,
# a multirotor drone a rotorcraft)
TYPES = {
    "aircraft": "Air+FixedWing",
    "uav": "Air+FixedWing",
    "drone": "Air+Rotorcraft",
    "missile": "Weapon+Missile",
    "ship": "Sea+Watercraft",
    "vehicle": "Ground+Vehicle",
}
# Tacview's colours by hue (degrees, the upper end of each range); a light blue is Cyan, a dark one Blue
_HUES = [(15, "Red"), (45, "Orange"), (75, "Yellow"), (170, "Green"), (200, "Cyan"), (255, "Blue"), (335, "Violet"), (361, "Red")]


class AcmiObject(TypedDict, total=False):
    name: str
    kind: str
    color: str                    # "#rrggbb"
    group: str
    t: np.ndarray                 # seconds (the recording's own time)
    lat: np.ndarray               # degrees
    lon: np.ndarray               # degrees
    alt: Optional[np.ndarray]     # metres above sea level
    roll: Optional[np.ndarray]    # degrees
    pitch: Optional[np.ndarray]
    yaw: Optional[np.ndarray]


def acmi_color(hex_color: str) -> str:
    """The Tacview colour nearest to an "#rrggbb" (by hue; a grey is Blue - Tacview has no grey)."""
    h = (hex_color or "").lstrip("#")
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except (ValueError, IndexError):
        return "Blue"
    hue, light, s = colorsys.rgb_to_hls(r, g, b)
    if s < 0.15:
        return "Blue"
    deg = hue * 360
    if 170 <= deg < 215 and light > 0.55:
        return "Cyan"
    return next(name for top, name in _HUES if deg < top)


def text(v: str) -> str:
    """A text value as ACMI writes it: commas escaped, no line breaks."""
    return " ".join(str(v).split()).replace("\\", "/").replace(",", "\\,")


def _num(v: float, digits: int) -> str:
    s = f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _on(grid: np.ndarray, t: np.ndarray, v: Optional[np.ndarray], angle: bool = False) -> Optional[np.ndarray]:
    """v (at times t) on the grid: interpolated (angles the short way round), NaN outside its span."""
    if v is None:
        return None
    t = np.asarray(t, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    ok = np.isfinite(t) & np.isfinite(v)
    t, v = t[ok], v[ok]
    if len(t) < 1:
        return None
    if len(t) == 1:
        out = np.where(np.abs(grid - t[0]) < 1e-9, v[0], np.nan)
        return out
    if angle:
        v = np.unwrap(v, period=360.0)
    out = np.interp(grid, t, v)
    out[(grid < t[0]) | (grid > t[-1])] = np.nan
    if angle:
        out = np.mod(out, 360.0)
    return out


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + (
        "" if ts == int(ts) else f".{int(round((ts % 1) * 1000)):03d}") + "Z"


def write_acmi(objects: Sequence[AcmiObject], *, rate: float = 10.0, title: str = "",
               reference_time: Optional[str] = None, recording_time: Optional[str] = None,
               recorder: str = "Signal Viewer", comments: str = "") -> str:
    """The ACMI text of these objects, sampled `rate` times a second on one time grid (from the first
    sample of any object to the last). An object appears at its first valid position and is removed
    (``-id``) when its position ends. Times that look like Unix epoch seconds (after 2001) become the
    ReferenceTime; otherwise `reference_time` (ISO 8601 UTC) or 2000-01-01T00:00:00Z, and the frames
    count from the recording's start."""
    objs = [o for o in objects if len(np.asarray(o.get("t", []))) > 0]
    if not objs:
        raise ValueError("No object has a position to export.")
    rate = float(min(max(rate, 0.1), 100.0))
    t0 = min(float(np.nanmin(o["t"])) for o in objs)
    t1 = max(float(np.nanmax(o["t"])) for o in objs)
    if not (math.isfinite(t0) and math.isfinite(t1)):
        raise ValueError("No object has a position to export.")
    n = int(math.floor((t1 - t0) * rate + 1e-9)) + 1
    if n > 2_000_000:
        raise ValueError("The recording is too long for this rate; choose fewer samples a second.")
    grid = t0 + np.arange(n) / rate
    if grid[-1] < t1 - 1e-9:
        grid = np.append(grid, t1)
    epoch = t0 > 1e9
    ref = iso(math.floor(t0)) if epoch else (reference_time or "2000-01-01T00:00:00Z")
    base = math.floor(t0) if epoch else t0

    rows: List[Dict[str, Any]] = []        # per object: id, its arrays on the grid
    for k, o in enumerate(objs):
        t = np.asarray(o["t"], dtype=np.float64)
        lat, lon = _on(grid, t, o["lat"]), _on(grid, t, o["lon"])
        alt = _on(grid, t, o.get("alt"))
        roll, pitch = _on(grid, t, o.get("roll"), True), _on(grid, t, o.get("pitch"), True)
        yaw = _on(grid, t, o.get("yaw"), True)
        if lat is None or lon is None:
            continue
        rows.append({"id": format(0x101 + k, "x"), "o": o, "lat": lat, "lon": lon, "alt": alt,
                     "att": None if roll is None and pitch is None and yaw is None else (roll, pitch, yaw)})
    if not rows:
        raise ValueError("No object has a position to export.")
    # the reference point: whole degrees near the first position (smaller numbers in every line)
    first = rows[0]
    i_ok = np.flatnonzero(np.isfinite(first["lat"]) & np.isfinite(first["lon"]))
    ref_lat = float(math.floor(first["lat"][i_ok[0]])) if len(i_ok) else 0.0
    ref_lon = float(math.floor(first["lon"][i_ok[0]])) if len(i_ok) else 0.0

    out: List[str] = [HEADER]
    glob = [f"0,ReferenceTime={ref}", f"0,ReferenceLongitude={_num(ref_lon, 0)}", f"0,ReferenceLatitude={_num(ref_lat, 0)}",
            f"0,DataSource={text(recorder)}", f"0,DataRecorder={text(recorder)}"]
    if recording_time:
        glob.append(f"0,RecordingTime={recording_time}")
    if title:
        glob.append(f"0,Title={text(title)}")
    if comments:
        glob.append(f"0,Comments={text(comments)}")
    out.append("\n".join(glob) + "\n")

    alive = [False] * len(rows)
    for i, tg in enumerate(grid):
        lines: List[str] = []
        for j, r in enumerate(rows):
            la, lo = r["lat"][i], r["lon"][i]
            here = bool(np.isfinite(la) and np.isfinite(lo))
            if not here:
                if alive[j]:
                    lines.append(f"-{r['id']}")
                    alive[j] = False
                continue
            h = r["alt"][i] if r["alt"] is not None and np.isfinite(r["alt"][i]) else 0.0
            pos = f"{_num(lo - ref_lon, 7)}|{_num(la - ref_lat, 7)}|{_num(h, 2)}"
            if r["att"] is not None:
                ang = ["" if a is None or not np.isfinite(a[i]) else _num(((a[i] + 180) % 360) - 180 if q < 2 else a[i], 2)
                       for q, a in enumerate(r["att"])]
                if not alive[j]:            # its first line: a missing angle is 0 (nothing to keep yet)
                    ang = [a or "0" for a in ang]
                pos += "|" + "|".join(ang)
            line = f"{r['id']},T={pos}"
            if not alive[j]:
                o = r["o"]
                line += (f",Type={TYPES.get(o.get('kind', ''), 'Air+FixedWing')},Name={text(o.get('name') or 'Object')}"
                         f",Color={acmi_color(o.get('color', ''))}")
                if o.get("group"):
                    line += f",Group={text(o['group'])}"
                alive[j] = True
            lines.append(line)
        if lines:
            out.append(f"#{_num(tg - base, 3)}\n" + "\n".join(lines) + "\n")
    return "".join(out)
