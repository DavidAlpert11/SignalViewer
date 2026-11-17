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


def test_a_chart_spans_its_own_sets_and_shows_a_set_alone(pg, tmp_path):
    """Owner, 2026-11-17: a pane of the sets that hold is not stretched by a set that fails (one run of 250 among runs
    below 30); in a pane of every set, that set's bar is seen though it is 1 among hundreds (no point left out)."""
    import numpy as np
    import pandas as pd
    from test_sweeps_flow import _condition, _idle, _open_table
    rng = np.random.default_rng(5)
    gain, rate = np.meshgrid(np.arange(20) * 0.5, np.arange(20) * 0.1, indexing="ij")
    df = pd.DataFrame({"gain": np.repeat(gain.ravel(), 10), "rate": np.repeat(rate.ravel(), 10), "scenario_wind": np.tile(np.arange(10), 400)})
    df["error"] = (5 + df.gain + df.rate + df.scenario_wind * 0.5 + rng.normal(0, 1, len(df))).round(3)
    df.loc[1234, "error"] = 2500.0                                           # one run: its set's mean far from the rest
    df.to_csv(os.path.join(tmp_path, "needle_sets.csv"), index=False)
    mean = df.groupby(["gain", "rate"], sort=False).error.mean()
    _open_table(pg, tmp_path, "needle_sets.csv")
    _step(pg, "goals")
    _condition(pg, "error", "<=", 40)
    _step(pg, "results")
    pg.locator(".sw-show select").select_option("all")
    _idle(pg)
    _tab(pg, "charts")
    pane = pg.locator(".sw-pane").nth(0)
    pane.locator("select[aria-label='Chart']").select_option("histogram")
    hist = pane
    hist.locator("label:has-text('Column') select").select_option("error")
    labels = lambda: hist.locator("svg.sw-chart text.sw-ax").evaluate_all("ts => ts.map((t) => t.textContent)")
    hist.locator("svg.sw-chart").wait_for()
    # the axis ends: the last two numbers before the title
    end = "([p, big]) => { const t = [...p.querySelectorAll('svg.sw-chart text.sw-ax')]; const v = t.length >= 4 ? Number(t[t.length - 2].textContent) : NaN; return big ? v > 100 : v < 40; }"
    pg.wait_for_function(end, arg=[hist.element_handle(), True])
    assert float(labels()[-2]) == pytest.approx(float(np.float32(mean.max())), rel=1e-3)   # every set: up to the far set's mean
    heights = [float(h) for h in hist.locator("svg.sw-chart rect:not(.sw-brush-mark)").evaluate_all("rs => rs.map((r) => r.getAttribute('height'))")]
    assert heights and min(heights) >= 2                                     # the bar of that one set is seen
    hist.locator("select[aria-label='Group']").select_option("holds")
    pg.wait_for_function(end, arg=[hist.element_handle(), False])
    hi = float(labels()[-2])
    assert hi == pytest.approx(float(mean[mean < 40].max()), abs=0.05)       # the holding sets' own range
