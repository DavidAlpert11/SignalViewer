"""A signal's style in the Inspector must change what is drawn, not only what is stored: a line
width was ignored on every dense line (most recordings), and a limit's dashed line appeared only
after another style change."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, open_files, pg, sig  # noqa: E402,F401

CANVAS = "() => [...document.querySelectorAll('.plot canvas')].map((c) => c.toDataURL()).join('|')"


def _set(pg, label, value):
    box = pg.locator(f".inspector input[aria-label='{label}']")
    box.fill(value); box.press("Enter")
    pg.wait_for_timeout(600)


def test_line_width_and_limits_are_drawn(pg):
    open_files(pg, "run_a.csv")                                  # 3000 samples: a dense line
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")
    pg.locator(".plot .chip").first.click()
    pg.locator(".inspector input[aria-label='Line width']").wait_for()
    pg.wait_for_timeout(400)

    before = pg.evaluate(CANVAS)
    _set(pg, "Line width", "5")
    assert pg.evaluate(CANVAS) != before, "a chosen line width must be drawn on a dense line"

    before = pg.evaluate(CANVAS)
    _set(pg, "Lower limit (empty: none)", "25")      # inside Speed's range (18 - 38): a limit off the axis draws nothing
    assert pg.evaluate("window.__sv.state().ws.tabs[0].plots[0].signals[0].limits.lo") == 25
    assert pg.evaluate(CANVAS) != before, "a new limit must show its line at once"
