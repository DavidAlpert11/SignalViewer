"""T49 items 9 + 12, F25: the plot type is one button (a menu of types); the plot's options and a
right-click in the plot open the app's menu, drawn above everything (a short plot cut it off)."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, set_layout, sig  # noqa: E402,F401


def test_plot_type_button_options_and_right_click(pg):
    pg.set_viewport_size({"width": 1024, "height": 700})
    open_files(pg, "run_a.csv")
    set_layout(pg, 3, 1)
    pg.keyboard.press("1"); sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")

    # one type button per plot instead of nine; its menu marks the current type
    assert pg.locator(".plot").first.locator(".mode-btn").inner_text().strip() == "Time"
    pg.locator(".plot").first.locator(".mode-btn").click()
    assert pg.locator(".menu.ctx button[aria-checked=true]").inner_text().strip().endswith("Time")
    pg.keyboard.press("Escape")

    # ⋯ in a short plot: every item is visible and on top (the plot card clipped Axis limits / Clear plot)
    pg.locator(".plot").first.locator(".plot-more").click()
    item = pg.locator(".menu.ctx button", has_text="Clear plot")
    b = item.bounding_box()
    assert b["y"] + b["height"] <= 700
    assert pg.evaluate(f"document.elementFromPoint({b['x'] + b['width'] / 2}, {b['y'] + b['height'] / 2}).closest('.menu.ctx') !== null")
    pg.keyboard.press("Escape")

    # right-click in the plot: the moment under the pointer first
    ov = pg.locator(".plot").first.locator(".u-over").bounding_box()
    x, y = ov["x"] + ov["width"] * 0.5, ov["y"] + ov["height"] * 0.5
    pg.mouse.click(x, y, button="right")
    labels = pg.locator(".menu.ctx button").all_inner_texts()
    assert labels[0] == "Cursor here" and "Axis limits" in labels and "Clear plot" in labels, labels
    pg.get_by_role("menuitem", name="Cursor here", exact=True).click()
    on, t1 = S(pg, "[s.cursor.on, s.cursor.t1]")
    assert on and 10 < t1 < 20, t1                         # run_a: 0-30 s, the middle of the plot
    pg.mouse.click(ov["x"] + ov["width"] * 0.75, y, button="right")
    pg.locator(".menu.ctx button", has_text="Second cursor here").click()
    dual, t2 = S(pg, "[s.cursor.dual, s.cursor.t2]")
    assert dual and 20 < t2 < 26 and S(pg, "s.cursor.t1") == t1

    # the type menu switches the plot
    pg.locator(".plot").first.locator(".mode-btn").click()
    pg.locator(".menu.ctx button", has_text="FFT").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.find(t => t.id === window.__sv.state().ws.activeTab).plots[0].mode === 'fft'")
