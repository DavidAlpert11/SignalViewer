"""The built-in file browser: folders, path completion, the example files."""

import os
import re
import string
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app import prefs
from app.common import UPLOAD_DIR, fail, supported_now
from app.store import store

router = APIRouter()




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
        mask = ctypes.windll.kernel32.GetLogicalDrives()  # type: ignore[attr-defined]  # Windows only
        return [f"{d}:\\" for i, d in enumerate(string.ascii_uppercase) if mask >> i & 1]
    except (AttributeError, OSError):   # not Windows / no kernel32: probe the letters instead
        return [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]



def _wanted(exts: Optional[List[str]]):
    """Which files a listing shows: the requested extensions, else the supported data files."""
    allowed = tuple(x.lower() for x in exts) if exts else supported_now()
    return lambda name: name.lower().endswith(allowed)



def _entry(e: "os.DirEntry", is_dir: bool) -> dict:
    st = e.stat()                       # once per entry (slow on network drives)
    return {"name": e.name, "path": e.path, "dir": is_dir,
            "size": None if is_dir else st.st_size, "mtime": st.st_mtime}



# (this file is app/routes/fs.py: three levels below the project root)
EXAMPLES = os.environ.get("SV_EXAMPLES") or os.path.join(os.path.dirname(__file__), "..", "..", "..", "examples")

# the welcome screen offers these; a set with a missing file (a trimmed install) is left out whole -
# "the same mission flown twice" with one file would be wrong
EXAMPLE_SETS = [
    {"id": "flight", "files": ["uav_flight.csv"]},
    {"id": "twoFlights", "files": ["uav_flight.csv", "uav_flight_windy.csv"]},     # T44: two tracks, Compare
    {"id": "car", "files": ["run_012.csv", "run_013.csv", "run_014.csv"]},
    {"id": "ardupilot", "files": ["copter_flight.bin"]},                               # T45: a flight log
    {"id": "simVsFlight", "files": ["sim_vs_flight/sim_attitude_doublets.mat",         # C13: a model against its flight
                                     "sim_vs_flight/flight_attitude_doublets.bin"]},
]



@router.get("/api/examples")
def list_examples():
    out: list = []
    for ex in EXAMPLE_SETS:
        paths = [os.path.abspath(os.path.join(EXAMPLES, f)) for f in ex["files"]]
        if all(os.path.isfile(p) for p in paths):
            out.append({"id": ex["id"], "paths": paths})
    return out



@router.post("/api/fs/list")
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
    hidden = 0                          # files of other types: "N other files hidden" in an empty folder
    try:
        for e in os.scandir(path):
            if e.name.startswith("."):
                continue
            try:
                is_dir = e.is_dir()
                if is_dir or wanted(e.name):
                    entries.append(_entry(e, is_dir))
                else:
                    hidden += 1
            except OSError:
                continue
    except PermissionError:
        fail(403, "No permission to open this folder.")
    entries.sort(key=lambda x: (not x["dir"], x["name"].lower()))
    parent = os.path.dirname(path)
    return {"path": path, "parent": parent if parent != path else ("" if os.name == "nt" else None),
            "entries": entries, "hidden": hidden}


# ------------------------------------------------------------------ places (T24)
# The side column of the file dialog: folders of the open files, the user's favourites, recent
# folders, and this computer's usual places. Nothing here touches a folder that may hang (a network
# drive): drives come from the OS bitmask; the standard folders are a few isdir checks in the profile.

_STANDARD = (("desktop", ("Desktop", "שולחן העבודה")), ("documents", ("Documents", "מסמכים")),
             ("downloads", ("Downloads", "הורדות")))


def _standard_folders() -> List[Dict[str, str]]:
    home = os.path.expanduser("~")
    out = [{"id": "home", "path": home}]
    for key, names in _STANDARD:
        for base in (home, os.path.join(home, "OneDrive")):
            hit = next((os.path.join(base, n) for n in names if os.path.isdir(os.path.join(base, n))), None)
            if hit:
                out.append({"id": key, "path": hit})
                break
    return out


def _drives() -> List[str]:
    if os.name == "nt":
        return _windows_drives()
    roots: List[str] = []
    user = os.environ.get("USER") or os.path.basename(os.path.expanduser("~"))
    for base in ("/Volumes", f"/media/{user}", f"/run/media/{user}", "/media", "/mnt"):
        try:
            for e in os.scandir(base):
                if e.is_dir() and not e.name.startswith(".") and e.path != f"/media/{user}" and e.path not in roots:
                    roots.append(e.path)
        except OSError:
            continue
    return roots[:12]


@router.get("/api/fs/places")
def places():
    open_folders: List[str] = []
    for lr in store.runs.values():
        fp = getattr(lr.run, "file_path", "") or ""
        d = os.path.dirname(fp)
        if d and os.path.isdir(d) and d not in open_folders and not d.startswith(UPLOAD_DIR):
            open_folders.append(d)
    return {"open": open_folders, "favourites": prefs.favourite_folders(), "recent": prefs.recent_folders(),
            "standard": _standard_folders(), "drives": _drives()}


class FavouritesRequest(BaseModel):
    paths: List[str]


@router.put("/api/fs/favourites")
def set_favourites(req: FavouritesRequest):
    """The whole list, in order (pin, unpin and reorder all send it)."""
    return {"favourites": prefs.set_favourite_folders(req.paths)}



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



@router.post("/api/fs/complete")
def complete_path(req: CompleteRequest):
    """Path autocomplete for the file browser: the folders / files whose names start with
    what was typed after the last separator (case-insensitive). `common` is the longest
    completion all matches share - what Tab fills in."""
    text = os.path.expanduser(req.text or "")
    empty: Dict[str, Any] = {"dir": None, "items": [], "common": req.text or ""}
    if not text.strip():
        return empty
    # "c:" (or a lone "c" with no folder to complete in) -> drives; with a folder shown,
    # "c" is the start of a name in that folder
    if os.name == "nt" and (re.fullmatch(r"[A-Za-z]:", text) or (re.fullmatch(r"[A-Za-z]", text) and not req.base)):
        drives = [d for d in _windows_drives() if d.lower().startswith(text.lower())]
        items: list = [{"name": d, "path": d, "dir": True} for d in drives]
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
