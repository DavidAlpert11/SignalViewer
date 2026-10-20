"""MAVLink .tlog, PX4 .ulg, health checks, time sync of two recordings, statistics while in a state,
spectrogram, report with spectrogram + notes:   python -m pytest backend/tests"""
import os
import subprocess
import sys
import time

import numpy as np
import pytest

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import store  # noqa: E402

client = TestClient(app)
TOOLS = os.path.join(ROOT, "tools")


@pytest.fixture(autouse=True)
def _clean():
    yield
    for rid in list(store.order):
        store.remove(rid)


def run_tool(*args):
    subprocess.run([sys.executable, *args], check=True, cwd=ROOT, capture_output=True)


@pytest.fixture(scope="module")
def flight(tmp_path_factory):
    d = tmp_path_factory.mktemp("flight")
    run_tool(os.path.join(TOOLS, "make_same_flight.py"), str(d), "--boot-at", "37.25")
    run_tool(os.path.join(TOOLS, "make_test_tlog.py"), str(d / "syn.tlog"), "--seconds", "60")
    run_tool(os.path.join(TOOLS, "make_test_bin.py"), str(d / "syn.bin"), "--seconds", "40")
    return d


def open_(path):
    r = client.post("/api/files/open", json={"paths": [str(path)]}).json()
    assert not r["errors"], r["errors"]
    return r["opened"][0]


def sid(info, name):
    return next(s["id"] for s in info["signals"] if s["name"] == name)


def wait_job(j):
    for _ in range(200):
        st = client.get(f"/api/jobs/{j}").json()
        if st["state"] != "running":
            return st
        time.sleep(0.05)
    return st


# ---------------------------------------------------------------------------- .tlog
def test_tlog_signals_units_enums_and_log(flight):
    info = open_(flight / "syn.tlog")
    assert info["format"] == "tlog"
    names = {s["name"]: s for s in info["signals"]}
    assert "ATTITUDE.roll [rad]" in names and "GPS_RAW_INT.lat [deg]" in names     # degE7 -> deg
    assert "SYS_STATUS.voltage_battery [V]" in names                               # mV -> V
    assert names["GPS_RAW_INT.fix_type"]["labels"]["3"] == "GPS_FIX_TYPE_3D_FIX"    # enum names
    assert names["HEARTBEAT.custom_mode"]["labels"]["5"] == "LOITER"               # ArduCopter mode names
    assert not any(n.startswith("HEARTBEAT[") for n in names)                       # the GCS's own heartbeat left out
    t, v = store.signal(names["BATTERY_STATUS[0].voltages[4] [V]"]["id"])
    assert np.isnan(v).all()                                                         # unused cells
    t, lat = store.signal(names["GPS_RAW_INT.lat [deg]"]["id"])
    assert abs(lat[0] - 32.0853) < 1e-6
    log = client.get(f"/api/runs/{info['id']}/log").json()
    assert log["vehicle"] == "copter" and log["firmware"].startswith("ArduCopter V4.5.7")
    ev = [(round(e["t"], 3), e["kind"], e["text"], e["level"]) for e in log["events"]]
    assert (5.0, "event", "ARMED", "info") in ev and (20.0, "mode", "RTL", "info") in ev
    assert any(x == "EKF variance" and lvl == "error" for _t, _k, x, lvl in ev)          # STATUSTEXT severity 2
    params = {p["name"]: p for p in log["params"]}
    assert params["RTL_ALT"]["changes"] == [[35.0, 2000.0]]


def test_tlog_live_append(tmp_path):
    p = tmp_path / "live.tlog"
    run_tool(os.path.join(TOOLS, "make_test_tlog.py"), str(p), "--seconds", "10")
    info = open_(p)
    full_before = len(store.signal(sid(info, "ATTITUDE.roll [rad]"))[0])
    data = open(p, "rb").read()
    q = tmp_path / "more.tlog"
    run_tool(os.path.join(TOOLS, "make_test_tlog.py"), str(q), "--seconds", "20")
    extra = open(q, "rb").read()[len(data):]                                         # what the next 10 s add
    with open(p, "ab") as f:
        f.write(extra[:-5])                                                          # a packet cut in half
    store.poll_appends()
    with open(p, "ab") as f:
        f.write(extra[-5:])
    store.poll_appends()
    n = len(store.signal(sid(info, "ATTITUDE.roll [rad]"))[0])
    assert n == 2 * full_before


# ---------------------------------------------------------------------------- .ulg
ULG = os.path.join(ROOT, "backend", "tests", "data", "sample.ulg")


