"""Q130, Q131, Q133: changes in clusters, the more likely first (with its parts), and the signals that
cannot tell anything left out - on synthetic files whose answer is known."""
import numpy as np
import pytest

from app.store import Store
from svcore import firstchange as fc

RNG = np.random.default_rng(3)
T = np.round(np.arange(0, 6, 0.01), 2)              # 100 Hz


def _csv(path, cols):
    names = list(cols)
    rows = "".join(",".join([f"{t:.2f}"] + [f"{cols[n][i]:.5f}" for n in names]) + "\n" for i, t in enumerate(T))
    path.write_text("Time," + ",".join(names) + "\n" + rows)
    return str(path)


def _noise():
    return RNG.normal(0, 0.05, len(T))


def test_two_clusters_by_gaps(tmp_path):
    # changes at 1.00 / 1.01 / 1.02 s and at 2.5 s -> two clusters
    cols = {"A": _noise() + 5 * (T >= 1.00), "B": _noise() + 5 * (T >= 1.01), "C": _noise() + 5 * (T >= 1.02),
            "D": _noise() + 5 * (T >= 2.5), "N": _noise()}
    st = Store()
    rid = st.open_file(_csv(tmp_path / "c.csv", cols)).id
    items = st.first_changes([], [rid], 2.6, 3.0, (0.0, 0.8))
    cl = fc.clusters(items, 2.6, 3.0, 0.8)
    names = [[i.split("/")[1] for i in c["ids"]] for c in cl]
    assert names == [["A", "B", "C"], ["D"]]
    assert cl[0]["first"].endswith("/A") and cl[0]["t0"] == pytest.approx(1.0) and cl[0]["t1"] == pytest.approx(1.02)


def test_a_leading_step_scores_above_a_bigger_blip_after_and_a_change_the_reference_has(tmp_path):
    ev = _noise() + 4 * (T >= 3.0)                       # the event signal: a step at 3.0 s
    step = _noise() + 2 * (T >= 2.5)                     # leads it by 0.5 s and stays
    blip = _noise() + 20 * ((T >= 3.2) & (T < 3.25))     # larger, after the event, gone at once
    both = _noise() + 3 * (T >= 2.5)                     # the same lead - but the reference run has it too
    st = Store()
    rid = st.open_file(_csv(tmp_path / "e.csv", {"Event": ev, "Step": step, "Blip": blip, "Both": both})).id
    ref = st.open_file(_csv(tmp_path / "r.csv", {"Event": _noise(), "Step": _noise(), "Blip": _noise(),
                                                  "Both": _noise() + 3 * (T >= 2.5)})).id
    items = st.first_changes([], [rid], 3.0, 3.5, (0.5, 2.0))
    out = st.change_clusters(items, 3.0, 3.5, [ref], event=f"{rid}/Event")
    by = {x["name"]: x for x in items if x.get("score") is not None}
    assert by["Step"]["score"] > by["Blip"]["score"]
    assert by["Step"]["score"] > by["Both"]["score"]
    assert by["Both"]["inRef"] == [ref] and by["Both"]["parts"]["unique"] == 0
    assert by["Blip"]["parts"]["timing"] == 0 and by["Blip"]["parts"]["stays"] < 0.3
    assert by["Step"]["parts"]["shape"] > 0.5 and by["Step"]["leadsEvent"] == pytest.approx(0.5, abs=0.05)
    # in its cluster the reference's change comes last
    c = next(c for c in out["clusters"] if any(i.endswith("/Both") for i in c["ids"]))
    assert c["ids"][-1].endswith("/Both")
    assert set(fc.WEIGHTS) == set(by["Step"]["parts"])


def test_constant_counter_clock_and_heartbeat_are_left_out():
    t = np.arange(0, 10, 0.01)
    assert fc.uninformative(t, np.full(len(t), 3.0), 0, 10) == "constant"
    assert fc.uninformative(t, np.arange(len(t)) * 1.0, 0, 10) == "counter"           # a sequence number
    assert fc.uninformative(t, 1.7e9 + t, 0, 10) == "counter"                        # a time stamp
    assert fc.uninformative(t, (np.floor(t * 2) % 2), 0, 10) == "heartbeat"          # toggles every 0.5 s
    assert fc.uninformative(t, np.sin(t) + 0.01 * np.cos(37 * t), 0, 10) is None
    # a heartbeat that stops changing its period is worth a look
    beat = np.floor(np.where(t < 5, t * 2, 10 + (t - 5) * 8)) % 2
    assert fc.uninformative(t, beat, 0, 10) is None


def test_route_returns_clusters_scores_and_skipped(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    cols = {"A": _noise() + 5 * (T >= 2.0), "Seq": np.arange(len(T)) * 1.0, "Flat": np.zeros(len(T))}
    c = TestClient(app)
    rid = store.open_file(_csv(tmp_path / "q.csv", cols), {}).id
    try:
        r = c.post("/api/firstchange", json={"a": 2.2, "b": 2.6, "runs": [rid]}).json()
        assert r["clusters"] and r["clusters"][0]["ids"] == [f"{rid}/A"]
        assert r["skipped"] == {"counter": 1, "constant": 1}
        a = next(x for x in r["items"] if x["name"] == "A")
        assert 0 < a["score"] <= 1 and set(a["parts"]) == set(r["weights"])
    finally:
        store.remove(rid)


def test_a_chain_of_who_leads_whom(tmp_path):
    """Q134: A steps, B follows it 0.3 s later (shaped like it), the event follows B; N is noise that
    changes once on its own: edges A -> B and B -> Event (and A -> Event), none to or from N."""
    a_ = _noise() + 3 * (T >= 2.0)
    b_ = _noise() + 3 * (T >= 2.3)
    ev = _noise() + 3 * (T >= 2.6)
    n_ = RNG.normal(0, 0.05, len(T)) + 4 * ((T >= 1.2) & (T < 1.22))
    st = Store()
    rid = st.open_file(_csv(tmp_path / "ch.csv", {"A": a_, "B": b_, "Event": ev, "N": n_})).id
    items = st.first_changes([], [rid], 2.6, 3.0, (0.2, 1.0))
    ch = st.change_clusters(items, 2.6, 3.0, [], event=f"{rid}/Event")["chain"]
    pairs = {(e["a"].split("/")[1], e["b"].split("/")[1]): e for e in ch["edges"]}
    assert ("A", "B") in pairs and ("B", "Event") in pairs
    assert pairs[("A", "B")]["lag"] == pytest.approx(0.3, abs=0.03) and pairs[("A", "B")]["r"] > 0.8
    assert not any("N" in k for k in pairs)
    assert [n["id"].split("/")[1] for n in ch["nodes"]][-1] == "Event"
