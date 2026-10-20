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
from svcore.time_pairs import clean_pair, find_time_pairs
from svcore.extras import missing

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


def _read_scipy(path: str) -> Tuple[Dict[str, np.ndarray], bool]:
    """(vectors, cut_off). A v5 file that ends in the middle (MATLAB stopped while saving, a
    half-copied file) keeps every variable that was complete before the cut (T33)."""
    from scipy.io import loadmat
    try:
        data = loadmat(path, squeeze_me=False, struct_as_record=True)
        cut = False
    except Exception:
        data = _read_v5_until_damage(path)
        if not data:
            raise
        cut = True
    out: Dict[str, np.ndarray] = {}
    for k, v in data.items():
        if not k.startswith("__"):
            _walk_scipy(v, k, out)
    return out, cut


def _read_v5_until_damage(path: str) -> Dict:
    """The variables of a MATLAB v5 file one by one, stopping at the first one that cannot be
    read. Empty when the file is not v5 or its header is damaged."""
    try:
        from scipy.io.matlab._mio5 import MatFile5Reader
    except ImportError:                # scipy moved its private module: no recovery, the caller reports
        return {}
    out: Dict = {}
    with open(path, "rb") as f:
        try:
            r = MatFile5Reader(f, squeeze_me=False, struct_as_record=True)
            r.initialize_read()
            r.read_file_header()
        except Exception:
            return {}
        while True:
            try:
                if r.end_of_stream():
                    break
                hdr, next_pos = r.read_var_header()
                name = hdr.name.decode("latin1") if isinstance(hdr.name, bytes) else str(hdr.name)
                value = r.read_var_array(hdr, True)
            except Exception:
                break                  # the damaged / missing part: keep what came before
            if name and not name.startswith("__"):
                out[name] = value
            f.seek(next_pos)
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


class MatNeedsExtra(Exception):
    """T59: a MATLAB v7.3 file (HDF5 inside) and h5py is not installed."""


def _is_hdf5(path: str) -> bool:
    try:
        import h5py
    except ImportError:
        with open(path, "rb") as f:
            if f.read(128).startswith(b"MATLAB 7.3"):
                raise MatNeedsExtra(missing("Reading MATLAB v7.3 files", "hdf5")) from None
        return False
    try:
        return bool(h5py.is_hdf5(path))
    except Exception:
        return False


def read_mat_vectors(path: str) -> Dict[str, np.ndarray]:
    return _read_mat(path)[0]


def _read_mat(path: str) -> Tuple[Dict[str, np.ndarray], bool]:
    # v7.3 files are HDF5 containers: detect by content, not by scipy's error text
    if _is_hdf5(path):
        return _read_h5(path), False
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
    vectors, cut = _read_mat(path)
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
    # variables with a time variable of their own, by name (Speed + Speed_time, msg.roll + msg.time...):
    # their own length, their own time (owner, 2026-10-19)
    pairs = {v: t for v, t in find_time_pairs(list(vectors), tname).items()
             if t != tname and len(vectors[v]) == len(vectors[t])}
    used_times = set(pairs.values())
    for name, a in vectors.items():
        if name == tname or name in used_times:
            continue
        if name in pairs:
            t, y = clean_pair(vectors[pairs[name]], np.asarray(a, dtype=np.float64))
            if len(t):
                run.signals[name] = Signal(name=name, data=y, time=t)
                continue
        if len(a) != n:
            skipped.append(name)
            continue
        a = np.asarray(a, dtype=np.float64)
        if order is not None:
            a = a[order]
        run.signals[name] = Signal(name=name, data=a)
    run.import_settings = {"format": "mat", "time_column": tname}
    if pairs:
        run.load_report = {"timePairs": sum(1 for v in pairs if v in run.signals)}
    run.byte_offset = os.path.getsize(path)
    run.compute_metadata()
    if cut:
        run.load_report = {**(getattr(run, "load_report", None) or {}), "cutOff": True}
    return run, skipped
