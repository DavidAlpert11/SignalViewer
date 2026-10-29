"""Q123: the file list shows when the version on screen was saved to the disk, and says when the file
was saved again since (only its date and size are looked at - nothing is read)."""
import os

import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.store import Store, store


def _write(p, k=0.0):
    t = np.arange(100) * 0.01
    p.write_text("Time,Speed\n" + "\n".join(f"{a:.2f},{np.sin(a) + k:.6f}" for a in t) + "\n")


def _later(p, seconds=5):
    st = os.stat(p)
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + seconds * 1_000_000_000))


def test_saved_time_read_time_and_newer_on_disk(tmp_path):
    st = Store()
    p = tmp_path / "a.csv"
    _write(p)
    lr = st.open_file(str(p), {})
    d = st.describe(lr)
    assert abs(d["fileTime"] - os.stat(p).st_mtime) < 1e-3 and d["readAt"] > 0
    assert st.newer_on_disk() == {}

    _write(p, 0.001)                                    # saved again by another program
    _later(p)
    newer = st.newer_on_disk()
    assert list(newer) == [lr.id] and abs(newer[lr.id] - os.stat(p).st_mtime) < 1e-3
    assert abs(st.describe(st.runs[lr.id])["fileTime"] - os.stat(p).st_mtime) > 1     # still the old version

    st.reload_all()                                     # F5: the new version, nothing newer any more
    assert st.newer_on_disk() == {}
    assert abs(st.describe(st.runs[lr.id])["fileTime"] - os.stat(p).st_mtime) < 1e-3


def test_route(tmp_path):
    p = tmp_path / "b.csv"
    _write(p)
    rid = store.open_file(str(p), {}).id
    try:
        c = TestClient(app)
        assert rid not in c.get("/api/runs/newer-on-disk").json()
        _later(p)
        assert rid in c.get("/api/runs/newer-on-disk").json()
    finally:
        store.remove(rid)
