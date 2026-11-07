"""
U3 (owner, 2026-11-07): one flight-mode band per tab. When a tab's time plots share the time axis
(X linked, one column, two or more), its lanes (MODE.Mode on an ArduPilot tab) are drawn ONCE above
the plots, lined up with them and following their zoom - not at the bottom of every plot. Cursors
1 / 2 and the pointer over a plot are lines on it with the state under them named; the overview
strip shows them too (the owner: "so the context is clear"). A plot can show the lanes again itself.
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_template_tabs import open_ardupilot_example, pg  # noqa: E402,F401


def _lane_title(pg, n=0):
    """What a plot's own bottom lane says when hovered ('' when it has none there)."""
    box = pg.locator(".plot").nth(n).locator(".u-over").bounding_box()
    pg.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] - 4)
    pg.wait_for_timeout(300)
    return pg.evaluate(f"document.querySelectorAll('.plot .u-over')[{n}].title || ''")


def test_one_band_with_cursors_and_hover(pg):
    open_ardupilot_example(pg)
    band = pg.locator(".tab-band")
    band.locator(".band-seg").first.wait_for(timeout=20000)
    assert band.locator(".band-row").count() == 1 and "MODE.Mode" in band.locator(".band-label").inner_text()
    assert "MODE" not in _lane_title(pg)                     # the plots no longer draw it
    # cursors: lines on the band, each naming the mode under it; the overview strip shows them too
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 140, t2: 230, active: 1 } })")
    pg.mouse.move(5, 5)
    pg.wait_for_selector(".tab-band .band-line.c1 .band-tag")
    assert band.locator(".band-line.c1 .band-tag").inner_text() == "1 · AUTO"
    assert band.locator(".band-line.c2 .band-tag").inner_text() == "2 · LAND"
    assert band.locator(".band-seg.at").count() == 2
    assert pg.locator(".ov-strip .ov-cur.c1").count() >= 1 and pg.locator(".ov-strip .ov-cur.c2").count() >= 1
    # the pointer over a plot (cursors off): a dashed line on the band and on the strip
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: false } })")
    box = pg.locator(".plot").nth(1).locator(".u-over").bounding_box()
    for k in range(4):                                       # uPlot follows a moving pointer
        pg.mouse.move(box["x"] + box["width"] * (0.3 + 0.02 * k), box["y"] + box["height"] * 0.4)
        pg.wait_for_timeout(100)
    pg.wait_for_selector(".tab-band .band-line.hover .band-tag")
    assert pg.locator(".ov-strip .ov-cur.hover").count() >= 1
    # a click on a stretch: the cursors on its edges (as on a plot's lane)
    pg.mouse.move(5, 5)
    band.locator(".band-seg", has_text="LOITER").first.click()
    pg.wait_for_function("window.__sv.state().cursor.on && window.__sv.state().cursor.dual")
    t1, t2 = pg.evaluate("[window.__sv.state().cursor.t1, window.__sv.state().cursor.t2]")
    assert 0 < t1 < t2


def test_a_plot_shows_the_lane_again_and_single_plot_tabs_keep_theirs(pg):
    open_ardupilot_example(pg)
    pg.locator(".tab-band .band-seg").first.wait_for(timeout=20000)
    pg.locator(".plot").first.locator(".plot-more").click()
    pg.locator(".menu.ctx button", has_text="State lanes in this plot too").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].ownBand === true")
    assert "MODE" in _lane_title(pg, 0) and "MODE" not in _lane_title(pg, 1)
    # X not linked: no band, every plot its lane again (as before U3)
    pg.evaluate("""(() => { const s = window.__sv.state(); const ws = structuredClone(s.ws);
        ws.tabs[0].linkX = false; window.__sv.setState({ ws }); })()""")
    pg.wait_for_selector(".tab-band", state="detached")
    assert "MODE" in _lane_title(pg, 1)
