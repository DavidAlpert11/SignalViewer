"""MF09: clusters, PCA, MDS and SOM on data whose answer is known."""
import numpy as np
import pytest

from svcore.sweep import clusters as C


def _blobs(seed=0):
    rng = np.random.default_rng(seed)
    a = rng.normal([0, 0], 0.1, (30, 2)); b = rng.normal([5, 5], 0.1, (20, 2)); c = rng.normal([0, 5], 0.1, (10, 2))
    X = np.vstack([a, b, c])
    return {"x": X[:, 0], "y": X[:, 1]}, [0] * 30 + [1] * 20 + [2] * 10


@pytest.mark.parametrize("method", ["kmeans", "hierarchical"])
def test_three_blobs_are_three_clusters_largest_first(method):
    cols, truth = _blobs()
    r = C.analyse(cols, method, k=3)
    assert r["clusters"]["labels"] == truth          # cluster 0 = the largest blob, then by size
    assert r["clusters"]["sizes"] == [30, 20, 10]


def test_pca_of_a_line_has_one_component():
    t = np.linspace(-1, 1, 50)
    r = C.pca(C.standardise({"a": t, "b": 2 * t + 1, "c": -t})["X"], 2)
    assert r["explained"][0] == pytest.approx(1, abs=1e-9)
    # equal loadings in size: each column standardised; c opposite to a and b
    l0 = np.array(r["loadings"][0])
    assert np.abs(l0) == pytest.approx([1 / np.sqrt(3)] * 3)
    assert l0[0] * l0[2] < 0


def test_mds_of_points_in_a_plane_is_exact():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(40, 2))
    r = C.mds(X, 2)
    Y = np.array(r["coords"])
    d = lambda Z: np.sqrt(((Z[:, None] - Z[None]) ** 2).sum(-1))
    assert np.allclose(d(X), d(Y), atol=1e-8) and r["stress"] == pytest.approx(0, abs=1e-8)


def test_som_separates_two_blobs():
    cols, truth = _blobs()
    r = C.analyse({"x": cols["x"][:50], "y": cols["y"][:50]}, "som", som_size=(4, 4))["som"]
    node = np.array(r["node"])
    assert not set(node[:30]) & set(node[30:50])      # no node holds sets of both blobs
    assert sum(r["hits"]) == 50 and len(r["umatrix"]) == 16


def test_constant_and_missing():
    with pytest.raises(C.ClusterError):
        C.analyse({"a": [1, 1, 1]})
    r = C.analyse({"a": [0, 0, 10, 10, float("nan")], "b": [1, 1, 1, 1, 1]}, "kmeans", 2)
    assert r["columns"] == ["a"] and r["n"] == 5
    with pytest.raises(C.ClusterError):
        C.analyse({"a": [0, 1, 2]}, "nope")


def test_route(tmp_path):
    import pandas as pd
    from fastapi.testclient import TestClient
    from app.main import app
    rows = [{"a": a, "b": b, "out": (5 if a > 0.5 else 0) + 0.01 * b} for a in np.linspace(0, 1, 6) for b in np.linspace(0, 1, 6)]
    path = tmp_path / "t.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    c = TestClient(app, base_url="http://127.0.0.1")
    tid = c.post("/api/sweep/open", json={"path": str(path)}).json()["id"]
    q = {"roles": {"a": "param", "b": "param", "out": "output"}, "goal": {"column": "out", "direction": "max"}}
    r = c.post("/api/sweep/clusters", json={"id": tid, "question": q, "columns": ["out"], "k": 2}).json()
    assert r["clusters"]["sizes"] == [18, 18] and len(r["sets"]) == 36 and len(r["pca"]["coords"]) == 36
    r = c.post("/api/sweep/clusters", json={"id": tid, "question": q, "columns": ["a", "out"], "method": "mds", "sets": list(range(10))}).json()
    assert len(r["mds"]["coords"]) == 10
    assert c.post("/api/sweep/clusters", json={"id": tid, "question": q, "columns": ["zz"]}).status_code == 400
