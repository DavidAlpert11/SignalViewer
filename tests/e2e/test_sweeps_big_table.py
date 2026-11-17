"""Sweeps on a big table (1.29): All runs draws a sample above the cap, but what the brush turns into a result -
Keep, Save as group, Export shown - is the whole table's, resolved by the server. A 200,000-row table made here."""
import csv
import os

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, pg, save_as  # noqa: E402,F401
from test_sweeps_flow import _idle, _open_table, _step, _tab  # noqa: E402

RAW_PLOT = "Parallel plot"
CAP_SEL = ".settings .set-sweep-lines [role=radio]"


def _cap(pg, label, over=None):
    """Settings - Sweeps: most lines to draw (and above it: "Every run (density)" - the default - or "A sample")."""
    pg.click(".topbar [aria-label='Settings']")
    if over:
        pg.locator(".settings .set-sweep-over [role=radio]", has_text=over).click()
    pg.locator(CAP_SEL, has_text=label).click()
    pg.wait_for_function(f"document.querySelector(\"{CAP_SEL}[aria-checked=true]\").innerText === {label!r}")
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".settings", state="detached")

TERRAINS = ["flat", "hill", "urban", "sea", "ridge", "dune", "marsh", "snow", "rock", "lake"]


def _big_table(folder) -> pd.DataFrame:
    """2,000 parameter sets (gain x rate) x 100 scenarios (wind x terrain) = 200,000 runs."""
    rng = np.random.default_rng(7)
    gain, rate = np.meshgrid(np.arange(40) * 0.25, np.arange(50) * 0.1, indexing="ij")
    wind, ter = np.meshgrid(np.arange(10), np.arange(10), indexing="ij")
    n_sets, n_sc = gain.size, wind.size
    df = pd.DataFrame({
        "gain": np.repeat(gain.ravel(), n_sc), "rate": np.repeat(rate.ravel(), n_sc),
        "scenario_wind": np.tile(wind.ravel(), n_sets), "scenario_terrain": np.tile(np.array(TERRAINS)[ter.ravel()], n_sets),
    })
    df["error"] = (df.gain * 0.7 + df.rate + df.scenario_wind * 0.2 + rng.normal(0, 1, len(df))).round(4)
    df.to_csv(os.path.join(folder, "big_sweep.csv"), index=False)
    return df


def _expected(df: pd.DataFrame, lo: float, hi: float, terrain: str):
    e = df.error.astype(np.float32)
    m = (e >= lo) & (e <= hi) & (df.scenario_terrain == terrain)
    sets = df.groupby(["gain", "rate"], sort=False).ngroup().to_numpy()       # the server's set numbers
    return sorted(set(sets[m.to_numpy()].tolist())), int(m.sum())


