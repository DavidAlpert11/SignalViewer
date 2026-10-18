"""T27: ROS 2 / Foxglove recordings (.mcap) and HDF5 files (.h5 / .hdf5)."""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import LoadError, store  # noqa: E402

client = TestClient(app)
T0 = 1_700_000_000_000_000_000

VEC = """std_msgs/Header header
geometry_msgs/Vector3 vector
================================================================================
MSG: std_msgs/Header
builtin_interfaces/Time stamp
string frame_id
================================================================================
MSG: builtin_interfaces/Time
int32 sec
uint32 nanosec
================================================================================
MSG: geometry_msgs/Vector3
float64 x
float64 y
float64 z"""
STATUS = "bool armed\nuint8 mode\nstring note\nfloat32[] cells\nuint8[] blob"
IMAGE = "uint32 height\nuint32 width\nstring encoding\nuint8[] data"


def write_ros2(path, seconds=2.0, chunk_size=1024 * 1024):
    from mcap_ros2.writer import Writer
    with open(path, "wb") as f:
        w = Writer(f, chunk_size=chunk_size)
        vec = w.register_msgdef("geometry_msgs/msg/Vector3Stamped", VEC)
        st = w.register_msgdef("my_pkg/msg/Status", STATUS)
        img = w.register_msgdef("sensor_msgs/msg/Image", IMAGE)
        for i in range(int(seconds * 100)):                       # 100 Hz
            ns = T0 + i * 10_000_000
            w.write_message("/imu/accel", vec, {"header": {"stamp": {"sec": 50 + i // 100, "nanosec": (i % 100) * 10_000_000},
                                                           "frame_id": "imu"},
                                                "vector": {"x": float(i), "y": 2.0, "z": -9.8}}, log_time=ns, publish_time=ns)
            if i % 10 == 0:                                        # 10 Hz
                w.write_message("/status", st, {"armed": i >= 100, "mode": i // 10, "note": "takeoff" if i >= 100 else "idle",
                                                 "cells": [3.7, 3.8], "blob": bytes(300)}, log_time=ns + 1, publish_time=ns + 1)
                w.write_message("/camera", img, {"height": 2, "width": 2, "encoding": "mono8", "data": bytes(4)},
                                log_time=ns + 2, publish_time=ns + 2)
        w.finish()


def write_json_and_protobuf(path):
    from mcap.writer import Writer
    with open(path, "wb") as f:
        w = Writer(f)
        w.start()
        js = w.register_schema(name="foxglove.Battery", encoding="jsonschema", data=b"{}")
        cj = w.register_channel(topic="/battery", message_encoding="json", schema_id=js)
        pb = w.register_schema(name="my.Proto", encoding="protobuf", data=b"\x00")
        cp = w.register_channel(topic="/proto", message_encoding="protobuf", schema_id=pb)
        for i in range(20):
            w.add_message(channel_id=cj, log_time=T0 + i * 10**8, publish_time=T0 + i * 10**8,
                          data=json.dumps({"voltage": 12.0 - i * 0.1, "state": {"ok": i < 15},
                                           "stamp": {"sec": 1, "nsec": 500_000_000}}).encode())
            w.add_message(channel_id=cp, log_time=T0 + i * 10**8, publish_time=T0 + i * 10**8, data=b"\x08\x01")
        w.finish()


@pytest.fixture(autouse=True)
def _clean():
    yield
    for rid in list(store.order):
        store.remove(rid)


def opened(path):
    r = client.post("/api/files/open", json={"paths": [str(path)]}).json()
    assert r["errors"] == [], r["errors"]
    run = r["opened"][0]
    return run, {s["name"]: s["id"] for s in run["signals"]}


def test_ros2_bag_topics_fields_and_own_rates(tmp_path):
    p = tmp_path / "flight.mcap"
    write_ros2(p)
    run, sig = opened(p)
    assert run["format"] == "mcap"
    t, y = store.signal(sig["imu/accel.vector.x"])
    assert len(t) == 200 and np.allclose(np.diff(t), 0.01) and t[0] == 0 and y[5] == 5   # 100 Hz, from 0 s
    t2, _ = store.signal(sig["status.mode"])
    assert len(t2) == 20 and np.allclose(np.diff(t2), 0.1)                                # 10 Hz: its own time
    _, stamp = store.signal(sig["imu/accel.header.stamp"])
    assert stamp[150] == pytest.approx(51.5)                                              # sec + nanosec, in seconds
    _, armed = store.signal(sig["status.armed"])
    assert set(armed) == {0.0, 1.0}
    assert "status.cells[1]" in sig
    note = next(s for s in run["signals"] if s["name"] == "status.note")
    assert store.is_state(note["id"])                                                    # text -> a state with labels
    skipped = " | ".join(run["report"]["skipped"])
    assert "/camera: sensor_msgs/msg/Image (not a time series)" in skipped                 # never decoded
    assert "/status.blob: 300 values per message" in skipped
    assert not any(n.startswith("camera") for n in sig) and "imu/accel.header.frame_id" not in sig


def test_json_topics_and_unsupported_encodings(tmp_path):
    p = tmp_path / "fox.mcap"
    write_json_and_protobuf(p)
    run, sig = opened(p)
    _, v = store.signal(sig["battery.voltage"])
    assert v[0] == pytest.approx(12.0) and len(v) == 20
    _, ok = store.signal(sig["battery.state.ok"])
    assert ok[0] == 1 and ok[-1] == 0
    _, st = store.signal(sig["battery.stamp"])
    assert st[0] == pytest.approx(1.5)                                                    # {sec, nsec} too
    assert any("/proto: encoding 'protobuf' is not read yet" in s for s in run["report"]["skipped"])


def test_cut_off_recording_keeps_what_was_written(tmp_path):
    p = tmp_path / "full.mcap"
    write_ros2(p, seconds=20, chunk_size=16 * 1024)        # a long recording: many chunks
    data = p.read_bytes()
    cut = tmp_path / "cut.mcap"
    cut.write_bytes(data[: int(len(data) * 0.6)])
    run, sig = opened(cut)
    n = len(store.signal(sig["imu/accel.vector.x"])[0])
    assert run["report"].get("cutOff") is True and 0 < n < 2000


def test_wrong_extension_is_named(tmp_path):
    p = tmp_path / "flight.mcap"
    write_ros2(p, seconds=0.2)
    q = tmp_path / "flight.csv"
    q.write_bytes(p.read_bytes())
    with pytest.raises(LoadError) as e:
        store.open_file(str(q))
    assert e.value.code == "wrongExt" and ".mcap" in str(e.value)


def test_not_an_mcap(tmp_path):
    p = tmp_path / "x.mcap"
    p.write_bytes(os.urandom(5000))
    with pytest.raises(LoadError) as e:
        store.open_file(str(p))
    assert e.value.code in ("badMcap", "noSignals")


def write_h5(path):
    import h5py
    with h5py.File(path, "w") as f:
        f["time"] = np.arange(0, 10, 0.1)                              # the main time: 100 samples
        f["altitude"] = np.linspace(0, 99, 100)
        f["pos"] = np.column_stack([np.arange(100.0), np.zeros(100), np.ones(100)])   # 2-D: 3 columns
        g = f.create_group("imu")
        g["t"] = np.arange(0, 10, 0.01)                                # its own, faster time
        g["ax"] = np.sin(np.arange(1000) * 0.01)
        rec = np.zeros(100, dtype=[("rpm", "f8"), ("on", "?"), ("gear", "i4")])
        rec["rpm"] = 1500
        f["engine"] = rec                                              # a table
        f["odd"] = np.arange(7.0)                                      # no time of that length
        f["name"] = np.array([b"a", b"b"])                             # text: not a signal


def test_hdf5_groups_columns_tables_and_times(tmp_path):
    p = tmp_path / "test.h5"
    write_h5(p)
    run, sig = opened(p)
    assert run["format"] == "hdf5"
    t, y = store.signal(sig["altitude"])
    assert len(t) == 100 and t[-1] == pytest.approx(9.9)
    t, y = store.signal(sig["imu/ax"])
    assert len(t) == 1000 and t[1] == pytest.approx(0.01)                 # the group's own time
    assert {"pos[0]", "pos[1]", "pos[2]", "engine.rpm", "engine.on", "engine.gear"} <= set(sig)
    assert "time" not in sig and "imu/t" not in sig and "name" not in sig
    assert any(s.startswith("odd (7 values") for s in run["report"]["skipped"])


def test_hdf5_without_time_uses_the_sample_number(tmp_path):
    import h5py
    p = tmp_path / "plain.hdf5"
    with h5py.File(p, "w") as f:
        f["a"] = np.array([5.0, 6, 7])
    run, sig = opened(p)
    t, _ = store.signal(sig["a"])
    assert list(t) == [0, 1, 2] and run["report"].get("noTime") is True


def test_not_an_hdf5(tmp_path):
    p = tmp_path / "x.h5"
    p.write_bytes(b"not hdf5" * 100)
    with pytest.raises(LoadError) as e:
        store.open_file(str(p))
    assert e.value.code == "badHdf5"
