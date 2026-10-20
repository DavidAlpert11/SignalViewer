"""F24 / T14c: the plots of a column line up (one value-axis width, whatever the units and labels),
and an Envelope plot zooms together with the tab's time plots."""
import os

import numpy as np
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, _csv, env, open_files, pg, set_layout, sig  # noqa: E402,F401


def _boxes(pg):
    return [pg.locator(".plot").nth(i).locator(".u-over").bounding_box() for i in range(pg.locator(".plot").count())]


def test_column_of_plots_lines_up_and_envelope_zooms_with_them(pg):
    t = np.arange(0, 60, 0.05)
    _csv(os.path.join(pg.env["data"], "units.csv"), ["Time", "Speed [km/h]", "Gear", "Speed2 [km/h]"],
         [t, 1000 + 900 * np.sin(t / 7), np.floor(t / 15), 1000 + 880 * np.sin(t / 7 + 0.1)])
    open_files(pg, "units.csv")
    set_layout(pg, 2, 1)
    pg.keyboard.press("1"); sig(pg, "Speed").click()          # a unit label on the value axis: wider
    pg.keyboard.press("2"); sig(pg, "Gear").click()           # no unit, short labels: narrower
    pg.wait_for_function("document.querySelectorAll('.plot .u-over').length === 2")
    pg.wait_for_timeout(500)
    a, b = _boxes(pg)
    assert abs(a["x"] - b["x"]) < 1 and abs(a["width"] - b["width"]) < 1, (a, b)

    # Envelope (two runs of one quantity) in the second plot: lined up too, and its zoom is the tab's
    sig(pg, "Speed2").click()
    pg.locator(".plot").nth(1).locator(".mode-btn").click(); pg.locator(".menu.ctx button", has_text="Envelope").click()
    pg.wait_for_function("document.querySelectorAll('.plot').length === 2 && document.querySelectorAll('.plot .u-over').length === 2")
    pg.wait_for_timeout(800)
    a, b = _boxes(pg)
    assert abs(a["x"] - b["x"]) < 1 and abs(a["width"] - b["width"]) < 1, (a, b)
    y = b["y"] + b["height"] / 2
    pg.mouse.move(b["x"] + b["width"] * 0.25, y); pg.mouse.down()
    pg.mouse.move(b["x"] + b["width"] * 0.5, y, steps=5); pg.mouse.up()
    pg.wait_for_function("Object.values(window.__sv.state().ranges).some(r => r && r[1] - r[0] < 25)")
    lo, hi = S(pg, "Object.values(s.ranges).find(r => r)")
    assert 10 < lo < 20 and 25 < hi < 35, (lo, hi)                 # a quarter to a half of 0-60 s
    pg.mouse.dblclick(b["x"] + b["width"] / 2, y)
    pg.wait_for_function("Object.values(window.__sv.state().ranges).every(r => !r)")
