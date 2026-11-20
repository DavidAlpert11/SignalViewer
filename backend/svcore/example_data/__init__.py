"""The examples' recordings, written by code (owner, 2026-11-18: no heavy example files in the packages).

Every recording of `examples/` that is made by one of the generators here is listed in GENERATED. The repository
keeps the files (tests, the docs and running from source use them as they are); the packages leave them out
(tools/make_pypi.py, SignalViewer.spec, tools/make_windows_portable.py) and the app writes them on first use
(app/routes/fs.py: /api/examples/{id}/prepare). The generators are deterministic: they write the recordings in git - the CSV files byte for byte, the binary
ones (.bin, .parquet, .mat) with the same signals and values (another system's math library can differ in the last
bit, so their bytes can) - backend/tests/test_example_data.py checks it.
`tools/make_*.py` run the same modules from the command line.
"""
import contextlib
import importlib.util
import io
import os
from typing import Callable, Dict, List, Sequence, Tuple

# the repository's examples folder: the default of the command-line tools (meaningless inside a package)
REPO_EXAMPLES = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "examples"))


def _csv_examples(root: str) -> None:
    from . import make_demo_data
    make_demo_data.csv_examples(root)


def _copter(root: str) -> None:
    from . import make_example_bin
    make_example_bin.main(os.path.join(root, "copter_flight.bin"))


def _bench(root: str) -> None:
    from . import make_bench_example
    make_bench_example.main(os.path.join(root, "bench"))


def _sim_vs_flight(root: str) -> None:
    from . import make_sim_vs_flight
    make_sim_vs_flight.main(os.path.join(root, "sim_vs_flight"))


def _investigate(root: str) -> None:
    from . import make_investigation_demo
    make_investigation_demo.main(os.path.join(root, "investigate"))


def _folder(root: str) -> None:
    from . import make_folder_example
    make_folder_example.main(os.path.join(root, "folder_of_flights"))


def _local_frames(root: str) -> None:
    from . import make_local_objects_fixture
    make_local_objects_fixture.main(root)


def _three_objects(root: str) -> None:
    from . import make_objects_fixture
    make_objects_fixture.main(root)


def _report_demo(root: str) -> None:
    from . import make_report_demo
    make_report_demo.main(os.path.join(root, "report_demo"))


def _serial_link(root: str) -> None:
    from . import make_serial_link
    make_serial_link.main(os.path.join(root, "serial_link"))


def _gps_nmea(root: str) -> None:
    from . import make_gps_nmea
    make_gps_nmea.main(os.path.join(root, "gps_nmea"))


_FOLDER = [f"folder_of_flights/X8-{v}_2026-{d}.bin" for v, d in (
    ("A", "09-02"), ("A", "09-09"), ("A", "09-16"), ("A", "09-23"), ("A", "09-30"), ("A", "10-07"),
    ("B", "09-05"), ("B", "09-19"), ("B", "10-03"), ("B", "10-17"))]

# (the files it writes, relative to the examples folder; the Python packages it needs; the writer)
GENERATORS: List[Tuple[Sequence[str], Sequence[str], Callable[[str], None]]] = [
    (["uav_flight.csv", "uav_flight_windy.csv", "run_012.csv", "run_013.csv", "run_014.csv"], [], _csv_examples),
    (["copter_flight.bin"], [], _copter),
    (["bench/pump_run_07.parquet"], ["pandas", "pyarrow"], _bench),
    (["sim_vs_flight/sim_attitude_doublets.mat", "sim_vs_flight/flight_attitude_doublets.bin"], ["scipy"], _sim_vs_flight),
    (["investigate/heavy_payload.csv", "investigate/light_payload.csv"], [], _investigate),
    (_FOLDER, [], _folder),
    (["ardupilot_lanes.csv", "local_frames.csv"], [], _local_frames),
    (["three_objects.csv"], [], _three_objects),
    (["report_demo/mission_ref.csv", "report_demo/mission_gust.csv"], [], _report_demo),
    (["serial_link/link_tx_rx.csv", "serial_link/link_mixed.csv", "serial_link/link_columns.csv",
      "serial_link/link_tx.svmsg.json", "serial_link/link_rx.svmsg.json"], [], _serial_link),
    (["gps_nmea/receiver.nmea", "gps_nmea/receiver_uart.csv"], [], _gps_nmea),
]
GENERATED: Dict[str, int] = {f: i for i, (files, _, _) in enumerate(GENERATORS) for f in files}


def can_write(rel: str) -> bool:
    """Whether this file is made here and everything its generator needs is installed (signalviewer-lite has
    no pyarrow: no Parquet example there)."""
    i = GENERATED.get(rel.replace("\\", "/"))
    return i is not None and all(importlib.util.find_spec(m) is not None for m in GENERATORS[i][1])


def write(rels: Sequence[str], root: str) -> None:
    """Write these files (and their generators' other files) under `root`, each generator once."""
    for i in sorted({GENERATED[r.replace("\\", "/")] for r in rels}):
        with contextlib.redirect_stdout(io.StringIO()):            # the tools' progress lines: not the app's
            GENERATORS[i][2](root)


def ignore_generated(root: str, *patterns: str) -> Callable[[str, List[str]], List[str]]:
    """`shutil.copytree(root, ..., ignore=...)` for a package's copy of the examples folder: the generated files
    left out (and names matching `patterns`, as shutil.ignore_patterns)."""
    import shutil
    others = shutil.ignore_patterns(*patterns)

    def ignore(folder: str, names: List[str]) -> List[str]:
        rel = os.path.relpath(folder, root)
        made = [n for n in names if os.path.normpath(os.path.join(rel, n)).replace(os.sep, "/") in GENERATED]
        return sorted(set(made) | set(others(folder, names)))
    return ignore
