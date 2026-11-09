"""26.U7: the per-signal data-quality summary (svcore/quality.py, /api/runs/{id}/quality)."""
import os

import numpy as np
from fastapi.testclient import TestClient

from svcore.quality import run_quality, time_quality


def test_time_checks():
    t = np.concatenate([np.arange(0, 10, 0.01), np.arange(12, 20, 0.1)])      # a gap, then 100 Hz -> 10 Hz
    q = time_quality(t)
    assert round(q["rate"]) == 100 and q["gaps"] == 1 and abs(q["gapTime"] - 2.01) < 0.02 and q["firstGap"] > 9.9
    assert len(q["rateChanges"]) == 1 and round(q["rateChanges"][0]["to"]) == 10 and 11 < q["rateChanges"][0]["t"] < 14
    assert q["duplicates"] == 0 and q["backwards"] == 0
    j = np.arange(0, 10, 0.01) + np.random.default_rng(1).normal(0, 0.002, 1000)      # jitter is not a rate change
    assert time_quality(np.sort(j))["rateChanges"] == []
    d = np.array([0, 1, 1, 2, 1.5, 3, 4, 5.0])
    q = time_quality(d)
    assert q["duplicates"] == 1 and q["backwards"] == 1


def test_run_summary_checks_a_shared_time_once():
    t = np.arange(0, 5, 0.1)
    y = np.sin(t)
    m = y.copy(); m[3:7] = np.nan
    ev = np.array([0.0, 0.0, 3.0, 4.0])                          # events: repeated times and a pause are normal
    r = run_quality([("A", t, y, False), ("B", t, m, False), ("C", np.arange(0, 5, 0.5), np.ones(10), False),
                     ("Mode", ev, np.array([1.0, 2, 3, 4]), True)])
    rows = {x["name"]: x for x in r["signals"]}
    assert rows["A"]["issues"] == [] and rows["B"]["issues"] == ["missing"] and rows["B"]["missing"] == 4
    assert r["count"]["missing"] == 1 and r["withIssues"] == 1 and r["checked"] == 4
    assert rows["Mode"]["issues"] == [] and rows["Mode"]["event"] and rows["Mode"]["n"] == 4
    assert round(rows["C"]["rate"]) == 2


def test_route(tmp_path):
    from app.main import app
    p = tmp_path / "q.csv"
    rows = ["time,A,B"] + [f"{i / 100:.2f},{i},{'' if 20 <= i < 30 else i}" for i in range(300)] + ["2.99,1,1"]
    p.write_text("\n".join(rows) + "\n")
    c = TestClient(app, base_url="http://127.0.0.1")
    rid = c.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]["id"]
    try:
        q = c.get(f"/api/runs/{rid}/quality").json()
        b = next(x for x in q["signals"] if x["name"] == "B")
        assert b["missing"] == 10 and "missing" in b["issues"] and b["duplicates"] == 1
        assert q["count"]["duplicates"] == 2
        assert c.get(f"/api/runs/{rid}/quality").json() == q                      # kept
    finally:
        c.delete(f"/api/runs/{rid}")
