"""T60: the user's own file readers (svcore/readers.py), from the readers folder.

The folder is read again whenever a .py file in it is added, removed or saved, so editing a
reader and opening the file again is enough - no restart, no Reload button needed.
"""
import os
import threading
from typing import Any, Dict, List, Optional

from app import prefs
from app.atomic import atomic_open, atomic_write
from app.subproc import Worker, WorkerGone
from svcore import icd, readerworker
from svcore import readers as rd

# 26.A2: the user's Python readers run in their own process - a crash or an endless loop there is
# stopped and the app keeps working (the ICD layouts are data, decoded here)
TIMEOUT = float(os.environ.get("SV_READER_TIMEOUT", "600"))   # seconds one file's reading may take
LIST_TIMEOUT = 60.0
_worker = Worker(readerworker.main, "signalviewer-file-readers", lambda: (folder(),))
# In the app (app/main.py turns it on) the readers run in the worker. The Python API and the command
# line are the user's own script: there they run in it, as before - a worker started with "spawn"
# re-imports the script, which fails in a script without `if __name__ == "__main__":`.
ISOLATED = False


def isolate(on: bool = True) -> None:
    global ISOLATED
    if on != ISOLATED:
        ISOLATED = on
        with _lock:
            _cache["key"] = None               # read the folder again, the other way

ICD_SUFFIXES = (".icd.json", ".icd.yaml", ".icd.yml")

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
        names = sorted(fn for fn in os.listdir(d) if fn.lower().endswith((".py",) + ICD_SUFFIXES)
                       and not fn.startswith((".", "_")))
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


def _layout_reader(lay: Dict[str, Any]):
    return lambda path: icd.decode(lay, path)


def _load_layouts(d: str):
    """T61: every <name>.icd.json / .icd.yaml in the folder is a reader of raw binary recordings."""
    found: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    try:
        names = sorted(fn for fn in os.listdir(d) if fn.lower().endswith(ICD_SUFFIXES) and not fn.startswith((".", "_")))
    except OSError:
        return found, errors
    for fn in names:
        path = os.path.join(d, fn)
        try:
            lay = icd.read_layout(path)
        except icd.LayoutError as e:
            errors.append({"file": fn, "error": str(e)})
            continue
        found.append({"name": lay["name"], "extensions": lay["extensions"], "file": fn, "id": f"{fn}:layout",
                      "fn": _layout_reader(lay), "path": path, "kind": "icd"})
    return found, errors


def _remote(meta: Dict[str, Any]):
    """A Python reader as a function of the path that runs it in the worker process."""
    def read(path: str) -> Any:
        try:
            res = _worker.call(("read", meta["id"], path), TIMEOUT)
        except WorkerGone as e:
            if e.timed_out:
                raise rd.ReaderError(f'The reader "{meta["name"]}" took longer than {TIMEOUT:g} s and was stopped '
                                     f'(SV_READER_TIMEOUT). Check {meta["file"]} for a loop that never ends.') from None
            raise rd.ReaderError(f'The reader "{meta["name"]}" crashed its process (exit code {e.exitcode}); the app kept working '
                                 f'and starts it again for the next file. Check {meta["file"]}.') from None
        if res[0] == "err":
            raise rd.ReaderError(res[1])
        return res[1]
    return read


def _load_python(d: str):
    """The folder's Python readers, as the worker process loaded them."""
    if not any(fn.lower().endswith(".py") and not fn.startswith((".", "_")) for fn in os.listdir(d)):
        return [], []
    try:
        res = _worker.call(("list",), LIST_TIMEOUT)
    except WorkerGone as e:                 # a file that loops or crashes while it is loaded
        why = f"loading it took longer than {LIST_TIMEOUT:g} s" if e.timed_out else f"loading it crashed Python (exit code {e.exitcode})"
        return [], [{"file": "", "error": f"The readers folder could not be read: {why}."}]
    return [{**m, "fn": _remote(m)} for m in res["readers"]], list(res["errors"])


def current() -> Dict[str, Any]:
    d = folder()
    key = _key(d)
    with _lock:
        if _cache["key"] != key:
            _worker.stop()                  # a file was added / saved / removed: the worker loads them again
            if not os.path.isdir(d):
                found, errors = [], []
            else:
                found, errors = _load_python(d) if ISOLATED else rd.load_folder(d)
            lf, le = _load_layouts(d)
            _cache.update(key=key, readers=found + lf, errors=errors + le)
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
            "readers": [{"id": r["id"], "name": r["name"], "extensions": r["extensions"], "file": r["file"],
                         "kind": r.get("kind", "python")}
                        for r in c["readers"]]}


def write_example_icd() -> Dict[str, str]:
    """The example layout in the readers folder and a recording for it (in the folder given)."""
    import json
    d = folder()
    os.makedirs(d, exist_ok=True)
    lay = os.path.join(d, "example_bench.icd.json")
    if not os.path.exists(lay):
        with atomic_open(lay) as f:
            json.dump(icd.EXAMPLE, f, indent=2)
    return {"layout": lay}


def write_example() -> str:
    d = folder()
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "example_kv_reader.py")
    if not os.path.exists(path):
        atomic_write(path, rd.EXAMPLE)
    return path
