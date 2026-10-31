"""Sweeps area, step by step: the raw results, cleaning the columns, scenarios and parameters, goals
(several, compared), the results (the parallel plot filtered as in HiPlot, keep / exclude, export),
the report of the process, and the plot alone. The example: a drone's roll controller - parameters
kp_roll, ki_roll, filter_hz; scenarios wind, payload, gusts; outputs roll error, overshoot, energy..."""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg, save_as  # noqa: E402,F401

STEP = {"raw": 0, "clean": 1, "roles": 2, "goals": 3, "results": 4, "report": 5}


def _to_sweeps(pg):
    pg.locator(".areas .area-btn", has_text="Sweeps").click()
    pg.wait_for_selector(".sw-welcome, .sw-study-wrap")


def _bar_menu(pg, button, item):
    pg.locator(".areabar .btn", has_text=button).first.click()
    pg.locator(".menu.ctx button", has_text=item).first.click()


def _fresh(pg):
    """The example, from the start: its first step, no goals, the guessed roles."""
    _to_sweeps(pg)
    if pg.locator(".sw-welcome").count():
        pg.locator(".sw-welcome .btn", has_text="Try an example").click()
    else:
        _bar_menu(pg, "Study", "Start the study over")
    pg.wait_for_selector(".sw-steps")
    pg.wait_for_function("document.querySelector('.sw-step-btn.on .sw-step-n').innerText === '1'")


def _step(pg, name):
    pg.locator(".sw-step-btn").nth(STEP[name]).click()
    pg.wait_for_function(f"document.querySelector('.sw-step-btn.on .sw-step-n').innerText === '{STEP[name] + 1}'")


def _condition(pg, column, op, value):
    pg.locator(".sw-goal-part .btn", has_text="+ condition").click()
    row = pg.locator(".sw-cond").last
    row.locator("select[aria-label='Column']").select_option(column)
    row.locator("select[aria-label='Comparison']").select_option(op)
    box = row.locator("input[aria-label='Limit']")
    box.fill(str(value)); box.press("Enter")


def _optimize(pg, column, direction):
    pg.locator(".sw-goal-part .btn", has_text="+ goal").click()
    pg.locator(".sw-goal-part select[aria-label='Goal']").last.select_option(column)
    pg.locator(".sw-goal-part select[aria-label='Direction']").last.select_option(direction)


def _the_goal(pg):
    """Roll error <= 5 and overshoot <= 15 in every scenario, the least energy."""
    _step(pg, "goals")
    _condition(pg, "roll_error_deg", "<=", 5)
    _condition(pg, "overshoot_pct", "<=", 15)
    _optimize(pg, "energy_wh", "min")


def _holding(pg):
    pg.wait_for_selector(".sw-answer .sw-answer-n")
    return int(pg.locator(".sw-answer-n").inner_text().split()[0].replace(",", ""))


def _variant_holding(pg, i):
    cell = pg.locator(".sw-variants tbody tr").nth(i).locator("td").nth(2)
    pg.wait_for_function("el => !el.innerText.includes('…')", arg=cell.element_handle())
    return int(cell.inner_text().split("/")[0])


def test_area_switch_keeps_recordings(pg):
    assert pg.locator(".areas .area-btn").count() == 2
    _to_sweeps(pg)
    assert pg.locator(".rail").count() == 0
    pg.locator(".areas .area-btn", has_text="Recordings").click()
    pg.wait_for_selector(".rail")


def test_raw_results_table_and_plot(pg, tmp_path):
    _fresh(pg)
    assert "810 runs" in pg.locator(".sw-step-btn").nth(0).inner_text()
    assert "Rows 1–100 of 810" in pg.locator(".sw-raw").inner_text()
    pg.locator(".sw-raw .sw-table th", has_text="energy_wh").click()                 # sort
    pg.locator(".sw-center-tabs button", has_text="Parallel plot").click()
    pg.wait_for_selector(".pp canvas")
    assert "810 of 810" in pg.locator(".sw-plotbar .sw-count").inner_text()
    # the plot alone, to play with
    pg.locator(".sw-plotbar .btn", has_text="Export the plot").click()
    save_as(pg, "raw_plot.html")
    pg.wait_for_selector(".toast:has-text('raw_plot.html')")
    html = open(os.path.join(pg.env["out"], "raw_plot.html"), encoding="utf-8").read()
    assert "<canvas" in html and "kp_roll" in html


