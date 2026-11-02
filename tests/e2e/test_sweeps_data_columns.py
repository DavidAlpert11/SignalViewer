"""The owner's spec of 2026-11-02 for the Sweeps steps Data and Columns: tables apart, a merge that
makes a new table (join on keys, a source column), Continue with, a saved study keeping its tables;
the Columns step's condition cards (a search, +N more, All / None, a range), the runs "n of m", new
columns with completion and a preview, a Template saved to a file and loaded with its summary; the
side panel folded in a narrow window."""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg, save_as  # noqa: E402,F401
from test_sweeps_flow import _bar_menu, _close_studies, _fresh, _open_table, _step, _to_sweeps  # noqa: E402


def _add_table(pg, folder, name, n):
    pg.locator(".sw-tables .btn", has_text="Add table").click()
    goto_folder(pg, str(folder))
    pg.locator(".dialog .fs-row", has_text=name).click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function(f"document.querySelectorAll('.sw-table-item').length === {n}")


def test_join_on_keys_continue_with_and_reopen(pg, tmp_path):
    (tmp_path / "sim.csv").write_text("gain,wind,roll\n" + "".join(f"{g},{w},{g * 0.1 + w}\n" for g in (1, 2, 3) for w in (0, 5)))
    (tmp_path / "hw.csv").write_text("gain,wind,roll,energy\n" + "".join(f"{g},{w},{g * 0.2 + w},{10 * g + w}\n" for g in (1, 2) for w in (0, 5)))
    _to_sweeps(pg)
    _close_studies(pg)
    _open_table(pg, tmp_path, "sim.csv")
    _add_table(pg, tmp_path, "hw.csv", 2)
    # under two ticked: what to do, no button
    assert "Tick two tables" in pg.locator(".sw-side-step").inner_text()
    for box in pg.locator(".sw-table-item input[type=checkbox]").all():
        box.check()
    pg.locator(".sw-merge select").select_option("join")
    for key in ("gain", "wind"):
        pg.locator(".sw-join-keys .sw-pill", has_text=key).click()
    pg.wait_for_selector(".sw-merge-preview:has-text('6 rows')")                 # an outer join: every key once
    pg.locator(".sw-merge .btn", has_text="Create merged table").click()
    pg.wait_for_function("document.querySelectorAll('.sw-table-item').length === 3")
    assert "merged (2 tables)" in pg.locator(".sw-tabs-name").inner_text()     # shown in the middle at once
    # the tables merged stay as they were; the next steps still work on the first
    assert "6 runs" in pg.locator(".sw-step-btn").nth(0).inner_text()
    pg.locator(".sw-continue select").select_option("2")
    pg.wait_for_function("document.querySelector('.sw-step-btn').innerText.includes('6 runs · 5 columns')")
    pg.locator(".sw-continue .btn", has_text="Columns").click()
    pg.wait_for_selector("input[aria-label='roll [hw.csv]: output']")
    # saved and opened again: every table, the merged one in use
    _bar_menu(pg, "Study", "Save the study")
    save_as(pg, "joined.svsweep")
    pg.wait_for_selector(".toast:has-text('Saved')")
    pg.locator(".areabar .tab.active .x").click()
    pg.wait_for_selector(".sw-welcome")
    pg.locator(".sw-welcome .btn", has_text="Open a saved study").click()
    goto_folder(pg, pg.env["out"])
    pg.locator(".dialog .fs-row", has_text="joined.svsweep").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".sw-steps")
    _step(pg, "raw")
    pg.wait_for_function("document.querySelectorAll('.sw-table-item').length === 3")
    assert pg.locator(".sw-continue select").input_value() == "2"


def test_source_column_and_closing_tables(pg):
    _fresh(pg)
    ex = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "examples", "sweeps"))
    _add_table(pg, ex, "drone_tuning_refine.csv", 2)
    for box in pg.locator(".sw-table-item input[type=checkbox]").all():
        box.check()
    pg.locator(".sw-source-name").fill("version")
    pg.locator(".sw-merge .btn", has_text="Create merged table").click()
    pg.wait_for_function("document.querySelectorAll('.sw-table-item').length === 3")
    pg.locator(".sw-center-tabs button", has_text="Table").click()
    pg.wait_for_selector(".sw-raw th:has-text('version')")
    # closing the table in use: the next steps go on with another
    pg.locator(".sw-table-item").nth(0).locator("button[aria-label^='Close']").click()
    pg.wait_for_function("document.querySelectorAll('.sw-table-item').length === 2")
    assert pg.locator(".areabar .tab").count() >= 1


