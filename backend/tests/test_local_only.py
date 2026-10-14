"""The API answers only to loopback names (defence against DNS rebinding and other web sites)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from app.main import app, _hostname

client = TestClient(app, base_url="http://127.0.0.1")


def test_hostname_parsing():
    assert _hostname("127.0.0.1:8765") == "127.0.0.1"
    assert _hostname("localhost") == "localhost"
    assert _hostname("[::1]:8765") == "::1"
    assert _hostname("http://localhost:5173") == "localhost"
    assert _hostname("EVIL.example:80") == "evil.example"


def test_loopback_hosts_are_served():
    for host in ("127.0.0.1:8765", "localhost:8765", "[::1]:8765", "localhost:5173"):
        assert client.get("/api/runs", headers={"Host": host}).status_code == 200, host


def test_rebinding_host_is_refused_on_read_and_write():
    r = client.post("/api/fs/list", json={"path": "/"}, headers={"Host": "evil.example:8765"})
    assert r.status_code == 403 and "localhost" in r.json()["detail"]
    r = client.post("/api/save/text", json={"path": "x.csv", "content": "x", "ext": ".csv"},
                    headers={"Host": "evil.example"})
    assert r.status_code == 403


def test_foreign_origin_is_refused_even_with_a_loopback_host():
    for origin in ("http://evil.example", "null", "https://127.0.0.1.evil.example"):
        r = client.post("/api/fs/list", json={"path": "/"}, headers={"Origin": origin})
        assert r.status_code == 403, origin


def test_same_origin_and_dev_server_origin_are_served():
    for origin in ("http://127.0.0.1:8765", "http://localhost:5173"):
        r = client.post("/api/fs/list", json={"path": "/"}, headers={"Origin": origin})
        assert r.status_code == 200, origin


def test_extra_names_can_be_allowed_on_purpose(monkeypatch):
    monkeypatch.setenv("SV_ALLOWED_HOSTS", "testserver,myhost")
    assert client.get("/api/runs", headers={"Host": "myhost:1"}).status_code == 200
