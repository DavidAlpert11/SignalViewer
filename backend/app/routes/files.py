"""Files: open / locate / upload / suggest, signal lists and previews, the open runs, log health."""

import asyncio
import os
import shutil
import tempfile
import time
from typing import List, Optional

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from app import prefs
from app.common import SUPPORTED, UPLOAD_DIR, _load_error, _log_signal_names, fail, open_with_prefs
from app.patterns import name_pattern as _name_pattern
from app.store import LoadError, store
from svcore.csv_loader import CSVImportSettings, detect_delimiter, preview_csv
from svcore.health import health as log_health
from svcore.mat_loader import choose_time, read_mat_vectors

router = APIRouter()




# =============================================================================
# FILES
# =============================================================================

class OpenRequest(BaseModel):
    paths: List[str]
    settings: Optional[dict] = None



@router.post("/api/files/open")
async def open_files(req: OpenRequest):
    opened, errors = [], []
    for p in req.paths:
        try:
            lr = await asyncio.to_thread(open_with_prefs, p, req.settings)
            opened.append(store.describe(lr))
        except LoadError as e:
            errors.append(_load_error(p, e))
        except Exception as e:  # never crash on bad data
            errors.append({"path": p, "message": f"Unexpected error while reading the file: {e}"})
    return {"opened": opened, "errors": errors}



class LocateItem(BaseModel):
    name: str
    size: int
    mtime: float                     # seconds (the browser's File.lastModified / 1000)



class LocateRequest(BaseModel):
    files: List[LocateItem]



def _locate_roots() -> List[str]:
    """Where dragged files usually come from: folders of open files, recently used folders,
    the last folder of the file dialog, and the usual user folders (OneDrive included)."""
    home = os.path.expanduser("~")
    roots = [os.path.dirname(lr.run.file_path) for lr in store.runs.values()]
    roots += [x.get("folder", "") for x in prefs.list_recent()]
    for base in (home, os.path.join(home, "OneDrive")):
        for sub in ("Desktop", "Downloads", "Documents", "שולחן העבודה", "מסמכים", "הורדות"):
            roots.append(os.path.join(base, sub))
    roots.append(home)
    seen, out = set(), []
    for r in roots:
        r = os.path.abspath(r) if r else ""
        if r and r not in seen and os.path.isdir(r) and not r.startswith(UPLOAD_DIR):
            seen.add(r); out.append(r)
    return out



LOCATE_DEPTH = 5            # folder levels searched below each root

LOCATE_SECONDS = 4.0        # time budget PER dropped file



def locate_file(name: str, size: int, mtime: float, deadline: float) -> Optional[str]:
    """The original of a dragged file: same name, same size, same modified time (2 s tolerance
    for FAT / zip timestamps). A browser hides the real path, so it is searched: first in the
    folders you work in (open files, recent files, the file dialog's last folder), then Desktop /
    Downloads / Documents, and only last the whole profile. The search stops at the first group of
    roots that contains the file. Only a single exact match counts - never a guess; if the same
    file exists in two places (a copy of the same file) it is opened as a copy instead."""
    found: List[str] = []
    for root in _locate_roots():
        queue = [(root, 0)]
        while queue and time.time() < deadline:
            folder, depth = queue.pop(0)
            try:
                with os.scandir(folder) as it:
                    for e in it:
                        try:
                            if e.is_file(follow_symlinks=False) and e.name == name:
                                st = e.stat()
                                path = os.path.abspath(e.path)
                                if st.st_size == size and abs(st.st_mtime - mtime) <= 2.0 and path not in found:
                                    found.append(path)
                            elif depth < LOCATE_DEPTH and e.is_dir(follow_symlinks=False) and not e.name.startswith((".", "$")) \
                                    and e.name not in ("node_modules", "AppData", "Library", "__pycache__", "Windows", "Program Files", "Program Files (x86)"):
                                queue.append((e.path, depth + 1))
                        except OSError:
                            continue
            except OSError:
                continue
        if len(found) > 1:
            return None                         # ambiguous: do not guess
        if found:
            return found[0]                     # found in this root: no need to search the rest
    return None



@router.post("/api/files/locate")
async def locate_files(req: LocateRequest):
    """Drag & drop: find each dropped file's ORIGINAL on disk, so it is opened from there
    (refresh and live mode then follow edits). Unfound files are uploaded as a copy instead."""
    out: list = []
    for f in req.files:
        deadline = time.time() + LOCATE_SECONDS
        out.append(await asyncio.to_thread(locate_file, os.path.basename(f.name), f.size, f.mtime, deadline))
    return {"paths": out}



@router.post("/api/files/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Drag & drop from the OS: the browser gives file contents, not paths."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    paths, skipped = [], []
    for f in files:
        name = os.path.basename(f.filename or "upload.csv")
        if not name.lower().endswith(SUPPORTED):
            skipped.append(name)       # reported to the user, never dropped silently
            continue
        dest_dir = tempfile.mkdtemp(dir=UPLOAD_DIR)
        dest = os.path.join(dest_dir, name)
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)
        paths.append(dest)
    return {"paths": paths, "skipped": skipped}



class SuggestRequest(BaseModel):
    path: str



