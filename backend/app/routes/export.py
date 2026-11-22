"""Export and reports: CSV, HTML / PDF / Word reports, images, saved text."""

import asyncio
import base64
import os
import re
import urllib.parse
from typing import Dict, List, Optional

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel

from app import report as reports
from svcore.atomic import write_text as _write_text
from app.common import atomic_open, atomic_path, atomic_write, fail, heavy
from app.store import store

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
    """The plot's quick Export CSV: its signals on the first signal's time base, inside [t0, t1], full
    resolution (E1: written by svcore.subset, as Export recording… is)."""
    from svcore import subset
    path = _check_target(req.path, ".csv")

    def work():
        sub = subset.from_store(store, req.signals, timing="first", t0=req.t0, t1=req.t1, alignment=req.alignment)
        subset.write(path, sub, sidecar=False)
        return len(sub.t)
    return await _run_subset(work, path)


async def _run_subset(work, path: str) -> dict:
    from svcore.subset import SubsetError
    try:
        rows = await asyncio.to_thread(work)
    except KeyError:
        fail(404, "One of the signals is no longer open.")
    except (SubsetError, ValueError) as e:
        fail(400, str(e))
    return {"path": path, "rows": rows}


class ExportRecordingRequest(BaseModel):
    path: str                         # its extension is the format: .csv .parquet .mat .h5
    signals: List[dict]               # [{id, label, unit, scale, offset, tOffset}] - one run's
    t0: Optional[float] = None
    t1: Optional[float] = None
    where: str = ""                   # only where this condition holds (Investigate's language)
    margin: float = 0.0               # s kept before and after each stretch
    rate: Optional[float] = None      # Hz: one time base; None: as recorded (the fastest signal's samples)
    antialias: bool = True
    fromZero: bool = False
    source: str = ""                  # the recording's file, for the sidecar


@router.post("/api/export/recording")
async def export_recording(req: ExportRecordingRequest):
    """E1: a part of a recording as a new file (svcore/subset.py) and `<file>.export.json` beside it."""
    from app.version import __version__
    from svcore import subset
    ext = os.path.splitext(req.path)[1].lower()
    path = _check_target(req.path, ext if ext in (*subset.FORMATS, ".hdf5") else ".csv")

    def work():
        sub = subset.from_store(store, req.signals, where=req.where, margin=req.margin,
                                timing="rate" if req.rate else "fastest", rate=req.rate, t0=req.t0, t1=req.t1,
                                antialias=req.antialias, from_zero=req.fromZero)
        subset.write(path, sub, {"recorder": f"Signal Viewer {__version__}", "source": req.source})
        return len(sub.t)
    return await _run_subset(work, path)



class ReportRequest(BaseModel):
    path: str
    format: str = "html"             # html | pdf | docx | tex (a LaTeX project, .zip) | texpdf (typeset by LaTeX)
    engine: str = ""                 # RE3: xelatex | lualatex | pdflatex (default: the best on this computer)
    title: str = ""
    intro: str = ""
    summary: str = ""
    lang: str = "en"
    theme: str = "light"
    tabs: List[dict] = []
    notes: List[dict] = []          # the user's notes: [{t, text}]
    sections: List[dict] = []       # investigation: [{title, text?, items?, table?: {head, rows}}]
    replay: Optional[dict] = None   # R1: a replay page - {t, extent, events: [{t, text, level}]} (report.build_html)
    # RE1: the report the user wrote (app/reportdoc.py): Markdown with markers, what each marker stands for,
    # the callouts' words in the report's language, the folder a relative picture is read from
    text: Optional[str] = None
    items: List[dict] = []
    words: Dict[str, str] = {}
    base: str = ""
    assets: Dict[str, dict] = {}    # RE2: the pictures kept in the session ({id: {name, mime, data}}), written asset:<id>



REPORT_EXT = {"html": ".html", "pdf": ".pdf", "docx": ".docx", "tex": ".zip", "texpdf": ".pdf"}


