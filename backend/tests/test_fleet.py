"""T41: the fleet index - many flight logs, search by finding, trends, incremental rescans."""
import os
import shutil
import subprocess
import sys
import time

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app import fleet  # noqa: E402
from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from svcore.models import Run, Signal  # noqa: E402

client = TestClient(app)
TOOLS = os.path.join(os.path.dirname(__file__), "..", "..", "tools")
ULG = os.path.join(os.path.dirname(__file__), "data", "sample.ulg")


@pytest.fixture(scope="module")
def logs(tmp_path_factory):
    d = tmp_path_factory.mktemp("flights")
    subprocess.run([sys.executable, os.path.join(TOOLS, "make_test_bin.py"), str(d / "f1.bin"), "--seconds", "20",
                    "--imu-hz", "50"], check=True, capture_output=True)
    subprocess.run([sys.executable, os.path.join(TOOLS, "make_test_tlog.py"), str(d / "f2.tlog"), "--seconds", "20"],
                   check=True, capture_output=True)
    (d / "sub").mkdir()
    shutil.copy(ULG, d / "sub" / "f3.ulg")
    (d / "bad.bin").write_bytes(os.urandom(4000))
    (d / "notes.csv").write_text("t,v\n0,1\n")
    return d


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(fleet, "DB_PATH", str(tmp_path / "fleet.sqlite"))
    fleet.reset_connection()
    yield
    fleet.reset_connection()


def by_name(rows):
    return {r["name"]: r for r in rows}


def test_scan_reads_every_log_once_and_keeps_the_open_files_alone(logs, db):
    before = list(store.order)
    r = fleet.scan(str(logs))
    assert (r["total"], r["read"], r["failed"]) == (4, 4, 1)              # 3 logs + the damaged one; not the .csv
    assert list(store.order) == before                                     # the app's open files untouched
    rows = by_name(fleet.query())
    assert set(rows) == {"f1.bin", "f2.tlog", "f3.ulg", "bad.bin"}
    assert rows["bad.bin"]["error"] and rows["f1.bin"]["error"] is None
    assert rows["f1.bin"]["duration"] > 10 and rows["f1.bin"]["date_source"] == "file"
    assert rows["f1.bin"]["modes"] and rows["f1.bin"]["metrics"]["vibration.max"] > 0
    keys = {k["key"] for k in fleet.keys()}
    assert {"vibration.max", "duration"} <= keys


def test_search_by_finding_number_text_and_mode(logs, db):
    fleet.scan(str(logs))
    assert set(by_name(fleet.query(level="error"))) == {"f1.bin", "f3.ulg"}
    assert set(by_name(fleet.query(level="warning", code="logWarnings"))) == {"f2.tlog"}
    assert fleet.query(level="warning", code="gpsSats") == []            # an "ok" finding is not a warning
    assert "f2.tlog" in by_name(fleet.query(code="gpsSats"))              # ...but the check ran on it
    rows = by_name(fleet.query())
    hi, lo = rows["f1.bin"]["metrics"]["vibration.max"], rows["f2.tlog"]["metrics"]["vibration.max"]
    assert hi > lo
    mid = (hi + lo) / 2                                                    # a threshold between the two logs
    assert [r["name"] for r in fleet.query(key="vibration.max", above=mid)] == ["f1.bin"]
    assert [r["name"] for r in fleet.query(key="vibration.max", below=mid)] == ["f2.tlog"]
    assert [r["name"] for r in fleet.query(text="tlog")] == ["f2.tlog"]
    mode = next(iter(by_name(fleet.query())["f1.bin"]["modes"]))
    assert "f1.bin" in by_name(fleet.query(mode=mode))


def test_trend_is_by_date(logs, db):
    fleet.scan(str(logs))
    pts = fleet.trend("vibration.max")
    assert {p["name"] for p in pts} == {"f1.bin", "f2.tlog"}
    assert [p["date"] for p in pts] == sorted(p["date"] for p in pts)


def test_rescan_reads_only_what_changed(logs, db, tmp_path):
    d = tmp_path / "copy"
    shutil.copytree(logs, d)
    fleet.scan(str(d))
    r = fleet.scan(str(d))
    assert (r["read"], r["unchanged"], r["removed"]) == (0, 4, 0)
    subprocess.run([sys.executable, os.path.join(TOOLS, "make_test_tlog.py"), str(d / "f2.tlog"), "--seconds", "30"],
                   check=True, capture_output=True)
    os.remove(d / "f1.bin")
    r = fleet.scan(str(d))
    assert (r["read"], r["unchanged"], r["removed"]) == (1, 2, 1)
    assert "f1.bin" not in by_name(fleet.query())
    fleet.remove_folder(str(d))
    assert fleet.query() == [] and fleet.folders() == []


