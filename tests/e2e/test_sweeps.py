"""Sweeps area, step 0: the area switch, opening a results table, the guessed roles and the shape
of the study, and correcting a role."""
import pytest

pytest.importorskip("playwright.sync_api")
import os  # noqa: E402

from test_features import env, goto_folder, pg, save_as  # noqa: E402,F401


def _to_sweeps(pg):
    pg.locator(".areas .area-btn", has_text="Sweeps").click()
    pg.wait_for_selector(".sw-welcome, .sw-study")


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


def _center(pg, name):
    pg.locator(".sw-center-tabs button", has_text=name).click()


def test_effects_map_and_next_runs(pg):
    _example(pg)
    pg.select_option("select[aria-label='Goal']", "range_m")
    _center(pg, "Which parameter matters")
    pg.wait_for_selector(".sw-effect")
    assert pg.locator(".sw-effect b").first.inner_text() == "payload_kg"          # it matters most here
    _center(pg, "Map")
    pg.wait_for_selector(".sw-map svg rect")
    _center(pg, "Next runs")
    pg.locator(".sw-next .btn", has_text="Suggest").click()
    pg.wait_for_selector(".sw-next .sw-table tbody tr")
    assert pg.locator(".sw-next .sw-table tbody tr").count() == 40
    pg.locator(".sw-next .btn", has_text="Export the run list").click()
    save_as(pg, "next.csv")
    pg.wait_for_selector(".sw-next .hint:has-text('runs written')")
    lines = open(os.path.join(pg.env["out"], "next.csv")).read().splitlines()
    assert lines[0].startswith("payload_kg,kp_roll,cruise_mps,controller,scenario_terrain") and len(lines) == 1 + 40 * 18
    _center(pg, "Lines")


def test_data_health_leaves_a_suspicious_run_out(pg):
    _example(pg)
    _center(pg, "Data health")
    pg.wait_for_selector(".sw-health .sw-table tbody tr")
    assert pg.locator(".sw-health .sw-table tbody tr").count() == 4                 # the example's four odd runs
    before = _holding(pg)
    pg.locator(".sw-health .btn", has_text="Leave all of them out").click()
    pg.wait_for_selector(".sw-answer .hint:has-text('4 runs left out')")
    pg.locator(".sw-answer .linklike", has_text="Keep every run").click()
    pg.wait_for_function(f"+document.querySelector('.sw-answer-n').innerText.split(' ')[0] === {before}")
    _center(pg, "Lines")


def test_save_and_reopen_a_study_and_report(pg):
    _example(pg)
    pg.select_option("select[aria-label='Goal']", "flight_time_s")
    pg.locator(".areabar [aria-label='Save the study']").click()
    save_as(pg, "mine.svsweep")
    pg.wait_for_selector(".sw-note:has-text('Saved')")
    pg.locator(".areabar [aria-label='Report (HTML)']").click()
    save_as(pg, "mine.html")
    pg.wait_for_function("document.querySelector('.sw-note').innerText.includes('mine.html')")
    html = open(os.path.join(pg.env["out"], "mine.html"), encoding="utf-8").read()
    assert "flight_time_s" in html and "<img" in html
    n = pg.locator(".areabar .tab").count()
    pg.locator(".areabar [aria-label='Open a saved study']").click()
    goto_folder(pg, pg.env["out"])
    pg.locator(".dialog .fs-row", has_text="mine.svsweep").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function(f"document.querySelectorAll('.areabar .tab').length === {n + 1}")
    assert pg.locator("select[aria-label='Goal']").input_value() == "flight_time_s"


def test_a_sets_recordings_open_in_recordings(pg, tmp_path):
    ex = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "examples"))
    rows = ["recording,gain,scenario,score"]
    for i, f in enumerate(("run_012.csv", "run_013.csv", "run_014.csv")):
        for g in (1, 2):
            rows.append(f"{os.path.join(ex, f)},{g},{'abc'[i]},{g * 10 + i + 0.37 * g * i}")
    t = tmp_path / "with_recordings.csv"
    t.write_text("\n".join(rows) + "\n")
    _to_sweeps(pg)
    pg.locator(".areabar .btn", has_text="Open a table").click()
    goto_folder(pg, str(tmp_path))
    pg.locator(".dialog .fs-row", has_text="with_recordings.csv").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".sw-table tbody tr")
    pg.locator(".sw-tabs button", has_text="Columns").click()
    assert "recording" in pg.locator(".sw-role-recording .sw-col-name").inner_text()
    if pg.locator(".sw-col", has_text="scenario").locator("select").first.input_value() != "hold":
        pg.select_option("select[aria-label='Role of scenario']", "hold")
    pg.locator(".sw-tabs button", has_text="Question").click()
    pg.locator(".sw-table tbody tr").first.click()
    pg.locator(".sw-detail .btn", has_text="recordings in Recordings").click()
    pg.wait_for_selector(".rail")
    pg.wait_for_function("document.querySelectorAll('.run-head').length >= 3")



def _open_table(pg, folder, name):
    _to_sweeps(pg)
    pg.locator(".areabar .btn", has_text="Open a table").click()
    goto_folder(pg, str(folder))
    pg.locator(".dialog .fs-row", has_text=name).click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".sw-study")


