"""A1: the Investigate computations as pure functions (svcore/investigate.py) - tested on a Source
made of plain arrays, without a Store or a file."""
import numpy as np
import pytest

from svcore import investigate as inv

T = np.linspace(0, 100, 2001)
RNG = np.random.default_rng(3)
# run A: Speed steps up at 50 s, Gear (a state) changes at 50 s, Noise never changes
SIGS = {
    "A/Speed": (T, np.where(T >= 50, 20.0, 10.0) + RNG.normal(0, 0.05, T.size)),
    "A/Noise": (T, RNG.normal(0, 1.0, T.size)),
    "A/Gear": (T, np.where(T >= 50, 2.0, 1.0)),
    "B/Speed": (T, np.full(T.size, 10.0) + RNG.normal(0, 0.05, T.size)),
}
LABELS = {"A": {"Speed": None, "Noise": None, "Gear": {1: "LOW", 2: "HIGH"}}, "B": {"Speed": None}}


def src():
    def signal(sid):
        if sid not in SIGS:
            raise KeyError(sid)
        return SIGS[sid]
    return inv.Source(signal=signal, signals=lambda rid: LABELS.get(rid), runs=["A", "B"])


def test_condition_in_every_file_with_texts_and_missing_signals():
    out = inv.evaluate_condition(src(), 'Gear == "HIGH"')
    assert out["A"]["intervals"][0][0] == pytest.approx(50, abs=0.1)
    assert "error" in out["B"]                              # B has no Gear: it says so
    with pytest.raises(inv.InvestigateError):
        inv.evaluate_condition(src(), "  ")


def test_occurrences_rows_and_what_differs():
    iv = {"A": [[60.0, 80.0]], "B": [[60.0, 80.0]]}
    rows = inv.occurrence_rows(src(), iv, ["Speed"])
    assert len(rows) == 2 and rows[0]["values"]["Speed"]["max"] == pytest.approx(20, abs=0.5)
    differ = inv.occurrence_differ(src(), {"A": [[60.0, 80.0]]})
    assert differ[0]["name"] == "Speed" and differ[0]["up"]


def test_first_change_and_find_similar_leave_states_out():
    ch = inv.first_changes(src(), [], ["A"], 49.0, 52.0)
    first = ch[0]
    assert first["status"] == "changed" and first["id"] in ("A/Speed", "A/Gear") and first["t"] == pytest.approx(50, abs=0.3)
    sug = inv.suggest_condition(src(), ["A/Speed", "A/Gear", "A/Noise"], 55.0, 70.0)
    assert sug["id"] == "A/Speed" and sug["text"].startswith("Speed >")


def test_clusters_mark_a_change_seen_in_the_reference_run():
    items = inv.first_changes(src(), [], ["A"], 49.0, 52.0)
    r = inv.change_clusters(src(), items, 49.0, 52.0, refs=["B"])
    ids = [i for c in r["clusters"] for i in c["ids"]]
    assert "A/Speed" in ids and "nodes" in r["chain"]


def test_lag_between_two_signals():
    s = src()
    shifted = (T, np.interp(T - 2.0, T, SIGS["A/Speed"][1]))
    s2 = inv.Source(signal=lambda sid: shifted if sid == "A/Late" else s.signal(sid), signals=s.signals)
    r = inv.lag_between(s2, "A/Speed", "A/Late", 30.0, 80.0)
    assert r["status"] == "ok" and r["lag"] == pytest.approx(2.0, abs=0.2)
