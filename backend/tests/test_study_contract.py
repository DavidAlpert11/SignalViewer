"""W0 contract: the study file (load / save / defaults, unknown keys kept, the schema) and the shape of the
six /api/sweeps/* responses. The JSON fixtures in tests/fixtures/sweeps/ are the shapes the panel (L5)
builds against; whatever the routes return now (a fixture, later the real engine) must have every key of
the fixture, with the same JSON type."""
import json
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from svcore import study as S

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
FIX = os.path.join(ROOT, "tests", "fixtures")
STUDY = os.path.join(FIX, "drones", "fixture.svstudy.json")
client = TestClient(app)


def _fixture(name):
    with open(os.path.join(FIX, "sweeps", name), encoding="utf-8") as f:
        return json.load(f)


def _kind(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "number"
    return type(v).__name__


def _same_shape(want, got, where="$"):
    """Every key of `want` is in `got` with the same JSON type (null in either = optional); lists by their first item."""
    if want is None or got is None:
        return
    assert _kind(want) == _kind(got), f"{where}: {_kind(want)} expected, {_kind(got)} returned"
    if isinstance(want, dict) and not all(k[:1].isupper() or k in ("wind", "mass", "filter_hz") for k in want):
        for k, v in want.items():
            assert k in got, f"{where}: key '{k}' missing"
            _same_shape(v, got[k], f"{where}.{k}")
    elif isinstance(want, list) and want and got:
        _same_shape(want[0], got[0], f"{where}[0]")


def test_study_loads_with_defaults_and_keeps_unknown_keys(tmp_path):
    s = S.load(STUDY)
    assert [t.id for t in s.tables] == ["A", "B", "C"]
    assert s.tables[2].rename == {"P_gain": "Kp", "I_gain": "Ki"}
    assert s.next.batch == 4 and s.next.mix["refine"] == 0.5          # given, and defaulted
    assert s.launcher.results.glob == "results/{{table}}/{{run_id}}*"
    assert s.table_files(s.tables[0])[0].endswith("drone_a.csv")
    d = json.load(open(STUDY, encoding="utf-8"))
    d["future_key"] = {"x": 1}
    d["next"]["future_inner"] = 7
    p = tmp_path / "x.svstudy.json"
    s2 = S.loads(json.dumps(d), str(p))
    S.save(s2)
    back = json.load(open(p, encoding="utf-8"))
    assert back["future_key"] == {"x": 1} and back["next"]["future_inner"] == 7
    assert S.to_dict(S.load(str(p))) == S.to_dict(s2)


def test_a_newer_study_says_update():
    with pytest.raises(ValueError, match="Update Signal Viewer"):
        S.loads('{"version": 2, "tables": []}')


def test_study_matches_its_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.load(open(os.path.join(ROOT, "docs", "dev", "study.schema.json"), encoding="utf-8"))
    jsonschema.validate(json.load(open(STUDY, encoding="utf-8")), schema)
    jsonschema.validate(S.to_dict(S.load(STUDY)), schema)          # what save writes, too


@pytest.mark.parametrize("method,url,fixture,body", [
    ("post", "/api/sweeps/common", "common.json", {"study_path": STUDY}),
    ("post", "/api/sweeps/next-runs", "next_runs.json", {"study_path": STUDY}),
    ("post", "/api/sweeps/launcher/submit", "launcher_submit.json", {"study_path": STUDY, "dry_run": True}),
    ("get", "/api/sweeps/launcher/status", "launcher_status.json", {"study_path": STUDY}),
    ("post", "/api/sweeps/demo/step", "demo_step.json", None),
    ("get", "/api/sweeps/demo/progress", "demo_progress.json", None),
])
def test_route_shapes(method, url, fixture, body):
    if body is None:                                              # the demo routes: the demo's own study
        demo = os.path.join(ROOT, "examples", "smart_sweep_demo", "demo.svstudy.json")
        if not os.path.isfile(demo):
            demo = STUDY
        body = {"study_path": demo} if method == "get" else {"study_path": demo, "action": "reset"}
    r = client.post(url, json=body) if method == "post" else client.get(url, params=body)
    if r.status_code == 409:                                      # e.g. no launcher configured in the fixture study
        pytest.skip(r.json().get("detail"))
    assert r.status_code == 200, r.text
    _same_shape(_fixture(fixture), r.json())
