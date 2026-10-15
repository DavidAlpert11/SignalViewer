"""run.py from the source folder serves a UI built from the CURRENT sources (ensure_ui)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import run  # noqa: E402


@pytest.fixture
def front(tmp_path, monkeypatch):
    f = tmp_path / "frontend"
    (f / "src").mkdir(parents=True)
    (f / "src" / "App.tsx").write_text("a")
    (f / "package.json").write_text("{}")
    monkeypatch.setattr(run, "FRONT", str(f))
    monkeypatch.setattr(run, "LOCAL_DIST", str(f / ".local-dist"))
    monkeypatch.delenv("SV_DIST", raising=False)
    monkeypatch.delenv("SV_NO_BUILD", raising=False)
    return f


def stamp(f, h):
    (f / ".local-dist").mkdir(exist_ok=True)
    (f / ".local-dist" / run.STAMP).write_text(json.dumps({"source": h}))


def test_hash_follows_the_sources(front):
    h = run.ui_source_hash(str(front))
    assert run.ui_source_hash(str(front)) == h
    (front / "src" / "App.tsx").write_text("b")
    assert run.ui_source_hash(str(front)) != h
    (front / "src" / "New.tsx").write_text("c")                     # a new file counts too
    assert len({h, run.ui_source_hash(str(front))}) == 2


def test_up_to_date_local_build_is_served_without_building(front, monkeypatch):
    stamp(front, run.ui_source_hash(str(front)))
    monkeypatch.setattr(run, "_build_ui", lambda h: pytest.fail("must not build"))
    run.ensure_ui()
    assert os.environ.pop("SV_DIST") == str(front / ".local-dist")


def test_changed_sources_build_once(front, monkeypatch):
    stamp(front, "old")
    built = []
    monkeypatch.setattr(run, "committed_dist_is_current", lambda: False)
    monkeypatch.setattr(run, "_build_ui", lambda h: built.append(h) or True)
    run.ensure_ui()
    assert built == [run.ui_source_hash(str(front))] and os.environ.pop("SV_DIST") == str(front / ".local-dist")


def test_current_committed_ui_or_no_build_keeps_the_default(front, monkeypatch):
    monkeypatch.setattr(run, "_build_ui", lambda h: pytest.fail("must not build"))
    monkeypatch.setattr(run, "committed_dist_is_current", lambda: True)
    run.ensure_ui()
    assert "SV_DIST" not in os.environ                               # the tracked frontend/dist
    monkeypatch.setattr(run, "committed_dist_is_current", lambda: False)
    run.ensure_ui(skip=True)
    assert "SV_DIST" not in os.environ


def test_without_npm_it_says_so_and_keeps_the_last_ui(front, monkeypatch, capsys):
    monkeypatch.setattr(run, "committed_dist_is_current", lambda: False)
    monkeypatch.setattr(run.shutil, "which", lambda name: None)
    run.ensure_ui()
    assert "SV_DIST" not in os.environ and "Node.js" in capsys.readouterr().out


def test_an_explicit_ui_folder_wins(front, monkeypatch):
    monkeypatch.setenv("SV_DIST", "/somewhere")
    monkeypatch.setattr(run, "_build_ui", lambda h: pytest.fail("must not build"))
    run.ensure_ui(force=True)
    assert os.environ["SV_DIST"] == "/somewhere"


def test_a_dist_built_after_the_sources_counts_as_current(front, monkeypatch):
    """`npm run build` by hand / in CI writes frontend/dist after the sources: no second build."""
    (front / "dist").mkdir()
    (front / "dist" / "index.html").write_text("<html>")
    old = os.path.getmtime(front / "dist" / "index.html") - 100
    os.utime(front / "src" / "App.tsx", (old, old)); os.utime(front / "package.json", (old, old))
    assert run.committed_dist_is_current()
    (front / "src" / "App.tsx").write_text("changed later")                      # a newer source: not current
    new = os.path.getmtime(front / "dist" / "index.html") + 100
    os.utime(front / "src" / "App.tsx", (new, new))
    monkeypatch.setattr(run, "_git", lambda *a: (_ for _ in ()).throw(OSError("no git")))
    assert run.committed_dist_is_current()                                       # (no git: trusted)
    monkeypatch.setattr(run, "_git", lambda *a: " M frontend/src/App.tsx" if a[0] == "status" else "")
    assert not run.committed_dist_is_current()
