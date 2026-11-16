"""E1: Export recording… - a part of a recording as a new file that opens again with the same values."""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from svcore.subset import Column, SubsetError, build  # noqa: E402

client = TestClient(app)


@pytest.fixture
def run(tmp_path):
    t = np.arange(4000) / 400.0                         # 10 s at 400 Hz
    mode = (t >= 4).astype(int) + (t >= 7).astype(int)  # 0, 1, 2 - a state
    p = tmp_path / "rec.csv"
    with open(p, "w", encoding="utf-8") as f:
        f.write("Time,Speed,Mode\n")
        for ti, m in zip(t, mode):
            f.write(f"{ti:.4f},{3 * ti:.6f},{m}\n")
    r = client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]
    yield {s["name"]: s["id"] for s in r["signals"]}, r
    for rid in list(store.order):
        store.remove(rid)


def _reopen(path):
    r = client.post("/api/files/open", json={"paths": [path]}).json()
    assert not r["errors"], r["errors"]
    got = r["opened"][0]
    out = {}
    for s in got["signals"]:
        t, y = store.signal(s["id"])
        out[s["name"]] = (np.asarray(t), np.asarray(y))
    return out


@pytest.mark.parametrize("ext", [".csv", ".parquet", ".mat", ".h5"])
def test_round_trip_each_format(run, tmp_path, ext):
    ids, rec = run
    body = {"path": str(tmp_path / f"part{ext}"), "source": rec["path"], "t0": 2, "t1": 5, "rate": 50,
            "signals": [{"id": ids["Speed"], "label": "Speed", "unit": "m/s"}, {"id": ids["Mode"], "label": "Mode"}]}
    e = client.post("/api/export/recording", json=body)
    assert e.status_code == 200, e.text
    assert e.json()["rows"] == 151                      # 2..5 s at 50 Hz
    back = _reopen(e.json()["path"])
    speed = next(v for k, v in back.items() if k.startswith("Speed"))
    t, y = speed
    assert len(t) == 151 and t[0] == pytest.approx(2) and t[-1] == pytest.approx(5)
    assert np.allclose(y, 3 * t, atol=1e-3)            # linear: a straight line stays straight
    m = back["Mode"][1]
    assert set(np.unique(m)) <= {0.0, 1.0}             # held: never between two states
    side = json.loads(open(os.path.splitext(e.json()["path"])[0] + ".export.json", encoding="utf-8").read())
    assert side["rate"] == 50 and side["source"] == rec["path"] and side["signals"][0]["unit"] == "m/s"


def test_only_where_a_condition_holds(run, tmp_path):
    ids, _ = run
    e = client.post("/api/export/recording", json={"path": str(tmp_path / "w.csv"), "where": "Mode == 1", "margin": 0,
                                                   "signals": [{"id": ids["Speed"], "label": "Speed"}]}).json()
    lines = open(e["path"], encoding="utf-8-sig").read().splitlines()
    assert lines[0] == "Time,Speed,Segment"
    t = np.array([float(x.split(",")[0]) for x in lines[1:]])
    assert t.min() == pytest.approx(4, abs=0.01) and t.max() == pytest.approx(7, abs=0.01)
    bad = client.post("/api/export/recording", json={"path": str(tmp_path / "x.csv"), "where": "Nope > 1",
                                                     "signals": [{"id": ids["Speed"]}]})
    assert bad.status_code == 400 and "Nope" in bad.json()["detail"]


def test_as_recorded_keeps_the_samples_and_time_from_zero(run, tmp_path):
    ids, _ = run
    e = client.post("/api/export/recording", json={"path": str(tmp_path / "a.parquet"), "t0": 1, "t1": 2, "fromZero": True,
                                                   "signals": [{"id": ids["Speed"]}]}).json()
    assert e["rows"] == 401
    t, y = next(iter(_reopen(e["path"]).values()))
    assert t[0] == pytest.approx(0) and y[0] == pytest.approx(3.0)


def test_anti_alias_when_the_rate_goes_down():
    t = np.arange(0, 10, 0.0025)
    slow = np.sin(2 * np.pi * 0.5 * t)
    y = slow + np.sin(2 * np.pi * 97 * t)              # 97 Hz folds onto 3 Hz at 10 Hz without a filter
    for aa, worst in ((True, 0.01), (False, 0.5)):
        s = build([Column("a", t, y)], timing="rate", rate=10, antialias=aa)
        err = np.abs(s.cols["a"] - np.sin(2 * np.pi * 0.5 * s.t))[5:-5]
        assert (err.max() < worst) if aa else (err.max() > worst)


def test_mistakes_are_said():
    t = np.arange(10.0)
    with pytest.raises(SubsetError):
        build([], timing="rate", rate=10)
    with pytest.raises(SubsetError):
        build([Column("a", t, t)], timing="rate", rate=0)
    with pytest.raises(SubsetError, match="rows"):
        build([Column("a", t, t)], timing="rate", rate=1e9)
