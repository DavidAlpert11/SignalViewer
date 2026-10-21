"""A5: flight logs from real vehicles, not only the ones our own tools write.

Three parts:
  * a regression test that always runs: telemetry with a real radio's delay (0-4 s, from ArduPilot's
    vtol.tlog) and a reboot, read at once and live - the .tlog reader moved samples by 1-3 s before A5;
  * public logs (PX4's pyulog tests, ArduPilot's pymavlink and UAV Log Viewer), pinned to a commit
    and a SHA-256, checked against their projects' own readers (pymavlink, pyulog). Downloaded once
    by `python tools/fetch_real_logs.py` (or SV_DOWNLOAD_LOGS=1); skipped when not there;
  * your own logs: SV_REAL_LOGS=<folder> checks every log in it for the invariants below.
"""
import contextlib
import hashlib
import io
import os
import struct
import sys
import urllib.request
from collections import defaultdict

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PUBLIC_LOGS = {
    # name: (url pinned to a commit, sha256, licence of the source project)
    "sample.ulg": ("https://raw.githubusercontent.com/PX4/pyulog/46732a7130d6eafba070bf40c9df68f2f1a25410/test/sample.ulg",
                   "81952e6059bc095717e7911c010e07f85749d6b04d332a5ffc51575a3fd0a558", "BSD-3-Clause"),
    "sample_log_small.ulg": ("https://raw.githubusercontent.com/PX4/pyulog/46732a7130d6eafba070bf40c9df68f2f1a25410/test/sample_log_small.ulg",
                             "68d1020f688109f027dba08d2950247cc0ae34aaefdcf37e4a7d60838f3e1aa3", "BSD-3-Clause"),
    "sample_px4_events.ulg": ("https://raw.githubusercontent.com/PX4/pyulog/46732a7130d6eafba070bf40c9df68f2f1a25410/test/sample_px4_events.ulg",
                              "4b43a23a7b7f649004facba5c7835d800bbc8cc13e71cbc96678d971451e3d7e", "BSD-3-Clause"),
    "test.BIN": ("https://raw.githubusercontent.com/ArduPilot/pymavlink/bd0a1b29d5b8b54b7d66abfe9ac043c528ac490f/tests/test.BIN",
                 "a51f040b2ad7f55185c1da5705f226f51469b86562c4ff76d05c99e0e52c2bf4", "LGPL-3.0"),
    "flight.tlog": ("https://raw.githubusercontent.com/ArduPilot/pymavlink/bd0a1b29d5b8b54b7d66abfe9ac043c528ac490f/generator/swift/Tests/MAVLinkTests/Testdata/flight.tlog",
                    "16c79fedb900a61e9f67bca6133dd49a40a66f6b431e75138c8d9023c9a31523", "LGPL-3.0"),
    "vtol.tlog": ("https://raw.githubusercontent.com/ArduPilot/UAVLogViewer/01f9d510b7df31687819a6c87415161041d73ae6/src/assets/vtol.tlog",
                  "18c84c91e28115418c46cd35200ecc7197015a0817049bab6093ab38acd6242c", "GPL-3.0"),
}
LOG_EXT = (".bin", ".tlog", ".ulg", ".mcap", ".log", ".csv", ".mat", ".h5", ".hdf5", ".parquet")


def cache_dir() -> str:
    """Outside the repository and outside the tests' temporary home (conftest moves HOME)."""
    home = os.environ.get("SV_TEST_REAL_HOME") or os.path.expanduser("~")
    return os.environ.get("SV_REAL_LOGS_CACHE") or os.path.join(home, ".cache", "signalviewer-test-logs")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fetch(name: str, download: bool = False) -> str:
    """The cached public log (checked against its SHA-256), downloading it when asked."""
    url, sha, _ = PUBLIC_LOGS[name]
    path = os.path.join(cache_dir(), name)
    if not os.path.exists(path):
        if not (download or os.environ.get("SV_DOWNLOAD_LOGS") == "1"):
            pytest.skip(f"{name}: not downloaded - python tools/fetch_real_logs.py (or SV_DOWNLOAD_LOGS=1)")
        os.makedirs(cache_dir(), exist_ok=True)
        tmp = path + ".part"
        urllib.request.urlretrieve(url, tmp)
        os.replace(tmp, path)
    got = _sha256(path)
    assert got == sha, f"{name}: SHA-256 {got} is not the pinned {sha} - delete it and download again"
    return path


def _load(path):
    import signalviewer as sv
    with contextlib.redirect_stdout(io.StringIO()):
        return sv.load(path)