def test_all_runs_keep_group_and_export_are_of_the_whole_table(pg, tmp_path):
    df = _big_table(tmp_path)
    want_sets, want_runs = _expected(df, 9.0, 9.5, "urban")
    _cap(pg, "50,000", "A sample")
    _open_table(pg, tmp_path, "big_sweep.csv")
    _step(pg, "results")
    pg.locator(".sw-show select").select_option("all")
    _tab(pg, "runs")
    pg.wait_for_selector(".sw-what-line:has-text('A line per run')")
    _idle(pg)
    pg.wait_for_selector(".sw-sampled:has-text('Drawing 50,000 of 200,000 runs')")       # the cap: a sample drawn
    pg.evaluate("window.__svSweeps.filter('error', {kind: 'ranges', ranges: [[9.0, 9.5]]})")
    pg.evaluate("window.__svSweeps.filter('scenario_terrain', {kind: 'labels', labels: ['urban']})")
    pg.wait_for_selector(".sw-plotbar .btn:has-text('Clear 2 filters')")
    # the count is of the whole table; the filter is narrow - every run it keeps is drawn: no sample said
    pg.wait_for_selector(f".sw-plotbar .sw-count:has-text('{want_runs:,} of 200,000')")
    pg.wait_for_selector(".sw-sampled", state="detached")
    # Export shown: every matching run of the table, not of the runs drawn
    pg.locator(".sw-plotbar .btn", has_text="Export shown").click()
    save_as(pg, "shown_big.csv")
    pg.wait_for_selector(".toast:has-text('runs written')")
    rows = list(csv.DictReader(open(os.path.join(pg.env["out"], "shown_big.csv"))))
    assert len(rows) == want_runs > 500                 # about 4 times what a 50,000-run sample holds
    assert {r["scenario_terrain"] for r in rows} == {"urban"}
    # Save as group (a run's own column: the sets with such runs, frozen)
    pg.locator(".sw-groups .btn", has_text="Save as group").click()
    g = pg.locator(".sw-groups .sw-group:not(.auto)").first
    g.wait_for()
    assert int(g.locator(".sw-group-n").inner_text().replace(",", "")) == len(want_sets)
    # Keep: exactly the sets with a matching run
    pg.evaluate("window.__svSweeps.filter('error', {kind: 'ranges', ranges: [[9.0, 9.5]]})")
    pg.evaluate("window.__svSweeps.filter('scenario_terrain', {kind: 'labels', labels: ['urban']})")
    pg.wait_for_selector(".sw-plotbar .btn:has-text('Clear 2 filters')")
    pg.locator(".sw-plotbar .btn", has_text="Keep").click()
    pg.wait_for_selector(".sw-plotbar .btn:has-text('Restore all (1)')")
    kept = pg.evaluate("window.__svSweeps.doc().view.scope.steps[0].sets")
    assert sorted(kept) == want_sets


def test_data_step_counts_the_whole_table_and_the_cap_in_settings(pg, tmp_path):
    df = _big_table(tmp_path)
    _cap(pg, "50,000", "A sample")
    _open_table(pg, tmp_path, "big_sweep.csv")
    pg.locator("[role=tab]", has_text=RAW_PLOT).first.click()
    pg.wait_for_selector(".pp canvas")
    pg.wait_for_selector(".sw-sampled:has-text('Drawing 50,000 of 200,000 runs')")
    assert pg.locator(".sw-plotbar .sw-count").inner_text() == "200,000 of 200,000 lines"
    # a drag on the error axis: the count is every run of the table in that range
    ax = pg.locator(".pp-axis-name", has_text="error").bounding_box()
    b = pg.locator(".pp canvas").bounding_box()
    x = ax["x"] + ax["width"] / 2
    pg.mouse.move(x, b["y"] + 120); pg.mouse.down(); pg.mouse.move(x, b["y"] + 200, steps=5); pg.mouse.up()
    f = pg.wait_for_function("Object.values(window.__svSweeps.rawViews())[0]?.filters?.error").json_value()
    lo, hi = f["ranges"][0]
    e = df.error.astype(np.float32)
    want = int(((e >= lo) & (e <= hi)).sum())
    pg.wait_for_selector(f".sw-plotbar .sw-count[data-exact='1']:has-text('{want:,} of 200,000 lines')")
    # no limit: every run drawn, no sample said
    _cap(pg, "No limit")
    pg.wait_for_function("document.querySelector('.pp canvas') && !document.querySelector('.sw-sampled')")
    pg.wait_for_selector(f".sw-plotbar .sw-count:has-text('{want:,} of 200,000 lines')")
    assert int(pg.locator(".pp canvas").get_attribute("data-shown")) == want     # every kept run is a line now


def test_html_page_of_the_table_draws_every_row(pg, tmp_path):
    """FT4: the Data step's plot saved as a page carries every row up to the cap and draws them a frame at a time."""
    _big_table(tmp_path)
    _cap(pg, "No limit")
    _open_table(pg, tmp_path, "big_sweep.csv")
    pg.locator("[role=tab]", has_text=RAW_PLOT).first.click()
    pg.wait_for_selector(".pp canvas")
    pg.locator(".sw-nav-row button[aria-label^='Export']").first.click()
    save_as(pg, "big_plot.html")
    pg.wait_for_selector(".toast:has-text('big_plot.html')")
    page = pg.context.new_page()
    page.goto("file://" + os.path.join(pg.env["out"], "big_plot.html"))
    page.wait_for_function("document.getElementById('cv').dataset.drawing === '0'", timeout=120000)
    assert "200000 of 200000" in page.locator("#count").inner_text()
    page.close()


