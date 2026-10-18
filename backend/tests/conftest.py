"""Test setup: Starlette's TestClient sends 'Host: testserver'. The real server accepts only
loopback names (see LocalOnlyMiddleware), so the tests add that one name on purpose."""
import os

os.environ.setdefault("SV_ALLOWED_HOSTS", "testserver")

# T38: the tests' error log goes to a temporary folder, not the developer's ~/.signalviewer/logs
import tempfile  # noqa: E402

os.environ.setdefault("SV_LOG_DIR", tempfile.mkdtemp(prefix="sv-test-logs-"))

# F15: every app file (recent.json, autosave.json, uploads, push.json, fleet.sqlite, templates...)
# goes to a temporary home, not the developer's real ~/.signalviewer. The app folder is computed
# from the home at import, so this must run before any test imports the app. (The e2e servers get
# a home of their own the same way.)
os.environ.setdefault("SV_TEST_REAL_HOME", os.path.expanduser("~"))   # for test_app_folder
_home = tempfile.mkdtemp(prefix="sv-test-home-")
os.environ["HOME"] = _home
os.environ["USERPROFILE"] = _home       # Windows: expanduser reads USERPROFILE
os.environ.setdefault("SV_CACHE_DIR", os.path.join(_home, ".signalviewer", "cache"))
