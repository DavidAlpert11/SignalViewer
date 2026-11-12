"""Export and reports: CSV, HTML / PDF / Word reports, images, saved text."""

import asyncio
import base64
import os
from typing import List, Optional

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel

from app import report as reports
from app.atomic import write_text as _write_text
from app.common import atomic_open, atomic_path, atomic_write, fail
from app.store import store
from svcore.analysis import align_to

router = APIRouter()




# =============================================================================
# EXPORT, REPORTS, SESSIONS (phase 4)
# =============================================================================

def _check_target(path: str, ext: str) -> str:
    if not path:
        fail(400, "Choose where to save the file.")
    path = os.path.abspath(os.path.expanduser(path))
    if not path.lower().endswith(ext):
        path += ext
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        fail(400, f"Folder not found: {folder}")
    return path



class ExportCsvRequest(BaseModel):
    path: str
    signals: List[dict]              # [{id, label, scale, offset}]
    t0: Optional[float] = None
    t1: Optional[float] = None
    alignment: str = "linear"



@router.post("/api/export/csv")
async def export_csv(req: ExportCsvRequest):
    """Signals on the first signal's time base, inside [t0, t1], full resolution."""
    path = _check_target(req.path, ".csv")

    def work():
        if not req.signals:
            raise ValueError("No signals to export.")
        t_base, _ = store.signal(req.signals[0]["id"])
        if req.signals[0].get("tOffset"):          # work in the displayed (shifted) time
            t_base = np.asarray(t_base, dtype=np.float64) + float(req.signals[0]["tOffset"])
        i0 = 0 if req.t0 is None else int(np.searchsorted(t_base, min(req.t0, req.t1), "left"))
        i1 = len(t_base) if req.t1 is None else int(np.searchsorted(t_base, max(req.t0, req.t1), "right"))
        t = np.asarray(t_base[i0:i1], dtype=np.float64)
        cols, header = [t], ["Time"]
        for s in req.signals:
            ts, ys = store.signal(s["id"])
            if s.get("tOffset"):
                ts = np.asarray(ts, dtype=np.float64) + float(s["tOffset"])
            y = align_to(t, ts, ys, req.alignment) if s is not req.signals[0] else np.asarray(ys[i0:i1], dtype=np.float64)
            cols.append(y * float(s.get("scale", 1) or 1) + float(s.get("offset", 0) or 0))
            header.append(str(s.get("label") or s["id"].split("/", 1)[-1]).replace(",", " "))
        with atomic_open(path, "w", "utf-8-sig", "") as f:
            f.write(",".join(header) + "\n")
            np.savetxt(f, np.column_stack(cols), delimiter=",", fmt="%.10g")
        return len(t)
    try:
        rows = await asyncio.to_thread(work)
    except KeyError:
        fail(404, "One of the signals is no longer open.")
    except ValueError as e:
        fail(400, str(e))
    return {"path": path, "rows": rows}



class ReportRequest(BaseModel):
    path: str
    format: str = "html"             # html | pdf | docx
    title: str = ""
    intro: str = ""
    summary: str = ""
    lang: str = "en"
    theme: str = "light"
    tabs: List[dict] = []
    notes: List[dict] = []          # the user's notes: [{t, text}]
    sections: List[dict] = []       # investigation: [{title, text?, items?, table?: {head, rows}}]
    replay: Optional[dict] = None   # R1: a replay page - {t, extent, events: [{t, text, level}]} (report.build_html)



@router.post("/api/report")
async def make_report(req: ReportRequest):
    ext = {"html": ".html", "pdf": ".pdf", "docx": ".docx"}.get(req.format)
    if not ext:
        fail(400, "Unknown report format.")
    path = _check_target(req.path, ext)
    body = req.model_dump()

    def work():
        # O3: built into a temporary file that replaces the old report only when complete (the HTML was
        # opened - emptied - before it was built, so a failed build left an empty report)
        with atomic_path(path) as tmp:
            if req.format == "html":
                _write_text(tmp, reports.build_html(store, body))
            elif req.format == "pdf":
                reports.build_pdf(store, body, tmp)
            else:
                reports.build_docx(store, body, tmp)
    try:
        await asyncio.to_thread(work)
    except KeyError:
        fail(404, "One of the signals in the report is no longer open.")
    except reports.ReportNeedsExtra as e:
        fail(400, str(e))
    return {"path": path, "size": os.path.getsize(path)}



class OpenRequest(BaseModel):
    path: str


@router.post("/api/export/open")
def open_page(req: OpenRequest):
    """R1: a page the app just wrote (a replay, a report, a map) in the user's own browser - to look at it
    before sending it. HTML only: nothing else is opened from here."""
    import webbrowser
    from pathlib import Path
    path = os.path.abspath(os.path.expanduser(req.path or ""))
    if not path.lower().endswith((".html", ".htm")) or not os.path.isfile(path):
        fail(400, "Only an HTML file the app saved can be opened here.")
    return {"opened": bool(webbrowser.open(Path(path).as_uri(), new=2))}


