"""T22: what the file list shows per signal - its sample rate (from the describe) and a small
picture (/api/sparks):  python -m pytest backend/tests/test_signal_list_info.py"""
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import spark, store  # noqa: E402

client = TestClient(app)
ROOT = os.path.join(HERE, "..", "..")


def test_rate_and_samples_per_signal(tmp_path):
    t = np.arange(0, 10, 0.01)                                         # 100 Hz
    p = tmp_path / "r.csv"
    np.savetxt(p, np.column_stack([t, np.sin(t), t]), delimiter=",", header="Time,A [m],B", comments="", fmt="%.6g")
    run = client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]
    a = next(s for s in run["signals"] if s["name"] == "A [m]")
    assert a["n"] == 1000 and abs(a["rate"] - 100) < 0.01
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_test_bin.py"), str(tmp_path / "f.bin"), "--seconds", "10"],
                   check=True, capture_output=True)
    log = client.post("/api/files/open", json={"paths": [str(tmp_path / "f.bin")]}).json()["opened"][0]
    rates = {s["name"]: s.get("rate") for s in log["signals"]}
    assert rates["IMU[0].AccZ [m/s/s]"] > rates["GPS[0].Lat [deg]"] > 0      # every message type at its own rate
    for r in (run, log):
        store.remove(r["id"])


def test_spark_keeps_spikes_and_gaps():
    y = np.zeros(10000)
    y[5000] = 7.0                                                      # one spike in 10000 samples
    y[:100] = np.nan
    s = spark(np.arange(10000.0), y, 40)
    assert len(s["lo"]) == len(s["hi"]) == 40 and max(v for v in s["hi"] if v is not None) == 7.0
    assert s["lo"][0] == 0.0                                           # a slice with some NaN still has its values
    assert spark(np.arange(3.0), np.array([np.nan] * 3)) is None and spark(np.array([]), np.array([])) is None
    short = spark(np.arange(5.0), np.arange(5.0), 40)
    assert short["lo"] == [0.0, 1.0, 2.0, 3.0, 4.0]


def test_sparks_endpoint(tmp_path):
    p = tmp_path / "s.csv"
    t = np.arange(0, 1, 0.001)
    np.savetxt(p, np.column_stack([t, t * 2]), delimiter=",", header="Time,X", comments="", fmt="%.6g")
    run = client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]
    r = client.post("/api/sparks", json={"signals": [f"{run['id']}/X", "nope/x"], "points": 20}).json()["sparks"]
    assert len(r[f"{run['id']}/X"]["hi"]) == 20 and r["nope/x"] is None
    store.remove(run["id"])
