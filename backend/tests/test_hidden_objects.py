"""P6 (1.26): a hidden map object is not drawn in pictures, not part of the fitted box, and the offline pages
start with it hidden (their legend rows are buttons: click, Alt+click)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from app import mapimage, scene3d  # noqa: E402
from app.main import app  # noqa: E402
from app.store import store  # noqa: E402

client = TestClient(app)
EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "three_objects.csv")


def _spec(run, hide):
    s = lambda n: f"{run}/{n}"
    objs = [{"name": n, "color": c, "lat": s(f"{n}.lat"), "lon": s(f"{n}.lon"), "alt": s(f"{n}.alt"), **({"hidden": True} if n in hide else {})}
            for n, c in (("phys", "#0072B2"), ("nav", "#D55E00"), ("gps", "#009E73"))]
    return {"mode": "geo", "title": "t", "signals": [], "geo": {"objects": objs, "base": "offline", "cursor": None, "bounds": None},
            "scene": {"objects": objs}}


def test_hidden_objects_in_data_pictures_and_pages():
    run = client.post("/api/files/open", json={"paths": [EX]}).json()["opened"][0]["id"]
    try:
        md_all = mapimage.map_data(store, _spec(run, set()))
        md = mapimage.map_data(store, _spec(run, {"gps"}))
        assert [o["hidden"] for o in md["objects"]] == [False, False, True]          # kept, flagged
        page = mapimage.build_html(md)
        assert "svLegend" in page and '"hidden": true' in page.replace('"hidden":true', '"hidden": true')
        assert mapimage.render(md, "svg").count(b"gps") < mapimage.render(md_all, "svg").count(b"gps")
        sd = scene3d.scene_data(store, {**_spec(run, {"gps"}), "mode": "3d"})
        assert [o["hidden"] for o in sd["objects"]] == [False, False, True]
        assert "svLegend" in scene3d.build_html(sd, fallback_png=b"x")
    finally:
        client.delete(f"/api/runs/{run}")


def test_the_map_from_above_is_the_flat_picture_and_the_page_opens_from_above(monkeypatch):
    """P4: a Map on its From above camera (a 2D-era map) goes out as the flat map picture; the live page opens
    From above; any other camera is the 3D picture."""
    from app import report
    run = client.post("/api/files/open", json={"paths": [EX]}).json()["opened"][0]["id"]
    try:
        spec = {**_spec(run, set()), "mode": "3d"}
        monkeypatch.setattr(mapimage, "render", lambda *a, **k: b"FLAT")
        monkeypatch.setattr(scene3d, "render", lambda *a, **k: b"SCENE")
        assert report.build_image(store, {**spec, "scene": {**spec["scene"], "camera": "top"}}, "png", "light") == b"FLAT"
        assert report.build_image(store, {**spec, "scene": {**spec["scene"], "camera": "free"}}, "png", "light") == b"SCENE"
        page = report.build_plot_html(store, {**spec, "scene": {**spec["scene"], "camera": "top"}})
        assert '"camera":"top"' in page and 'D.camera === "top"' in page
    finally:
        client.delete(f"/api/runs/{run}")
