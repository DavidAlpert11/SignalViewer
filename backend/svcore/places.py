"""P7 (2026-11-12): places, as in Google Earth - the airfield, the range, the target, the ground station.

A place is a plain dict (the app keeps it in the session, ``Workspace.places``, or in My places,
``~/.signalviewer/places.json``)::

    {id, name, kind: "point" | "line" | "area" | "view", lat, lon, alt?, icon?, color?, note?,
     points?: [[lat, lon], ...], view?: {heading, pitch, range}, hidden?}

This module holds the one coordinate parser (decimal degrees or degrees-minutes-seconds), the readers of
the files places come in (KML, KMZ - a zip holding one KML -, GeoJSON, CSV ``name, lat, lon[, alt]``) and
``clean`` - what every place that comes from outside (a file, the UI) goes through. Files are read with
the standard library only (``xml.etree``, ``zipfile``, ``csv``, ``json``)."""
from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import uuid
import zipfile
from typing import Any, Dict, Iterable, List, Optional, Tuple
from xml.etree import ElementTree as ET

ICONS = ("pin", "airfield", "target", "antenna", "flag", "home", "camera")
KINDS = ("point", "line", "area", "view")
MAX_PLACES = 5000                    # a file with more is cut (and the reply says so)
MAX_POINTS = 5000                    # points of one line / area

# ---- coordinates -----------------------------------------------------------------------------------

_HEMI = {"N": 1, "S": -1, "E": 1, "W": -1}
# one angle: an optional hemisphere letter before or after, degrees, optional minutes and seconds
_ANGLE = re.compile(
    r"""(?P<h1>[NSEW])?\s*
        (?P<sign>[-+])?(?P<deg>\d+(?:[.,]\d+)?)\s*(?:°|º|d)?\s*
        (?:(?P<min>\d+(?:[.,]\d+)?)\s*(?:'|′|’)?\s*)?
        (?:(?P<sec>\d+(?:[.,]\d+)?)\s*(?:"|″|”|'')?\s*)?
        (?P<h2>[NSEW])?""", re.IGNORECASE | re.VERBOSE)


def _angle(m: "re.Match[str]") -> Tuple[float, Optional[str]]:
    num = lambda s: float(s.replace(",", ".")) if s else 0.0    # noqa: E731
    deg, mi, se = num(m.group("deg")), num(m.group("min")), num(m.group("sec"))
    if mi >= 60 or se >= 60:
        raise ValueError("minutes / seconds of 60 or more")
    v = deg + mi / 60 + se / 3600
    hemi = (m.group("h1") or m.group("h2") or "").upper() or None
    if m.group("sign") == "-":
        v = -v
    if hemi:
        v = abs(v) * _HEMI[hemi]
    return v, hemi


def parse_coords(text: str) -> Optional[Tuple[float, float]]:
    """``"32.687, 35.39"``, ``"32.687 35.39"``, ``32°41'13"N 35°23'24"E``, ``N32 41 13 E35 23 24``,
    ``35.39E 32.687N`` (the letters decide which is which) -> (lat, lon); None when it is not a position.
    Without letters the order is latitude, longitude (as Google Earth and most people write them)."""
    s = (text or "").strip()
    if not s or len(s) > 80:
        return None
    s = s.replace("−", "-")
    # two plain decimals: a comma, a semicolon or spaces between them (a decimal comma only with "; ")
    m = re.fullmatch(r"\s*([-+]?\d+(?:\.\d+)?)\s*[,;\s]\s*([-+]?\d+(?:\.\d+)?)\s*", s)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
    else:
        parts = [p for p in re.split(r"\s*[,;/]\s*", s) if p]
        if len(parts) != 2:
            # no separator: split by the hemisphere letters - before the second one when they lead
            # ("N32 41 13 E35 23 24"), after the first one when they follow ("32°41'13"N 35°23'24"E")
            letters = [m.start() for m in re.finditer(r"[NSEWnsew]", s)]
            if len(letters) != 2:
                return None
            cut = letters[1] if letters[0] == 0 else letters[0] + 1
            parts = [s[:cut], s[cut:]]
        vals = []
        for p in parts:
            p = p.strip()
            am = _ANGLE.fullmatch(p)
            if not am:
                return None
            try:
                vals.append(_angle(am))
            except ValueError:
                return None
        (a, ha), (b, hb) = vals
        if ha in ("E", "W") or hb in ("N", "S"):
            a, b, ha, hb = b, a, hb, ha
        if (ha and ha not in ("N", "S")) or (hb and hb not in ("E", "W")):
            return None
        lat, lon = a, b
    if not (math.isfinite(lat) and math.isfinite(lon)) or abs(lat) > 90 or abs(lon) > 180:
        return None
    return lat, lon


