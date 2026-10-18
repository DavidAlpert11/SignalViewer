"""T15: the video file is served in byte ranges (the player seeks with them)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
DATA = bytes(range(256)) * 4000            # ~1 MB of known bytes


@pytest.fixture
def vid(tmp_path):
    p = tmp_path / "flight.mp4"
    p.write_bytes(DATA)
    return str(p)


def get(path, rng=None):
    return client.get("/api/video", params={"path": path}, headers={"Range": rng} if rng else {})


def test_whole_file_says_it_can_do_ranges(vid):
    r = get(vid)
    assert r.status_code == 200 and r.content == DATA
    assert r.headers["accept-ranges"] == "bytes" and r.headers["content-type"] == "video/mp4"


@pytest.mark.parametrize("rng,start,end", [("bytes=0-99", 0, 99), ("bytes=1000-", 1000, len(DATA) - 1),
                                           ("bytes=-500", len(DATA) - 500, len(DATA) - 1),
                                           ("bytes=10-99999999", 10, len(DATA) - 1)])
def test_ranges(vid, rng, start, end):
    r = get(vid, rng)
    assert r.status_code == 206
    assert r.content == DATA[start:end + 1]
    assert r.headers["content-range"] == f"bytes {start}-{end}/{len(DATA)}"
    assert int(r.headers["content-length"]) == end - start + 1


@pytest.mark.parametrize("rng", ["bytes=999999999-", "bytes=50-10", "lines=1-2", "bytes=-"])
def test_unsatisfiable_range(vid, rng):
    r = get(vid, rng)
    assert r.status_code == 416 and r.headers["content-range"] == f"bytes */{len(DATA)}"


def test_not_a_video_and_missing_file(tmp_path):
    p = tmp_path / "data.csv"
    p.write_text("t,v\n")
    r = get(str(p))
    assert r.status_code == 400 and "Not a video" in r.json()["detail"]
    r = get(str(tmp_path / "gone.webm"))
    assert r.status_code == 404 and "not found" in r.json()["detail"]
