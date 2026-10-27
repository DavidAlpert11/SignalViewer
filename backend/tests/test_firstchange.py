"""Investigation step 4: what changed first around a moment, and the lag between two signals."""
import numpy as np

from app.store import Store
from svcore.firstchange import first_change, lag

T = np.arange(0, 20, 0.01)
RNG = np.random.default_rng(1)


def _step(at, size=5.0, noise=0.1):
    return RNG.normal(0, noise, len(T)) + size * (T >= at)


def test_first_change_order_and_direction():
    a, b = 10.0, 11.0
    early, late = _step(9.9), -_step(10.3)
    fe = first_change(T, early, a, b, (9.0, 9.75))
    fl = first_change(T, late, a, b, (9.0, 9.75))
    assert fe["status"] == fl["status"] == "changed"
    assert abs(fe["t"] - 9.9) < 0.03 and abs(fl["t"] - 10.3) < 0.03
    assert fe["up"] and not fl["up"] and fe["rel"] < 0 < fl["rel"]


def test_noise_alone_is_not_a_change_and_states_count_new_values():
    quiet = first_change(T, RNG.normal(0, 1, len(T)), 10, 11, (9, 9.75))
    assert quiet["status"] == "same"
    mode = np.where(T >= 10.5, 4.0, 2.0)
    m = first_change(T, mode, 10, 11, (9, 9.75), discrete=True)
    assert m["status"] == "changed" and abs(m["t"] - 10.5) < 0.02
    assert first_change(T[:1], mode[:1], 10, 11, (9, 9.75))["status"] == "nodata"


def test_lag_finds_the_delay_and_says_when_it_is_weak_or_ambiguous():
    x = np.sin(2 * np.pi * 0.3 * T) + 0.5 * np.sin(2 * np.pi * 0.07 * T)
    delayed = np.interp(T - 0.25, T, x)
    r = lag(T, x, T, delayed, 2, 18)
    assert r["status"] == "ok" and abs(r["lag"] - 0.25) < 0.02 and r["r"] > 0.95 and not r["weak"]
    noise = lag(T, RNG.normal(0, 1, len(T)), T, RNG.normal(0, 1, len(T)), 2, 18)
    assert noise["weak"]
    pure = np.sin(2 * np.pi * 1.0 * T)
    assert lag(T, pure, T, np.interp(T - 0.1, T, pure), 2, 18)["ambiguous"]


def test_store_ranks_candidates(tmp_path):
    p = tmp_path / "r.csv"
    rows = "".join(f"{t:.2f},{(5 if t >= 9.9 else 0) + RNG.normal(0, .05):.4f},{(-3 if t >= 10.2 else 0) + RNG.normal(0, .05):.4f},{RNG.normal(0, 1):.4f}\n"
                   for t in T)
    p.write_text("Time,Vibe,Roll,Noise\n" + rows)
    st = Store()
    rid = st.open_file(str(p)).id
    items = st.first_changes([], [rid], 10.0, 11.0)
    changed = [x["name"] for x in items if x["status"] == "changed"]
    assert changed[:2] == ["Vibe", "Roll"] and "Noise" not in changed
    lg = st.lag_between(f"{rid}/Vibe", f"{rid}/Roll", 5, 15)
    assert lg["status"] == "ok"


def test_the_investigate_example_is_offered():
    from app.routes.fs import list_examples
    ids = {x["id"]: x["paths"] for x in list_examples()}
    assert "investigate" in ids and all(p.endswith(".csv") for p in ids["investigate"])