def test_clean_scenarios_and_parameters(pg):
    _fresh(pg)
    _step(pg, "clean")
    pg.locator(".sw-side-step .btn", has_text="Take out these").click()
    pg.wait_for_selector(".sw-clean tr.sw-out")
    assert "sim_version" in pg.locator(".sw-clean tr.sw-out").first.inner_text()
    _step(pg, "roles")
    radio = lambda col, role: pg.locator(f"input[aria-label='{col}: {role}']")
    for c in ("scenario_wind_mps", "scenario_payload_kg", "scenario_gusts"):
        assert radio(c, "hold").is_checked()
    for c in ("kp_roll", "ki_roll", "filter_hz"):
        assert radio(c, "param").is_checked()
    stat = lambda label: pg.locator(".sw-shape .sw-stat", has_text=label).locator(".sw-stat-value").inner_text()
    assert stat("Parameter sets") == "45" and stat("Combinations to hold in") == "18"
    radio("ki_roll", "hold").check()                                                 # what if ki were a scenario
    pg.wait_for_function("[...document.querySelectorAll('.sw-shape .sw-stat')].some(e => e.innerText.includes('Combinations') && e.innerText.includes('54'))")
    assert stat("Parameter sets") == "15"
    pg.locator(".sw-side-step .linklike", has_text="Back to the guessed roles").click()
    pg.wait_for_function("[...document.querySelectorAll('.sw-shape .sw-stat')].some(e => e.innerText.includes('Combinations') && e.innerText.includes('18'))")


def test_goals_compared_and_or(pg):
    _fresh(pg)
    _the_goal(pg)
    first = _variant_holding(pg, 0)
    assert 5 <= first <= 20
    pg.locator(".sw-goal-tabs .linklike", has_text="copy this goal").click()        # goal 2: a tighter roll limit
    pg.wait_for_selector(".sw-variants tbody tr:nth-child(2)")
    box = pg.locator(".sw-cond input[aria-label='Limit']").first
    box.fill("4"); box.press("Enter")
    pg.wait_for_function(f"(() => {{ const c = document.querySelectorAll('.sw-variants tbody tr')[1].querySelectorAll('td')[2].innerText; return !c.includes('…') && +c.split('/')[0] < {first}; }})()")
    # or: either condition is enough - more sets
    pg.locator(".sw-andor button", has_text="or").click()
    pg.wait_for_function(f"(() => {{ const c = document.querySelectorAll('.sw-variants tbody tr')[1].querySelectorAll('td')[2].innerText; return !c.includes('…') && +c.split('/')[0] > {first}; }})()")
    pg.locator(".sw-variants tbody tr").first.click()                               # goal 1 is the one shown
    _step(pg, "results")
    pg.wait_for_function(f"+document.querySelector('.sw-answer-n')?.innerText.split(' ')[0] === {first}")


def test_results_filter_keep_exclude_export_and_why(pg):
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".sw-table tbody tr")
    rows = lambda: pg.locator(".sw-table-wrap .sw-table tbody tr").count()
    total = rows()
    b = pg.locator(".pp canvas").bounding_box()
    x = b["x"] + 56
    pg.mouse.move(x, b["y"] + 50); pg.mouse.down(); pg.mouse.move(x, b["y"] + 150, steps=5); pg.mouse.up()
    pg.wait_for_selector(".sw-plotbar .btn:has-text('Clear 1 filters')")
    kept = rows()
    assert 0 < kept < total
    pg.locator(".sw-plotbar .btn", has_text="Keep").click()
    pg.wait_for_selector(".sw-plotbar .btn:has-text('Restore all (1)')")
    assert rows() == kept
    pg.locator(".sw-plotbar .btn", has_text="Export shown").click()
    save_as(pg, "shown.csv")
    pg.wait_for_selector(".toast:has-text('runs written')")
    assert len(open(os.path.join(pg.env["out"], "shown.csv")).read().splitlines()) - 1 == kept * 18
    pg.locator(".sw-plotbar .btn", has_text="Restore all").click()
    pg.wait_for_function(f"document.querySelectorAll('.sw-table-wrap .sw-table tbody tr').length === {total}")
    # a set that fails says why
    pg.locator(".sw-table tbody tr:not(.holds)").first.click()
    pg.wait_for_selector(".sw-detail .sw-why")
    assert "roll_error_deg" in pg.locator(".sw-why").inner_text() or "overshoot_pct" in pg.locator(".sw-why").inner_text()
    pg.locator(".sw-detail [aria-label='Close']").click()
    # the plot alone, from the results
    pg.locator(".sw-plotbar .btn", has_text="Export the plot").click()
    save_as(pg, "sets_plot.html")
    pg.wait_for_selector(".toast:has-text('sets_plot.html')")


