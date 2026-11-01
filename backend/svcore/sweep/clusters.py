"""MF09: the sets' shape - clusters, principal components, a 2-D map by distances, a self-organising map.

All on the chosen columns (parameters and / or results) of a group's sets, each column standardised
((x - mean) / sd; a constant column is dropped, a missing value is the column's mean). Written here with
numpy and scipy (BSD-3, already dependencies) - no new dependency; the self-organising map is the
published algorithm (Kohonen 1982) in a few lines rather than MiniSom, so nothing to licence-check.

- k-means: k-means++ starts, Lloyd iterations, the best of several starts by inertia.
- hierarchical: Ward linkage (scipy.cluster.hierarchy), cut into k.
- PCA: SVD of the standardised matrix: coordinates, explained variance shares, loadings.
- MDS: classical (Torgerson) scaling of the Euclidean distances - 2-D coordinates.
- SOM: a w x h grid of nodes, Gaussian neighbourhood shrinking over the epochs; each set's node and the
  U-matrix (each node's mean distance to its neighbours: high = a border between clusters).

Each cluster is meant to become a group (source "cluster") in the page.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

MAX_SETS = 20000


class ClusterError(ValueError):
    pass


def standardise(cols: Dict[str, Sequence[float]]) -> Dict[str, Any]:
    names, out = [], []
    for k, v in cols.items():
        a = np.asarray(v, dtype=float)
        ok = np.isfinite(a)
        if ok.sum() < 2:
            continue
        mu, sd = float(a[ok].mean()), float(a[ok].std())
        if sd <= 0:
            continue
        out.append(np.where(ok, (a - mu) / sd, 0.0))
        names.append(k)
    if not names:
        raise ClusterError("Choose at least one column that changes among these sets.")
    X = np.column_stack(out)
    if X.shape[0] < 2:
        raise ClusterError("Two sets or more are needed.")
    return {"X": X, "columns": names}


def kmeans(X: np.ndarray, k: int, seed: int = 0, starts: int = 8, iters: int = 100) -> Dict[str, Any]:
    n = X.shape[0]
    k = max(1, min(int(k), n))
    rng = np.random.default_rng(seed)
    best: Optional[Dict[str, Any]] = None
    for _ in range(max(1, starts)):
        c = [X[int(rng.integers(n))]]
        for _j in range(1, k):                                   # k-means++
            d2 = np.min(((X[:, None, :] - np.array(c)[None]) ** 2).sum(-1), axis=1)
            p = d2 / d2.sum() if d2.sum() > 0 else np.full(n, 1 / n)
            c.append(X[int(rng.choice(n, p=p))])
        C = np.array(c)
        lab = np.zeros(n, dtype=int)
        for it in range(iters):
            d = ((X[:, None, :] - C[None]) ** 2).sum(-1)
            new = d.argmin(axis=1)
            if it and np.array_equal(new, lab):
                break
            lab = new
            for j in range(k):
                if (lab == j).any():
                    C[j] = X[lab == j].mean(axis=0)
        inertia = float(((X - C[lab]) ** 2).sum())
        if best is None or inertia < best["inertia"]:
            best = {"labels": lab, "centres": C, "inertia": inertia}
    assert best is not None
    return _relabel(best["labels"], X)


def hierarchical(X: np.ndarray, k: int) -> Dict[str, Any]:
    from scipy.cluster.hierarchy import fcluster, linkage
    k = max(1, min(int(k), X.shape[0]))
    lab = fcluster(linkage(X, method="ward"), t=k, criterion="maxclust") - 1
    return _relabel(np.asarray(lab, dtype=int), X)


def _relabel(lab: np.ndarray, X: np.ndarray) -> Dict[str, Any]:
    """Cluster 0 = the largest (the same answer whatever the starts' order); sizes and inertia."""
    uniq, counts = np.unique(lab, return_counts=True)
    order = uniq[np.argsort(-counts, kind="stable")]
    m = {int(o): i for i, o in enumerate(order)}
    lab = np.array([m[int(x)] for x in lab])
    k = len(order)
    C = np.array([X[lab == j].mean(axis=0) for j in range(k)])
    return {"labels": lab.tolist(), "sizes": [int((lab == j).sum()) for j in range(k)],
            "inertia": float(((X - C[lab]) ** 2).sum()), "centres": C.tolist()}


def pca(X: np.ndarray, components: int = 2) -> Dict[str, Any]:
    Xc = X - X.mean(axis=0)
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    m = max(1, min(components, Vt.shape[0]))
    # sign: the largest loading of each component positive (one answer across platforms)
    for i in range(Vt.shape[0]):
        j = int(np.argmax(np.abs(Vt[i])))
        if Vt[i, j] < 0:
            Vt[i] *= -1
            U[:, i] *= -1
    var = S ** 2
    share = var / var.sum() if var.sum() > 0 else var
    return {"coords": (U[:, :m] * S[:m]).tolist(), "explained": share[:m].tolist(),
            "explainedAll": share.tolist(), "loadings": Vt[:m].tolist()}


def mds(X: np.ndarray, dims: int = 2) -> Dict[str, Any]:
    n = X.shape[0]
    if n > 3000:
        raise ClusterError("A map by distances takes 3000 sets at most; choose a smaller group.")
    sq = (X ** 2).sum(1)
    D2 = np.maximum(sq[:, None] + sq[None] - 2 * X @ X.T, 0)
    J = np.eye(n) - 1.0 / n
    B = -0.5 * J @ D2 @ J
    vals, vecs = np.linalg.eigh(B)
    idx = np.argsort(vals)[::-1][:dims]
    L = np.sqrt(np.maximum(vals[idx], 0))
    coords = vecs[:, idx] * L
    for i in range(coords.shape[1]):
        j = int(np.argmax(np.abs(coords[:, i])))
        if coords[j, i] < 0:
            coords[:, i] *= -1
    # stress: how well the 2-D distances keep the real ones (0 = exactly)
    d = np.sqrt(D2)
    sq2 = (coords ** 2).sum(1)
    e = np.sqrt(np.maximum(sq2[:, None] + sq2[None] - 2 * coords @ coords.T, 0))
    stress = float(np.sqrt(((d - e) ** 2).sum() / (d ** 2).sum())) if (d ** 2).sum() > 0 else 0.0
    return {"coords": coords.tolist(), "stress": stress}


def som(X: np.ndarray, w: int = 6, h: int = 6, epochs: int = 30, seed: int = 0) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    n, d = X.shape
    grid = np.array([[i, j] for j in range(h) for i in range(w)], dtype=float)
    # start on the plane of the first two principal components (fewer epochs needed than random)
    p = pca(X, 2)
    comp = np.array(p["loadings"] + [[0.0] * d] * (2 - len(p["loadings"])))
    sd = np.sqrt(np.maximum(np.array(p["explainedAll"][:2] + [0.0] * 2)[:2], 1e-9)) * np.sqrt(d)
    gx = (grid[:, 0] / max(1, w - 1) - 0.5) * 2
    gy = (grid[:, 1] / max(1, h - 1) - 0.5) * 2
    W = X.mean(axis=0) + gx[:, None] * sd[0] * comp[0] + gy[:, None] * sd[1] * comp[1]
    steps = max(1, epochs) * n
    s0, s1 = max(w, h) / 2.0, 0.5
    t = 0
    for _ in range(max(1, epochs)):
        for i in rng.permutation(n):
            frac = t / steps
            sigma = s0 * (s1 / s0) ** frac
            lr = 0.5 * (0.01 / 0.5) ** frac
            b = int(((W - X[i]) ** 2).sum(1).argmin())
            g = np.exp(-((grid - grid[b]) ** 2).sum(1) / (2 * sigma ** 2))
            W += lr * g[:, None] * (X[i] - W)
            t += 1
    node = ((X[:, None, :] - W[None]) ** 2).sum(-1).argmin(axis=1)
    umat = []
    for k in range(w * h):
        nb = [m for m in range(w * h) if abs(grid[m] - grid[k]).sum() == 1]
        umat.append(float(np.mean([np.linalg.norm(W[k] - W[m]) for m in nb])) if nb else 0.0)
    hits = np.bincount(node, minlength=w * h)
    qerr = float(np.mean(np.linalg.norm(X - W[node], axis=1)))
    return {"w": w, "h": h, "node": node.tolist(), "umatrix": umat, "hits": hits.tolist(), "qerror": qerr,
            "weights": W.tolist()}


def analyse(cols: Dict[str, Sequence[float]], method: str = "kmeans", k: int = 3, seed: int = 0,
            som_size: Sequence[int] = (6, 6)) -> Dict[str, Any]:
    """The whole answer for one request: clusters (kmeans / hierarchical) or a SOM, with PCA always
    (the plane to show them on) and MDS when asked."""
    s = standardise(cols)
    X = s["X"]
    if X.shape[0] > MAX_SETS:
        raise ClusterError(f"At most {MAX_SETS} sets; choose a smaller group.")
    out: Dict[str, Any] = {"columns": s["columns"], "n": int(X.shape[0]), "pca": pca(X, 2)}
    if method == "kmeans":
        out["clusters"] = kmeans(X, k, seed)
    elif method == "hierarchical":
        out["clusters"] = hierarchical(X, k)
    elif method == "som":
        w, h = (max(2, min(20, int(x))) for x in som_size[:2])
        r = som(X, w, h, seed=seed)
        out["som"] = r
    elif method == "mds":
        out["mds"] = mds(X, 2)
    else:
        raise ClusterError("The method is one of kmeans, hierarchical, som, mds.")
    return out
