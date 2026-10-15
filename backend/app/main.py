"""
Signal Viewer - local API server.

Runs only on 127.0.0.1. The React UI (frontend/dist) is served from the same
origin. All heavy work happens here, on full-resolution data; the UI receives
only decimated display points (binary-packed, base64) and computed values.
"""

import asyncio
import subprocess
import sys
import re
import math
import time
import base64
import json
import os
import shutil
import string
import tempfile
from typing import Dict, List, Optional

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from svcore.csv_loader import CSVImportSettings, detect_delimiter, preview_csv
from svcore.decimate import decimate_for_view, hold_at, interp_at
from svcore.ops import compute_signal_stats
from svcore.mat_loader import read_mat_vectors, choose_time
from svcore.bin_loader import bin_signal_names
from svcore.health import health as log_health
from svcore.sync import suggest as sync_suggest_fn
from svcore.analysis import state_mask, spectrogram as make_spectrogram


def _log_signal_names(path: str):
    if path.lower().endswith(".bin"):
        return bin_signal_names(path)
    from svcore.tlog_loader import load_tlog
    from svcore.ulog_loader import load_ulog
    run, _ = (load_tlog if path.lower().endswith(".tlog") else load_ulog)(path, os.path.basename(path))
    return list(run.signals) if run else []

from app.store import LoadError, store
from svcore.limits import check_limits
from svcore.envelope import envelope
from svcore.analysis import OpError, OPS, align_to, fft_display, fft_for, transitions, xy_pair
from svcore.compare import auto_shift, compare as compare_runs
from app import report as reports
from app.jobs import jobs, JobCancelled
from app import prefs

APP_DIR = os.path.join(os.path.expanduser("~"), ".signalviewer")
UPLOAD_DIR = os.path.join(APP_DIR, "uploads")
AUTOSAVE = os.path.join(APP_DIR, "autosave.json")
DIST = os.environ.get("SV_DIST") or os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
SUPPORTED = (".csv", ".txt", ".tsv", ".dat", ".mat", ".bin", ".tlog", ".ulg")

class SafeJSONResponse(JSONResponse):
    """JSON cannot carry NaN or infinity: any that slips into a response becomes null
    instead of failing the whole request with a server error."""
    def render(self, content) -> bytes:
        def clean(v):
            if isinstance(v, float):
                return v if math.isfinite(v) else None
            if isinstance(v, dict):
                return {k: clean(x) for k, x in v.items()}
            if isinstance(v, (list, tuple)):
                return [clean(x) for x in v]
            if isinstance(v, np.generic):
                return clean(v.item())
            return v
        return json.dumps(clean(content), ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


app = FastAPI(default_response_class=SafeJSONResponse, title="Signal Viewer", docs_url="/api/docs")


# =============================================================================
# LOCAL-ONLY GUARD
# =============================================================================
# Binding to 127.0.0.1 keeps other computers out, but not a web page open in the user's own
# browser: with DNS rebinding such a page can make "evil.example" resolve to 127.0.0.1 and then
# read folders, open files and write files through this API. Browsers always send the name
# they used in Host / Origin, so answering only to loopback names closes that door.
# SV_ALLOWED_HOSTS (comma separated names) adds names on purpose, e.g. for the test client.

_LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}


def _hostname(value: str) -> str:
    """'127.0.0.1:8765' -> '127.0.0.1', '[::1]:8765' -> '::1', 'http://localhost:5173' -> 'localhost'."""
    v = value.strip().lower()
    if "://" in v:
        v = v.split("://", 1)[1].split("/", 1)[0]
    if v.startswith("["):
        return v[1:].split("]", 1)[0]
    return v.rsplit(":", 1)[0] if v.count(":") == 1 else v


def _allowed_names() -> set:
    extra = os.environ.get("SV_ALLOWED_HOSTS", "")
    return _LOOPBACK_NAMES | {x.strip().lower() for x in extra.split(",") if x.strip()}


