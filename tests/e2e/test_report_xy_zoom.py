"""The offline HTML page: an XY plot zooms BOTH axes - a box, the wheel around the pointer (Shift: x only, Alt: y
only), a double click shows everything again (owner, 2026-11-22: "in HTML the zoom was only on the x axis, not in XY").
The page alone (no app): made by report.build_plot_html, opened from the disk."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
from app import report as R  # noqa: E402
from app.store import Store  # noqa: E402

pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture()
def page_file(tmp_path):
    t = np.arange(20_000) * 0.01
    np.savetxt(tmp_path / "track.csv", np.c_[t, 100 * np.cos(t / 30), 50 * np.sin(t / 30)], delimiter=",",
               header="Time,East,North", comments="", fmt="%.6f")
    s = Store()
    rid = s.open_file(str(tmp_path / "track.csv")).id
    spec = {"title": "Track", "mode": "xy", "xSignal": f"{rid}/East", "range": None,
            "signals": [{"id": f"{rid}/North", "label": "North", "color": "#3D8BFD", "width": 1.5, "scale": 1, "offset": 0, "state": False, "tOffset": 0}]}
    p = tmp_path / "xy.html"
    p.write_text(R.build_plot_html(s, spec), encoding="utf-8")
    return p


def scales(pg):
    return pg.evaluate("() => { const u = window.__svPage.plots()[0].u; return [u.scales.x.min, u.scales.x.max, u.scales.y.min, u.scales.y.max]; }")


def test_xy_zoom_both_axes(page_file):
    with pw.sync_playwright() as p:
        exe = os.environ.get("SV_CHROMIUM")
        b = p.chromium.launch(**({"executable_path": exe} if exe else {}))
        pg = b.new_page(viewport={"width": 1100, "height": 800})
        pg.goto(page_file.as_uri())
        pg.wait_for_function("() => window.__svPage && window.__svPage.plots()[0] && window.__svPage.plots()[0].u")
        full = scales(pg)
        assert full[0] < -95 and full[1] > 95 and full[2] < -45 and full[3] > 45
        box = pg.locator(".u-over").first.bounding_box()
        # a box in the upper-right quarter: both axes to it
        pg.mouse.move(box["x"] + box["width"] * 0.55, box["y"] + box["height"] * 0.1)
        pg.mouse.down()
        pg.mouse.move(box["x"] + box["width"] * 0.9, box["y"] + box["height"] * 0.45, steps=8)
        pg.mouse.up()
        z = scales(pg)
        assert z[0] > 0 and z[1] - z[0] < 0.5 * (full[1] - full[0]), z
        assert z[2] > 0 and z[3] - z[2] < 0.5 * (full[3] - full[2]), z          # y zoomed too (was: back to auto)
        # the wheel: both axes around the pointer
        pg.mouse.move(box["x"] + box["width"] * 0.7, box["y"] + box["height"] * 0.3)
        pg.mouse.wheel(0, -100)
        pg.wait_for_timeout(100)
        w = scales(pg)
        assert w[1] - w[0] < z[1] - z[0] and w[3] - w[2] < z[3] - z[2]
        # Shift + wheel: x only
        pg.keyboard.down("Shift"); pg.mouse.wheel(0, 100); pg.keyboard.up("Shift")
        pg.wait_for_timeout(100)
        sh = scales(pg)
        assert sh[1] - sh[0] > w[1] - w[0] and abs((sh[3] - sh[2]) - (w[3] - w[2])) < 1e-9
        # double click: everything again
        pg.mouse.dblclick(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
        pg.wait_for_timeout(100)
        assert scales(pg) == pytest.approx(full)
        b.close()
