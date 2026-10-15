"""T10b: the same segment (value + occurrence of a state signal) in every run, and comparing
runs over "time since the segment started":  python -m pytest backend/tests/test_segments_across.py"""
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import store  # noqa: E402

client = TestClient(app)


@pytest.fixture()
def runs(tmp_path):
    """Three runs: Mode goes 0 -> 2 -> 0 -> 2 at different times in each; inside every Mode-2
    stretch Speed ramps up from 0 at 1 / s (run c: 1.1 / s), so aligned on the start of the
    segment the runs nearly match although they happen at different times."""
    ids = []
    for name, starts, slope in (("a", (2.0, 10.0), 1.0), ("b", (5.0, 14.0), 1.0), ("c", (3.0, 20.0), 1.1)):
        t = np.round(np.arange(0, 30, 0.01), 2)
        mode = np.zeros_like(t)
        speed = np.zeros_like(t)
        for s0 in starts:
            m = (t >= s0) & (t < s0 + 4)
            mode[m] = 2
            speed[m] = slope * (t[m] - s0)
        p = tmp_path / f"{name}.csv"
        np.savetxt(p, np.column_stack([t, mode, speed]), delimiter=",", header="Time,Mode,Speed", comments="", fmt="%.6g")
        ids.append(client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]["id"])
    yield ids
    for rid in ids:
        store.remove(rid)


def test_segment_found_in_every_run(runs):
    w = client.post("/api/segments/across", json={"runs": runs, "state": "Mode", "value": 2, "occurrence": 2}).json()["windows"]
    assert [round(x["t0"], 2) for x in w] == [10.0, 14.0, 20.0]
    assert all(abs(x["t1"] - x["t0"] - 4.0) < 0.02 and x["count"] == 2 for x in w)
    last = client.post("/api/segments/across", json={"runs": runs, "state": "Mode", "value": 2, "occurrence": -1}).json()["windows"]
    assert [x["t0"] for x in last] == [x["t0"] for x in w]
    none = client.post("/api/segments/across", json={"runs": runs, "state": "Mode", "value": 2, "occurrence": 3}).json()["windows"]
    assert all(x.get("missing") == "segment" for x in none)
    nosig = client.post("/api/segments/across", json={"runs": runs, "state": "Gear", "value": 2}).json()["windows"]
    assert all(x.get("missing") == "signal" for x in nosig)
    assert client.post("/api/segments/across", json={"runs": runs, "state": "Mode", "value": 2, "occurrence": 0}).status_code == 400


def test_compare_over_the_segment(runs):
    w = client.post("/api/segments/across", json={"runs": runs, "state": "Mode", "value": 2, "occurrence": 1}).json()["windows"]
    windows = {x["run"]: [x["t0"], x["t1"]] for x in w}
    a, b, c = runs
    # over the whole runs the segments do not line up in time: Speed differs a lot
    whole = client.post("/api/compare", json={"signals": [f"{a}/Speed", f"{b}/Speed"], "baseline": f"{a}/Speed"}).json()
    seg = client.post("/api/compare", json={"signals": [f"{a}/Speed", f"{b}/Speed", f"{c}/Speed"],
                                            "baseline": f"{a}/Speed", "windows": windows}).json()
    assert whole["rows"][0]["rmsDiff"] > 0.5
    rb, rc = seg["rows"]
    assert rb["rmsDiff"] < 0.02 and rc["rmsDiff"] > 0.05                 # b is the same flight, c ramps 10 % faster
    assert seg["overlap"][0] == pytest.approx(0.0, abs=0.02)              # time since the segment started
    table = client.post("/api/compare/all", json={"runs": runs, "baselineRun": a, "windows": windows}).json()["signals"]
    speed = next(x for x in table if x["name"] == "Speed")
    assert {f["run"] for f in speed["files"]} == set(runs)
    fa = next(f for f in speed["files"] if f["run"] == a)
    assert fa["max"] == pytest.approx(3.99, abs=0.02)                     # stats over the segment only