class LocalOnlyMiddleware:
    """Plain ASGI middleware (no buffering, so downloads and long jobs are unaffected)."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.inner(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        ok = _allowed_names()
        host = headers.get("host")
        origin = headers.get("origin")
        bad = None
        if host is None or _hostname(host) not in ok:
            bad = "this server only answers requests addressed to localhost"
        elif origin is not None and (origin == "null" or _hostname(origin) not in ok):
            bad = "requests from other web sites are not accepted"
        if bad is None:
            return await self.inner(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        body = json.dumps({"detail": f"Blocked: {bad}. Open Signal Viewer at http://127.0.0.1:<port>."}).encode()
        await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


app.add_middleware(LocalOnlyMiddleware)


def b64(a: np.ndarray, dtype) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype=dtype).tobytes()).decode("ascii")


def fail(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


# =============================================================================
# FILES
# =============================================================================

class OpenRequest(BaseModel):
    paths: List[str]
    settings: Optional[dict] = None


def open_with_prefs(path: str, settings: Optional[dict]):
    """
    Explicit settings win (and are remembered for the folder). Otherwise auto-detection
    comes FIRST; the folder's remembered settings are used only when auto-detection does
    not recognise the file (it fails, or finds no time column by name). Applying them
    blindly would silently misread other files that live in the same folder.
    """
    if settings is not None:
        lr = store.open_file(path, settings)
        prefs.remember_import(path, settings)
    else:
        remembered = prefs.import_for(path)
        auto, auto_err = None, None
        try:
            auto = store.open_file(path, None)
        except LoadError as e:
            auto_err = e
        lr = auto
        if remembered and (auto is None or not auto.run.load_report.get("timeByName", True)):
            try:
                alt = store.open_file(path, remembered)
                if auto is None or alt.run.load_report.get("timeByName"):
                    if auto is not None:
                        store.remove(auto.id)
                    lr = alt
                    lr.load_report["rememberedSettings"] = True
                else:
                    store.remove(alt.id)
            except LoadError:
                pass
        if lr is None:
            raise auto_err or LoadError("Could not read this file.")
    prefs.add_recent(path, "file")
    return lr


def _load_error(path: str, e: Exception) -> dict:
    out = {"path": path, "message": str(e)}
    if getattr(e, "code", None):
        out["code"] = e.code
        out["params"] = getattr(e, "params", {}) or {}
    return out


@app.post("/api/files/open")
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


@app.post("/api/files/locate")
async def locate_files(req: LocateRequest):
    """Drag & drop: find each dropped file's ORIGINAL on disk, so it is opened from there
    (refresh and live mode then follow edits). Unfound files are uploaded as a copy instead."""
    out = []
    for f in req.files:
        deadline = time.time() + LOCATE_SECONDS
        out.append(await asyncio.to_thread(locate_file, os.path.basename(f.name), f.size, f.mtime, deadline))
    return {"paths": out}


@app.post("/api/files/upload")
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


from app.patterns import name_pattern as _name_pattern


@app.post("/api/files/suggest")
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


@app.post("/api/files/signals")
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


@app.post("/api/files/preview")
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


@app.get("/api/runs")
def list_runs():
    return store.list()


@app.delete("/api/runs/{run_id}")
def remove_run(run_id: str):
    store.remove(run_id)
    return {"ok": True}


class RunPatch(BaseModel):
    name: Optional[str] = None
    timeOffset: Optional[float] = None
    description: Optional[str] = None


@app.patch("/api/runs/{run_id}")
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


@app.post("/api/runs/{run_id}/replace")
async def replace_run(run_id: str, req: ReplaceRequest):
    try:
        lr = await asyncio.to_thread(store.replace_path, run_id, req.path)
        return store.describe(lr)
    except KeyError:
        fail(404, "File is not open.")
    except LoadError as e:
        fail(400, str(e))


@app.post("/api/runs/{run_id}/reload")
async def reload_run(run_id: str):
    try:
        lr = await asyncio.to_thread(store.reload, run_id)
        return store.describe(lr)
    except KeyError:
        fail(404, "File is not open.")
    except LoadError as e:
        fail(400, str(e))


# Live mode. Start: the UI refreshes every file (job "reloadAll"), then calls /start, then polls
# once a second. A poll reads only what was ADDED to each file, says how long ago each file last
# grew (so the UI can show which files are still being written), and every few seconds looks for
# NEW files next to the open ones (same name pattern) that appeared since live mode started.
LIVE = {"since": None, "reported": set(), "last_scan": 0.0}


class StreamStart(BaseModel):
    lookBack: float = 0.0          # also report files created up to this many seconds before now


@app.post("/api/stream/start")
def stream_start(req: StreamStart = StreamStart()):
    LIVE["since"] = time.time() - max(0.0, req.lookBack)
    LIVE["reported"] = set()
    LIVE["last_scan"] = 0.0
    for lr in store.runs.values():
        lr.last_change = 0.0
    return {"ok": True}


@app.post("/api/stream/stop")
def stream_stop():
    LIVE["since"] = None
    return {"ok": True}


@app.post("/api/stream/poll")
async def stream_poll():
    changed = await asyncio.to_thread(store.poll_appends)
    new_files = []
    now = time.time()
    if LIVE["since"] is not None and now - LIVE["last_scan"] >= 2.0:
        LIVE["last_scan"] = now
        found = await asyncio.to_thread(store.new_files, LIVE["since"], LIVE["reported"])
        for f in found:
            LIVE["reported"].add(f["path"])
        new_files = found
    return {"changed": changed, "runs": store.list() if changed else None,
            "errors": getattr(store, "poll_errors", {}), "activity": store.activity(), "newFiles": new_files}


# =============================================================================
# DATA
# =============================================================================

class DataRequest(BaseModel):
    signals: List[str]
    x0: Optional[float] = None
    x1: Optional[float] = None
    points: int = 4000


@app.post("/api/data")
def get_data(req: DataRequest):
    """Display points for each signal: min/max decimated inside [x0, x1], coarse outside."""
    out = []
    points = int(max(200, min(req.points, 20000)))
    for sid in req.signals:
        try:
            t, y = store.signal(sid)
        except KeyError:
            out.append({"id": sid, "missing": True})
            continue
        rng = [req.x0, req.x1] if req.x0 is not None and req.x1 is not None else None
        xd, yd, dec = decimate_for_view(t, y, rng, points)
        out.append({"id": sid, "n": int(len(xd)), "total": int(len(t)), "decimated": bool(dec),
                    "x": b64(xd, np.float64), "y": b64(yd, np.float32)})
    return {"series": out}


class CursorRequest(BaseModel):
    signals: List[str]
    t: float


@app.post("/api/cursor")
def cursor_values(req: CursorRequest):
    vals: Dict[str, Optional[float]] = {}
    for sid in req.signals:
        try:
            t, y = store.signal(sid)
            # states, text values and other discrete signals: the value in force, never interpolated
            v = hold_at(t, y, req.t) if store.is_state(sid) else interp_at(t, y, req.t)
            vals[sid] = None if v is None or not np.isfinite(v) else float(v)
        except KeyError:
            vals[sid] = None
    return {"t": req.t, "values": vals}


class NeighborRequest(BaseModel):
    signal: str
    t: float
    steps: int = 1          # > 0: forward, < 0: backward (in samples)


@app.post("/api/neighbor")
def neighbor(req: NeighborRequest):
    """Time of the sample `steps` samples after / before time `t` (no interpolation):
    what the arrow keys use to move the cursor from one recorded value to the next."""
    try:
        t, _ = store.signal(req.signal)
    except KeyError:
        fail(404, "Signal not found.")
    n = len(t)
    if n == 0:
        return {"t": req.t, "index": None}
    k = int(req.steps)
    if k >= 0:
        i = int(np.searchsorted(t, req.t, side="right")) + max(0, k - 1)   # first sample after t
        if k == 0:
            i = max(0, int(np.searchsorted(t, req.t, side="left")))
    else:
        i = int(np.searchsorted(t, req.t, side="left")) - 1 - (-k - 1)     # last sample before t
    i = min(n - 1, max(0, i))
    return {"t": float(t[i]), "index": i}


class StatsRequest(BaseModel):
    signals: List[str]
    t0: Optional[float] = None
    t1: Optional[float] = None
    state: Optional[str] = None             # only where this state signal ...
    stateValues: Optional[List[float]] = None   # ... is one of these values
    stateOffset: float = 0.0                # the state signal's display time shift relative to these


def _stretches(sig_id: str, st, sy, offset: float = 0.0):
    """A state signal as stretches [(start, end, value)]: each change to the next one; the last
    lasts to the end of its file. Shared by "statistics while state = X" and the segment list."""
    pts, _c, end = transitions(st, sy, cap=10 ** 9)
    lr = store.runs.get(sig_id.partition("/")[0])
    if lr is not None and end is not None:
        end = max(end, float(lr.run.end_time) + float(lr.run.time_offset or 0) + offset)
    out = []
    for i, (a, v) in enumerate(pts):
        b = pts[i + 1][0] if i + 1 < len(pts) else end
        if v is not None and b is not None:
            out.append((float(a), float(b), float(v)))
    return out


class LimitItem(BaseModel):
    id: str
    lo: Optional[float] = None
    hi: Optional[float] = None
    scale: float = 1.0
    offset: float = 0.0
    tOffset: float = 0.0


class LimitsRequest(BaseModel):
    items: List[LimitItem]
    t0: Optional[float] = None          # plot time (time offsets included); None = whole signal
    t1: Optional[float] = None


@app.post("/api/limits")
def limits(req: LimitsRequest):
    """T13: pass / fail of each signal against its limits, on the values as plotted."""
    out = {}
    for it in req.items:
        try:
            t, y = store.signal(it.id)
        except KeyError:
            continue
        tt = np.asarray(t, dtype=np.float64) + it.tOffset
        yy = np.asarray(y, dtype=np.float64) * (it.scale or 1.0) + it.offset
        out[it.id] = check_limits(tt, yy, it.lo, it.hi, req.t0, req.t1)
    return {"results": out}


class EnvelopeRequest(BaseModel):
    signals: List[dict]                 # [{id, scale, offset, tOffset}] - as plotted
    t0: Optional[float] = None
    t1: Optional[float] = None
    points: int = 2000
    pct: float = 5.0


@app.post("/api/envelope")
def envelope_view(req: EnvelopeRequest):
    """T14: the plot's signals (many runs of one quantity) as min/max, percentile band and median."""
    series, ids = [], []
    for s in req.signals:
        try:
            t, y = store.signal(s["id"])
        except KeyError:
            continue
        series.append((np.asarray(t, dtype=np.float64) + float(s.get("tOffset") or 0),
                       np.asarray(y, dtype=np.float64) * float(s.get("scale", 1) or 1) + float(s.get("offset") or 0)))
        ids.append(s["id"])
    r = envelope(series, req.t0, req.t1, req.points, max(0.0, min(req.pct, 49.0)))
    if r is None:
        return {"n": len(ids), "empty": True}
    enc = lambda a, dt=np.float32: b64(np.asarray(a), dt)
    return {"n": len(ids), "pct": r["pct"], "t": enc(r["t"], np.float64),
            **{k: enc(r[k]) for k in ("min", "max", "lo", "median", "hi")},
            "runs": [{"id": i, "deviation": d, "outlier": o} for i, d, o in zip(ids, r["deviation"], r["outlier"])]}


