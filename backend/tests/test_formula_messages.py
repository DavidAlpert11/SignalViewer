"""RV11 (review B8): a formula's syntax error at its real place, an unknown function named with the closest one."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.formula import FormulaError, parse, syntax_message_for  # noqa: E402


def _msg(expr):
    with pytest.raises(FormulaError) as e:
        parse(expr, 1)
    return str(e.value)


def test_a_formula_that_ends_too_early_says_so():
    assert "ends too early" in _msg("v0 +") and "'v0 +'" in _msg("v0 +")
    assert "ends too early" in _msg("sqrt(v0")
    assert "position 0" not in _msg("v0 **")


def test_a_syntax_error_in_the_middle_gives_its_character():
    m = _msg("v0 + )")
    assert "character 6" in m and "'v0 + )'" in m


def test_an_unknown_function_is_named_with_the_closest():
    assert _msg("sqrtt(v0)") == "Unknown function: sqrtt() - did you mean sqrt()?"
    assert _msg("zzzq(v0)").startswith("Unknown function: zzzq().")


def test_the_message_points_into_the_text_as_typed():
    assert "'{ATT.Roll} +'" in syntax_message_for("{ATT.Roll} +")
    assert "character 14" in syntax_message_for("{ATT.Roll} + )")
    assert syntax_message_for("2 ^ {A}") is None
