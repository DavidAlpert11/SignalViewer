"""PLAN 2026-11-16 §7b: the file dialog's New folder, Rename and Delete - only in the user's own folders, a file
deleted goes to the recycle bin (here the freedesktop trash under XDG_DATA_HOME), never deleted for good."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    (h / "data").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    monkeypatch.setenv("XDG_DATA_HOME", str(h / ".local" / "share"))
    # every platform checks the freedesktop bin here: on Windows the real Recycle Bin would be the CI machine's own
    from app import trash
    monkeypatch.setattr(trash, "to_trash", lambda p: trash._freedesktop(os.path.abspath(p)))
    return h


def test_the_mac_bin_keeps_both_of_one_name(home):
    from app import trash
    for text in ("one", "two"):
        (home / "data" / "x.csv").write_text(text)
        trash._mac(str(home / "data" / "x.csv"))
    assert (home / ".Trash" / "x.csv").read_text() == "one" and (home / ".Trash" / "x 2.csv").read_text() == "two"


def test_new_folder_rename_and_delete_to_the_bin(home):
    data = home / "data"
    r = client.post("/api/fs/mkdir", json={"parent": str(data), "name": "  run 7 "})
    assert r.status_code == 200 and os.path.isdir(r.json()["path"]) and r.json()["path"].endswith("run 7")
    assert client.post("/api/fs/mkdir", json={"parent": str(data), "name": "run 7"}).status_code == 409     # taken
    (data / "a.csv").write_text("t,v\n0,1\n")
    r = client.post("/api/fs/rename", json={"path": str(data / "a.csv"), "name": "b.csv"})
    assert r.status_code == 200 and (data / "b.csv").is_file() and not (data / "a.csv").exists()
    (data / "c.csv").write_text("x")
    assert client.post("/api/fs/rename", json={"path": str(data / "c.csv"), "name": "b.csv"}).status_code == 409
    r = client.post("/api/fs/delete", json={"path": str(data / "b.csv")})
    assert r.status_code == 200 and not (data / "b.csv").exists()
    trash = home / ".local" / "share" / "Trash"
    assert (trash / "files" / "b.csv").read_text() == "t,v\n0,1\n"                # in the bin, not gone
    info = (trash / "info" / "b.csv.trashinfo").read_text()
    assert "Path=" in info and "b.csv" in info and "DeletionDate=" in info
    (data / "b.csv").write_text("again")                                          # a second one of that name
    client.post("/api/fs/delete", json={"path": str(data / "b.csv")})
    assert (trash / "files" / "b 2.csv").read_text() == "again"
    r = client.post("/api/fs/delete", json={"path": str(data / "run 7")})        # a folder too
    assert r.status_code == 200 and (trash / "files" / "run 7").is_dir()


@pytest.mark.parametrize("name", ["", "..", "a/b", ".hidden"])
def test_names_said_plainly(home, name):
    r = client.post("/api/fs/mkdir", json={"parent": str(home / "data"), "name": name})
    assert r.status_code == 400 and ("name" in r.json()["detail"] or "hidden" in r.json()["detail"])


def test_only_in_the_users_own_folders(home, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "x.csv").write_text("x")
    r = client.post("/api/fs/delete", json={"path": str(outside / "x.csv")})
    assert r.status_code == 403 and "own folders" in r.json()["detail"] and (outside / "x.csv").exists()
    assert client.post("/api/fs/mkdir", json={"parent": str(outside), "name": "n"}).status_code == 403
    assert client.post("/api/fs/delete", json={"path": str(home)}).status_code == 403          # the home folder itself
    (home / ".signalviewer").mkdir()
    (home / ".signalviewer" / "settings.json").write_text("{}")
    r = client.post("/api/fs/delete", json={"path": str(home / ".signalviewer" / "settings.json")})
    assert r.status_code == 403 and "hidden" in r.json()["detail"]


def test_a_file_open_in_the_app_is_not_deleted(home):
    p = home / "data" / "run.csv"
    p.write_text("Time,V\n0,1\n0.1,2\n0.2,3\n")
    rid = client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]["id"]
    try:
        r = client.post("/api/fs/delete", json={"path": str(p)})
        assert r.status_code == 409 and "close it first" in r.json()["detail"] and p.exists()
        assert client.post("/api/fs/delete", json={"path": str(home / "data")}).status_code == 409   # nor its folder
    finally:
        client.delete(f"/api/runs/{rid}")
