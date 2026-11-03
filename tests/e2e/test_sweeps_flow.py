"""Sweeps area, step by step: the raw results, cleaning the columns, scenarios and parameters, goals
(several, compared), the results (the parallel plot filtered as in HiPlot, keep / exclude, export),
the report of the process, and the plot alone. The example: a drone's roll controller - parameters
kp_roll, ki_roll, filter_hz; scenarios wind, payload, gusts; outputs roll error, overshoot, energy..."""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg, save_as  # noqa: E402,F401

# the four steps (2026-11-01 redesign); "clean" is part of the columns, "report" and "run" are tools
STEP = {"raw": 0, "clean": 1, "roles": 1, "goals": 2, "results": 3, "report": 3}
NAV = {"raw": "raw", "clean": "roles", "roles": "roles", "goals": "goals", "results": "results", "report": "results"}


def _to_sweeps(pg):
    pg.locator(".areas .area-btn", has_text="Sweeps").click()
    pg.wait_for_selector(".sw-welcome, .sw-study-wrap")


def _bar_menu(pg, button, item):
    pg.locator(".areabar .btn", has_text=button).first.click()
    pg.locator(".menu.ctx button", has_text=item).first.click()


def _close_studies(pg):
    """Every study closed (its tab's ×): the welcome page."""
    while pg.locator(".areabar .tab").count():
        n = pg.locator(".areabar .tab").count()
        pg.locator(".areabar .tab .x").first.click()
        pg.wait_for_function(f"document.querySelectorAll('.areabar .tab').length === {n - 1}")
    pg.wait_for_selector(".sw-welcome")


def _merged_example(pg):
    """The example's two sweeps, each a table, merged into a third one the next steps work on."""
    _to_sweeps(pg)
    _close_studies(pg)
    pg.locator(".sw-welcome .btn", has_text="two sweeps, merged").click()
    pg.wait_for_selector(".sw-steps")
    pg.wait_for_function("document.querySelectorAll('.sw-table-item').length === 3")
    pg.wait_for_function("document.querySelector('.sw-continue select').value === '2'")


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
    """A step (the four of the 2026-11-01 redesign); the report and running sets are tools of the results."""
    pg.locator(f".sw-step-btn[data-step='{NAV[name]}']").click()
    pg.wait_for_function(f"document.querySelector('.sw-step-btn.on .sw-step-n').innerText === '{STEP[name] + 1}'")
    if name == "report":
        _tab(pg, "report")


def _tab(pg, name):
    """A results tab: sets, runs, charts, next, report."""
    pg.locator(f".sw-center-tabs button[data-tab='{name}']").click()


def _more(pg):
    """The goal's More options (the full condition editor, robustness, several goals)."""
    d = pg.locator("details.sw-more")
    if d.count() and not d.evaluate("e => e.open"):
        d.locator("summary").click()


def _condition(pg, column, op, value):
    """At least / at most in the goal's table; other comparisons through More options."""
    if op in ("<=", ">="):
        box = pg.locator(f"input[aria-label='{column} {'at most' if op == '<=' else 'at least'}']")
        box.fill(str(value)); box.press("Enter")
        # the end state: the answer has this limit (its count beside it)
        pg.locator(f".sw-goal-table tr[data-col='{column}'] .sw-limit-met").first.wait_for()
        return
    _more(pg)
    pg.locator(".sw-goal-part .btn", has_text="+ condition").click()
    row = pg.locator(".sw-cond").last
    col = row.locator("input[aria-label='Column']")                              # typed: part of the name finds it
    col.click(); col.fill(column.replace("_", " ")); col.press("Enter")
    row.locator("select[aria-label='Comparison']").select_option(op)
    box = row.locator("input[aria-label='Limit']")
    box.fill(str(value)); box.press("Enter")


def _optimize(pg, column, direction):
    pg.locator(f"select[aria-label='Optimize {column}']").select_option(direction)


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
    if not pg.locator(".sw-variants").count():          # one goal: no comparison table, the count
        return _holding(pg)
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
    # zoom: the buttons (and the wheel); kept when the tab changes
    pg.locator(".sw-zoom button[aria-label^='Zoom in']").click()
    pg.wait_for_function("document.querySelector('.pp canvas')?.dataset.zoom === '1.25'")
    pg.locator(".sw-center-tabs button", has_text="Table").click()
    pg.locator(".sw-center-tabs button", has_text="Parallel plot").click()
    pg.wait_for_function("document.querySelector('.pp canvas')?.dataset.zoom === '1.25'")
    # a click on a column's name colours by it
    pg.locator(".pp-axis-name", has_text="energy_wh").click()
    pg.wait_for_selector(".sw-plotbar .hint:has-text('energy_wh')")
    # the table to a file: the save dialog at once, HTML first on the plot's tab - the plot as it was
    pg.locator(".sw-table-item button[aria-label^='Export as CSV or HTML']").click()
    assert pg.locator(".savename select").input_value() == "1"
    save_as(pg, "raw_plot.html")
    pg.wait_for_selector(".toast:has-text('raw_plot.html')")
    html = open(os.path.join(pg.env["out"], "raw_plot.html"), encoding="utf-8").read()
    assert "<canvas" in html and "kp_roll" in html and '"colorBy": "energy_wh"' in html and '"k": 1.25' in html
    pg.locator(".sw-zoom .btn", has_text="Reset zoom").click()
    pg.wait_for_function("document.querySelector('.pp canvas')?.dataset.zoom === '1.00'")
    pg.locator(".sw-center-tabs button", has_text="Table").click()
    pg.locator(".sw-table-item button[aria-label^='Export as CSV or HTML']").click()
    assert pg.locator(".savename select").input_value() == "0"
    save_as(pg, "raw.csv")
    pg.wait_for_selector(".toast:has-text('raw.csv')")
    assert len(open(os.path.join(pg.env["out"], "raw.csv")).read().splitlines()) == 811


