"""Big files: the lazy / compact / parallel .bin reader, its index cache, the CSV cache limits, the
Storage section's API, the browser watchdog and the bounded caches:  python -m pytest backend/tests"""
import os
import sys
import time

import numpy as np
import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
from fastapi.testclient import TestClient  # noqa: E402

import make_test_bin as mk  # noqa: E402
from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from svcore import bin_loader as B  # noqa: E402
from svcore import csv_loader as C  # noqa: E402
from svcore.models import LAZY_BUDGET, LazySignal  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    yield
    for rid in list(store.order):
        store.remove(rid)


@pytest.fixture
def big_mode(monkeypatch, tmp_path):
    """Every path a 1-2 GB log takes, on a small file: lazy values, float32, memory map, small
    blocks, several threads, and a cache folder of its own."""
    monkeypatch.setattr(B, "LAZY_MIN", 0)
    monkeypatch.setattr(B, "COMPACT_MIN", 0)
    monkeypatch.setattr(B, "_MMAP_MIN", 0)
    monkeypatch.setattr(B, "_BLOCK", 1 << 14)
    monkeypatch.setattr(B, "_WORKERS", 4)
    monkeypatch.setattr(C, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(B, "INDEX_QUIET_S", 0.0)
    return tmp_path


def write_bin(path, t0=1.0, t1=11.0, corrupt=False):
    mk.FMTS.clear()
    data = mk.header() + mk.body(t0, (t0 + t1) / 2, 100)
    if corrupt:
        data += b"\xa3\x95\x82garbage\xa3\x95" + bytes(range(40))
    data += mk.body((t0 + t1) / 2, t1, 100)
    with open(path, "wb") as f:
        f.write(data)
    old = time.time() - 3600                      # "not being written": the index may be kept
    os.utime(path, (old, old))


def same(a, b):
    assert set(a.signals) == set(b.signals)
    for n, s in a.signals.items():
        t = b.signals[n]
        assert np.array_equal(s.time, t.time), n
        assert np.array_equal(np.asarray(s.data, np.float64), np.asarray(t.data, np.float64), equal_nan=True), n
        assert s.labels == t.labels, n


def eager(path):
    saved = (B.LAZY_MIN, B.COMPACT_MIN)
    B.LAZY_MIN = B.COMPACT_MIN = 1 << 40
    try:
        return B.load_bin(path, "x")
    finally:
        B.LAZY_MIN, B.COMPACT_MIN = saved


def wait_for_index(cache_dir, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        if os.path.isdir(cache_dir) and any(d.startswith("bin-") and not d.endswith(".tmp") for d in os.listdir(cache_dir)):
            return
        time.sleep(0.05)
    raise AssertionError("the log index was not written")


# ---------------------------------------------------------------------------- the .bin reader
def test_big_mode_reads_exactly_what_the_normal_read_does(big_mode):
    p = str(big_mode / "a.bin")
    write_bin(p, corrupt=True)
    full, rep_full = eager(p)
    lazy, rep_lazy = B.load_bin(p, "x")
    assert any(isinstance(s, LazySignal) for s in lazy.signals.values())
    assert any(s.data.dtype == np.float32 for s in lazy.signals.values())       # exact float32 fields
    assert rep_lazy["corruptBytes"] == rep_full["corruptBytes"] > 0
    same(full, lazy)
    assert full._flightlog.events == lazy._flightlog.events


def test_lazy_values_are_not_read_until_used(big_mode):
    p = str(big_mode / "b.bin")
    write_bin(p)
    run, _ = B.load_bin(p, "x")
    s = run.signals["IMU[0].AccZ [m/s/s]"]
    assert isinstance(s, LazySignal) and not s.loaded
    info = client.post("/api/files/open", json={"paths": [p]}).json()["opened"][0]
    assert not run.signals["IMU[0].AccZ [m/s/s]"].loaded                     # describing reads nothing
    acc = next(x for x in info["signals"] if x["name"] == "IMU[0].AccZ [m/s/s]")
    assert acc["discrete"] is None and acc["n"] == len(s.time)
    assert len(s.data) == len(s.time) and s.loaded


def test_lazy_live_append_equals_a_full_read(big_mode):
    p = str(big_mode / "live.bin")
    write_bin(p, 1.0, 5.0)
    run, _ = B.load_bin(p, "x")
    _ = run.signals["IMU[0].AccZ [m/s/s]"].data             # one read already, one still lazy
    chunk = mk.body(5.0, 7.0, 100)
    with open(p, "ab") as f:
        f.write(chunk[:-5])
    assert B.append_new_messages(run) > 0
    with open(p, "ab") as f:
        f.write(chunk[-5:])
    B.append_new_messages(run)
    same(eager(p)[0], run)


def test_values_dropped_by_the_memory_budget_are_read_again(big_mode, monkeypatch):
    p = str(big_mode / "c.bin")
    write_bin(p)
    full, _ = eager(p)
    run, _ = B.load_bin(p, "x")
    monkeypatch.setattr(LAZY_BUDGET, "limit", 1)             # keep (almost) nothing
    names = [n for n, s in run.signals.items() if isinstance(s, LazySignal)]
    for n in names:
        _ = run.signals[n].data
    assert sum(run.signals[n].loaded for n in names) <= 1
    same(full, run)                                          # every value read again, identical


def test_a_rewritten_file_is_never_read_as_the_old_one(big_mode):
    p = str(big_mode / "d.bin")
    write_bin(p)
    run, _ = B.load_bin(p, "x")
    write_bin(p, 50.0, 60.0)                                 # re-saved: other bytes
    with pytest.raises(ValueError, match="refresh"):
        _ = run.signals["IMU[0].AccZ [m/s/s]"].data


# ---------------------------------------------------------------------------- the index cache
def test_a_big_log_opens_again_from_its_index(big_mode):
    p = str(big_mode / "e.bin")
    write_bin(p, corrupt=True)
    first, rep1 = B.load_bin(p, "x")
    assert not rep1.get("fromCache")
    wait_for_index(C.CACHE_DIR)
    again, rep2 = B.load_bin(p, "x")
    assert rep2.get("fromCache") and rep2["corruptBytes"] == rep1["corruptBytes"]
    same(first, again)
    assert again._flightlog.log_info()["params"] == first._flightlog.log_info()["params"]
    # live mode continues from an index too
    with open(p, "ab") as f:
        f.write(mk.body(11.0, 12.0, 100))
    assert B.append_new_messages(again) > 0
    same(eager(p)[0], again)


def test_a_changed_log_does_not_use_its_old_index(big_mode):
    p = str(big_mode / "f.bin")
    write_bin(p)
    B.load_bin(p, "x")
    wait_for_index(C.CACHE_DIR)
    write_bin(p, 1.0, 13.0)
    run, rep = B.load_bin(p, "x")
    assert not rep.get("fromCache")
    same(eager(p)[0], run)


def test_a_log_being_written_gets_no_index(big_mode, monkeypatch):
    monkeypatch.setattr(B, "INDEX_QUIET_S", 3600.0)
    p = str(big_mode / "g.bin")
    write_bin(p)
    os.utime(p)                                              # just written
    B.load_bin(p, "x")
    time.sleep(0.3)
    assert not os.path.isdir(C.CACHE_DIR) or not os.listdir(C.CACHE_DIR)


# ---------------------------------------------------------------------------- CSV cache limits
def _entry(name, source, size, age_days):
    d = os.path.join(C.CACHE_DIR, name)
    os.makedirs(d)
    with open(os.path.join(d, "meta.json"), "w") as f:
        f.write('{"source": "%s"}' % source)
    with open(os.path.join(d, "signals.npy"), "wb") as f:
        f.write(b"\0" * size)
    old = time.time() - age_days * 86400
    os.utime(os.path.join(d, "meta.json"), (old, old))
    return d


def test_cache_keeps_one_copy_per_file_and_its_limits(big_mode, monkeypatch):
    os.makedirs(C.CACHE_DIR)
    a1 = _entry("a1", "/x/a.csv", 1000, 1)
    a2 = _entry("a2", "/x/a.csv", 1000, 0)
    old = _entry("old", "/x/b.csv", 1000, 400)
    busy = _entry("busy", "/x/c.csv", 1000, 400)
    monkeypatch.setattr(C, "CACHE_IN_USE", lambda: {busy})
    C.prune_cache(keep=a2, source="/x/a.csv")
    assert not os.path.exists(a1) and os.path.exists(a2)        # the older copy of the same file
    assert not os.path.exists(old)                               # unused for too long
    assert os.path.exists(busy)                                  # an open file reads it
    b1, b2 = _entry("b1", "/x/d.csv", 5000, 2), _entry("b2", "/x/e.csv", 5000, 1)
    monkeypatch.setattr(C, "CACHE_MAX_BYTES", 8000)
    C.prune_cache()
    assert not os.path.exists(b1) and os.path.exists(b2)         # least recently used first


def test_storage_api_reports_and_clears(big_mode, monkeypatch):
    from app import storage
    os.makedirs(C.CACHE_DIR)
    _entry("x1", "/x/a.csv", 4096, 0)
    info = client.get("/api/storage").json()
    assert info["cache"]["bytes"] >= 4096 and {"uploads", "tiles"} <= set(info)
    monkeypatch.setattr(storage, "cache_dirs_in_use", lambda: set())
    r = client.post("/api/storage/clear", json={"what": ["cache", "nonsense"]}).json()
    assert r["result"]["cache"]["freed"] >= 4096 and r["cache"]["bytes"] == 0 and "nonsense" not in r["result"]


def test_an_open_files_cache_entry_is_in_use(big_mode):
    from app import storage
    p = str(big_mode / "h.bin")
    write_bin(p)
    B.load_bin(p, "x")
    wait_for_index(C.CACHE_DIR)
    lr = store.open_file(p)                                      # opened from the index
    assert lr.load_report.get("fromCache")
    used = storage.cache_dirs_in_use()
    assert len(used) == 1 and os.path.basename(next(iter(used))).startswith("bin-")


# ---------------------------------------------------------------------------- watchdog, caches
def test_watchdog_waits_for_throttled_tabs_and_running_jobs(monkeypatch):
    from app.jobs import jobs
    from app.routes import system as S
    monkeypatch.setitem(S.WATCHDOG, "enabled", True)
    monkeypatch.setitem(S.WATCHDOG, "bye", None)
    monkeypatch.setitem(S.WATCHDOG, "last", time.time() - 90)     # a background tab: a ping a minute
    assert not S.idle_too_long(30)
    monkeypatch.setitem(S.WATCHDOG, "last", time.time() - S.IDLE_LIMIT - 5)
    assert S.idle_too_long(30)
    job = jobs.start("test", "t", lambda j: time.sleep(0.5))
    assert not S.idle_too_long(30)                                 # a load still running
    while job.state == "running":
        time.sleep(0.05)
    monkeypatch.setitem(S.WATCHDOG, "last", time.time() - S.BYE_LIMIT - 5)
    monkeypatch.setitem(S.WATCHDOG, "bye", time.time() - S.BYE_LIMIT - 4)
    assert S.idle_too_long(30)                                     # the page said goodbye
    client.post("/api/ping")
    assert S.WATCHDOG["bye"] is None and not S.idle_too_long(30)


def test_discrete_cache_does_not_grow_in_live_mode(big_mode):
    p = str(big_mode / "i.bin")
    write_bin(p, 1.0, 5.0)
    B.LAZY_MIN = 1 << 40                                           # eager: every signal described
    lr = store.open_file(p)
    store.describe(lr)
    n0 = len(store._discrete)
    for k in range(3):
        with open(p, "ab") as f:
            f.write(mk.body(5.0 + k, 6.0 + k, 100))
        assert B.append_new_messages(lr.run) > 0
        store.describe(lr)
    assert len(store._discrete) == n0


def test_fft_cache_is_bounded_by_size(monkeypatch):
    from svcore import analysis as A
    monkeypatch.setattr(A, "_FFT_CACHE_BYTES", 3 << 20)
    A._fft_cache.clear()
    t = np.arange(400_000) / 1000.0
    y = np.sin(t)
    for v in range(6):                                             # live mode: a new version each time
        A.fft_for("r/x", v, t, y, "hann", None, None)
    assert len([k for k in A._fft_cache if k[0] == "r/x"]) == 1
    for s in range(6):
        A.fft_for(f"r/y{s}", 0, t, y, "hann", None, None)
    assert sum(v[0].nbytes + v[1].nbytes for v in A._fft_cache.values()) <= (3 << 20) or len(A._fft_cache) == 1
