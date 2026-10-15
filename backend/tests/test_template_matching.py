"""T11b: template matching lives in svcore/templates.py (one implementation for the UI and the
command line). It must answer exactly as the TypeScript version did - the recorded answers are in
tests/data/template_matching_ts.json:  python -m pytest backend/tests/test_template_matching.py"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
from svcore import templates as T  # noqa: E402

DATA = json.load(open(os.path.join(HERE, "data", "template_matching_ts.json"), encoding="utf-8"))
ALL = T.builtin_templates() + DATA["templates"]


@pytest.mark.parametrize("case", DATA["cases"], ids=lambda c: f"{c['template']}-{len(c['runs'])}runs-{c['prefer']}")
def test_same_answers_as_the_typescript_version(case):
    t = next(x for x in ALL if x["id"] == case["template"])
    e = T.expand(t, ALL)
    assert T.auto_bind(e, case["runs"], case["prefer"]) == case["expected"]["bind"]
    f = T.fit(t, ALL, case["runs"])
    exp = case["expected"]["fit"]
    # an objects-only generator: the UI decides with its position roles (None here)
    assert (f is None and t.get("generator") == "objects") or f == pytest.approx(exp)
    assert [T.match_signal(n, w) for n, w in case["match"]] == case["expected"]["matches"]


def test_resolve_builds_tabs_with_signal_ids():
    runs = [{"id": "r1", "path": "/a/run_a.csv", "format": "csv", "signals": [{"name": n} for n in ("Speed", "RPM", "Gear")]},
            {"id": "r2", "path": "/b/run_b.csv", "format": "csv", "signals": [{"name": n} for n in ("Speed", "Temp")]}]
    one = next(x for x in DATA["templates"] if x["id"] == "m-one")
    r = T.resolve(one, ALL, {"main": "r1"}, runs)
    assert [s["sig"] for s in r["tabs"][0]["plots"][0]["signals"]] == ["r1/Speed", "r1/Gear"]
    assert r["missing"] == [] and r["dropped"] == []
    r = T.resolve(one, ALL, {"main": T.ALL}, runs)                 # all files: Speed from both, colour left to the caller
    sp = r["tabs"][0]["plots"][0]["signals"]
    assert [s["sig"] for s in sp] == ["r1/Speed", "r2/Speed", "r1/Gear"] and sp[0]["color"] is None
    r = T.resolve(one, ALL, {"main": "r2"}, runs)                 # no RPM in run_b: that plot is dropped, Gear missing
    assert r["dropped"] == ["T › R"] and set(r["missing"]) == {"Gear", "RPM"}
    assert r["tabs"][0]["rows"] == 1                              # one plot left of two
    filled = T.fill_colors(T.resolve(one, ALL, {"main": T.ALL}, runs))
    assert all(s["color"] for s in filled["tabs"][0]["plots"][0]["signals"])
    extra = [{"name": "Q", "rows": 1, "cols": 1, "plots": [{"title": "t", "signals": [{"name": "Temp", "slot": "main"}]}]}]
    r = T.resolve(one, ALL, {"main": "r2"}, runs, chosen=[], extra_tabs=extra)   # generator tabs from the UI
    assert [t["name"] for t in r["tabs"]] == ["Q"] and r["tabs"][0]["plots"][0]["signals"][0]["sig"] == "r2/Temp"


def test_objects_need_a_position():
    runs = [{"id": "r1", "path": "/f.BIN", "format": "bin", "signals": [{"name": n} for n in ("GPS.Lat", "GPS.Lng", "GPS.Alt", "ATT.Yaw")]}]
    t = next(x for x in ALL if x["id"] == "bi-ap-flight")
    r = T.resolve(t, ALL, {"main": "r1"}, runs)
    o = r["tabs"][0]["plots"][0]["objects"][0]
    assert (o["lat"], o["lon"], o["alt"], o["yaw"], o["roll"]) == ("r1/GPS.Lat", "r1/GPS.Lng", "r1/GPS.Alt", "r1/ATT.Yaw", None)
    no_pos = [{"id": "r1", "path": "/f.BIN", "format": "bin", "signals": [{"name": "ATT.Yaw"}]}]
    assert T.resolve(t, ALL, {"main": "r1"}, no_pos)["tabs"] == []