@router.post("/api/report/preview")
async def report_preview(req: ReportRequest):
    html_text = await asyncio.to_thread(reports.build_html, store, req.model_dump())
    return {"html": html_text}



class ImageRequest(BaseModel):
    path: str
    format: str = "png"              # png | svg | html (the plot alone, interactive, as in the report)
    theme: str = "light"
    plot: dict
    scale: float = 1                 # png: 2 = twice the pixels (a report, a slide), up to 4
    lang: str = "en"



@router.post("/api/export/image")
async def export_image(req: ImageRequest):
    if req.format not in ("png", "svg", "html"):
        fail(400, "Unknown image format.")
    path = _check_target(req.path, "." + req.format)
    try:
        if req.format == "html":
            text = await asyncio.to_thread(reports.build_plot_html, store, req.plot, req.theme, req.lang)
            atomic_write(path, text)
            return {"path": path, "size": len(text.encode("utf-8"))}
        data = await asyncio.to_thread(reports.build_image, store, req.plot, req.format, req.theme, max(1.0, min(4.0, req.scale)))
    except KeyError:
        fail(404, "One of the plot's signals is no longer open.")
    except ValueError as e:                                       # L11: a map with nothing to draw
        fail(400, str(e))
    atomic_write(path, data)
    return {"path": path}



class TextSave(BaseModel):
    path: str
    content: str
    ext: str = ".csv"
    bom: bool = True          # Excel wants it for CSV; a .param file for Mission Planner must not have it



@router.post("/api/save/text")
def save_text(req: TextSave):
    """Save text produced by the UI (e.g. comparison results as CSV)."""
    path = _check_target(req.path, req.ext)
    atomic_write(path, req.content, "utf-8-sig" if req.bom else "utf-8", "")
    return {"path": path}



class ImageSave(BaseModel):
    path: str
    data: str                   # base64 of the image the UI drew (the 3D view)



@router.post("/api/save/image")
def save_image(req: ImageSave):
    """Save a PNG the UI made itself (the 3D view is drawn in the browser, not by the server)."""
    path = _check_target(req.path, ".png")
    try:
        raw = base64.b64decode(req.data.split(",", 1)[-1], validate=True)
    except Exception:
        fail(400, "Not an image.")
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        fail(400, "Not a PNG image.")
    atomic_write(path, raw)
    return {"path": path}



class AcmiRequest(BaseModel):
    path: str
    title: str = ""
    rate: float = 10.0               # samples a second in the file
    objects: List[dict]              # MapObject as the views fetch it (trackRequest: borrowed attitude resolved)
    places: List[dict] = []          # P7: the map's shown places (svcore/places.py) - in the ACMI and KML files


def _decode(s, dtype):
    return None if s is None else np.frombuffer(base64.b64decode(s), dtype=dtype).astype(np.float64)


def acmi_objects(objects: List[dict], st=None) -> list:
    """N8: each map object's position and attitude, as the 3D view draws it: altitude above sea level
    by its reference (above the take-off point / the ground: plus the bundled elevation; none: on the
    ground), angles in degrees (the object's own unit if set, else the one found)."""
    from app.routes.analysis import ObjectTrackRequest, track_of
    from app.store import store
    out = []
    for o in objects:
        req = ObjectTrackRequest(lat=o["lat"], lon=o["lon"], alt=o.get("alt"), yaw=o.get("yaw"), pitch=o.get("pitch"),
                                 roll=o.get("roll"), qw=o.get("qw"), qx=o.get("qx"), qy=o.get("qy"), qz=o.get("qz"),
                                 points=10_000_000, attitude=o.get("attitude"), minSpeed=float(o.get("minSpeed") or 1.0))
        tr = track_of(st if st is not None else store, req)
        t, lat, lon = _decode(tr["t"], np.float64), _decode(tr["lat"], np.float64), _decode(tr["lon"], np.float64)
        ground = _decode(tr.get("ground"), np.float32)
        g = np.where(np.isfinite(ground), ground, 0.0) if ground is not None else np.zeros(len(t))
        alt = _decode(tr.get("alt"), np.float32)
        kind = o.get("kind") or "aircraft"
        if alt is None:
            alt = g + (0.0 if kind == "ship" else 0.5 if kind == "vehicle" else 2.0)
        elif o.get("altRef") == "agl":
            alt = g + alt
        elif o.get("altRef") == "home":
            ok = np.flatnonzero(np.isfinite(alt))
            alt = alt + (g[ok[0]] if len(ok) else 0.0)
        unit_set = o.get("angleUnit") if o.get("angleUnit") in ("deg", "rad") else None
        ang: dict = {}
        for role in ("roll", "pitch", "yaw"):
            v = _decode(tr.get(role), np.float32)
            if v is None:
                ang[role] = None
                continue
            unit = unit_set if (unit_set and o.get(role)) else tr["units"].get(role, "deg")
            ang[role] = np.degrees(v) if unit == "rad" else v
        if any(a is not None for a in ang.values()):
            ang = {k: (v if v is not None else np.zeros(len(t))) for k, v in ang.items()}   # roll unknown: level
        out.append({"name": o.get("name") or "Object", "kind": kind, "color": o.get("color", ""), "t": t, "lat": lat,
                    "lon": lon, "alt": alt, "roll": ang["roll"], "pitch": ang["pitch"], "yaw": ang["yaw"],
                    "group": o.get("cls") or ""})
    return out