def test_clean_scenarios_and_parameters(pg):
    _fresh(pg)
    _step(pg, "roles")
    radio = lambda col, role: pg.locator(f"input[aria-label='{col}: {role}']")
    if not radio("sim_version", "ignore").is_checked():                              # the constant one: not used
        pg.locator(".sw-side-step .btn", has_text="as not used").click()
    pg.wait_for_function("document.querySelector(\"input[aria-label='sim_version: ignore']\").checked")
    for c in ("scenario_wind_mps", "scenario_payload_kg", "scenario_gusts"):
        assert radio(c, "hold").is_checked()
    for c in ("kp_roll", "ki_roll", "filter_hz"):
        assert radio(c, "param").is_checked()
    stat = lambda label: pg.locator(".sw-shape .sw-stat", has_text=label).locator(".sw-stat-value").inner_text()
    assert stat("Parameter sets") == "45" and stat("Combinations to hold in") == "18"
    radio("ki_roll", "hold").check()                                                 # what if ki were a scenario
    pg.wait_for_function("[...document.querySelectorAll('.sw-shape .sw-stat')].some(e => e.innerText.includes('Combinations') && e.innerText.includes('54'))")
    assert stat("Parameter sets") == "15"
    pg.locator(".sw-toolrow .btn", has_text="Reset to guessed roles").click()
    pg.wait_for_function("[...document.querySelectorAll('.sw-shape .sw-stat')].some(e => e.innerText.includes('Combinations') && e.innerText.includes('18'))")


def test_goals_compared_and_or(pg):
    _fresh(pg)
    _the_goal(pg)
    first = _variant_holding(pg, 0)
    assert 5 <= first <= 20
    pg.locator(".sw-goal-tabs .linklike", has_text="copy this goal").click()        # goal 2: a tighter roll limit
    pg.wait_for_selector(".sw-variants tbody tr:nth-child(2)")
    _condition(pg, "roll_error_deg", "<=", 4)
    pg.wait_for_function(f"(() => {{ const c = document.querySelectorAll('.sw-variants tbody tr')[1].querySelectorAll('td')[2].innerText; return !c.includes('…') && +c.split('/')[0] < {first}; }})()")
    # or: either condition is enough - more sets (More options)
    _more(pg)
    pg.locator(".sw-andor button", has_text="or").first.click()
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
    pg.locator(".sw-show select").select_option("all")                           # every set, not only those that hold
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
    _step(pg, "roles")
    pg.locator(".sw-fold .btn", has_text="Add").click()                            # the form opens only on + Add
    pg.locator(".sw-seg button", has_text="per parameter set").click()
    pg.locator(".sw-derived-editor input").first.fill("energy_strong_max")
    pg.select_option(".sw-derived-editor select[aria-label='Operation']", "max")
    pg.select_option(".sw-derived-editor select[aria-label='Of the column']", "energy_wh")
    pg.locator(".sw-derived-editor .sw-pill", has_text="strong").click()
    pg.locator(".sw-derived-editor .btn", has_text="Add the column").click()
    pg.wait_for_selector(".sw-derived b:has-text('energy_strong_max')")
    _step(pg, "goals")
    _condition(pg, "energy_strong_max", "<=", 50)
    assert _variant_holding(pg, 0) > 0


def test_report_of_the_process(pg):
    _fresh(pg)
    _step(pg, "roles")
    _the_goal(pg)
    pg.locator(".sw-goal-tabs .linklike", has_text="copy this goal").click()
    _step(pg, "report")
    preview = pg.locator(".sw-report-preview").inner_text()
    # the map and the point plots are those on screen (Charts' first pane: points; next runs' map);
    # "which parameter matters" is not part of a sweep's report any more (owner, 2026-11-02)
    boxes = pg.locator(".sw-report-inc").inner_text()
    assert "Which parameter matters" not in boxes and "Map (1)" in boxes and "Points (1)" in boxes, boxes
    pg.locator(".sw-report-format", has_text="Interactive HTML").click()
    pg.locator(".sw-report-page .btn", has_text="Make the report").click()
    save_as(pg, "process.html")
    pg.wait_for_selector(".toast:has-text('process.html')", timeout=60000)
    html = open(os.path.join(pg.env["out"], "process.html"), encoding="utf-8").read()
    assert "Goal 2" in html and "<canvas" in html
    assert "<h2>Map: " in html and "<h2>Points: " in html
    assert "filters" in preview.lower() or "every parameter set" in preview.lower() or "shown:" in preview.lower()
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
    assert pg.locator(".sw-step-btn.on .sw-step-n").inner_text() == "3"              # where it was saved: the goal
    pg.wait_for_function("document.querySelectorAll('.sw-limit-met').length === 2")
    pg.locator(".areabar .tab.active .x").click()
    pg.wait_for_function(f"document.querySelectorAll('.areabar .tab').length === {n}")


def test_two_sweeps_merged(pg):
    _merged_example(pg)
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
    pg.locator(".sw-banner .btn", has_text="Columns").click()
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
    assert pg.locator("input[aria-label='recording: ident']").is_checked()
    assert pg.locator(".sw-ident-kind").input_value() == "recording"
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
    assert pg.locator("select[aria-label='Optimize out']").input_value() in ("min", "max")


def test_take_out_a_merged_table_delete_a_goal_and_column_groups(pg):
    _merged_example(pg)
    pg.locator(".sw-table-item").nth(2).locator("button[aria-label^='Close']").click()   # the merged table out again
    pg.wait_for_function("document.querySelectorAll('.sw-table-item').length === 2")
    pg.wait_for_function("document.querySelector('.sw-step-btn').innerText.includes('810 runs')")   # back on the first table
    pg.locator(".sw-table-item .sw-table-name").first.click()
    # the raw table: only the outputs
    pg.locator(".sw-raw .sw-colpick-btn").click()
    pg.locator(".sw-colpick-pop .linklike", has_text="Outputs only").click()
    pg.keyboard.press("Escape")
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
    pg.locator(".sw-plotbar .sw-colpick-btn").click()
    pg.locator(".sw-colpick-pop .linklike", has_text="Parameters and the goal").click()
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    names = [x.strip() for x in pg.locator(".pp-axis-name").all_inner_texts()]
    # (the rank's axis is added when an answer with it arrives after the choice: S19)
    names = [x for x in names if x != "rank"]
    assert names[:3] == ["kp_roll", "ki_roll", "filter_hz"] and len(names) == 6, " | ".join(names)


