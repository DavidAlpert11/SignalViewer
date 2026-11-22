"""The offline HTML page: an XY plot zooms BOTH axes - a box, the wheel around the pointer (Alt: x only, Shift: y
only - as in the app), a double click shows everything again (owner, 2026-11-22: "in HTML the zoom was only on the x axis, not in XY").
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
        # Alt + wheel: x only (as in the app: Shift the values, Alt the x axis)
        pg.keyboard.down("Alt"); pg.mouse.wheel(0, 100); pg.keyboard.up("Alt")
        pg.wait_for_timeout(100)
        sh = scales(pg)
        assert sh[1] - sh[0] > w[1] - w[0] and abs((sh[3] - sh[2]) - (w[3] - w[2])) < 1e-9
        # double click: everything again
        pg.mouse.dblclick(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
        pg.wait_for_timeout(100)
        assert scales(pg) == pytest.approx(full)
        b.close()


def test_time_and_fft_zoom_the_values_too(tmp_path):
    """Z1 (owner, 2026-11-22: "I still cannot zoom on the y axis, only x - fix it everywhere"): a time plot - an up /
    down drag zooms its values (the time stays), the wheel over the value axis too, a sideways drag the time; an FFT -
    a box zooms both axes; a double click shows everything."""
    t = np.arange(20_000) * 0.01
    np.savetxt(tmp_path / "r.csv", np.c_[t, 100 * np.sin(t), np.sin(7 * t) + 0.3 * np.sin(31 * t)], delimiter=",",
               header="Time,A,B", comments="", fmt="%.6f")
    s = Store()
    rid = s.open_file(str(tmp_path / "r.csv")).id
    sig_ = lambda n: {"id": f"{rid}/{n}", "label": n, "color": "#3D8BFD", "width": 1.5, "scale": 1, "offset": 0, "state": False, "tOffset": 0}  # noqa: E731
    req = {"title": "Y", "lang": "en", "theme": "light", "tabs": [{"name": "", "plots": [
        {"title": "A", "mode": "time", "range": None, "signals": [sig_("A")]},
        {"title": "B spectrum", "mode": "fft", "range": None, "signals": [sig_("B")]}]}]}
    page = tmp_path / "y.html"
    page.write_text(R.build_html(s, req), encoding="utf-8")
    sc = "(i) => { const u = window.__svPage.plots()[i].u; return [u.scales.x.min, u.scales.x.max, u.scales.y.min, u.scales.y.max]; }"
    with pw.sync_playwright() as p:
        exe = os.environ.get("SV_CHROMIUM")
        b = p.chromium.launch(**({"executable_path": exe} if exe else {}))
        pg = b.new_page(viewport={"width": 1100, "height": 1100})
        pg.goto(page.as_uri())
        pg.wait_for_function("() => window.__svPage && window.__svPage.plots().length === 2 && window.__svPage.plots()[1].u")
        full = pg.evaluate(sc, 0)
        box = pg.locator(".u-over").nth(0).bounding_box()
        # up / down: the values only
        pg.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.2)
        pg.mouse.down(); pg.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5, steps=8); pg.mouse.up()
        pg.wait_for_timeout(150)
        z = pg.evaluate(sc, 0)
        assert z[0:2] == pytest.approx(full[0:2]) and z[3] - z[2] < 0.6 * (full[3] - full[2]) and z[2] > 0, (full, z)
        # sideways: the time, the values stay as zoomed
        pg.mouse.move(box["x"] + box["width"] * 0.2, box["y"] + box["height"] * 0.5)
        pg.mouse.down(); pg.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5, steps=8); pg.mouse.up()
        pg.wait_for_timeout(150)
        x = pg.evaluate(sc, 0)
        assert x[1] - x[0] < 0.5 * (full[1] - full[0]) and x[2:4] == pytest.approx(z[2:4])
        # the wheel over the value axis: the values only
        pg.mouse.move(box["x"] - 20, box["y"] + box["height"] * 0.5)
        pg.mouse.wheel(0, 100)
        pg.wait_for_timeout(150)
        w = pg.evaluate(sc, 0)
        assert w[3] - w[2] > x[3] - x[2] and w[0:2] == pytest.approx(x[0:2])
        # a double click: everything
        pg.mouse.dblclick(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
        pg.wait_for_timeout(150)
        assert pg.evaluate(sc, 0) == pytest.approx(full)
        # the FFT: a box zooms both axes
        f0 = pg.evaluate(sc, 1)
        fb = pg.locator(".u-over").nth(1).bounding_box()
        pg.mouse.move(fb["x"] + fb["width"] * 0.05, fb["y"] + fb["height"] * 0.3)
        pg.mouse.down(); pg.mouse.move(fb["x"] + fb["width"] * 0.4, fb["y"] + fb["height"] * 0.7, steps=8); pg.mouse.up()
        pg.wait_for_timeout(150)
        f1 = pg.evaluate(sc, 1)
        assert f1[1] - f1[0] < 0.6 * (f0[1] - f0[0]) and f1[3] - f1[2] < f0[3] - f0[2], (f0, f1)
        b.close()
