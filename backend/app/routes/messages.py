"""MSG3: messages and links in one place - a byte stream's structure proposed, parsed into a recording (MSG2), the
byte streams of the open files listed for the Messages panel, and the structure library: the structures folder
(~/.signalviewer/structures, `.svmsg.json`), the ICD layouts of the readers folder (T61) and NMEA built in."""
import json
import os
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app import prefs, userreaders
from app.common import fail, heavy
from app.store import store
from svcore.atomic import atomic_write

router = APIRouter()

STRUCT_SUFFIX = ".svmsg.json"


def structures_dir() -> str:
    """The structure library's folder (Settings key structuresDir, else ~/.signalviewer/structures)."""
    chosen = prefs._read("settings.json", {}).get("structuresDir")
    return chosen if isinstance(chosen, str) and chosen.strip() else os.path.join(prefs.APP_DIR, "structures")


class StructureRequest(BaseModel):
    sources: List[str]
    params: Optional[dict] = None            # dir (a direction column's value), header / checksum forced
    structure: Optional[dict] = None
    name: Optional[str] = None
    id: Optional[str] = None                 # a session reopened: the recording gets the id its plots refer to


def _stream_sources(req: StructureRequest):
    try:
        return [store.signal(s) for s in req.sources]
    except KeyError as e:
        fail(404, f"Signal not found: {e} - is its file still open?")


@router.post("/api/messages/suggest")
async def messages_suggest(req: StructureRequest):
    """A structure proposed from a byte stream: NMEA-like text, or the framing found with each message's fields
    guessed (16-bit values LSB / MSB first, floats, counters, flags, bytes) - for the user to correct."""
    from svcore.bytestream import StreamError
    from svcore.protocol import suggest
    sigs = _stream_sources(req)
    try:
        return {"structure": await heavy(suggest, sigs, req.params or {})}
    except StreamError as e:
        fail(400, str(e))


@router.post("/api/messages/parse")
async def messages_parse(req: StructureRequest):
    """The stream's messages by the structure, as a new recording (the same name again: replaced, its plots kept)."""
    from svcore.bytestream import StreamError
    from svcore.protocol import ProtocolError, parse, to_run
    sigs = _stream_sources(req)
    name = (req.name or "Messages").strip()[:120] or "Messages"
    try:
        out = await heavy(parse, sigs, req.structure or {}, req.params or {})
        run = to_run(name, "python:messages/" + name, out)     # "python:": no file behind it (as pushed data)
    except (StreamError, ProtocolError) as e:
        fail(400, str(e))
    lr, new = store.add_pushed(name, run, True)
    if req.id and req.id != lr.id and req.id not in store.runs and new:
        with store._lock:                            # the id the session's plots use
            store.runs[req.id] = store.runs.pop(lr.id)
            store.order[store.order.index(lr.id)] = req.id
            lr.id = req.id
    return {"run": lr.id, "new": new, "report": out["report"], "signals": [f"{lr.id}/{k}" for k in lr.run.signals],
            "runs": store.list()}


class StructurePath(BaseModel):
    path: str


def _read_structure(path: str) -> Dict[str, Any]:
    """A structure file (.svmsg.json), or an ICD layout (.icd.json / .icd.yaml, T61) read as the structure it is."""
    from svcore.protocol import check, from_icd
    with open(os.path.expanduser(path), encoding="utf-8") as f:
        text = f.read()
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError:
            raise ValueError("YAML layouts need PyYAML (pip install pyyaml), or write the layout as .icd.json.") from None
        d = yaml.safe_load(text)
    else:
        d = json.loads(text)
    if isinstance(d, dict) and "packets" in d and "messages" not in d:      # an ICD layout: the same packets
        d = from_icd(d)
    return check(d)


@router.post("/api/messages/structure")
def messages_structure_load(req: StructurePath):
    """A structure file (.svmsg.json, or an ICD layout) - checked, so a mistake is said where it is."""
    from svcore.protocol import ProtocolError
    try:
        return {"structure": _read_structure(req.path)}
    except FileNotFoundError:
        fail(404, f"No such file: {req.path}")
    except json.JSONDecodeError as e:
        fail(400, f"{os.path.basename(req.path)} is not valid JSON (line {e.lineno}): {e.msg}")
    except (ProtocolError, ValueError) as e:
        fail(400, f"{os.path.basename(req.path)}: {e}")


@router.get("/api/messages/nmea")
def messages_nmea():
    """The built-in NMEA 0183 structure (GGA, RMC, VTG, GSA, GSV, GLL, ZDA), to start from."""
    from svcore.protocol import NMEA
    return {"structure": NMEA}


# ----------------------------------------------------------------------------- the structure library

