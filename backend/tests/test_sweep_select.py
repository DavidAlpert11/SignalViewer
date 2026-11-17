"""What the brush of All runs selects is resolved on the whole table (svcore/sweep/select.py, 1.29) - never
on the runs drawn, which are a sample above the cap. The guard: with the cap forced tiny and with no cap,
every result (sets kept, runs exported, counts) is the same."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore import sweep  # noqa: E402
from svcore.sweep.encode import encode  # noqa: E402
from svcore.sweep.select import selection  # noqa: E402


def _big(n_sets=400, per=30, seed=1):
    rng = np.random.default_rng(seed)
    p = np.repeat(np.arange(n_sets) % 20, per).astype(float)
    k = np.repeat(np.arange(n_sets) // 20, per).astype(float)
    wind = np.tile(np.arange(per) % 6, n_sets).astype(float)
    terrain = np.tile(np.array(["flat", "hill", "urban", "sea", "ridge"])[np.arange(per) % 5], n_sets)
    out = p * 0.5 + k * 0.1 + wind * 0.3 + rng.normal(0, 1, n_sets * per)
    return pd.DataFrame({"p": p, "k": k, "wind": wind, "terrain": terrain, "out": out})


ROLES = {"p": "param", "k": "param", "wind": "hold", "terrain": "hold", "out": "output"}


def test_selection_is_every_run_the_filters_keep():
    df = _big()
    prep = sweep.prepare(df, {"roles": ROLES})
    f = {"out": {"kind": "ranges", "ranges": [[3, 6], [9, 9.5]]}, "terrain": {"kind": "labels", "labels": ["hill", "sea"]},
         "wind": {"kind": "values", "values": [1, 2]}}
    r = selection(prep, f)
    o = prep.df.out.to_numpy(np.float32).astype(float)
    want = (((o >= 3) & (o <= 6)) | ((o >= 9) & (o <= 9.5))) & prep.df.terrain.isin(["hill", "sea"]).to_numpy() & prep.df.wind.isin([1, 2]).to_numpy()
    assert r["runs"] == int(want.sum()) > 0
    assert r["sets"] == sorted(set(prep.set_id[want].tolist()))
    assert r["rows"] == prep.row_id[want].tolist()
    # the sets the page shows: only those, and a filter on a column the table lacks is ignored (as on the page)
    some = r["sets"][::2]
    r2 = selection(prep, {**f, "#group": {"kind": "values", "values": [0]}}, some)
    assert set(r2["sets"]) == set(some) and r2["runs"] < r["runs"]


def test_category_codes_come_from_the_whole_column():
    s = pd.Series(["b", "a", "c", "a", "d"])
    w = encode(s.iloc[[0, 2]], s)                       # a sample without "a" and "d"
    assert w["labels"] == ["a", "b", "c", "d"]
    codes = np.frombuffer(__import__("base64").b64decode(w["data"]), dtype=np.float32)
    assert codes.tolist() == [1, 2]
    n = pd.Series(["10", "9", "100"])                   # numbers kept as text: number order, as before
    assert encode(n)["labels"] == ["9", "10", "100"]


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _flows(c, tid, tmp_path, tag):
    """Every result a brush on run columns gives in All runs, as the page asks for it."""
    q = {"roles": ROLES, "goal": {"column": "out", "direction": "min"}, "conditions": [{"column": "out", "op": "<=", "value": 12}]}
    e = c.post("/api/sweep/evaluate", json={"id": tid, "question": q, "runs": True}).json()
    sel = {"filters": {"out": {"kind": "ranges", "ranges": [[2, 4]]}, "terrain": {"kind": "labels", "labels": ["urban"]}}}
    s = c.post("/api/sweep/select", json={"id": tid, "question": q, **sel}).json()
    # Keep: the question narrowed to the sets selected - the best set and the suggestions follow from it
    kept = s["sets"]
    path = tmp_path / f"shown_{tag}.csv"
    x = c.post("/api/sweep/export-rows", json={"id": tid, "question": q, "select": sel, "path": str(path)}).json()
    ex = c.post("/api/sweep/select", json={"id": tid, "question": q, **sel, "sets": kept[: len(kept) // 2]}).json()
    return {"drawn": e["runs"]["n"], "sampled": e["runs"]["sampled"], "kept": kept, "runs": s["runs"],
            "export": path.read_text(), "exportRows": x["rows"], "narrowed": ex}


def test_tiny_cap_and_no_cap_give_the_same_results(client, tmp_path, monkeypatch):
    from app.routes import sweep as route
    tid = route._register(_big(), "", "big", 0.0)["id"]
    monkeypatch.setattr(route, "RUNS_MAX", 300)
    tiny = _flows(client, tid, tmp_path, "tiny")
    monkeypatch.setattr(route, "RUNS_MAX", 10_000_000)
    full = _flows(client, tid, tmp_path, "full")
    assert tiny["sampled"] and tiny["drawn"] == 300 and not full["sampled"] and full["drawn"] == 12_000
    for k in ("kept", "runs", "export", "exportRows", "narrowed"):
        assert tiny[k] == full[k], k
    assert full["runs"] == full["exportRows"] > 300                        # more than were drawn with the tiny cap
    df = _big()
    want = df[(df.out.astype(np.float32) >= 2) & (df.out.astype(np.float32) <= 4) & (df.terrain == "urban")]
    assert full["exportRows"] == len(want)


def test_category_codes_are_the_same_whatever_the_cap(client, monkeypatch):
    from app.routes import sweep as route
    tid = route._register(_big(), "", "big", 0.0)["id"]
    q = {"roles": ROLES}
    labels = []
    for cap in (7, 10_000_000):
        monkeypatch.setattr(route, "RUNS_MAX", cap)
        e = client.post("/api/sweep/evaluate", json={"id": tid, "question": q, "runs": True}).json()
        labels.append(next(c for c in e["runs"]["columns"] if c["name"] == "terrain")["labels"])
    assert labels[0] == labels[1] == ["flat", "hill", "ridge", "sea", "urban"]


# ----------------------------------------------------------------------------- FT3: what is drawn above the cap
def _decode(col):
    return np.frombuffer(__import__("base64").b64decode(col["data"]), dtype=np.float32)


def test_runs_above_the_cap_are_a_sample_of_the_runs_kept(client):
    from app.routes import sweep as route
    tid = route._register(_big(), "", "big", 0.0)["id"]
    q = {"roles": ROLES}
    sel = {"filters": {"out": {"kind": "ranges", "ranges": [[2, 3]]}}}
    e = client.post("/api/sweep/evaluate", json={"id": tid, "question": q, "runs": True, "cap": 1000, "select": sel, "pinned": 7}).json()
    r = e["runs"]
    out = _decode(next(c for c in r["columns"] if c["name"] == "out"))
    sets = _decode(next(c for c in r["columns"] if c["name"] == "#set"))
    prep = sweep.prepare(_big(), q)
    kept = ((prep.df.out.astype(np.float32) >= 2) & (prep.df.out.astype(np.float32) <= 3)).to_numpy()
    assert r["sampled"] and r["total"] == 12_000 and r["kept"] == int(kept.sum())        # the count of the whole table
    inside = (out >= 2) & (out <= 3)
    assert int(inside.sum()) >= 900 - 30 and r["n"] <= 1000 + 30                          # 90 % of the cap kept lines, 10 % background
    assert (sets == 7).sum() == (prep.set_id == 7).sum()                                  # the open set: every run of it
    # a narrow filter: every run it keeps is drawn
    sel2 = {"filters": {"out": {"kind": "ranges", "ranges": [[2, 2.05]]}}}
    r2 = client.post("/api/sweep/evaluate", json={"id": tid, "question": q, "runs": True, "cap": 1000, "select": sel2}).json()["runs"]
    out2 = _decode(next(c for c in r2["columns"] if c["name"] == "out"))
    assert int(((out2 >= 2) & (out2 <= 2.05)).sum()) == r2["kept"] < 900
    # no cap: every run, as read
    r3 = client.post("/api/sweep/evaluate", json={"id": tid, "question": q, "runs": True, "cap": 0}).json()["runs"]
    assert not r3["sampled"] and r3["n"] == 12_000


def test_raw_above_the_cap_samples_the_rows_kept_and_keeps_the_picked_run(client):
    from app.routes import sweep as route
    df = _big()
    tid = route._register(df, "", "big", 0.0)["id"]
    f = {"terrain": {"kind": "labels", "labels": ["sea"]}}
    r = client.post("/api/sweep/raw", json={"id": tid, "question": {}, "cap": 3000, "select": {"filters": f}, "picked": 11}).json()
    assert r["sampled"] and r["total"] == 12_000 and r["kept"] == int((df.terrain == "sea").sum()) == 2400
    ter = next(c for c in r["columns"] if c["name"] == "terrain")
    codes = _decode(ter)
    assert int((codes == ter["labels"].index("sea")).sum()) == 2400                       # all of them fit: all drawn
    assert 11 in _decode(next(c for c in r["columns"] if c["name"] == "#row")).tolist()
    full = client.post("/api/sweep/raw", json={"id": tid, "question": {}}).json()       # the default cap: all 12,000
    assert not full["sampled"] and full["n"] == 12_000
    assert next(c for c in full["columns"] if c["name"] == "terrain")["labels"] == ter["labels"]


def test_html_page_of_a_table_carries_every_row_up_to_the_cap(client, tmp_path):
    """FT4: the exported page draws what the app would - every row up to the cap, a sample above it."""
    import json as js
    import re
    from app.routes import sweep as route
    tid = route._register(_big(), "", "big", 0.0)["id"]

    def rows_in(cap):
        p = tmp_path / f"t{cap}.html"
        body = {"id": tid, "path": str(p), "format": "html", "axes": ["p", "k", "out"], **({"cap": cap} if cap is not None else {})}
        assert client.post("/api/sweep/export-table", json=body).status_code == 200
        return js.loads(re.search(r"const D=(\{.*?\});\n", p.read_text(encoding="utf-8")).group(1))["n"]
    assert rows_in(None) == 12_000                       # the default cap (200,000): all of them
    assert rows_in(5000) == 5000
    assert rows_in(0) == 12_000                          # no limit