@pytest.mark.skipif(not os.path.exists(ULG), reason="PX4 sample log not in the repository")
def test_ulog():
    info = open_(ULG)
    assert info["format"] == "ulg" and info["log"]["params"] > 400
    names = {s["name"]: s for s in info["signals"]}
    assert "vehicle_attitude.q[0]" in names
    assert names["vehicle_status.nav_state"]["labels"]["0"] == "MANUAL"
    assert "ekf2_innovations.vel_pos_innov[0]" not in names            # a topic with no time stamps is skipped
    log = client.get(f"/api/runs/{info['id']}/log").json()
    assert log["vehicle"] == "px4" and log["firmware"].startswith("PX4")
    assert any(p["changes"] for p in log["params"])


# ---------------------------------------------------------------------------- health
def test_health_finds_the_planted_faults(flight):
    info = open_(flight / "syn.bin")
    h = client.get(f"/api/runs/{info['id']}/health").json()
    f = {x["code"]: x for x in h["findings"]}
    assert f["vibration"]["level"] == "error" and f["vibration"]["vals"]["max"] == 63 and f["vibration"]["spans"][0][0] == 30
    assert f["ekf"]["level"] == "error" and f["ekf"]["t"] == 12
    assert f["battLow"]["vals"]["limit"] == 14                          # from the log's BATT_LOW_VOLT
    assert f["motorsSat"]["spans"][0][0] == 20
    assert f["motorsBalance"]["vals"]["motor"] == 1
    assert f["clipping"]["level"] == "warning"
    assert f["vcc"]["level"] == "ok"
    csv = flight / "plain.csv"
    csv.write_text("Time,A\n0,1\n1,2\n", encoding="utf-8")
    c = open_(csv)
    assert client.get(f"/api/runs/{c['id']}/health").status_code == 404


def test_health_on_tlog(flight):
    info = open_(flight / "syn.tlog")
    f = {x["code"]: x for x in client.get(f"/api/runs/{info['id']}/health").json()["findings"]}
    assert f["vibration"]["level"] == "warning" and f["vibration"]["t"] == pytest.approx(30, abs=0.01)
    assert f["gpsSats"]["vals"]["min"] == 5


# ---------------------------------------------------------------------------- sync
def test_sync_two_recordings_of_one_flight(flight):
    a = open_(flight / "flight.bin")
    b = open_(flight / "flight.tlog")
    c = client.post("/api/sync/suggest", json={"ref": a["id"], "other": b["id"]}).json()["candidates"]
    by = {x["method"]: x for x in c}
    assert set(by) == {"boot", "events", "signal"}
    for m in by.values():                       # true offset 37.25 s, minus 10-60 ms of radio latency
        assert 37.15 < m["delta"] < 37.26, m
        assert m["quality"] == "high"
    assert by["signal"]["corr"] > 0.99 and by["signal"]["check"]["scale"] == pytest.approx(57.2958, rel=1e-4)
    assert c[0]["method"] == "boot" and all(x.get("agrees", True) for x in c)
    # applying it: the .tlog's roll now lines up with the .bin's in time
    client.patch(f"/api/runs/{b['id']}", json={"timeOffset": c[0]["offset"]})
    ta, ya = store.signal(sid(a, "ATT.Roll"))
    tb, yb = store.signal(sid(b, "ATTITUDE.roll [rad]"))
    yi = np.interp(ta, tb, np.degrees(yb))
    ok = (ta > tb[0]) & (ta < tb[-1])
    assert np.sqrt(np.mean((yi[ok] - ya[ok]) ** 2)) < 1.0                  # degrees
    # the other way round, and by a pair of signals the user picks
    c2 = client.post("/api/sync/suggest", json={"ref": b["id"], "other": a["id"]}).json()["candidates"]
    assert c2[0]["delta"] == pytest.approx(-c[0]["delta"], abs=1e-6)
    c3 = client.post("/api/sync/suggest", json={"ref": a["id"], "other": b["id"], "refSignal": "ATT.Roll",
                                                "otherSignal": "ATTITUDE.roll [rad]"}).json()["candidates"]
    assert len(c3) == 1 and c3[0]["method"] == "signal" and 37.15 < c3[0]["delta"] < 37.3