def test_flight_date_from_gps_time():
    t = np.arange(0.0, 10.0, 1.0)
    run = Run(file_path="x.bin", csv_display_name="x", time=t)
    run.signals["GPS.GWk"] = Signal(name="GPS.GWk", data=np.r_[0, 0, np.full(8, 2400.0)], time=t)
    run.signals["GPS.GMS"] = Signal(name="GPS.GMS", data=np.r_[0, 0, np.full(8, 100_000.0)], time=t)
    run.compute_metadata()
    want = fleet.GPS_EPOCH + 2400 * 604800 + 100.0 - fleet.LEAP - 2.0     # the fix is 2 s into the log
    assert fleet.flight_date(run) == pytest.approx(want)
    run2 = Run(file_path="x.ulg", csv_display_name="x", time=t)
    run2.signals["sensor_gps.time_utc_usec"] = Signal(name="sensor_gps.time_utc_usec",
                                                      data=np.r_[0, 1.7e15, np.full(8, 1.7e15)], time=t)
    run2.compute_metadata()
    assert fleet.flight_date(run2) == pytest.approx(1.7e9 - 1.0)
    # F11: a modern ArduPilot log - instanced GPS, FMTU units: GMS arrives in SECONDS ("GPS[0].GMS [s]")
    run3 = Run(file_path="y.bin", csv_display_name="y", time=t)
    run3.signals["GPS[1].GWk"] = Signal(name="GPS[1].GWk", data=np.full(10, 2399.0), time=t)    # 2nd receiver
    run3.signals["GPS[0].GWk"] = Signal(name="GPS[0].GWk", data=np.r_[0, 0, np.full(8, 2400.0)], time=t)
    run3.signals["GPS[0].GMS [s]"] = Signal(name="GPS[0].GMS [s]", data=np.r_[0, 0, np.full(8, 100.0)], time=t)
    run3.compute_metadata()
    assert fleet.flight_date(run3) == pytest.approx(want)


def test_an_index_from_before_f11_reads_its_bin_logs_again(db, tmp_path):
    """F11 in an existing index: a scan skips unchanged files, so the .bin logs a 1.5.0 index dated
    by the file must be read again once - the index's version (PRAGMA user_version) says so."""
    import calendar
    import shutil
    ex = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "copter_flight.bin")
    logs = tmp_path / "logs"
    logs.mkdir()
    shutil.copy(ex, logs / "f.bin")
    first = fleet.scan(str(logs))
    assert first["read"] == 1
    again = fleet.scan(str(logs))
    assert again["read"] == 0 and again["unchanged"] == 1            # unchanged files are skipped
    # make it look like an index written by 1.5.0: version 0, the log dated by the file
    conn = fleet._db()
    conn.execute("UPDATE logs SET date_source = 'file', date = 0")
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    fleet.reset_connection()
    upgraded = fleet.scan(str(logs))
    assert upgraded["read"] == 1                                       # read again, once
    row = fleet._db().execute("SELECT date, date_source FROM logs").fetchone()
    assert row["date_source"] != "file"
    assert row["date"] == pytest.approx(calendar.timegm((2026, 9, 14, 6, 30, 0)), abs=1.0)
    assert fleet.scan(str(logs))["read"] == 0                          # and not again after that


def test_flight_date_of_the_ardupilot_example():
    """F11 found with T45: the example .bin is written like real firmware (GPS[0], FMTU); its GPS
    time says 2026-09-14 06:30 UTC."""
    import calendar
    from app.store import Store
    ex = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "copter_flight.bin")
    lr = Store().open_file(ex)
    assert fleet.flight_date(lr.run) == pytest.approx(calendar.timegm((2026, 9, 14, 6, 30, 0)), abs=1.0)


def test_through_the_api_as_a_job(logs, db):
    job = client.post("/api/fleet/folder", json={"path": str(logs)}).json()
    for _ in range(300):
        st = client.get(f"/api/jobs/{job['id']}").json()
        if st["state"] != "running":
            break
        time.sleep(0.1)
    assert st["state"] == "done" and st["result"]["read"] == 4
    assert len(client.get("/api/fleet/logs", params={"level": "error"}).json()["logs"]) == 2
    assert client.get("/api/fleet/trend", params={"key": "duration"}).json()["points"]
    assert client.post("/api/fleet/folder", json={"path": str(logs / "nope")}).status_code == 400
