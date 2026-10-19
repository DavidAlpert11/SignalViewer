"""T39: arrays sent from Python by the client (signalviewer/push_client.py) to a running app."""
import os
import socket
import stat
import sys
import threading
import time

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app import push  # noqa: E402
from app.main import app  # noqa: E402
from app.store import LoadError, store  # noqa: E402
from signalviewer import push_client  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """The app on a real port, its push.json in a home of its own (like run.py does)."""
    import uvicorn
    home = tmp_path_factory.mktemp("home")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    while not srv.started:
        time.sleep(0.02)
    mp = pytest.MonkeyPatch()
    mp.setattr(push, "APP_DIR", str(home / ".signalviewer"))
    mp.setattr(push, "PUSH_FILE", str(home / ".signalviewer" / "push.json"))
    push.write_push_file(f"http://127.0.0.1:{port}")
    yield str(home)
    mp.undo()
    srv.should_exit = True
    th.join(5)


@pytest.fixture(autouse=True)
def _clean():
    yield
    for rid in list(store.order):
        store.remove(rid)


def test_push_file_is_private_and_holds_the_token(server):
    p = os.path.join(server, ".signalviewer", "push.json")
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(p).st_mode) == 0o600
    url, token = push_client._connection(server)
    assert token == push.TOKEN and url.startswith("http://127.0.0.1:")


def test_send_then_send_again_replaces_in_place(server):
    t = np.linspace(0, 10, 101)
    r1 = push_client.show(t, {"alt": t * 2, "v": np.sin(t)}, name="sim run", home=server)
    assert r1["new"] is True and len(r1["signals"]) == 2
    tt, y = store.signal(f"{r1['run']}/alt")
    assert np.allclose(tt, t) and np.allclose(y, t * 2)
    # a derived signal on it follows the next send (same run id, new data)
    d = client.post("/api/derived", json={"op": "affine", "sources": [f"{r1['run']}/alt"],
                                          "params": {"gain": 1, "bias": 1}}).json()
    r2 = push_client.show(t, {"alt": t * 3, "v": np.cos(t)}, name="sim run", home=server)
    assert r2["run"] == r1["run"] and r2["new"] is False
    assert np.allclose(store.signal(d["id"])[1], t * 3 + 1)
    ev = client.get("/api/push/events", params={"since": r1["seq"] - 1}).json()["events"]
    assert [(e["new"], e["plot"]) for e in ev] == [(True, True), (False, True)]


def test_forms_the_client_accepts(server):
    import pandas as pd
    t = np.array([0.0, 1, 2, 3])
    r = push_client.show(pd.DataFrame({"a": [1.0, 2, 3, 4]}, index=t), name="df", home=server)
    assert np.allclose(store.signal(f"{r['run']}/a")[0], t)
    r = push_client.show(t, [5.0, 6, 7, 8], name="one", plot=False, home=server)
    assert r["signals"] == [f"{r['run']}/y"]
    r = push_client.show(None, {"n": [1.0, 2, 3]}, name="no time", home=server)       # time = sample number
    assert np.allclose(store.signal(f"{r['run']}/n")[0], [0, 1, 2])
    r = push_client.show([2.0, 0, 1], {"x": [20.0, 0, 10]}, name="unsorted", home=server)
    tt, y = store.signal(f"{r['run']}/x")
    assert np.allclose(tt, [0, 1, 2]) and np.allclose(y, [0, 10, 20])                  # sorted by time


def test_mistakes_are_explained_before_and_after_sending(server, tmp_path):
    with pytest.raises(ValueError, match="3 values for 4 times"):
        push_client.show([0, 1, 2, 3], {"a": [1, 2, 3]}, home=server)
    with pytest.raises(RuntimeError, match="not running"):
        push_client.show([0, 1], [1, 2], home=str(tmp_path))                       # no push.json there


def test_wrong_token_and_bad_body_are_refused():
    assert client.post("/api/push", content=b"x").status_code == 403
    assert client.post("/api/push", content=b"x", headers={"X-SV-Token": "guess"}).status_code == 403
    r = client.post("/api/push", content=b"not an npz", headers={"X-SV-Token": push.TOKEN})
    assert r.status_code == 400 and "Not data from the Signal Viewer client" in r.json()["detail"]


