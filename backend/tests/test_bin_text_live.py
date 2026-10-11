"""ArduPilot .bin logs, text (state) values, live mode and refresh-all:  python -m pytest backend/tests"""
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
from svcore.analysis import transitions  # noqa: E402
from svcore.bin_loader import load_bin, append_new_messages  # noqa: E402
from svcore.csv_loader import encode_text  # noqa: E402
from svcore.decimate import hold_at  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    yield
    for rid in list(store.order):
        store.remove(rid)


def write_bin(path, t0=1.0, t1=11.0, corrupt=False, hz=100):
    mk.FMTS.clear()
    data = mk.header() + mk.body(t0, (t0 + t1) / 2, hz)
    if corrupt:
        data += b"\xa3\x95\x82garbage\xa3\x95" + bytes(range(40))
    data += mk.body((t0 + t1) / 2, t1, hz)
    with open(path, "wb") as f:
        f.write(data)


# ---------------------------------------------------------------------------- .bin
def test_bin_signals_units_instances_modes(tmp_path):
    p = str(tmp_path / "00000001.BIN")
    write_bin(p)
    run, rep = load_bin(p, "x")
    names = set(run.signals)
    assert "IMU[0].AccZ [m/s/s]" in names and "IMU[1].AccZ [m/s/s]" in names     # instances split
    assert "GPS[0].Lat [deg]" in names                                             # 'L' x 1e-7, unit
    assert "GPS[0].Alt [m]" in names                                               # cm -> m
    assert rep["vehicle"] == "copter"
    lat = run.signals["GPS[0].Lat [deg]"].data
    assert abs(lat[0] - 32.08531) < 1e-6                                           # 32.0853 + 1e-5 x t(=1)
    alt = run.signals["GPS[0].Alt [m]"].data
    assert abs(alt[0] - 10.10) < 1e-6                                              # int(1000 + 10*1) cm
    # every message type has its own time vector
    t_imu = run.signals["IMU[0].AccZ [m/s/s]"].time
    t_gps = run.signals["GPS[0].Alt [m]"].time
    assert len(t_imu) > 10 * len(t_gps) and np.all(np.diff(t_imu) > 0)
    # flight modes and text messages are state signals with their texts
    mode = run.signals["MODE.Mode"]
    assert mode.labels[0] == "STABILIZE" and mode.labels[5] == "LOITER"
    msg = run.signals["MSG.Message"]
    assert "ArduCopter V4.6.0 (synthetic)" in msg.labels.values()


def test_bin_corrupt_block_is_skipped(tmp_path):
    a, b = str(tmp_path / "a.bin"), str(tmp_path / "b.bin")
    write_bin(a)
    write_bin(b, corrupt=True)
    ra, _ = load_bin(a, "a")
    rb, rep = load_bin(b, "b")
    assert rep["corruptBytes"] > 0
    for n in ra.signals:
        assert np.array_equal(ra.signals[n].data, rb.signals[n].data, equal_nan=True), n


def test_bin_live_append_equals_full_read(tmp_path):
    p = str(tmp_path / "live.bin")
    write_bin(p, 1.0, 5.0)
    run, _ = load_bin(p, "x")
    chunk = mk.body(5.0, 7.0, 100)
    with open(p, "ab") as f:
        f.write(chunk[:-5])                      # a message cut in half: must wait for the rest
    assert append_new_messages(run) > 0
    with open(p, "ab") as f:
        f.write(chunk[-5:])
    append_new_messages(run)
    full, _ = load_bin(p, "x")
    for n, s in full.signals.items():
        assert np.array_equal(s.data, run.signals[n].data, equal_nan=True), n
        assert np.array_equal(s.time, run.signals[n].time), n