class SegmentsRequest(BaseModel):
    signal: str
    limit: int = 2000


@app.post("/api/segments")
def segments(req: SegmentsRequest):
    """T10: a state signal (flight mode, gear...) split into its stretches, with the text of each
    value when the signal has labels, and the total time per value."""
    try:
        st, sy = store.signal(req.signal)
    except KeyError:
        fail(404, "This signal is no longer open.")
    st = np.asarray(st, dtype=np.float64)
    parts = _stretches(req.signal, st, sy)
    labels = store.labels(req.signal) or {}
    lab = lambda v: labels.get(int(v), None) if float(v).is_integer() else None
    totals: Dict[float, list] = {}
    for a, b, v in parts:
        tot = totals.setdefault(v, [0.0, 0])
        tot[0] += b - a; tot[1] += 1
    return {
        "segments": [{"t0": a, "t1": b, "value": v, "label": lab(v)} for a, b, v in parts[:max(1, req.limit)]],
        "total": len(parts),
        "byValue": [{"value": v, "label": lab(v), "duration": d, "count": n}
                    for v, (d, n) in sorted(totals.items(), key=lambda kv: -kv[1][0])],
    }


@app.post("/api/stats")
def stats(req: StatsRequest):
    res = {}
    where = None
    seg_total, seg_count = 0.0, 0
    if req.state and req.stateValues:
        try:
            st, sy = store.signal(req.state)
            st = np.asarray(st, dtype=np.float64) + req.stateOffset
            where = (st, sy)
        except KeyError:
            fail(404, "The state signal is no longer open.")
        want = set(float(v) for v in req.stateValues)
        for a, b, v in _stretches(req.state, st, sy, req.stateOffset):
            if float(v) not in want:
                continue
            a2, b2 = max(a, req.t0) if req.t0 is not None else a, min(b, req.t1) if req.t1 is not None else b
            if b2 > a2:
                seg_total += b2 - a2
                seg_count += 1
    for sid in req.signals:
        try:
            t, y = store.signal(sid)
        except KeyError:
            continue
        if where is None:
            s = compute_signal_stats(t, y, req.t0, req.t1)
        else:
            t = np.asarray(t, dtype=np.float64)
            m = state_mask(t, where[0], where[1], req.stateValues)
            if req.t0 is not None:
                m &= t >= req.t0
            if req.t1 is not None:
                m &= t <= req.t1
            s = compute_signal_stats(t[m], np.asarray(y)[m]) if m.any() else {}
            if s:
                s = {**s, "duration": seg_total, "segments": seg_count}     # time in the state, not first-to-last
        if s:
            res[sid] = s
    return {"stats": res}


class SpecRequest(BaseModel):
    signal: str
    x0: Optional[float] = None
    x1: Optional[float] = None
    nfft: int = 1024
    width: int = 800
    height: int = 300
    fmax: Optional[float] = None


@app.post("/api/spectrogram")
def spectrogram_ep(req: SpecRequest):
    """Spectrogram image of one signal over the visible time window (power in dB, 0..255 coded)."""
    try:
        t, y = store.signal(req.signal)
    except KeyError:
        fail(404, "The signal is no longer open.")
    try:
        r = make_spectrogram(t, y, req.x0, req.x1, int(max(64, min(req.nfft, 16384))),
                             int(max(50, min(req.width, 3000))), int(max(50, min(req.height, 1500))), req.fmax)
    except ValueError as e:
        fail(400, str(e))
    f = r["f"]
    step = float(f[1] - f[0]) if len(f) > 1 else r["df"]
    return {"nf": int(len(f)), "nt": int(len(r["t"])), "f0": max(0.0, float(f[0]) - step / 2), "f1": float(f[-1]) + step / 2,
            "t0": float(r["t"][0]), "t1": float(r["t"][-1]), "img": base64.b64encode(np.ascontiguousarray(r["img"]).tobytes()).decode(),
            "dbLo": r["dbLo"], "dbHi": r["dbHi"], "fs": r["fs"], "nfft": r["nfft"], "df": r["df"], "dt": r["dt"]}


# =============================================================================
# ANALYSIS (phase 3)
# =============================================================================

class DerivedRequest(BaseModel):
    op: str
    sources: List[str]
    params: Optional[dict] = None
    name: Optional[str] = None


@app.post("/api/derived")
async def create_derived(req: DerivedRequest):
    if req.op not in OPS:
        fail(400, f"Unknown operation: {req.op}")
    try:
        d = await asyncio.to_thread(store.add_derived, req.op, req.sources, req.params or {}, req.name)
    except KeyError:
        fail(404, "One of the chosen signals is no longer open.")
    except OpError as e:
        fail(400, str(e))
    return {"id": f"derived/{d.name}", "name": d.name, "runs": store.list()}


class PreviewRequest2(BaseModel):
    op: str
    sources: List[str]
    params: Optional[dict] = None
    x0: Optional[float] = None
    x1: Optional[float] = None
    points: int = 3000


@app.post("/api/derived/preview")
def preview_derived(req: PreviewRequest2):
    """Compute an operation WITHOUT keeping it, for a dashed preview in the plot (O-04)."""
    from svcore.analysis import compute
    try:
        t, y = compute(req.op, [store.signal(s) for s in req.sources], req.params or {})
    except KeyError:
        fail(404, "One of the chosen signals is no longer open.")
    except OpError as e:
        fail(400, str(e))
    rng = [req.x0, req.x1] if req.x0 is not None and req.x1 is not None else None
    xd, yd, _ = decimate_for_view(t, y, rng, int(max(200, min(req.points, 20000))))
    return {"n": int(len(xd)), "x": b64(xd, np.float64), "y": b64(yd, np.float32)}


class TransformRequest(BaseModel):
    signals: List[str] = []
    transform: Optional[dict] = None            # None clears
    specs: Optional[Dict[str, Optional[dict]]] = None   # or one spec per signal (undo / restore)


@app.post("/api/transforms")
def set_transforms(req: TransformRequest):
    """Change signals THEMSELVES (no new signals): function, scale, offset, time shift."""
    specs = req.specs if req.specs is not None else {sid: req.transform for sid in req.signals}
    if not specs:
        fail(400, "No signals chosen.")
    try:
        previous = store.set_transforms(specs)
    except KeyError as e:
        fail(404, f"Not an open file signal: {e}")
    except OpError as e:
        fail(400, str(e))
    return {"previous": previous, "runs": store.list()}


class DerivedBatch(BaseModel):
    items: List[DerivedRequest]


@app.post("/api/derived/restore")
async def restore_derived(req: DerivedBatch):
    """Recreate derived signals from saved formulas (autosave / sessions). Idempotent: a formula
    whose name already exists REPLACES it (no "name (2)" duplicates, and "derived/<name>"
    references in the layout stay valid) - e.g. when the same work is re-opened with new files."""
    ok, failed = [], []
    for it in req.items:
        if it.name and it.name in store.derived:
            store.remove_derived(it.name)
        try:
            d = await asyncio.to_thread(store.add_derived, it.op, it.sources, it.params or {}, it.name)
            ok.append(d.name)
        except Exception as e:
            failed.append({"name": it.name, "message": str(e)})
    return {"restored": ok, "failed": failed, "runs": store.list()}


