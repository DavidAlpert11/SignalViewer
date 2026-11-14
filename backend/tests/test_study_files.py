"""C5: one study file - `.svstudy.json` with an optional `workspace` block (what only the Sweeps area needs).
Every example and its 1.27 copy reads and writes back unchanged; a workspace survives a save; files without
the new optional blocks (`start`, `workspace`) are written without them (older versions read them as before)."""
import json
import os

import pytest

from svcore import study as S

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STUDIES = [os.path.join(ROOT, "examples", "smart_sweep_demo", "demo.svstudy.json"),
           os.path.join(ROOT, "tests", "fixtures", "drones", "fixture.svstudy.json"),
           os.path.join(ROOT, "tests", "fixtures", "sweeps", "v1_27", "demo.svstudy.json"),
           os.path.join(ROOT, "tests", "fixtures", "sweeps", "v1_27", "fixture.svstudy.json")]


def _norm(d):
    """What load fills in by itself (defaults) is not a change: compare a file with its re-read self."""
    return json.loads(S.dumps(S.loads(json.dumps(d))))


@pytest.mark.parametrize("path", STUDIES, ids=lambda p: os.path.relpath(p, ROOT))
def test_every_study_file_round_trips(path, tmp_path):
    d = json.load(open(path, encoding="utf-8"))
    s = S.load(path)
    out = tmp_path / "x.svstudy.json"
    S.save(s, str(out))
    w = json.load(open(out, encoding="utf-8"))
    assert "start" not in w and "workspace" not in w
    assert w == _norm(d)
    _kept(d, w)                                    # every value the file said is written back as it was


def _kept(a, b, where="$"):
    if isinstance(a, dict):
        assert isinstance(b, dict), where
        for k, v in a.items():
            assert k in b, f"{where}.{k} lost"
            _kept(v, b[k], f"{where}.{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), where
        for i, (x, y) in enumerate(zip(a, b)):
            _kept(x, y, f"{where}[{i}]")
    else:
        assert a == b, f"{where}: {a!r} -> {b!r}"


def test_a_workspace_is_kept_and_validates(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    d = json.load(open(STUDIES[0], encoding="utf-8"))
    tuning = json.load(open(os.path.join(ROOT, "examples", "sweeps", "drone_tuning.svsweep"), encoding="utf-8"))
    d["workspace"] = {"version": 1, "sweeps": [tuning], "active": 0, "place": {"part": "table", "table": 0}}
    s = S.loads(json.dumps(d), str(tmp_path / "w.svstudy.json"))
    assert s.workspace and s.workspace["sweeps"][0]["question"] == tuning["question"]
    S.save(s)
    back = json.load(open(tmp_path / "w.svstudy.json", encoding="utf-8"))
    assert back["workspace"] == d["workspace"]
    schema = json.load(open(os.path.join(ROOT, "docs", "dev", "study.schema.json"), encoding="utf-8"))
    jsonschema.validate(back, schema)


def test_the_1_27_svsweep_is_kept_as_it_was():
    """The single-table file is the area's own (read by the UI); its 1.27 copy must stay readable as it is."""
    old = json.load(open(os.path.join(ROOT, "tests", "fixtures", "sweeps", "v1_27", "drone_tuning.svsweep"), encoding="utf-8"))
    assert old["kind"] == "signalviewer-sweep" and old["version"] == 1 and old["question"]["goals"]
