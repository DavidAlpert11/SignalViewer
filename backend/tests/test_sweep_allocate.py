"""Next runs: how the budget is shared among the kinds of suggestion (owner, 2026-11-02) - equal
(in turns), proportional (to what each kind has), manual (the numbers given)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.sweep.analysis import allocate  # noqa: E402

AV = {"edge": 30, "best": 10, "gaps": 2}
K = ["edge", "best", "gaps"]


def test_equal_in_turns_a_short_kind_gives_its_turn():
    assert allocate(AV, K, 12) == {"edge": 5, "best": 5, "gaps": 2}
    assert allocate(AV, K, 2) == {"edge": 1, "best": 1, "gaps": 0}


def test_proportional_to_what_each_has():
    n = allocate(AV, K, 21, "proportional")
    assert sum(n.values()) == 21 and n["edge"] == 15 and n["best"] == 5 and n["gaps"] == 1
    assert allocate(AV, K, 100, "proportional") == AV                          # more than all: all


def test_manual_numbers_capped():
    assert allocate(AV, K, 20, "manual", {"edge": 5, "best": 50, "gaps": 1}) == {"edge": 5, "best": 10, "gaps": 1}
    assert sum(allocate(AV, K, 8, "manual", {"edge": 6, "best": 6}).values()) == 8


def test_proportional_gives_every_kind_found_at_least_one():
    n = allocate({"edge": 92, "best": 11, "gaps": 1}, ["edge", "best", "gaps"], 10, "proportional")
    assert sum(n.values()) == 10 and n["gaps"] == 1 and n["best"] >= 1 and n["edge"] > n["best"]
