"""L2 (2026-11-13): the first minute with your own file - W3 the chips in the empty plot, W4 the start card's
next step, W5 Click places the cursor (both states), W6 the status bar's sentence, W13.5 empty states."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401


def test_a_plain_csv_opens_with_the_chips_in_the_middle(pg):
    open_files(pg, "run_a.csv")
    box = pg.locator(".plot-empty-start")
    box.wait_for()
    assert "start from a view that fits" in box.inner_text()
    b = box.locator(".chipbtn").first.bounding_box()
    plot = pg.locator(".plot").first.bounding_box()
    assert abs((b["y"] + b["height"] / 2) - (plot["y"] + plot["height"] / 2)) < plot["height"] / 3   # in the middle
    assert pg.locator(".tpl-strip").count() == 0                                    # one place at a time
    box.locator(".chipbtn", has_text="Quick look").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.plots.some(p => p.signals.length))")
    pg.wait_for_selector(".tpl-strip")
    pg.keyboard.press("Control+z")
    pg.wait_for_selector(".plot-empty-start .chipbtn")                              # back to the empty plot


def test_two_files_name_the_next_step_compare(pg):
    open_files(pg, "run_a.csv", "run_b.csv")
    nxt = pg.locator(".start-card .start-next[data-reason='compare']")
    nxt.wait_for()
    assert "compare the 2 files" in nxt.inner_text()
    nxt.locator(".linklike").click()
    pg.wait_for_function("window.__sv.state().panel === 'compare'")


def test_click_places_the_cursor_only_when_the_setting_is_on(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    over = pg.locator(".plot .u-over").first
    over.wait_for()
    over.click(position={"x": 120, "y": 40})
    pg.evaluate("n => new Promise((r) => { const f = (k) => (k ? requestAnimationFrame(() => f(k - 1)) : r(true)); f(n); })", 3)
    assert S(pg, "s.cursor.on") is False                                            # default off: nothing changes
    pg.click(".topbar [aria-label='Settings']")
    pg.locator(".dialog.settings .set-row", has_text="Click places the cursor").locator("button[role=radio]", has_text="On").click()
    pg.keyboard.press("Escape")
    pg.wait_for_function("window.__sv.state().clickPlacesCursor === true")
    over.click(position={"x": 120, "y": 40})
    pg.wait_for_function("window.__sv.state().cursor.on && window.__sv.state().cursor.t1 !== null")
    pg.keyboard.press("Space")                                                      # Space still toggles it
    pg.wait_for_function("!window.__sv.state().cursor.on")


def test_the_status_bar_reads_as_a_sentence(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pts = pg.locator(".status .status-points")
    pts.wait_for()
    text = pts.inner_text()
    assert text in ("Every sample shown", "Shown reduced (min–max) – zoom in for every sample")
    assert any(ch.isdigit() for ch in pts.get_attribute("title"))                  # the numbers one hover away
    assert not any(ch.isdigit() for ch in text)


def test_the_empty_file_list_offers_open(pg):
    """W13.5 + W16: one sentence, and its action is the panel's own Open files right above it."""
    pg.evaluate("window.__sv.setState({ panel: 'data' })")
    st = pg.locator(".empty-tree")
    st.wait_for()
    assert "Open data files" in st.inner_text()
    pg.locator(".side [data-tour='open']").click()
    pg.wait_for_selector(".crumbs input")
    pg.keyboard.press("Escape")
