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
from typing import Dict, List, Optional, Sequence, Tuple, TypedDict

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


GAP_S = 2.0                     # samples further apart than this: the object is gone in between (-id)
MAX_CELLS = 1_500_000           # frames x objects above this: the rate is lowered to fit (>= 1 a second)
# P1 (T2): Tacview reads ``Name`` as the MODEL it looks up in its database; the object's own name goes
# into ``CallSign`` ("displayed in priority over the object name"). A name the database does not know is
# drawn as Tacview's generic triangle shape (owner, 2026-11-12: "some objects show as triangles" - the
# old files had Name=XKF1[0], POS...). Every kind therefore gets a model that is in Tacview's public
# database (github.com/Vyrtuoz/Tacview, Database/Default Properties, checked 2026-11-12) with a 3D shape:
# C172 (FixedWing.C172.obj), MQ-9 (FixedWing.MQ-9.obj), DJI300 (the database's multirotor drone shape;
# Bell 206 was the first choice, a helicopter), AIM-9M, Zodiac (Watercraft.Zodiac.obj), Pickup
# (Vehicle.Car.Pickup.obj).
MODELS = {"aircraft": "C172", "uav": "MQ-9", "drone": "DJI300", "missile": "AIM-9M", "ship": "Zodiac", "vehicle": "Pickup"}


def _on(grid: np.ndarray, t: np.ndarray, v: Optional[np.ndarray], angle: bool = False,
        gap: Optional[float] = None) -> Optional[np.ndarray]:
    """v (at times t) on the grid: interpolated (angles the short way round), NaN outside its span -
    and, with `gap`, NaN inside any stretch where its valid samples are more than `gap` s apart."""
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
    if gap is not None:
        k = np.clip(np.searchsorted(t, grid, side="right") - 1, 0, len(t) - 2)
        within = (grid > t[k] + 1e-9) & (grid < t[k + 1] - 1e-9)
        out[within & (t[k + 1] - t[k] > gap)] = np.nan
    if angle:
        out = np.mod(out, 360.0)
    return out


def _carry(v: Optional[np.ndarray], first: float = np.nan) -> Optional[np.ndarray]:
    """Each missing value replaced by the last one before it (`first` before the first one)."""
    if v is None:
        return None
    ok = np.isfinite(v)
    if not ok.any():
        return np.full(len(v), first)
    idx = np.where(ok, np.arange(len(v)), -1)
    np.maximum.accumulate(idx, out=idx)
    return np.where(idx >= 0, v[np.maximum(idx, 0)], first)


def _has_attitude(*angles: Optional[np.ndarray]) -> bool:
    """P1 (T3): angles that are absent, never finite or always exactly 0 are not an attitude (a GPS
    receiver written with 0|0|0 for the whole flight flew sideways with a frozen nose)."""
    vals = [a[np.isfinite(a)] for a in angles if a is not None]
    return any(len(a) and np.any(a != 0) for a in vals)


def fit_rate(objects: Sequence[AcmiObject], rate: float) -> float:
    """The rate the files are written at: `rate` (0.1-100 a second), lowered so that frames x objects
    stays under MAX_CELLS (never under 1 a second) - Tacview and Google Earth stay responsive."""
    rate = float(min(max(rate, 0.1), 100.0))
    objs = [o for o in objects if len(np.asarray(o.get("t", []))) > 1]
    if not objs:
        return rate
    span = max(float(np.nanmax(o["t"])) for o in objs) - min(float(np.nanmin(o["t"])) for o in objs)
    if span > 0 and span * rate * len(objs) > MAX_CELLS:
        rate = max(1.0, min(rate, MAX_CELLS / (span * len(objs))))
    return rate


class Sampled(TypedDict):
    """One object on the common time grid, cut into the stretches it is present."""
    o: AcmiObject
    lat: np.ndarray
    lon: np.ndarray
    alt: np.ndarray                     # metres above sea level, never missing (carried)
    att: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]   # roll, pitch, yaw (degrees, carried)
    spans: List[Tuple[int, int]]        # [i0, i1) grid indexes where it is present


