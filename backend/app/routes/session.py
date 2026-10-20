"""Sessions: save / load, autosave and restoring the files of a session."""

import asyncio
import json
import os
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from app import prefs
from app.common import APP_DIR, AUTOSAVE, fail, log
from app.routes.export import _check_target
from app.store import store

router = APIRouter()




class SessionSave(BaseModel):
    path: str
    state: dict



@router.post("/api/session/save")
def session_save(req: SessionSave):
    path = _check_target(req.path, ".svsession")
    doc = {"format": "signalviewer-session", "version": 3, "saved": __import__("datetime").datetime.now().isoformat(), **req.state}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    prefs.add_recent(path, "session")
    return {"path": path}



class SessionLoad(BaseModel):
    path: str



@router.post("/api/session/load")
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
# AUTOSAVE / SESSIONS
# =============================================================================

@router.get("/api/autosave")
def get_autosave():
    if not os.path.isfile(AUTOSAVE):
        return {"state": None}
    try:
        with open(AUTOSAVE, "r", encoding="utf-8") as f:
            return {"state": json.load(f)}
    except (OSError, ValueError):       # unreadable or half-written: start clean, but say so in the log
        # F29: keep it aside - the next autosave would overwrite the only copy of the last work
        kept = AUTOSAVE.replace(".json", ".damaged.json")
        try:
            os.replace(AUTOSAVE, kept)
        except OSError:
            kept = AUTOSAVE
        log.warning("autosave %s could not be read; starting without it (kept as %s)", AUTOSAVE, kept, exc_info=True)
        return {"state": None, "damaged": kept}



@router.post("/api/autosave")
def put_autosave(state: dict):
    os.makedirs(APP_DIR, exist_ok=True)
    # each process its own temporary file: two apps started at once must not write into one
    tmp = f"{AUTOSAVE}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, AUTOSAVE)
    return {"ok": True}



class RestoreRequest(BaseModel):
    runs: List[dict]   # [{id, path, name, importSettings, timeOffset, tag?, color?}]



@router.post("/api/session/restore")
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
        except Exception:               # listed to the user as missing; the reason goes to the log
            log.warning("restore: %s did not open", path, exc_info=True)
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
            store.marks.pop(lr.id, None)
            if r.get("tag") or r.get("color"):           # T46: the saved file colour and tag
                store.set_mark(lr.id, r.get("tag"), r.get("color"))
        restored.append(store.describe(lr))
    return {"restored": restored, "missing": missing}
