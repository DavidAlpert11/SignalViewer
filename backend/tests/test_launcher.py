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
    monkeypatch.setattr(run, "DIST", str(f / "dist"))
    monkeypatch.delenv("SV_DIST", raising=False)
    monkeypatch.delenv("SV_NO_BUILD", raising=False)
    return f


def stamp(f, h):
    (f / "dist").mkdir(exist_ok=True)
    (f / "dist" / "index.html").write_text("<html>")
    (f / "dist" / run.STAMP).write_text(json.dumps({"source": h}))


def _times(front, dist_newer: bool):
    """dist/index.html (built by hand, no stamp) newer - or older - than every UI source, by 100 s."""
    (front / "dist").mkdir(exist_ok=True)
    (front / "dist" / "index.html").write_text("<html>")
    base = os.path.getmtime(front / "dist" / "index.html")
    src = base - 100 if dist_newer else base + 100
    for f in (front / "src" / "App.tsx", front / "package.json"):
        os.utime(f, (src, src))


def test_hash_follows_the_sources(front):
    h = run.ui_source_hash(str(front))
    assert run.ui_source_hash(str(front)) == h
    (front / "src" / "App.tsx").write_text("b")
    assert run.ui_source_hash(str(front)) != h
    (front / "src" / "New.tsx").write_text("c")                     # a new file counts too
    assert len({h, run.ui_source_hash(str(front))}) == 2


def test_an_up_to_date_ui_is_served_without_building(front, monkeypatch):
    stamp(front, run.ui_source_hash(str(front)))
    monkeypatch.setattr(run, "_build_ui", lambda h: pytest.fail("must not build"))
    run.ensure_ui()
    assert "SV_DIST" not in os.environ                               # frontend/dist, as the server's default


def test_changed_sources_build_once(front, monkeypatch):
    stamp(front, "old")
    built = []
    monkeypatch.setattr(run, "_build_ui", lambda h: built.append(h) or True)
    run.ensure_ui()
    assert built == [run.ui_source_hash(str(front))]


def test_a_fresh_clone_builds_the_ui(front, monkeypatch):
    """FR10: frontend/dist is not in git - the first run builds it."""
    built = []
    monkeypatch.setattr(run, "_build_ui", lambda h: built.append(h) or True)
    run.ensure_ui()
    assert built == [run.ui_source_hash(str(front))]


def test_a_build_by_hand_counts_when_built_after_the_sources(front, monkeypatch):
    built = []
    monkeypatch.setattr(run, "_build_ui", lambda h: built.append(h) or True)
    _times(front, dist_newer=True)
    run.ensure_ui()
    assert built == []
    _times(front, dist_newer=False)
    run.ensure_ui()
    assert len(built) == 1


def test_no_build_keeps_what_is_there_and_says_when_nothing_is(front, monkeypatch, capsys):
    monkeypatch.setattr(run, "_build_ui", lambda h: pytest.fail("must not build"))
    run.ensure_ui(skip=True)
    assert "not built" in capsys.readouterr().out
    stamp(front, "old")
    run.ensure_ui(skip=True)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("built", [True, False])
def test_without_npm_it_says_so(front, monkeypatch, capsys, built):
    if built:
        stamp(front, "old")
    monkeypatch.setattr(run.shutil, "which", lambda name: None)
    run.ensure_ui()
    out = capsys.readouterr().out
    assert "SV_DIST" not in os.environ and "Node.js" in out
    assert ("last build" in out) == built and ("installer" in out) == (not built)


def test_an_explicit_ui_folder_wins(front, monkeypatch):
    monkeypatch.setenv("SV_DIST", "/somewhere")
    monkeypatch.setattr(run, "_build_ui", lambda h: pytest.fail("must not build"))
    run.ensure_ui(force=True)
    assert os.environ["SV_DIST"] == "/somewhere"


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
