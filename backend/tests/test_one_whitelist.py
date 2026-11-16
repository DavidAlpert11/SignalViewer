"""M34 FR7: one formula whitelist. svcore/formula.py owns it; a Sweeps column (svcore/sweep/derived.py) and a study's
constraints (svcore/sweeps_common.py) are parsed and checked by it - so what one refuses, all three refuse."""
import numpy as np
import pandas as pd
import pytest

from svcore import formula, sweeps_common
from svcore.formula import FormulaError
from svcore.sweep.derived import DerivedError, row_formula
from svcore.sweeps_common import StudyError

T = np.arange(5.0)
SIG = [(T, T * 2.0)]
# a table that even has columns with those names: a name with __ is refused, not looked up
DF = pd.DataFrame({"kp": [1.0, 2.0, 3.0], "__class__": [1.0, 2.0, 3.0], "__import__": [0.0, 0.0, 0.0]})

# (as a signal formula, as a row formula) - an import, an attribute, a dunder name, a subscript, a lambda,
# a keyword argument
REFUSED = [
    ("__import__('os')", "__import__('os')"),
    ("__import__('os').system('x')", "__import__('os').system('x')"),
    ("v0.real", "kp.real"),
    ("v0.__class__", "kp.__class__"),
    ("__class__", "__class__"),
    ("__class__ + v0", "__class__ + kp"),
    ("v0[0]", "kp[0]"),
    ("lambda: 1", "lambda: 1"),
    ("abs(x=v0)", "abs(x=kp)"),
    ("(v0 for v0 in t)", "(kp for kp in pi)"),
]


def _align(t, ts, ys):
    return np.interp(t, ts, ys)


@pytest.mark.parametrize("signal,row", REFUSED)
def test_refused_by_all_three_entry_points(signal, row):
    with pytest.raises(FormulaError):
        formula.evaluate(signal, SIG, _align)                       # a signal formula (Create, conditions, transforms)
    with pytest.raises(DerivedError):
        row_formula(DF, row)                                         # a Sweeps column / objective
    with pytest.raises(StudyError):
        sweeps_common.check(DF, [row])                               # a study's constraint
    with pytest.raises(StudyError):
        sweeps_common.check(DF, [f"kp > 0 and {row}"])               # ... also as a part of an `and`


def test_one_module_owns_the_whitelist():
    import inspect

    from svcore.sweep import derived
    assert "ast.parse" not in inspect.getsource(derived)
    assert "import ast" not in inspect.getsource(sweeps_common)
    assert set(derived.FUNCTIONS) == set(formula.ROW_FUNCTIONS)


def test_what_sweeps_needs_still_passes():
    assert list(row_formula(DF, 'if(kp > 1, "high", "low")')) == ["low", "high", "high"]
    assert list(row_formula(DF, "kp in (1, 3)")) == [1.0, 0.0, 1.0]
    assert list(row_formula(DF, "bins(kp, [2])")) == ["<2", "≥2", "≥2"]
    assert list(row_formula(DF, "rank(kp) + pct(kp)")) == pytest.approx([1 + 100 / 3, 2 + 200 / 3, 3 + 100])
    assert list(row_formula(DF, 'text(kp) == "2"')) == [0.0, 1.0, 0.0]
    c = sweeps_common.check(DF, ["kp < 2.5 and kp > 1"])
    assert list(c.ok) == [False, True, False] and list(c.by) == [pytest.approx(0.0), pytest.approx(np.nan, nan_ok=True), pytest.approx(0.5)]
