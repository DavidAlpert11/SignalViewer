"""T60: the user's own file readers (svcore/readers.py), from the readers folder.

The folder is read again whenever a .py file in it is added, removed or saved, so editing a
reader and opening the file again is enough - no restart, no Reload button needed.
"""
import os
import threading
from typing import Any, Dict, List, Optional

from app import prefs
from svcore import readers as rd

_lock = threading.Lock()
_cache: Dict[str, Any] = {"key": None, "readers": [], "errors": []}


def default_dir() -> str:
    return os.path.join(prefs.APP_DIR, "readers")


def folder() -> str:
    chosen = prefs._read("settings.json", {}).get("readersDir")
    return chosen if isinstance(chosen, str) and chosen.strip() else default_dir()


def set_folder(path: Optional[str]) -> str:
    new = os.path.abspath(os.path.expanduser(path)) if path else None
    if new and not os.path.isdir(new):
        raise ValueError(f"Not a folder: {new}")
    with prefs._lock:
        s = prefs._read("settings.json", {})
        if new:
            s["readersDir"] = new
        else:
            s.pop("readersDir", None)
        prefs._write("settings.json", s)
    return folder()


def _key(d: str):
    try:
        names = sorted(fn for fn in os.listdir(d) if fn.endswith(".py") and not fn.startswith((".", "_")))
    except OSError:
        return (d,)
    out: List[Any] = [d]
    for fn in names:
        try:
            st = os.stat(os.path.join(d, fn))
            out.append((fn, st.st_mtime_ns, st.st_size))
        except OSError:
            pass
    return tuple(out)


def current() -> Dict[str, Any]:
    d = folder()
    key = _key(d)
    with _lock:
        if _cache["key"] != key:
            found, errors = rd.load_folder(d)
            _cache.update(key=key, readers=found, errors=errors)
        return {"folder": d, "readers": list(_cache["readers"]), "errors": list(_cache["errors"])}


def for_ext(ext: str) -> List[Dict[str, Any]]:
    ext = ext.lower()
    if not os.path.isdir(folder()):                   # the common case: no folder, nothing to read
        return []
    return [r for r in current()["readers"] if ext in r["extensions"]]


def extensions() -> List[str]:
    if not os.path.isdir(folder()):
        return []
    return sorted({e for r in current()["readers"] for e in r["extensions"]})


def listing() -> Dict[str, Any]:
    c = current()
    return {"folder": c["folder"], "default": c["folder"] == default_dir(), "errors": c["errors"],
            "readers": [{"id": r["id"], "name": r["name"], "extensions": r["extensions"], "file": r["file"]}
                        for r in c["readers"]]}


def write_example() -> str:
    d = folder()
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "example_kv_reader.py")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(rd.EXAMPLE)
    return path
