"""Sweeps area, step 0: the area switch, opening a results table, the guessed roles and the shape
of the study, and correcting a role."""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, pg  # noqa: E402,F401


def _to_sweeps(pg):
    pg.locator(".areas .area-btn", has_text="Sweeps").click()
    pg.wait_for_selector(".sw-welcome, .sw-main")


def test_area_switch_keeps_recordings(pg):
    assert pg.locator(".areas .area-btn").count() == 2           # two areas: the switch is a row of tabs
    _to_sweeps(pg)
    assert pg.locator(".rail").count() == 0                      # the Recordings tools are not here
    pg.locator(".areas .area-btn", has_text="Recordings").click()
    pg.wait_for_selector(".rail")


def test_example_table_roles_and_summary(pg):
    _to_sweeps(pg)
    pg.locator(".sw-welcome .btn", has_text="Try an example").click()
    pg.wait_for_selector(".sw-main .sw-stat")
    hold = pg.locator(".sw-role-hold .sw-col-name").all_inner_texts()
    assert hold == ["scenario_terrain", "scenario_wind_mps", "scenario_mission"]
    assert "sim_version" in pg.locator(".sw-role-ignore .sw-col-name").all_inner_texts()
    stat = lambda label: pg.locator(".sw-stat", has_text=label).locator(".sw-stat-value").inner_text()
    assert stat("Parameter sets") == "150" and stat("Combinations to hold in") == "18"
    # the controller is a scenario after all: 75 sets, 36 combinations
    pg.select_option("select[aria-label='Role of controller']", "hold")
    pg.wait_for_function("[...document.querySelectorAll('.sw-stat')].some(e => e.innerText.includes('Combinations') && e.innerText.includes('36'))")
    assert stat("Parameter sets") == "75"
    pg.locator(".areas .area-btn", has_text="Recordings").click()
