"""T39: arrays sent from Python into the open app (app/push.py; the client is
signalviewer/push_client.py)."""
import hmac
import logging
import os
import shutil
import sys
from typing import List

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app import push
from app.common import fail
from app.store import store

router = APIRouter()
log = logging.getLogger("signalviewer").getChild(__name__)
# the client as a file: from the source folder, or bundled as data in the packaged app (modules
# there live in an archive, not as .py files)
CLIENT_PATHS = [os.path.join(getattr(sys, "_MEIPASS", ""), "clients", "push_client.py"),
                os.path.join(os.path.dirname(__file__), "..", "..", "signalviewer", "push_client.py")]


@router.post("/api/push")
async def push_data(request: Request, name: str = "Python", replace: bool = True, plot: bool = True):
    if not hmac.compare_digest(request.headers.get("x-sv-token", ""), push.TOKEN):
        fail(403, "Wrong or missing token: use the Signal Viewer Python client (it reads the token "
                  "this app wrote to ~/.signalviewer/push.json at start).")
    name = (name or "Python").strip()[:120] or "Python"
    try:
        t, arrays = push.parse(await request.body())
    except ValueError as e:
        fail(400, str(e))
    lr, new = store.add_pushed(name, push.make_run(name, t, arrays), replace)
    seq = push.add_event(lr.id, name, plot, new)
    return {"run": lr.id, "name": lr.name, "signals": [f"{lr.id}/{k}" for k in lr.run.signals],
            "new": new, "seq": seq}


class ExternalOpen(BaseModel):
    paths: List[str]


@router.post("/api/open-external")
def open_external(req: ExternalOpen, request: Request):
    """T54: files opened from outside while the app runs (a second start hands them over, app/instance.py).
    The page opens them like files chosen in the dialog (missing ones are reported there)."""
    if not hmac.compare_digest(request.headers.get("x-sv-token", ""), push.TOKEN):
        fail(403, "Wrong or missing token (only a Signal Viewer start on this computer can hand files over).")
    paths = [os.path.abspath(os.path.expanduser(p)) for p in req.paths if p and p.strip()][:200]
    if not paths:
        fail(400, "No files to open.")
    seq = push.add_open_event(paths)
    for f in list(push.ON_OPEN):
        try:
            f()
        except Exception:                # bringing the window forward is a nicety; the files open anyway
            log.warning("could not bring the window to the front", exc_info=True)
    return {"seq": seq, "paths": paths}


@router.get("/api/push/events")
def push_events(since: int = 0, opens: bool = False):
    return push.events_since(since, opens)


class ClientSave(BaseModel):
    path: str


@router.post("/api/push/save-client")
def push_save_client(req: ClientSave):
    """Save the client next to the user's notebook / simulation (one file, numpy only)."""
    dest = os.path.abspath(os.path.expanduser(req.path))
    if os.path.isdir(dest):
        dest = os.path.join(dest, "signalviewer_push.py")
    src = next((p for p in CLIENT_PATHS if os.path.isfile(p)), None)
    if src is None:
        fail(500, "The Python client is missing from this installation.")
    try:
        shutil.copyfile(src, dest)
    except OSError as e:
        fail(400, f"Could not save the client: {e}")
    return {"path": dest}
