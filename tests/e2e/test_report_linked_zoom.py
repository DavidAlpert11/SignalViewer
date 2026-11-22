"""The offline HTML page: the time plots of a tab zoom together and share the cursor (the 🔗 button, on by default;
off: each plot on its own) - owner, 2026-11-22: "in the HTML export, can all the plots be linked when zooming".
The page alone (no app): made by report.build_html, opened from the disk."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
from app import report as R  # noqa: E402
from app.store import Store  # noqa: E402

pw = pytest.importorskip("playwright.sync_api")


def _sig(rid, name, color):
    return {"id": f"{rid}/{name}", "label": name, "color": color, "width": 1.5, "scale": 1, "offset": 0, "state": False, "tOffset": 0}


@pytest.fixture()
def page_file(tmp_path):
    t = np.arange(10_000) * 0.01
    np.savetxt(tmp_path / "run.csv", np.c_[t, np.sin(t), np.cos(t / 3), 2 * t], delimiter=",",
               header="Time,A,B,C", comments="", fmt="%.6f")
    s = Store()
    rid = s.open_file(str(tmp_path / "run.csv")).id
    plot = lambda title, sigs: {"title": title, "mode": "time", "range": None, "signals": sigs}  # noqa: E731
    req = {"title": "Linked", "lang": "en", "theme": "light", "tabs": [
        {"name": "Two", "plots": [plot("A", [_sig(rid, "A", "#3D8BFD")]), plot("B", [_sig(rid, "B", "#E5484D")]),
                                  {"title": "XY", "mode": "xy", "xSignal": f"{rid}/A", "range": None, "signals": [_sig(rid, "B", "#30A46C")]}]},
        {"name": "One", "plots": [plot("C", [_sig(rid, "C", "#3D8BFD")])]}]}
    p = tmp_path / "linked.html"
    p.write_text(R.build_html(s, req), encoding="utf-8")
    return p


JS_X = "() => window.__svPage.plots().map(p => p.spec.mode === 'time' ? [p.u.scales.x.min, p.u.scales.x.max, p.cursor] : null)"


def test_time_plots_zoom_and_cursor_together(page_file):
    with pw.sync_playwright() as p:
        exe = os.environ.get("SV_CHROMIUM")
        b = p.chromium.launch(**({"executable_path": exe} if exe else {}))
        pg = b.new_page(viewport={"width": 1100, "height": 1400})
        pg.goto(page_file.as_uri())
        pg.wait_for_function("() => window.__svPage && window.__svPage.plots().length === 3 && window.__svPage.plots()[1].u")
        link = pg.locator("#link")
        assert link.is_visible() and link.get_attribute("aria-pressed") == "true"
        full = pg.evaluate(JS_X)
        over = pg.locator(".u-over")
        box = over.nth(0).bounding_box()
        # a box on the first plot: the second follows (the XY plot keeps its own axes)
        pg.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] * 0.5)
        pg.mouse.down()
        pg.mouse.move(box["x"] + box["width"] * 0.6, box["y"] + box["height"] * 0.5, steps=6)
        pg.mouse.up()
        pg.wait_for_timeout(150)
        z = pg.evaluate(JS_X)
        assert z[0][1] - z[0][0] < 0.5 * (full[0][1] - full[0][0])
        assert z[1][0] == pytest.approx(z[0][0]) and z[1][1] == pytest.approx(z[0][1]), z
        assert z[2] is None
        # a click on the second plot: the cursor on both, the values in both legends
        box2 = over.nth(1).bounding_box()
        pg.mouse.click(box2["x"] + box2["width"] * 0.5, box2["y"] + box2["height"] * 0.5)
        pg.wait_for_timeout(100)
        c = pg.evaluate(JS_X)
        assert c[0][2] is not None and c[0][2] == pytest.approx(c[1][2])
        assert pg.locator(".legend").nth(0).locator(".val").count() == 1
        # a double click on the second plot: both back to everything
        pg.mouse.dblclick(box2["x"] + box2["width"] * 0.5, box2["y"] + box2["height"] * 0.5)
        pg.wait_for_timeout(150)
        r = pg.evaluate(JS_X)
        assert r[0][:2] == pytest.approx(full[0][:2]) and r[1][:2] == pytest.approx(full[1][:2])
        # unlinked: the wheel on the first plot leaves the second as it is
        link.click()
        assert link.get_attribute("aria-pressed") == "false" and not pg.evaluate("() => window.__svPage.linked")
        pg.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
        pg.mouse.wheel(0, -100)
        pg.wait_for_timeout(150)
        u = pg.evaluate(JS_X)
        assert u[0][1] - u[0][0] < full[0][1] - full[0][0] and u[1][:2] == pytest.approx(full[1][:2])
        # linked again: the second to the first one's range
        link.click()
        pg.wait_for_timeout(150)
        l2 = pg.evaluate(JS_X)
        assert l2[1][:2] == pytest.approx(l2[0][:2]) and l2[0][1] - l2[0][0] < full[0][1] - full[0][0]
        # a tab with one time plot: nothing to link, no button
        pg.locator(".tabbtn").nth(1).click()
        pg.wait_for_function("() => window.__svPage.plots().length === 1")
        assert not link.is_visible()
        b.close()
