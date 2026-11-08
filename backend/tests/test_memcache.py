"""P2: one memory cache for everything that can be computed again (changed signals, derived signals,
spectra, block summaries, statistics) - bounded in bytes, least recently used first, locked."""
import gc
import os
import sys
import threading

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from svcore.memcache import CACHE, ByteLRU  # noqa: E402
from svcore.models import Run, Signal  # noqa: E402

client = TestClient(app)


@pytest.fixture()
def small_cache():
    old = CACHE.limit
    CACHE.clear()
    CACHE.set_limit(4 << 20)               # 4 MB: a few 1 MB results
    yield CACHE
    CACHE.set_limit(old)
    CACHE.clear()


def _run(name, n=125_000, k=8):
    t = np.arange(n) / 1000.0
    r = Run(file_path=name, csv_display_name=name, time=t)
    for i in range(k):
        r.signals[f"s{i}"] = Signal(name=f"s{i}", data=np.sin(t + i), time=t)
    r.compute_metadata()
    return store.add_pushed(name, r)[0]


def test_bytes_lru_and_owners():
    c = ByteLRU(3000)
    a, b, d = (np.zeros(125) for _ in range(3))               # 1000 bytes each
    c.put("a", a, "x"); c.put("b", b, "x")
    assert c.get("a") is a                                      # a is now the most recent
    c.put("d", d, "x"); c.put("e", np.zeros(125), "x")          # 4000 > 3000: b (least recent) goes
    assert c.get("b") is None and c.get("a") is a and c.total <= 3000
    assert c.put("big", np.zeros(1000), "x") is not None and c.get("big") is None   # bigger than all: not kept
    owner = np.ones(10)
    c.put("sum", 10.0, "y", owners=(owner,))
    assert c.get("sum") == 10.0
    del owner; gc.collect()
    assert c.get("sum") is None                                 # its array is gone: so is the entry
    info = c.info()
    assert info["bytes"] == c.total and set(info["kinds"]) == {"x"}


def test_transformed_signals_are_bounded_in_bytes(small_cache):
    lr = _run("p2_transforms")
    try:
        ids = [f"{lr.id}/s{i}" for i in range(8)]
        store.set_transforms({sid: {"scale": 2.0} for sid in ids})
        for sid in ids:                                         # 8 x 2 MB (time + values) > 4 MB
            t, y = store.signal(sid)
            assert np.allclose(y, 2 * np.sin(t + int(sid[-1])))
        info = small_cache.info()
        assert info["bytes"] <= 4 << 20 and info["kinds"]["transform"]["entries"] >= 1
        t, y = store.signal(ids[0])                             # pushed out: computed again, same values
        assert np.allclose(y, 2 * np.sin(t))
    finally:
        store.remove(lr.id)


def test_derived_signals_are_bounded_in_bytes(small_cache):
    lr = _run("p2_derived")
    names = []
    try:
        for i in range(8):
            names.append(store.add_derived("negate", [f"{lr.id}/s{i}"], {}, f"p2neg{i}").name)
        for nm in names:
            store.signal(f"derived/{nm}")
        info = small_cache.info()
        assert info["bytes"] <= 4 << 20 and info["kinds"]["derived"]["entries"] >= 1
        t, y = store.signal(f"derived/{names[0]}")
        assert np.allclose(y, -np.sin(t))
    finally:
        for nm in names:
            store.remove_derived(nm)
        store.remove(lr.id)


def test_two_requests_at_once_never_see_a_signal_missing():
    """Store._tcache (an OrderedDict without the lock): move_to_end on a key another thread had just
    pushed out raised KeyError - read by the routes as "signal missing" (33 errors in 8 x 300 reads
    on the code before P2)."""
    lr = _run("p2_race", n=2000, k=64)
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)                                 # switch threads as often as possible
    errors = []
    try:
        store.set_transforms({f"{lr.id}/s{i}": {"scale": 2.0} for i in range(64)})

        def work(k):
            for _ in range(100):
                for i in range(64):
                    try:
                        store.signal(f"{lr.id}/s{(i * 7 + k) % 64}")
                    except Exception as e:                      # noqa: BLE001 - any error is the bug
                        errors.append(repr(e))
        ths = [threading.Thread(target=work, args=(k,)) for k in range(8)]
        [x.start() for x in ths]
        [x.join() for x in ths]
    finally:
        sys.setswitchinterval(old)
        store.remove(lr.id)
    assert errors == []


def test_storage_dialog_shows_the_memory_cache():
    r = client.get("/api/storage").json()
    assert r["memory"]["limit"] == CACHE.limit and "bytes" in r["memory"] and "kinds" in r["memory"]
    r = client.post("/api/storage/clear", json={"what": ["memory"]}).json()
    assert r["memory"]["bytes"] == 0 and "freed" in r["result"]["memory"]
