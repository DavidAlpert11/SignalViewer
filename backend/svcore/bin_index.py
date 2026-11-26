"""The index of a big DataFlash log kept in the app's cache folder (CC21: from svcore/bin_loader.py) - the time
vectors and where each message is, not the values - so opening the same log again is near-instant."""
import hashlib
import json
import logging
import os
import pickle
import shutil
import threading
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np

from svcore.bin_lazy import _BinSource, LazyField

if TYPE_CHECKING:
    from svcore.bin_loader import DataFlash

log = logging.getLogger("signalviewer").getChild("svcore.bin_loader")


# ---------------------------------------------------------------------------- index cache
# A big log opened again (every start restores the last session) used to be read from scratch.
# Its index - the time vectors and where each message is in the file, NOT the values - is kept in
# the app's cache folder (the CSV cache's, with its size limits, cleaning and Settings button) and
# memory-mapped when the same file is opened again: near-instant, and almost no RAM until a signal
# is plotted. Used only when size, time stamp and a fingerprint of the bytes all match. Written
# only for a log that is not being written to (live files change every second).
INDEX_VERSION = 3   # v2: old GPS on its boot time (T); v3: O2 - damage left out (a v2 index keeps the phantom
                    # signals, and its pickled DataFlash lacks the O2 fields that live mode reads)
INDEX_QUIET_S = 60.0


def _index_dir(path: str, st: os.stat_result) -> Optional[str]:
    from svcore import csv_loader as cl
    if not cl.CACHE_ENABLED:
        return None
    fp = cl.content_fingerprint(path, st.st_size)
    raw = json.dumps([INDEX_VERSION, "bin", os.path.abspath(path), st.st_size, st.st_mtime_ns, fp])
    return os.path.join(cl.CACHE_DIR, "bin-" + hashlib.sha1(raw.encode()).hexdigest())


def _index_save(d: str, path: str, df: "DataFlash", sigs: Dict[str, tuple], end: int, report: dict):
    """Arrays shared by several signals (one time vector per message instance) are written once."""
    arrays: List[np.ndarray] = []
    ids: Dict[int, int] = {}

    def ref(a) -> int:
        k = id(a)
        if k not in ids:
            ids[k] = len(arrays)
            arrays.append(a)
        return ids[k]

    entries: List[tuple] = []
    for name, v in sigs.items():
        t, y = v[0], v[1]
        labels = v[2] if len(v) > 2 else None
        if isinstance(y, LazyField):
            entries.append((name, ref(t), "lazy", (ref(y.pos), y.off, y.dt, np.dtype(y.out).str, y.fmult, y.mult), labels))
        else:
            entries.append((name, ref(t), "data", ref(y), labels))
    src, df.src = df.src, None
    try:
        state = pickle.dumps({"df": df, "entries": entries, "end": end, "report": report}, protocol=4)
    finally:
        df.src = src

    def write():
        tmp = d + ".tmp"
        try:
            shutil.rmtree(tmp, ignore_errors=True)
            os.makedirs(tmp)
            for i, a in enumerate(arrays):
                np.save(os.path.join(tmp, f"a{i}.npy"), np.ascontiguousarray(a))
            with open(os.path.join(tmp, "state.pkl"), "wb") as f:
                f.write(state)
            with open(os.path.join(tmp, "meta.json"), "w", encoding="utf-8") as f:
                json.dump({"source": os.path.abspath(path), "kind": "bin-index", "arrays": len(arrays)}, f)
            shutil.rmtree(d, ignore_errors=True)
            os.replace(tmp, d)
            from svcore.csv_loader import prune_cache
            prune_cache(keep=d, source=os.path.abspath(path))
        except Exception as e:                 # a cache only: never fail the open for it
            log.info(f"Could not write the log index: {e}")
            shutil.rmtree(tmp, ignore_errors=True)

    # the arrays are never changed in place (live mode replaces them), so writing them while the
    # user already works is safe - the open does not wait for the disk
    threading.Thread(target=write, daemon=True, name="bin-index").start()


def _index_load(d: str, path: str):
    meta = os.path.join(d, "meta.json")
    if not os.path.isfile(meta):
        return None
    try:
        with open(os.path.join(d, "state.pkl"), "rb") as f:
            state = pickle.load(f)                 # the app's own cache folder, written above
        with open(meta, encoding="utf-8") as f:
            n = json.load(f)["arrays"]
        arrays = [np.load(os.path.join(d, f"a{i}.npy"), mmap_mode="r") for i in range(n)]
        try:
            os.utime(meta)                         # last used (the cache's size limit)
        except OSError:
            pass
    except Exception as e:
        log.info(f"Damaged log index, reading the log instead: {e}")
        shutil.rmtree(d, ignore_errors=True)
        return None
    df: DataFlash = state["df"]
    df.src = _BinSource(path)
    sigs: Dict[str, tuple] = {}
    for name, ti, kind, payload, labels in state["entries"]:
        t = arrays[ti]
        if kind == "lazy":
            pi, off, dt, out, fmult, mult = payload
            y: Any = LazyField(df.src, arrays[pi], off, dt, np.dtype(out), fmult, mult)
        else:
            y = arrays[payload]
        sigs[name] = (t, y, labels) if labels else (t, y)
    return df, sigs, state["end"], state["report"]
