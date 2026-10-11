"""
Small JSON stores in ~/.signalviewer: recent files/sessions, work templates and
import settings remembered per folder. Every write is atomic (temp file + rename),
and a damaged file is treated as empty instead of breaking the app.
"""
import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

APP_DIR = os.path.join(os.path.expanduser("~"), ".signalviewer")
_lock = threading.Lock()


def _path(name: str) -> str:
    return os.path.join(APP_DIR, name)


def _read(name: str, default):
    try:
        with open(_path(name), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write(name: str, data) -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    tmp = _path(name) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _path(name))


# ------------------------------------------------------------------ recent
RECENT_MAX = 12


def add_recent(path: str, kind: str) -> None:
    """kind: 'file' or 'session'. Uploaded temp copies are not remembered."""
    path = os.path.abspath(path)
    if os.sep + "uploads" + os.sep in path and APP_DIR in path:
        return
    with _lock:
        items = [x for x in _read("recent.json", []) if x.get("path") != path]
        items.insert(0, {"path": path, "kind": kind, "time": time.time()})
        _write("recent.json", items[:RECENT_MAX * 2])


def list_recent() -> List[Dict[str, Any]]:
    out = []
    for x in _read("recent.json", []):
        p = x.get("path", "")
        out.append({**x, "name": os.path.basename(p), "folder": os.path.dirname(p), "exists": os.path.isfile(p)})
    files = [x for x in out if x["kind"] == "file"][:RECENT_MAX]
    sessions = [x for x in out if x["kind"] == "session"][:RECENT_MAX]
    return files + sessions


def forget_recent(path: str) -> None:
    with _lock:
        _write("recent.json", [x for x in _read("recent.json", []) if x.get("path") != path])


# --------------------------------------------------------------- templates
# One JSON file per template in ~/.signalviewer/templates, so templates can be edited, shared,
# backed up, imported and exported. Format (version 2):
#   {version: 2, id, name, description, group, slots: [{id, name, formats}], tabs: [tab...],
#    includes: [template ids], saved}
# A tab: {name, rows, cols, rowSizes, colSizes, linkX, linkY, lanes: [{name, slot}], plots: [...]};
# a plot's signals are stored by NAME with the slot (file) they come from.
DEFAULT_TEMPLATE_DIR = os.path.join(APP_DIR, "templates")


def _configured_template_dir() -> str:
    """The folder the user chose for templates (settings.json), else the default one."""
    chosen = _read("settings.json", {}).get("templateDir")
    return chosen if isinstance(chosen, str) and chosen.strip() else DEFAULT_TEMPLATE_DIR


TEMPLATE_DIR = _configured_template_dir()


def template_folder_info() -> Dict[str, Any]:
    return {"folder": TEMPLATE_DIR, "default": os.path.normcase(os.path.abspath(TEMPLATE_DIR)) == os.path.normcase(os.path.abspath(DEFAULT_TEMPLATE_DIR)),
            "exists": os.path.isdir(TEMPLATE_DIR), "defaultFolder": DEFAULT_TEMPLATE_DIR}


def set_template_dir(path: Optional[str]) -> Dict[str, Any]:
    """Use another folder for templates (None: back to the default). The templates of the current
    folder are copied there (never overwriting a file of the same name), so nothing is lost; the old
    files stay where they were. The choice is remembered in settings.json."""
    global TEMPLATE_DIR
    new = os.path.abspath(os.path.expanduser(path)) if path else DEFAULT_TEMPLATE_DIR
    try:
        os.makedirs(new, exist_ok=True)
        probe = os.path.join(new, ".sv-write-test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
    except OSError as e:
        raise ValueError(f"Templates cannot be saved in this folder: {e.strerror or e}") from None
    copied = 0
    with _lock:
        old = TEMPLATE_DIR
        if os.path.isdir(old) and os.path.normcase(os.path.abspath(old)) != os.path.normcase(new):
            for fn in sorted(os.listdir(old)):
                src, dst = os.path.join(old, fn), os.path.join(new, fn)
                if fn.lower().endswith(".json") and os.path.isfile(src) and not os.path.exists(dst):
                    try:
                        with open(src, "rb") as a, open(dst, "wb") as b:
                            b.write(a.read())
                        copied += 1
                    except OSError:
                        pass
        settings = _read("settings.json", {})
        if path:
            settings["templateDir"] = new
        else:
            settings.pop("templateDir", None)
        _write("settings.json", settings)
        TEMPLATE_DIR = new
    return {**template_folder_info(), "copied": copied}
TEMPLATE_MAX = 2_000_000          # bytes per template file


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\u0590-\u05FF -]+", "", name, flags=re.UNICODE).strip().replace(" ", "-")
    return (s or "template")[:80]


def template_v2(t: Dict[str, Any], tid: Optional[str] = None) -> Dict[str, Any]:
    """Any template (a version-1 single tab, or version 2) as version 2."""
    if t.get("version") == 2:
        out = dict(t)
    else:                                                 # version 1: one tab, one file
        tab = {k: v for k, v in t.items() if k in ("rows", "cols", "rowSizes", "colSizes", "linkX", "linkY", "lanes", "plots")}
        tab["name"] = t.get("name") or "Tab"
        out = {"version": 2, "name": t.get("name") or "Template", "slots": [{"id": "main", "name": "File"}],
               "tabs": [tab], "saved": t.get("saved")}
    out["id"] = tid or out.get("id") or _slug(out.get("name", ""))
    out.setdefault("slots", [{"id": "main", "name": "File"}])
    out.setdefault("tabs", [])
    return out