def check_invariants(path: str) -> None:
    """What every log must give, whatever wrote it: it opens; every signal has as many times as values,
    finite and never going back; the flight-log health check (when it applies) runs."""
    rec = _load(path)
    assert rec.signals, f"{path}: no signals"
    for n in rec.signals:
        t, y = rec._store.signal(f"{rec._id}/{n}")
        t = np.asarray(t, dtype=np.float64)
        assert len(t) == len(y), f"{n}: {len(t)} times, {len(y)} values"
        assert np.all(np.isfinite(t)), f"{n}: time not finite"
        assert not np.any(np.diff(t) < 0), f"{n}: time goes back"
    from svcore.health import health
    health(rec._store.get(rec._id).run)


# --------------------------------------------------------------- always: a radio's delay and a reboot

def _write_tlog(path, rows):
    os.environ.setdefault("MAVLINK20", "1")
    from pymavlink.dialects.v20 import ardupilotmega as mav
    m = mav.MAVLink(None, srcSystem=1, srcComponent=1)
    T0 = 1_760_000_000_000_000
    with open(path, "wb") as f:
        for t_recv, boot_ms, roll in rows:
            if boot_ms % 1000 == 0:
                f.write(struct.pack(">Q", int(T0 + t_recv * 1e6)) + mav.MAVLink_heartbeat_message(2, 3, 81, 5, 4, 3).pack(m))
            msg = mav.MAVLink_attitude_message(int(boot_ms), float(roll), 0.0, 0.0, 0.0, 0.0, 0.0)
            f.write(struct.pack(">Q", int(T0 + t_recv * 1e6)) + msg.pack(m))


def _radio_rows():
    """ATTITUDE at 10 Hz for 120 s, a reboot after 60 s (the boot clock starts again from 2 s), and a
    radio delay that wanders 0.1 - 4 s (never faster than real time, as received packets cannot be)."""
    rows, k = [], 0
    for boot, (b0, r0) in enumerate(((50.0, 0.0), (2.0, 70.0))):
        for i in range(600):
            tb = b0 + i * 0.1
            lat = 0.1 + 1.95 * (1 - np.cos(2 * np.pi * i / 300))      # 0.1 .. 4 s, slow
            rows.append((r0 + i * 0.1 + lat, int(round(tb * 1000)), float(k)))   # roll = sample number
            k += 1
    return rows


def test_radio_delay_does_not_move_samples(tmp_path):
    p = tmp_path / "radio.tlog"
    _write_tlog(p, _radio_rows())
    rec = _load(str(p))
    t, y = rec.signal("ATTITUDE.roll")
    assert np.array_equal(y, np.arange(1200.0))                      # every sample, in order
    st = rec._store.get(rec._id).run._tlog
    assert len(st.boots) == 2                                         # one boot each side of the reboot
    for part in (slice(0, 600), slice(600, 1200)):                    # the boot clock's exact 0.1 s spacing
        assert np.allclose(np.diff(t[part]), 0.1, atol=1e-6)


def test_radio_delay_live(tmp_path):
    """The same file growing, read in four pieces: every sample in order with the boot clock's exact
    spacing. (Live, a boot's offset is learned from the data seen so far and then kept - moving
    samples already on screen would be worse - so it may differ from a full read by a constant
    within the radio delay.)"""
    from svcore.tlog_loader import append_tlog, load_tlog
    rows = _radio_rows()
    whole = tmp_path / "whole.tlog"
    _write_tlog(whole, rows)
    data = whole.read_bytes()
    p = tmp_path / "live.tlog"
    cut = [int(len(data) * f) for f in (0.3, 0.55, 0.8, 1.0)]
    p.write_bytes(data[:cut[0]])
    run, _ = load_tlog(str(p), "live.tlog")
    for c in cut[1:]:
        p.write_bytes(data[:c])
        append_tlog(run)
    full, _ = load_tlog(str(whole), "whole.tlog")
    a, b = run.signals["ATTITUDE.roll [rad]"], full.signals["ATTITUDE.roll [rad]"]
    assert np.array_equal(a.data, b.data)
    for part in (slice(0, 600), slice(600, 1200)):
        d = a.time[part] - b.time[part]
        assert np.ptp(d) < 1e-6 and abs(d[0]) < 4.0


# ---------------------------------------------------------------------------- public logs

@pytest.mark.parametrize("name", sorted(PUBLIC_LOGS))
def test_public_log_invariants(name):
    check_invariants(fetch(name))