@router.post("/api/report")
async def make_report(req: ReportRequest):
    ext = REPORT_EXT.get(req.format)
    if not ext:
        fail(400, "Unknown report format.")
    path = _check_target(req.path, ext)
    body = req.model_dump()
    if req.format in ("tex", "texpdf") and req.text is not None:
        from app.reportdoc import build_doc
        from svcore.latex import LatexError
        try:
            with atomic_path(path) as tmp:
                await heavy(build_doc, store, body, req.format, tmp)
        except LatexError as e:
            fail(400, str(e))
        return {"path": path, "size": os.path.getsize(path)}

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


class PartsRequest(BaseModel):
    runs: Optional[List[str]] = None
    streams: Optional[List[dict]] = None          # MSG1: ws.messageStreams - the streams the user defined


@router.post("/api/report/parts")
async def report_parts(req: PartsRequest):
    """RE2: what the report's ready-made parts would find in the open files (the Report screen's library): the
    commanded / measured pairs, the map objects and the guessed reference, the state signals, the tracks."""
    from app.reportparts import scan
    return await heavy(scan, store, req.runs, req.streams)


@router.post("/api/report/preview")
async def report_preview(req: ReportRequest):
    body = req.model_dump()
    from app.reportlatex import is_latex_doc
    if req.text is not None and is_latex_doc(req.text):     # RE3: a LaTeX document - the PDF this computer's TeX makes
        from app.reportlatex import preview
        return await heavy(preview, store, body)
    if req.text is not None:                  # RE1: the written report, exactly as its .html file will be
        from app.reportdoc import build_doc_html
        html_text = await heavy(build_doc_html, store, body)
    else:
        html_text = await asyncio.to_thread(reports.build_html, store, body)
    return {"html": html_text}



class ClipRequest(BaseModel):
    path: str                       # where the page (every sample) is saved - the file attached to the Confluence page
    title: str = ""
    lang: str = "en"
    theme: str = "light"
    tabs: List[dict] = []           # one tab (the tab copied) or one tab with the one plot copied
    notes: List[dict] = []
    macro: str = "html"             # CP3: "html" - the HTML macro's lines; "user" - the Signal Viewer user macro's markup
    scale: float = 1                # CP7: the static copy's pictures - 2 or 3 times the pixels (Settings: Copied pictures)


@router.post("/api/export/clip")
async def export_clip(req: ClipRequest):
    """CP1: a plot or a tab for a Confluence page. The page with every sample is saved at `path` (dragged onto the
    Confluence page: an attachment); `macro`: the HTML macro's lines that show that attachment (text/plain on the
    clipboard); `static`: picture + statistics + notes without scripts (text/html: a page, Word, an e-mail)."""
    body = req.model_dump()
    if not any(t.get("plots") for t in body["tabs"]):
        fail(400, "Nothing to copy: the plot or tab has no lines.")
    path = _check_target(req.path, ".html")
    if req.macro == "user" and any(c in os.path.basename(path) for c in "|{}"):
        fail(400, "Confluence's markup cannot carry | { or } in a file name: save the page under another name.")
    try:
        page = await asyncio.to_thread(reports.build_clip_page, store, body)
        static = await asyncio.to_thread(reports.build_clip_static, store, body)
    except KeyError:
        fail(404, "One of the plot's signals is no longer open.")
    await asyncio.to_thread(atomic_write, path, page)
    return {"path": path, "name": os.path.basename(path), "size": len(page.encode("utf-8")),
            "macro": (reports.build_clip_markup if req.macro == "user" else reports.build_clip_macro)(body, os.path.basename(path)),
            "static": static}


class ConfluenceSend(BaseModel):
    page: str                       # the Confluence page's link (or its id)
    title: str = ""
    lang: str = "en"
    theme: str = "light"
    tabs: List[dict] = []
    notes: List[dict] = []
    macro: str = "html"             # the macro the page gets: "html" or "user" (the Signal Viewer user macro)
    name: str = ""                  # the attachment's name (default: from the title)
    where: str = "end"              # CP6: "end", "start", "after:<heading index>" (a marker in the page wins)