def test_a_goals_weight_is_its_own_and_template_saved_says_so(pg):
    """S01: switching goals shows each goal's own weight; saving a template says it was saved."""
    _fresh(pg)
    _step(pg, "goals")
    _optimize(pg, "energy_wh", "min")
    _optimize(pg, "roll_error_deg", "min")
    w = pg.locator(".sw-goal-table input[aria-label^='Weight of']").last
    w.fill("3"); w.press("Tab")
    pg.locator(".sw-goal-tabs .linklike", has_text="+ empty goal").click()
    _optimize(pg, "energy_wh", "min")
    _optimize(pg, "roll_error_deg", "min")
    assert pg.locator(".sw-goal-table input[aria-label^='Weight of']").last.input_value() == "1"
    pg.locator(".sw-goal-tabs button[role='tab']").first.click()
    assert pg.locator(".sw-goal-table input[aria-label^='Weight of']").last.input_value() == "3"
    _bar_menu(pg, "Study", "Save as a template")
    pg.fill(".dialog input", "weights check"); pg.keyboard.press("Enter")
    pg.wait_for_selector(".toast:has-text('Template saved: weights check')")
    _bar_menu(pg, "Study", "Templates…")
    pg.locator(".sw-tpl-item", has_text="weights check").click()
    pg.locator(".sw-tpl .dialog-foot .btn", has_text="Delete").click()
    pg.locator(".dialog.small .btn.primary").click()                           # yes, delete
    pg.wait_for_selector(".toast:has-text('Template deleted: weights check')")
    pg.keyboard.press("Escape")


def test_undo_redo_and_the_studies_open_again(pg):
    """S02: a change to the question is undone and redone (buttons, Ctrl+Z / Ctrl+Y, Ctrl+K); the
    open studies come back after the app starts again, where they were."""
    _fresh(pg)
    _step(pg, "goals")
    undo = pg.locator(".areabar button[aria-label='Undo']")
    redo = pg.locator(".areabar button[aria-label='Redo']")
    assert undo.is_disabled()                                         # opening a table is not a change
    _condition(pg, "roll_error_deg", "<=", 5)
    pg.wait_for_function("document.querySelectorAll('.sw-goal-table tr.sw-goal-on').length === 1")
    undo.click()
    pg.wait_for_function("document.querySelectorAll('.sw-goal-table tr.sw-goal-on').length === 0")
    redo.click()
    pg.wait_for_function("document.querySelectorAll('.sw-goal-table tr.sw-goal-on').length === 1")
    pg.locator(".sw-side-step").click(position={"x": 5, "y": 5})     # out of any input
    pg.keyboard.press("Control+z")
    pg.wait_for_function("document.querySelectorAll('.sw-goal-table tr.sw-goal-on').length === 0")
    pg.keyboard.press("Control+y")
    pg.wait_for_function("document.querySelectorAll('.sw-goal-table tr.sw-goal-on').length === 1")
    pg.keyboard.press("Control+k")
    pg.fill(".palette-input", "Undo"); pg.keyboard.press("Enter")
    pg.wait_for_function("document.querySelectorAll('.sw-goal-table tr.sw-goal-on').length === 0")
    _condition(pg, "overshoot_pct", "<=", 15)
    pg.wait_for_timeout(1500)                                        # the autosave, a moment after the change
    pg.reload()
    pg.wait_for_selector(".app")
    _to_sweeps(pg)
    pg.wait_for_selector(".sw-steps")
    assert pg.locator(".sw-step-btn.on .sw-step-n").inner_text() == "3"
    assert pg.locator(".sw-goal-table tr.sw-goal-on").count() == 1
    assert undo.is_disabled()                                        # what was reopened is not a change to undo


