"""T60: file formats added as Python files in the user's readers folder."""
import json
import os

import numpy as np
import pytest

import app.prefs as prefs
from app.store import LoadError, Store
from signalviewer.cli import main


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "APP_DIR", str(tmp_path))
    return tmp_path


def write(home, name, code):
    d = home / "readers"
    d.mkdir(exist_ok=True)
    (d / name).write_text(code, encoding="utf-8")


def test_example_reader_opens_kv_files(home, tmp_path, capsys):
    assert main(["readers", "--example"]) == 0
    p = tmp_path / "bench.kv"
    p.write_text("t=0.0 speed=1 mode=IDLE\nt=0.1 speed=2 mode=RUN\nt=0.2 speed=3 mode=RUN\n", encoding="utf-8")
    lr = Store().open_file(str(p))
    assert set(lr.run.signals) == {"speed", "mode"}
    assert np.allclose(lr.run.signals["speed"].data, [1, 2, 3]) and lr.run.end_time == pytest.approx(0.2)
    assert lr.run.signals["mode"].labels == {0: "IDLE", 1: "RUN"}
    assert lr.load_report["reader"] == "key=value lines"
    import signalviewer as sv                                   # the Python API and the CLI too
    assert sv.load(str(p)).signal("SPEED")[1][-1] == 3
    capsys.readouterr()
    assert main(["readers", "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["readers"][0]["extensions"] == [".kv"] and not info["errors"]


def test_own_times_unsorted_and_none(home, tmp_path):
    write(home, "r.py", '''
@reader(extensions="xyz", name="two clocks")
def read(path):
    if open(path).read().startswith("skip"):
        return None
    return {"time": [2.0, 0.0, 1.0], "signals": {"a": [20, 0, 10], "b": ([0, 5], [1.0, 2.0])}}
''')
    p = tmp_path / "f.xyz"
    p.write_text("data")
    run = Store().open_file(str(p)).run
    assert np.allclose(run.time, [0, 1, 2]) and np.allclose(run.signals["a"].data, [0, 10, 20])  # sorted together
    assert np.allclose(run.signals["b"].time, [0, 5]) and run.end_time == pytest.approx(5)          # its own time
    q = tmp_path / "g.xyz"
    q.write_text("skip")
    with pytest.raises(LoadError, match="found nothing"):
        Store().open_file(str(q))


def test_errors_name_the_line_and_other_files_still_load(home, tmp_path, capsys):
    write(home, "bad.py", "x = (\n")
    write(home, "boom.py", '''
@reader(extensions=[".boom"])
def read(path):
    return 1 / 0
''')
    p = tmp_path / "f.boom"
    p.write_text("x")
    with pytest.raises(LoadError, match=r"boom\.py, line 4: ZeroDivisionError"):
        Store().open_file(str(p))
    assert main(["readers"]) == 1                              # the broken file is listed with its reason
    out = capsys.readouterr().out
    assert "bad.py" in out and "read" in out


def test_builtin_types_unchanged_and_folder_reread(home, tmp_path):
    ex = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "run_012.csv")
    write(home, "csvmine.py", '''
@reader(extensions=[".csv"])
def read(path):
    return None                     # not mine: the built-in CSV reader takes it
''')
    assert "Speed [km/h]" in Store().open_file(ex).run.signals
    p = tmp_path / "f.new"
    p.write_text("1")
    with pytest.raises(LoadError, match="Unsupported"):
        Store().open_file(str(p))
    write(home, "new.py", '''
@reader(extensions=[".new"])
def read(path):
    return {"time": [0, 1], "signals": {"v": [1, 2]}}
''')
    assert "v" in Store().open_file(str(p)).run.signals          # no restart needed
