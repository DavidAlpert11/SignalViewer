"""Sweeps' report (HTML, Word, PDF, CSV, the plot alone) and where its answer comes from (each table read, with
its size, time and SHA-256). Split out of app/routes/sweep.py (2026-11-18); the tables stay there."""
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.common import atomic_path, atomic_write, fail
from app.routes.sweep import _TABLES, _answer, _drawn, _get, _recipe
from svcore import sweep

router = APIRouter()

class ReportReq(BaseModel):
    id: str
    question: Dict[str, Any]
    format: str                          # html | docx | pdf | csv
    path: str
    title: str = ""
    subtitle: str = ""
    notes: str = ""
    lang: str = "en"
    sections: List[Dict[str, Any]] = []  # [{title, items}] - the question, the process, in the user's language
    summary: List[List[Any]] = []        # [[what, value]]
    labels: Dict[str, str] = {}          # a column's name on screen, and a few headings (#answer, #best...)
    columns: List[str] = []              # the table's columns
    axes: List[str] = []                 # the plot's axes
    shown: Optional[List[int]] = None    # the sets on screen after the filters
    rows: Optional[List[int]] = None     # the table's sets, in its order (S04: only those that hold, sorted)
    top: int = 25
    include: Dict[str, bool] = {}
    mapX: Optional[str] = None
    mapY: Optional[str] = None
    maps: Optional[List[Dict[str, Any]]] = None   # S05: every map on screen [{x, y, rest}] (else mapX / mapY)
    iterations: Optional[List[Dict[str, Any]]] = None   # S08: [{n, label, sets, holding, best}] - each merge an iteration
    scatters: Optional[List[Dict[str, Any]]] = None     # S11: every point plot on screen [{x, y}]
    only: Optional[List[int]] = None                     # S14: the plot alone of only these sets
    style: Optional[Dict[str, Any]] = None              # S12: the plots' style (colour map, point size, grid...)
    colorBy: Optional[str] = None                        # the colour column of the plots
    raw: bool = False                    # plot: the raw table's runs instead of the parameter sets
    cap: Optional[int] = None            # raw: the most runs in the page (Settings; 0 = all), a sample above it


@router.post("/api/sweep/report")
def sweep_report(req: ReportReq):
    from app import sweep_report
    from app.report import ReportNeedsExtra
    ext = {"html": ".html", "docx": ".docx", "pdf": ".pdf", "csv": ".csv", "plot": ".html"}.get(req.format)
    if not ext:
        fail(400, "Unknown report format.")
    path = os.path.abspath(os.path.expanduser(req.path))
    if not path.lower().endswith(ext):
        path += ext
    if req.raw:                                        # the raw results' plot: the table's runs, no question
        df = _drawn(_get(req.id)["df"], req.cap)
        names = [c for c in (req.axes or list(df.columns)) if c in df.columns]
        try:
            atomic_write(path, sweep_report._html(sweep_report.plot_data(df, names), {**req.model_dump(), "axes": names, "plotOnly": True}, []))
        except OSError as e:
            fail(400, f"Could not write {path}: {e}")
        return {"path": path, "size": os.path.getsize(path)}
    p, a = _answer(req.id, req.question)
    body = {**req.model_dump(), "path": path}       # (the report is built into a temporary file below, O3)
    if (req.include or {}).get("provenance", True):
        L = req.labels or {}
        body["sections"] = [*(req.sections or []), {"title": L.get("#provenance", "Where it comes from"), "items": provenance(req.id)}]
    try:
        with atomic_path(path) as tmp:
            sweep_report.build(p, req.question, a, {**body, "path": tmp})
    except ReportNeedsExtra as e:
        fail(400, str(e))
    except OSError as e:
        fail(400, f"Could not write {path}: {e}")
    return {"path": path, "size": os.path.getsize(path)}


def provenance(tid: str) -> List[str]:
    """Where the answer comes from (S08): each table read - its size, time and SHA-256, so the same
    file can be found again - and the app's version."""
    import hashlib
    from app.version import __version__
    t = _TABLES.get(tid) or {}
    paths = sweep.recipe_files(_recipe(t)) if t else []
    out = []
    for path in [x for x in paths if x]:
        try:
            if os.path.isdir(path):
                n = len([f for f in os.listdir(path) if f.lower().endswith(sweep.io.TABLE_EXTS)])
                out.append(f"{path} - a folder of {n} tables")
                continue
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            st = os.stat(path)
            out.append(f"{path} - {st.st_size:,} bytes, {time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))}, SHA-256 {h.hexdigest()}")
        except OSError as e:
            out.append(f"{path} - could not be read now: {e.strerror or e}")
    out.append(f"Signal Viewer {__version__}")
    return out