@app.delete("/api/derived/{name:path}")
def delete_derived(name: str):
    store.remove_derived(name)
    return {"runs": store.list()}


class FFTRequest(BaseModel):
    signals: List[str]
    window: str = "hanning"
    method: str = "fft"                 # fft | welch (power spectral density)
    t0: Optional[float] = None
    t1: Optional[float] = None
    points: int = 4000


@app.post("/api/fft")
def fft(req: FFTRequest):
    out = []
    for sid in req.signals:
        try:
            t, y = store.signal(sid)
        except KeyError:
            out.append({"id": sid, "missing": True})
            continue
        f, m = fft_for(sid, store.version(sid), t, y, req.window, req.t0, req.t1, req.method)
        fx, fy, peak = fft_display(f, m, int(max(200, min(req.points, 20000))))
        out.append({"id": sid, "n": int(len(fx)), "peak": peak, "x": b64(fx, np.float64), "y": b64(fy, np.float32)})
    return {"series": out}


class XYRequest(BaseModel):
    x: str
    ys: List[str]
    alignment: str = "linear"
    t0: Optional[float] = None
    t1: Optional[float] = None
    points: int = 16000


@app.post("/api/xy")
def xy(req: XYRequest):
    try:
        tx, x = store.signal(req.x)
    except KeyError:
        fail(404, "The X signal is no longer open.")
    out = []
    for sid in req.ys:
        try:
            ty, y = store.signal(sid)
        except KeyError:
            out.append({"id": sid, "missing": True})
            continue
        xs, ys, ts = xy_pair(tx, x, ty, y, req.alignment, req.t0, req.t1, req.points, with_t=True)
        out.append({"id": sid, "n": int(len(xs)), "x": b64(xs, np.float64), "y": b64(ys, np.float32), "t": b64(ts, np.float64)})
    return {"series": out}


class XYZTrack(BaseModel):
    x: str
    y: str
    z: str


class XYZRequest(BaseModel):
    tracks: List[XYZTrack]
    alignment: str = "linear"
    points: int = 20000


@app.post("/api/xyz")
def xyz(req: XYZRequest):
    """T17c: plain 3D plot - each track's Y and Z on its X signal's samples (svcore.xyz)."""
    from svcore.xyz import xyz_track
    out = []
    for tr in req.tracks:
        try:
            sx, sy, sz = store.signal(tr.x), store.signal(tr.y), store.signal(tr.z)
        except KeyError:
            out.append({"id": tr.x, "missing": True})
            continue
        r = xyz_track(sx, sy, sz, req.alignment, max(100, min(req.points, 200000)))
        if r is None:
            out.append({"id": tr.x, "empty": True})
            continue
        out.append({"id": tr.x, "n": int(len(r["t"])), **{k: b64(r[k], np.float64 if k == "t" else np.float32) for k in ("t", "x", "y", "z")}})
    return {"tracks": out}


class ObjectTrackRequest(BaseModel):
    lat: str
    lon: str
    alt: Optional[str] = None
    yaw: Optional[str] = None
    pitch: Optional[str] = None
    roll: Optional[str] = None
    # or the attitude as a quaternion (w, x, y, z - e.g. PX4's vehicle_attitude.q[0..3]): turned into
    # heading / pitch / roll here
    qw: Optional[str] = None
    qx: Optional[str] = None
    qy: Optional[str] = None
    qz: Optional[str] = None
    points: int = 20000


def _unit_guess(v: np.ndarray) -> str:
    """Angles in degrees or radians, from their range."""
    f = v[np.isfinite(v)]
    return "rad" if len(f) and np.nanmax(np.abs(f)) <= 2 * np.pi + 0.05 else "deg"