# ---------------------------------------------------------------------------- stats while in a state, spectrogram
def test_stats_while_in_state_and_spectrogram(flight):
    info = open_(flight / "syn.tlog")
    roll, mode = sid(info, "ATTITUDE.roll [rad]"), sid(info, "HEARTBEAT.custom_mode")
    r = client.post("/api/stats", json={"signals": [roll], "state": mode, "stateValues": [6]}).json()["stats"][roll]
    assert r["segments"] == 1 and r["duration"] == pytest.approx(20, abs=1.1) and r["samples"] == 400   # RTL 20-40 s
    r = client.post("/api/stats", json={"signals": [roll], "t0": 30, "t1": 60, "state": mode, "stateValues": [6]}).json()["stats"][roll]
    assert r["duration"] == pytest.approx(10, abs=1.1)
    s = client.post("/api/spectrogram", json={"signal": roll, "width": 200, "height": 64}).json()
    assert s["fs"] == pytest.approx(20) and s["f1"] == pytest.approx(10, abs=0.2) and s["nt"] > 50
    assert s["sigT0"] < s["t0"] and s["sigT1"] > s["t1"]      # F24: the signal's own extent, wider than the windows
    img = np.frombuffer(__import__("base64").b64decode(s["img"]), np.uint8)
    assert img.size == s["nf"] * s["nt"]


def test_report_with_spectrogram_and_notes(flight, tmp_path):
    info = open_(flight / "syn.bin")
    imu = next(s["id"] for s in info["signals"] if s["name"].startswith("IMU[0].AccZ"))
    plots = [{"title": "Spec", "mode": "spec", "specN": 512, "signals": [{"id": imu, "color": "#3D8BFD"}]},
             {"title": "Time", "mode": "time", "signals": [{"id": imu, "color": "#3D8BFD"}]}]
    notes = [{"t": 12.0, "text": "EKF spike"}, {"t": 20.0, "t2": 26.5, "text": "Hover test"}]   # T23: a range
    for fmt in ("html", "pdf", "docx"):
        p = tmp_path / f"r.{fmt}"
        r = client.post("/api/report", json={"path": str(p), "format": fmt, "title": "T",
                                             "tabs": [{"name": "A", "plots": plots}], "notes": notes})
        assert r.status_code == 200 and p.stat().st_size > 10000, (fmt, r.text)
    html = (tmp_path / "r.html").read_text(encoding="utf-8")
    assert "specimg" in html and "EKF spike" in html
    assert "20 – 26.5 s" in html and "Hover test" in html


