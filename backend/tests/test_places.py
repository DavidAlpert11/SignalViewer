"""T24: the file dialog's places - favourite folders, recent folders, folders of the open files,
the usual folders and drives - and the count of files of other types in a listing."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

import app.prefs as prefs  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def appdir(tmp_path, monkeypatch):
    d = tmp_path / "app"
    d.mkdir()
    monkeypatch.setattr(prefs, "APP_DIR", str(d))
    return d


def test_favourites_pin_reorder_unpin(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    r = client.put("/api/fs/favourites", json={"paths": [str(a), str(b), str(a), "", str(tmp_path / "gone")]}).json()
    assert [x["path"] for x in r["favourites"]] == [str(a), str(b), str(tmp_path / "gone")]     # once each, in order
    assert [x["exists"] for x in r["favourites"]] == [True, True, False]
    client.put("/api/fs/favourites", json={"paths": [str(b), str(a)]})
    assert [x["path"] for x in client.get("/api/fs/places").json()["favourites"]] == [str(b), str(a)]   # kept (settings.json)
    client.put("/api/fs/favourites", json={"paths": [str(b)]})
    assert [x["path"] for x in client.get("/api/fs/places").json()["favourites"]] == [str(b)]


def test_recent_folders_newest_first_once_each(tmp_path):
    x, y = tmp_path / "x", tmp_path / "y"
    x.mkdir(); y.mkdir()
    for p in (x / "1.csv", y / "2.csv", x / "3.csv", y / "s.svsession"):
        prefs.add_recent(str(p), "session" if p.suffix == ".svsession" else "file")
    rec = client.get("/api/fs/places").json()["recent"]
    assert [r["path"] for r in rec] == [str(y), str(x)]
    assert all(r["exists"] for r in rec)


def test_places_has_home_and_open_files_folders(tmp_path):
    csv = tmp_path / "data" / "run.csv"
    csv.parent.mkdir()
    csv.write_text("t,v\n0,1\n1,2\n")
    opened = client.post("/api/files/open", json={"paths": [str(csv)]}).json()
    try:
        p = client.get("/api/fs/places").json()
        assert str(csv.parent) in p["open"]
    finally:
        for o in opened.get("opened", []):
            if o and o.get("id"):
                client.delete(f"/api/runs/{o['id']}")
    assert p["standard"][0]["id"] == "home"
    assert isinstance(p["drives"], list)


def test_listing_counts_other_files(tmp_path):
    (tmp_path / "a.csv").write_text("t,v\n0,1\n")
    (tmp_path / "notes.docx").write_text("x")
    (tmp_path / "pic.png").write_text("x")
    r = client.post("/api/fs/list", json={"path": str(tmp_path)}).json()
    assert r["hidden"] == 2 and [e["name"] for e in r["entries"] if not e["dir"]] == ["a.csv"]