def test_many_columns_scroll_pick_and_panels(pg, tmp_path):
    """S03: with many columns the plot keeps room per axis and scrolls sideways (the wheel too), or
    fits the width; columns are chosen by typing; the side panels are dragged wider and hidden."""
    f = tmp_path / "wide.csv"
    outs = [f"out_{i:02d}" for i in range(40)]
    rows = ["scenario,p,q," + ",".join(outs)]
    for sc in "ab":
        for p in (1, 2, 3):
            for q in (10, 20):
                rows.append(f"{sc},{p},{q}," + ",".join(str(p * q + i * 0.1 + (sc == 'b')) for i in range(40)))
    f.write_text("\n".join(rows) + "\n")
    _open_table(pg, tmp_path, "wide.csv")
    _step(pg, "results")
    pg.wait_for_selector(".pp canvas")
    # every column: the plot is wider than the screen and scrolls
    pg.locator(".sw-plotbar .sw-colpick-btn").click()
    pg.locator(".sw-colpick-pop .linklike", has_text="All columns").click()
    pg.keyboard.press("Escape")
    sc = pg.locator(".pp-scroll")
    pg.wait_for_function("(() => { const e = document.querySelector('.pp-scroll'); return e.scrollWidth > e.clientWidth + 100; })()")
    sc.hover()
    pg.mouse.wheel(0, 400)
    pg.wait_for_function("document.querySelector('.pp-scroll').scrollLeft > 100")
    # S13: a slider under the plot says where the view is and moves it
    slider = pg.locator(".pp-slider input[type='range']")
    assert "axes 1–" not in pg.locator(".pp-slider-at").inner_text()             # the wheel moved it already
    slider.focus(); pg.keyboard.press("End")
    pg.wait_for_function("(() => { const e = document.querySelector('.pp-scroll'); return e.scrollLeft >= e.scrollWidth - e.clientWidth - 2; })()")
    pg.wait_for_function("document.querySelector('.pp-slider-at').innerText.endsWith('–42 of 42 on screen')")
    slider.focus(); pg.keyboard.press("Home")
    pg.wait_for_function("document.querySelector('.pp-scroll').scrollLeft === 0")
    pg.wait_for_function("document.querySelector('.pp-slider-at').innerText.startsWith('axes 1–')")
    pg.locator(".sw-plotbar .btn", has_text="Fit to width").click()
    pg.wait_for_function("(() => { const e = document.querySelector('.pp-scroll'); return e.scrollWidth <= e.clientWidth + 1; })()")
    assert pg.locator(".pp-slider").count() == 0
    # typed: only the columns whose name matches
    pg.locator(".sw-plotbar .sw-colpick-btn").click()
    pg.locator(".sw-colpick-pop input[aria-label='Type part of a name…']").fill("out_0")
    pg.locator(".sw-colpick-pop .btn", has_text="Choose these 10 only").click()
    pg.wait_for_function("document.querySelectorAll('.pp-axis-name').length === 10")
    pg.keyboard.press("Escape")
    assert pg.locator(".sw-colpick-pop").count() == 0
    # the steps' panel: dragged wider, then hidden and shown again
    left = pg.locator(".sw-left")
    w0 = left.bounding_box()["width"]
    r = pg.locator(".sw-study > .resizer").first.bounding_box()
    pg.mouse.move(r["x"] + 3, r["y"] + 200); pg.mouse.down(); pg.mouse.move(r["x"] + 103, r["y"] + 200, steps=4); pg.mouse.up()
    assert left.bounding_box()["width"] > w0 + 30                                # wider, up to 320 px (owner, 2026-11-02)
    assert left.bounding_box()["width"] <= 321
    pg.locator(".sw-panel-toggle").click()
    assert pg.locator(".sw-left").count() == 0
    pg.locator(".sw-panel-toggle").click()
    pg.wait_for_selector(".sw-left")


def test_the_sets_that_hold_sorted_and_exported(pg):
    """S04: only the sets that hold, sorted by a column, with a column added - and exported as shown
    (a row per set) and as their runs."""
    import csv
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".sw-table th:has-text('worst')")
    holding = _holding(pg)
    rows = lambda: pg.locator(".sw-sets-table tbody tr").count()
    assert rows() == holding                                                       # Show: Holds, first
    pg.locator(".sw-show select").select_option("all")
    pg.wait_for_function("document.querySelectorAll('.sw-sets-table tbody tr').length === 45")
    pg.locator(".sw-show select").select_option("holds")
    pg.wait_for_function(f"document.querySelectorAll('.sw-sets-table tbody tr').length === {holding}")
    assert pg.locator(".sw-sets-table td.st-2.bad").count() == 0
    # sorted by kp_roll, the largest first (a second click)
    pg.locator(".sw-sets-table th", has_text="kp_roll").click()
    pg.locator(".sw-sets-table th", has_text="kp_roll").click()
    col = pg.locator(".sw-sets-table thead th").all_inner_texts().index(next(h for h in pg.locator(".sw-sets-table thead th").all_inner_texts() if h.startswith("kp_roll")))
    kp = [float(x) for x in pg.locator(f".sw-sets-table tbody tr td:nth-child({col + 1})").all_inner_texts()]
    assert kp == sorted(kp, reverse=True)
    # a column more: the settle time
    pg.locator(".sw-sets-bar .sw-colpick-btn").click()
    pg.locator(".sw-colpick-pop input[aria-label='Type part of a name…']").fill("settle")
    pg.locator(".sw-colpick-pop .msp-item", has_text="settle_time_s").locator("input").check()
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".sw-sets-table th:has-text('settle_time_s')")
    # export: the sets, as shown
    pg.locator(".sw-sets-bar .btn", has_text="Export").click()
    pg.locator(".menu.ctx button", has_text="a row each").click()
    save_as(pg, "holding_sets.csv")
    pg.wait_for_selector(".toast:has-text('sets written')")
    with open(os.path.join(pg.env["out"], "holding_sets.csv"), encoding="utf-8-sig") as f:
        got = list(csv.reader(f))
    assert len(got) - 1 == holding and any(h.startswith("settle_time_s") for h in got[0])
    k = next(j for j, h in enumerate(got[0]) if h == "kp_roll")
    assert [float(r[k]) for r in got[1:]] == kp                                     # the table's order
    assert {r[1] for r in got[1:]} == {"1"}                                         # every one holds
    # and their runs
    pg.locator(".sw-sets-bar .btn", has_text="Export").click()
    pg.locator(".menu.ctx button", has_text="Their runs").click()
    save_as(pg, "holding_runs.csv")
    pg.wait_for_selector(".toast:has-text('runs written')")
    assert len(open(os.path.join(pg.env["out"], "holding_runs.csv")).read().splitlines()) - 1 == holding * 18
    # undone in one step each: the column, the sort, Show (holds, all) - back to every set
    pg.locator(".sw-sets-table").click(position={"x": 5, "y": 5})
    for _ in range(4):
        pg.keyboard.press("Control+z")
    pg.wait_for_function("document.querySelectorAll('.sw-sets-table tbody tr').length === 45")


