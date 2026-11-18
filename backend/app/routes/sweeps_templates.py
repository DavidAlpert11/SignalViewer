"""Sweeps' templates (a table's columns and its question, kept to use again on the next table): saved, listed,
exported to a file, imported, deleted. Split out of app/routes/sweep.py (2026-11-18)."""
import json
import os
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.common import atomic_open, atomic_write, fail

router = APIRouter()

TEMPLATES = os.path.join(os.path.expanduser("~"), ".signalviewer", "sweep_templates")


class TemplateReq(BaseModel):
    name: str
    template: Optional[Dict[str, Any]] = None


def _tpl_path(name: str) -> str:
    safe = "".join(ch for ch in name.strip() if ch not in '\\\\/:*?"<>|').strip() or "template"
    return os.path.join(TEMPLATES, safe + ".json")


@router.get("/api/sweep/templates")
def sweep_templates():
    out = []
    if os.path.isdir(TEMPLATES):
        for n in sorted(os.listdir(TEMPLATES)):
            # a save in progress writes a hidden ".<name>.<pid>.tmp.json" first (svcore/atomic.py): not a template
            if n.endswith(".json") and not n.startswith("."):
                try:
                    with open(os.path.join(TEMPLATES, n), encoding="utf-8") as f:
                        out.append(json.load(f))
                except (OSError, ValueError):
                    continue
    return {"templates": out, "folder": TEMPLATES}


TEMPLATE_KIND = "signalviewer-sweep-template"


def _tpl_write(name: str, tpl: Dict[str, Any]) -> None:
    with atomic_open(_tpl_path(name)) as f:
        json.dump({**tpl, "kind": TEMPLATE_KIND, "name": name.strip(), "saved": time.strftime("%Y-%m-%d %H:%M")}, f, indent=1)


@router.post("/api/sweep/templates/save")
def sweep_template_save(req: TemplateReq):
    _tpl_write(req.name, req.template or {})
    return sweep_templates()


class TemplateFileReq(BaseModel):
    name: Optional[str] = None
    path: str


@router.post("/api/sweep/templates/export")
def sweep_template_export(req: TemplateFileReq):
    """A template to a file of its own - to send to a colleague, keep with a project."""
    src = _tpl_path(req.name or "")
    if not os.path.isfile(src):
        fail(404, f"No template named {req.name!r}.")
    path = os.path.abspath(os.path.expanduser(req.path))
    try:
        with open(src, encoding="utf-8") as f:
            atomic_write(path, f.read())
    except OSError as e:
        fail(400, f"Could not write {path}: {e}")
    return {"path": path}


@router.post("/api/sweep/templates/import")
def sweep_template_import(req: TemplateFileReq):
    """A template from a file (exported here, by a colleague): kept under its name, or that name
    with (2), (3)... when one is taken."""
    path = os.path.abspath(os.path.expanduser(req.path))
    try:
        with open(path, encoding="utf-8") as f:
            tpl = json.load(f)
    except (OSError, ValueError) as e:
        fail(400, f"Could not read {path}: {e}")
    if not isinstance(tpl, dict) or not isinstance(tpl.get("columns"), list) or not isinstance(tpl.get("question"), dict):
        fail(400, f"{os.path.basename(path)} is not a Sweeps template.")
    base = (req.name or tpl.get("name") or os.path.splitext(os.path.basename(path))[0]).strip()
    name, k = base, 2
    while os.path.isfile(_tpl_path(name)):
        name, k = f"{base} ({k})", k + 1
    _tpl_write(name, tpl)
    return {**sweep_templates(), "name": name}


@router.post("/api/sweep/templates/delete")
def sweep_template_delete(req: TemplateReq):
    p = _tpl_path(req.name)
    if os.path.isfile(p):
        os.remove(p)
    return sweep_templates()
