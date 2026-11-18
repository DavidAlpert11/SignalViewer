"""Owner, 2026-11-18: the packages carry no heavy example recordings - svcore/example_data writes them on first use.

The generators must write exactly the files in git (the demos, the docs and the tests rely on their numbers), and
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
    x, y = open(a, "rb").read(), open(b, "rb").read()
    if a.endswith(".mat"):                         # a MAT file's text header carries its creation date
        x, y = x[116:], y[116:]
    return x == y


def test_every_generated_file_is_in_git_and_written_the_same(tmp_path):
    assert example_data.REPO_EXAMPLES == EXAMPLES
    for rel in example_data.GENERATED:
        assert os.path.isfile(os.path.join(EXAMPLES, rel)), rel
    example_data.write(list(example_data.GENERATED), str(tmp_path))
    differ = [r for r in example_data.GENERATED if not _same(os.path.join(EXAMPLES, r), str(tmp_path / r))]
    assert differ == [], "the generators no longer write the files in git: run tools/make_*.py and commit"


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
