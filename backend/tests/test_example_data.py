"""Owner, 2026-11-18: the packages carry no heavy example recordings - svcore/example_data writes them on first use.

The generators must write the recordings in git (the demos, the docs and the tests rely on their numbers), and
an installation without them must still offer and open every example."""
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from svcore import example_data  # noqa: E402

EXAMPLES = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "examples"))
client = TestClient(app)


def _same(a: str, b: str) -> bool:
    """The same recording. A CSV byte for byte (its values are rounded as they are written); a binary file
    (.bin, .parquet, .mat) read back by the app: the same signals, the same times and values to the precision
    the file keeps - on Windows the math library's last bit differs from Linux, and so do the bytes (CI,
    2026-11-18); a .mat's header also carries its creation date."""
    x, y = open(a, "rb").read(), open(b, "rb").read()
    if x == y:
        return True
    if a.endswith(".csv"):
        return False
    import numpy as np
    import signalviewer as sv
    ra, rb = sv.load(a), sv.load(b)
    if list(ra.signals) != list(rb.signals):
        return False
    for n in ra.signals:
        (ta, ya), (tb, yb) = ra.signal(n), rb.signal(n)
        if ta.shape != tb.shape or not np.allclose(ta, tb, rtol=1e-12, atol=1e-9):
            return False
        if not np.allclose(ya, yb, rtol=1e-5, atol=1e-6, equal_nan=True):        # float32 fields: ~7 digits
            return False
    return True


def test_every_generated_file_is_in_git_and_written_again_the_same(tmp_path):
    assert example_data.REPO_EXAMPLES == EXAMPLES
    for rel in example_data.GENERATED:
        assert os.path.isfile(os.path.join(EXAMPLES, rel)), rel
    example_data.write(list(example_data.GENERATED), str(tmp_path))
    differ = [r for r in example_data.GENERATED if not _same(os.path.join(EXAMPLES, r), str(tmp_path / r))]
    assert differ == [], "the generators no longer write the recordings in git: run tools/make_*.py and commit"


def test_an_installation_without_them_offers_and_opens_every_example(monkeypatch, tmp_path):
    from app.routes import fs as m
    shipped = tmp_path / "shipped"                                     # what a package carries
    shutil.copytree(EXAMPLES, shipped, ignore=lambda d, names: [
        n for n in names if os.path.relpath(os.path.join(d, n), EXAMPLES).replace(os.sep, "/") in example_data.GENERATED])
    assert not (shipped / "copter_flight.bin").exists() and (shipped / "bench" / "checks.json").exists()
    monkeypatch.setattr(m, "EXAMPLES", str(shipped))
    monkeypatch.setattr(m, "EXAMPLES_MADE", str(tmp_path / "made"))
    listed = client.get("/api/examples").json()
    assert [x["id"] for x in listed] == [e["id"] for e in m.EXAMPLE_SETS]        # every card is still offered
    for ex in listed:
        r = client.post(f"/api/examples/{ex['id']}/prepare")
        assert r.status_code == 200, r.text
        assert r.json()["paths"] == ex["paths"] and all(os.path.isfile(p) for p in ex["paths"]), ex["id"]
    made = tmp_path / "made"
    assert (made / "folder_of_flights" / "measures.json").exists()             # the small files beside them
    assert (made / "bench" / "checks.json").exists() and (made / "sim_vs_flight" / "tolerances.json").exists()
    assert _same(os.path.join(EXAMPLES, "copter_flight.bin"), str(made / "copter_flight.bin"))
    assert client.post("/api/examples/nope/prepare").status_code == 404
