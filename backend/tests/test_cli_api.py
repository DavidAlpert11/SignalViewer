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


def test_signal_names_without_unit_and_suggestions(tmp_path, capsys):
    """F31: scripts write "ATT.Roll", the file has "ATT.Roll [deg]"."""
    rec = sv.load(os.path.join(EX, "copter_flight.bin"))
    t, y = rec.signal("ATT.Roll")
    t2, y2 = rec.signal("ATT.Roll [deg]")
    assert np.array_equal(y, y2) and len(t) > 100
    assert np.array_equal(rec.signal("att.roll")[1], y)               # any case
    df = rec.to_dataframe(["ATT.Roll", "ATT.Pitch"], t0=10, t1=20)
    assert list(df.columns) == ["Time", "ATT.Roll", "ATT.Pitch"]      # the names as written
    with pytest.raises(KeyError) as e:
        rec.signal("ATT.Rol")
    assert "Did you mean 'ATT.Roll [deg]'" in str(e.value) and not str(e.value).startswith("'")
    # the command line goes through the same names (its own --help example)
    out = tmp_path / "roll.csv"
    assert main(["export", os.path.join(EX, "copter_flight.bin"), "--signals", "ATT.Roll,ATT.Pitch",
                 "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8-sig").splitlines()[0] == "Time,ATT.Roll,ATT.Pitch"
    assert main(["export", os.path.join(EX, "copter_flight.bin"), "--signals", "ATT.Rol",
                 "--out", str(out)]) == 1
    assert "Did you mean 'ATT.Roll [deg]'" in capsys.readouterr().err


def test_resolve_signal_name_rules():
    from svcore.naming import resolve_signal_name, SignalNameError
    names = ["Speed [km/h]", "Speed", "Alt [m]", "Alt [ft]", "RPM"]
    assert resolve_signal_name(names, "Speed") == "Speed"                # exact wins
    assert resolve_signal_name(names, "rpm") == "RPM"
    assert resolve_signal_name(names, "Speed [km/h]") == "Speed [km/h]"
    with pytest.raises(SignalNameError, match="several signals.*Alt \\[ft\\].*Alt \\[m\\]"):
        resolve_signal_name(names, "Alt")                                # never a guess
    with pytest.raises(SignalNameError, match="No signal named 'zzz'"):
        resolve_signal_name(names, "zzz")


def test_pypi_readme_links_are_absolute():
    """F32: PyPI shows the README without the repository - pictures and links must be absolute."""
    import importlib.util
    path = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "make_pypi.py")
    spec = importlib.util.spec_from_file_location("make_pypi", path)
    mp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mp)
    with open(os.path.join(os.path.dirname(path), "..", "README.md"), encoding="utf-8") as f:
        out = mp.pypi_readme(f.read(), "1.2.3")
    import re
    assert not re.search(r'(src|href)="(?!https?:|#|mailto:|data:)', out)
    assert not re.search(r"\]\((?!https?:|#|mailto:)", out)
    assert "raw.githubusercontent.com/DavidAlpert11/SignalViewer/v1.2.3/docs/images/" in out
