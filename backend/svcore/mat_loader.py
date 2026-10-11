"""
MATLAB .mat loader (v4/v5/v7 via scipy, v7.3 via HDF5/h5py).

MAT files have no fixed layout, so the loader:
  1. flattens every numeric vector it can find (top-level variables, struct fields
     recursively as "parent.field", N x K matrices as "name[1]".."name[K]");
  2. picks the time vector: a variable named like time (t, time, Time, timestamp...)
     whose length is shared by the most other vectors; without one, the sample index;
  3. keeps every vector with the same length as the time vector as a signal.
Vectors of other lengths are reported as skipped (shown in the load report).
"""

import os
from typing import Dict, List, Optional, Tuple

import numpy as np

from svcore.models import Run, Signal

TIME_NAMES = ("time", "t", "timestamp", "time_s", "tout", "times")


def _is_numeric(a) -> bool:
    return isinstance(a, np.ndarray) and a.dtype.kind in "fiub" and a.size > 1


def _add_array(out: Dict[str, np.ndarray], name: str, a: np.ndarray):
    a = np.asarray(a)
    if a.dtype.kind == "b":
        a = a.astype(np.float64)
    if a.ndim == 1:
        out[name] = a
    elif a.ndim == 2 and 1 in a.shape:
        out[name] = a.reshape(-1)
    elif a.ndim == 2:
        # columns are channels if there are more rows than columns
        if a.shape[0] < a.shape[1]:
            a = a.T
        if a.shape[1] <= 64:
            for k in range(a.shape[1]):
                out[f"{name}[{k + 1}]"] = a[:, k]


def _walk_scipy(obj, prefix: str, out: Dict[str, np.ndarray], depth: int = 0):
    if depth > 6:
        return
    if isinstance(obj, np.ndarray) and obj.dtype.names:  # struct array
        if obj.size == 1:
            rec = obj.reshape(-1)[0]
            for f in obj.dtype.names:
                _walk_scipy(rec[f], f"{prefix}.{f}" if prefix else f, out, depth + 1)
        return
    if isinstance(obj, np.ndarray) and obj.dtype == object:
        if obj.size == 1:
            _walk_scipy(obj.reshape(-1)[0], prefix, out, depth + 1)
        return
    if hasattr(obj, "_fieldnames"):  # mat_struct (squeeze_me/struct_as_record=False)
        for f in obj._fieldnames:
            _walk_scipy(getattr(obj, f), f"{prefix}.{f}" if prefix else f, out, depth + 1)
        return
    if _is_numeric(obj):
        _add_array(out, prefix, obj)


def _read_scipy(path: str) -> Dict[str, np.ndarray]:
    from scipy.io import loadmat
    data = loadmat(path, squeeze_me=False, struct_as_record=True)
    out: Dict[str, np.ndarray] = {}
    for k, v in data.items():
        if not k.startswith("__"):
            _walk_scipy(v, k, out)
    return out


def _read_h5(path: str) -> Dict[str, np.ndarray]:
    import h5py
    out: Dict[str, np.ndarray] = {}

    def visit(name, node):
        if isinstance(node, h5py.Dataset) and node.dtype.kind in "fiub" and node.size > 1:
            if name.startswith("#refs#"):
                return
            # MATLAB stores arrays transposed in HDF5
            _add_array(out, name.replace("/", "."), np.asarray(node[()]).T)

    with h5py.File(path, "r") as f:
        f.visititems(visit)
    return out


def _is_hdf5(path: str) -> bool:
    try:
        import h5py
        return bool(h5py.is_hdf5(path))
    except Exception:
        return False


def read_mat_vectors(path: str) -> Dict[str, np.ndarray]:
    # v7.3 files are HDF5 containers: detect by content, not by scipy's error text
    if _is_hdf5(path):
        return _read_h5(path)
    return _read_scipy(path)


def choose_time(vectors: Dict[str, np.ndarray], wanted: Optional[str] = None) -> Tuple[Optional[str], int]:
    """Return (time variable name or None, signal length)."""
    lengths: Dict[int, int] = {}
    for a in vectors.values():
        lengths[len(a)] = lengths.get(len(a), 0) + 1
    if wanted and wanted in vectors:
        return wanted, len(vectors[wanted])
    candidates = []
    for name, a in vectors.items():
        leaf = name.split(".")[-1].lower()
        if leaf in TIME_NAMES and np.all(np.diff(a[:1000].astype(np.float64)) >= 0):
            candidates.append((lengths[len(a)], name))
    if candidates:
        candidates.sort(reverse=True)
        name = candidates[0][1]
        return name, len(vectors[name])
    best_len = max(lengths.items(), key=lambda kv: (kv[1], kv[0]))[0] if lengths else 0
    return None, best_len


def load_mat(path: str, display_name: str, time_variable: Optional[str] = None) -> Tuple[Optional[Run], List[str]]:
    """Returns (Run or None, list of skipped variable names)."""
    vectors = read_mat_vectors(path)
    if not vectors:
        return None, []
    tname, n = choose_time(vectors, time_variable)
    time = np.asarray(vectors[tname], dtype=np.float64) if tname else np.arange(n, dtype=np.float64)
    order = None
    if len(time) > 1 and np.any(np.diff(time) < 0):
        order = np.argsort(time, kind="stable")
        time = time[order]
    run = Run(file_path=path, csv_display_name=display_name, time=time)
    skipped = []
    for name, a in vectors.items():
        if name == tname:
            continue
        if len(a) != n:
            skipped.append(name)
            continue
        a = np.asarray(a, dtype=np.float64)
        if order is not None:
            a = a[order]
        run.signals[name] = Signal(name=name, data=a)
    run.import_settings = {"format": "mat", "time_column": tname}
    run.byte_offset = os.path.getsize(path)
    run.compute_metadata()
    return run, skipped