def test_charts_of_all_runs_count_every_run(pg, tmp_path):
    """FT6: above the cap (a sample or density) the Charts of All runs are of every run - the histogram's bars add up
    to the whole table (they added up to the sample)."""
    _big_table(tmp_path)
    _cap(pg, "50,000", "A sample")
    _open_table(pg, tmp_path, "big_sweep.csv")
    _step(pg, "results")
    pg.locator(".sw-show select").select_option("all")
    _tab(pg, "runs")
    _idle(pg)
    for over in ("A sample", "Every run (density)"):
        _cap(pg, "50,000", over)
        _tab(pg, "runs")
        pg.wait_for_selector(f".pp canvas[data-density='{1 if 'density' in over else 0}']")
        _tab(pg, "charts")
        pg.wait_for_selector(".sw-hist svg rect title", state="attached")
        total = pg.evaluate("""() => [...document.querySelectorAll('.sw-hist svg rect title')]
          .reduce((s, t) => s + Number(t.textContent.trim().split(' ').pop()), 0)""")
        assert total == 200_000, (over, total)


def test_a_filter_remembers_its_tab(pg, tmp_path):
    """FT9 (owner, 2026-11-17): a filter on an output made in Parameter sets keeps SETS by their mean - All runs then
    shows every run of those sets ("n of N" exact), said by the chip above the plot; back in Parameter sets the same
    sets. A filter made in All runs keeps runs - in Parameter sets, the sets with a run that passes."""
    rng = np.random.default_rng(3)
    gain, rate = np.meshgrid(np.arange(20) * 0.5, np.arange(20) * 0.1, indexing="ij")
    n_sets, n_sc = gain.size, 20
    df = pd.DataFrame({"gain": np.repeat(gain.ravel(), n_sc), "rate": np.repeat(rate.ravel(), n_sc),
                       "scenario_wind": np.tile(np.arange(n_sc), n_sets)})
    df["error"] = (df.gain + df.rate + df.scenario_wind * 0.3 + rng.normal(0, 2, len(df))).round(4)
    df.to_csv(os.path.join(tmp_path, "tabs_sweep.csv"), index=False)
    total = len(df)                                                       # 400 sets x 20 runs = 8,000
    mean = df.groupby(["gain", "rate"], sort=False).error.mean().astype(np.float32).to_numpy()
    lo, hi = 6.0, 8.0
    k_sets = int(((mean >= lo) & (mean <= hi)).sum())
    assert 0 < k_sets < n_sets
    own = int(((df.error.astype(np.float32) >= lo) & (df.error.astype(np.float32) <= hi)).sum())
    assert own != k_sets * n_sc                                           # each run by its own value: another count
    _open_table(pg, tmp_path, "tabs_sweep.csv")
    _step(pg, "results")
    pg.locator(".sw-show select").select_option("all")
    _tab(pg, "sets")
    _idle(pg)
    pg.evaluate(f"window.__svSweeps.filter('error', {{kind: 'ranges', ranges: [[{lo}, {hi}]]}})")
    pg.wait_for_selector(f".sw-plotbar .sw-count:has-text('{k_sets} of {n_sets} lines')")
    assert pg.locator(".sw-across").count() == 0                          # made here: no chip
    _tab(pg, "runs")
    pg.wait_for_selector(".sw-what-line:has-text('A line per run')")
    _idle(pg)
    pg.wait_for_selector(f".sw-plotbar .sw-count[data-exact='1']:has-text('{k_sets * n_sc:,} of {total:,} lines')")
    chip = pg.locator(".sw-across")
    assert f"{k_sets} sets, all their {k_sets * n_sc:,} runs" in chip.inner_text()
    _tab(pg, "sets")
    _idle(pg)
    pg.wait_for_selector(f".sw-plotbar .sw-count:has-text('{k_sets} of {n_sets} lines')")
    # a filter made in All runs: in Parameter sets, the sets with at least one run that passes
    pg.locator(".sw-plotbar .btn", has_text="Clear 1 filters").click()
    _tab(pg, "runs")
    _idle(pg)
    lo2, hi2 = 14.0, 99.0
    e = df.error.astype(np.float32)
    passing = ((e >= lo2) & (e <= hi2)).to_numpy()
    sets = df.groupby(["gain", "rate"], sort=False).ngroup().to_numpy()
    k2 = len(set(sets[passing].tolist()))
    pg.evaluate(f"window.__svSweeps.filter('error', {{kind: 'ranges', ranges: [[{lo2}, {hi2}]]}})")
    pg.wait_for_selector(f".sw-plotbar .sw-count[data-exact='1']:has-text('{int(passing.sum()):,} of {total:,} lines')")
    _tab(pg, "sets")
    _idle(pg)
    pg.wait_for_selector(f".sw-plotbar .sw-count[data-exact='1']:has-text('{k2} of {n_sets} lines')")
    assert f"{k2} sets with a run that passes" in pg.locator(".sw-across").inner_text()
    pg.locator(".sw-across button").click()                              # x: the filters of the other tab go
    pg.wait_for_selector(f".sw-plotbar .sw-count:has-text('{n_sets} of {n_sets} lines')")
    pg.wait_for_selector(".sw-across", state="detached")


