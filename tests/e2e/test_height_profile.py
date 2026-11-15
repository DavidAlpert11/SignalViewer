"""F5: the height profile under the map - the primary object's height and the ground under it along the distance;
the cursor's moment marked, a click moves the cursor; for any recording with positions (here a CSV).

    python -m pytest tests/e2e/test_height_profile.py -q
"""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, flat_maps, open_files, pg  # noqa: E402,F401

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def mapped(pg):
    shutil.copy(os.path.join(ROOT, "examples", "three_objects.csv"), pg.env["data"])
    open_files(pg, "three_objects.csv")
    flat_maps(pg)
    pg.locator(".obj-suggest-add").click()
    pg.wait_for_selector(".plot-canvas.geo[data-view]")
    return pg


def test_profile_of_the_primary_object(mapped):
    pg = mapped
    plot = "s.ws.tabs[0].plots.find((p) => (p.mode === 'geo' || p.mode === '3d'))"
    pg.locator(".plot-canvas.geo").hover()
    pg.locator(".map-bar .map-profile").click()
    assert S(pg, f"{plot}.showProfile") is True                          # saved with the plot (Undo too)
    pg.wait_for_selector(".hprof[data-points]")
    assert int(pg.locator(".hprof").get_attribute("data-points")) > 50
    assert pg.locator(".hprof .hprof-alt").count() == 1 and pg.locator(".hprof .hprof-ground").count() == 1
    assert "km" in pg.locator(".hprof-head").inner_text() or " m" in pg.locator(".hprof-head").inner_text()
    # a click on the profile moves the cursor to that moment; the mark follows it
    box = pg.locator(".hprof-svg").bounding_box()
    pg.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2)
    pg.wait_for_function("window.__sv.state().cursor.on && window.__sv.state().cursor.t1 > 1")
    pg.wait_for_selector(".hprof .hprof-cursor", state="attached")              # a vertical line: no width to be "visible"
    assert "height" in pg.locator(".hprof-read").inner_text() and "ground" in pg.locator(".hprof-read").inner_text()
    pg.locator(".map-bar .map-profile").click()
    pg.wait_for_selector(".hprof", state="detached")
