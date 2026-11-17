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
    _open_table(pg, tmp_path, "big_sweep.csv")
    _step(pg, "results")
    pg.locator(".sw-show select").select_option("all")
    _tab(pg, "runs")
    pg.wait_for_selector(".sw-what-line:has-text('A line per run')")
    _idle(pg)
    pg.wait_for_selector(".hint:has-text('runs, picked at random')")                     # the cap: a sample drawn
    pg.evaluate("window.__svSweeps.filter('error', {kind: 'ranges', ranges: [[9.0, 9.5]]})")
    pg.evaluate("window.__svSweeps.filter('scenario_terrain', {kind: 'labels', labels: ['urban']})")
    pg.wait_for_selector(".sw-plotbar .btn:has-text('Clear 2 filters')")
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
