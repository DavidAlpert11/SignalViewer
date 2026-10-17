"""T36 (found by mypy): settings files of the wrong shape and template files that hold no
templates are refused in words, not with a server error."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import prefs  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "APP_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize("content", ["null", "[]", "42", '"text"'])
def test_settings_file_of_the_wrong_shape_gives_the_defaults(home, content):
    (home / "import_prefs.json").write_text(content)
    assert prefs._read("import_prefs.json", {}) == {}


def test_remembering_import_settings_survives_a_null_file(home, tmp_path):
    (home / "import_prefs.json").write_text("null")
    csv = tmp_path / "d" / "a.csv"
    csv.parent.mkdir()
    csv.write_text("t,v\n0,1\n")
    prefs.remember_import(str(csv), {"delimiter": ";"})       # crashed: 'NoneType' ... item assignment
    assert json.loads((home / "import_prefs.json").read_text())


@pytest.mark.parametrize("content", ['[1, 2]', '{"templates": null}', '{"templates": []}', '["a"]'])
def test_template_file_without_templates_is_refused_in_words(home, tmp_path, content):
    p = tmp_path / "t.json"
    p.write_text(content)
    with pytest.raises(ValueError, match="does not hold Signal Viewer templates"):
        prefs.import_templates(str(p))
