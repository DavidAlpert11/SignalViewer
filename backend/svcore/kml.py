"""P1 (2026-11-12): "Open in Google Earth" - the objects of a map as one KML file (plain XML, no zip).

Each object is a Placemark: when the recording has real dates (epoch seconds, as write_acmi tests them:
the first time > 1e9) a ``gx:Track`` with a ``<when>`` per sample - Google Earth then shows its time
slider and plays the flight; otherwise a plain ``LineString``. Altitudes are absolute (metres above sea
level). A stretch where the object is absent starts a new track / line (``gx:MultiTrack`` /
``MultiGeometry``). Places (P7, optional): point placemarks.

The objects come from the same sample() as the ACMI and Tacview CSV files (svcore/acmi.py)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence
from xml.sax.saxutils import escape

from svcore.acmi import AcmiObject, _num, sample


def kml_color(hex_color: str, alpha: int = 255) -> str:
    """"#rrggbb" -> KML's aabbggrr."""
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        h = "0072b2"
    return f"{alpha:02x}{h[4:6]}{h[2:4]}{h[0:2]}".lower()


def _when(t: float) -> str:
    d = datetime.fromtimestamp(t, tz=timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(round((t % 1) * 1000)) % 1000:03d}Z"


def write_kml(objects: Sequence[AcmiObject], places: Optional[Iterable[dict]] = None, *, rate: float = 10.0,
              title: str = "", left_out: Optional[List[str]] = None) -> str:
    rows: list = []
    dated = False
    if objects:                                    # P7: a file of places alone has no objects
        grid, rows, left = sample(objects, rate)
        if left_out is not None:
            left_out.extend(left)
        dated = float(grid[0]) > 1e9
    out: List[str] = ['<?xml version="1.0" encoding="UTF-8"?>',
                      '<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">',
                      "<Document>", f"<name>{escape(title or 'Signal Viewer')}</name>"]
    for k, r in enumerate(rows):
        o = r["o"]
        sid = f"s{k}"
        out.append(f'<Style id="{sid}"><LineStyle><color>{kml_color(o.get("color", ""))}</color><width>3</width></LineStyle>'
                   f'<IconStyle><color>{kml_color(o.get("color", ""))}</color></IconStyle></Style>')
        out.append(f"<Placemark><name>{escape(str(o.get('name') or 'Object'))}</name><styleUrl>#{sid}</styleUrl>")
        parts: List[str] = []
        for a, b in r["spans"]:
            coords = [f"{_num(r['lon'][i], 7)} {_num(r['lat'][i], 7)} {_num(r['alt'][i], 2)}" for i in range(a, b)]
            if dated:
                body = "".join(f"<when>{_when(float(grid[i]))}</when>" for i in range(a, b))
                body += "".join(f"<gx:coord>{c}</gx:coord>" for c in coords)
                parts.append(f"<gx:Track><altitudeMode>absolute</altitudeMode>{body}</gx:Track>")
            else:
                pts = " ".join(c.replace(" ", ",") for c in coords)
                parts.append(f"<LineString><altitudeMode>absolute</altitudeMode><coordinates>{pts}</coordinates></LineString>")
        if len(parts) == 1:
            out.append(parts[0])
        elif dated:
            out.append("<gx:MultiTrack>" + "".join(parts) + "</gx:MultiTrack>")
        else:
            out.append("<MultiGeometry>" + "".join(parts) + "</MultiGeometry>")
        out.append("</Placemark>")
    for k, p in enumerate(places or []):
        out.append(place_kml(p, k))
    out += ["</Document>", "</kml>", ""]
    return "\n".join(x for x in out if x)


def place_kml(p: dict, k: int = 0) -> str:
    """P7: one place as a Placemark - a point, a line, an area (a polygon) or a saved view (a LookAt)."""
    try:
        lat, lon = float(p["lat"]), float(p["lon"])
    except (KeyError, TypeError, ValueError):
        return ""
    kind = p.get("kind") or "point"
    col = p.get("color") or "#d29922"
    head = (f"<Placemark><name>{escape(str(p.get('name') or 'Place'))}</name>"
            + (f"<description>{escape(str(p['note']))}</description>" if p.get("note") else ""))
    if kind == "view":
        v = p.get("view") or {}
        return (head + f"<LookAt><longitude>{_num(lon, 7)}</longitude><latitude>{_num(lat, 7)}</latitude>"
                f"<altitude>{_num(float(p.get('alt') or 0), 1)}</altitude><heading>{_num(float(v.get('heading') or 0), 1)}</heading>"
                f"<tilt>{_num(max(0.0, min(90.0, 90 + float(v.get('pitch') or -90))), 1)}</tilt><range>{_num(float(v.get('range') or 1000), 1)}</range>"
                "<altitudeMode>absolute</altitudeMode></LookAt></Placemark>")
    if kind in ("line", "area") and p.get("points"):
        pts = [q for q in p["points"] if isinstance(q, (list, tuple)) and len(q) >= 2]
        if kind == "area" and pts and list(pts[0]) != list(pts[-1]):
            pts = pts + [pts[0]]
        co = " ".join(f"{_num(float(q[1]), 7)},{_num(float(q[0]), 7)},0" for q in pts)
        style = (f"<Style><LineStyle><color>{kml_color(col)}</color><width>2</width></LineStyle>"
                 f"<PolyStyle><color>{kml_color(col, 0x44)}</color></PolyStyle></Style>")
        geo = (f"<LineString><tessellate>1</tessellate><altitudeMode>clampToGround</altitudeMode><coordinates>{co}</coordinates></LineString>"
               if kind == "line" else
               f"<Polygon><tessellate>1</tessellate><altitudeMode>clampToGround</altitudeMode><outerBoundaryIs><LinearRing><coordinates>{co}"
               "</coordinates></LinearRing></outerBoundaryIs></Polygon>")
        return head + style + geo + "</Placemark>"
    alt = p.get("alt")
    mode = "absolute" if alt is not None else "clampToGround"
    return (head + f"<Style><IconStyle><color>{kml_color(col)}</color></IconStyle></Style>"
            f"<Point><altitudeMode>{mode}</altitudeMode><coordinates>{_num(lon, 7)},{_num(lat, 7)},{_num(float(alt or 0), 2)}"
            "</coordinates></Point></Placemark>")
