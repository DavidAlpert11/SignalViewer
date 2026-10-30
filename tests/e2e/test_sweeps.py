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
    pg.wait_for_selector(".sw-study")
    pg.locator(".sw-tabs button", has_text="Columns").click()
    hold = pg.locator(".sw-role-hold .sw-col-name").all_inner_texts()
    assert [h.strip() for h in hold] == ["scenario_terrain", "scenario_wind_mps", "scenario_mission"]
    assert "sim_version" in [x.strip() for x in pg.locator(".sw-role-ignore .sw-col-name").all_inner_texts()]
    stat = lambda label: pg.locator(".sw-shape .sw-stat", has_text=label).locator(".sw-stat-value").inner_text()
    assert stat("Parameter sets") == "150" and stat("Combinations to hold in") == "18"
    # the controller is a scenario after all: 75 sets, 36 combinations - and it is remembered as the user's
    pg.select_option("select[aria-label='Role of controller']", "hold")
    pg.wait_for_function("[...document.querySelectorAll('.sw-shape .sw-stat')].some(e => e.innerText.includes('Combinations') && e.innerText.includes('36'))")
    assert stat("Parameter sets") == "75"
    assert pg.locator(".sw-col", has_text="controller").locator(".sw-changed").count() == 1
    pg.locator(".sw-columns .linklike", has_text="Back to the guessed").click()
    pg.wait_for_function("[...document.querySelectorAll('.sw-shape .sw-stat')].some(e => e.innerText.includes('Combinations') && e.innerText.includes('18'))")
    pg.locator(".sw-tabs button", has_text="Question").click()

def _example(pg):
    _to_sweeps(pg)
    if pg.locator(".sw-study").count() == 0:
        pg.locator(".sw-welcome .btn", has_text="Try an example").click()
    pg.wait_for_selector(".pp canvas")


def _holding(pg):
    return int(pg.locator(".sw-answer-n").inner_text().split()[0].replace(",", ""))


def test_goal_condition_and_why_a_set_fails(pg):
    _example(pg)
    pg.select_option("select[aria-label='Goal']", "range_m")
    pg.locator(".sw-question .btn", has_text="+ condition").click()
    pg.select_option(".sw-cond select[aria-label='Column']", "max_roll_deg")
    box = pg.locator(".sw-cond input[aria-label='Limit']")
    box.fill("25"); box.press("Enter")
    pg.wait_for_selector(".sw-cond .hint:has-text('met by')")              # the answer to this question
    pg.wait_for_function("document.querySelector('.sw-table tbody tr td:nth-child(2)')?.innerText === '1'")
    n = _holding(pg)
    assert 0 < n < 150
    # the best set first, ranked 1, and it holds
    first = pg.locator(".sw-table tbody tr").first
    assert first.locator("td").nth(1).inner_text() == "1" and "holds" in first.get_attribute("class")
    # a set that fails says why
    pg.locator(".sw-table tbody tr:not(.holds)").filter(has=pg.locator("td", has_text="18 / 18")).first.click()
    pg.wait_for_selector(".sw-detail .sw-why")
    assert "max_roll_deg" in pg.locator(".sw-why").inner_text()
    # in at least 17 of 18: more sets hold
    pg.select_option(".sw-cond select[aria-label='Where it must hold']", "atLeast")
    k = pg.locator(".sw-cond input[aria-label='How many combinations at least']")
    k.fill("17"); k.press("Tab")
    pg.wait_for_function(f"+document.querySelector('.sw-answer-n').innerText.split(' ')[0] > {n}")


def test_brush_filters_the_lines_and_the_table(pg):
    _example(pg)
    total = pg.locator(".sw-table tbody tr").count()
    b = pg.locator(".pp canvas").bounding_box()
    x = b["x"] + 56                                         # the first axis
    pg.mouse.move(x, b["y"] + 50); pg.mouse.down(); pg.mouse.move(x, b["y"] + 150, steps=5); pg.mouse.up()
    pg.wait_for_selector(".sw-plotbar .btn:has-text('Clear 1 filters')")
    assert pg.locator(".sw-table tbody tr").count() < total
    pg.locator(".sw-plotbar .btn", has_text="Clear").click()
    assert pg.locator(".sw-table tbody tr").count() == total


def test_new_column_per_set(pg):
    _example(pg)
    pg.locator(".sw-question .btn", has_text="per parameter set").click()
    pg.locator(".sw-derived-editor input").first.fill("range_urban_min")
    pg.select_option(".sw-derived-editor select[aria-label='Operation']", "min")
    pg.select_option(".sw-derived-editor select[aria-label='Of the column']", "range_m")
    pg.locator(".sw-derived-editor .sw-pill", has_text="urban").click()
    pg.locator(".sw-derived-editor .btn", has_text="Add the column").click()
    pg.wait_for_selector(".pp-axis-name:has-text('range_urban_min')")
