"""M1: summarize runs - measures per run, parameters from the file name, the CLI over a folder."""
import csv
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from signalviewer.cli import main  # noqa: E402
from svcore.summary import params_from_name, take  # noqa: E402

client = TestClient(app)


@pytest.fixture
def folder(tmp_path):
    t = np.arange(0, 10, 0.01)
    for kp in (0.5, 1.0, 2.0):
        y = 1 - np.exp(-kp * t) * np.cos(3 * t)
        with open(tmp_path / f"kp_{kp}_wind_low.csv", "w") as f:
            f.write("Time,Roll [deg],Mode\n")
            for ti, yi in zip(t, y):
                f.write(f"{ti:.3f},{yi:.6f},{int(ti >= 5)}\n")
    yield tmp_path
    for rid in list(store.order):
        store.remove(rid)


MEASURES = [{"name": "peak", "signal": "Roll", "op": "max"}, {"name": "final", "signal": "Roll", "op": "final"},
            {"name": "late mean", "signal": "Roll", "op": "mean", "where": "Mode == 1"},
            {"name": "none", "signal": "Nope", "op": "max"}]


def test_measures_of_the_open_runs(folder):
    opened = client.post("/api/files/open", json={"paths": sorted(str(p) for p in folder.glob("*.csv"))}).json()["opened"]
    r = client.post("/api/runs/summary", json={"measures": MEASURES, "pattern": "kp_{kp}_wind_{wind}"}).json()["rows"]
    assert len(r) == 3
    row = r[opened[0]["id"]]
    assert row["params"] == {"kp": 0.5, "wind": "low"}
    assert row["values"]["peak"] > 1.1 and row["values"]["none"] is None
    assert row["values"]["late mean"] == pytest.approx(1.0, abs=0.05)
    bad = client.post("/api/runs/summary", json={"measures": [{"signal": "Roll", "op": "median"}]})
    assert bad.status_code == 400 and "median" in bad.json()["detail"]


def test_cli_summarize_a_folder(folder, tmp_path_factory):
    m = tmp_path_factory.mktemp("m") / "m.json"
    m.write_text(json.dumps({"measures": MEASURES[:2], "pattern": "kp_{kp}_wind_{wind}"}))
    out = tmp_path_factory.mktemp("o") / "table.csv"
    assert main(["summarize", str(folder), "--measures", str(m), "--out", str(out)]) == 0
    rows = list(csv.DictReader(open(out, encoding="utf-8-sig")))
    assert [float(r["kp"]) for r in rows] == [0.5, 1.0, 2.0] and set(rows[0]) == {"recording", "kp", "wind", "peak", "final"}
    assert float(rows[0]["peak"]) > float(rows[2]["peak"])          # less gain, more overshoot here
    assert not store.order or all(rid not in store.runs for rid in store.order)


def test_take_and_names():
    t = np.linspace(0, 10, 1001)
    y = 1 - np.exp(-t) * np.cos(3 * t)
    assert take(t, y, "overshoot") == pytest.approx(37, abs=1) and 2 < take(t, y, "settle") < 5
    assert take(t, y, "at", 99) is None and take(t, np.full(5, np.nan)[:0], "max") is None
    assert params_from_name("flight_{run}.bin", "/a/flight_12.bin") == {"run": 12.0}
    assert params_from_name("kp_{kp}", "other.csv") == {}


def test_folder_job_reads_one_file_at_a_time(folder):
    import time
    before = set(store.order)
    j = client.post("/api/jobs", json={"kind": "summarizeFolder", "body": {"folder": str(folder), "measures": MEASURES[:1],
                                                                           "pattern": "kp_{kp}_wind_{wind}"}}).json()
    for _ in range(100):
        j = client.get(f"/api/jobs/{j['id']}").json()
        if j["state"] not in ("running", "queued"):
            break
        time.sleep(0.1)
    assert j["state"] == "done", j
    res = j["result"]
    assert res["columns"] == ["recording", "kp", "wind", "peak"] and len(res["rows"]) == 3 and not res["skipped"]
    assert set(store.order) == before                    # nothing opened in the app
    bad = client.post("/api/jobs", json={"kind": "summarizeFolder", "body": {"folder": str(folder / "nope"), "measures": MEASURES[:1]}})
    assert bad.status_code == 400


def _wait(j):
    import time
    for _ in range(300):
        j = client.get(f"/api/jobs/{j['id']}").json()
        if j["state"] not in ("running", "queued"):
            break
        time.sleep(0.1)
    return j


def test_a_folder_keeps_its_measures(folder):
    """FL1: a measures.json beside the recordings is used when no measures are given; the folder's info says so."""
    info = client.get("/api/summary/folder", params={"path": str(folder)}).json()
    assert info["files"] == 3 and info["first"].endswith(".csv") and info["measures"] is None
    bad = client.post("/api/jobs", json={"kind": "summarizeFolder", "body": {"folder": str(folder)}})
    assert bad.status_code == 400 and "Runs matrix" in bad.json()["detail"]
    (folder / "measures.json").write_text(json.dumps({"measures": MEASURES[:1], "pattern": "kp_{kp}_wind_{wind}"}))
    info = client.get("/api/summary/folder", params={"path": str(folder)}).json()
    assert info["measures"] == MEASURES[:1] and info["pattern"] == "kp_{kp}_wind_{wind}" and info["files"] == 3
    j = _wait(client.post("/api/jobs", json={"kind": "summarizeFolder", "body": {"folder": str(folder)}}).json())
    assert j["state"] == "done" and j["result"]["columns"] == ["recording", "kp", "wind", "peak"]
    (folder / "measures.json").write_text("{not json")
    assert client.get("/api/summary/folder", params={"path": str(folder)}).status_code == 400
    assert client.get("/api/summary/folder", params={"path": str(folder / "nope")}).status_code == 404


def test_the_folder_example_tells_its_story():
    """FL1: examples/folder_of_flights with its measures.json - X8-A's vibration grows to its last flight, X8-B's
    battery drops on its last one."""
    ex = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "folder_of_flights")
    j = _wait(client.post("/api/jobs", json={"kind": "summarizeFolder", "body": {"folder": ex}}).json())
    assert j["state"] == "done", j
    cols, rows = j["result"]["columns"], j["result"]["rows"]
    assert cols == ["recording", "vehicle", "date", "vibration_max", "battery_min_V"] and len(rows) == 10
    a = [r[3] for r in rows if r[1] == "X8-A"]
    assert a == sorted(a) and a[0] < 20 < 60 < a[-1]
    b = [r[4] for r in rows if r[1] == "X8-B"]
    assert min(b) == b[-1] < 14 < min(b[:-1])
