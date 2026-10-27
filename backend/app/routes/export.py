"""Export and reports: CSV, HTML / PDF / Word reports, images, saved text."""

import asyncio
import base64
import os
from typing import List, Optional

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel

from app import report as reports
from app.common import fail
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
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
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



@router.post("/api/report")
async def make_report(req: ReportRequest):
    ext = {"html": ".html", "pdf": ".pdf", "docx": ".docx"}.get(req.format)
    if not ext:
        fail(400, "Unknown report format.")
    path = _check_target(req.path, ext)
    body = req.model_dump()

    def work():
        if req.format == "html":
            with open(path, "w", encoding="utf-8") as f:
                f.write(reports.build_html(store, body))
        elif req.format == "pdf":
            reports.build_pdf(store, body, path)
        else:
            reports.build_docx(store, body, path)
    try:
        await asyncio.to_thread(work)
    except KeyError:
        fail(404, "One of the signals in the report is no longer open.")
    except reports.ReportNeedsExtra as e:
        fail(400, str(e))
    return {"path": path, "size": os.path.getsize(path)}



@router.post("/api/report/preview")
async def report_preview(req: ReportRequest):
    html_text = await asyncio.to_thread(reports.build_html, store, req.model_dump())
    return {"html": html_text}



class ImageRequest(BaseModel):
    path: str
    format: str = "png"              # png | svg
    theme: str = "light"
    plot: dict



@router.post("/api/export/image")
async def export_image(req: ImageRequest):
    if req.format not in ("png", "svg"):
        fail(400, "Unknown image format.")
    path = _check_target(req.path, "." + req.format)
    data = await asyncio.to_thread(reports.build_image, store, req.plot, req.format, req.theme)
    with open(path, "wb") as f:
        f.write(data)
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
    with open(path, "w", encoding="utf-8-sig" if req.bom else "utf-8", newline="") as f:
        f.write(req.content)
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
    with open(path, "wb") as f:
        f.write(raw)
    return {"path": path}
