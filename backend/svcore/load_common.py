"""What every loader shares (CC21: it lived in csv_loader.py, and the .bin, MCAP and flight-log readers reached into the
CSV reader for it): the per-thread progress and cancel of a background load, text values as state codes, and a file's
content fingerprint (the caches' key). csv_loader re-exports these names."""
import hashlib
import os
import threading as _threading
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

_ctx = _threading.local()


class LoadCancelled(Exception):
    pass


def set_progress_context(report=None, cancelled=None):
    """report(fraction 0..1, phase str); cancelled() -> bool. Per thread."""
    _ctx.report, _ctx.cancelled = report, cancelled


def _progress(frac: float, phase: str = "read"):
    rep = getattr(_ctx, "report", None)
    if rep:
        rep(max(0.0, min(1.0, frac)), phase)
    can = getattr(_ctx, "cancelled", None)
    if can and can():
        raise LoadCancelled()


def encode_text(values, labels: Optional[Dict[int, str]] = None) -> Tuple[np.ndarray, Dict[int, str]]:
    """Text values -> float codes (empty -> NaN). Codes follow the order of first appearance and
    continue an existing {code: text} map (live mode adds the new texts at the end)."""
    s = pd.Series(np.asarray(values, dtype=object))
    s = s.map(lambda v: v.strip() if isinstance(v, str) else v)
    s = s.where(s.map(lambda v: isinstance(v, str) and v != ""), None)
    codes, uniques = pd.factorize(s, sort=False, use_na_sentinel=True)
    labels = dict(labels or {})
    rev = {v: k for k, v in labels.items()}
    nxt = (max(labels) + 1) if labels else 0
    remap = np.empty(len(uniques) + 1, dtype=np.float64)
    remap[-1] = np.nan                       # sentinel -1 -> NaN
    for i, u in enumerate(uniques):
        u = str(u)
        if u not in rev:
            rev[u], labels[nxt] = nxt, u
            nxt += 1
        remap[i] = rev[u]
    return remap[codes], labels


def content_fingerprint(path: str, size: int, block: int = 65536, blocks: int = 16) -> str:
    """F34: a fingerprint of the file's bytes - the first and last MB and 16 blocks in between
    (a few MB read, whatever the size). With size and mtime it tells a re-saved file of the same
    size and time stamp (a copy over it, a coarse file-system clock) from the one cached / read."""
    h = hashlib.sha1(str(size).encode())
    try:
        with open(path, "rb") as f:
            h.update(f.read(min(size, 1 << 20)))
            if size > 2 << 20:
                for k in range(1, blocks + 1):
                    f.seek(size * k // (blocks + 1))
                    h.update(f.read(block))
                f.seek(max(0, size - (1 << 20)))
                h.update(f.read(1 << 20))
    except OSError:
        return ""
    return h.hexdigest()
