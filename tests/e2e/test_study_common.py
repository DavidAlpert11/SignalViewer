"""W14 / W15 (2026-11-13): Sweeps → Common parameters - the welcome card opens the drone tables and the
filled-in panel with the known best value; a click on it shows its runs (the deciding scenario marked);
Suggest next runs on a saved copy writes a round, its candidates shown with their reasons."""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, pg, save_as  # noqa: E402,F401

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _open_card(pg):
    pg.locator(".ex-card[data-example='commonGains']").click()
    pg.wait_for_selector("[data-shot='study'][data-settled='1']", timeout=60000)


def test_the_card_opens_the_panel_with_the_answer_and_the_runs(pg):
    _open_card(pg)
    assert pg.locator(".cp-count").inner_text().startswith("14 of 150 values hold in every table")
    first = pg.locator(".cp-rank tbody tr[data-rank='1'] td")
    assert [first.nth(i).inner_text() for i in (1, 2, 3)] == ["1.4", "0.5", "0.8"]        # Kp, Ki, Kd
    pg.locator(".cp-rank tbody tr[data-rank='1']").click()
    pg.wait_for_selector(".cp-runs-table")
    assert pg.locator(".cp-runs-table").count() == 3                                   # the runs in each drone's table
    assert pg.locator(".cp-runs-table").first.locator("tbody tr").count() == 4         # A: four winds
    assert pg.locator(".cp-runs-table").first.locator("tr.cp-deciding").count() == 1   # the deciding wind marked
    # a value that fails says where and why
    bad = pg.locator(".cp-rank tbody tr.cp-no td.cp-cell.fail").first
    assert " by " in bad.get_attribute("title") and " at " in bad.get_attribute("title")


def test_an_edit_is_undone_and_the_answer_follows(pg):
    _open_card(pg)
    pg.locator(".cp-table-head", has_text="Drone B").click()
    box = pg.locator(".cp-table.open input[placeholder='wind = 10']")
    box.fill("mass = 5")                                                               # the heaviest payload left out
    pg.wait_for_function("document.querySelector('.cp-count').innerText.startsWith('24 of 150')")
    pg.locator(".cp-head [aria-label='Undo']").click()
    pg.wait_for_function("document.querySelector('.cp-count').innerText.startsWith('14 of 150')")
    assert "not saved" not in pg.locator(".cp-state").inner_text()


def test_suggest_next_runs_writes_a_round(pg):
    work = os.path.join(pg.env["out"], "drones_w15")
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "examples", "drones"), work)
    pg.evaluate("p => window.__svRequestStudy(p)", os.path.join(work, "drones.svstudy.json"))
    pg.wait_for_selector("[data-shot='study'][data-settled='1']", timeout=60000)
    pg.locator(".cp-results-head .btn.primary", has_text="Suggest next runs").click()
    pg.wait_for_selector(".cp-rank tr.cp-proposed")
    n = pg.locator(".cp-rank tr.cp-proposed").count()
    assert n == 20                                                                     # the batch: candidate values
    reasons = set(pg.locator(".cp-rank tr.cp-proposed td:last-child").all_inner_texts())
    assert all(r.startswith("proposed: ") for r in reasons)
    assert "1 round" not in pg.locator(".cp-state").inner_text()
    pg.wait_for_function("document.querySelector('.cp-state').innerText.includes('pending runs from round 1')")
    assert os.path.isfile(os.path.join(work, "next", "round_1", "A.csv"))
    assert pg.locator(".cp-space .cp-cand").count() > 0                                # on the space, another marker
