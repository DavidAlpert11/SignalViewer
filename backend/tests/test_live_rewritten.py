"""Live mode with a file rewritten as a whole (MAT): it used to be read only after two polls saw
the same size and date - a file saved every second was never shown until the writing stopped."""
import os
import sys
import time

import numpy as np
from scipy.io import savemat

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import store as store_mod  # noqa: E402
from app.store import store  # noqa: E402


def _save(path, n):
    savemat(path, {"time": np.arange(n) * 0.01, "Speed": np.arange(n, dtype=float)})


def test_a_mat_saved_again_and_again_is_followed(tmp_path):
    p = str(tmp_path / "grow.mat")
    _save(p, 100)
    lr = store.open_file(p)
    rid = lr.id
    try:
        _save(p, 300)                                          # saved just now: still being written?
        assert store.poll_appends() == [] and rid in store.writing
        assert store.runs[rid].last_change > 0                 # but live mode is not idle
        store.runs[rid].pending_since = time.time() - store_mod.SETTLE_MAX - 0.1   # it keeps changing...
        _save(p, 500)
        assert store.poll_appends() == [rid]                   # ...read anyway, not stuck
        assert len(store.runs[rid].run.time) == 500
        _save(p, 700)
        old = time.time() - 5
        os.utime(p, (old, old))                                # quiet for a while: read at once
        assert store.poll_appends() == [rid] and len(store.runs[rid].run.time) == 700
        assert store.poll_appends() == []                      # unchanged: nothing to do
    finally:
        store.remove(rid)


def test_one_poll_at_a_time():
    store._poll_lock.acquire()
    try:
        assert store.poll_appends() == []                      # another poll is running: skip
    finally:
        store._poll_lock.release()
