"""Damaged, empty, unsupported and mislabelled files: each gets a clear reason (and a code the UI
translates), never a raw exception, and never stops the other files of the same open."""
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import store  # noqa: E402

client = TestClient(app)
SAMPLE_ULG = os.path.join(os.path.dirname(__file__), "data", "sample.ulg")


@pytest.fixture(autouse=True)
def _clean():
    yield
    for rid in list(store.order):
        store.remove(rid)


def _write(tmp_path, name, data: bytes):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


CASES = [
    ("empty.csv", b"", "empty"),
    ("empty.mat", b"", "empty"),
    ("empty.bin", b"", "empty"),
    ("header.csv", b"a,b\n", "csvNoRows"),
    ("words.csv", b"name,city\nx,y\nz,w\n", "csvNoNumbers"),
    ("random.csv", bytes(range(256)) * 50, "binaryText"),
    ("random.mat", b"\x01\x02junk" * 500, "badMat"),
    ("sheet.xlsx", b"PK\x03\x04", "unsupported"),
    ("noext", b"1,2\n3,4\n", "unsupported"),
    ("matlab.csv", b"MATLAB 5.0 MAT-file, junk", "wrongExt"),
]


@pytest.mark.parametrize("name,data,code", CASES)
def test_bad_file_has_a_clear_reason(tmp_path, name, data, code):
    p = _write(tmp_path, name, data)
    r = client.post("/api/files/open", json={"paths": [p]}).json()
    assert r["opened"] == []
    err = r["errors"][0]
    assert err["code"] == code, err
    assert "Unexpected error" not in err["message"]


def test_flight_log_with_wrong_extension(tmp_path):
    p = str(tmp_path / "flight.csv")
    shutil.copy(SAMPLE_ULG, p)
    err = client.post("/api/files/open", json={"paths": [p]}).json()["errors"][0]
    assert err["code"] == "wrongExt" and err["params"]["real"] == ".ulg"


def test_one_bad_file_does_not_stop_the_others(tmp_path):
    bad = _write(tmp_path, "bad.mat", b"not a mat file at all" * 10)
    good = _write(tmp_path, "good.csv", b"t,v\n0,1\n1,2\n2,3\n")
    r = client.post("/api/files/open", json={"paths": [bad, good]}).json()
    assert [o["name"] for o in r["opened"]] == ["good.csv"]
    assert r["errors"][0]["code"] == "badMat"


def test_utf16_text_is_not_called_binary(tmp_path):
    p = _write(tmp_path, "wide.csv", "t,v\n0,1\n1,2\n".encode("utf-16"))
    r = client.post("/api/files/open", json={"paths": [p]}).json()
    assert all(e.get("code") != "binaryText" for e in r["errors"])


def test_failed_file_is_not_added_to_recent(tmp_path):
    p = _write(tmp_path, "nothing.csv", b"")
    client.post("/api/files/open", json={"paths": [p]})
    paths = [x["path"] for x in client.get("/api/recent").json()["items"]]
    assert os.path.abspath(p) not in paths


def test_upload_reports_skipped_types():
    r = client.post("/api/files/upload", files=[("files", ("a.xlsx", b"PK", "application/octet-stream")),
                                                 ("files", ("b.csv", b"t,v\n0,1\n1,2\n", "text/csv"))]).json()
    assert r["skipped"] == ["a.xlsx"]
    assert len(r["paths"]) == 1
