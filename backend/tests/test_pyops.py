"""T31: the user's own Python operations run in a worker process, from the folder the user chose
only; errors, endless loops and crashes are reported and the app keeps working."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app import prefs, pyops  # noqa: E402
from app.main import app  # noqa: E402
from app.store import store  # noqa: E402

client = TestClient(app)

GOOD = '''import numpy as np, os, time

@operation(name="Times k", params={"k": 2.0})
def times(t, y, k=2.0):
    """y * k"""
    return y * k

@operation(name="A minus B", inputs=2)
def minus(t, a, b):
    return a - b

@operation
def half_rate(t, y):
    return t[::2], y[::2]

@operation(name="Divide by zero")
def broken(t, y):
    return y / 0 + [][1]

@operation(name="Forever")
def forever(t, y):
    while True:
        time.sleep(0.01)

@operation(name="Crash")
def crash(t, y):
    os._exit(3)

@operation(name="Wrong length")
def wrong(t, y):
    return y[:3]

def helper(x):           # not an operation: not listed
    return x
'''


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "APP_DIR", str(tmp_path / "home"))
    os.makedirs(prefs.APP_DIR)
    d = tmp_path / "ops"
    d.mkdir()
    (d / "mine.py").write_text(GOOD)
    (d / "bad_syntax.py").write_text("def oops(:\n")
    (d / "_private.py").write_text("raise SystemExit('never loaded')\n")
    r = client.post("/api/pyops/folder", json={"path": str(d)})
    assert r.status_code == 200
    yield d
    pyops.stop()
    for rid in list(store.order):
        store.remove(rid)


@pytest.fixture
def sig(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("t,a,b\n" + "".join(f"{i * 0.1:.1f},{i},{2 * i}\n" for i in range(50)))
    run = client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]
    return {s["name"]: s["id"] for s in run["signals"]}


def derive(op_id, sources, args=None):
    return client.post("/api/derived", json={"op": "py", "sources": sources,
                                             "params": {"op": op_id, "args": args or {}}})


def test_listing_shows_operations_and_the_broken_file(folder):
    r = client.get("/api/pyops").json()
    ids = {o["id"]: o for o in r["ops"]}
    assert r["folder"] == str(folder)
    assert ids["mine.py:times"]["params"] == {"k": 2.0} and ids["mine.py:times"]["doc"] == "y * k"
    assert ids["mine.py:minus"]["inputs"] == 2
    assert ids["mine.py:half_rate"]["name"] == "Half rate"                   # bare @operation
    assert "mine.py:helper" not in ids                                       # not marked
    assert [e["file"] for e in r["errors"]] == ["bad_syntax.py"]             # _private.py never loaded
    assert "SyntaxError" in r["errors"][0]["error"] and "line 1" in r["errors"][0]["error"]


def test_runs_with_parameters_and_two_aligned_inputs(folder, sig):
    r = derive("mine.py:times", [sig["a"]], {"k": "3"})                      # the UI sends text: coerced
    assert r.status_code == 200, r.text
    t, y = store.signal(r.json()["id"])
    assert np.allclose(y, np.arange(50) * 3)
    t, y = store.signal(derive("mine.py:minus", [sig["b"], sig["a"]]).json()["id"])
    assert np.allclose(y, np.arange(50))
    t, y = store.signal(derive("mine.py:half_rate", [sig["a"]]).json()["id"])
    assert len(t) == 25                                                      # a new time base


def test_error_names_the_line_in_the_users_file(folder, sig):
    r = derive("mine.py:broken", [sig["a"]])
    assert r.status_code == 400
    assert "IndexError" in r.json()["detail"] and "mine.py line 18" in r.json()["detail"]   # the raising line of GOOD


def test_wrong_output_is_explained(folder, sig):
    r = derive("mine.py:wrong", [sig["a"]])
    assert r.status_code == 400 and "returned 3 values for 50 times" in r.json()["detail"]


def test_endless_loop_is_stopped_and_the_next_run_works(folder, sig, monkeypatch):
    monkeypatch.setattr(pyops, "TIMEOUT", 1.5)
    r = derive("mine.py:forever", [sig["a"]])
    assert r.status_code == 400 and "took longer than 1.5 s and was stopped" in r.json()["detail"]
    assert derive("mine.py:times", [sig["a"]]).status_code == 200


def test_a_crash_is_reported_and_the_next_run_works(folder, sig):
    r = derive("mine.py:crash", [sig["a"]])
    assert r.status_code == 400 and "crashed the worker process (exit code 3)" in r.json()["detail"]
    assert derive("mine.py:times", [sig["a"]]).status_code == 200


def test_an_operation_that_is_not_in_the_folder_says_so(folder, sig):
    """A session from another computer names an operation this folder does not have: nothing runs."""
    r = derive("theirs.py:secret", [sig["a"]])
    assert r.status_code == 400 and "not in your operations folder" in r.json()["detail"]


def test_reload_reads_edited_files(folder, sig):
    (folder / "mine.py").write_text(GOOD.replace("return y * k", "return y * k + 100"))
    client.post("/api/pyops/reload")
    t, y = store.signal(derive("mine.py:times", [sig["a"]], {"k": 1}).json()["id"])
    assert y[0] == 100


def test_example_file_works(folder, sig):
    r = client.post("/api/pyops/example").json()
    assert os.path.isfile(r["example"])
    ids = {o["id"] for o in r["ops"]}
    assert {"example_operations.py:despike", "example_operations.py:scaled_difference",
            "example_operations.py:resample"} <= ids
    assert derive("example_operations.py:resample", [sig["a"]], {"rate_hz": 5}).status_code == 200


def test_folder_must_exist_and_default_comes_back(folder, tmp_path):
    assert client.post("/api/pyops/folder", json={"path": str(tmp_path / "nope")}).status_code == 400
    r = client.post("/api/pyops/folder", json={"path": None}).json()
    assert r["default"] is True and r["folder"] == pyops.DEFAULT_DIR