def test_optimize_says_how_it_ranks_and_weights_count(pg):
    """Optimize: the step says by what the sets that hold are ranked; with two objectives the
    weights decide the order (the first alone used to)."""
    _fresh(pg)
    _step(pg, "goals")
    now = pg.locator(".sw-optimize-now")
    assert "Nothing to optimize" in now.inner_text()
    _condition(pg, "roll_error_deg", "<=", 5)
    _optimize(pg, "energy_wh", "min")
    pg.wait_for_function("document.querySelector('.sw-optimize-now').innerText.includes('energy_wh at its worst case, the smallest first')")
    _optimize(pg, "roll_error_deg", "min")
    pg.wait_for_function("document.querySelector('.sw-optimize-now').innerText.includes('weighted score')")

    def best():
        _step(pg, "results")
        pg.wait_for_selector(".sw-sets-table tbody tr")
        pg.wait_for_function("!document.querySelector('.sw-step-btn.on').innerText.includes('…')")
        pg.wait_for_timeout(600)
        heads = pg.locator(".sw-sets-table thead th").all_inner_texts()
        cells = pg.locator(".sw-sets-table tbody tr").first.locator("td").all_inner_texts()
        return tuple(cells[heads.index(h)] for h in heads if h.strip() in ("kp_roll", "ki_roll", "filter_hz"))
    w = lambda i, v: (pg.locator(".sw-goal-table input[aria-label^='Weight of']").nth(i).fill(v),
                      pg.locator(".sw-goal-table input[aria-label^='Weight of']").nth(i).press("Tab"))
    _step(pg, "goals"); w(0, "10"); w(1, "0")
    by_energy = best()
    _step(pg, "goals"); w(0, "0"); w(1, "10")
    by_error = best()
    assert by_energy != by_error


def test_robust_to_a_parameter_and_next_runs_on_chosen_ones(pg):
    """S06: robust to kp_roll (± a grid step) - only the sets that hold robustly are ranked; next
    runs explore ki_roll only, 'Is it robust?' among the kinds; the suggestions stay with the study."""
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "goals")
    _more(pg)
    sec = pg.locator(".sw-goal-part", has_text="Robust to")
    box = sec.locator("input[aria-label^='Add a parameter']")
    box.click(); box.fill("kp"); box.press("Enter")
    row = sec.locator(".sw-robust-row", has_text="kp_roll")
    assert row.locator("select").first.input_value() == "steps"          # the mode (then the distribution, MF08)
    pg.wait_for_function("document.querySelector('.sw-optimize-now').innerText.includes('hold robustly')")
    _step(pg, "results")
    pg.wait_for_selector(".sw-sets-table th:has-text('holds robustly')")
    # next runs: only ki_roll moves
    _tab(pg, "next")
    pg.locator(".sw-next-side .sw-colpick-btn").click()
    pg.locator(".sw-colpick-pop .msp-item", has_text="kp_roll").locator("input").uncheck()
    pg.locator(".sw-colpick-pop .msp-item", has_text="filter_hz").locator("input").uncheck()
    pg.keyboard.press("Escape")
    assert "1 of 3 parameters" in pg.locator(".sw-next-side .sw-colpick-btn").inner_text()
    pg.locator(".sw-kind", has_text="Is it robust?").locator("input").check()
    pg.locator(".sw-next-side .btn", has_text="Suggest").click()
    pg.wait_for_selector(".sw-next .sw-table tbody tr")
    assert "exploring ki_roll" in pg.locator(".sw-next-main").inner_text()
    heads = pg.locator(".sw-next .sw-table thead th").all_inner_texts()
    moved = pg.locator(".sw-next .sw-table td.sw-moved")
    for k in range(moved.count()):                                   # each moved value is in the ki_roll column
        idx = moved.nth(k).evaluate("td => td.cellIndex")
        assert heads[idx] == "ki_roll"
    n = pg.locator(".sw-next .sw-table tbody tr").count()
    # kept with the study: after a restart they are still there
    pg.wait_for_timeout(1500)
    pg.reload(); pg.wait_for_selector(".app"); _to_sweeps(pg)
    pg.wait_for_selector(".sw-steps")
    _tab(pg, "next")
    pg.wait_for_function(f"document.querySelectorAll('.sw-next .sw-table tbody tr').length === {n}")
    # a change to the question: they are out of date
    _step(pg, "goals")
    _more(pg)
    pg.locator(".sw-robust-row button[aria-label='Remove']").click()
    _step(pg, "results")
    _tab(pg, "next")
    pg.wait_for_selector(".sw-banner:has-text('The question changed')")


def test_templates_dialog_save_replace_export_import_apply(pg):
    """S07: the templates dialog - save (asks before replacing), export to a file, import it back
    under a new name, apply it to another study."""
    _fresh(pg)
    _the_goal(pg)
    _bar_menu(pg, "Study", "Templates…")
    pg.fill(".sw-tpl-save input", "drone tpl")
    pg.locator(".sw-tpl-save .btn", has_text="Save this study").click()
    pg.wait_for_selector(".sw-tpl-item:has-text('drone tpl')")
    pg.locator(".sw-tpl-save .btn", has_text="Save this study").click()            # the same name: asks
    pg.wait_for_selector(".dialog.small:has-text('Replace the template?')")
    pg.locator(".dialog.small .btn.primary").click()
    assert pg.locator(".sw-tpl-item", has_text="drone tpl").count() == 1
    assert "this table has 13 of its 13 columns" in pg.locator(".sw-tpl-item", has_text="drone tpl").inner_text()
    pg.locator(".sw-tpl-item", has_text="drone tpl").click()
    pg.locator(".sw-tpl .dialog-foot .btn", has_text="Export to a file").click()
    save_as(pg, "drone_tpl.json")
    pg.wait_for_selector(".toast:has-text('drone_tpl.json')")
    pg.locator(".sw-tpl-save .btn", has_text="Import a file").click()
    goto_folder(pg, pg.env["out"])
    pg.locator(".scrim-top .dialog .fs-row", has_text="drone_tpl.json").click(); pg.click(".scrim-top .dialog-foot .btn.primary")
    pg.wait_for_selector(".sw-tpl-item:has-text('drone tpl (2)')")
    # applied to the study after starting over: the goal comes back
    pg.keyboard.press("Escape")
    _bar_menu(pg, "Study", "Start the study over")
    _step(pg, "goals")
    pg.wait_for_function("document.querySelectorAll('.sw-goal-table tr.sw-goal-on').length === 0")
    _bar_menu(pg, "Study", "Templates…")
    pg.locator(".sw-tpl-item", has_text="drone tpl (2)").dblclick()
    pg.wait_for_selector(".toast:has-text('Template applied:'):has-text('columns matched')")
    _step(pg, "goals")
    pg.wait_for_function("document.querySelectorAll('.sw-goal-table tr.sw-goal-on').length >= 2")
    for n in ("drone tpl", "drone tpl (2)"):
        _bar_menu(pg, "Study", "Templates…")
        pg.locator(".sw-tpl-item b").get_by_text(n, exact=True).click()
        pg.locator(".sw-tpl .dialog-foot .btn", has_text="Delete").click()
        pg.locator(".dialog.small .btn.primary").click()
        pg.wait_for_selector(f".toast:has-text('Template deleted: {n}')")
        pg.keyboard.press("Escape")


