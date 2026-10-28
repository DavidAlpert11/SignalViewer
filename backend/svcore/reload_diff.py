"""What a refresh changed (F5, Refresh all, the ↻ of a file).

A refresh used to say only "2 files refreshed": when the new data differed from the old in a few
samples, the user could not tell whether the file had really been read again. Before a file is read
again, each signal's values (and its time) get a short fingerprint; afterwards the same is done on the
new data and the two are compared, so the app can say which signals changed, which are new or gone,
and how many samples there are now.

Values of a big log that were never read (lazy signals) are not read just for this: they are counted
as not compared.
"""
import hashlib
from typing import Dict, Iterable, List, Optional

import numpy as np

MAX_NAMES = 200            # names listed per kind; the counts are always whole


def _digest(*arrays: np.ndarray, extra: str = "") -> str:
    h = hashlib.blake2b(digest_size=12)
    for a in arrays:
        a = np.ascontiguousarray(a)
        h.update(str(a.dtype).encode())
        h.update(str(a.shape).encode())
        h.update(a.tobytes())
    h.update(extra.encode())
    return h.hexdigest()


def fingerprints(run, only: Optional[Iterable[str]] = None) -> Dict[str, str]:
    """{signal name: fingerprint of its values and time}. Without `only`, signals whose values are
    not in memory (a big log's, never used) are left out; with `only`, those names are read."""
    names = list(run.signals) if only is None else [n for n in only if n in run.signals]
    shared: Optional[str] = None
    out: Dict[str, str] = {}
    for n in names:
        sg = run.signals[n]
        if only is None and not getattr(sg, "loaded", True):
            continue
        if sg.time is not None:
            tkey = _digest(np.asarray(sg.time))
        else:
            if shared is None:
                shared = _digest(np.asarray(run.time))
            tkey = shared
        labels = repr(sorted(sg.labels.items())) if sg.labels else ""
        out[n] = _digest(np.asarray(sg.data), extra=tkey + labels)
    return out


def compare(before: Dict[str, str], after: Dict[str, str], names_before: List[str], names_after: List[str],
            samples_before: int, samples_after: int) -> dict:
    """The summary sent to the UI. `same`: nothing that was compared differs and no signal came or went."""
    nb, na = set(names_before), set(names_after)
    changed = [n for n in names_after if n in before and n in after and before[n] != after[n]]
    added = [n for n in names_after if n not in nb]
    removed = [n for n in names_before if n not in na]
    compared = sum(1 for n in names_after if n in before and n in after)
    return {
        "same": not changed and not added and not removed and samples_before == samples_after,
        "changed": changed[:MAX_NAMES], "nChanged": len(changed),
        "added": added[:MAX_NAMES], "nAdded": len(added),
        "removed": removed[:MAX_NAMES], "nRemoved": len(removed),
        "notCompared": len([n for n in names_after if n in nb]) - compared,
        "samplesBefore": int(samples_before), "samplesAfter": int(samples_after),
    }