def test_keep_works_on_show_and_the_chip_counts_what_is_on_screen(pg, tmp_path):
    """Owner, 2026-11-17: Keep acts on what Show shows (only the sets that hold) with no filter; the chip in All runs
    counts what is on screen with every filter - the parameters' too - not the other tab's filter alone."""
    from test_sweeps_flow import _condition
    rng = np.random.default_rng(3)
    gain, rate = np.meshgrid(np.arange(20) * 0.5, np.arange(20) * 0.1, indexing="ij")
    n_sc = 20
    df = pd.DataFrame({"gain": np.repeat(gain.ravel(), n_sc), "rate": np.repeat(rate.ravel(), n_sc),
                       "scenario_wind": np.tile(np.arange(n_sc), gain.size)})
    df["error"] = (df.gain + df.rate + df.scenario_wind * 0.3 + rng.normal(0, 2, len(df))).round(4)
    df.to_csv(os.path.join(tmp_path, "show_sweep.csv"), index=False)
    g = df.groupby(["gain", "rate"], sort=False)
    worst, mean = g.error.max().astype(np.float32), g.error.mean().astype(np.float32)
    holds = worst <= 18
    assert 0 < holds.sum() < len(holds)
    _open_table(pg, tmp_path, "show_sweep.csv")
    _step(pg, "goals")
    _condition(pg, "error", "<=", 18)
    _step(pg, "results")
    _tab(pg, "sets")
    _idle(pg)
    pg.wait_for_selector(f".sw-plotbar .sw-count:has-text('{int(holds.sum())} of {len(holds)} lines')")    # Show: holds
    keep = pg.locator(".sw-plotbar .btn", has_text="Keep")
    assert keep.is_enabled()                                              # no filter: Keep acts on what Show shows
    keep.click()
    pg.wait_for_selector(".sw-plotbar .btn:has-text('Restore')")
    pg.locator(".sw-show select").select_option("all")
    _idle(pg)
    pg.wait_for_selector(f".sw-plotbar .sw-count:has-text('{int(holds.sum())} of')")              # the step keeps them
    # the chip: a parameter's filter and an output's (mean), then All runs
    pg.evaluate("window.__svSweeps.filter('gain', {kind: 'ranges', ranges: [[0, 4]]})")
    pg.evaluate("window.__svSweeps.filter('error', {kind: 'ranges', ranges: [[4, 9]]})")
    want = holds & (mean >= 4) & (mean <= 9) & (g.gain.first() <= 4)
    k = int(want.sum())
    assert k > 0 and k < int(((mean >= 4) & (mean <= 9)).sum())          # the parameter's filter matters
    pg.wait_for_selector(f".sw-plotbar .sw-count:has-text('{k} of')")
    _tab(pg, "runs")
    _idle(pg)
    pg.wait_for_selector(f".sw-plotbar .sw-count[data-exact='1']:has-text('{k * n_sc:,} of')")
    assert f"{k} sets, all their {k * n_sc:,} runs" in pg.locator(".sw-across").inner_text()