def test_the_whole_process_in_the_report(pg):
    """S08: the journal (what was done, in order), the iterations (each table merged in) and where
    it comes from (the table's SHA-256, the app's version) - on screen and in the report; the
    journal stays with the study."""
    import hashlib
    ex = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "examples", "sweeps"))
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".sw-table th:has-text('worst')")
    # a second iteration: the finer sweep merged in
    _step(pg, "raw")
    pg.locator(".sw-tables .btn", has_text="Add table").click()
    goto_folder(pg, ex)
    pg.locator(".dialog .fs-row", has_text="drone_tuning_refine.csv").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function("document.querySelectorAll('.sw-table-item').length === 2")
    for box in pg.locator(".sw-table-item input[type=checkbox]").all():
        box.check()
    pg.locator(".sw-merge .btn", has_text="Create merged table").click()
    pg.wait_for_function("document.querySelectorAll('.sw-table-item').length === 3")
    pg.locator(".sw-continue select").select_option("2")
    _step(pg, "report")
    j = pg.locator(".sw-journal").first
    pg.wait_for_function("document.querySelectorAll('.sw-iterations li').length === 2")      # two iterations
    text = j.inner_text()
    assert "Opened" not in text and "Merged" in text and "drone_tuning_refine.csv" in text      # S20: opening is not a step
    assert "Goal 1: roll_error_deg <= 5 & overshoot_pct <= 15 · ↓energy_wh" in text
    pg.locator(".sw-report-format", has_text="Interactive HTML").click()
    pg.locator(".sw-report-page .btn", has_text="Make the report").click()
    save_as(pg, "process.html")
    pg.wait_for_selector(".toast:has-text('process.html')", timeout=60000)
    html = open(os.path.join(pg.env["out"], "process.html"), encoding="utf-8").read()
    sha = hashlib.sha256(open(os.path.join(ex, "drone_tuning_refine.csv"), "rb").read()).hexdigest()
    for want in ("The journal: what was done, in order", "Iterations: each table merged in", "Where it comes from", sha, "Signal Viewer "):
        assert want in html, want
    # the report itself is in the journal now, and the journal survives a restart
    pg.wait_for_function("document.querySelector('.sw-journal').innerText.includes('Report made')")
    pg.wait_for_timeout(1500)
    pg.reload(); pg.wait_for_selector(".app"); _to_sweeps(pg)
    pg.wait_for_selector(".sw-steps")
    _step(pg, "report")
    pg.wait_for_function("document.querySelector('.sw-journal').innerText.includes('Report made')")


def test_a_narrow_window_nothing_overlaps(pg):
    """S09: at 1024 px the app is no wider than the window, the step's two buttons do not overlap
    (with the side panel narrow), the plot's bar wraps rather than scrolls."""
    pg.set_viewport_size({"width": 1024, "height": 700})
    _fresh(pg)
    _the_goal(pg)
    for step in ("roles", "goals", "results"):
        _step(pg, step)
        assert pg.evaluate("document.querySelector('.app').scrollWidth") <= 1024
        boxes = [x.bounding_box() for x in pg.locator(".sw-step-foot .btn").all()]
        if len(boxes) < 2:
            continue                                                        # the last step: Back only
        a, b = boxes[:2]
        assert a["x"] + a["width"] <= b["x"] + 1 or a["y"] + a["height"] <= b["y"] + 1      # side by side, or one under the other
    bar = pg.locator(".sw-plotbar")
    assert bar.evaluate("e => e.scrollWidth <= e.clientWidth + 1")
    pg.set_viewport_size({"width": 1440, "height": 900})


def test_the_optimization_in_the_plots(pg):
    """S19: the lines get the rank and the score when two objectives rank the sets."""
    _fresh(pg)
    _step(pg, "goals")
    _condition(pg, "roll_error_deg", "<=", 5)
    _optimize(pg, "energy_wh", "min")
    _optimize(pg, "settle_time_s", "min")
    _step(pg, "results")
    pg.wait_for_selector(".sw-sets-table tbody tr")
    pg.wait_for_function("[...document.querySelectorAll('.pp-axis-name')].some(e => e.innerText.startsWith('score'))")
    names = pg.locator(".pp-axis-name").all_inner_texts()
    assert any(n.startswith("rank") for n in names), names
    assert any(n.startswith("score") for n in names), names


def test_the_sets_that_hold_as_an_interactive_plot(pg):
    """S14: the table's Export writes the sets shown (only those that hold) as an interactive plot."""
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".sw-table th:has-text('worst')")
    holding = _holding(pg)
    pg.wait_for_function(f"document.querySelectorAll('.sw-sets-table tbody tr').length === {holding}")   # Show: Holds
    pg.locator(".sw-sets-bar .btn", has_text="Export").click()
    pg.locator(".menu.ctx button", has_text="interactive plot").click()
    save_as(pg, "holding_plot.html")
    pg.wait_for_selector(".toast:has-text('holding_plot.html')")
    html = open(os.path.join(pg.env["out"], "holding_plot.html"), encoding="utf-8").read()
    assert f'"n": {holding}' in html and "<canvas" in html