class ConfluenceSettings(BaseModel):
    url: Optional[str] = None
    user: Optional[str] = None
    token: Optional[str] = None


_last_page: Dict[str, str] = {}     # the page last sent to - the only address /api/confluence/open opens


@router.get("/api/confluence")
def confluence_get():
    """CP4: the Confluence settings the page may see (never the token)."""
    from app import confluence
    return confluence.public()


@router.post("/api/confluence")
def confluence_set(req: ConfluenceSettings):
    from app import confluence
    try:
        return confluence.save(req.url, req.user, req.token)
    except confluence.ConfluenceError as e:
        fail(400, str(e))


@router.post("/api/confluence/test")
async def confluence_test():
    from app import confluence
    try:
        return await asyncio.to_thread(confluence.test)
    except confluence.ConfluenceError as e:
        fail(400, str(e))


@router.post("/api/export/confluence")
async def export_confluence(req: ConfluenceSend):
    """CP4: Send to Confluence - the plot or tab's page (every sample) attached to the page and its macro added."""
    from app import confluence
    body = req.model_dump()
    if not any(t.get("plots") for t in body["tabs"]):
        fail(400, "Nothing to send: the plot or tab has no lines.")
    name = req.name.strip() or confluence.safe_name(req.title)
    if not name.lower().endswith(".html"):
        name += ".html"
    try:
        page = await asyncio.to_thread(reports.build_clip_page, store, body)
    except KeyError:
        fail(404, "One of the plot's signals is no longer open.")
    try:
        out = await asyncio.to_thread(confluence.send, req.page, page, name, req.macro,
                                      reports._clip_height(body), reports.build_clip_macro(body, name), req.where, req.title)
    except confluence.ConfluenceError as e:
        fail(400, str(e))
    _last_page["url"] = out["url"]
    return out


class ConfluenceOutline(BaseModel):
    page: str
    title: str = ""
    name: str = ""


@router.post("/api/confluence/outline")
async def confluence_outline(req: ConfluenceOutline):
    """CP6: where on the page it can go - its headings, a marker waiting for it, whether it is there already."""
    from app import confluence
    name = req.name.strip() or confluence.safe_name(req.title)
    try:
        return await asyncio.to_thread(confluence.outline, req.page, req.title, name)
    except confluence.ConfluenceError as e:
        fail(400, str(e))


@router.post("/api/confluence/open")
def confluence_open():
    """The page last sent to, in the user's browser (the address Confluence gave - never one from the page)."""
    import webbrowser
    url = _last_page.get("url")
    if not url:
        fail(400, "Nothing was sent to Confluence yet.")
    try:
        return {"opened": bool(webbrowser.open(url, new=2)), "url": url}
    except Exception:
        return {"opened": False, "url": url}


# CP5 (owner, 2026-11-22: "hold the plot or the tab by its grip and drag it out - to Confluence or any file; HTML by
# default"): a plot or a tab dragged out of the window. The page says at the drag's start what it is (POST) and gives
# the system a link (DownloadURL) it fetches when the drag ends on a folder or the desktop: the report's page of it,
# every sample. A link is known to the page that made it only (a random token) and is forgotten after 15 minutes.
_drags: Dict[str, Dict] = {}


class DragRegister(BaseModel):
    token: str
    title: str = ""
    lang: str = "en"
    theme: str = "light"
    tabs: List[dict] = []
    notes: List[dict] = []
    macro: str = "html"


@router.post("/api/export/drag")
def export_drag(req: DragRegister):
    import time
    if not re.fullmatch(r"[A-Za-z0-9-]{16,64}", req.token):
        fail(400, "A drag's token is 16-64 letters, digits or dashes.")
    now = time.time()
    for k in [k for k, v in _drags.items() if now - v["at"] > 900]:
        _drags.pop(k, None)
    while len(_drags) >= 32:
        _drags.pop(next(iter(_drags)))
    _drags[req.token] = {"at": now, "body": req.model_dump()}
    return {"ok": True}