def test_new_column_in_the_cleaning_step(pg):
    _fresh(pg)
    _step(pg, "clean")
    pg.locator(".sw-side-step .btn", has_text="per parameter set").click()
    pg.locator(".sw-derived-editor input").first.fill("energy_strong_max")
    pg.select_option(".sw-derived-editor select[aria-label='Operation']", "max")
    pg.select_option(".sw-derived-editor select[aria-label='Of the column']", "energy_wh")
    pg.locator(".sw-derived-editor .sw-pill", has_text="strong").click()
    pg.locator(".sw-derived-editor .btn", has_text="Add the column").click()
    pg.wait_for_selector(".sw-derived b:has-text('energy_strong_max')")
    _step(pg, "goals")
    _condition(pg, "energy_strong_max", "<=", 50)
    assert _variant_holding(pg, 0) > 0


def test_effects_map_next_runs_and_health(pg):
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.locator(".sw-center-tabs button", has_text="Which parameter matters").click()
    pg.wait_for_selector(".sw-effect")
    pg.locator(".sw-center-tabs button", has_text="Map").click()
    pg.wait_for_selector(".sw-map svg rect")
    pg.locator(".sw-center-tabs button", has_text="Next runs").click()
    pg.locator(".sw-next .btn", has_text="Suggest").click()
    pg.wait_for_selector(".sw-next .sw-table tbody tr")
    pg.locator(".sw-center-tabs button", has_text="Data health").click()
    pg.wait_for_selector(".sw-health .sw-table tbody tr")
    assert pg.locator(".sw-health .sw-table tbody tr").count() == 2                  # the example's two odd runs
    pg.locator(".sw-center-tabs button", has_text="Lines").click()


def test_report_of_the_process(pg):
    _fresh(pg)
    _step(pg, "clean")
    pg.locator(".sw-side-step .btn", has_text="Take out these").click()
    _the_goal(pg)
    pg.locator(".sw-goal-tabs .linklike", has_text="copy this goal").click()
    _step(pg, "report")
    preview = pg.locator(".sw-report-preview").inner_text()
    pg.locator(".sw-report-format", has_text="Interactive HTML").click()
    pg.locator(".sw-report-page .btn", has_text="Make the report").click()
    save_as(pg, "process.html")
    pg.wait_for_selector(".toast:has-text('process.html')", timeout=60000)
    html = open(os.path.join(pg.env["out"], "process.html"), encoding="utf-8").read()
    assert "Columns taken out" in html and "Goal 2" in html and "<canvas" in html
    assert "filters" in preview.lower() or "every parameter set" in preview.lower()
    pg.locator(".sw-report-format", has_text="Word").click()
    pg.locator(".sw-report-page .btn", has_text="Make the report").click()
    save_as(pg, "process.docx")
    pg.wait_for_selector(".toast:has-text('process.docx')", timeout=60000)


