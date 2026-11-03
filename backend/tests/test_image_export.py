"""A plot's image (owner, 2026-11-03): PNG, a high-resolution PNG for a report (twice the pixels or
more), SVG, and an interactive HTML page of the plot alone."""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "uav_flight.csv")


def _png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", head[16:24])


def test_png_high_resolution_and_html(tmp_path):
    run = client.post("/api/files/open", json={"paths": [EX]}).json()["opened"][0]
    try:
        plot = {"mode": "time", "title": "Speed", "signals": [{"id": f"{run['id']}/GroundSpeed [m/s]", "label": "GroundSpeed", "color": "#3D8BFD",
                                                                 "width": 1.5, "scale": 1, "offset": 0}]}
        post = lambda name, **k: client.post("/api/export/image", json={"path": str(tmp_path / name), "plot": plot, **k})
        assert post("a.png").status_code == 200
        assert post("b.png", scale=2).status_code == 200
        w1, h1 = _png_size(tmp_path / "a.png")
        w2, h2 = _png_size(tmp_path / "b.png")
        assert abs(w2 - 2 * w1) <= 4 and abs(h2 - 2 * h1) <= 4
        r = post("c", format="html")
        assert r.status_code == 200 and r.json()["path"].endswith(".html")
        page = (tmp_path / "c.html").read_text(encoding="utf-8")
        assert "<canvas" in page or 'class="canvas"' in page
        assert "GroundSpeed" in page
        assert post("d.gif", format="gif").status_code == 400
    finally:
        client.delete(f"/api/runs/{run['id']}")