def _entries(folder: str, suffixes, source: str) -> List[Dict[str, Any]]:
    try:
        names = sorted(fn for fn in os.listdir(folder) if fn.lower().endswith(suffixes) and not fn.startswith((".", "_")))
    except OSError:
        return []
    out = []
    for fn in names:
        path = os.path.join(folder, fn)
        try:
            st = _read_structure(path)
            out.append({"key": path, "name": st.get("name") or fn, "kind": st.get("kind", "binary"), "source": source,
                        "path": path, "file": fn, "messages": len(st.get("messages") or [])})
        except Exception as e:                      # a broken file is listed with what is wrong, not left out silently
            out.append({"key": path, "name": fn, "source": source, "path": path, "file": fn, "error": str(e)})
    return out


@router.get("/api/messages/library")
def messages_library():
    """The structures to choose from: NMEA built in, the structures folder, the readers folder's ICD layouts."""
    from svcore.protocol import NMEA
    folder = structures_dir()
    return {"folder": folder,
            "items": [{"key": "builtin:nmea", "name": "NMEA 0183", "kind": "text", "source": "builtin", "messages": len(NMEA["messages"])}]
            + _entries(folder, (STRUCT_SUFFIX, ".json"), "folder")
            + _entries(userreaders.folder(), userreaders.ICD_SUFFIXES, "readers")}


class LibraryKey(BaseModel):
    key: str


@router.post("/api/messages/library/get")
def messages_library_get(req: LibraryKey):
    if req.key == "builtin:nmea":
        return messages_nmea()
    known = {e["key"] for e in messages_library()["items"]}
    if req.key not in known:
        fail(404, f"Not in the structure library: {req.key} (the file was moved or deleted?)")
    return messages_structure_load(StructurePath(path=req.key))


class LibrarySave(BaseModel):
    structure: dict
    name: Optional[str] = None
    overwrite: bool = False


@router.post("/api/messages/library/save")
def messages_library_save(req: LibrarySave):
    """A structure into the library's folder as <name>.svmsg.json (a file to copy to a colleague, too)."""
    from svcore.protocol import ProtocolError, check
    try:
        st = check(req.structure)
    except ProtocolError as e:
        fail(400, f"The structure: {e}")
    base = re.sub(r"[^\w-]+", "_", (req.name or st.get("name") or "messages").strip()).strip("_") or "messages"
    folder = structures_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, base + STRUCT_SUFFIX)
    if os.path.exists(path) and not req.overwrite:
        fail(409, f"{base + STRUCT_SUFFIX} is already in the library ({folder}). Save it again to replace it.")
    atomic_write(path, json.dumps(st, indent=1, ensure_ascii=False) + "\n")
    return {"path": path, "key": path}


@router.post("/api/messages/library/reveal")
def messages_library_reveal():
    """Open the structures folder in the file manager (to copy, share or edit the files)."""
    import subprocess
    import sys
    folder = structures_dir()
    os.makedirs(folder, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            os.startfile(folder)                     # type: ignore[attr-defined]
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        fail(400, f"Could not open the folder: {e}")
    return {"folder": folder}


# ----------------------------------------------------------------------------- the byte streams of the open files

class StreamsRequest(BaseModel):
    streams: Optional[List[dict]] = None          # ws.messageStreams - the definitions the user made
    runs: Optional[List[str]] = None              # the files to look in (default: every open one)


def _streams(defs: List[dict], only: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    from app.reportparts import find_streams
    rids = [i for i in store.order if i in store.runs and (only is None or i in only)]
    owner: Dict[str, str] = {}                    # a source signal -> the definition it belongs to (sources joined)
    for d in defs:
        for s in d.get("sources") or []:
            owner[str(s)] = ",".join(str(x) for x in d.get("sources") or [])
    out = []
    for s in find_streams(store, rids, defs):
        ids = s["ids"]
        # the key a definition of these bytes has: its sources (a direction column is not one of them)
        key = owner.get(ids[0]) or (",".join(ids) if s["params"].get("dir") is None else ids[0])
        row: Dict[str, Any] = {"key": key, "name": s["name"], "rid": s["rid"], "file": store.get(s["rid"]).name,
                               "ids": ids, "params": {k: v for k, v in s["params"].items()}}
        if s.get("error"):
            row["error"] = s["error"]
        else:
            r = s["r"]
            row.update(count=r["count"], bytes=r["bytes"], header=r["header"], framing=r["framing"],
                       checksum=(r["checksum"] or {}).get("scheme"), errors=r["errors"], duration=r["duration"],
                       types=[{"type": x["type"], "count": x["count"], "rate": x["rate"]} for x in r["types"][:12]],
                       typed=r["typeOffset"] is not None)
        out.append(row)
    return out


@router.post("/api/messages/streams")
async def messages_streams(req: StreamsRequest):
    """The byte streams in the open files (the defined ones and the ones found by themselves), each with its
    messages at a glance - count, header, checksum, the types and their rates - for the Messages panel."""
    return {"streams": await heavy(_streams, req.streams or [], req.runs)}
