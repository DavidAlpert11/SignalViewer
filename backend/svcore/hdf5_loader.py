"""HDF5 files (.h5 / .hdf5) - T27. (MATLAB v7.3 .mat files are HDF5 too: svcore/mat_loader.py.)

HDF5 is a container with no fixed layout, so this takes what most test and simulation tools write:
  * every numeric 1-D dataset is a signal named by its path ("sensors/imu/ax");
  * a 2-D dataset of up to MAX_COLS columns gives one signal per column ("pos[0]", "pos[1]"...);
  * a table (compound dataset: pandas / PyTables / h5py records) gives one signal per numeric field.
Time: each group's own time dataset (time / t / timestamp... - the names .mat uses too) applies to
the signals of that group with the same length; otherwise the file's main time; signals with no
time of their length are left out and listed. A file with no time at all uses the sample number."""
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from svcore.mat_loader import TIME_NAMES
from svcore.models import Run, Signal
from svcore.extras import missing

MAX_COLS = 16


class Hdf5Error(Exception):
    pass


def _is_time_name(name: str) -> bool:
    return name.split("/")[-1].split(".")[-1].lower() in TIME_NAMES


def _collect(f) -> Tuple[Dict[str, Dict[str, np.ndarray]], int]:
    """({group path: {signal path: 1-D float array}}, damaged objects); table fields count as their
    table's group. Walked object by object (not h5py's visititems, which stops at the first damaged
    object and raises RuntimeError): a damaged object is skipped and counted, the rest is read."""
    import h5py
    groups: Dict[str, Dict[str, np.ndarray]] = {}
    damaged = [0]

    def add(group: str, name: str, a: np.ndarray):
        if a.ndim == 1 and len(a) >= 2 and np.issubdtype(a.dtype, np.number):
            groups.setdefault(group, {})[name] = a.astype(np.float64, copy=False)
        elif a.dtype == np.bool_ and a.ndim == 1 and len(a) >= 2:
            groups.setdefault(group, {})[name] = a.astype(np.float64)

    def visit(name: str, node: Any):
        if not isinstance(node, h5py.Dataset) or node.shape is None:
            return
        group = name.rsplit("/", 1)[0] if "/" in name else ""
        dt = node.dtype
        try:
            if dt.names:                                    # a table: one signal per numeric field
                data = node[()]
                for fld in dt.names:
                    col = data[fld]
                    if col.ndim == 1:
                        add(name, f"{name}.{fld}", np.asarray(col))
            elif node.ndim == 1:
                add(group, name, np.asarray(node[()]))
            elif node.ndim == 2 and node.shape[1] <= MAX_COLS and node.shape[0] >= 2:
                data = np.asarray(node[()])
                for k in range(data.shape[1]):
                    add(group, f"{name}[{k}]", data[:, k])
        except (TypeError, ValueError):                      # an odd type (strings, references...): not a signal
            return
        except (OSError, RuntimeError, KeyError):            # damaged data
            damaged[0] += 1

    def walk(group: Any, prefix: str, depth: int = 0):
        if depth > 32:
            return
        try:
            keys = list(group.keys())
        except (OSError, RuntimeError, KeyError, ValueError):
            damaged[0] += 1
            return
        for k in keys:
            path = f"{prefix}/{k}" if prefix else k
            try:
                node = group[k]
            except (OSError, RuntimeError, KeyError, ValueError):
                damaged[0] += 1
                continue
            if isinstance(node, h5py.Group):
                walk(node, path, depth + 1)
            else:
                visit(path, node)

    walk(f, "")
    return groups, damaged[0]


def _time_of(arrays: Dict[str, np.ndarray]) -> Optional[str]:
    names = [n for n, a in arrays.items() if _is_time_name(n) and len(a) and np.all(np.diff(a) >= 0)]
    return max(names, key=lambda n: len(arrays[n])) if names else None


def _main_time(groups: Dict[str, Dict[str, np.ndarray]], all_arrays: Dict[str, np.ndarray]) -> Optional[str]:
    """The file's main time: the root group's own, else the time that fits the most signals
    (not the longest: a fast sensor's time would leave the slow signals without one)."""
    root = _time_of(groups.get("", {}))
    if root:
        return root
    lengths: Dict[int, int] = {}
    for a in all_arrays.values():
        lengths[len(a)] = lengths.get(len(a), 0) + 1
    names = [n for n, a in all_arrays.items() if _is_time_name(n) and len(a) and np.all(np.diff(a) >= 0)]
    return max(names, key=lambda n: (lengths[len(all_arrays[n])], len(all_arrays[n]))) if names else None


def load_hdf5(path: str, display_name: str) -> Tuple[Optional[Run], Dict[str, Any]]:
    try:
        import h5py
    except ImportError:
        raise Hdf5Error(missing("Reading HDF5 (.h5)", "hdf5")) from None
    try:
        with h5py.File(path, "r") as f:
            groups, damaged = _collect(f)
    except (OSError, RuntimeError, ValueError):
        raise Hdf5Error("This is not an HDF5 file, or it is damaged.") from None
    report: Dict[str, Any] = {}
    if damaged:
        report["damagedObjects"] = damaged
    if not groups:
        return None, report

    all_arrays = {n: a for g in groups.values() for n, a in g.items()}
    main = _main_time(groups, all_arrays)
    sigs: Dict[str, Signal] = {}
    left_out: List[str] = []
    no_time = main is None and not any(_time_of(g) for g in groups.values())
    for group, arrays in sorted(groups.items()):
        own = _time_of(arrays)
        for name, y in arrays.items():
            if name in (own, main) or (not no_time and _is_time_name(name)):
                continue
            if no_time:
                t = np.arange(len(y), dtype=np.float64)
            elif own is not None and len(arrays[own]) == len(y):
                t = arrays[own]
            elif main is not None and len(all_arrays[main]) == len(y):
                t = all_arrays[main]
            else:
                left_out.append(f"{name} ({len(y)} values, no time of that length)")
                continue
            sigs[name] = Signal(name=name, data=y, time=t)
    if no_time:
        report["noTime"] = True
    if left_out:
        report["skipped"] = left_out
    if not sigs:
        return None, report
    longest = max(sigs.values(), key=lambda s: len(s.time))   # type: ignore[arg-type]
    run = Run(file_path=path, csv_display_name=display_name, time=longest.time)   # type: ignore[arg-type]
    run.signals = dict(sorted(sigs.items()))
    run.compute_metadata()
    times = [s.time for s in run.signals.values() if s.time is not None]
    run.start_time = float(min(t[0] for t in times))
    run.end_time = float(max(t[-1] for t in times))
    run.sample_count = int(max(len(t) for t in times))
    run.import_settings = {"format": "hdf5"}
    return run, report
