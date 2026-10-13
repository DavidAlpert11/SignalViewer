"""T11a: Python API and command line (no server)."""
import json
import os

import numpy as np
import pytest

import signalviewer as sv
from signalviewer.cli import main

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


def test_load_signal_and_dataframe():
    rec = sv.load(os.path.join(EX, "run_012.csv"))
    assert "Speed [km/h]" in rec.signals
    t, y = rec.signal("Speed [km/h]")
    assert len(t) == len(y) == 6000
    df = rec.to_dataframe(["Speed [km/h]", "RPM"], t0=10, t1=20)
    assert list(df.columns) == ["Time", "Speed [km/h]", "RPM"]
    assert df["Time"].iloc[0] >= 10 and df["Time"].iloc[-1] <= 20
    with pytest.raises(KeyError, match="No signal named"):
        rec.signal("nope")


def test_cli_info_json_is_clean(capsys):
    assert main(["info", os.path.join(EX, "uav_flight.csv"), "--json"]) == 0
    out = capsys.readouterr().out
    d = json.loads(out)                                  # nothing else on stdout
    assert d["name"] == "uav_flight.csv" and len(d["signals"]) == 9


def test_cli_export_csv_and_mat(tmp_path, capsys):
    from scipy.io import loadmat
    csv = tmp_path / "a.csv"
    assert main(["export", os.path.join(EX, "run_012.csv"), "--signals", "RPM,Gear", "--t0", "1", "--t1", "2", "--out", str(csv)]) == 0
    lines = csv.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0] == "Time,RPM,Gear" and len(lines) == 1 + 101
    mat = tmp_path / "a.mat"
    assert main(["export", os.path.join(EX, "run_012.csv"), "--out", str(mat)]) == 0
    m = loadmat(str(mat))
    assert "Speed_km_h" in m and "EngineTemp_C" in m and m["Time"].size == 6000   # valid MATLAB names
    assert np.allclose(m["RPM"].ravel()[:3], sv.load(os.path.join(EX, "run_012.csv")).signal("RPM")[1][:3])


def test_cli_errors_exit_1(tmp_path, capsys):
    assert main(["info", str(tmp_path / "missing.csv")]) == 1
    assert "not found" in capsys.readouterr().err.lower()
    assert main(["export", os.path.join(EX, "run_012.csv"), "--out", str(tmp_path / "x.txt")]) == 1
