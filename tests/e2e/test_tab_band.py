"""
U3 (owner, 2026-11-07): one flight-mode row per tab - in the overview strip when it shows that
signal, else in a band above the plots. When a tab's time plots share the time axis
(X linked, one column, two or more), its lanes (MODE.Mode on an ArduPilot tab) are drawn ONCE above
the plots, lined up with them and following their zoom - not at the bottom of every plot. Cursors
1 / 2 and the pointer over a plot are lines on it with the state under them named; the overview
strip shows them too (the owner: "so the context is clear"). A plot can show the lanes again itself.
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_template_tabs import open_ardupilot_example, pg  # noqa: E402,F401
from test_features import frames, settled  # noqa: E402


def _lane_title(pg, n=0):
    """What a plot's own bottom lane says when hovered ('' when it has none there)."""
    box = pg.locator(".plot").nth(n).locator(".u-over").bounding_box()
    pg.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] - 4)
    frames(pg)                                               # (T2) the hover drawn
    return pg.evaluate(f"document.querySelectorAll('.plot .u-over')[{n}].title || ''")


def test_one_mode_row_with_cursors_and_hover(pg):
    """1.22.0 fix (owner): the strip's mode row and the band showed the same MODE.Mode twice - the
    strip shows it (with the cursors, the mode under each named), the band only what it does not."""
    open_ardupilot_example(pg)
    strip = pg.locator(".ov-strip")
    strip.locator(".ov-phase").first.wait_for(timeout=20000)
    settled(pg); frames(pg)
    assert pg.locator(".tab-band .band-row").count() == 0           # once, in the strip
    assert "MODE" not in _lane_title(pg)                            # and not in every plot
    # cursors: lines on the strip's row, each naming the mode under it
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 140, t2: 230, active: 1 } })")
    pg.mouse.move(5, 5)
    pg.wait_for_selector(".ov-row .ov-cur.c1 .ov-cur-tag")
    assert strip.locator(".ov-row .ov-cur.c1 .ov-cur-tag").inner_text() == "1 · AUTO"
    assert strip.locator(".ov-row .ov-cur.c2 .ov-cur-tag").inner_text() == "2 · LAND"
    assert strip.locator(".ov-phase.at").count() == 2
    # the pointer over a plot (cursors off): a dashed line there too, naming the mode
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: false } })")
    box = pg.locator(".plot").nth(1).locator(".u-over").bounding_box()
    for k in range(4):                                       # uPlot follows a moving pointer
        pg.mouse.move(box["x"] + box["width"] * (0.3 + 0.02 * k), box["y"] + box["height"] * 0.4)
        pg.wait_for_timeout(100)
    pg.wait_for_selector(".ov-row .ov-cur.hover .ov-cur-tag")
    # the strip hidden: the band above the plots takes the lane, with the same lines
    pg.mouse.move(5, 5)
    pg.locator(".ov-hide").click()
    band = pg.locator(".tab-band")
    band.locator(".band-seg").first.wait_for(timeout=20000)
    assert band.locator(".band-row").count() == 1 and "MODE.Mode" in band.locator(".band-label").inner_text()
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 140, t2: 230, active: 1 } })")
    pg.wait_for_selector(".tab-band .band-line.c1 .band-tag")
    assert band.locator(".band-line.c1 .band-tag").inner_text() == "1 · AUTO"
    # a click on a stretch: the cursors on its edges (as on a plot's lane)
    band.locator(".band-seg", has_text="LOITER").first.click()
    pg.wait_for_function("window.__sv.state().cursor.on && window.__sv.state().cursor.dual")
    t1, t2 = pg.evaluate("[window.__sv.state().cursor.t1, window.__sv.state().cursor.t2]")
    assert 0 < t1 < 100 and t1 < t2
    pg.locator(".ov-show").click()                                  # the strip back (a preference)
    pg.wait_for_selector(".tab-band .band-row", state="detached")


def test_a_plot_shows_the_lane_again_and_single_plot_tabs_keep_theirs(pg):
    open_ardupilot_example(pg)
    pg.locator(".ov-strip .ov-phase").first.wait_for(timeout=20000)
    pg.locator(".plot").first.locator(".plot-more").click()
    pg.locator(".menu.ctx button", has_text="State lanes in this plot too").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].ownBand === true")
    assert "MODE" in _lane_title(pg, 0) and "MODE" not in _lane_title(pg, 1)
    # X not linked: no band, every plot its lane again (as before U3)
    pg.evaluate("""(() => { const s = window.__sv.state(); const ws = structuredClone(s.ws);
        ws.tabs[0].linkX = false; window.__sv.setState({ ws }); })()""")
    frames(pg, 3)
    assert "MODE" in _lane_title(pg, 1)