def test_save_reopen_and_close(pg):
    _fresh(pg)
    _the_goal(pg)
    _bar_menu(pg, "Study", "Save the study")
    save_as(pg, "drone.svsweep")
    pg.wait_for_selector(".toast:has-text('Saved')")
    n = pg.locator(".areabar .tab").count()
    _bar_menu(pg, "Open", "Open a saved study")
    goto_folder(pg, pg.env["out"])
    pg.locator(".dialog .fs-row", has_text="drone.svsweep").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function(f"document.querySelectorAll('.areabar .tab').length === {n + 1}")
    assert pg.locator(".sw-step-btn.on .sw-step-n").inner_text() == "4"              # where it was saved
    assert pg.locator(".sw-cond").count() == 2
    _bar_menu(pg, "Study", "Close this table")
    pg.wait_for_function(f"document.querySelectorAll('.areabar .tab').length === {n}")


def test_two_sweeps_merged(pg):
    _to_sweeps(pg)
    while pg.locator(".areabar .tab").count():
        _bar_menu(pg, "Study", "Close this table")
    pg.wait_for_selector(".sw-welcome")
    pg.locator(".sw-welcome .btn", has_text="two sweeps, merged").click()
    pg.wait_for_selector(".sw-steps")
    pg.wait_for_function("document.querySelectorAll('.sw-hide-box .sw-tag').length === 2")
    _step(pg, "roles")
    pg.wait_for_function("+[...document.querySelectorAll('.sw-shape .sw-stat')].find(e => e.innerText.includes('Parameter sets')).querySelector('.sw-stat-value').innerText > 45")


def test_a_table_with_no_parameter_still_opens(pg, tmp_path):
    (tmp_path / "flat.csv").write_text("a,b\n1.5,2.25\n3.75,4.125\n5.5,6.875\n7.25,8.5\n")
    _to_sweeps(pg)
    _bar_menu(pg, "Open", "Open a table") if pg.locator(".sw-welcome").count() == 0 else pg.locator(".sw-welcome .btn", has_text="Open a table").click()
    goto_folder(pg, str(tmp_path))
    pg.locator(".dialog .fs-row", has_text="flat.csv").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".sw-raw .sw-table")                                        # the raw results first, always
    _step(pg, "goals")
    pg.wait_for_selector(".sw-banner:has-text('No column is a parameter')")
    pg.locator(".sw-banner .btn", has_text="Scenarios").click()
    pg.locator("input[aria-label='a: param']").check()
    pg.wait_for_function("+[...document.querySelectorAll('.sw-shape .sw-stat')].find(e => e.innerText.includes('Parameter sets')).querySelector('.sw-stat-value').innerText === 4")


def test_one_place_for_each_control(pg):
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".pp-axis-name")
    names = lambda: [x.strip() for x in pg.locator(".pp-axis-name").all_inner_texts()]
    first = names()[0]
    pg.locator(".pp-axis-name").nth(1).click()
    pg.locator(".sw-axis-menu button", has_text="Colour the lines by this").click()
    pg.keyboard.press("Escape")
    assert names()[1].split(" ·")[0] in pg.locator(".sw-colour-key").inner_text()
    a = pg.locator(".pp-axis-name").nth(0).bounding_box(); c = pg.locator(".pp-axis-name").nth(2).bounding_box()
    pg.mouse.move(a["x"] + a["width"] / 2, a["y"] + a["height"] / 2); pg.mouse.down()
    pg.mouse.move(c["x"] + c["width"] / 2, a["y"] + a["height"] / 2, steps=8); pg.mouse.up()
    pg.wait_for_function(f"document.querySelectorAll('.pp-axis-name')[2].innerText.trim() === {first!r}")


def _open_table(pg, folder, name):
    _to_sweeps(pg)
    if pg.locator(".sw-welcome").count():
        pg.locator(".sw-welcome .btn", has_text="Open a table").click()
    else:
        _bar_menu(pg, "Open", "Open a table")
    goto_folder(pg, str(folder))
    pg.locator(".dialog .fs-row", has_text=name).click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".sw-steps")