def test_condition_cards_runs_and_range(pg):
    _fresh(pg)
    _step(pg, "roles")
    card = pg.locator(".sw-cond-card", has_text="scenario_wind_mps")
    card.locator("summary").click()
    total = pg.locator(".sw-shape-bar .sw-stat").first.locator(".sw-stat-value").inner_text()
    card.locator(".sw-pill").first.click()                                          # one value out
    pg.wait_for_function("document.querySelector('.sw-shape-bar .sw-stat').innerText.includes(' of ')")
    runs = pg.locator(".sw-shape-bar .sw-stat").first.locator(".sw-stat-value").inner_text()
    assert runs.endswith(f"of {total}")
    assert " of " in card.locator("summary").inner_text()
    pg.locator(".sw-toolrow .btn", has_text="Undo").click()
    pg.wait_for_function("!document.querySelector('.sw-shape-bar .sw-stat').innerText.includes(' of ')")


def test_new_column_completion_preview_and_edit(pg):
    _fresh(pg)
    _step(pg, "roles")
    pg.locator(".sw-fold .btn", has_text="Add").click()
    ed = pg.locator(".sw-derived-editor")
    ed.locator("input").first.fill("energy_x2")
    f = ed.locator("input[role=combobox]")
    f.click(); f.type("energ")
    pg.wait_for_selector(".sw-complete-list li:has-text('energy_wh')")
    f.press("Tab")
    assert f.input_value() == "energy_wh"
    f.type(" * 2")
    pg.wait_for_selector(".sw-formula-ok:has-text('First run')")
    f.fill("nope + 1")
    pg.wait_for_selector(".sw-derived-editor .sw-warn:has-text('nope')")
    f.fill("energy_wh * 2")
    pg.wait_for_selector(".sw-formula-ok")
    ed.locator(".btn", has_text="Add the column").click()
    pg.wait_for_selector(".sw-derived b:has-text('energy_x2')")
    # changed: renamed in place
    pg.locator(".sw-derived button[aria-label^='Change']").click()
    pg.locator(".sw-derived-editor input").first.fill("energy_double")
    pg.locator(".sw-derived-editor .btn", has_text="Save the column").click()
    pg.wait_for_selector(".sw-derived b:has-text('energy_double')")


def test_template_file_saved_and_loaded_with_its_summary(pg, tmp_path):
    _fresh(pg)
    _step(pg, "roles")
    pg.locator("input[aria-label='ki_roll: hold']").check()
    pg.locator(".sw-toolrow .btn", has_text="Template").click()
    pg.locator(".sw-menu button", has_text="Save").click()
    save_as(pg, "drone_tpl.json")
    pg.wait_for_selector(".toast:has-text('drone_tpl.json')")
    assert os.path.isfile(os.path.join(pg.env["out"], "drone_tpl.json"))
    pg.locator(".sw-toolrow .btn", has_text="Reset to guessed roles").click()
    pg.wait_for_function("document.querySelector(\"input[aria-label='ki_roll: param']\").checked")
    pg.locator(".sw-toolrow .btn", has_text="Template").click()
    pg.locator(".sw-menu button", has_text="Load").click()
    goto_folder(pg, pg.env["out"])
    pg.locator(".dialog .fs-row", has_text="drone_tpl.json").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".toast:has-text('Template applied:'):has-text('columns matched')")
    pg.wait_for_function("document.querySelector(\"input[aria-label='ki_roll: hold']\").checked")


def test_a_narrow_window_folds_the_side_panel(pg):
    _fresh(pg)
    pg.set_viewport_size({"width": 820, "height": 700})
    try:
        pg.wait_for_selector(".sw-left", state="detached")
        pg.locator(".sw-panel-toggle").click()
        pg.wait_for_selector(".sw-left")
        assert pg.evaluate("getComputedStyle(document.querySelector('.sw-left')).position") == "absolute"
        assert pg.evaluate("document.querySelector('.app').scrollWidth") <= 820
    finally:
        pg.set_viewport_size({"width": 1440, "height": 900})
