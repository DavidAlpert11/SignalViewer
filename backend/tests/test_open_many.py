"""P4: several files opened at once, within a memory budget - results, names and the file list in the
order asked; one bad file does not stop the others; a file bigger than the budget is read alone."""
import os
import sys
import threading
import time

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.openmany import open_many  # noqa: E402
from app.store import store  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    yield
    for rid in list(store.order):
        store.remove(rid)


def _csv(path, k):
    t = np.arange(0, 5, 0.01)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("time,v\n" + "".join(f"{x:.2f},{k + np.sin(x):.4f}\n" for x in t)).encode())
    return str(path)


def test_files_run_side_by_side_and_come_back_in_order():
    live, peak = [0], [0]
    lock = threading.Lock()

    def slow(p, i):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        time.sleep(0.2)
        with lock:
            live[0] -= 1
        return p.upper()
    a = time.perf_counter()
    out = open_many(["a", "b", "c", "d"], slow, workers=4)
    assert [r for _p, r, _e in out] == ["A", "B", "C", "D"]
    assert peak[0] > 1 and time.perf_counter() - a < 0.6           # one after the other: 0.8 s


def test_a_file_bigger_than_the_budget_is_read_alone(tmp_path, monkeypatch):
    monkeypatch.setenv("SV_OPEN_BUDGET_MB", "0.01")                 # every file is "too big"
    paths = [_csv(tmp_path / f"r{k}.csv", k) for k in range(3)]
    live, peak = [0], [0]
    lock = threading.Lock()

    def one(p, i):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        time.sleep(0.05)
        with lock:
            live[0] -= 1
    open_many(paths, one, workers=3)
    assert peak[0] == 1


def test_cancelled_files_are_not_started():
    started = []
    out = open_many(["a", "b"], lambda p, i: started.append(p), cancelled=lambda: True, workers=1)
    assert started == [] and all(r is None and e is None for _p, r, e in out)


def test_open_route_order_names_and_a_bad_file(tmp_path):
    paths = [_csv(tmp_path / "one" / "log.csv", 1), str(tmp_path / "bad.csv"), _csv(tmp_path / "two" / "log.csv", 2),
             _csv(tmp_path / "c.csv", 3)]
    (tmp_path / "bad.csv").write_bytes(bytes(range(256)) * 20)       # binary: refused, the others open
    r = client.post("/api/files/open", json={"paths": paths}).json()
    names = [o["name"] for o in r["opened"]]
    assert names == ["one/log.csv", "two/log.csv", "c.csv"], names   # same name: by folder, from the start
    assert [e["path"] for e in r["errors"]] == [paths[1]]
    listed = [x["name"] for x in store.list() if x.get("format") != "derived"]
    assert listed == names                                           # the file list in the order asked
    tags = [o.get("tag") for o in r["opened"]]
    assert tags == sorted(tags)                                      # A, B, C follow the order


def test_open_job_reports_progress_to_the_end(tmp_path):
    paths = [_csv(tmp_path / f"j{k}.csv", k) for k in range(4)]
    j = client.post("/api/jobs", json={"kind": "open", "body": {"paths": paths}}).json()
    for _ in range(200):
        s = client.get(f"/api/jobs/{j['id']}").json()
        if s["state"] != "running":
            break
        time.sleep(0.02)
    assert s["state"] == "done" and s["progress"] == 1.0
    assert [o["name"] for o in s["result"]["opened"]] == [f"j{k}.csv" for k in range(4)]