def test_a_table_with_no_parameter_still_opens(pg, tmp_path):
    (tmp_path / "flat.csv").write_text("a,b\n1.5,2.25\n3.75,4.125\n5.5,6.875\n7.25,8.5\n")
    _open_table(pg, tmp_path, "flat.csv")
    pg.wait_for_selector(".sw-banner:has-text('No column is a parameter')")
    assert pg.locator(".sw-tabs button.on").inner_text().startswith("Columns")       # the columns come first
    pg.select_option("select[aria-label='Role of a']", "param")
    pg.wait_for_selector(".sw-table tbody tr")


def test_follow_the_file_and_templates(pg, tmp_path):
    f = tmp_path / "grow.csv"
    rows = ["scenario,p,out"] + [f"{sc},{p},{p * 10 + i * 0.37}" for i, (sc, p) in enumerate((s, p) for s in "ab" for p in (1, 2, 3))]
    f.write_text("\n".join(rows) + "\n")
    _open_table(pg, tmp_path, "grow.csv")
    pg.select_option("select[aria-label='Goal']", "out")
    # the file grows: the study says so and reads it again, question kept
    f.write_text("\n".join(rows + [f"{sc},4,{40 + i * 0.37}" for i, sc in enumerate("ab")]) + "\n")
    pg.wait_for_selector(".sw-banner:has-text('changed')", timeout=15000)
    pg.locator(".sw-banner .btn", has_text="Read the table again").click()
    pg.wait_for_function("document.querySelectorAll('.sw-table tbody tr').length === 4")
    assert pg.locator("select[aria-label='Goal']").input_value() == "out"
    # a template: saved here, offered and applied on the next table with these columns
    pg.select_option(".sw-templates", "#save")
    pg.fill(".dialog input", "grow check"); pg.keyboard.press("Enter")
    pg.wait_for_function("[...document.querySelectorAll('.sw-templates option')].some(o => o.textContent === 'grow check')")
    (tmp_path / "grow2.csv").write_text(f.read_text())
    _open_table(pg, tmp_path, "grow2.csv")
    pg.wait_for_selector(".sw-banner:has-text('grow check')")
    pg.locator(".sw-banner .btn", has_text="Apply").click()
    pg.wait_for_function("document.querySelector(\"select[aria-label='Goal']\").value === 'out'")



def _rows(pg):
    return pg.locator(".sw-table-wrap .sw-table tbody tr").count()


def test_two_sweeps_merged(pg):
    _to_sweeps(pg)
    if pg.locator(".sw-welcome").count() == 0:
        pg.locator(".areabar .tab .x").first.click()                 # back to the welcome
        pg.wait_for_selector(".sw-welcome")
    pg.locator(".sw-welcome .btn", has_text="two sweeps, merged").click()
    pg.wait_for_selector(".sw-welcome, .sw-study")
    pg.locator(".sw-tabs button", has_text="Columns").click()
    pg.wait_for_function("document.querySelectorAll('.sw-hide-box .sw-tag').length === 2")
    pg.wait_for_function("+[...document.querySelectorAll('.sw-shape .sw-stat')].find(e => e.innerText.includes('Parameter sets')).querySelector('.sw-stat-value').innerText.replace(',', '') > 150")
    pg.locator(".sw-tabs button", has_text="Question").click()


def test_keep_exclude_restore_and_export_shown(pg):
    _example(pg)
    pg.wait_for_selector(".sw-table tbody tr")
    total = _rows(pg)
    b = pg.locator(".pp canvas").bounding_box()
    x = b["x"] + 56
    pg.mouse.move(x, b["y"] + 50); pg.mouse.down(); pg.mouse.move(x, b["y"] + 150, steps=5); pg.mouse.up()
    pg.wait_for_selector(".sw-plotbar .btn:has-text('Clear 1 filters')")
    kept = _rows(pg)
    assert 0 < kept < total
    pg.locator(".sw-scope .btn", has_text="Keep").click()
    pg.wait_for_selector(".sw-scope .btn:has-text('Restore all (1)')")
    assert pg.locator(".sw-plotbar .btn:has-text('Clear')").count() == 0          # the filter became the scope
    assert _rows(pg) == kept
    pg.locator(".sw-scope .btn", has_text="Export shown").click()
    save_as(pg, "shown.csv")
    pg.wait_for_selector(".sw-center .hint:has-text('runs written')")
    lines = open(os.path.join(pg.env["out"], "shown.csv")).read().splitlines()
    assert len(lines) - 1 >= kept and lines[0].startswith("scenario_terrain,")
    pg.locator(".sw-scope .btn", has_text="Restore all").click()
    pg.wait_for_function(f"document.querySelectorAll('.sw-table-wrap .sw-table tbody tr').length === {total}")
    # exclude: the other way round
    pg.wait_for_timeout(300)
    b = pg.locator(".pp canvas").bounding_box()                     # the bar above may have changed height
    pg.mouse.move(x, b["y"] + 50); pg.mouse.down(); pg.mouse.move(x, b["y"] + 150, steps=5); pg.mouse.up()
    pg.wait_for_selector(".sw-plotbar .btn:has-text('Clear 1 filters')")
    kept = _rows(pg)
    pg.locator(".sw-scope .btn", has_text="Exclude").click()
    pg.wait_for_function(f"document.querySelectorAll('.sw-table-wrap .sw-table tbody tr').length === {total - kept}")
    pg.locator(".sw-scope .btn", has_text="Step back").click()
    pg.wait_for_function(f"document.querySelectorAll('.sw-table-wrap .sw-table tbody tr').length === {total}")