def sample(objects: Sequence[AcmiObject], rate: float) -> Tuple[np.ndarray, List[Sampled], List[str]]:
    """The one time grid every export uses (ACMI, Tacview CSV, KML): from the first sample of any
    object to the last, `rate` a second. Returns (grid, objects on it, names left out). An object with
    fewer than two valid positions is left out (P2: an object with no position is not an object)."""
    objs: List[AcmiObject] = []
    left: List[AcmiObject] = []
    for o in objects:
        t = np.asarray(o.get("t", []), dtype=np.float64)
        lat = np.asarray(o.get("lat", []), dtype=np.float64)
        lon = np.asarray(o.get("lon", []), dtype=np.float64)
        ok = np.isfinite(t) & np.isfinite(lat) & np.isfinite(lon) if len(t) == len(lat) == len(lon) else np.zeros(0, bool)
        (objs if np.count_nonzero(ok) >= 2 else left).append(o)
    left_names = [str(o.get("name") or "Object") for o in left]
    if not objs:
        raise ValueError("No object has a position to export.")
    t0 = min(float(np.nanmin(np.where(np.isfinite(o["lat"]), o["t"], np.nan))) for o in objs)
    t1 = max(float(np.nanmax(np.where(np.isfinite(o["lat"]), o["t"], np.nan))) for o in objs)
    if not (math.isfinite(t0) and math.isfinite(t1)):
        raise ValueError("No object has a position to export.")
    n = int(math.floor((t1 - t0) * rate + 1e-9)) + 1
    if n > 2_000_000:
        raise ValueError("The recording is too long for this rate; choose fewer samples a second.")
    grid = t0 + np.arange(n) / rate
    if grid[-1] < t1 - 1e-9:
        grid = np.append(grid, t1)
    rows: List[Sampled] = []
    for o in objs:
        t = np.asarray(o["t"], dtype=np.float64)
        pos_ok = np.isfinite(np.asarray(o["lat"], dtype=np.float64)) & np.isfinite(np.asarray(o["lon"], dtype=np.float64))
        lat_g = _on(grid, t[pos_ok], np.asarray(o["lat"])[pos_ok], gap=GAP_S)
        lon_g = _on(grid, t[pos_ok], np.asarray(o["lon"])[pos_ok], gap=GAP_S)
        if lat_g is None or lon_g is None:
            left_names.append(str(o.get("name") or "Object"))
            continue
        lat, lon = lat_g, lon_g
        here = np.isfinite(lat) & np.isfinite(lon)
        if np.count_nonzero(here) < 2:
            left_names.append(str(o.get("name") or "Object"))
            continue
        # an altitude missing at a sample keeps the previous one (0 only if there never was one)
        alt = _carry(_on(grid, t, o.get("alt")), 0.0)
        alt = np.zeros(len(grid)) if alt is None else alt
        roll, pitch, yaw = (_on(grid, t, o.get("roll"), True), _on(grid, t, o.get("pitch"), True), _on(grid, t, o.get("yaw"), True))
        att = None
        if _has_attitude(roll, pitch, yaw):
            # a missing angle carries its last value; before the first one: level (0)
            att = tuple(_carry(a, 0.0) if a is not None else np.zeros(len(grid)) for a in (roll, pitch, yaw))
        edges = np.diff(np.r_[0, here.astype(np.int8), 0])
        spans = list(zip(np.flatnonzero(edges == 1).tolist(), np.flatnonzero(edges == -1).tolist()))
        rows.append({"o": o, "lat": lat, "lon": lon, "alt": alt, "att": att, "spans": spans})   # type: ignore[typeddict-item]
    if not rows:
        raise ValueError("No object has a position to export.")
    return grid, rows, left_names


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + (
        "" if ts == int(ts) else f".{int(round((ts % 1) * 1000)):03d}") + "Z"


