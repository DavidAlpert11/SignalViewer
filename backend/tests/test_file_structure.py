"""F1 *The file*: the structure of any recording - groups, rates, units, gaps, the time base -
for a CSV, a .mat, a .bin, a .ulg, an .mcap and a followed (live) MAVLink link."""
import os
import subprocess
import sys

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store
from svcore import filestruct

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
TOOLS = os.path.join(ROOT, "tools")
client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    yield
    for rid in list(store.order):
        store.remove(rid)


def tool(*args):
    subprocess.run([sys.executable, *args], check=True, cwd=ROOT, capture_output=True)


def struct(path):
    rid = store.open_file(str(path)).id
    r = client.get(f"/api/runs/{rid}/structure")
    assert r.status_code == 200, r.text
    s = r.json()
    return rid, s, {g["name"]: g for g in s["groups"]}


def test_csv_prefix_groups_units_rate_and_a_gap(tmp_path):
    t = np.r_[np.arange(0, 5, 0.01), np.arange(7, 10, 0.01)]          # 100 Hz with a 2 s hole
    p = tmp_path / "bench.csv"
    cols = np.column_stack([t, t, t * 2, np.sin(t)])
    np.savetxt(p, cols, delimiter=",", header="Time,Engine_rpm [1/min],Engine_temp [degC],Speed", comments="", fmt="%.6g")
    _, s, g = struct(p)
    assert s["format"] == "csv" and s["timeBase"]["column"] == "Time" and s["columns"] == 3
    eng = g["Engine"]
    assert eng["kind"] == "prefix" and [c["field"] for c in eng["columns"]] == ["rpm", "temp"]
    assert eng["columns"][0]["unit"] == "1/min" and eng["rate"] == pytest.approx(100, rel=0.3)
    assert eng["gaps"] == 1 and eng["longestGap"] == pytest.approx(2.01, abs=0.02)
    assert g[""]["kind"] == "columns" and g[""]["columns"][0]["name"] == "Speed"


def test_mat_structs_and_own_time(tmp_path):
    from scipy.io import savemat
    t = np.linspace(0, 1, 101)
    savemat(tmp_path / "sim.mat", {"t": t, "ctrl": {"u": np.sin(t), "e": np.cos(t)}, "y": t * 2,
                                   "gps": {"lat": np.ones(11), "time": np.linspace(0, 1, 11)}})
    _, s, g = struct(tmp_path / "sim.mat")
    assert s["format"] == "mat" and s["timeBase"]["column"] == "t"
    assert g["ctrl"]["kind"] == "struct" and sorted(c["field"] for c in g["ctrl"]["columns"]) == ["e", "u"]
    assert g["ctrl"]["rate"] == pytest.approx(100) and g["ctrl"]["n"] == 101
    assert g["gps"]["columns"][0]["ownTime"] and g["gps"]["n"] == 11            # its own time vector
    assert [c["name"] for c in g[""]["columns"]] == ["y"]


def test_ardupilot_log_message_types_at_their_own_rates(tmp_path):
    tool(os.path.join(TOOLS, "make_test_bin.py"), str(tmp_path / "f.bin"), "--seconds", "10", "--imu-hz", "100")
    _, s, g = struct(tmp_path / "f.bin")
    assert s["format"] == "bin" and s["timeBase"]["clock"] == "log"
    imu, gps = g["IMU[0]"], g["GPS[0]"]
    assert imu["kind"] == "message" and imu["rate"] > gps["rate"] > 0
    assert any(c["unit"] == "m/s/s" for c in imu["columns"])
    assert any(c.get("state") for c in g.get("MODE", {"columns": []})["columns"]) or "MODE" not in g
    assert s["timeVectors"] >= 3


def test_px4_ulog_topics():
    ulg = os.path.join(ROOT, "backend", "tests", "data", "sample.ulg")
    _, s, g = struct(ulg)
    assert s["format"] == "ulg" and len(g) > 5
    assert g["actuator_outputs"]["kind"] == "message" and g["actuator_outputs"]["rate"] > 1
    assert sum(len(x["columns"]) for x in s["groups"]) == s["columns"]


def test_mcap_topics(tmp_path):
    pytest.importorskip("mcap_ros2")
    from tests.test_mcap_hdf5 import write_ros2
    write_ros2(tmp_path / "f.mcap")
    _, s, g = struct(tmp_path / "f.mcap")
    assert s["format"] == "mcap" and g["imu/accel"]["kind"] == "topic"
    assert g["imu/accel"]["rate"] == pytest.approx(100, rel=0.02) and g["status"]["rate"] == pytest.approx(10, rel=0.05)
    assert any(c.get("state") for c in g["status"]["columns"])                  # status.note is text


def test_a_followed_mavlink_link_grows(tmp_path):
    """Live MAVLink records into a .tlog that the app follows: the structure is read as it is now."""
    p, q = tmp_path / "live.tlog", tmp_path / "more.tlog"
    tool(os.path.join(TOOLS, "make_test_tlog.py"), str(p), "--seconds", "10")
    tool(os.path.join(TOOLS, "make_test_tlog.py"), str(q), "--seconds", "20")
    rid, s, g = struct(p)
    assert s["format"] == "tlog" and g["ATTITUDE"]["kind"] == "message"
    n0 = g["ATTITUDE"]["n"]
    with open(p, "ab") as f:
        f.write(open(q, "rb").read()[os.path.getsize(p):])
    store.poll_appends()
    g2 = {x["name"]: x for x in client.get(f"/api/runs/{rid}/structure").json()["groups"]}
    assert g2["ATTITUDE"]["n"] == 2 * n0


def test_group_rules_and_unknown_file():
    assert filestruct.group_key("ATT.Roll [deg]", "bin") == ("ATT", "Roll")
    assert filestruct.group_key("a.b.c", "mat") == ("a.b", "c")
    assert filestruct.group_key("MOT_1_PWM", "csv", {"MOT"}) == ("MOT", "1_PWM")
    assert filestruct.group_key("Speed", "csv", {"MOT"}) == ("", "Speed")
    assert client.get("/api/runs/nope/structure").status_code == 404
