"""CC20 (advocate N4): a derived signal named by its formula keeps a readable name - a long formula is cut, the
whole formula stays its formula; a name the user gives is kept as given."""
import numpy as np

from app.store import AUTO_NAME_MAX, Store


def test_a_long_formula_is_not_a_name(tmp_path):
    p = tmp_path / "r.csv"
    t = np.arange(0, 1, 0.01)
    p.write_text("Time,A,B\n" + "".join(f"{x:.2f},{x:.3f},{2 * x:.3f}\n" for x in t))
    st = Store()
    lr = st.open_file(str(p))
    a, b = f"{lr.id}/A", f"{lr.id}/B"
    expr = " + ".join(["v0 * 2", "v1 / 3", "sin(v0)", "cos(v1)", "v0 ** 2", "abs(v1 - v0)", "sqrt(abs(v0))"])
    d = st.add_derived("expr", [a, b], {"expr": expr, "text": expr})
    assert len(d.name) <= AUTO_NAME_MAX and d.name.endswith("…")
    assert d.formula(st.short_name) == expr                       # the whole formula is still its formula
    short = st.add_derived("expr", [a], {"expr": "v0 * 2", "text": "A * 2"})
    assert short.name == "A * 2"
    named = st.add_derived("expr", [a, b], {"expr": expr, "text": expr}, name="x" * 80)
    assert named.name == "x" * 80                                  # the user's own name: as given
