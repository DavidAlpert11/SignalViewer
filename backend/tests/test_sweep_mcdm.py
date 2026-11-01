"""MF10: ranking methods against a table worked by hand (3 sets x 2 objectives)."""
import pytest

from svcore.sweep import mcdm

# obj1 maximised, obj2 minimised; weights 3 : 1 -> 0.75 / 0.25
VALUES = [[10, 4], [6, 2], [8, 3]]
DIRS = ["max", "min"]
W = [3, 1]
# by hand: utilities u1 = 1, 0, 0.5 ; u2 = 0, 1, 0.5


def test_weighted_sum_by_hand():
    r = mcdm.rank(VALUES, DIRS, W, "weighted")
    assert r["scores"] == pytest.approx([0.75, 0.25, 0.5])
    assert r["order"] == [0, 2, 1]
    assert r["ranks"] == [1, 3, 2]
    # "0 above 2 because": obj1 +0.75 * 0.5, obj2 -0.25 * 0.5
    assert r["why"][0]["a"] == 0 and r["why"][0]["b"] == 2
    assert r["why"][0]["parts"] == pytest.approx([0.375, -0.125])
    assert sum(r["why"][0]["parts"]) == pytest.approx(r["scores"][0] - r["scores"][2])


def test_topsis_by_hand():
    # norms sqrt(200), sqrt(29); closeness 0.6956, 0.3044, 0.5 (worked by hand)
    r = mcdm.rank(VALUES, DIRS, W, "topsis")
    assert r["scores"] == pytest.approx([0.6956, 0.3044, 0.5], abs=1e-3)
    assert r["order"] == [0, 2, 1]


def test_hurwicz_by_hand():
    # relative weights 1, 1/3: set0 (1, 0) -> 0.5; set1 (0, 1/3) -> 1/6; set2 (0.5, 1/6) -> 1/3
    r = mcdm.rank(VALUES, DIRS, W, "hurwicz", alpha=0.5)
    assert r["scores"] == pytest.approx([0.5, 1 / 6, 1 / 3])
    # alpha 1 = only the best objective counts, alpha 0 = only the worst
    assert mcdm.rank(VALUES, DIRS, W, "hurwicz", alpha=1)["scores"] == pytest.approx([1, 1 / 3, 0.5])
    assert mcdm.rank(VALUES, DIRS, W, "hurwicz", alpha=0)["scores"] == pytest.approx([0, 0, 1 / 6])


def test_savage_by_hand():
    # regrets (1 - u) * rel: max per set 1/3, 1, 0.5
    r = mcdm.rank(VALUES, DIRS, W, "savage")
    assert r["scores"] == pytest.approx([-1 / 3, -1, -0.5])
    assert r["order"] == [0, 2, 1]


def test_indifference_margin_ties():
    # range 0.5; margin 0.6 -> 0.3: 0.75 and 0.5 tie, 0.25 is 0.5 below the leader
    r = mcdm.rank(VALUES, DIRS, W, "weighted", margin=0.6)
    assert r["ranks"] == [1, 3, 1]
    assert r["why"][0]["tie"] is True


def test_ahp_consistent_matrix():
    w = [0.5, 0.3, 0.2]
    m = [[w[i] / w[j] for j in range(3)] for i in range(3)]
    a = mcdm.ahp(m)
    assert a["weights"] == pytest.approx(w, abs=1e-9)
    assert a["lambdaMax"] == pytest.approx(3, abs=1e-9)
    assert a["cr"] == pytest.approx(0, abs=1e-9) and a["consistent"]


def test_ahp_upper_triangle_and_inconsistent():
    # only the upper triangle given (lower ignored); A > B 9x, B > C 9x, but C > A 9x: inconsistent
    a = mcdm.ahp([[1, 9, 1 / 9], [0, 1, 9], [0, 0, 1]])
    assert a["cr"] > 0.1 and not a["consistent"]
    with pytest.raises(ValueError):
        mcdm.ahp([[1, -2], [0, 1]])


def test_rank_from_pairwise_weights():
    r = mcdm.rank(VALUES, DIRS, [1, 1], "weighted", pairwise=[[1, 3], [1 / 3, 1]])
    assert r["weights"] == pytest.approx([0.75, 0.25])
    assert r["scores"] == pytest.approx([0.75, 0.25, 0.5])


def test_missing_value_and_bad_input():
    r = mcdm.rank([[1, float("nan")], [2, 1]], DIRS, [1, 1], "topsis")
    assert r["order"][0] == 1
    with pytest.raises(ValueError):
        mcdm.rank(VALUES, ["max"], W)
    with pytest.raises(ValueError):
        mcdm.rank(VALUES, DIRS, W, "nope")


def test_mcdm_route():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.post("/api/sweep/mcdm", json={"values": VALUES, "directions": DIRS, "weights": W, "method": "savage"})
    assert r.status_code == 200 and r.json()["order"] == [0, 2, 1]
    r = c.post("/api/sweep/mcdm", json={"values": [[1, None], [2, 1]], "directions": DIRS, "method": "weighted"})
    assert r.status_code == 200 and r.json()["order"][0] == 1
    r = c.post("/api/sweep/mcdm", json={"values": VALUES, "directions": DIRS, "pairwise": [[1, -1], [0, 1]]})
    assert r.status_code == 400 and "positive" in r.json()["detail"]
