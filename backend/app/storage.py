"""What the app keeps on disk besides the user's own files, how big it is, and clearing it.

    cache/     CSV files over SV_CACHE_MIN_MB converted to a binary copy (svcore/csv_loader.py):
               reopening a big CSV is near-instant. Kept within limits (below) automatically.
    uploads/   files dropped into a BROWSER window are copied here (a browser does not give the
               path). Copies older than UPLOAD_DAYS are removed at start.
    tiles/     online map tiles seen so far (app/tiles.py) - what makes those places work offline.

Nothing in use is removed: a cache entry an open file reads from, the copy an open file is.
"""

import logging
import os
import shutil
import time
from typing import Dict, Iterable, List, Set

import numpy as np

from app import tiles
from app.common import UPLOAD_DIR
from app.store import store
from svcore import csv_loader

log = logging.getLogger("signalviewer").getChild(__name__)

UPLOAD_DAYS = 7


def _size(path: str) -> int:
    total = 0
    for here, _d, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(here, f))
            except OSError:
                pass
    return total


def cache_dirs_in_use() -> Set[str]:
    """Cache entries an open file reads from (its signals are memory maps into them)."""
    out: Set[str] = set()
    root = os.path.abspath(csv_loader.CACHE_DIR)
    for lr in list(store.runs.values()):
        arrays: List[object] = [lr.run.time] + [s.__dict__.get("data") for s in lr.run.signals.values()]
        for a in arrays:
            fn = getattr(a, "filename", None) if isinstance(a, np.memmap) else None
            if fn:
                d = os.path.dirname(os.path.abspath(fn))
                if os.path.dirname(d) == root:
                    out.add(d)
                    break
    return out


def uploads_in_use() -> Set[str]:
    root = os.path.abspath(UPLOAD_DIR)
    out: Set[str] = set()
    for lr in list(store.runs.values()):
        p = os.path.abspath(lr.run.file_path)
        if p.startswith(root + os.sep):
            out.add(os.path.join(root, os.path.relpath(p, root).split(os.sep)[0]))
    return out


def info() -> Dict[str, object]:
    return {
        "cache": {"path": csv_loader.CACHE_DIR, "bytes": _size(csv_loader.CACHE_DIR)},
        "uploads": {"path": UPLOAD_DIR, "bytes": _size(UPLOAD_DIR)},
        "tiles": {"path": tiles.CACHE, "bytes": _size(tiles.CACHE)},
    }


def _remove_children(root: str, keep: Iterable[str]) -> Dict[str, int]:
    keep = {os.path.abspath(k) for k in keep}
    freed, kept = 0, 0
    try:
        names = os.listdir(root)
    except OSError:
        return {"freed": 0, "kept": 0}
    for name in names:
        p = os.path.abspath(os.path.join(root, name))
        if p in keep:
            kept += 1
            continue
        size = _size(p) if os.path.isdir(p) else (os.path.getsize(p) if os.path.isfile(p) else 0)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        else:
            try:
                os.remove(p)
            except OSError:
                pass
        if not os.path.exists(p):
            freed += size
        else:
            kept += 1                       # locked (Windows: another program has it open)
    return {"freed": freed, "kept": kept}


def clear(what: Iterable[str]) -> Dict[str, Dict[str, int]]:
    """Clear "cache", "uploads" and / or "tiles"; what is in use stays."""
    out: Dict[str, Dict[str, int]] = {}
    for w in what:
        if w == "cache":
            out[w] = _remove_children(csv_loader.CACHE_DIR, cache_dirs_in_use())
        elif w == "uploads":
            out[w] = _remove_children(UPLOAD_DIR, uploads_in_use())
        elif w == "tiles":
            out[w] = _remove_children(tiles.CACHE, ())
    log.info("cleared %s", out)
    return out


def startup_cleanup() -> None:
    """At start: dropped-file copies older than UPLOAD_DAYS, and the CSV cache within its limits."""
    try:
        cutoff = time.time() - UPLOAD_DAYS * 86400
        for name in os.listdir(UPLOAD_DIR) if os.path.isdir(UPLOAD_DIR) else []:
            p = os.path.join(UPLOAD_DIR, name)
            try:
                if os.path.getmtime(p) < cutoff:
                    shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
            except OSError:
                continue
        csv_loader.prune_cache()
    except Exception:                         # tidying up must never stop the app
        log.warning("start-up cleanup failed", exc_info=True)


csv_loader.CACHE_IN_USE = cache_dirs_in_use     # the cache never prunes what an open file reads
