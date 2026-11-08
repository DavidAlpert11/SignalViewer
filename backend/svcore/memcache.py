"""P2: one memory cache for results that can always be computed again - changed signals (transforms),
derived signals, spectra (FFT), the plot's block summaries and statistics.

Before, each kept its own: transforms by count (32 entries: 32 changed 20M-sample signals are 5 GB) and
without the store's lock (two requests at once could make a signal look "missing"), derived signals
without any bound, spectra by their own 256 MB. Now there is one budget in BYTES (SV_MEMCACHE_MB,
default 1024 MB), the least recently used entries go first, every operation holds one lock, and the
total is shown in Settings > Storage.

An entry can name OWNERS - the arrays it was computed from (a summary of a signal, its statistics):
when an owner is freed (a file closed or read again), its entries go at once instead of waiting to be
pushed out, and a new array that happens to get the freed one's address can never match them.
Values handed out stay alive as long as the caller holds them; the cache only lets go of its copy.
"""
import os
import threading
import weakref
from collections import OrderedDict
from typing import Any, Callable, Dict, Hashable, Iterable, Optional, Tuple

import numpy as np

DEFAULT_MB = float(os.environ.get("SV_MEMCACHE_MB", "1024"))


def nbytes_of(value: Any) -> int:
    """Bytes held by a value: arrays (also inside tuples, lists and dicts), else a small constant."""
    if isinstance(value, np.ndarray):
        return int(value.nbytes)
    if isinstance(value, (tuple, list)):
        return sum(nbytes_of(v) for v in value) + 64
    if isinstance(value, dict):
        return sum(nbytes_of(v) for v in value.values()) + 64 * (1 + len(value))
    return 64


def own_bytes(arrays: Iterable[np.ndarray], shared: Iterable[np.ndarray] = ()) -> int:
    """Bytes the cache really holds for these arrays: not those that ARE (or are views of) arrays kept
    anyway - a scaled signal keeps its file's time vector, a derived one often its source's."""
    keep = [s for s in shared if isinstance(s, np.ndarray)]

    def root(a: np.ndarray) -> np.ndarray:
        while isinstance(a.base, np.ndarray):
            a = a.base
        return a
    roots = {id(root(s)) for s in keep}
    return sum(int(a.nbytes) for a in arrays if isinstance(a, np.ndarray) and id(root(a)) not in roots) + 64


class ByteLRU:
    def __init__(self, limit_bytes: int):
        self.limit = int(limit_bytes)
        self.total = 0
        self._items: "OrderedDict[Hashable, Tuple[Any, int, str, tuple]]" = OrderedDict()
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    # ------------------------------------------------------------------ lookups
    def get(self, key: Hashable, default: Any = None) -> Any:
        with self._lock:
            item = self._items.get(key)
            if item is None or any(r() is None for r in item[3]):
                if item is not None:
                    self._pop(key)
                self.misses += 1
                return default
            self._items.move_to_end(key)
            self.hits += 1
            return item[0]

    def put(self, key: Hashable, value: Any, kind: str, nbytes: Optional[int] = None,
            owners: Iterable[Any] = ()) -> Any:
        """Keep value under key (replacing an older one). A value bigger than the whole budget is not
        kept (it would push everything else out and go next). Returns value."""
        nb = nbytes_of(value) if nbytes is None else int(nbytes)
        refs = []
        for o in owners:
            try:
                refs.append(weakref.ref(o, self._owner_gone(key)))
            except TypeError:               # not weak-referenceable: cannot tell when it goes - not kept
                return value
        with self._lock:
            self._pop(key)
            if nb > self.limit:
                return value
            self._items[key] = (value, nb, kind, tuple(refs))
            self.total += nb
            self._shrink()
        return value

    def get_or_compute(self, key: Hashable, kind: str, compute: Callable[[], Any],
                       owners: Iterable[Any] = ()) -> Any:
        hit = self.get(key)
        if hit is not None:
            return hit
        return self.put(key, compute(), kind, owners=owners)

    # ------------------------------------------------------------------ removal
    def drop(self, pred: Callable[[Any], bool]) -> int:
        """Remove the entries whose key matches (an older version of a signal...). Returns bytes freed."""
        with self._lock:
            keys = [k for k in self._items if pred(k)]
            return sum(self._pop(k) for k in keys)

    def clear(self) -> int:
        with self._lock:
            freed = self.total
            self._items.clear()
            self.total = 0
            return freed

    def set_limit(self, limit_bytes: int) -> None:
        with self._lock:
            self.limit = int(limit_bytes)
            self._shrink()

    def info(self) -> Dict[str, Any]:
        """Total, limit and bytes per kind - for Settings > Storage."""
        with self._lock:
            kinds: Dict[str, Dict[str, int]] = {}
            for _v, nb, kind, _r in self._items.values():
                k = kinds.setdefault(kind, {"bytes": 0, "entries": 0})
                k["bytes"] += nb
                k["entries"] += 1
            return {"bytes": self.total, "limit": self.limit, "entries": len(self._items), "kinds": kinds,
                    "hits": self.hits, "misses": self.misses}

    # ------------------------------------------------------------------ inside
    def _pop(self, key: Hashable) -> int:
        item = self._items.pop(key, None)
        if item is None:
            return 0
        self.total -= item[1]
        return item[1]

    def _shrink(self) -> None:
        while self.total > self.limit and self._items:
            self._pop(next(iter(self._items)))

    def _owner_gone(self, key: Hashable):
        me = weakref.ref(self)

        def cb(_ref: Any) -> None:
            cache = me()
            if cache is None:
                return
            # a callback can run while this thread holds the lock (a freed array during put):
            # the RLock lets it in; another thread waits its turn
            with cache._lock:
                item = cache._items.get(key)
                if item is not None and any(r is _ref for r in item[3]):
                    cache._pop(key)
        return cb


CACHE = ByteLRU(int(DEFAULT_MB * (1 << 20)))