def test_bin_matches_pymavlink():
    """Our own DataFlash reader against pymavlink's DFReader: every numeric field, every message."""
    from pymavlink import DFReader
    path = fetch("test.BIN")
    rec = _load(path)
    base = defaultdict(list)
    for n in rec.signals:
        base[n.split(" [")[0]].append(n)
    ref = defaultdict(list)
    d = DFReader.DFReader_binary(path, zero_time_base=False)
    while True:
        m = d.recv_msg()
        if m is None:
            break
        if m.get_type() in ("FMT", "FMTU", "UNIT", "MULT", "PARM", "MSG"):
            continue
        for fld in m.get_fieldnames():
            v = getattr(m, fld, None)
            if isinstance(v, (int, float)) and fld != "TimeUS":
                ref[f"{m.get_type()}.{fld}"].append(float(v))
    checked = 0
    for key, vals in ref.items():
        names = base.get(key)
        if not names or len(names) != 1:
            continue
        _, y = rec.signal(names[0])
        assert len(y) == len(vals) and np.allclose(y, vals, rtol=1e-6, atol=1e-6, equal_nan=True), key
        checked += 1
    assert checked > 300


@pytest.mark.parametrize("name", ["vtol.tlog", "flight.tlog"])
def test_tlog_matches_pymavlink_on_the_boot_clock(name):
    """Every ATTITUDE sample, in the order of the autopilot's own clock (one offset per boot), as
    pymavlink reads them. Before A5: vtol.tlog had samples moved by up to 3 s and out of order."""
    from pymavlink import mavutil
    path = fetch(name)
    rec = _load(path)
    t, y = rec.signal("ATTITUDE.roll")
    m = mavutil.mavlink_connection(path, dialect="ardupilotmega")
    rows, ts0 = [], None
    while True:
        msg = m.recv_match()
        if msg is None:
            break
        ts0 = msg._timestamp if ts0 is None else ts0
        if msg.get_type() == "ATTITUDE" and msg.get_srcSystem() == 1:
            rows.append((msg._timestamp - ts0, msg.time_boot_ms * 1e-3, msg.roll))
    tr, tb, roll = np.array(rows).T
    boot = np.zeros(len(tb), int)
    top = tb[0]
    for i in range(1, len(tb)):                    # a reboot: the boot clock back by > 10 s, and staying back
        if tb[i] < top - 10 and np.all(tb[i:i + 4] < top - 10):
            boot[i:] += 1
            top = tb[i]
        top = max(top, tb[i])
    order = np.lexsort((tb, boot))
    assert np.allclose(y, roll[order])                                  # the same samples, in clock order
    for k in np.unique(boot):                                           # one constant offset per boot
        sel = boot[order] == k
        assert np.ptp(t[sel] - tb[order][sel]) < 1e-6


def test_ulog_matches_pyulog():
    """Every numeric field of every topic, as pyulog reads it (samples with a zero time stamp - an
    old PX4 fault - are left out by design and said in the load report)."""
    from pyulog import ULog
    for name in ("sample.ulg", "sample_log_small.ulg", "sample_px4_events.ulg"):
        path = fetch(name)
        rec = _load(path)
        names = set(rec.signals)
        base = defaultdict(list)
        for n in names:
            base[n.split(" [")[0]].append(n)
        u = ULog(path)
        multi = {d.name for d in u.data_list if d.multi_id > 0}
        checked = 0
        for d in u.data_list:
            ts = d.data["timestamp"]
            keep = ts != 0
            if not keep.any():
                continue
            for fld, v in d.data.items():
                if fld == "timestamp" or v.dtype.kind not in "iuf":
                    continue
                key = f"{d.name}[{d.multi_id}].{fld}" if d.name in multi else f"{d.name}.{fld}"
                if len(base.get(key, [])) != 1:
                    continue
                t, y = rec.signal(base[key][0])
                assert np.allclose(t, ts[keep] * 1e-6) and np.allclose(y, v[keep].astype(float), equal_nan=True), key
                checked += 1
        assert checked > 200, name


# ------------------------------------------------------------------------------- your logs

def _user_logs():
    root = os.environ.get("SV_REAL_LOGS")
    if not root:
        return []
    return sorted(os.path.join(dp, f) for dp, _, fs in os.walk(root) for f in fs if f.lower().endswith(LOG_EXT))


@pytest.mark.skipif(not os.environ.get("SV_REAL_LOGS"), reason="SV_REAL_LOGS=<folder of your logs> to check them")
@pytest.mark.parametrize("path", _user_logs() or ["(none)"])
def test_your_log(path):
    if path == "(none)":
        pytest.skip("no log files in SV_REAL_LOGS")
    check_invariants(path)