def _export_meta(req) -> dict:
    from datetime import datetime, timezone

    from app.version import __version__
    return {"recorder": f"Signal Viewer {__version__}", "title": req.title,
            "recording_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


@router.post("/api/export/acmi")
async def export_acmi(req: AcmiRequest):
    """N8: the objects of a map / 3D view as a Tacview ACMI 2.2 text file (svcore/acmi.py). P1: the
    reply says the rate used (lowered for a long recording, svcore.acmi.fit_rate) and the objects left
    out because they have no position (P2)."""
    from svcore.acmi import fit_rate, write_acmi
    path = _check_target(req.path, ".acmi")

    def work():
        objs = acmi_objects(req.objects)
        rate = fit_rate(objs, req.rate)
        left: List[str] = []
        meta = _export_meta(req)
        body = write_acmi(objs, rate=rate, title=meta["title"], recorder=meta["recorder"],
                          recording_time=meta["recording_time"], left_out=left, places=req.places)
        with atomic_open(path, "w", "utf-8-sig", "\n") as f:
            f.write(body)
        return len(objs) - len(left), rate, left
    try:
        n, rate, left = await asyncio.to_thread(work)
    except KeyError:
        fail(404, "A signal of one of the objects is no longer open.")
    except ValueError as e:
        fail(400, str(e))
    return {"path": path, "objects": n, "size": os.path.getsize(path), "rate": rate,
            "lowered": rate < min(req.rate, 100.0) - 1e-9, "leftOut": left}


class TacviewCsvRequest(AcmiRequest):
    pass                              # `path` is the folder the files go into


@router.post("/api/export/tacview_csv")
async def export_tacview_csv(req: TacviewCsvRequest):
    """P1: Tacview CSV files - one per object - into a folder (svcore/tacview_csv.py)."""
    from svcore.acmi import fit_rate
    from svcore.tacview_csv import write_csvs
    folder = os.path.abspath(os.path.expanduser(req.path or ""))
    if not req.path:
        fail(400, "Choose the folder for the files.")
    parent = os.path.dirname(folder.rstrip(os.sep)) or folder
    if not os.path.isdir(folder) and not os.path.isdir(parent):
        fail(400, f"Folder not found: {parent}")

    def work():
        objs = acmi_objects(req.objects)
        rate = fit_rate(objs, req.rate)
        left: List[str] = []
        paths = write_csvs(objs, folder, rate, left_out=left)
        return paths, rate, left
    try:
        paths, rate, left = await asyncio.to_thread(work)
    except KeyError:
        fail(404, "A signal of one of the objects is no longer open.")
    except ValueError as e:
        fail(400, str(e))
    return {"path": folder, "files": paths, "objects": len(paths), "rate": rate,
            "lowered": rate < min(req.rate, 100.0) - 1e-9, "leftOut": left}


class KmlRequest(AcmiRequest):
    pass


@router.post("/api/export/kml")
async def export_kml(req: KmlRequest):
    """P1: the objects (and places) as one KML file for Google Earth (svcore/kml.py)."""
    from svcore.acmi import fit_rate
    from svcore.kml import write_kml
    path = _check_target(req.path, ".kml")

    def work():
        objs = acmi_objects(req.objects)
        rate = fit_rate(objs, req.rate)
        left: List[str] = []
        body = write_kml(objs, req.places, rate=rate, title=req.title, left_out=left)
        with atomic_open(path, "w", "utf-8", "\n") as f:
            f.write(body)
        return len(objs) - len(left), rate, left
    try:
        n, rate, left = await asyncio.to_thread(work)
    except KeyError:
        fail(404, "A signal of one of the objects is no longer open.")
    except ValueError as e:
        fail(400, str(e))
    return {"path": path, "objects": n, "size": os.path.getsize(path), "rate": rate,
            "lowered": rate < min(req.rate, 100.0) - 1e-9, "leftOut": left}


class StoryRequest(BaseModel):
    objects: List[dict] = []          # the Map's shown objects as the views fetch them (trackRequest), with names
    places: List[dict] = []
    primary: Optional[str] = None     # names
    secondary: Optional[str] = None
    events: List[dict] = []           # the app's timeline marks: [{t, text, level}]
    units: str = "metric"
    lang: str = "en"


@router.post("/api/story")
async def story(req: StoryRequest):
    """P10: the Story's moments of a Map in the app (svcore/story.py) - the same as the live page's."""
    from app import report as reports
    tab = {"plots": [{"mode": "3d", "scene": {"objects": req.objects, "primary": req.primary, "secondary": req.secondary},
                      "geo": {"places": req.places, "units": req.units}}]}
    replay = reports._replay({"events": req.events}) or {"events": []}
    return {"moments": await asyncio.to_thread(reports.story_of, store, tab, replay, "he" if req.lang == "he" else "en")}