def write_acmi(objects: Sequence[AcmiObject], *, rate: float = 10.0, title: str = "",
               reference_time: Optional[str] = None, recording_time: Optional[str] = None,
               recorder: str = "Signal Viewer", comments: str = "", left_out: Optional[List[str]] = None,
               places: Optional[Sequence[dict]] = None) -> str:
    """The ACMI text of these objects, sampled `rate` times a second on one time grid (sample()).
    An object appears at its first valid position and is removed (``-id``) when its position ends or
    has a gap longer than GAP_S; when it comes back it is a new object (a new id - Tacview does not
    allow an id again after ``-id``). Times that look like Unix epoch seconds (after 2001) become the
    ReferenceTime; otherwise `reference_time` (ISO 8601 UTC) or 2000-01-01T00:00:00Z, and the frames
    count from the recording's start. P1: ``Name`` is the model (MODELS), ``CallSign`` the object's
    name; an object with no attitude of its own gets the 3-field ``T=``; no field is ever empty.
    `left_out` (a list) receives the names of objects with no position. P7: `places` (points) are
    stationary objects in the first frame - ``Navaid+Static+Waypoint`` (an airfield
    ``Ground+Static+Aerodrome``), the types the ACMI 2.2 spec lists for them."""
    grid, rows, left = sample(objects, float(min(max(rate, 0.1), 100.0)))
    if left_out is not None:
        left_out.extend(left)
    t0 = float(grid[0])
    epoch = t0 > 1e9
    ref = iso(math.floor(t0)) if epoch else (reference_time or "2000-01-01T00:00:00Z")
    base = math.floor(t0) if epoch else t0
    # the reference point: whole degrees near the first position (smaller numbers in every line)
    first = rows[0]
    i0 = first["spans"][0][0]
    ref_lat = float(math.floor(first["lat"][i0]))
    ref_lon = float(math.floor(first["lon"][i0]))

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

    # one id per stretch of presence: (grid index it starts at, ends at, row, id)
    events: List[Tuple[int, int, int, str]] = []
    for j, r in enumerate(rows):
        for a, b in r["spans"]:
            events.append((a, b, j, ""))
    events.sort(key=lambda e: (e[0], e[2]))
    ids = {(a, j): format(0x101 + k, "x") for k, (a, _b, j, _x) in enumerate(events)}
    start_at: Dict[int, List[Tuple[int, int, str]]] = {}
    end_at: Dict[int, List[str]] = {}
    for a, b, j, _x in events:
        start_at.setdefault(a, []).append((j, b, ids[(a, j)]))
        end_at.setdefault(b, []).append(ids[(a, j)])
    live: Dict[int, str] = {}                      # row -> its current id
    for i, tg in enumerate(grid):
        lines: List[str] = [f"-{x}" for x in end_at.get(i, [])]
        for x in end_at.get(i, []):
            live = {j: v for j, v in live.items() if v != x}
        new = {j: x for j, _b, x in start_at.get(i, [])}
        live.update(new)
        for j in sorted(live):
            r, oid = rows[j], live[j]
            pos = f"{_num(r['lon'][i] - ref_lon, 7)}|{_num(r['lat'][i] - ref_lat, 7)}|{_num(r['alt'][i], 2)}"
            if r["att"] is not None:
                ang = [_num(((a[i] + 180) % 360) - 180 if q < 2 else a[i], 2) for q, a in enumerate(r["att"])]
                pos += "|" + "|".join(ang)
            line = f"{oid},T={pos}"
            if j in new:
                o = r["o"]
                kind = o.get("kind", "")
                line += f",Type={TYPES.get(kind, 'Air+FixedWing')},Name={MODELS.get(kind, 'C172')}"
                line += f",CallSign={text(o.get('name') or 'Object')},Color={acmi_color(o.get('color', ''))}"
                if o.get("group"):
                    line += f",Group={text(o['group'])}"
            lines.append(line)
        if i == 0:
            lines += _place_lines(places or [], ref_lat, ref_lon)
        if lines:
            out.append(f"#{_num(tg - base, 3)}\n" + "\n".join(lines) + "\n")
    return "".join(out)


def _place_lines(places: Sequence[dict], ref_lat: float, ref_lon: float) -> List[str]:
    out = []
    for k, p in enumerate(p for p in places if (p.get("kind") or "point") == "point"):
        try:
            lat, lon, alt = float(p["lat"]), float(p["lon"]), float(p.get("alt") or 0.0)
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon) and math.isfinite(alt)) or abs(lat) > 90 or abs(lon) > 180:
            continue
        typ = "Ground+Static+Aerodrome" if p.get("icon") == "airfield" else "Navaid+Static+Waypoint"
        out.append(f"{format(0xF0001 + k, 'x')},T={_num(lon - ref_lon, 7)}|{_num(lat - ref_lat, 7)}|{_num(alt, 2)},"
                   f"Type={typ},Name={text(str(p.get('name') or 'Place'))},Color={acmi_color(p.get('color') or '')}")
    return out
