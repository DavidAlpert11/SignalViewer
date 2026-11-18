"""The built-in file browser: folders, path completion, the example files."""

import os
import re
import shutil
import string
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app import prefs
from app.common import UPLOAD_DIR, fail, supported_now
from app.store import store
from app.version import __version__
from svcore import example_data

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
    {"id": "bench", "files": ["bench/pump_run_07.parquet"]},                       # E4: a pump on a test bench (Parquet)
    {"id": "ardupilot", "files": ["copter_flight.bin"]},                               # T45: a flight log
    {"id": "simVsFlight", "files": ["sim_vs_flight/sim_attitude_doublets.mat",         # C13: a model against its flight
                                     "sim_vs_flight/flight_attitude_doublets.bin"]},
    {"id": "investigate", "files": ["investigate/heavy_payload.csv",                  # the Investigate tools,
                                    "investigate/light_payload.csv"]},                # with a known answer
    # FL1: "open": "summary" = the folder of the first file summed up with its measures.json, one row per recording in Sweeps
    {"id": "folderOfFlights", "open": "summary", "files": ["folder_of_flights/measures.json", "folder_of_flights/X8-A_2026-09-02.bin"]},
    # review (owner, 2026-11-13: a clear demo for everything): the single results table opens in Sweeps -
    # "open" says where; the last file is what the area opens
    {"id": "sweepTable", "open": "sweep", "files": ["sweeps/drone_tuning.csv", "sweeps/drone_tuning.svsweep"]},
    # --- lane W0 --- the 2026-11-13 round's two sets: "open": "study" = the card opens the study file
    # (the last file) in the Sweeps panel, not the tables as recordings.
    {"id": "commonGains", "open": "study",                                            # W14: one gain set, 3 drones
     "files": ["drones/drone_a.csv", "drones/drone_b.csv", "drones/drone_c.csv", "drones/drones.svstudy.json"]},
    {"id": "smartSweepDemo", "open": "study",                                         # W18: converge on your PC
     "files": ["smart_sweep_demo/sim.py", "smart_sweep_demo/demo.svstudy.json"]},
]



# owner, 2026-11-18: the packages carry no heavy example recordings - the app writes them on first use (svcore/
# example_data), once per version, here; the small files beside them (checks.json, measures.json...) are copied in
EXAMPLES_MADE = os.path.join(prefs.APP_DIR, "examples", __version__)
_MAKING = threading.Lock()


def _example_root(ex: Dict[str, Any]) -> Optional[str]:
    """Where an example's files are: the shipped folder when it has them all (from source: the files in git),
    else the folder they are written to - None when a file is neither shipped nor can be written here."""
    if all(os.path.isfile(os.path.join(EXAMPLES, f)) for f in ex["files"]):
        return EXAMPLES
    if all(os.path.isfile(os.path.join(EXAMPLES, f)) or example_data.can_write(f) for f in ex["files"]):
        return EXAMPLES_MADE
    return None


def _example_entry(ex: Dict[str, Any], root: str) -> Dict[str, Any]:
    paths = [os.path.abspath(os.path.join(root, f)) for f in ex["files"]]
    return {"id": ex["id"], "paths": paths, **({"open": ex["open"]} if "open" in ex else {})}


@router.get("/api/examples")
def list_examples():
    return [_example_entry(ex, root) for ex in EXAMPLE_SETS if (root := _example_root(ex))]


@router.post("/api/examples/{ex_id}/prepare")
def prepare_example(ex_id: str):
    """The example's files ready to open: written now if they are not yet (a second or two, once per version)."""
    ex = next((e for e in EXAMPLE_SETS if e["id"] == ex_id), None)
    root = _example_root(ex) if ex else None
    if ex is None or root is None:
        fail(404, f"The example {ex_id} is not part of this installation.")
    if root == EXAMPLES_MADE:
        with _MAKING:
            try:
                for folder in sorted({os.path.dirname(f) for f in ex["files"]}):     # the small files beside them
                    src, dst = os.path.join(EXAMPLES, folder), os.path.join(EXAMPLES_MADE, folder)
                    os.makedirs(dst, exist_ok=True)
                    for name in os.listdir(src) if os.path.isdir(src) else []:
                        p = os.path.join(src, name)
                        if os.path.isfile(p) and not os.path.isfile(os.path.join(dst, name)):
                            shutil.copy2(p, dst)
                missing = [f for f in ex["files"] if not os.path.isfile(os.path.join(EXAMPLES_MADE, f))]
                if missing:
                    example_data.write(missing, EXAMPLES_MADE)
            except OSError as e:
                fail(500, f"Could not write the example's files to {EXAMPLES_MADE}: {e}. "
                          "Check that this folder can be written (disk space, permissions) and try again.")
    return _example_entry(ex, root)



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


# ------------------------------------------------------------------ New folder, Rename, Delete (PLAN 2026-11-16 §7b)
# The file dialog works like a browser's: a folder made where you save, a file renamed or moved to the recycle bin
# (app/trash.py - never deleted for good). Only in the user's own folders: under the home folder or on a data drive
# (another drive than the system's; /media, /mnt, /Volumes) - never the system's folders, a hidden one (the app's own
# ~/.signalviewer among them), a drive itself or the home / Desktop / Documents / Downloads folders themselves.

