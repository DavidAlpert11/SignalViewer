"""T38: errors are kept in a local log and Help > "Copy error details" gives the text to report."""
import os
import re
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app import crashlog  # noqa: E402
from app.main import app  # noqa: E402
from app.store import store  # noqa: E402
from app.version import __version__  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def _log_text():
    for h in crashlog.logging.getLogger("signalviewer").handlers:
        h.flush()
    with open(crashlog.LOG_FILE, encoding="utf-8") as f:
        return f.read()


def test_version_is_the_one_build_bat_releases():
    m = re.search(r"^set VERSION=([0-9.]+)", open(os.path.join(ROOT, "build.bat")).read(), re.M)
    assert m and m.group(1) == __version__, "change app/version.py together with build.bat"


def test_log_file_is_in_the_test_folder_not_the_users():
    assert "sv-test-logs-" in crashlog.LOG_FILE
    assert os.path.isfile(crashlog.LOG_FILE)


def test_unexpected_error_in_a_request_is_readable_and_logged(monkeypatch):
    def boom():
        raise RuntimeError("probe 4711")
    monkeypatch.setattr(store, "list", boom)
    r = TestClient(app, raise_server_exceptions=False).get("/api/runs")
    assert r.status_code == 500
    assert "probe 4711" in r.json()["detail"] and "Copy error details" in r.json()["detail"]
    text = _log_text()
    assert "unexpected error in GET /api/runs" in text and "RuntimeError: probe 4711" in text   # with the traceback


def test_ui_errors_are_logged_and_limited(monkeypatch):
    c = TestClient(app)
    assert c.post("/api/client-error", json={"message": "probe UI 0815", "stack": "at draw (TimeChart.tsx:12)",
                                             "where": "window.onerror"}).json()["logged"] is True
    assert "UI error (window.onerror): probe UI 0815" in _log_text()
    monkeypatch.setattr(crashlog, "_ui_reports", crashlog.UI_REPORTS_MAX)
    assert c.post("/api/client-error", json={"message": "one too many"}).json()["logged"] is False


def test_error_in_a_thread_is_logged():
    def work():
        raise ValueError("probe thread 2718")
    t = threading.Thread(target=work, name="probe-thread")
    t.start()
    t.join()
    text = _log_text()
    assert "unhandled error in thread probe-thread" in text and "probe thread 2718" in text


def test_diagnostics_has_version_system_and_the_end_of_the_log():
    TestClient(app).post("/api/client-error", json={"message": "probe diag 1618"})
    d = TestClient(app).get("/api/diagnostics", params={"ui": __version__}).json()
    assert d["version"] == __version__
    assert d["text"].startswith(f"Signal Viewer {__version__}")
    assert "System:" in d["text"] and "Python:" in d["text"] and "probe diag 1618" in d["text"]


def test_tail_starts_at_a_whole_line(tmp_path):
    p = tmp_path / "x.log"
    p.write_text("".join(f"line {i}\n" for i in range(5000)))
    tail = crashlog._tail(str(p), 1000)
    assert tail.startswith("line ") and len(tail) < 1000