def test_an_axis_taken_off_comes_back(pg):
    """S15: an axis hidden from its menu, or taken off in the column picker, is offered back under
    the bar - one click brings it back."""
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".pp-axis-name")
    assert "(add / remove)" in pg.locator(".sw-plotbar .sw-colpick-btn").inner_text()
    pg.locator(".pp-axis-name", has_text="ki_roll").click()
    pg.locator("button", has_text="Hide this axis").click()
    pg.wait_for_selector(".sw-axes-off .sw-tag:has-text('ki_roll')")
    assert pg.locator(".pp-axis-name", has_text="ki_roll").count() == 0
    pg.locator(".sw-plotbar .sw-colpick-btn").click()
    pg.locator(".sw-colpick-pop .msp-item", has_text="filter_hz").locator("input").uncheck()
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".sw-axes-off .sw-tag:has-text('filter_hz')")
    pg.locator(".sw-axes-off .sw-tag", has_text="ki_roll").click()
    pg.wait_for_selector(".pp-axis-name:has-text('ki_roll')")
    assert pg.locator(".sw-axes-off .sw-tag", has_text="ki_roll").count() == 0
    pg.locator(".sw-axes-off .iconbtn").click()
    assert pg.locator(".sw-axes-off").count() == 0


def test_next_runs_numbers_add_up(pg):
    """S16: each kind says what it found and took, and the takes add up to what is suggested; the
    runs are the sets times the combinations; fewer than asked says why; a small budget: one each."""
    import re
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".sw-table th:has-text('worst')")
    _tab(pg, "next")
    side = pg.locator(".sw-next-side")
    side.locator("input[type='number']").fill("80")
    assert "up to 80 sets × 18 combinations each = up to 1,440 runs" in side.inner_text()
    side.locator(".btn", has_text="Suggest").click()
    pg.wait_for_selector(".sw-next .sw-table tbody tr")
    taken = sum(int(n) for n in re.findall(r"taken (\d+)", side.inner_text()))
    n = pg.locator(".sw-next .sw-table tbody tr").count()
    assert taken == n
    main = pg.locator(".sw-next-main").inner_text()
    assert f"{n} sets × 18 combinations = {n * 18:,} runs" in main
    if n < 80:
        assert f"the kinds ticked found only {n}" in main
    side.locator("input[type='number']").fill("2")
    side.locator(".btn", has_text="Suggest").click()
    pg.wait_for_function("document.querySelectorAll('.sw-next .sw-table tbody tr').length === 2")
    assert sorted(int(x) for x in re.findall(r"taken (\d+)", side.inner_text()) if x != "0") == [1, 1]


def test_next_runs_compact_and_formats(pg):
    """S17: a parameter the same in every suggestion is said once and left out of the table (back
    with 'show every column'); the sets alone as JSON, the run list as MATLAB."""
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "results")
    pg.wait_for_selector(".sw-table th:has-text('worst')")
    _tab(pg, "next")
    side = pg.locator(".sw-next-side")
    side.locator(".sw-colpick-btn").click()                                     # explore ki_roll only
    for p in ("kp_roll", "filter_hz"):
        pg.locator(".sw-colpick-pop .msp-item", has_text=p).locator("input").uncheck()
    pg.keyboard.press("Escape")
    for k in ("Sharpen the edge", "Where scenarios disagree", "Finish what's missing"):
        side.locator(".sw-kind", has_text=k).locator("input").uncheck()
    side.locator("input[type='number']").fill("1")                              # one set: everything is the same
    side.locator(".btn", has_text="Suggest").click()
    pg.wait_for_selector(".sw-next .sw-table tbody tr")
    heads = lambda: [h for h in pg.locator(".sw-next .sw-table thead th").all_inner_texts() if h != "Why"]
    side.locator("input[type='number']").fill("5")
    side.locator(".btn", has_text="Suggest").click()
    pg.wait_for_function("document.querySelectorAll('.sw-next .sw-table tbody tr').length >= 2")
    if pg.locator(".sw-next-same").count():
        n_same = pg.locator(".sw-next-same b").inner_text().count(" = ")
        assert len(heads()) == 3 - n_same
        pg.locator(".sw-next-same .linklike").click()
        assert len(heads()) == 3
    n = pg.locator(".sw-next .sw-table tbody tr").count()
    # the sets alone, as JSON
    pg.locator(".sw-next-main .btn", has_text="Export the next runs").click()
    pg.locator(".menu.ctx button", has_text="sets alone").hover()
    pg.locator(".menu.ctx button", has_text="JSON").click()
    save_as(pg, "next_sets.json")
    pg.wait_for_selector(".toast:has-text('next_sets.json')")
    import json as _json
    sets = _json.load(open(os.path.join(pg.env["out"], "next_sets.json")))
    assert len(sets) == n and set(sets[0]) == {"kp_roll", "ki_roll", "filter_hz"}
    # the run list, as MATLAB
    pg.locator(".sw-next-main .btn", has_text="Export the next runs").click()
    pg.locator(".menu.ctx button", has_text="The run list").hover()
    pg.locator(".menu.ctx button", has_text="MATLAB").click()
    save_as(pg, "next_runs.m")
    pg.wait_for_selector(".toast:has-text('next_runs.m')")
    assert open(os.path.join(pg.env["out"], "next_runs.m")).read().startswith(f"% {n * 18} runs")


