"""MF02: the chart desktop - 1 / 2 / 4 panes of linked charts; a range dragged on a histogram is the
one brush (the table follows), the scatter matrix's correlations, the broken conditions."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg, save_as  # noqa: E402,F401
from test_sweeps_flow import _fresh, _step, _the_goal  # noqa: E402


def _charts(pg):
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".sw-table tbody tr")
    pg.locator(".sw-center-tabs button", has_text="Charts").click()
    pg.wait_for_selector(".sw-desk .sw-pane")


def test_desk_layouts_and_kinds(pg):
    _charts(pg)
    assert pg.locator(".sw-desk .sw-pane").count() == 2
    pg.locator(".sw-desk-bar button[role='radio']", has_text="4").click()
    pg.wait_for_function("document.querySelectorAll('.sw-desk .sw-pane').length === 4")
    kinds = [pg.locator(".sw-pane").nth(i).get_attribute("data-kind") for i in range(4)]
    assert kinds == ["scatter", "histogram", "box", "matrix"]
    pane = pg.locator(".sw-pane").nth(0)
    pane.locator("select[aria-label='Chart']").select_option("broken")
    pg.wait_for_selector(".sw-pane[data-kind='broken'] .sw-broken-row")
    assert pg.locator(".sw-broken-row").count() == 2                     # the goal's two conditions
    # the matrix: a coefficient between -1 and 1 in every lower cell
    coefs = pg.locator(".sw-pane[data-kind='matrix'] g[data-coef]")
    assert coefs.count() >= 1
    for i in range(coefs.count()):
        v = coefs.nth(i).get_attribute("data-coef")
        assert v == "NaN" or -1.0001 <= float(v) <= 1.0001
    pg.locator(".sw-pane[data-kind='matrix'] select[aria-label='Correlation']").select_option("spearman")
    # one pane large, then back
    pg.locator(".sw-pane").nth(1).locator(".sw-pane-big").click()
    pg.wait_for_function("document.querySelectorAll('.sw-desk .sw-pane').length === 1")
    pg.locator(".sw-pane .sw-pane-big").click()
    pg.wait_for_function("document.querySelectorAll('.sw-desk .sw-pane').length === 4")


def test_histogram_brush_filters_everything(pg):
    _charts(pg)
    pg.locator(".sw-center-tabs button", has_text="Lines").click()
    total = pg.locator(".sw-table-wrap .sw-table tbody tr").count()
    pg.locator(".sw-center-tabs button", has_text="Charts").click()
    svg = pg.locator(".sw-pane[data-kind='histogram'] svg.sw-chart")
    b = svg.bounding_box()
    y = b["y"] + b["height"] * 0.5
    pg.mouse.move(b["x"] + b["width"] * 0.15, y); pg.mouse.down()
    pg.mouse.move(b["x"] + b["width"] * 0.55, y, steps=5); pg.mouse.up()
    pg.wait_for_selector(".sw-pane[data-kind='histogram'] .sw-brush-mark")
    pg.locator(".sw-center-tabs button", has_text="Lines").click()
    pg.wait_for_selector(".sw-plotbar .btn:has-text('Clear 1 filters')")
    assert 0 < pg.locator(".sw-table-wrap .sw-table tbody tr").count() < total


def test_every_pane_kind_and_a_group_per_pane(pg):
    _charts(pg)
    pane = pg.locator(".sw-pane").nth(0)
    for kind in ("lines", "map", "history", "pareto", "compare", "bubble", "histogram", "box", "matrix", "broken", "scatter"):
        pane.locator("select[aria-label='Chart']").select_option(kind)
        pg.wait_for_selector(f".sw-pane[data-kind='{kind}']")
        assert pg.locator(".sw-pane").nth(0).locator("svg, canvas, table, .empty-note, .sw-broken").count() > 0
    # the histogram of only the holding sets counts fewer than of all
    pane.locator("select[aria-label='Chart']").select_option("broken")
    allfail = pg.locator(".sw-broken-n").first.inner_text()
    pane.locator("select[aria-label='Group']").select_option("holds")
    pg.wait_for_function("document.querySelector('.sw-broken-n').innerText.startsWith('0 of')")
    assert allfail != pg.locator(".sw-broken-n").first.inner_text()
