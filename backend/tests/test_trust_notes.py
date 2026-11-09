"""26.U6: what a trust badge can say about a derived signal - values interpolated between samples
(another signal's sample times), a filter across gaps or on an uneven grid (26.A3), missing values (C3)."""
import numpy as np

from svcore.analysis import compute


def test_interpolated_only_when_another_signals_times_are_used():
    t = np.arange(0, 10, 0.1)
    a, b_same, b_other = (t, np.sin(t)), (t, np.cos(t)), (np.arange(0.05, 10, 0.2), np.ones(50))
    rep: dict = {}
    compute("add", [a, b_same], {}, report=rep)
    assert "interpolated" not in rep                              # the same samples: nothing read between them
    rep = {}
    compute("add", [a, b_other], {"alignment": "nearest"}, report=rep)
    assert rep["interpolated"] == {"method": "nearest", "sources": [1]}
    rep = {}
    compute("mean", [a, b_other, b_other], {}, report=rep)
    assert rep["interpolated"]["sources"] == [1, 2] and rep["interpolated"]["method"] == "linear"
    rep = {}
    compute("expr", [a, b_other], {"expr": "v0 + v1"}, report=rep)
    assert len(rep["interpolated"]["sources"]) == 1
    rep = {}
    compute("add", [a, (t, np.zeros_like(t))], {}, states=[False, True], report=rep)
    assert "interpolated" not in rep                              # a state is held (C2), not interpolated


def test_a_filter_across_a_gap_is_noted():
    t = np.concatenate([np.arange(0, 5, 0.01), np.arange(8, 13, 0.01)])
    rep: dict = {}
    compute("lowpass", [(t, np.sin(t))], {"cutoff": 2}, report=rep)
    assert rep["filter"]["gaps"] == 1