@app.post("/api/object_track")
def object_track(req: ObjectTrackRequest):
    """An object on the map: its signals - possibly from different files - on one time axis (the
    latitude's samples), each one interpolated in time and NaN outside its own time span; angles
    interpolated the short way round. Latitude / longitude in 1e7 degrees (MAVLink integers) are
    turned into degrees. `course`: the direction of travel in degrees from north (for objects
    without a heading signal)."""
    try:
        t, lat = store.signal(req.lat)
        tlo, lon = store.signal(req.lon)
    except KeyError:
        fail(404, "A position signal of this object is no longer open.")
    t = np.asarray(t, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    keep = np.isfinite(t) & np.isfinite(lat)
    t, lat = t[keep], lat[keep]
    if len(t) < 2:
        fail(400, "The latitude signal has no samples.")
    step = max(1, int(np.ceil(len(t) / max(100, req.points))))
    t, lat = t[::step], lat[::step]

    def onto(tt, vv, angle=False):
        tt = np.asarray(tt, dtype=np.float64)
        vv = np.asarray(vv, dtype=np.float64)
        ok = np.isfinite(tt) & np.isfinite(vv)
        tt, vv = tt[ok], vv[ok]
        if len(tt) < 2:
            return np.full(len(t), np.nan)
        if angle:                                   # the short way round: unwrap, interpolate, wrap
            per = 2 * np.pi if _unit_guess(vv) == "rad" else 360.0
            vv = np.unwrap(vv, period=per)
        out = np.interp(t, tt, vv)
        out[(t < tt[0]) | (t > tt[-1])] = np.nan
        if angle:
            out = np.mod(out + per / 2, per) - per / 2
        return out

    lon_a = onto(tlo, lon)
    if np.nanmax(np.abs(lat)) > 90 or np.nanmax(np.abs(lon_a)) > 180:     # 1e7 degrees (MAVLink ints)
        lat, lon_a = lat / 1e7, lon_a / 1e7
    out = {"n": int(len(t)), "t": b64(t, np.float64), "lat": b64(lat, np.float64), "lon": b64(lon_a, np.float64), "units": {}}
    raw = {}
    for role in ("alt", "yaw", "pitch", "roll"):
        sid = getattr(req, role)
        if not sid:
            continue
        try:
            raw[role] = (sid, *store.signal(sid))
        except KeyError:
            continue
    # angle units: the signal's name says it ("... [rad]", "_deg"), else the object's angles together -
    # if any of them goes beyond 2 pi they are all degrees (one log uses one unit), else radians.
    # (By its own range alone, a pitch of a few degrees would pass for radians.)
    angles = {r: v for r, v in raw.items() if r != "alt"}
    beyond = any(np.nanmax(np.abs(np.asarray(v[2], dtype=np.float64))) > 2 * np.pi + 0.05 for v in angles.values() if len(v[2]))
    for role, (sid, ts, vs) in raw.items():
        v = onto(ts, vs, angle=role != "alt")
        if role != "alt":
            name = sid.split("/", 1)[-1].lower()
            if re.search(r"(\[rad\]|\brad\b|_rad\b|\(rad\))", name):
                out["units"][role] = "rad"
            elif re.search(r"(\[deg\]|\bdeg\b|_deg\b|\(deg\)|°)", name):
                out["units"][role] = "deg"
            else:
                out["units"][role] = "deg" if beyond else "rad"
        out[role] = b64(v, np.float32)
    # a quaternion (Hamilton, w first; body to NED as PX4 logs it) -> roll / pitch / yaw in radians,
    # for the angles not given as signals
    if all((req.qw, req.qx, req.qy, req.qz)):
        try:
            q = [onto(*store.signal(s)) for s in (req.qw, req.qx, req.qy, req.qz)]
        except KeyError:
            q = None
        if q is not None:
            w, x, y, z = q
            norm = np.sqrt(w * w + x * x + y * y + z * z)
            norm[norm == 0] = np.nan
            w, x, y, z = w / norm, x / norm, y / norm, z / norm
            euler = {"roll": np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)),
                     "pitch": np.arcsin(np.clip(2 * (w * y - z * x), -1, 1)),
                     "yaw": np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))}
            for role, v in euler.items():
                if role not in out:
                    out[role] = b64(v, np.float32)
                    out["units"][role] = "rad"
    # direction of travel: bearing between points ~1 s apart (or 3 samples), in degrees from north
    la, lo = np.radians(lat), np.radians(lon_a)
    k = max(1, int(np.searchsorted(t, t[0] + 1.0)) if len(t) > 3 else 1)
    k = max(1, min(k, len(t) // 4 or 1))
    i0, i1 = np.arange(len(t)) - k // 2, np.arange(len(t)) + (k - k // 2)
    i0, i1 = np.clip(i0, 0, len(t) - 1), np.clip(i1, 0, len(t) - 1)
    y = np.sin(lo[i1] - lo[i0]) * np.cos(la[i1])
    x = np.cos(la[i0]) * np.sin(la[i1]) - np.sin(la[i0]) * np.cos(la[i1]) * np.cos(lo[i1] - lo[i0])
    course = np.degrees(np.arctan2(y, x))
    still = (np.abs(y) + np.abs(x)) < 1e-9                       # not moving: keep the last direction
    if still.any():
        idx = np.where(~still, np.arange(len(t)), 0)
        np.maximum.accumulate(idx, out=idx)
        course = course[idx]
    out["course"] = b64(course, np.float32)
    # the ground under the object (bundled elevation): height above ground, and altitudes given
    # relative to the take-off point
    from app import basemap
    out["ground"] = b64(basemap.ground_at(lat, lon_a), np.float32)
    return out


@app.get("/api/discrete")
def discrete(sig: str):
    """On-demand discrete-signal check (wide files skip it at load)."""
    try:
        store.signal(sig)
    except KeyError:
        fail(404, "Signal not found.")
    return {"discrete": store.is_discrete(sig)}


class StatesRequest(BaseModel):
    signals: List[str]
    x0: Optional[float] = None
    x1: Optional[float] = None
    bins: int = 1500                  # about the plot width in pixels


@app.post("/api/states")
def states(req: StatesRequest):
    out = {}
    for sid in req.signals:
        try:
            t, y = store.signal(sid)
        except KeyError:
            continue
        pts, collapsed, end = transitions(t, y, req.x0, req.x1, bins=int(max(100, min(req.bins, 4000))))
        # a state holds until the next change: the last one lasts to the end of its file
        lr = store.runs.get(sid.partition("/")[0])
        if end is not None and lr is not None:
            end = max(end, float(lr.run.end_time) + float(lr.run.time_offset or 0))
        out[sid] = {"points": pts, "tooMany": collapsed, "end": end}
    return {"states": out}


# =============================================================================
# COMPARE (phase 4)
# =============================================================================

class CompareRequest(BaseModel):
    signals: List[str]               # the same signal in several runs
    baseline: str = "mean"           # a signal id from `signals`, or "mean"
    alignment: str = "linear"
    tolAbs: Optional[float] = None
    tolPct: Optional[float] = None


@app.post("/api/compare")
def compare(req: CompareRequest):
    try:
        series = [(sid, *store.signal(sid)) for sid in req.signals]
        return compare_runs(series, req.baseline, req.alignment, req.tolAbs, req.tolPct)
    except KeyError:
        fail(404, "One of the chosen signals is no longer open.")
    except ValueError as e:
        fail(400, str(e))


class CompareAllRequest(BaseModel):
    points: int = 50_000              # per signal; the similarity list asks for fewer
    runs: List[str]
    baselineRun: str = "mean"        # a run id, or "mean"
    alignment: str = "linear"
    tolAbs: Optional[float] = None
    tolPct: Optional[float] = None


def compare_table(ca: "CompareAllRequest", progress=None) -> list:
    """Every signal name present in AT LEAST TWO of the chosen files: the spread between
    files (mean, std), the differences against the baseline (RMS, max, mean, std of the
    difference, correlation, tolerance) and per-file statistics over the common time range."""
    from collections import OrderedDict
    present: "OrderedDict[str, list]" = OrderedDict()
    for rid in ca.runs:
        for name in store.get(rid).run.signals.keys():
            present.setdefault(name, []).append(rid)
    names = [n for n, rids in present.items() if len(rids) >= 2]
    out = []
    for k, name in enumerate(names):
        rids = present[name]
        ids = [f"{rid}/{name}" for rid in rids]
        base = f"{ca.baselineRun}/{name}" if ca.baselineRun in rids else "mean"
        try:
            r = compare_runs([(sid, *store.signal(sid)) for sid in ids], base, ca.alignment, ca.tolAbs, ca.tolPct,
                             int(max(2_000, min(ca.points, 200_000))))
        except ValueError as e:
            out.append({"name": name, "runs": rids, "error": str(e)})
            continue
        lo, hi = r["overlap"]
        files = []
        for rid, sid in zip(rids, ids):
            t, y = store.signal(sid)
            st = compute_signal_stats(t, y, lo, hi)
            files.append({"run": rid, "mean": st.get("mean"), "std": st.get("std"), "min": st.get("min"),
                          "max": st.get("max"), "rms": st.get("rms")})
        diffs = [{"run": x["id"].split("/")[0], **{kk: x.get(kk) for kk in
                  ("rmsDiff", "rmsPct", "matchPct", "maxAbsDiff", "meanDiff", "stdDiff", "correlation", "withinPct", "pass")}}
                 for x in r["rows"] if x.get("valid")]
        worst = max((x for x in r["rows"] if x.get("valid")), key=lambda x: x["rmsPct"], default=None)
        means = [f["mean"] for f in files if f["mean"] is not None]
        stds = [f["std"] for f in files if f["std"] is not None]
        out.append({
            "name": name, "runs": rids, "baseline": "mean" if base == "mean" else ca.baselineRun,
            "meanSpread": (max(means) - min(means)) if means else None,
            "stdSpread": (max(stds) - min(stds)) if stds else None,
            "worstRmsDiff": max((d["rmsDiff"] for d in diffs), default=None),
            "worstRmsPct": max((d["rmsPct"] for d in diffs), default=None),
            "matchPct": min((d["matchPct"] for d in diffs), default=None),          # the least similar file
            "profile": worst.get("profile") if worst else None,                     # where it diverges
            "worstMaxAbs": max((d["maxAbsDiff"] for d in diffs), default=None),
            "minCorrelation": min((d["correlation"] for d in diffs), default=None),
            "pass": all(d.get("pass", True) for d in diffs) if diffs and (ca.tolAbs is not None or ca.tolPct is not None) else None,
            "files": files, "diffs": diffs,
        })
        if progress:
            progress((k + 1) / max(1, len(names)), name)
    out.sort(key=lambda x: -(x.get("worstRmsPct") or -1))
    return out


@app.post("/api/compare/all")
async def compare_all(req: CompareAllRequest):
    try:
        return {"signals": await asyncio.to_thread(compare_table, req)}
    except KeyError:
        fail(404, "One of the chosen files is no longer open.")


class ShiftRequest(BaseModel):
    base: str
    other: str


@app.post("/api/compare/shift")
def compare_shift(req: ShiftRequest):
    try:
        return {"shift": auto_shift(store.signal(req.base), store.signal(req.other))}
    except KeyError:
        fail(404, "One of the chosen signals is no longer open.")


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


@app.post("/api/export/csv")
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


@app.post("/api/report")
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
    return {"path": path, "size": os.path.getsize(path)}


@app.post("/api/report/preview")
async def report_preview(req: ReportRequest):
    html_text = await asyncio.to_thread(reports.build_html, store, req.model_dump())
    return {"html": html_text}


class ImageRequest(BaseModel):
    path: str
    format: str = "png"              # png | svg
    theme: str = "light"
    plot: dict


@app.post("/api/export/image")
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


class SyncRequest(BaseModel):
    ref: str                       # the reference file (its time stays)
    other: str                     # the file to move
    refSignal: Optional[str] = None     # optional: a signal pair to correlate (names)
    otherSignal: Optional[str] = None
    feature: Optional[dict] = None      # with the pair: align a recognised moment {kind, levelPct, occurrence}
    maxLag: Optional[float] = None      # with the pair: search only within +-maxLag s of the current alignment


@app.post("/api/sync/suggest")
async def sync_suggest(req: SyncRequest):
    """Ways to align two recordings of the same flight (boot clock, matching events, signal
    correlation), each with the time offset to give the other file."""
    a, b = store.runs.get(req.ref), store.runs.get(req.other)
    if a is None or b is None:
        fail(404, "File is no longer open.")
    cands = await asyncio.to_thread(sync_suggest_fn, a.run, b.run, req.refSignal, req.otherSignal, req.feature, req.maxLag)
    return {"candidates": cands}


@app.get("/api/terrain/{z}/{x}/{y}")
def terrain(z: int, x: int, y: int):
    """Ground heights for the 3D view (from the bundled elevation grids; works offline)."""
    from app import basemap
    data = basemap.terrain_tile(z, x, y)
    if data is None:
        fail(404, "No terrain here.")
    return Response(content=data, media_type="application/octet-stream", headers={"Cache-Control": "max-age=86400"})


@app.get("/api/basemap/places")
def basemap_places():
    """Place and airport names for the offline map (it draws them itself, in the UI language)."""
    from app import basemap
    if not basemap.available():
        return {"places": [], "attribution": ""}
    return basemap.places()


@app.get("/api/tiles/{src}/{z}/{x}/{y}")
async def map_tile(src: str, z: int, x: int, y: int):
    """A map tile (cached on disk). 404 when offline and not cached: the map then shows its own
    country borders only."""
    from fastapi.responses import Response
    from app.tiles import tile
    r = await asyncio.to_thread(tile, src, z, x, y)
    if r is None:
        return Response(status_code=404)
    return Response(content=r[0], media_type=r[1], headers={"Cache-Control": "max-age=86400"})


@app.get("/api/runs/{run_id}/health")
def run_health(run_id: str):
    """Automatic checks of a flight log (vibration, GPS, battery, EKF, motors, board power, errors)."""
    lr = store.runs.get(run_id)
    if lr is None:
        fail(404, "This file is no longer open.")
    res = log_health(lr.run)
    if res is None:
        fail(404, "Nothing to check in this file.")
    return res              # times already include the file's time offset (as on the plots)


@app.get("/api/runs/{run_id}/log")
def run_log(run_id: str):
    """Parameters and events (messages, mode changes, events, errors) of a flight log."""
    info = store.log_info(run_id)
    if info is None:
        fail(404, "This file has no flight-log parameters or messages.")
    return info


@app.post("/api/save/text")
def save_text(req: TextSave):
    """Save text produced by the UI (e.g. comparison results as CSV)."""
    path = _check_target(req.path, req.ext)
    with open(path, "w", encoding="utf-8-sig" if req.bom else "utf-8", newline="") as f:
        f.write(req.content)
    return {"path": path}


class ImageSave(BaseModel):
    path: str
    data: str                   # base64 of the image the UI drew (the 3D view)


@app.post("/api/save/image")
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


class SessionSave(BaseModel):
    path: str
    state: dict


@app.post("/api/session/save")
def session_save(req: SessionSave):
    path = _check_target(req.path, ".svsession")
    doc = {"format": "signalviewer-session", "version": 3, "saved": __import__("datetime").datetime.now().isoformat(), **req.state}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    prefs.add_recent(path, "session")
    return {"path": path}


class SessionLoad(BaseModel):
    path: str


@app.post("/api/session/load")
def session_load(req: SessionLoad):
    if not os.path.isfile(req.path):
        fail(404, "File not found.")
    try:
        with open(req.path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        fail(400, "This file is not a Signal Viewer session.")
    prefs.add_recent(req.path, "session")
    if doc.get("format") == "signalviewer-session":
        return {"state": doc, "converted": False}
    if "run_paths" in doc and ("view_state" in doc or "signal_settings" in doc):
        return {"state": convert_v2_session(doc), "converted": True}
    fail(400, "This file is not a Signal Viewer session.")


def convert_v2_session(doc: dict) -> dict:
    """One-way import of a Signal Viewer 2.x session (layout, signals, styling, import settings).
    2.x derived signals were stored as raw numbers without a formula and are not imported."""
    paths = doc.get("run_paths", [])
    meta = doc.get("runs_meta", [])
    runs = []
    for i, p in enumerate(paths):
        m = meta[i] if i < len(meta) else {}
        runs.append({"id": f"r{i}", "path": p, "name": m.get("csv_display_name") or os.path.basename(p),
                     "importSettings": m.get("import_settings") or {}, "timeOffset": m.get("time_offset") or 0})
    settings = doc.get("signal_settings", {})
    palette = ["#3D8BFD", "#2FBF9F", "#E5677A", "#9B7BFF", "#7CC35A", "#F07B3F", "#4FC3E8", "#D08CE8", "#B8A33A", "#FF8FB1"]
    color_i = [0]

    def key(k):
        if not k or ":" not in k:
            return None
        idx, name = k.split(":", 1)
        return f"r{idx}/{name}" if idx.lstrip("-").isdigit() and int(idx) >= 0 else None

    def tab_from(vs, n):
        rows, cols = int(vs.get("layout_rows", 1) or 1), int(vs.get("layout_cols", 1) or 1)
        plots = []
        for i, sp in enumerate((vs.get("subplots") or [])[: rows * cols]):
            sigs = []
            for k in sp.get("assigned_signals", []):
                if sp.get("mode") == "xy" and k == sp.get("x_signal"):
                    continue
                nk = key(k)
                if not nk:
                    continue
                st = settings.get(k, {})
                color = st.get("color") or palette[color_i[0] % len(palette)]
                color_i[0] += 1
                sigs.append({"sig": nk, "color": color, "width": st.get("line_width") or 1.5,
                             "scale": 1 if st.get("scale") is None else st.get("scale"), "offset": st.get("offset") or 0,
                             "label": st.get("display_name") or None, "state": bool(st.get("is_state"))})
            plots.append({"id": f"p{n}_{i}", "title": sp.get("title") or "", "signals": sigs,
                          "mode": sp.get("mode") or "time", "xSignal": key(sp.get("x_signal")),
                          "xyAlign": sp.get("xy_alignment") or "linear", "fftWindow": sp.get("fft_window") or "hanning",
                          "fftLog": sp.get("fft_log_scale", True), "caption": sp.get("caption") or ""})
        while len(plots) < rows * cols:
            plots.append({"id": f"p{n}_{len(plots)}", "title": "", "signals": []})
        return {"id": f"t{n}", "name": "", "rows": rows, "cols": cols, "plots": plots, "active": 0, "linkX": True}

    tabs = [tab_from(doc.get("view_state") or {}, 0)]
    for n, (tid, vs) in enumerate((doc.get("tab_view_states") or {}).items(), start=1):
        if vs:
            tabs.append(tab_from(vs, n))
    return {"format": "signalviewer-session", "version": 3, "ws": {"tabs": tabs, "activeTab": tabs[0]["id"]},
            "runs": runs, "derived": [], "ui": {}, "skippedDerived": len(doc.get("derived_signals") or {})}


# =============================================================================
# BACKGROUND JOBS (phase 5): progress + cancel for long operations
# =============================================================================

class JobRequest(BaseModel):
    kind: str                         # open | report | compareAll | exportCsv
    body: dict = {}
    label: str = ""


@app.post("/api/jobs")
def start_job(req: JobRequest):
    b = req.body
    if req.kind == "open":
        paths, settings = list(b.get("paths") or []), b.get("settings")

        def work(job):
            opened, errors, n = [], [], max(1, len(paths))
            for i, p in enumerate(paths):
                # each file gets an equal share of the bar; the loader reports inside it
                def sub(frac, phase="", i=i):
                    job.report((i + frac) / n, phase)
                from svcore.csv_loader import set_progress_context
                set_progress_context(sub, job.cancelled)
                try:
                    lr = open_with_prefs(p, settings)
                    opened.append(store.describe(lr))
                except LoadError as e:
                    errors.append(_load_error(p, e))
                except JobCancelled:
                    raise
                except Exception as e:
                    if e.__class__.__name__ == "LoadCancelled":
                        raise
                    errors.append({"path": p, "message": f"Unexpected error while reading the file: {e}"})
                job.report((i + 1) / n, "read")
            return {"opened": opened, "errors": errors}
    elif req.kind == "report":
        rr = ReportRequest(**b)
        ext = {"html": ".html", "pdf": ".pdf", "docx": ".docx"}.get(rr.format)
        if not ext:
            fail(400, "Unknown report format.")
        path = _check_target(rr.path, ext)

        def work(job):
            body = rr.model_dump()
            job.report(0.05, "prepare")
            if rr.format == "html":
                text = reports.build_html(store, body, progress=job.report)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            elif rr.format == "pdf":
                reports.build_pdf(store, body, path, progress=job.report)
            else:
                reports.build_docx(store, body, path, progress=job.report)
            return {"path": path, "size": os.path.getsize(path)}
    elif req.kind == "reloadAll":
        def work(job):
            res = store.reload_all(progress=lambda f, name: job.report(f, name), cancelled=job.cancelled)
            job.report(1.0, "read")
            return res
    elif req.kind == "compareAll":
        ca = CompareAllRequest(**b)

        def work(job):
            return {"signals": compare_table(ca, job.report)}
    else:
        fail(400, f"Unknown job: {req.kind}")
    job = jobs.start(req.kind, req.label or req.kind, work)
    return job.to_dict()


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        fail(404, "Unknown job.")
    return job.to_dict()


@app.post("/api/jobs/{job_id}/cancel")
def job_cancel(job_id: str):
    return {"cancelled": jobs.cancel(job_id)}


# =============================================================================
# BROWSER-MODE WATCHDOG: stop the server when no tab is open (no orphan process)
# =============================================================================

WATCHDOG = {"enabled": False, "last": None}


@app.post("/api/ping")
def ping():
    WATCHDOG["last"] = time.time()
    return {"ok": True}


def idle_too_long(seconds: float) -> bool:
    last = WATCHDOG["last"]
    return WATCHDOG["enabled"] and last is not None and time.time() - last > seconds


# =============================================================================
# RECENT, TEMPLATES, IMPORT PREFERENCES
# =============================================================================

@app.get("/api/recent")
def recent():
    return {"items": prefs.list_recent()}


class PathOnly(BaseModel):
    path: str


@app.post("/api/recent/forget")
def recent_forget(req: PathOnly):
    prefs.forget_recent(req.path)
    return {"items": prefs.list_recent()}


@app.post("/api/import/forget")
def import_forget(req: PathOnly):
    prefs.forget_import(req.path)
    return {"ok": True}


@app.get("/api/templates")
def templates():
    """The user's templates (one JSON file each, in the templates folder)."""
    return {"templates": prefs.list_templates(), **prefs.template_folder_info()}


class TemplateFolder(BaseModel):
    path: Optional[str] = None     # None: back to the default folder


@app.post("/api/templates/folder")
def template_folder(req: TemplateFolder):
    """Where templates are kept: the user can pick any folder (a shared drive, say). The current
    templates are copied there; the app looks for templates in that folder from now on."""
    try:
        return prefs.set_template_dir(req.path)
    except ValueError as e:
        fail(400, str(e))


class TemplateSave(BaseModel):
    template: dict
    replace: bool = True           # False: always a new template (a free name is found)


@app.post("/api/templates")
def template_save(req: TemplateSave):
    try:
        return {"template": prefs.save_template(req.template, req.replace)}
    except ValueError as e:
        fail(400, str(e))


@app.delete("/api/templates/{tid:path}")
def template_delete(tid: str):
    prefs.delete_template(tid)
    return {"ok": True}


class TemplatePath(BaseModel):
    path: str
    ids: List[str] = []


@app.post("/api/templates/import")
def template_import(req: TemplatePath):
    if not os.path.isfile(req.path):
        fail(404, "File not found.")
    try:
        return {"templates": prefs.import_templates(req.path)}
    except (ValueError, OSError, json.JSONDecodeError) as e:
        fail(400, f"Could not import: {e}")


@app.post("/api/templates/export")
def template_export(req: TemplatePath):
    """Templates (by id) to one .json file - to share them or keep a copy."""
    path = _check_target(req.path, ".json")
    mine = {t["id"]: t for t in prefs.list_templates()}
    items = [{k: v for k, v in mine[i].items() if k != "file"} for i in req.ids if i in mine]
    if not items:
        fail(400, "Nothing to export.")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items[0] if len(items) == 1 else {"templates": items}, f, ensure_ascii=False, indent=1)
    return {"path": path}


@app.post("/api/templates/reveal")
def template_reveal():
    """Open the templates folder in the file manager (to edit, copy or share the files)."""
    os.makedirs(prefs.TEMPLATE_DIR, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            os.startfile(prefs.TEMPLATE_DIR)                     # type: ignore[attr-defined]
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", prefs.TEMPLATE_DIR],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        fail(400, f"Could not open the folder: {e}")
    return {"folder": prefs.TEMPLATE_DIR}


# =============================================================================
# BUILT-IN FILE BROWSER (replaces tkinter; works on every OS)
# =============================================================================

class ListDirRequest(BaseModel):
    path: Optional[str] = None
    exts: Optional[List[str]] = None


def _windows_drives() -> List[str]:
    """Drive letters from the OS bitmask: never touches a drive, so a disconnected network
    drive cannot stall the listing (probing A:-Z: with os.path.exists could hang for seconds)."""
    try:
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        return [f"{d}:\\" for i, d in enumerate(string.ascii_uppercase) if mask >> i & 1]
    except Exception:
        return [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]


def _wanted(exts: Optional[List[str]]):
    """Which files a listing shows: the requested extensions, else the supported data files."""
    allowed = tuple(x.lower() for x in exts) if exts else SUPPORTED
    return lambda name: name.lower().endswith(allowed)


def _entry(e: "os.DirEntry", is_dir: bool) -> dict:
    st = e.stat()                       # once per entry (slow on network drives)
    return {"name": e.name, "path": e.path, "dir": is_dir,
            "size": None if is_dir else st.st_size, "mtime": st.st_mtime}


EXAMPLES = os.environ.get("SV_EXAMPLES") or os.path.join(os.path.dirname(__file__), "..", "..", "examples")
# the welcome screen offers these; files that are missing (a trimmed install) are simply left out
EXAMPLE_SETS = [
    {"id": "flight", "files": ["uav_flight.csv"]},
    {"id": "car", "files": ["run_012.csv", "run_013.csv", "run_014.csv"]},
]


@app.get("/api/examples")
def list_examples():
    out = []
    for ex in EXAMPLE_SETS:
        paths = [os.path.abspath(os.path.join(EXAMPLES, f)) for f in ex["files"]]
        paths = [p for p in paths if os.path.isfile(p)]
        if paths:
            out.append({"id": ex["id"], "paths": paths})
    return out


@app.post("/api/fs/list")
def list_dir(req: ListDirRequest):
    path = os.path.expanduser(req.path) if req.path else os.path.expanduser("~")
    if os.name == "nt" and path in ("", "/", "\\"):
        return {"path": "", "parent": None,
                "entries": [{"name": d, "path": d, "dir": True} for d in _windows_drives()]}
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        fail(404, "Folder not found.")
    wanted = _wanted(req.exts)
    entries = []
    try:
        for e in os.scandir(path):
            if e.name.startswith("."):
                continue
            try:
                is_dir = e.is_dir()
                if is_dir or wanted(e.name):
                    entries.append(_entry(e, is_dir))
            except OSError:
                continue
    except PermissionError:
        fail(403, "No permission to open this folder.")
    entries.sort(key=lambda x: (not x["dir"], x["name"].lower()))
    parent = os.path.dirname(path)
    return {"path": path, "parent": parent if parent != path else ("" if os.name == "nt" else None),
            "entries": entries}


class CompleteRequest(BaseModel):
    text: str
    base: Optional[str] = None           # the folder shown now: relative text completes from here
    exts: Optional[List[str]] = None
    limit: int = 50


def _common_prefix(names: List[str]) -> str:
    if not names:
        return ""
    lo = [n.lower() for n in names]
    k = 0
    while all(len(n) > k for n in lo) and len({n[k] for n in lo}) == 1:
        k += 1
    return names[0][:k]


@app.post("/api/fs/complete")
def complete_path(req: CompleteRequest):
    """Path autocomplete for the file browser: the folders / files whose names start with
    what was typed after the last separator (case-insensitive). `common` is the longest
    completion all matches share - what Tab fills in."""
    text = os.path.expanduser(req.text or "")
    empty = {"dir": None, "items": [], "common": req.text or ""}
    if not text.strip():
        return empty
    # "c:" (or a lone "c" with no folder to complete in) -> drives; with a folder shown,
    # "c" is the start of a name in that folder
    if os.name == "nt" and (re.fullmatch(r"[A-Za-z]:", text) or (re.fullmatch(r"[A-Za-z]", text) and not req.base)):
        drives = [d for d in _windows_drives() if d.lower().startswith(text.lower())]
        items = [{"name": d, "path": d, "dir": True} for d in drives]
        return {"dir": "", "items": items, "common": drives[0] if len(drives) == 1 else text}
    if not os.path.isabs(text) and req.base:
        text = os.path.join(req.base, text)
    seps = "\\/" if os.name == "nt" else "/"
    cut = max(text.rfind(c) for c in seps) + 1
    folder, prefix = text[:cut], text[cut:]
    if not folder or not os.path.isdir(folder):
        return empty
    wanted, low = _wanted(req.exts), prefix.lower()
    items = []
    try:
        for e in os.scandir(folder):
            if not e.name.lower().startswith(low) or (e.name.startswith(".") and not prefix.startswith(".")):
                continue
            try:
                is_dir = e.is_dir()
            except OSError:
                continue
            if is_dir or wanted(e.name):
                items.append({"name": e.name, "path": e.path + (os.sep if is_dir else ""), "dir": is_dir})
    except OSError:
        return empty
    items.sort(key=lambda x: (not x["dir"], x["name"].lower()))
    items = items[:max(1, min(req.limit, 200))]
    common = _common_prefix([i["name"] for i in items])
    if len(items) == 1:
        common_path = items[0]["path"]
    else:
        common_path = folder + (common if len(common) >= len(prefix) else prefix)
    return {"dir": folder, "items": items, "common": common_path}


# =============================================================================
# AUTOSAVE / SESSIONS
# =============================================================================

@app.get("/api/autosave")
def get_autosave():
    if not os.path.isfile(AUTOSAVE):
        return {"state": None}
    try:
        with open(AUTOSAVE, "r", encoding="utf-8") as f:
            return {"state": json.load(f)}
    except Exception:
        return {"state": None}


@app.post("/api/autosave")
def put_autosave(state: dict):
    os.makedirs(APP_DIR, exist_ok=True)
    tmp = AUTOSAVE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, AUTOSAVE)
    return {"ok": True}


class RestoreRequest(BaseModel):
    runs: List[dict]   # [{id, path, name, importSettings, timeOffset}]


@app.post("/api/session/restore")
async def restore(req: RestoreRequest):
    """Re-open the files of a saved workspace, keeping their ORIGINAL ids so every
    signal reference in the saved layout stays valid. Missing files are reported."""
    restored, missing = [], []
    for r in req.runs:
        path = r.get("path")
        existing = store.runs.get(r.get("id") or "")
        if existing is not None and os.path.abspath(existing.run.file_path) == os.path.abspath(path or ""):
            # already open (browser reload while the server kept running): keep it as is
            restored.append(store.describe(existing))
            continue
        if not path or not os.path.isfile(path):
            missing.append(r)
            continue
        settings = dict(r.get("importSettings") or {})
        settings.pop("format", None)
        try:
            lr = await asyncio.to_thread(store.open_file, path, settings)
        except Exception:
            missing.append(r)
            continue
        with store._lock:
            store.runs.pop(lr.id)
            store.order.remove(lr.id)
            lr.id = r.get("id") or lr.id
            lr.name = r.get("name") or lr.name
            lr.run.time_offset = float(r.get("timeOffset") or 0)
            store.runs[lr.id] = lr
            if lr.id not in store.order:
                store.order.append(lr.id)
        restored.append(store.describe(lr))
    return {"restored": restored, "missing": missing}


# =============================================================================
# STATIC UI
# =============================================================================

if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404)
        candidate = os.path.realpath(os.path.join(DIST, full_path))
        inside = candidate.startswith(os.path.realpath(DIST) + os.sep)     # no "../" out of the UI folder
        if full_path and inside and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(DIST, "index.html"))