_BAD_CHARS = set('<>:"|?*') if os.name == "nt" else set()
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def _norm(p: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.expanduser(p)))


def _under(p: str, root: str) -> bool:
    return p == root or p.startswith(root.rstrip("\\/") + os.sep)


def _own_roots() -> List[str]:
    roots = [_norm("~")]
    if os.name == "nt":
        system = (os.environ.get("SystemDrive") or "C:").upper()
        roots += [_norm(d) for d in _windows_drives() if not d.upper().startswith(system)]
    else:
        roots += [_norm(d) for d in ("/media", "/mnt", "/Volumes", "/run/media") if os.path.isdir(d)]
    return roots


def _check_own(path: str, target: bool) -> str:
    """The real path of `path` if it is in the user's own folders (else a 403 that says so). `target`: it is the
    thing renamed or deleted (not only where something is made) - a drive or a standard folder itself is refused."""
    p = _norm(path)
    root = next((r for r in _own_roots() if _under(p, r)), None)
    if root is None:
        fail(403, f"{path} is not in your own folders (your home folder or a data drive) - "
                  "Signal Viewer does not change system folders. Use your file manager for it.")
    if any(part.startswith(".") for part in os.path.relpath(p, root).split(os.sep) if part != "."):
        fail(403, f"{path} is in a hidden folder - Signal Viewer does not change hidden folders (its own settings live there).")
    home = _norm("~")
    if target:
        fixed = {home, *(_norm(s["path"]) for s in _standard_folders()), *_own_roots(), *(_norm(d) for d in _drives())}
        if p in fixed:
            fail(403, f"{path} is a drive or one of your main folders - it is not renamed or deleted from here.")
        open_files = {_norm(getattr(lr.run, "file_path", "") or "") for lr in store.runs.values()}
        if any(f and _under(f, p) for f in open_files):
            fail(409, f"{os.path.basename(path)} is open in Signal Viewer - close it first (File > Close), then try again.")
    return os.path.realpath(os.path.expanduser(path))


def _check_name(name: str) -> str:
    n = (name or "").strip()
    if not n or n in (".", "..") or any(c in n for c in "\\/") or any(c in _BAD_CHARS for c in n) \
            or len(n) > 255 or (os.name == "nt" and n.split(".")[0].upper() in _RESERVED):
        fail(400, f"\"{name}\" cannot be a file or folder name - use letters, digits, spaces, - and _"
                  + (", without < > : \" | ? *." if os.name == "nt" else ", without /."))
    if n.startswith("."):
        fail(400, f"\"{name}\" would be hidden (it starts with a dot) - choose a name without the dot at the start.")
    return n


class MkdirRequest(BaseModel):
    parent: str
    name: str


@router.post("/api/fs/mkdir")
def make_folder(req: MkdirRequest):
    parent = _check_own(req.parent, target=False)
    if not os.path.isdir(parent):
        fail(404, f"Folder not found: {req.parent}")
    path = os.path.join(parent, _check_name(req.name))
    if os.path.lexists(path):
        fail(409, f"{os.path.basename(path)} already exists in this folder - choose another name.")
    try:
        os.mkdir(path)
    except PermissionError:
        fail(403, f"No permission to make a folder in {parent}.")
    except OSError as e:
        fail(500, f"Could not make the folder: {e.strerror or e}.")
    return {"path": path}


class RenameRequest(BaseModel):
    path: str
    name: str


@router.post("/api/fs/rename")
def rename_entry(req: RenameRequest):
    src = _check_own(req.path, target=True)
    if not os.path.lexists(src):
        fail(404, f"Not found: {req.path} - it may have been moved or deleted; the folder is listed again.")
    dst = os.path.join(os.path.dirname(src), _check_name(req.name))
    if os.path.normcase(dst) != os.path.normcase(src) and os.path.lexists(dst):
        fail(409, f"{os.path.basename(dst)} already exists in this folder - choose another name.")
    try:
        os.rename(src, dst)
    except PermissionError:
        fail(403, f"No permission to rename {os.path.basename(src)} - is it open in another program?")
    except OSError as e:
        fail(500, f"Could not rename it: {e.strerror or e}.")
    return {"path": dst}


class DeleteRequest(BaseModel):
    path: str


@router.post("/api/fs/delete")
def delete_entry(req: DeleteRequest):
    """To the recycle bin (app/trash.py): it can be put back from there."""
    from app.trash import to_trash
    path = _check_own(req.path, target=True)
    if not os.path.lexists(path):
        fail(404, f"Not found: {req.path} - it may have been moved or deleted already.")
    try:
        where = to_trash(path)
    except PermissionError:
        fail(403, f"No permission to delete {os.path.basename(path)} - is it open in another program?")
    except OSError as e:
        fail(500, f"Could not move {os.path.basename(path)} to the recycle bin: {e.strerror or e}. Nothing was deleted.")
    return {"path": path, "trash": where}
