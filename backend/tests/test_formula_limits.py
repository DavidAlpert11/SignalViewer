"""A formula too large or too deep for Python says so as a formula error (it was a 500 "Unexpected error")."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from svcore.formula import FormulaError, evaluate, parse_rows  # noqa: E402
from svcore.sweep.derived import DerivedError, row_formula  # noqa: E402

T = np.arange(5.0)
HUGE = "v0+1" + "0" * 400                     # an int far past float64's range
DEEP = "-" * 1990 + "v0"                      # past Python's recursion limit when evaluated


def _eval(expr):
    return evaluate(expr, [(T, T)], lambda t, ts, ys: ys)


@pytest.mark.parametrize("expr, said", [(HUGE, "too large"), (DEEP, "nested too deeply")])
def test_a_signal_formula_past_the_limits_is_a_formula_error(expr, said):
    with pytest.raises(FormulaError, match=said):
        _eval(expr)


def test_numbers_inside_the_range_still_work():
    _, r = _eval("v0 + 1" + "0" * 300)
    assert np.allclose(r, T + 1e300)
    _, r = _eval("-" * 50 + "v0")
    assert np.allclose(r, T)


def test_a_sweeps_row_formula_past_the_limits_is_said():
    with pytest.raises(FormulaError, match="too large"):
        parse_rows("x > 1" + "0" * 400)
    with pytest.raises(DerivedError, match="nested too deeply"):
        row_formula(pd.DataFrame({"x": [1.0, 2.0]}), "-" * 1990 + "x")


def test_the_derived_route_answers_400_with_the_reason(tmp_path):
    p = tmp_path / "s.csv"
    p.write_bytes(b"Time,V\n0,1\n1,2\n2,3\n")
    c = TestClient(app)
    run = c.post("/api/files/open", json={"paths": [str(p)]}).json()["opened"][0]
    sid = next(s["id"] for s in run["signals"] if s["name"] == "V")
    for expr, said in ((HUGE, "too large"), (DEEP, "nested too deeply")):
        r = c.post("/api/derived", json={"op": "expr", "sources": [sid], "params": {"expr": expr}})
        assert r.status_code == 400, r.text
        assert said in r.json()["detail"] and "Unexpected" not in r.json()["detail"]
    c.delete(f"/api/runs/{run['id']}")