def test_bin_through_api(tmp_path):
    p = str(tmp_path / "flight.bin")
    write_bin(p)
    r = client.post("/api/files/open", json={"paths": [p]}).json()
    assert not r["errors"]
    info = r["opened"][0]
    assert info["format"] == "bin"
    mode = next(s for s in info["signals"] if s["name"] == "MODE.Mode")
    assert mode["labels"]["0"] == "STABILIZE" and mode["discrete"]
    imu = next(s for s in info["signals"] if s["name"] == "IMU[0].AccZ [m/s/s]")
    d = client.post("/api/data", json={"signals": [imu["id"]], "points": 500}).json()["series"][0]
    assert d["total"] == len(store.signal(imu["id"])[0]) and d["total"] > 500    # its own (IMU) time vector
    # a flight mode at the cursor is the mode in force, never an interpolation
    v = client.post("/api/cursor", json={"signals": [mode["id"]], "t": 10.5}).json()["values"][mode["id"]]
    assert v == 0.0
    st = client.post("/api/states", json={"signals": [mode["id"]]}).json()["states"][mode["id"]]
    assert st["points"][0][1] == 0 and st["end"] >= 10.9          # the last mode lasts to the end


# ---------------------------------------------------------------------------- text values
def test_csv_text_column_states_cache_and_live(tmp_path):
    p = tmp_path / "s.csv"
    rows = [f"{i*0.1:.1f},{i},{['IDLE', 'ARMED', 'FLYING'][(i // 10) % 3]},{'' if i % 5 else 'note'}" for i in range(50)]
    p.write_text("Time,Speed,State,Note\n" + "\n".join(rows) + "\n", encoding="utf-8")
    info = client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]
    sigs = {s["name"]: s for s in info["signals"]}
    assert sigs["State"]["labels"] == {"0": "IDLE", "1": "ARMED", "2": "FLYING"}
    assert "labels" not in sigs["Speed"]
    sid = sigs["State"]["id"]
    # sparse text: the value in force between two notes is the last note
    nid = sigs["Note"]["id"]
    assert client.post("/api/cursor", json={"signals": [nid], "t": 0.33}).json()["values"][nid] == 0.0
    # live: a new text appears -> new code, same map
    with open(p, "a") as f:
        f.write("5.0,50,LANDED,\n5.1,51,IDLE,\n")
    assert store.poll_appends() == [info["id"]]
    labels = store.runs[info["id"]].run.signals["State"].labels
    assert labels[3] == "LANDED"
    t, y = store.signal(sid)
    assert list(y[-2:]) == [3.0, 0.0]
    # opened again (from the binary cache): the texts come back too
    store.remove(info["id"])
    info2 = client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]
    st = next(s for s in info2["signals"] if s["name"] == "State")
    assert st["labels"]["3"] == "LANDED"


def test_encode_text_continues_codes():
    codes, labels = encode_text(["A", "B", None, "", "A"])
    assert list(codes[:2]) == [0, 1] and np.isnan(codes[2]) and np.isnan(codes[3]) and codes[4] == 0
    codes2, labels2 = encode_text(["C", "A"], labels)
    assert list(codes2) == [2, 0] and labels2 == {0: "A", 1: "B", 2: "C"}


