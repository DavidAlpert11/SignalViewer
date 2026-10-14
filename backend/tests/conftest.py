"""Test setup: Starlette's TestClient sends 'Host: testserver'. The real server accepts only
loopback names (see LocalOnlyMiddleware), so the tests add that one name on purpose."""
import os

os.environ.setdefault("SV_ALLOWED_HOSTS", "testserver")