def test_the_journal_tells_the_final_story(pg):
    """S20: the report's journal is the final story by default - each goal's last version, a
    tolerance added and taken away is no step, files opened are not lines; a line can be hidden,
    and 'the analysis starts here' leaves out what came before; the report follows."""
    _fresh(pg)
    _the_goal(pg)
    _step(pg, "goals")
    _more(pg)
    sec = pg.locator(".sw-goal-part", has_text="Robust to")                      # a trial: on, then off
    box = sec.locator("input[aria-label^='Add a parameter']")
    box.click(); box.fill("kp"); box.press("Enter")
    pg.locator(".sw-robust-row button[aria-label='Remove']").click()
    _condition(pg, "settle_time_s", "<=", 3)                                     # the goal again, after it
    _step(pg, "report")
    lines = lambda: pg.locator(".sw-journal-lines li").all_inner_texts()
    final = lines()
    assert not any("Robust to" in x for x in final) and not any("Opened" in x for x in final)
    assert sum("Goal 1:" in x for x in final) == 1 and "settle_time_s <= 3" in next(x for x in final if "Goal 1:" in x)
    pg.locator(".sw-seg button", has_text="Everything").click()
    everything = lines()
    assert len(everything) > len(final) and any("Robust to" in x for x in everything)
    # the analysis starts at the trial with the tolerance: the goal's first version is out
    pg.locator(".sw-journal-lines li", has_text="Robust to").locator("button[aria-label^='The analysis starts here']").click()
    pg.locator(".sw-seg button", has_text="The final story").click()
    pg.wait_for_function("document.querySelector('.sw-journal h3').innerText.includes('(1 lines in the report)')")
    assert "settle_time_s <= 3" in lines()[0]
    # and that line hidden by hand: nothing is left - its older version does not come back
    pg.locator(".sw-journal-lines li", has_text="Goal 1:").locator("button[aria-label='Leave this line out of the report']").click()
    pg.wait_for_function("document.querySelector('.sw-journal h3').innerText.includes('(0 lines in the report)')")
    pg.locator(".sw-seg button", has_text="Everything").click()
    pg.locator(".sw-journal-lines li.hidden").locator("button[aria-label='Put this line back in the report']").click()
    pg.locator(".sw-seg button", has_text="The final story").click()
    pg.wait_for_function("document.querySelector('.sw-journal h3').innerText.includes('(1 lines in the report)')")
    # the report tells the same
    pg.locator(".sw-report-format", has_text="Interactive HTML").click()
    pg.locator(".sw-report-page .btn", has_text="Make the report").click()
    save_as(pg, "story.html")
    pg.wait_for_selector(".toast:has-text('story.html')", timeout=60000)
    html = open(os.path.join(pg.env["out"], "story.html"), encoding="utf-8").read()
    story = html.split("The journal: what was done, in order")[1]
    assert "settle_time_s &lt;= 3" in story or "settle_time_s <= 3" in story
    assert "Robust to" not in story and "Opened" not in story


def test_the_best_set_while_editing_a_goal(pg):
    """S22: the Goals step shows how many hold and the best set while it is edited - a weight moved
    there changes it, without going to the results; Open it goes to the results with the set open."""
    _fresh(pg)
    _step(pg, "goals")
    _condition(pg, "roll_error_deg", "<=", 5)
    _optimize(pg, "energy_wh", "min")
    pg.wait_for_selector(".sw-side-step .sw-best:has-text('kp_roll = ')")
    assert "parameter sets hold" in pg.locator(".sw-goal-count").inner_text()
    _optimize(pg, "roll_error_deg", "min")
    w = lambda i, v: (pg.locator(".sw-goal-table input[aria-label^='Weight of']").nth(i).fill(v),
                      pg.locator(".sw-goal-table input[aria-label^='Weight of']").nth(i).press("Tab"))
    w(0, "10"); w(1, "0")
    pg.wait_for_timeout(800)
    a = pg.locator(".sw-side-step .sw-best-params").inner_text()
    w(0, "0"); w(1, "10")
    pg.wait_for_function(f"document.querySelector('.sw-side-step .sw-best-params').innerText !== {a!r}")
    pg.locator(".sw-side-step .sw-best .btn", has_text="Open it").click()
    pg.wait_for_selector(".sw-detail")
    assert pg.locator(".sw-step-btn.on .sw-step-n").inner_text() == "4"


def test_four_steps_five_tabs_and_the_goal_as_one_table(pg):
    """2026-11-01 redesign: data, columns, goal, results; the goal is one table - a limit on a column is
    a filter on it (an output in every scenario, a parameter too), emptied it is gone; what to optimize
    beside it; the results: parameter sets, all runs, charts, next runs, report; undo beside Keep."""
    _fresh(pg)
    assert pg.locator(".sw-step-btn").all_inner_texts()[0].startswith("1\nData")
    assert pg.locator(".sw-step-btn").count() == 4 and pg.locator(".sw-area-btn").count() == 0
    _step(pg, "goals")
    assert _holding(pg) == 45
    _condition(pg, "kp_roll", "<=", 0.2)                          # a parameter: 3 of its 5 values
    pg.wait_for_function("document.querySelector('.sw-answer-n').innerText.startsWith('27 ')")
    _condition(pg, "roll_error_deg", "<=", 4)
    row = pg.locator(".sw-goal-table tr[data-col='roll_error_deg']")
    pg.wait_for_selector(".sw-goal-table tr[data-col='roll_error_deg'] .sw-limit-met")
    assert "sets meet it" in row.inner_text()
    n = _holding(pg)
    assert 0 < n < 27
    box = pg.locator("input[aria-label='kp_roll at most']")
    box.fill(""); box.press("Enter")                              # emptied: no limit
    pg.wait_for_function(f"+document.querySelector('.sw-answer-n').innerText.split(' ')[0] > {n}")
    _optimize(pg, "energy_wh", "min")
    pg.wait_for_selector(".sw-best:has-text('kp_roll = ')")
    _step(pg, "results")
    tabs = pg.locator(".sw-center-tabs button").all_inner_texts()
    assert tabs == ["Parameter sets", "All runs", "Charts", "Next runs", "Report"]
    assert pg.locator(".sw-plotbar .sw-undo").is_enabled()
    pg.locator(".sw-plotbar .sw-undo").click()                   # the last change undone (the optimize choice with it)
    pg.wait_for_function("!document.querySelector('.sw-best')")
    pg.locator(".sw-plotbar .sw-redo").click()
    pg.wait_for_selector(".sw-best:has-text('kp_roll = ')")
    _tab(pg, "runs")
    pg.wait_for_selector(".sw-what-line:has-text('A line per run')")
