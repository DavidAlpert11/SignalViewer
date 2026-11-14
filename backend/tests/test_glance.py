"""D14: the *run at a glance* numbers of a profile / pinned by the user - by signal name, over the whole run."""
import json
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store
from svcore import templates as tplm
from svcore.windowstats import glance_value

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    yield
    for rid in list(store.order):
        store.remove(rid)


def test_values_equal_numpy_and_skip_nan():
    t = np.arange(0, 10, 0.5)
    y = np.sin(t) * 4
    y[0] = y[-1] = y[7] = np.nan
    f = np.isfinite(y)
    assert glance_value(t, y, "max") == {"value": float(np.nanmax(y)), "t": float(t[np.nanargmax(y)])}
    assert glance_value(t, y, "min")["value"] == float(np.nanmin(y))
    assert glance_value(t, y, "mean")["value"] == pytest.approx(float(y[f].mean()))     # the plain sample mean
    assert glance_value(t, y, "first") == {"value": float(y[1]), "t": 0.5}
    assert glance_value(t, y, "final") == {"value": float(y[-2]), "t": float(t[-2])}
    assert glance_value(t, y, "range")["value"] == pytest.approx(float(np.nanmax(y) - np.nanmin(y)))
    assert glance_value(t, np.full(5, np.nan), "max") is None
    with pytest.raises(ValueError):
        glance_value(t, y, "median")


def test_endpoint_matches_names_loosely_and_says_what_is_missing(tmp_path):
    p = tmp_path / "bench.csv"
    t = np.arange(0, 100, 0.1)
    temp = 20 + t * 0.5
    np.savetxt(p, np.column_stack([t, temp, (t > 50).astype(int)]), delimiter=",",
               header="Time,Engine.Temp [degC],Step", comments="", fmt="%.6g")
    rid = client.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]["id"]
    store.set_time_offset(rid, 5.0)
    items = [{"name": "Oil.Temp|Engine.Temp", "stat": "max"}, {"name": "Engine.Temp", "stat": "first"},
             {"name": "Nope", "stat": "max"}, {"name": "Step", "stat": "max"}]
    r = client.post(f"/api/runs/{rid}/glance", json={"items": items}).json()["items"]
    assert r[0]["sig"] == f"{rid}/Engine.Temp [degC]" and r[0]["unit"] == "degC"
    assert r[0]["value"] == pytest.approx(temp.max()) and r[0]["t"] == pytest.approx(t[-1] + 5.0)   # shown time
    assert r[1]["value"] == pytest.approx(20)
    assert r[2]["sig"] is None and r[2]["value"] is None                    # not in this file: said, not hidden
    assert r[3]["sig"] == f"{rid}/Step" and r[3]["value"] is None           # a state has no number
    bad = client.post(f"/api/runs/{rid}/glance", json={"items": [{"name": "Engine.Temp", "stat": "median"}]})
    assert bad.status_code == 400
    assert client.post("/api/runs/gone/glance", json={"items": []}).status_code == 404


def test_builtin_profiles_carry_valid_glance_and_searches():
    from svcore.windowstats import GLANCE_STATS
    seen = 0
    for t in tplm.builtin_templates():
        g = t.get("glance", [])
        assert len(g) <= 4, t["id"]
        for it in g:
            assert it["stat"] in GLANCE_STATS and it["name"] and it.get("label", "@").startswith("@")
        for s in t.get("searches", []):
            assert s["q"].strip()
        seen += bool(g)
    assert seen >= 6


def test_glance_on_the_sample_log():
    path = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "copter_flight.bin")
    rid = client.post("/api/files/open", json={"paths": [os.path.abspath(path)]}).json()["opened"][0]["id"]
    review = next(t for t in tplm.builtin_templates() if t["id"] == "bi-ap-review")
    r = client.post(f"/api/runs/{rid}/glance", json={"items": review["glance"]}).json()["items"]
    assert all(x["sig"] for x in r), json.dumps(r)
    assert all(x["value"] is not None for x in r)


def test_saved_template_keeps_glance_and_searches(tmp_path, monkeypatch):
    from app import prefs
    monkeypatch.setattr(prefs, "TEMPLATE_DIR", str(tmp_path))
    tpl = {"version": 2, "id": "", "name": "Bench", "slots": [{"id": "main", "name": "File"}],
           "tabs": [{"name": "A", "rows": 1, "cols": 1, "plots": []}],
           "glance": [{"name": "Engine.Temp", "stat": "max"}, {"name": "x", "stat": "bogus"}, "junk"],
           "searches": [{"q": "Engine_"}, {"q": "  "}]}
    saved = prefs.save_template(tpl)
    assert saved["glance"] == [{"name": "Engine.Temp", "stat": "max"}]
    assert saved["searches"] == [{"q": "Engine_"}]
    old = prefs.save_template({k: v for k, v in tpl.items() if k not in ("glance", "searches")})
    assert "glance" not in old and "searches" not in old                       # an old template stays as it was
