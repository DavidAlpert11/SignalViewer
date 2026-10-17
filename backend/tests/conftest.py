"""Test setup: Starlette's TestClient sends 'Host: testserver'. The real server accepts only
loopback names (see LocalOnlyMiddleware), so the tests add that one name on purpose."""
import os

os.environ.setdefault("SV_ALLOWED_HOSTS", "testserver")

# T38: the tests' error log goes to a temporary folder, not the developer's ~/.signalviewer/logs
import tempfile  # noqa: E402

os.environ.setdefault("SV_LOG_DIR", tempfile.mkdtemp(prefix="sv-test-logs-"))
