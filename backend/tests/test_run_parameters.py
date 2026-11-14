"""F3: the parameters of a run for every format (one source) and two runs compared."""
import os
import subprocess
import sys

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store
from svcore import runinfo

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    for rid in list(store.order):
        store.remove(rid)
    yield
    for rid in list(store.order):
        store.remove(rid)


def open_(path) -> str:
    return store.open_file(str(path)).id


def test_two_csv_runs_differ_in_constants_and_name_numbers(tmp_path):
    a = tmp_path / "bench_mass2.4_run_1.csv"
    b = tmp_path / "bench_mass2.4_run_2.csv"
    a.write_text("Time,Gain,Seed,Speed\n0,0.5,7,1\n1,0.5,7,3\n2,0.5,7,2\n")
    b.write_text("Time,Gain,Seed,Speed\n0,0.8,7,1\n1,0.8,7,4\n2,0.8,7,2\n")
    ra, rb = open_(a), open_(b)
    rows = client.get(f"/api/runs/{ra}/parameters").json()["params"]
    by = {r["name"]: r for r in rows}
    assert by["Gain"] == {"name": "Gain", "value": 0.5, "source": "constant"}
    assert by["mass"]["source"] == "name" and by["run"]["value"] == 1
    assert "Speed" not in by
    d = client.post("/api/runs/parameters/compare", json={"a": ra, "b": rb}).json()
    assert [(r["name"], r["a"], r["b"]) for r in d["differ"]] == [("Gain", 0.5, 0.8), ("run", 1, 2)]
    assert d["differ"][0]["delta"] == pytest.approx(0.3)
    assert d["same"] == 2 and d["onlyA"] == [] and d["onlyB"] == []      # mass, Seed


def test_two_mat_runs_differ_in_scalars_texts_and_struct_fields(tmp_path):
    from scipy.io import savemat
    t = np.linspace(0, 1, 11)
    for name, kp, mode, extra in (("a", 1.5, "hover", {}), ("b", 2.0, "hover", {"seed": 3})):
        savemat(tmp_path / f"sim_{name}.mat", {"t": t, "y": np.sin(t), "Kp": kp, "mode": mode,
                                               "cfg": {"mass": 1.2, "name": "quad"}, **extra})
    ra, rb = open_(tmp_path / "sim_a.mat"), open_(tmp_path / "sim_b.mat")
    by = {r["name"]: r for r in client.get(f"/api/runs/{ra}/parameters").json()["params"]}
    assert by["Kp"] == {"name": "Kp", "value": 1.5, "source": "file"}
    assert by["mode"]["value"] == "hover" and by["cfg.mass"]["value"] == 1.2 and by["cfg.name"]["value"] == "quad"
    assert "y" not in by and "t" not in by                                 # signals stay signals
    d = client.post("/api/runs/parameters/compare", json={"a": ra, "b": rb}).json()
    assert [(r["name"], r["a"], r["b"]) for r in d["differ"]] == [("Kp", 1.5, 2.0)]
    assert [r["name"] for r in d["onlyB"]] == ["seed"]
    # the numbers feed Runs x conditions (one source); texts do not
    ps = store.run_params([ra])[ra]
    assert ps["Kp"] == 1.5 and ps["cfg.mass"] == 1.2 and "mode" not in ps


def test_mat_v73_scalars_and_text(tmp_path):
    h5py = pytest.importorskip("h5py")
    p = tmp_path / "v73.mat"
    with h5py.File(p, "w") as f:                        # what MATLAB -v7.3 writes (arrays transposed)
        f["t"] = np.linspace(0, 1, 5).reshape(1, -1)
        f["y"] = np.arange(5.0).reshape(1, -1)
        f["Kd"] = np.array([[0.25]])
        f["Kd"].attrs["MATLAB_class"] = np.bytes_(b"double")
        f["mode"] = np.array([[ord(c)] for c in "loiter"], dtype=np.uint16)
        f["mode"].attrs["MATLAB_class"] = np.bytes_(b"char")
    by = {r["name"]: r["value"] for r in runinfo.parameters(store.get(open_(p)).run)}
    assert by["Kd"] == 0.25 and by["mode"] == "loiter"


def test_two_flight_logs_compared(tmp_path):
    """A 40 s log tunes INS_GYRO_FILTER in flight (every 10 s), a 5 s log does not: that is the difference."""
    tool = os.path.join(ROOT, "tools", "make_test_bin.py")
    for name, secs in (("long.bin", "40"), ("short.bin", "5")):
        subprocess.run([sys.executable, tool, str(tmp_path / name), "--seconds", secs, "--imu-hz", "50"],
                       check=True, cwd=ROOT, capture_output=True)
    ra, rb = open_(tmp_path / "long.bin"), open_(tmp_path / "short.bin")
    rows = client.get(f"/api/runs/{ra}/parameters").json()["params"]
    log_rows = [r for r in rows if r["source"] == "log"]
    assert len(log_rows) == len(store.get(ra).run._flightlog.param_first) > 3
    gyro = next(r for r in log_rows if r["name"] == "INS_GYRO_FILTER")
    assert gyro["value"] == 20 and gyro["last"] == 35 and len(gyro["changes"]) == 3 and gyro["default"] == 20
    d = client.post("/api/runs/parameters/compare", json={"a": ra, "b": rb}).json()
    logged = [r for r in d["differ"] if r["source"] == "log"]
    assert [(r["name"], r["aLast"], r["bLast"]) for r in logged] == [("INS_GYRO_FILTER", 35, 20)]
    assert d["same"] >= len(log_rows) - 1


def test_compare_marks_a_parameter_changed_during_one_run():
    a = [{"name": "ATC_RAT_RLL_P", "value": 0.135, "source": "log"}]
    b = [{"name": "ATC_RAT_RLL_P", "value": 0.135, "source": "log", "last": 0.15, "changes": [[12.0, 0.15]]}]
    d = runinfo.compare(a, b)
    assert d["differ"] == [{"name": "ATC_RAT_RLL_P", "a": 0.135, "b": 0.135, "source": "log",
                            "aLast": 0.135, "bLast": 0.15, "delta": 0.0}]
    # a float32 value read twice is the same value
    assert runinfo.compare([{"name": "X", "value": 0.15, "source": "log"}],
                           [{"name": "X", "value": float(np.float32(0.15)), "source": "log"}])["same"] == 1


def test_unknown_run_says_what_to_do():
    r = client.post("/api/runs/parameters/compare", json={"a": "nope", "b": "nope2"})
    assert r.status_code == 404 and "open it again" in r.json()["detail"]