def test_boot_clock_messages_land_exactly(flight):
    """Messages that carry the autopilot's clock are placed at their own time, not at their (delayed,
    jittery) receive time: after syncing, the .tlog's roll matches the true roll at every sample."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("sf", os.path.join(TOOLS, "make_same_flight.py"))
    sf = importlib.util.module_from_spec(spec); spec.loader.exec_module(sf)
    a = open_(flight / "flight.bin")
    b = open_(flight / "flight.tlog")
    c = client.post("/api/sync/suggest", json={"ref": a["id"], "other": b["id"]}).json()["candidates"][0]
    client.patch(f"/api/runs/{b['id']}", json={"timeOffset": c["offset"]})
    t, y = store.signal(sid(b, "ATTITUDE.roll [rad]"))
    truth = np.array([sf.roll(x - 37.25) for x in t])
    steps = np.array([18, 21, 33, 34.5]) + 37.25
    away = np.min(np.abs(t[:, None] - steps[None, :]), axis=1) > 0.002
    assert np.max(np.abs(np.degrees(y) - truth)[away]) < 0.02          # 1 ms rounding of time_boot_ms only


def test_map_tiles_cache_and_offline(tmp_path, monkeypatch):
    """Tiles come from the disk cache when there is no network; unknown sources / zooms are refused."""
    import app.tiles as tiles
    monkeypatch.setattr(tiles, "CACHE", str(tmp_path))
    monkeypatch.setattr(tiles, "_offline_until", time.time() + 60)          # as if the network just failed
    d = tmp_path / "osm" / "3" / "4"
    d.mkdir(parents=True)
    (d / "2.png").write_bytes(b"\\x89PNG fake tile")
    r = client.get("/api/tiles/osm/3/4/2")
    assert r.status_code == 200 and r.content == b"\\x89PNG fake tile" and r.headers["content-type"] == "image/png"
    assert client.get("/api/tiles/osm/3/4/3").status_code == 404           # offline and not cached
    assert client.get("/api/tiles/nope/3/4/2").status_code == 404
    assert client.get("/api/tiles/topo/18/0/0").status_code == 404          # beyond the source's zoom


# ---------------------------------------------------------------------------- aligning any two files
@pytest.fixture(scope="module")
def experiment(tmp_path_factory):
    """One experiment recorded by three devices with their own clocks and rates:
    A.csv (true time, 100 Hz), B.csv (clock = true + 987.654 s, 50 Hz, other names), C.mat (true - 4.5 s, 20 Hz)."""
    import scipy.io
    d = tmp_path_factory.mktemp("exp")
    rng = np.random.default_rng(3)
    walk = np.cumsum(rng.normal(0, 0.4, 140))                 # one experiment: the same random part for every device
    T = lambda t: 3 * np.sin(0.9 * t) + 2 * np.sin(0.23 * t + 1) + np.interp(t, np.arange(0, 70, 0.5), walk)
    trig = lambda t: (t >= 12.0).astype(float)
    ta = np.arange(0, 60, 0.01)
    np.savetxt(d / "A.csv", np.c_[ta, T(ta), 101.3 + 0.2 * T(ta), trig(ta)], delimiter=",", header="Time,Speed,Pressure,Trigger", comments="", fmt="%.6f")
    tb_true = np.arange(5, 55, 0.02)
    np.savetxt(d / "B.csv", np.c_[tb_true + 987.654, T(tb_true) + rng.normal(0, 0.05, tb_true.size), 0.1013 + 0.0002 * T(tb_true), 5 * trig(tb_true)],
               delimiter=",", header="Time,Speed,Pres_kPa,TrigIn", comments="", fmt="%.6f")
    tc_true = np.arange(2, 58, 0.05)
    scipy.io.savemat(d / "C.mat", {"t": tc_true - 4.5, "Speed_mps": T(tc_true), "Trig": trig(tc_true)})
    return d


def test_align_any_files_by_same_name_pair_moment(experiment):
    a, b = open_(experiment / "A.csv"), open_(experiment / "B.csv")
    c = open_(experiment / "C.mat")
    # automatic: a signal with the same name in both (Speed)
    r = client.post("/api/sync/suggest", json={"ref": a["id"], "other": b["id"]}).json()["candidates"]
    assert r and r[0]["method"] == "signal" and r[0]["sameNames"] and r[0]["pair"] == ["Speed", "Speed"]
    assert r[0]["delta"] == pytest.approx(-987.654, abs=0.02) and r[0]["quality"] == "high"
    # two signals of the user's choice, with different names and units (Pressure ~ Pres_kPa)
    r = client.post("/api/sync/suggest", json={"ref": a["id"], "other": b["id"], "refSignal": "Pressure", "otherSignal": "Pres_kPa"}).json()["candidates"]
    assert r[0]["delta"] == pytest.approx(-987.654, abs=0.02)
    # a moment: the trigger's rise (0..1 in one file, 0..5 V in the other - the level is a share of each range)
    r = client.post("/api/sync/suggest", json={"ref": a["id"], "other": c["id"], "refSignal": "Trigger", "otherSignal": "Trig",
                                                "feature": {"kind": "rise", "levelPct": 50}}).json()["candidates"]
    assert r[0]["method"] == "feature" and r[0]["delta"] == pytest.approx(4.5, abs=0.06)
    r = client.post("/api/sync/suggest", json={"ref": a["id"], "other": b["id"], "refSignal": "Trigger", "otherSignal": "TrigIn",
                                                "feature": {"kind": "step"}}).json()["candidates"]
    assert r[0]["delta"] == pytest.approx(-987.654, abs=0.03)
    # a moment that is not there is reported, not guessed
    r = client.post("/api/sync/suggest", json={"ref": a["id"], "other": c["id"], "refSignal": "Trigger", "otherSignal": "Trig",
                                                "feature": {"kind": "fall"}}).json()["candidates"]
    assert r[0].get("error") == "notFound"
    # MAT vs CSV by correlation of differently named signals
    r = client.post("/api/sync/suggest", json={"ref": a["id"], "other": c["id"], "refSignal": "Speed", "otherSignal": "Speed_mps"}).json()["candidates"]
    assert r[0]["delta"] == pytest.approx(4.5, abs=0.06)


def test_align_periodic_signal_within_a_search_range(tmp_path):
    """A periodic signal correlates equally well one period away; a search range around the current
    alignment picks the right one."""
    t = np.arange(0, 40, 0.01)
    np.savetxt(tmp_path / "p1.csv", np.c_[t, np.sin(2 * np.pi * t / 2.0)], delimiter=",", header="Time,S", comments="", fmt="%.6f")
    np.savetxt(tmp_path / "p2.csv", np.c_[t - 0.3, np.sin(2 * np.pi * t / 2.0)], delimiter=",", header="Time,S", comments="", fmt="%.6f")
    a, b = open_(tmp_path / "p1.csv"), open_(tmp_path / "p2.csv")
    client.patch(f"/api/runs/{b['id']}", json={"timeOffset": 0.2})          # roughly aligned by hand already
    r = client.post("/api/sync/suggest", json={"ref": a["id"], "other": b["id"], "refSignal": "S", "otherSignal": "S", "maxLag": 0.6}).json()["candidates"]
    assert r[0]["delta"] == pytest.approx(0.3, abs=0.02)