def test_a_sets_recordings_open_in_recordings(pg, tmp_path):
    ex = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "examples"))
    rows = ["recording,gain,scenario,score"]
    for i, f in enumerate(("run_012.csv", "run_013.csv", "run_014.csv")):
        for g in (1, 2):
            rows.append(f"{os.path.join(ex, f)},{g},{'abc'[i]},{g * 10 + i + 0.37 * g * i}")
    (tmp_path / "with_recordings.csv").write_text("\n".join(rows) + "\n")
    _open_table(pg, tmp_path, "with_recordings.csv")
    _step(pg, "roles")
    assert pg.locator("input[aria-label='recording: recording']").is_checked()
    pg.locator("input[aria-label='scenario: hold']").check()
    _step(pg, "results")
    pg.locator(".sw-table tbody tr").first.click()
    pg.locator(".sw-detail .btn", has_text="recordings in Recordings").click()
    pg.wait_for_selector(".rail")
    pg.wait_for_function("document.querySelectorAll('.run-head').length >= 3")


def test_follow_the_file_and_templates(pg, tmp_path):
    f = tmp_path / "grow.csv"
    rows = ["scenario,p,out"] + [f"{sc},{p},{p * 10 + i * 0.37}" for i, (sc, p) in enumerate((s, p) for s in "ab" for p in (1, 2, 3))]
    f.write_text("\n".join(rows) + "\n")
    _open_table(pg, tmp_path, "grow.csv")
    _step(pg, "goals")
    _optimize(pg, "out", "max")
    f.write_text("\n".join(rows + [f"{sc},4,{40 + i * 0.37}" for i, sc in enumerate("ab")]) + "\n")
    pg.wait_for_selector(".sw-banner:has-text('changed')", timeout=15000)
    pg.locator(".sw-banner .btn", has_text="Read the table again").click()
    _step(pg, "results")
    pg.wait_for_function("document.querySelectorAll('.sw-table tbody tr').length === 4")
    _bar_menu(pg, "Study", "Save as a template")
    pg.fill(".dialog input", "grow check"); pg.keyboard.press("Enter")
    pg.wait_for_selector(".dialog", state="detached")
    (tmp_path / "grow2.csv").write_text(f.read_text())
    _open_table(pg, tmp_path, "grow2.csv")
    pg.wait_for_selector(".sw-banner:has-text('grow check')")
    pg.locator(".sw-banner .btn", has_text="Apply").click()
    _step(pg, "goals")
    assert pg.locator(".sw-goal-part select[aria-label='Goal']").first.input_value() == "out"


def test_take_out_a_merged_table_delete_a_goal_and_column_groups(pg):
    _to_sweeps(pg)
    while pg.locator(".areabar .tab").count():
        _bar_menu(pg, "Study", "Close this table")
    pg.locator(".sw-welcome .btn", has_text="two sweeps, merged").click()
    pg.wait_for_function("document.querySelectorAll('.sw-hide-box .sw-tag').length === 2")
    pg.locator(".sw-tag-x").first.click()                                          # the merged table out again
    pg.wait_for_function("document.querySelectorAll('.sw-hide-box .sw-tag').length === 1")
    assert "810 runs" in pg.locator(".sw-step-btn").nth(0).inner_text()
    # the raw table: only the outputs
    pg.locator(".sw-raw select[title^='Show every column']").select_option("outputs")
    heads = [h.strip() for h in pg.locator(".sw-raw thead th").all_inner_texts()]
    assert heads[0].startswith("roll_error_deg") and "kp_roll" not in " ".join(heads)
    # a goal deleted from its tab
    _the_goal(pg)
    pg.locator(".sw-goal-tabs .linklike", has_text="copy this goal").click()
    pg.wait_for_function("document.querySelectorAll('.sw-goal-tab').length === 2")
    pg.locator(".sw-goal-tab").nth(1).locator(".sw-tag-x").click()
    pg.wait_for_function("document.querySelectorAll('.sw-goal-tab').length === 1")
    # results: parameters and the goal only
    _step(pg, "results")
    pg.wait_for_selector(".sw-table th:has-text('worst')")                          # the answer to this goal is in
    pg.locator(".sw-plotbar select[aria-label='Show columns']").select_option("params-goal")
    pg.wait_for_timeout(300)
    names = [x.strip() for x in pg.locator(".pp-axis-name").all_inner_texts()]
    assert names[:3] == ["kp_roll", "ki_roll", "filter_hz"] and len(names) == 6


