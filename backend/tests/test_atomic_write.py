"""O3: a save that fails in the middle (a crash, a full disk, an error while building) leaves the file
that was there untouched - sessions, templates, reports, settings were written in place, so a failure
left a cut or empty file where the good one was."""
import json
import os
import stat
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.atomic import atomic_open, atomic_path, atomic_write  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


class Boom(Exception):
    pass


def _leftovers(folder):
    return [n for n in os.listdir(folder) if ".tmp" in n]


def test_atomic_write_replaces_whole_or_not_at_all(tmp_path):
    p = tmp_path / "a.json"
    atomic_write(str(p), "old")
    with pytest.raises(Boom):
        with atomic_open(str(p)) as f:
            f.write("new, half")
            raise Boom()
    assert p.read_text() == "old" and _leftovers(tmp_path) == []
    atomic_write(str(p), b"\x00new")
    assert p.read_bytes() == b"\x00new"


def test_atomic_path_keeps_the_extension_the_link_and_the_mode(tmp_path):
    real = tmp_path / "r.pdf"
    real.write_bytes(b"old")
    os.chmod(real, 0o640)
    link = tmp_path / "link.pdf"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("no symbolic links here")
    with atomic_path(str(link)) as tmp:
        assert tmp.endswith(".pdf") and os.path.dirname(tmp) == str(tmp_path)
        open(tmp, "wb").write(b"new")
    assert link.is_symlink() and real.read_bytes() == b"new"
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(real).st_mode) == 0o640


def test_session_save_that_fails_keeps_the_old_session(tmp_path, monkeypatch):
    import app.routes.session as session
    p = tmp_path / "work.svsession"
    assert client.post("/api/session/save", json={"path": str(p), "state": {"a": 1}}).status_code == 200
    before = p.read_text()

    class HalfJson:
        def dump(self, obj, f, **kw):
            f.write('{"format": "signalviewer-session", "ver')     # cut by a crash / a full disk
            raise OSError(28, "No space left on device")
    monkeypatch.setattr(session, "json", HalfJson())
    with pytest.raises(OSError):
        client.post("/api/session/save", json={"path": str(p), "state": {"a": 2}})
    assert p.read_text() == before and json.loads(before)["a"] == 1
    assert _leftovers(tmp_path) == []


def test_report_that_fails_while_building_keeps_the_old_report(tmp_path, monkeypatch):
    import app.routes.export as export
    p = tmp_path / "r.html"
    p.write_text("<p>the report of yesterday</p>")
    def fails(*a, **k):
        raise KeyError("a signal")                                  # closed while the report was built
    monkeypatch.setattr(export.reports, "build_html", fails)
    r = client.post("/api/report", json={"path": str(p), "format": "html", "plots": []})
    assert r.status_code == 404
    assert p.read_text() == "<p>the report of yesterday</p>"      # was emptied: opened before building


def test_template_export_that_fails_keeps_the_old_file(tmp_path, monkeypatch):
    import app.routes.templates as templates
    from app import prefs
    t = prefs.save_template({"version": 2, "name": "O3 test", "slots": [{"id": "main", "name": "File"}], "tabs": [{"name": "A", "plots": []}]}, replace=False)
    p = tmp_path / "mine.json"
    p.write_text('{"kept": true}')

    class HalfJson:
        def dump(self, obj, f, **kw):
            f.write('{"tem')
            raise OSError(28, "No space left on device")
    monkeypatch.setattr(templates, "json", HalfJson())
    try:
        with pytest.raises(OSError):
            client.post("/api/templates/export", json={"path": str(p), "ids": [t["id"]]})
        assert p.read_text() == '{"kept": true}'
    finally:
        prefs.delete_template(t["id"])
