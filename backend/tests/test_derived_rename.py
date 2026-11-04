"""A derived signal renamed in place (owner, 2026-11-03: a signal made in Create signals can be
deleted and renamed from the signal list): its place in the list kept, the signals made from it
follow - their sources and the {name} in a formula's text."""
import numpy as np

from test_backend import _open, client


def _names():
    runs = client.get("/api/runs").json()
    d = next((r for r in runs if r["format"] == "derived"), None)
    return [s["name"] for s in d["signals"]] if d else []


def test_rename_keeps_place_and_dependents(tmp_path):
    t = np.arange(0, 5, 0.01)
    sigs, run = _open(tmp_path, "rn.csv", ["Time", "A"], [t, np.sin(t)])
    a = sigs["A"]["id"]
    first = client.post("/api/derived", json={"op": "expr", "sources": [a], "params": {"expr": "2*v0", "text": "2*A"}, "name": "twice"}).json()
    dep = client.post("/api/derived", json={"op": "expr", "sources": [first["id"]], "params": {"expr": "v0+1", "text": "{twice}+1"}, "name": "plus"}).json()
    r = client.post("/api/derived/rename", json={"old": "twice", "new": "doubled"})
    assert r.status_code == 200 and r.json()["id"] == "derived/doubled"
    names = _names()                                                # (other tests' signals may be listed too)
    assert "twice" not in names and names.index("doubled") == names.index("plus") - 1   # the same place
    sig = next(s for x in r.json()["runs"] if x["format"] == "derived" for s in x["signals"] if s["name"] == "plus")
    assert sig["sources"] == ["derived/doubled"]
    assert sig["params"]["text"] == "{doubled}+1"
    # the dependent still computes (its source is found under the new name)
    st = client.post("/api/stats", json={"signals": [dep["id"]]}).json()["stats"][dep["id"]]
    assert abs(st["max"] - (2 * np.sin(t).max() + 1)) < 1e-9
    # a name in use, an empty one, a missing signal: said, nothing changed
    assert client.post("/api/derived/rename", json={"old": "doubled", "new": "plus"}).status_code == 400
    assert client.post("/api/derived/rename", json={"old": "doubled", "new": "  "}).status_code == 400
    assert client.post("/api/derived/rename", json={"old": "nope", "new": "x"}).status_code == 404
    assert "doubled" in _names() and "plus" in _names()
    for n in ("plus", "doubled"):
        client.delete(f"/api/derived/{n}")
    client.delete(f"/api/runs/{run['id']}")
