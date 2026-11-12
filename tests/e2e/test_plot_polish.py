"""L7 (2026-11-13): W7 the two cursors' bar in the plot's head, W9 the views badge / a flight log's dimmed
message part, W13.2 the first draw-in (once per tab), T49 item 10 the cursors next to the zoom."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, open_files, pg, sig  # noqa: E402,F401


def test_two_cursors_bar_sits_in_the_plot_head(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.keyboard.press("d")                                         # two cursors
    bar = pg.locator(".plot-head .sel-slot .sel-bar")
    pg.wait_for_function("(() => { const b = document.querySelector('.plot-head .sel-bar'); return b && !b.hidden; })()")
    head = pg.locator(".plot-head").first.bounding_box()
    b = bar.bounding_box()
    assert head["y"] <= b["y"] and b["y"] + b["height"] <= head["y"] + head["height"] + 1       # inside the head
    legend = pg.locator(".plot-head .legend").first.bounding_box()
    assert b["x"] >= legend["x"] + legend["width"] - 1                                        # right of the legend
    before = b["x"]
    pg.keyboard.press("ArrowRight")                                # the cursors move: the bar stays where it is
    assert abs(bar.bounding_box()["x"] - before) < 1


def test_cursor_buttons_next_to_the_zoom(pg):
    open_files(pg, "run_a.csv")
    order = pg.eval_on_selector_all(".stage-bar > *", "els => els.map((e) => e.className)")
    z = next(i for i, c in enumerate(order) if "zoom" in c or c == "pick-wrap" and i > 3)
    cur = next(i for i, c in enumerate(order) if "cursor-btn" in c)
    assert 0 < cur - z <= 4, order


def test_the_first_plot_draws_in_once_per_tab(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("window.__svDrawIn === 1")
    pg.keyboard.press("r")                                         # a zoom reset: no second draw-in
    sig(pg, "RPM").click()
    pg.wait_for_timeout(600)
    assert pg.evaluate("window.__svDrawIn") == 1


def test_a_flight_logs_message_part_is_dimmed_in_a_flat_list(pg):
    pg.locator(".examples-line button", has_text="ArduPilot").click()
    pg.wait_for_function("window.__sv.state().runs.some((r) => r.format === 'bin')")
    pg.fill(".filter input", "ATT.DesRoll")                        # one match: listed flat, with its message
    pg.wait_for_selector(".sig .nm .nm-grp")
    assert pg.locator(".sig .nm .nm-grp").first.inner_text() == "ATT."
