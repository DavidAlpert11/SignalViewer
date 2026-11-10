"""A signal's style in the Inspector must change what is drawn, not only what is stored: a line
width was ignored on every dense line (most recordings), and a limit's dashed line appeared only
after another style change."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, frames, open_files, pg, settled, sig  # noqa: E402,F401

CANVAS = "() => [...document.querySelectorAll('.plot canvas')].map((c) => c.toDataURL()).join('|')"


def _set(pg, label, value):
    box = pg.locator(f".inspector input[aria-label='{label}']")
    n = pg.evaluate("window.__sv.state().past.length")
    box.fill(value); box.press("Enter")
    pg.wait_for_function(f"window.__sv.state().past.length > {n}")    # (T2) the change made...
    settled(pg); frames(pg, 3)                                         # ...its data fetched and drawn


def test_line_width_and_limits_are_drawn(pg):
    open_files(pg, "run_a.csv")                                  # 3000 samples: a dense line
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")
    pg.locator(".plot .chip").first.click()
    pg.locator(".inspector input[aria-label='Line width']").wait_for()
    settled(pg); frames(pg, 3)

    before = pg.evaluate(CANVAS)
    _set(pg, "Line width", "5")
    assert pg.evaluate(CANVAS) != before, "a chosen line width must be drawn on a dense line"

    before = pg.evaluate(CANVAS)
    _set(pg, "Lower limit (empty: none)", "25")      # inside Speed's range (18 - 38): a limit off the axis draws nothing
    assert pg.evaluate("window.__sv.state().ws.tabs[0].plots[0].signals[0].limits.lo") == 25
    assert pg.evaluate(CANVAS) != before, "a new limit must show its line at once"


# N4: style a whole group of signals at once
SIGS = "window.__sv.state().ws.tabs[0].plots[0].signals"


def test_style_a_group_from_its_menu(pg):
    from test_features import menu_item
    open_files(pg, "wide.csv")
    head = pg.locator(".grp-head").first
    head.click(button="right")
    menu_item(pg, "Add all to the active plot")
    pg.wait_for_function(f"{SIGS}.length > 1")
    n = pg.evaluate(f"{SIGS}.length")
    past = pg.evaluate("window.__sv.state().past.length")

    head.click(button="right")
    menu_item(pg, "Style the lines…")
    dlg = pg.locator(".sl-dialog")
    dlg.wait_for()
    assert dlg.locator("input[value='plot']").is_checked()            # the narrowest scope with lines
    assert dlg.locator(".sl-count").inner_text() == f"{n} line(s)"
    dlg.locator(".sl-palette").click()
    dlg.locator(".sl-width").fill("3")
    dlg.locator(".sl-style").select_option("dot")
    dlg.locator(".sl-apply").click()
    pg.wait_for_selector(".sl-dialog", state="detached")
    sigs = pg.evaluate(SIGS)
    assert all(s["width"] == 3 and s.get("lineStyle") == "dot" for s in sigs)
    assert len({s["color"] for s in sigs}) == min(n, 20)               # the palette: a colour each (20, then again)
    assert pg.evaluate("window.__sv.state().past.length") == past + 1  # one Undo step
    assert "Styled" in pg.locator(".toast").last.inner_text()
    pg.locator(".toast").last.get_by_role("button", name="Undo").click()
    pg.wait_for_function(f"{SIGS}.every(s => s.width !== 3 && !s.lineStyle)")


def test_style_the_legend_selection(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click(); sig(pg, "RPM").click()
    pg.wait_for_function(f"{SIGS}.length === 2")
    chips = pg.locator(".plot .chip")
    chips.nth(0).click(); chips.nth(1).click(modifiers=["Control"])      # the batch section
    pg.locator(".inspector .batch-style").select_option("dashdot")
    pg.wait_for_function(f"{SIGS}.every(s => s.lineStyle === 'dashdot')")
    pg.locator(".inspector .batch-colors button[aria-label='#009E73']").click()
    pg.wait_for_function(f"{SIGS}.every(s => s.color === '#009E73')")
    pg.locator(".inspector .batch-style-dlg").click()                    # the same dialog, on just these lines
    dlg = pg.locator(".sl-dialog")
    assert dlg.locator(".sl-scope").count() == 0
    assert dlg.locator(".sl-count").inner_text() == "2 line(s)"
    dlg.locator(".sl-style").select_option("auto")
    dlg.locator(".sl-apply").click()
    pg.wait_for_function(f"{SIGS}.every(s => !s.lineStyle && s.dash === undefined)")
