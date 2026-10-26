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


def _times(front, dist_newer: bool):
    """dist/index.html newer (or older) than every UI source, by 100 s."""
    (front / "dist").mkdir(exist_ok=True)
    (front / "dist" / "index.html").write_text("<html>")
    base = os.path.getmtime(front / "dist" / "index.html")
    src = base - 100 if dist_newer else base + 100
    for f in (front / "src" / "App.tsx", front / "package.json"):
        os.utime(f, (src, src))


def _fake_git(monkeypatch, src_dirty="", dist_dirty="", last_dist="abc", src_commits_after=""):
    def git(*a):
        if a[0] == "status":
            return dist_dirty if a[-1] == "frontend/dist" else src_dirty
        if a[:2] == ("log", "-1"):
            return last_dist
        return src_commits_after                     # log <last_dist>..HEAD -- <sources>
    monkeypatch.setattr(run, "_git", git)


def test_git_history_decides_not_file_times(front, monkeypatch):
    """T38: a dist rewritten by git checkout / pull / clone has a FRESH time but OLD contents."""
    _times(front, dist_newer=True)
    _fake_git(monkeypatch, src_commits_after="def456")              # sources committed after dist
    assert not run.committed_dist_is_current()                      # (was True: the old UI was served)
    _times(front, dist_newer=False)
    _fake_git(monkeypatch, src_commits_after="")                    # dist committed after the sources
    assert run.committed_dist_is_current()                          # a clone's file order does not matter


def test_local_build_by_hand_counts_when_built_after_the_sources(front, monkeypatch):
    """`npm run build` by hand (frontend/dist changed, not committed) or edited sources."""
    for dirty in ({"dist_dirty": " M frontend/dist/index.html"}, {"src_dirty": " M frontend/src/App.tsx"}):
        _fake_git(monkeypatch, src_commits_after="def456", **dirty)
        _times(front, dist_newer=True)
        assert run.committed_dist_is_current()
        _times(front, dist_newer=False)
        assert not run.committed_dist_is_current()


def test_without_git_the_committed_ui_is_trusted(front, monkeypatch):
    _times(front, dist_newer=False)
    monkeypatch.setattr(run, "_git", lambda *a: (_ for _ in ()).throw(OSError("no git")))
    assert run.committed_dist_is_current()



# ---- which engine shows the app (a blank window on offline computers with an old WebView2) ----

def test_the_engine_floor_matches_the_ui_build():
    """run.py's MIN_CHROMIUM and the UI's build target must name the same engine."""
    cfg = open(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "vite.config.ts"), encoding="utf-8").read()
    assert f'"chrome{run.MIN_CHROMIUM}"' in cfg and f'"firefox{run.MIN_FIREFOX}"' in cfg


def test_fallback_prefers_a_new_enough_edge_then_chrome_then_firefox():
    edge_old = ("Edge", "e.exe", "86.0.622.69")
    chrome = ("Chrome", "c.exe", "120.0.6099.71")
    ff = ("Firefox", "f.exe", "115.3.0")
    assert run.choose_fallback([ff, chrome, edge_old]) == chrome          # old Edge skipped
    assert run.choose_fallback([ff, ("Edge", "e.exe", "118.0.2088.46")])[0] == "Edge"
    assert run.choose_fallback([ff, edge_old]) == ff
    assert run.choose_fallback([edge_old, ("Firefox", "f.exe", "60.0")]) is None
    assert run.choose_fallback([("Chrome", "c.exe", "")]) is None           # version unknown: not trusted
    assert run.choose_fallback([]) is None


def test_an_old_webview2_is_a_reason_not_to_use_the_window(monkeypatch):
    import types
    monkeypatch.setitem(sys.modules, "webview", types.ModuleType("webview"))
    monkeypatch.setattr(run.sys, "platform", "win32")
    monkeypatch.setattr(run, "_unblock_windows_dlls", lambda: None)
    monkeypatch.setattr(run, "webview2_version", lambda: "86.0.622.38")
    assert "too old (86.0.622.38" in run.window_unavailable_reason()
    monkeypatch.setattr(run, "webview2_version", lambda: "")
    assert "not found" in run.window_unavailable_reason()
    monkeypatch.setattr(run, "webview2_version", lambda: "130.0.2849.56")
    assert run.window_unavailable_reason() == ""


def test_newest_version_and_folders(tmp_path):
    for d in ("86.0.622.38", "109.0.1518.140", "Installer", "SetupMetrics"):
        (tmp_path / d).mkdir()
    found = run._version_folders(str(tmp_path))
    assert sorted(found) == ["109.0.1518.140", "86.0.622.38"]
    assert run._newest(found) == "109.0.1518.140"          # by number, not as text
    assert run._newest(["0.0.0.0", ""]) == ""


def test_app_window_uses_its_own_profile_and_safe_graphics(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(run.subprocess, "Popen", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(run.os.path, "expanduser", lambda p: str(tmp_path))
    run.open_in("Edge", "msedge.exe", "http://127.0.0.1:5000", safe=True)
    cmd = calls[-1]
    assert "--app=http://127.0.0.1:5000" in cmd and "--disable-gpu" in cmd
    assert any(a.startswith("--user-data-dir=") and "browser-profile" in a for a in cmd)
    run.open_in("Firefox", "firefox.exe", "http://127.0.0.1:5000")
    assert calls[-1] == ["firefox.exe", "-new-window", "http://127.0.0.1:5000"]


def test_safe_graphics_adds_to_webview2_arguments(monkeypatch):
    monkeypatch.setenv("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--lang=he")
    run._safe_graphics_env()
    assert run.os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] == "--lang=he --disable-gpu --enable-unsafe-swiftshader"
    run._safe_graphics_env()                                 # twice: not added again
    assert run.os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"].count("--disable-gpu") == 1
