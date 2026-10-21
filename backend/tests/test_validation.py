"""A4: the numerical validation cases (svcore/validation.py) - every one within its tolerance."""
import pytest

from svcore.validation import CASES, Result


@pytest.mark.parametrize("c", CASES, ids=[c.id for c in CASES])
def test_validation_case(c):
    r: Result = c.run()
    assert r.ok, f"{c.id} {c.title}: expected {r.expected!r}, measured {r.measured!r} (tolerance {r.tol!r})"


def test_case_ids_are_unique_and_in_order():
    ids = [c.id for c in CASES]
    assert ids == sorted(set(ids))


def test_cli_validate(capsys, tmp_path):
    import json

    from signalviewer.cli import main
    junit = tmp_path / "v.xml"
    assert main(["validate", "--json", "--junit", str(junit)]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == len(CASES) and all(r["ok"] for r in rows)
    assert 'failures="0"' in junit.read_text(encoding="utf-8")


def test_the_validation_page_is_current():
    """docs/validation.md is written by tools/make_validation_doc.py: regenerate it when a case changes."""
    import os
    import sys
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(root, "tools"))
    from make_validation_doc import render
    with open(os.path.join(root, "docs", "validation.md"), encoding="utf-8") as fh:
        assert fh.read() == render(), "run: python tools/make_validation_doc.py"


def test_python_dash_m_signalviewer_cli_runs():
    """A6: `python -m signalviewer.cli` ran nothing and exited 0, silently."""
    import os
    import subprocess
    import sys
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run([sys.executable, "-m", "signalviewer.cli", "templates"], cwd=here,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and r.stdout.strip()
