"""MF02: the chart desktop - 1 / 2 / 4 panes of linked charts; a range dragged on a histogram is the
one brush (the table follows), the scatter matrix's correlations, the broken conditions."""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg, save_as  # noqa: E402,F401
from test_sweeps_flow import _fresh, _step, _the_goal, _tab  # noqa: E402


def _charts(pg):
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".sw-table tbody tr")
    _tab(pg, "charts")
    pg.wait_for_selector(".sw-desk .sw-pane")


def test_desk_layouts_and_kinds(pg):
    _charts(pg)
    assert pg.locator(".sw-desk .sw-pane").count() == 2
    pg.locator(".sw-desk-bar .btn", has_text="Add chart").click()                    # as many charts as wanted
    pg.locator(".sw-desk-bar .btn", has_text="Add chart").click()
    pg.wait_for_function("document.querySelectorAll('.sw-desk .sw-pane').length === 4")
    pg.locator(".sw-desk-bar button[role='radio']", has_text="4").click()          # 4 in a row
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
    # a chart duplicated, one removed, one left out of the report
    pg.locator(".sw-pane").nth(2).locator(".sw-pane-menu").click()
    pg.locator(".menu.ctx button", has_text="Duplicate").click()
    pg.wait_for_function("document.querySelectorAll('.sw-desk .sw-pane').length === 5")
    assert pg.locator(".sw-pane").nth(3).get_attribute("data-kind") == "box"
    pg.locator(".sw-pane").nth(3).locator(".sw-pane-menu").click()
    pg.locator(".menu.ctx button", has_text="Remove").click()
    pg.wait_for_function("document.querySelectorAll('.sw-desk .sw-pane').length === 4")
    pg.locator(".sw-pane").nth(0).locator(".sw-in-report input").uncheck()
    # a chart as a PNG
    pg.locator(".sw-pane").nth(1).locator(".sw-pane-menu").click()
    pg.locator(".menu.ctx button", has_text="Export as PNG").click()
    save_as(pg, "hist.png")
    pg.wait_for_selector(".toast:has-text('hist.png')")
    assert open(os.path.join(pg.env["out"], "hist.png"), "rb").read(8) == b"\x89PNG\r\n\x1a\n"
    # for a report: twice the pixels; and as a page of its own (the drawing itself)
    import struct
    size = lambda n: struct.unpack(">II", open(os.path.join(pg.env["out"], n), "rb").read(24)[16:24])
    pg.locator(".sw-pane").nth(1).locator(".sw-pane-menu").click()
    pg.locator(".menu.ctx button", has_text="Export for a report").click()
    save_as(pg, "hist_hires.png")
    pg.wait_for_selector(".toast:has-text('hist_hires.png')")
    assert size("hist_hires.png")[0] >= 2 * size("hist.png")[0] - 4
    pg.locator(".sw-pane").nth(1).locator(".sw-pane-menu").click()
    pg.locator(".menu.ctx button", has_text="Export as a page").click()
    save_as(pg, "hist.html")
    pg.wait_for_selector(".toast:has-text('hist.html')")
    assert "<svg" in open(os.path.join(pg.env["out"], "hist.html"), encoding="utf-8").read()


def test_histogram_brush_filters_everything(pg):
    _charts(pg)
    _tab(pg, "sets")
    total = pg.locator(".sw-table-wrap .sw-table tbody tr").count()
    _tab(pg, "charts")
    svg = pg.locator(".sw-pane[data-kind='histogram'] svg.sw-chart")
    b = svg.bounding_box()
    y = b["y"] + b["height"] * 0.5
    pg.mouse.move(b["x"] + b["width"] * 0.15, y); pg.mouse.down()
    pg.mouse.move(b["x"] + b["width"] * 0.55, y, steps=5); pg.mouse.up()
    pg.wait_for_selector(".sw-pane[data-kind='histogram'] .sw-brush-mark")
    _tab(pg, "sets")
    pg.wait_for_selector(".sw-plotbar .btn:has-text('Clear 1 filters')")
    assert 0 < pg.locator(".sw-table-wrap .sw-table tbody tr").count() < total


def test_every_pane_kind_and_a_group_per_pane(pg):
    _charts(pg)
    pane = pg.locator(".sw-pane").nth(0)
    for kind in ("lines", "map", "history", "pareto", "compare", "bubble", "histogram", "box", "matrix", "broken", "scatter"):
        pane.locator("select[aria-label='Chart']").select_option(kind)
        pg.wait_for_selector(f".sw-pane[data-kind='{kind}']")
        # some kinds ask the server first (map, history): wait for the drawing, not for the pane
        pg.wait_for_function("document.querySelector('.sw-pane').querySelector('svg, canvas, table, .empty-note, .sw-broken') !== null")
    # the histogram of only the holding sets counts fewer than of all
    pane.locator("select[aria-label='Chart']").select_option("broken")
    allfail = pg.locator(".sw-broken-n").first.inner_text()
    pane.locator("select[aria-label='Group']").select_option("holds")
    pg.wait_for_function("document.querySelector('.sw-broken-n').innerText.startsWith('0 of')")
    assert allfail != pg.locator(".sw-broken-n").first.inner_text()


def test_principal_components_clusters_as_groups_and_a_som(pg):
    """MF09: the sets on their first two principal components, k-means clusters kept as groups (one
    per cluster, together every set); a map by distances; a self-organising map whose node is a group."""
    _charts(pg)
    pane = pg.locator(".sw-pane").nth(0)
    pane.locator("select[aria-label='Chart']").select_option("pca")
    pg.wait_for_selector(".sw-pane[data-kind='pca'] .sw-shape-plane svg[data-points='45']")
    assert "PC1 (" in pane.inner_text()
    pane.locator("input[aria-label='How many clusters']").fill("3")
    pane.locator(".btn", has_text="Keep the 3 clusters as groups").click()
    pg.wait_for_selector(".toast:has-text('3 groups saved')")
    pg.wait_for_function("document.querySelectorAll('.sw-groups .sw-group:not(.auto)').length === 3")
    n = sum(int(x) for x in pg.locator(".sw-groups .sw-group:not(.auto) .sw-group-n").all_inner_texts())
    assert n == 45
    pane.locator("select[aria-label='Clusters by']").select_option("mds")
    pg.wait_for_selector(".sw-pane[data-kind='pca'] figcaption:has-text('Stress')")
    pane.locator("select[aria-label='Chart']").select_option("som")
    pg.wait_for_selector(".sw-pane[data-kind='som'] .sw-som-node")
    hits = [int(x or 0) for x in pg.locator(".sw-som-node").all_inner_texts()]
    assert sum(hits) == 45
    pg.locator(".sw-som-node:not([disabled])").first.click()
    pg.wait_for_selector(".sw-groups .sw-group:not(.auto):has-text('Map node')")
