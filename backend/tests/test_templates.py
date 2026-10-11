"""Template files: one JSON per template, version-1 migration, import / export, validation."""
import json
import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
from fastapi.testclient import TestClient  # noqa: E402

import app.prefs as prefs  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

TAB = {"name": "T", "rows": 1, "cols": 1, "plots": [{"title": "P", "signals": [{"name": "Speed", "slot": "main"}]}]}


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "APP_DIR", str(tmp_path))
    monkeypatch.setattr(prefs, "TEMPLATE_DIR", str(tmp_path / "templates"))
    return tmp_path


def tpl(name, **kw):
    return {"version": 2, "name": name, "slots": [{"id": "main", "name": "File"}], "tabs": [TAB], **kw}


def test_save_list_replace_delete(home):
    a = client.post("/api/templates", json={"template": tpl("Pressure check")}).json()["template"]
    assert a["id"] == "Pressure-check" and os.path.isfile(home / "templates" / "Pressure-check.json")
    # a new template with a taken name gets a free id; saving with its id replaces it
    b = client.post("/api/templates", json={"template": tpl("Pressure check"), "replace": False}).json()["template"]
    assert b["id"] == "Pressure-check-2"
    client.post("/api/templates", json={"template": {**a, "description": "edited"}})
    r = client.get("/api/templates").json()
    assert r["folder"].endswith("templates")
    by = {x["id"]: x for x in r["templates"]}
    assert by["Pressure-check"]["description"] == "edited" and len(by) == 2
    client.delete("/api/templates/Pressure-check-2")
    assert [x["id"] for x in client.get("/api/templates").json()["templates"]] == ["Pressure-check"]


def test_collection_and_hebrew_names(home):
    c = client.post("/api/templates", json={"template": {"version": 2, "name": "סקירה מלאה", "slots": [{"id": "main", "name": "קובץ"}],
                                                          "tabs": [], "includes": ["bi-ap-attitude", "Pressure-check"]}}).json()["template"]
    assert c["id"] == "סקירה-מלאה" and c["includes"] == ["bi-ap-attitude", "Pressure-check"]
    assert client.post("/api/templates", json={"template": {"version": 2, "name": "x", "slots": [{"id": "m", "name": "f"}], "tabs": []}}).status_code == 400


def test_version1_file_is_migrated(home):
    (home / "templates.json").write_text(json.dumps([{"name": "Old view", "rows": 2, "cols": 1, "plots": TAB["plots"] * 2}]), encoding="utf-8")
    r = client.get("/api/templates").json()["templates"]
    assert len(r) == 1 and r[0]["version"] == 2 and r[0]["tabs"][0]["rows"] == 2 and r[0]["slots"][0]["id"] == "main"
    assert not (home / "templates.json").exists() and (home / "templates.json.migrated").exists()


def test_export_import_and_bad_files(home, tmp_path):
    client.post("/api/templates", json={"template": tpl("A")})
    client.post("/api/templates", json={"template": tpl("B")})
    out = tmp_path / "share.json"
    client.post("/api/templates/export", json={"path": str(out), "ids": ["A", "B"]})
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [t["name"] for t in data["templates"]] == ["A", "B"] and "file" not in data["templates"][0]
    imp = client.post("/api/templates/import", json={"path": str(out)}).json()["templates"]
    assert [t["id"] for t in imp] == ["A-2", "B-2"]                      # imported next to the originals
    bad = tmp_path / "bad.json"
    bad.write_text('{"hello": 1}', encoding="utf-8")
    assert client.post("/api/templates/import", json={"path": str(bad)}).status_code == 400
    (home / "templates" / "broken.json").write_text("{not json", encoding="utf-8")
    assert any(t.get("broken") for t in client.get("/api/templates").json()["templates"])


def test_choose_templates_folder(home, tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "DEFAULT_TEMPLATE_DIR", str(home / "templates"))
    client.post("/api/templates", json={"template": tpl("Kept")})
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "Kept.json").write_text('{"keep": "theirs"}', encoding="utf-8")   # same name there: not overwritten
    client.post("/api/templates", json={"template": tpl("Second")})
    r = client.post("/api/templates/folder", json={"path": str(shared)}).json()
    assert r["folder"] == str(shared) and r["copied"] == 1 and not r["default"]
    assert (shared / "Kept.json").read_text(encoding="utf-8") == '{"keep": "theirs"}'
    # remembered, and used for listing / saving from now on
    assert json.loads((home / "settings.json").read_text())["templateDir"] == str(shared)
    client.post("/api/templates", json={"template": tpl("New there")})
    assert (shared / "New-there.json").is_file()
    assert client.get("/api/templates").json()["folder"] == str(shared)
    # back to the default folder; old files stay where they were
    r = client.post("/api/templates/folder", json={"path": None}).json()
    assert r["default"] and r["folder"] == str(home / "templates")
    assert "templateDir" not in json.loads((home / "settings.json").read_text())


def test_unusable_templates_folder_is_refused(home, tmp_path):
    blocker = tmp_path / "a_file"
    blocker.write_text("x")
    assert client.post("/api/templates/folder", json={"path": str(blocker / "sub")}).status_code == 400
