"""L12: the shared object-detection vectors (tests/data/object_detect_cases.json) - the expectations were made
by the app's rules (Vitest, frontend/src/objectVectors.test.ts); Python's svcore/objects.py must give exactly
the same objects, picks, origins and near misses. Plus: Python reads the same table file as the app."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore import objects  # noqa: E402

DOC = json.load(open(os.path.join(os.path.dirname(__file__), "..", "..", "tests", "data", "object_detect_cases.json"), encoding="utf-8"))


def summary(c):
    p = c["picks"]
    return {"prefix": c["prefix"], "name": c["name"], "cls": c["cls"], "pos": c["pos"], "attitude": c["attitude"], "full": c["full"],
            "missing": c["missing"], "picks": {r: f"{p[r]['name']}|{p[r]['rule']}" for r in sorted(p)},
            "origin": (f"{c['origin']['via']}|{c['origin']['rule']}" + ("|moves" if c["origin"].get("moves") else "")) if c.get("origin") else None,
            "badUnit": c.get("badUnit"), "lane": f"{c['lane']['ekf']}:{c['lane']['n']}" if c.get("lane") else None,
            "nearMisses": [f"{m['name']}|{m['role']}|{m['why']}" for m in c["nearMisses"]]}


def run(names):
    d = objects.detect([(f"r/{n}", n) for n in names], "r", "case.csv")
    return {"candidates": [summary(c) for c in d["candidates"]], "incomplete": [i["prefix"] for i in d["incomplete"]],
            "nearMisses": [f"{m['name']}|{m['role']}|{m['why']}" for m in d["nearMisses"]]}


@pytest.mark.parametrize("case", DOC["cases"], ids=[c["name"] for c in DOC["cases"]])
def test_same_as_the_app(case):
    assert run(case["names"]) == case["expect"]


def test_one_table_file():
    src = open(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "objectDetect.ts"), encoding="utf-8").read()
    assert "backend/svcore/object_names.json" in src and objects.KNOWN_GROUPS["XKF1"]["origin"] == ["ORGN[0]", "ORGN"]