# ---- one place --------------------------------------------------------------------------------------

def _f(v: Any) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def new_id() -> str:
    return "pl" + uuid.uuid4().hex[:10]


def clean(p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A place as the app keeps it, or None when it has no valid position. Unknown fields are dropped."""
    if not isinstance(p, dict):
        return None
    kind = p.get("kind") if p.get("kind") in KINDS else "point"
    pts: List[List[float]] = []
    if kind in ("line", "area"):
        for q in (p.get("points") or [])[:MAX_POINTS]:
            if isinstance(q, (list, tuple)) and len(q) >= 2:
                la, lo = _f(q[0]), _f(q[1])
                if la is not None and lo is not None and abs(la) <= 90 and abs(lo) <= 180:
                    pts.append([round(la, 8), round(lo, 8)])
        if len(pts) < 2:
            return None
    lat, lon = _f(p.get("lat")), _f(p.get("lon"))
    if (lat is None or lon is None) and pts:
        lat, lon = pts[0]
    if lat is None or lon is None or abs(lat) > 90 or abs(lon) > 180:
        return None
    out: Dict[str, Any] = {"id": str(p.get("id") or new_id())[:40], "name": str(p.get("name") or "Place")[:120],
                           "kind": kind, "lat": round(lat, 8), "lon": round(lon, 8)}
    alt = _f(p.get("alt"))
    if alt is not None:
        out["alt"] = round(alt, 2)
    if pts:
        out["points"] = pts
    icon = p.get("icon")
    if kind == "point":
        out["icon"] = icon if icon in ICONS else "pin"
    if isinstance(p.get("color"), str) and re.fullmatch(r"#[0-9a-fA-F]{6}", p["color"]):
        out["color"] = p["color"]
    if p.get("note"):
        out["note"] = str(p["note"])[:2000]
    if kind == "view":
        raw_v = p.get("view")
        v: Dict[str, Any] = raw_v if isinstance(raw_v, dict) else {}
        out["view"] = {k: _f(v.get(k)) or 0.0 for k in ("heading", "pitch", "range")}
    if p.get("hidden"):
        out["hidden"] = True
    return out


def clean_all(places: Iterable[Any]) -> List[Dict[str, Any]]:
    out, seen = [], set()
    for p in places:
        c = clean(p)
        if c is None:
            continue
        if c["id"] in seen:
            c["id"] = new_id()
        seen.add(c["id"])
        out.append(c)
        if len(out) >= MAX_PLACES:
            break
    return out


# ---- reading files ----------------------------------------------------------------------------------

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kml_coords(text: str) -> List[Tuple[float, float, Optional[float]]]:
    out = []
    for tup in (text or "").split():
        f = tup.split(",")
        if len(f) < 2:
            continue
        lo, la = _f(f[0]), _f(f[1])
        al = _f(f[2]) if len(f) > 2 else None
        if la is not None and lo is not None:
            out.append((la, lo, al))
    return out


def _kml_places(root: ET.Element) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for pm in root.iter():
        if _local(pm.tag) != "Placemark":
            continue
        name, note = "", ""
        for ch in pm:
            if _local(ch.tag) == "name":
                name = (ch.text or "").strip()
            elif _local(ch.tag) == "description":
                note = (ch.text or "").strip()
        for g in pm.iter():
            tag = _local(g.tag)
            if tag not in ("Point", "LineString", "Polygon"):
                continue
            if tag == "Polygon":
                ring = next((e for e in g.iter() if _local(e.tag) == "outerBoundaryIs"), g)
                co = next((e for e in ring.iter() if _local(e.tag) == "coordinates"), None)
            else:
                co = next((e for e in g.iter() if _local(e.tag) == "coordinates"), None)
            pts = _kml_coords(co.text if co is not None and co.text else "")
            if not pts:
                out.append({"name": name, "kind": "point"})     # counted as left out (no valid position)
                continue
            if tag == "Point":
                la, lo, al = pts[0]
                out.append({"name": name, "kind": "point", "lat": la, "lon": lo, "alt": al, "note": note})
            else:
                if tag == "Polygon" and len(pts) > 2 and pts[0][:2] == pts[-1][:2]:
                    pts = pts[:-1]                        # KML closes a ring by repeating the first point
                out.append({"name": name, "kind": "area" if tag == "Polygon" else "line", "lat": pts[0][0], "lon": pts[0][1],
                            "points": [[a, b] for a, b, _ in pts], "note": note})
    return out


def _geojson_places(doc: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def geom(g: Any, name: str, note: str) -> None:
        if not isinstance(g, dict):
            return
        t, c = g.get("type"), g.get("coordinates")
        if t == "GeometryCollection":
            for x in g.get("geometries") or []:
                geom(x, name, note)
        elif t == "Point" and isinstance(c, list) and len(c) >= 2:
            out.append({"name": name, "kind": "point", "lat": c[1], "lon": c[0], "alt": c[2] if len(c) > 2 else None, "note": note})
        elif t == "MultiPoint":
            for x in c or []:
                geom({"type": "Point", "coordinates": x}, name, note)
        elif t == "LineString" and isinstance(c, list):
            out.append({"name": name, "kind": "line", "points": [[q[1], q[0]] for q in c if isinstance(q, list) and len(q) >= 2], "note": note})
        elif t == "MultiLineString":
            for x in c or []:
                geom({"type": "LineString", "coordinates": x}, name, note)
        elif t == "Polygon" and isinstance(c, list) and c:
            ring = [[q[1], q[0]] for q in c[0] if isinstance(q, list) and len(q) >= 2]
            if len(ring) > 2 and ring[0] == ring[-1]:
                ring = ring[:-1]
            out.append({"name": name, "kind": "area", "points": ring, "note": note})
        elif t == "MultiPolygon":
            for x in c or []:
                geom({"type": "Polygon", "coordinates": x}, name, note)

    def feature(f: Any) -> None:
        if not isinstance(f, dict):
            return
        if f.get("type") == "FeatureCollection":
            for x in f.get("features") or []:
                feature(x)
        elif f.get("type") == "Feature":
            pr = f.get("properties") or {}
            name = str(next((pr[k] for k in ("name", "Name", "NAME", "title") if pr.get(k)), ""))
            note = str(pr.get("description") or pr.get("note") or "")
            geom(f.get("geometry"), name, note)
        else:
            geom(f, "", "")
    feature(doc)
    return out


_CSV_NAMES = {"name": ("name", "title", "label", "place", "שם"),
              "lat": ("lat", "latitude", "y", "רוחב"), "lon": ("lon", "lng", "long", "longitude", "x", "אורך"),
              "alt": ("alt", "altitude", "elevation", "height", "גובה")}


def _csv_places(text: str) -> List[Dict[str, Any]]:
    try:
        dialect: Any = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        return []
    head = [c.strip().lower() for c in rows[0]]
    col: Dict[str, int] = {}
    for key, names in _CSV_NAMES.items():
        for i, h in enumerate(head):
            if h in names:
                col[key] = i
                break
    if "lat" in col and "lon" in col:
        body = rows[1:]
    else:                                   # no header: name, lat, lon[, alt]
        col = {"name": 0, "lat": 1, "lon": 2, "alt": 3}
        body = rows if _f(rows[0][1] if len(rows[0]) > 1 else None) is not None else rows[1:]
    out = []
    for r in body:
        g = lambda k: r[col[k]].strip() if k in col and col[k] < len(r) else ""    # noqa: E731
        la, lo = _f(g("lat")), _f(g("lon"))
        if la is None or lo is None:
            pos = parse_coords(f"{g('lat')} {g('lon')}")     # degrees-minutes-seconds in the cells
            if not pos:
                continue
            la, lo = pos
        out.append({"name": g("name"), "kind": "point", "lat": la, "lon": lo, "alt": _f(g("alt"))})
    return out


def read_places(path: str) -> Tuple[List[Dict[str, Any]], int]:
    """The places in a .kml, .kmz, .geojson / .json or .csv file -> (places, how many were left out:
    no valid position, or past MAX_PLACES). Raises ValueError with a message for the user."""
    ext = os.path.splitext(path)[1].lower()
    with open(path, "rb") as f:
        data = f.read()
    if ext == ".kmz":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                name = next((n for n in z.namelist() if n.lower().endswith(".kml")), None)
                if not name:
                    raise ValueError("This .kmz holds no .kml file.")
                data, ext = z.read(name), ".kml"
        except zipfile.BadZipFile as e:
            raise ValueError("This .kmz is not a readable zip file.") from e
    raw: List[Dict[str, Any]]
    if ext == ".kml":
        try:
            raw = _kml_places(ET.fromstring(data))
        except ET.ParseError as e:
            raise ValueError(f"This KML file is not valid XML ({e}).") from e
    elif ext in (".geojson", ".json"):
        try:
            raw = _geojson_places(json.loads(data.decode("utf-8-sig")))
        except (ValueError, UnicodeDecodeError) as e:
            raise ValueError(f"This GeoJSON file could not be read ({e}).") from e
    elif ext in (".csv", ".txt"):
        raw = _csv_places(data.decode("utf-8-sig", errors="replace"))
    else:
        raise ValueError("Places come from .kml, .kmz, .geojson or .csv files.")
    for k, p in enumerate(raw):
        if not p.get("name"):
            p["name"] = f"Place {k + 1}"
    places = clean_all(raw)
    return places, max(0, len(raw) - len(places))
