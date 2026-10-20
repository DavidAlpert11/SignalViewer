"""T31: the user's own Python operations - list, reload, folder, example (app/pyops.py)."""
import os
import subprocess
import sys
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app import pyops
from app.common import fail
from app.store import store

router = APIRouter()


@router.get("/api/pyops")
def pyops_list():
    return pyops.listing()


@router.post("/api/pyops/reload")
def pyops_reload():
    pyops.stop()
    store.invalidate_derived("py")          # F34: the code may have changed - not the sources
    return pyops.listing()


class FolderReq(BaseModel):
    path: Optional[str] = None


@router.post("/api/pyops/folder")
def pyops_folder(req: FolderReq):
    try:
        pyops.set_folder(req.path)
        store.invalidate_derived("py")
    except ValueError as e:
        fail(400, str(e))
    return pyops.listing()


@router.post("/api/pyops/example")
def pyops_example():
    try:
        path = pyops.write_example()
    except OSError as e:
        fail(400, f"Could not write the example: {e}")
    return {**pyops.listing(), "example": path}


@router.post("/api/pyops/reveal")
def pyops_reveal():
    """Open the operations folder in the file manager (to write or edit the .py files)."""
    d = pyops.folder()
    os.makedirs(d, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            os.startfile(d)                     # type: ignore[attr-defined]
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", d],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        fail(400, f"Could not open the folder: {e}")
    return {"folder": d}