def test_a_parameter_taken_out_leaves_the_map_and_next_runs(pg):
    """S01: a parameter taken out in Clean columns is not offered by the map (the server refused it)."""
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "clean")
    pg.locator("input[aria-label='Keep kp_roll']").uncheck()
    _step(pg, "results")
    pg.locator(".sw-center-tabs button", has_text="Map").click()
    pg.wait_for_selector(".sw-map svg rect")
    assert pg.locator(".sw-map .sw-error").count() == 0
    options = pg.locator(".sw-map select").first.locator("option").all_inner_texts()
    assert "kp_roll" not in options and "ki_roll" in options
    pg.locator(".sw-center-tabs button", has_text="Next runs").click()
    pg.locator(".sw-next .btn", has_text="Suggest").click()
    pg.wait_for_selector(".sw-next-main b:has-text('Suggested')")        # an answer (maybe none), not an error
    assert pg.locator(".sw-next .sw-error").count() == 0
    _step(pg, "clean")
    pg.locator("input[aria-label='Keep kp_roll']").check()


def test_a_goals_weight_is_its_own_and_template_saved_says_so(pg):
    """S01: switching goals shows each goal's own weight; saving a template says it was saved."""
    _fresh(pg)
    _step(pg, "goals")
    _optimize(pg, "energy_wh", "min")
    _optimize(pg, "roll_error_deg", "min")
    w = pg.locator(".sw-goal-part input[aria-label='Weight']").last
    w.fill("3"); w.press("Tab")
    pg.locator(".sw-goal-tabs .linklike", has_text="+ empty goal").click()
    _optimize(pg, "energy_wh", "min")
    _optimize(pg, "roll_error_deg", "min")
    assert pg.locator(".sw-goal-part input[aria-label='Weight']").last.input_value() == "1"
    pg.locator(".sw-goal-tabs button[role='tab']").first.click()
    assert pg.locator(".sw-goal-part input[aria-label='Weight']").last.input_value() == "3"
    _bar_menu(pg, "Study", "Save as a template")
    pg.fill(".dialog input", "weights check"); pg.keyboard.press("Enter")
    pg.wait_for_selector(".toast:has-text('Template saved: weights check')")
    _bar_menu(pg, "Study", "Delete a template")
    pg.locator(".menu.ctx button", has_text="weights check").click()
    pg.wait_for_selector(".toast:has-text('Template deleted: weights check')")


def test_undo_redo_and_the_studies_open_again(pg):
    """S02: a change to the question is undone and redone (buttons, Ctrl+Z / Ctrl+Y, Ctrl+K); the
    open studies come back after the app starts again, where they were."""
    _fresh(pg)
    _step(pg, "goals")
    undo = pg.locator(".areabar button[aria-label='Undo']")
    redo = pg.locator(".areabar button[aria-label='Redo']")
    assert undo.is_disabled()                                         # opening a table is not a change
    _condition(pg, "roll_error_deg", "<=", 5)
    pg.wait_for_function("document.querySelectorAll('.sw-cond').length === 1")
    undo.click()
    pg.wait_for_function("document.querySelectorAll('.sw-cond').length === 0")
    redo.click()
    pg.wait_for_function("document.querySelectorAll('.sw-cond').length === 1")
    pg.locator(".sw-side-step").click(position={"x": 5, "y": 5})     # out of any input
    pg.keyboard.press("Control+z")
    pg.wait_for_function("document.querySelectorAll('.sw-cond').length === 0")
    pg.keyboard.press("Control+y")
    pg.wait_for_function("document.querySelectorAll('.sw-cond').length === 1")
    pg.keyboard.press("Control+k")
    pg.fill(".palette-input", "Undo"); pg.keyboard.press("Enter")
    pg.wait_for_function("document.querySelectorAll('.sw-cond').length === 0")
    _condition(pg, "overshoot_pct", "<=", 15)
    pg.wait_for_timeout(1500)                                        # the autosave, a moment after the change
    pg.reload()
    pg.wait_for_selector(".app")
    _to_sweeps(pg)
    pg.wait_for_selector(".sw-steps")
    assert pg.locator(".sw-step-btn.on .sw-step-n").inner_text() == "4"
    assert pg.locator(".sw-cond").count() == 1
    assert undo.is_disabled()                                        # what was reopened is not a change to undo
