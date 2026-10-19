"""T46: every open data file has a colour and a short tag; kept by id, patchable, restored."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import FILE_COLORS, store  # noqa: E402

client = TestClient(app)


def _csv(path, k=1.0):
    path.write_text("t,v\n" + "".join(f"{i},{i * k}\n" for i in range(5)))
    return str(path)


def _open(*paths):
    r = client.post("/api/files/open", json={"paths": list(paths)}).json()
    return [o["id"] for o in r["opened"]]


def _close_all():
    for rid in list(store.order):
        client.delete(f"/api/runs/{rid}")


def test_tags_and_colours_in_order_and_reused(tmp_path):
    _close_all()
    try:
        ids = _open(_csv(tmp_path / "a.csv"), _csv(tmp_path / "b.csv"), _csv(tmp_path / "c.csv"))
        runs = {r["id"]: r for r in client.get("/api/runs").json()}
        assert [runs[i]["tag"] for i in ids] == ["A", "B", "C"]
        assert [runs[i]["color"] for i in ids] == FILE_COLORS[:3]
        client.delete(f"/api/runs/{ids[0]}")                       # A closed: the next file gets A again
        new = _open(_csv(tmp_path / "d.csv"))[0]
        runs = {r["id"]: r for r in client.get("/api/runs").json()}
        assert runs[new]["tag"] == "A" and runs[new]["color"] == FILE_COLORS[0]
        assert runs[ids[1]]["tag"] == "B"                          # the others keep theirs
        client.post(f"/api/runs/{ids[1]}/reload")                  # a reload keeps the mark
        assert {r["id"]: r for r in client.get("/api/runs").json()}[ids[1]]["tag"] == "B"
    finally:
        _close_all()


def test_patch_and_restore(tmp_path):
    _close_all()
    try:
        p = _csv(tmp_path / "x.csv")
        rid = _open(p)[0]
        r = client.patch(f"/api/runs/{rid}", json={"tag": "  windy  run ", "color": "#123abc"}).json()
        assert r["tag"] == "wind" and r["color"] == "#123ABC"      # 4 characters at most
        r = client.patch(f"/api/runs/{rid}", json={"tag": "", "color": "red"}).json()
        assert r["tag"] == "wind" and r["color"] == "#123ABC"      # empty / invalid ignored
        client.delete(f"/api/runs/{rid}")
        out = client.post("/api/session/restore", json={"runs": [{"id": rid, "path": p, "name": "x.csv", "tag": "W", "color": "#00AA00"}]}).json()
        assert out["restored"][0]["tag"] == "W" and out["restored"][0]["color"] == "#00AA00"
    finally:
        _close_all()