@router.post("/api/files/suggest")
def suggest_files(req: SuggestRequest):
    """New runs for a saved file: files in the same folder with the same extension, newest
    first; 'best' is the newest one whose name has the same pattern (run_012 -> run_013)."""
    folder, name = os.path.dirname(req.path), os.path.basename(req.path)
    ext = os.path.splitext(name)[1].lower()
    if not os.path.isdir(folder):
        return {"candidates": [], "best": None}
    pat, cands = _name_pattern(name), []
    try:
        with os.scandir(folder) as it:
            for e in it:
                try:
                    if e.is_file() and e.name.lower().endswith(ext) and os.path.abspath(e.path) != os.path.abspath(req.path):
                        st = e.stat()
                        cands.append({"path": os.path.abspath(e.path), "name": e.name, "mtime": st.st_mtime,
                                      "size": st.st_size, "similar": _name_pattern(e.name) == pat})
                except OSError:
                    continue
    except OSError:
        return {"candidates": [], "best": None}
    cands.sort(key=lambda c: (not c["similar"], -c["mtime"]))
    best = next((c["path"] for c in cands if c["similar"]), None)
    return {"candidates": cands[:12], "best": best}



class SignalsRequest(BaseModel):
    path: str
    settings: Optional[dict] = None



@router.post("/api/files/signals")
def file_signals(req: SignalsRequest):
    """Signal names of a file WITHOUT loading its data (header / variable names), to check
    that a new run has what the saved layout needs."""
    if not os.path.isfile(req.path):
        fail(404, "File not found.")
    if req.path.lower().endswith((".bin", ".tlog", ".ulg")):
        try:
            return {"signals": _log_signal_names(req.path)}
        except Exception as e:
            fail(400, f"Could not read the flight log: {e}")
    if req.path.lower().endswith(".mat"):
        try:
            vectors = read_mat_vectors(req.path)
        except Exception as e:
            fail(400, f"Could not read MAT file: {e}")
        return {"signals": list(vectors.keys())}
    s = CSVImportSettings.from_dict({k: v for k, v in (req.settings or {}).items() if k != "format"})
    try:
        _rows, header = preview_csv(req.path, s, max_rows=1)
    except Exception as e:
        fail(400, f"Could not read the file: {e}")
    return {"signals": [h for h in header if h]}



class PreviewRequest(BaseModel):
    path: str
    settings: Optional[dict] = None



@router.post("/api/files/preview")
def preview(req: PreviewRequest):
    if not os.path.isfile(req.path):
        fail(404, "File not found.")
    if req.path.lower().endswith((".bin", ".tlog", ".ulg")):
        try:
            names = _log_signal_names(req.path)
        except Exception as e:
            fail(400, f"Could not read the flight log: {e}")
        return {"format": "bin", "variables": [{"name": n, "length": 0} for n in names], "timeColumn": "TimeUS", "length": 0}
    if req.path.lower().endswith(".mat"):
        try:
            vectors = read_mat_vectors(req.path)
        except Exception as e:
            fail(400, f"Could not read MAT file: {e}")
        tname, n = choose_time(vectors, (req.settings or {}).get("time_column"))
        return {"format": "mat", "variables": [{"name": k, "length": int(len(v))} for k, v in vectors.items()],
                "timeColumn": tname, "length": n}
    s = CSVImportSettings.from_dict(req.settings or {})
    rows, header = preview_csv(req.path, s, max_rows=12)
    detected = detect_delimiter(req.path, skip_rows=s.skip_rows or 0)
    return {"format": "csv", "header": header, "rows": rows, "detectedDelimiter": detected,
            "size": os.path.getsize(req.path)}



@router.get("/api/runs")
def list_runs():
    return store.list()



@router.delete("/api/runs/{run_id}")
def remove_run(run_id: str):
    store.remove(run_id)
    return {"ok": True}



class RunPatch(BaseModel):
    name: Optional[str] = None
    timeOffset: Optional[float] = None
    description: Optional[str] = None



@router.patch("/api/runs/{run_id}")
def patch_run(run_id: str, patch: RunPatch):
    try:
        if patch.name is not None:
            store.rename(run_id, patch.name)
        if patch.timeOffset is not None:
            store.set_time_offset(run_id, patch.timeOffset)
        if patch.description is not None:
            store.set_description(run_id, patch.description)
        return store.describe(store.get(run_id))
    except KeyError:
        fail(404, "File is not open.")



class ReplaceRequest(BaseModel):
    path: str



@router.post("/api/runs/{run_id}/replace")
async def replace_run(run_id: str, req: ReplaceRequest):
    try:
        lr = await asyncio.to_thread(store.replace_path, run_id, req.path)
        return store.describe(lr)
    except KeyError:
        fail(404, "File is not open.")
    except LoadError as e:
        fail(400, str(e))



@router.post("/api/runs/{run_id}/reload")
async def reload_run(run_id: str):
    try:
        lr = await asyncio.to_thread(store.reload, run_id)
        return store.describe(lr)
    except KeyError:
        fail(404, "File is not open.")
    except LoadError as e:
        fail(400, str(e))



@router.get("/api/runs/{run_id}/health")
def run_health(run_id: str):
    """Automatic checks of a flight log (vibration, GPS, battery, EKF, motors, board power, errors)."""
    lr = store.runs.get(run_id)
    if lr is None:
        fail(404, "This file is no longer open.")
    res = log_health(lr.run)
    if res is None:
        fail(404, "Nothing to check in this file.")
    return res              # times already include the file's time offset (as on the plots)



@router.get("/api/runs/{run_id}/log")
def run_log(run_id: str):
    """Parameters and events (messages, mode changes, events, errors) of a flight log."""
    info = store.log_info(run_id)
    if info is None:
        fail(404, "This file has no flight-log parameters or messages.")
    return info
