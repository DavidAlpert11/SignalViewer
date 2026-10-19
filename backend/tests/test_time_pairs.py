"""Columns with a time column of their own, found by name (owner's request 2026-10-19: telemetry
exports - "the time column and the value column can be told apart by their names")."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from svcore.csv_loader import CSVImportSettings, load_csv  # noqa: E402
from svcore.time_pairs import find_time_pairs  # noqa: E402

client = TestClient(app)


def test_naming_rules():
    assert find_time_pairs(["Time", "Speed", "Speed_time", "RPM", "time_RPM", "Alt [m]", "Alt_t [s]"], "Time") == \
        {"Speed": "Speed_time", "RPM": "time_RPM", "Alt [m]": "Alt_t [s]"}
    assert find_time_pairs(["time", "Speed", "time_1", "RPM", "time_2", "Alt"], "time") == {"RPM": "time_1", "Alt": "time_2", "Speed": "time"}
    assert find_time_pairs(["Time", "ATTITUDE.time_boot_ms", "ATTITUDE.roll", "ATTITUDE.pitch", "GPS.timestamp", "GPS.lat", "VFR.alt"], "Time") == \
        {"ATTITUDE.roll": "ATTITUDE.time_boot_ms", "ATTITUDE.pitch": "ATTITUDE.time_boot_ms", "GPS.lat": "GPS.timestamp"}
    assert find_time_pairs(["Time", "ATTITUDE_time_boot_ms", "ATTITUDE_roll"], "Time") == {"ATTITUDE_roll": "ATTITUDE_time_boot_ms"}
    # ordinary files are left alone - a data column called gps_time is not the time of gps_lat
    assert find_time_pairs(["Time", "gps_time", "gps_lat", "gps_lon"], "Time") == {}
    assert find_time_pairs(["Time", "Speed", "RPM", "Gear"], "Time") == {}


def _write(path, header, rows):
    with open(path, "w") as f:
        f.write(",".join(header) + "\n")
        for r in rows:
            f.write(",".join("" if v is None else repr(float(v)) for v in r) + "\n")
    return str(path)


def test_alternating_columns_of_different_lengths(tmp_path):
    # time,Speed (10 Hz, 50 rows) | time,RPM (2 Hz, 10 rows, starts later) - the shorter pair is padded
    rows = []
    for i in range(50):
        rpm = (2.0 + i * 0.5, 1000 + i) if i < 10 else (None, None)
        rows.append([i * 0.1, 10 + i, *rpm])
    p = _write(tmp_path / "pairs.csv", ["time", "Speed", "time", "RPM"], rows)
    run = load_csv(p, [p])
    assert set(run.signals) == {"Speed", "RPM"}                       # the time columns are not signals
    rpm = run.signals["RPM"]
    assert rpm.time is not None and len(rpm.time) == 10 and abs(rpm.time[0] - 2.0) < 1e-9 and rpm.data[3] == 1003
    assert len(run.signals["Speed"].data) == 50                       # no row of the longer pair lost
    assert run.load_report["timePairs"] >= 1 and run.load_report["droppedRows"] == 0


def test_own_time_next_to_a_main_time(tmp_path):
    rows = [[i, i * 2, (i * 0.5 if i < 6 else None), (i * 100 if i < 6 else None)] for i in range(12)]
    p = _write(tmp_path / "own.csv", ["Time", "Speed", "Volt_time", "Volt"], rows)
    run = load_csv(p, [p])
    assert run.signals["Speed"].time is None and len(run.signals["Speed"].data) == 12
    assert list(run.signals["Volt"].time) == [0, 0.5, 1, 1.5, 2, 2.5]
    off = load_csv(p, [p], CSVImportSettings(time_pairs=False))       # the import option turns it off
    assert "Volt_time" in off.signals and off.signals["Volt"].time is None


def test_message_time_columns(tmp_path):
    rows = [[i, 1000 + i * 20, 0.01 * i, 2000 + i * 200, 32.1 + i * 1e-5] for i in range(20)]
    p = _write(tmp_path / "msgs.csv", ["Time", "ATTITUDE.time_boot_ms", "ATTITUDE.roll", "GPS.time_boot_ms", "GPS.lat"], rows)
    run = load_csv(p, [p])
    assert run.signals["ATTITUDE.roll"].time[1] == 1020 and run.signals["GPS.lat"].time[1] == 2200
    assert "ATTITUDE.time_boot_ms" not in run.signals


def test_a_text_tlog_opens_as_a_table(tmp_path):
    rows = [[i * 0.2, i, (i * 0.5 if i < 5 else None), (i * 3 if i < 5 else None)] for i in range(10)]
    p = _write(tmp_path / "flight.tlog", ["Speed_time", "Speed", "Alt_time", "Alt"], rows)
    r = client.post("/api/files/open", json={"paths": [p]}).json()
    o = r["opened"][0]
    try:
        assert o and o.get("id"), r
        names = {s["name"] for s in o["signals"]}
        assert names == {"Speed", "Alt"}
        t, _ = store.signal(f"{o['id']}/Alt")
        assert len(t) == 5 and abs(t[-1] - 2.0) < 1e-9
    finally:
        client.delete(f"/api/runs/{o['id']}")


def test_mat_pairs_with_their_own_length(tmp_path):
    from scipy.io import savemat
    p = str(tmp_path / "m.mat")
    savemat(p, {"time": np.arange(100) * 0.01, "Speed": np.arange(100.0),
                "Volt_time": np.arange(7) * 1.0, "Volt": np.linspace(16, 15, 7)})
    from svcore.mat_loader import load_mat
    run, skipped = load_mat(p, "m.mat")
    assert "Volt" in run.signals and len(run.signals["Volt"].time) == 7 and "Volt" not in skipped
    assert "Volt_time" not in run.signals
