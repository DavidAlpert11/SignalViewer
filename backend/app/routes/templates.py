"""Recent files, templates and remembered import settings."""

import json
import os
import subprocess
import sys
from typing import Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app import prefs
from app.common import fail
from app.routes.export import _check_target
from app.store import store
from svcore import templates as tplm

router = APIRouter()




# =============================================================================
# RECENT, TEMPLATES, IMPORT PREFERENCES
# =============================================================================

@router.get("/api/recent")
def recent():
    return {"items": prefs.list_recent()}



class PathOnly(BaseModel):
    path: str



@router.post("/api/recent/forget")
def recent_forget(req: PathOnly):
    prefs.forget_recent(req.path)
    return {"items": prefs.list_recent()}



@router.post("/api/import/forget")
def import_forget(req: PathOnly):
    prefs.forget_import(req.path)
    return {"ok": True}



@router.get("/api/templates")
def templates():
    """The user's templates (one JSON file each, in the templates folder)."""
    return {"templates": prefs.list_templates(), "builtin": tplm.builtin_templates(), **prefs.template_folder_info()}



# Template matching (T11b): ONE implementation in svcore/templates.py, used by the UI through these
# and by the command line (batch reports). Templates are sent by the UI (built-in + the user's, as
# shown), the open files are the server's own.
class TplFit(BaseModel):
    templates: List[dict]



@router.post("/api/templates/fit")
def templates_fit(req: TplFit):
    runs = store.list()
    return {"fits": {t.get("id"): tplm.fit(t, req.templates, runs) for t in req.templates}}



class TplBind(BaseModel):
    template: dict
    all: List[dict] = []
    prefer: Optional[str] = None



@router.post("/api/templates/bind")
def templates_bind(req: TplBind):
    runs = store.list()
    e = tplm.expand(req.template, req.all)
    return {"bind": tplm.auto_bind(e, runs, req.prefer), "slots": tplm.slot_report(e, runs)}



class TplResolve(BaseModel):
    template: dict
    all: List[dict] = []
    bind: Dict[str, str]
    chosen: Optional[List[int]] = None
    extraTabs: Optional[List[dict]] = None



@router.post("/api/templates/resolve")
def templates_resolve(req: TplResolve):
    return tplm.resolve(req.template, req.all, req.bind, store.list(), req.chosen, req.extraTabs)



class TemplateFolder(BaseModel):
    path: Optional[str] = None     # None: back to the default folder



@router.post("/api/templates/folder")
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



@router.post("/api/templates")
def template_save(req: TemplateSave):
    try:
        return {"template": prefs.save_template(req.template, req.replace)}
    except ValueError as e:
        fail(400, str(e))



@router.delete("/api/templates/{tid:path}")
def template_delete(tid: str):
    prefs.delete_template(tid)
    return {"ok": True}



class TemplatePath(BaseModel):
    path: str
    ids: List[str] = []



@router.post("/api/templates/import")
def template_import(req: TemplatePath):
    if not os.path.isfile(req.path):
        fail(404, "File not found.")
    try:
        return {"templates": prefs.import_templates(req.path)}
    except (ValueError, OSError, json.JSONDecodeError) as e:
        fail(400, f"Could not import: {e}")



@router.post("/api/templates/export")
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



@router.post("/api/templates/reveal")
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