@router.get("/api/export/drag/{token}/{name}")
async def export_drag_file(token: str, name: str, view: int = 0):
    """The dragged plot or tab as its interactive page - fetched by the system when the drag ends on a folder (a file),
    or opened by a browser it was dropped on (?view=1: shown, not downloaded - CP5)."""
    import time
    from fastapi.responses import Response
    end = time.time() + 5                       # the page's POST may still be on its way when the drop is quick
    while token not in _drags and time.time() < end:
        await asyncio.sleep(0.05)
    d = _drags.get(token)
    if not d:
        fail(404, "That drag is over - drag the plot again.")
    try:
        page = await asyncio.to_thread(reports.build_html, store, d["body"])
    except KeyError:
        fail(404, "One of the plot's signals is no longer open.")
    safe = re.sub(r'[\\/:*?"<>|]+', "_", name) or "signalviewer.html"
    disp = "inline" if view else "attachment"
    return Response(page, media_type="text/html; charset=utf-8",
                    headers={"Content-Disposition": disp + "; filename*=UTF-8''" + urllib.parse.quote(safe)})


@router.get("/api/export/clip/user-macro")
def clip_user_macro():
    """CP3: the Signal Viewer user macro's template - a Confluence administrator installs it once."""
    return {"name": reports.USER_MACRO, "template": reports.build_user_macro_template()}


class ImageBytes(BaseModel):
    plot: dict
    theme: str = "light"
    scale: float = 2
    lang: str = "en"


@router.post("/api/export/image-bytes")
async def export_image_bytes(req: ImageBytes):
    """CP7 (owner, 2026-11-22: "a copy as a high-resolution picture"): the plot as a PNG drawn again from the data at
    `scale` times the pixels (1-4), for the clipboard - nothing saved."""
    from fastapi.responses import Response
    try:
        data = await asyncio.to_thread(reports.build_image, store, req.plot, "png", req.theme, max(1.0, min(4.0, req.scale)))
    except KeyError:
        fail(404, "One of the plot's signals is no longer open.")
    return Response(data, media_type="image/png")


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


# ----------------------------------------------------------------------------- RE3: LaTeX

@router.get("/api/report/tex")
def report_tex_status():
    """What LaTeX this computer has (engines, latexmk, the converters a formula needs) - nothing is fetched."""
    from svcore import latex as TX
    from app import prefs
    chosen = prefs._read("settings.json", {}).get("texDir")
    TX.set_dir(chosen if isinstance(chosen, str) and chosen.strip() else None)
    return TX.status()


@router.get("/api/report/tex/pdf/{token}")
def report_tex_pdf(token: str):
    """A LaTeX document's preview PDF (served to the Report screen, inline)."""
    from fastapi.responses import FileResponse
    from app.reportlatex import preview_pdf
    p = preview_pdf(token)
    if not p:
        fail(404, "This preview is gone - it is made again when the text changes.")
    return FileResponse(p, media_type="application/pdf", headers={"Content-Disposition": "inline; filename=preview.pdf", "Cache-Control": "no-store"})


@router.post("/api/report/tex/open")
def report_tex_open(req: OpenRequest):
    """The preview PDF in the computer's own PDF viewer (a window with no built-in PDF view)."""
    import webbrowser
    from pathlib import Path
    from app.reportlatex import preview_pdf
    p = preview_pdf(req.path)
    if not p:
        fail(404, "This preview is gone - it is made again when the text changes.")
    return {"opened": bool(webbrowser.open(Path(p).as_uri(), new=2))}


class ToLatexRequest(BaseModel):
    text: str
    lang: str = "en"
    title: str = ""
    words: Dict[str, str] = {}


@router.post("/api/report/tolatex")
def report_to_latex(req: ToLatexRequest):
    """A Markdown report as a LaTeX document to edit (the page keeps its references: ⟦n⟧ markers, put back)."""
    from app.reportlatex import to_latex
    return {"text": to_latex(req.text, req.lang, req.words, req.title)}