def test_transitions_collapse_and_hold():
    t = np.arange(200000) * 0.001
    y = (np.arange(200000) // 3 % 2).astype(float)          # changes every 3 samples: too many to draw
    y[150000:] = 7
    pts, collapsed, end = transitions(t, y, bins=200)
    assert collapsed and pts[1][1] is None and pts[-1][1] == 7.0 and end == pytest.approx(t[-1])
    assert len(pts) < 20
    assert hold_at(t, y, 160.0) == 7.0
    assert hold_at(np.array([0.0, 1.0, 2.0]), np.array([5.0, np.nan, np.nan]), 1.9) == 5.0


# ---------------------------------------------------------------------------- refresh all / live
def test_refresh_all_and_new_files(tmp_path):
    a = tmp_path / "run_001.csv"
    a.write_text("Time,A\n0,1\n1,2\n", encoding="utf-8")
    b = tmp_path / "run_002.csv"
    b.write_text("Time,A\n0,1\n", encoding="utf-8")
    opened = client.post("/api/files/open", json={"paths": [str(a), str(b)]}).json()["opened"]
    res = store.reload_all()
    assert sorted(res["unchanged"]) == sorted(o["id"] for o in opened)          # untouched: not read again
    time.sleep(0.02)
    a.write_text("Time,A\n0,1\n1,2\n2,3\n", encoding="utf-8")
    res = store.reload_all()
    assert res["reloaded"] == [opened[0]["id"]]
    assert store.runs[opened[0]["id"]].run.sample_count == 3
    # live mode: a new file with the same name pattern appears next to them
    client.post("/api/stream/start", json={})
    (tmp_path / "run_003.csv").write_text("Time,A\n0,1\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")              # other pattern: ignored
    r = client.post("/api/stream/poll", json={}).json()
    assert [f["name"] for f in r["newFiles"]] == ["run_003.csv"]
    with open(b, "a") as f:
        f.write("1,5\n")
    time.sleep(2.1)                                                            # next scan is due
    r = client.post("/api/stream/poll", json={}).json()
    assert r["changed"] == [opened[1]["id"]] and r["newFiles"] == []           # reported once
    assert r["activity"][opened[1]["id"]] < 5
    client.post("/api/stream/stop", json={})


def test_reload_all_job(tmp_path):
    a = tmp_path / "x.csv"
    a.write_text("Time,A\n0,1\n", encoding="utf-8")
    client.post("/api/files/open", json={"paths": [str(a)]})
    job = client.post("/api/jobs", json={"kind": "reloadAll", "params": {}}).json()
    for _ in range(100):
        st = client.get(f"/api/jobs/{job['id']}").json()
        if st["state"] != "running":
            break
        time.sleep(0.05)
    assert st["state"] == "done" and "unchanged" in st["result"]


# ---------------------------------------------------------------------------- flight log: params & events
def test_log_params_and_events(tmp_path):
    p = str(tmp_path / "log.bin")
    write_bin(p, 1.0, 25.0)
    info = client.post("/api/files/open", json={"paths": [p]}).json()["opened"][0]
    assert info["log"]["params"] == 10 and info["log"]["errors"] >= 1 and info["log"]["warnings"] >= 1
    log = client.get(f"/api/runs/{info['id']}/log").json()
    assert log["vehicle"] == "copter" and log["firmware"].startswith("ArduCopter V4.6.0")
    params = {x["name"]: x for x in log["params"]}
    assert params["ATC_RAT_PIT_P"]["value"] == 0.15 and params["ATC_RAT_PIT_P"]["default"] == 0.135   # float32 shown as written
    gyro = params["INS_GYRO_FILTER"]
    assert gyro["first"] == 20 and gyro["changes"] == [[11.0, 25.0], [21.0, 30.0]] and gyro["value"] == 30
    ev = [(e["t"], e["kind"], e["text"], e["level"]) for e in log["events"]]
    assert (4.0, "event", "ARMED", "info") in ev
    assert (11.0, "mode", "ACRO", "info") in ev
    assert any(k == "error" and lvl == "error" for _t, k, _x, lvl in ev)
    assert any(x.startswith("PreArm") and lvl == "warning" for _t, _k, x, lvl in ev)
    assert [e["t"] for e in log["events"]] == sorted(e["t"] for e in log["events"])


def test_no_log_for_other_formats(tmp_path):
    c = tmp_path / "plain.csv"
    c.write_text("Time,A\n0,1\n1,2\n", encoding="utf-8")
    info = client.post("/api/files/open", json={"paths": [str(c)]}).json()["opened"][0]
    assert "log" not in info                                                  # the UI shows no Log panel
    assert client.get(f"/api/runs/{info['id']}/log").status_code == 404


def test_param_file_saved_without_bom(tmp_path):
    out = tmp_path / "p.param"
    client.post("/api/save/text", json={"path": str(out), "content": "A,1\r\n", "ext": ".param", "bom": False})
    assert out.read_bytes() == b"A,1\r\n"


def test_ui_function_list_matches_server():
    """The formula suggestions (frontend/src/formulaHelp.ts) offer exactly the server's functions."""
    import re
    from svcore.formula import FUNCTION_NAMES
    src = open(os.path.join(HERE, "..", "..", "frontend", "src", "formulaHelp.ts"), encoding="utf-8").read()
    ui = re.findall(r"^  (\w+): \{ args:", src, re.M)
    assert sorted(ui) == sorted(FUNCTION_NAMES)
