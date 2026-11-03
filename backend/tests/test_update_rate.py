"""A derivative / integral of a signal that updates slower than it is logged (owner, 2026-11-03):
its updates found by its own rate, or by a flag signal that is 1 when it updated; computed on
those samples alone and put back on every sample."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.analysis import DerivedDef, OpError, compute  # noqa: E402
from svcore.formula import FormulaError, evaluate  # noqa: E402
from svcore.ops import update_indices  # noqa: E402

T = np.arange(0, 2, 0.01)                                     # logged at 100 Hz
TRUE = np.sin(np.pi * T)
SLOW = TRUE[(np.arange(len(T)) // 10) * 10]                    # computed at 10 Hz: held between updates
FLAG = (np.arange(len(T)) % 10 == 0).astype(float)
D_TRUE = np.pi * np.cos(np.pi * T)
MID = slice(20, 180)


def test_update_indices_by_rate_and_by_flag():
    assert list(update_indices(T, SLOW, hz=10)) == list(range(0, 200, 10))
    assert list(update_indices(T, SLOW, flag=FLAG)) == list(range(0, 200, 10))
    y = SLOW.copy(); y[:3] = np.nan                            # the first sample with a value is kept
    assert update_indices(T, y, flag=FLAG)[0] == 3
    with pytest.raises(ValueError):
        update_indices(T, SLOW, hz=0)


def test_derivative_of_the_updates_not_the_repeats():
    _, plain = compute("derivative", [(T, SLOW)], {})
    _, by_rate = compute("derivative", [(T, SLOW)], {"update": {"hz": 10}})
    _, by_flag = compute("derivative", [(T, SLOW), (T, FLAG)], {"update": {"flag": True}})
    assert np.nanmax(np.abs(plain[MID] - D_TRUE[MID])) > 5          # zeros and spikes
    assert np.nanmax(np.abs(by_rate[MID] - D_TRUE[MID])) < 0.1
    assert np.allclose(by_rate, by_flag, equal_nan=True)
    assert len(by_rate) == len(T)                                   # back on every sample


def test_integral_of_the_updates():
    _, i = compute("integral", [(T, SLOW)], {"update": {"hz": 10}})
    exact = (1 - np.cos(np.pi * T)) / np.pi
    assert np.nanmax(np.abs(i[:191] - exact[:191])) < 0.01


def test_errors_and_names():
    with pytest.raises(OpError):
        compute("derivative", [(T, SLOW)], {"update": {"flag": True}})   # no flag signal
    with pytest.raises(OpError):
        compute("derivative", [(T, SLOW)], {"update": {"hz": 0}})
    d = DerivedDef("d", "derivative", ["run/A", "run/A_upd"], {"update": {"flag": True}})
    assert d.formula(lambda s: s.split("/")[1]) == "derivative(A, when A_upd)"
    d = DerivedDef("i", "integral", ["run/A"], {"update": {"hz": 10}})
    assert d.formula(lambda s: s.split("/")[1]) == "∫ A, 10 Hz dt"


def test_in_a_formula():
    t, r = evaluate("deriv(v0, 10)", [(T, SLOW)], lambda tb, ts, ys: np.interp(tb, ts, ys))
    assert np.nanmax(np.abs(r[MID] - D_TRUE[MID])) < 0.1
    t, r2 = evaluate("deriv(v0, v1)", [(T, SLOW), (T, FLAG)], lambda tb, ts, ys: np.interp(tb, ts, ys))
    assert np.allclose(r, r2, equal_nan=True)
    _, i = evaluate("integ(v0, v1)", [(T, SLOW), (T, FLAG)], lambda tb, ts, ys: np.interp(tb, ts, ys))
    assert abs(i[150] - (1 - np.cos(np.pi * 1.5)) / np.pi) < 0.01
    with pytest.raises(FormulaError):
        evaluate("deriv(v0, 0)", [(T, SLOW)], lambda tb, ts, ys: np.interp(tb, ts, ys))