def test_pushed_run_is_not_a_file(server):
    r = push_client.show([0.0, 1], {"a": [1.0, 2]}, name="sim", home=server)
    with pytest.raises(LoadError, match="sent from Python"):
        store.reload(r["run"])
    assert r["run"] in store.reload_all()["skipped"]
    assert store.poll_appends() == [] and r["run"] not in store.poll_errors


def test_save_client(tmp_path):
    r = client.post("/api/push/save-client", json={"path": str(tmp_path)}).json()
    assert r["path"].endswith("signalviewer_push.py")
    assert "def show(" in open(r["path"], encoding="utf-8").read()


def test_push_file_removed_only_by_its_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(push, "APP_DIR", str(tmp_path))
    monkeypatch.setattr(push, "PUSH_FILE", str(tmp_path / "push.json"))
    push.write_push_file("http://127.0.0.1:1")
    (tmp_path / "push.json").write_text('{"url": "x", "token": "another instance"}')
    push.remove_push_file()
    assert (tmp_path / "push.json").exists()                        # not ours: left alone
    push.write_push_file("http://127.0.0.1:1")
    push.remove_push_file()
    assert not (tmp_path / "push.json").exists()


# ---------------------------------------------------------------- T54: files opened from outside

def test_open_external_needs_the_token_and_becomes_an_open_event(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("t,x\n0,1\n1,2\n")
    assert client.post("/api/open-external", json={"paths": [str(f)]}).status_code == 403
    assert client.post("/api/open-external", json={"paths": [str(f)]},
                       headers={"X-SV-Token": "wrong"}).status_code == 403
    r = client.post("/api/open-external", json={"paths": [str(f), " "]}, headers={"X-SV-Token": push.TOKEN})
    assert r.status_code == 200 and r.json()["paths"] == [str(f)]
    assert not [e for e in push.events_since(0)["events"] if e.get("kind") == "open"]   # not before the page restored
    ev = push.events_since(r.json()["seq"], opens=True)["events"]      # not tied to `since`
    assert ev[-1]["kind"] == "open" and ev[-1]["paths"] == [str(f)] and ev[-1]["age"] < 5
    assert not [e for e in push.events_since(0, opens=True)["events"] if e.get("kind") == "open"]   # handed out once
    assert client.post("/api/open-external", json={"paths": []}, headers={"X-SV-Token": push.TOKEN}).status_code == 400


def test_a_second_start_hands_its_files_to_the_running_app(server, tmp_path):
    from app import instance
    called = []
    push.ON_OPEN.append(lambda: called.append(1))
    try:
        push.events_since(0, opens=True)                       # earlier tests' events taken
        assert instance.hand_over([str(tmp_path / "flight.bin")])
        ev = push.events_since(10**9, opens=True)["events"]
        assert ev and ev[-1]["kind"] == "open" and ev[-1]["paths"] == [str(tmp_path / "flight.bin")]
        assert called == [1]                                   # the window is brought forward
    finally:
        push.ON_OPEN.clear()


def test_no_running_app_means_no_hand_over(tmp_path, monkeypatch):
    from app import instance
    monkeypatch.setattr(push, "PUSH_FILE", str(tmp_path / "push.json"))
    assert not instance.hand_over(["x.csv"])                                  # no push.json
    (tmp_path / "push.json").write_text('{"url": "http://127.0.0.1:9", "token": "t"}')
    assert not instance.hand_over(["x.csv"], timeout=1)                       # a stale one: nobody answers
    (tmp_path / "push.json").write_text("{not json")
    assert not instance.hand_over(["x.csv"])


def test_start_lock_one_leader_and_stale_locks(tmp_path, monkeypatch):
    from app import instance
    monkeypatch.setattr(push, "PUSH_FILE", str(tmp_path / "home" / "push.json"))
    lock = tmp_path / "home" / instance.LOCK_NAME
    assert instance.wait_or_lead(["a"]) is False and lock.exists()          # the first start leads
    # a second start while the first is still starting: waits; nobody answers -> it leads after `wait`
    t0 = time.time()
    assert instance.wait_or_lead(["b"], wait=0.6, step=0.1) is False
    assert 0.5 < time.time() - t0 < 5
    instance.release_lock()
    assert not lock.exists()
    lock.write_text("")                                                       # left by a crashed start
    os.utime(lock, (time.time() - 100, time.time() - 100))
    t0 = time.time()
    assert instance.wait_or_lead(["c"], wait=5) is False and time.time() - t0 < 2
    instance.release_lock()