def _validate(t: Dict[str, Any]) -> Dict[str, Any]:
    t = template_v2(t)
    if not str(t.get("name") or "").strip():
        raise ValueError("A template needs a name.")
    if not isinstance(t["tabs"], list) or not isinstance(t["slots"], list) or not t["slots"]:
        raise ValueError("Not a Signal Viewer template (it needs tabs and at least one file slot).")
    if not t["tabs"] and not t.get("includes"):
        raise ValueError("The template has no tabs and includes no other template.")
    for tab in t["tabs"]:
        if not isinstance(tab, dict) or not isinstance(tab.get("plots"), list):
            raise ValueError("A tab of the template has no plots list.")
    t["name"] = str(t["name"]).strip()
    return t


def _migrate_v1():
    """templates.json (all templates in one file, version 1) -> one file per template."""
    old = os.path.join(APP_DIR, "templates.json")
    if not os.path.isfile(old):
        return
    try:
        items = _read("templates.json", [])
        os.makedirs(TEMPLATE_DIR, exist_ok=True)
        for t in items:
            v2 = template_v2(t)
            path = os.path.join(TEMPLATE_DIR, v2["id"] + ".json")
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(v2, f, ensure_ascii=False, indent=1)
        os.replace(old, old + ".migrated")
    except (OSError, ValueError):
        pass


def list_templates() -> List[Dict[str, Any]]:
    with _lock:
        _migrate_v1()
        out = []
        if os.path.isdir(TEMPLATE_DIR):
            for fn in sorted(os.listdir(TEMPLATE_DIR)):
                if not fn.lower().endswith(".json"):
                    continue
                path = os.path.join(TEMPLATE_DIR, fn)
                try:
                    if os.path.getsize(path) > TEMPLATE_MAX:
                        continue
                    with open(path, encoding="utf-8") as f:
                        t = json.load(f)
                    out.append({**template_v2(t, fn[:-5]), "file": path})
                except (OSError, ValueError):
                    out.append({"version": 2, "id": fn[:-5], "name": fn[:-5], "broken": True, "file": path, "slots": [], "tabs": []})
        return out


def save_template(tpl: Dict[str, Any], replace: bool = True) -> Dict[str, Any]:
    """Save (create or replace) a template; returns it with its id. A new template whose name is taken
    gets a free id ("Name-2")."""
    t = _validate(tpl)
    t.pop("file", None); t.pop("builtin", None)
    t["saved"] = time.time()
    with _lock:
        os.makedirs(TEMPLATE_DIR, exist_ok=True)
        tid = _slug(t["id"])
        if not replace or not tpl.get("id"):
            base, k = _slug(t["name"]), 2
            tid = base
            while os.path.exists(os.path.join(TEMPLATE_DIR, tid + ".json")):
                tid = f"{base}-{k}"; k += 1
        t["id"] = tid
        path = os.path.join(TEMPLATE_DIR, tid + ".json")
        tmp = path + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(t, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        return {**t, "file": path}


def delete_template(tid: str) -> None:
    with _lock:
        path = os.path.join(TEMPLATE_DIR, _slug(tid) + ".json")
        if os.path.isfile(path):
            os.remove(path)


def import_templates(path: str) -> List[Dict[str, Any]]:
    """A .json file with one template or a list of them (as exported) -> saved as new templates."""
    if os.path.getsize(path) > TEMPLATE_MAX * 20:
        raise ValueError("The file is too large to be a template.")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else data.get("templates") if isinstance(data, dict) and "templates" in data else [data]
    return [save_template({**t, "id": None}, replace=False) for t in items]


# ------------------------------------------------- import settings per folder
DEFAULTS = {"has_header": True, "header_row": 0, "skip_rows": 0, "delimiter": None, "time_column": "Time"}


def _is_default(settings: Optional[dict]) -> bool:
    if not settings:
        return True
    s = {k: settings.get(k) for k in DEFAULTS}
    return all((s[k] in (None, "") and DEFAULTS[k] in (None, "Time")) or s[k] == DEFAULTS[k] for k in DEFAULTS)


def remember_import(path: str, settings: Optional[dict]) -> None:
    """Remember non-default CSV import settings for the file's folder."""
    if _is_default(settings) or path.lower().endswith(".mat"):
        return
    folder = os.path.dirname(os.path.abspath(path))
    with _lock:
        prefs = _read("import_prefs.json", {})
        prefs[folder] = {k: settings.get(k) for k in DEFAULTS if k in settings}
        _write("import_prefs.json", prefs)


def import_for(path: str) -> Optional[dict]:
    return _read("import_prefs.json", {}).get(os.path.dirname(os.path.abspath(path)))


def forget_import(path: str) -> None:
    folder = os.path.dirname(os.path.abspath(path))
    with _lock:
        prefs = _read("import_prefs.json", {})
        if prefs.pop(folder, None) is not None:
            _write("import_prefs.json", prefs)
