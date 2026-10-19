"""T47: a signal on the plot's second (right) value axis - passed to every report format."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.report import plot_data, render_figure  # noqa: E402
from app.store import store  # noqa: E402

client = TestClient(app)
EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "uav_flight.csv")


def test_right_axis_in_reports_and_images(tmp_path):
    run = client.post("/api/files/open", json={"paths": [EX]}).json()["opened"][0]
    try:
        sig = lambda n, **k: {"id": f"{run['id']}/{n}", "label": n, "color": "#3D8BFD", "width": 1.5, "scale": 1, "offset": 0, **k}
        plot = {"mode": "time", "title": "", "signals": [sig("GroundSpeed [m/s]"), sig("Battery [V]", axis="right")]}
        pdata = plot_data(store, plot, for_html=True)
        assert [s.get("axis") for s in pdata["signals"]] == [None, "right"]
        fig = render_figure(plot_data(store, plot, for_html=False))
        assert len(fig.axes) == 2                                   # matplotlib: a twin axis
        import matplotlib.pyplot as plt
        plt.close(fig)
        fig = render_figure(plot_data(store, {**plot, "signals": [sig("GroundSpeed [m/s]")]}, for_html=False))
        assert len(fig.axes) == 1                                   # none on the right: one axis
        plt.close(fig)
        body = lambda fmt: {"path": str(tmp_path / f"r.{fmt}"), "format": fmt, "tabs": [{"name": "T", "plots": [plot]}]}
        for fmt in ("html", "pdf", "docx"):
            assert client.post("/api/report", json=body(fmt)).status_code == 200
        assert '"axis":"right"' in (tmp_path / "r.html").read_text(encoding="utf-8")
        assert client.post("/api/export/image", json={"path": str(tmp_path / "i"), "format": "png", "plot": plot}).status_code == 200
    finally:
        client.delete(f"/api/runs/{run['id']}")
