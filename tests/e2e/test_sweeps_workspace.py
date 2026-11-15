"""Sweeps as one study (plan §4.7): the walkthroughs - results first, runs first, the demo on one screen.
Each waits on state (`window.__svSweeps`, `window.__svStudy`, data-* attributes), never on a sleep."""
import json
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg  # noqa: E402,F401

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXAMPLES = os.path.join(ROOT, "examples", "sweeps")


def _idle(pg):
    pg.wait_for_function("window.__svSweeps && window.__svSweeps.idle()")


def _study(pg, expr):
    """A value of the study file being edited (Set up)."""
    return pg.evaluate(f"(() => {{ const s = window.__svStudy.state().study; return {expr}; }})()")


def _to_sweeps(pg):
    pg.locator(".areas .area-btn", has_text="Sweeps").click()
    pg.wait_for_selector(".sw-welcome, .sw-study-wrap, .su, .ns")
    while pg.locator(".areabar .tab").count():                     # every table closed: the welcome page
        n = pg.locator(".areabar .tab").count()
        pg.locator(".areabar .tab .x").first.click()
        pg.wait_for_function(f"document.querySelectorAll('.areabar .tab').length === {n - 1}")


def _new_study(pg):
    _to_sweeps(pg)
    pg.evaluate("window.__svSweeps.show('')")
    pg.wait_for_selector(".sw-welcome .sw-new-study")
    pg.locator(".sw-welcome .sw-new-study").click()
    pg.wait_for_selector("[data-part=new]")


def _field(pg, sel, value):
    loc = pg.locator(sel).first
    loc.fill(value)
    loc.press("Enter")


def test_results_first_opens_the_results_and_fills_set_up(pg):
    """1-2: New study -> I have results -> the table -> its results at once; Set up holds the parameters with their
    ranges and the three scenario columns, filled from the table."""
    _new_study(pg)
    pg.locator(".ns-have").click()
    goto_folder(pg, EXAMPLES)
    pg.locator(".dialog .dialog-body .fs-row", has_text="drone_tuning.csv").first.click()
    pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".sw-study-wrap")
    _idle(pg)
    pg.wait_for_function("window.__svStudy.state().study && window.__svStudy.state().guess")
    assert _study(pg, "s.tables[0].paths[0]").endswith("drone_tuning.csv")
    assert _study(pg, "Object.keys(s.search.params)") == ["kp_roll", "ki_roll", "filter_hz"]
    pg.locator(".sw-nav [data-nav=setup]").click()                              # C7: the navigator
    pg.wait_for_selector("[data-part=setup]")
    assert pg.locator(".sw-nav-done").inner_text().endswith("/4")
    assert pg.locator(".su-params tbody tr[data-param]").count() == 3
    assert [pg.locator(".su-scen tr[data-scenario]").nth(i).get_attribute("data-scenario") for i in range(3)] == \
        ["scenario_wind_mps", "scenario_payload_kg", "scenario_gusts"]
    lo, hi = (float(pg.locator(".su-params tr[data-param=kp_roll] input").nth(i).input_value()) for i in (1, 2))
    assert 0 < lo < hi                                                          # the range seen in the table
    assert _study(pg, "s.launcher.submit.length") == 0                          # no command: still the table's own file
    pg.locator(".su-to-results").click()
    pg.wait_for_selector(".sw-study-wrap")
    pg.locator(".sw-nav [data-nav=setup]").click()                              # and back with the table's own item
    pg.wait_for_selector("[data-part=setup]")
    pg.locator(".sw-nav [data-nav=table]", has_text="drone_tuning.csv").click()
    pg.wait_for_selector(".sw-study-wrap .sw-steps")


def test_start_from_nothing_types_the_set_up(pg):
    """4: New study -> Start from nothing: two parameters with ranges, one scenario column, an output to minimise,
    the command - each written into the study file; Undo takes the last one back."""
    _new_study(pg)
    pg.locator(".ns-nothing").click()
    pg.wait_for_selector("[data-part=setup]")
    assert set(pg.get_attribute("[data-part=setup]", "data-missing").split()) == {"params", "output", "goal", "command"}
    assert set(pg.get_attribute(".sw-run .rc-next", "data-missing").split()) == {"params", "output", "goal", "command"}   # C8
    assert "cannot run yet" in pg.locator(".sw-run .rc-next").inner_text()
    for name, lo, hi, step in (("a", "0", "2", "0.1"), ("b", "1", "3", "0.5")):
        pg.locator(".su-add-param").click()
        _field(pg, ".su-new-param", name)
        pg.wait_for_selector(f"tr[data-param={name}]")
        row = f"tr[data-param={name}] input"
        for i, v in ((1, lo), (2, hi), (3, step)):
            _field(pg, f"{row} >> nth={i}", v)
            pg.wait_for_function(f"window.__svStudy.state().study.search.params[{json.dumps(name)}] && "
                                 f"String(window.__svStudy.state().study.search.params[{json.dumps(name)}][{json.dumps(['', 'min', 'max', 'step'][i])}]) === {json.dumps(v)}")
    pg.locator(".su-add-scenario").click()
    _field(pg, ".su-new-scenario", "wind")
    pg.wait_for_selector("tr[data-scenario=wind]")
    _field(pg, "tr[data-scenario=wind] input >> nth=1", "0, 5")
    _field(pg, ".su-outputs", "err")
    pg.locator(".su-goal").select_option("err")
    _field(pg, ".su-command", "python sim.py {{params_file}}")
    pg.wait_for_function("document.querySelector('[data-part=setup]').dataset.missing === ''")
    pg.wait_for_function("document.querySelector('.sw-run .rc-next').dataset.missing === ''")       # C8: the Run column says round 1 is ready
    assert "Round 1 is ready to run" in pg.locator(".sw-run .rc-next").inner_text()
    assert "16 sets × 2 scenarios = 32 runs" in pg.locator(".sw-run .rc-next").inner_text()
    assert _study(pg, "s.start") == {"grid": {"a": 4, "b": 4}, "scenarios": {"T1": {"wind": [0, 5]}}}
    assert _study(pg, "s.tables[0].objective") == {"expr": "err", "sense": "min"}
    assert _study(pg, "s.launcher.submit") == ["python", "sim.py", "{{params_file}}"]
    pg.keyboard.press("Control+z")                                              # the one Undo: the command goes
    pg.wait_for_function("window.__svStudy.state().study.launcher.submit.length === 0")
    assert pg.get_attribute("[data-part=setup]", "data-missing") == "command"


def test_navigator_lists_the_rounds_and_opens_one(pg):
    """C7: the demo after a round - the navigator lists each table's Round 1 (from the study file's tables); a click on
    one opens its results in the four steps, the round marked as the one shown; Set up is a click away."""
    pg.locator(".ex-card[data-example='smartSweepDemo']").click()
    pg.wait_for_selector(".dm-strip")
    if pg.locator(".dm-reset").is_enabled():                     # a demo left by an earlier run: start again
        pg.locator(".dm-reset").click()
        pg.wait_for_function("document.querySelector('.dm-strip').dataset.round === '0'")
    pg.locator(".dm-next").click()
    pg.wait_for_function("document.querySelector('.dm-chart').dataset.points === '1' && "
                         "document.querySelector('[data-shot=demo]').dataset.settled === '1'", timeout=120000)
    pg.wait_for_function("document.querySelectorAll('.sw-nav [data-nav=round][data-round=\"1\"]').length >= 2", timeout=30000)
    pg.locator(".sw-nav [data-nav=round][data-round='1']").first.click()
    pg.wait_for_selector(".sw-study-wrap .sw-steps")
    _idle(pg)
    pg.wait_for_selector(".sw-nav [data-nav=round].on")
    assert pg.locator(".sw-nav [data-nav=round].on").get_attribute("data-round") == "1"
    pg.locator(".sw-nav [data-nav=setup]").click()
    pg.wait_for_selector("[data-part=setup]")


def test_the_run_column_folds_and_remembers(pg):
    """C8: the Run column beside every part of a study file (Set up, a table); folded, it stays folded after a reload."""
    _new_study(pg)
    pg.locator(".ns-nothing").click()
    pg.wait_for_selector("[data-part=setup]")
    pg.wait_for_selector(".sw-run .rc-next")
    pg.locator(".sw-run .rc-toggle").click()
    pg.wait_for_selector(".sw-run.folded")
    assert pg.locator(".sw-run .rc-next").count() == 0
    pg.wait_for_function("""() => { const x = new XMLHttpRequest(); x.open('GET', '/api/settings', false); x.send();
        return JSON.parse(x.responseText).settings['sv3.swRunHidden'] === true; }""", polling=200)   # written to the app's settings
    pg.reload()
    pg.wait_for_selector(".app")
    pg.locator(".areas .area-btn", has_text="Sweeps").click()
    pg.wait_for_selector(".sw-welcome .sw-new-study")
    pg.locator(".sw-welcome .sw-new-study").click()
    pg.locator(".ns-nothing").click()
    pg.wait_for_selector(".sw-run.folded")                                         # remembered
    pg.locator(".sw-run .rc-toggle").click()
    pg.wait_for_selector(".sw-run .rc-next")


def test_one_open_menu_and_each_command_once(pg):
    """C10: one Open ▾ (New study, a table, a folder, a saved study of either kind) - no second submenu; the palette
    lists each Sweeps command once; a study file's Save / Undo are the area bar's (the panel has none of its own)."""
    _to_sweeps(pg)
    pg.locator(".areabar .btn", has_text="Open").first.click()
    items = [x.strip() for x in pg.locator(".menu button").all_inner_texts() if x.strip()]
    assert items == ["New study…", "Open a table", "Open a folder of tables", "Open a saved study"]
    assert pg.locator(".menu .sub, .menu [aria-haspopup]").count() == 0
    pg.keyboard.press("Escape")
    pg.evaluate("p => window.__svRequestStudy(p)", os.path.join(ROOT, "examples", "drones", "drones.svstudy.json"))
    pg.wait_for_selector("[data-shot='study'][data-settled='1']", timeout=60000)
    assert pg.locator(".cp-head button").count() == 0                           # no Undo / Redo / Save / × of its own
    assert pg.locator(".areabar [aria-label='Undo']").count() == 1
    assert "Study: " in pg.locator("footer.status").inner_text()                 # one sentence for the study
    pg.locator(".areabar .btn", has_text="Study").first.click()                 # one report: the study's
    assert pg.locator(".menu button", has_text="Report of the study…").count() == 1
    pg.keyboard.press("Escape")
    pg.keyboard.press("Control+k")
    pg.wait_for_selector(".palette-input")
    ids = pg.evaluate("[...document.querySelectorAll('[role=option][data-cmd]')].map((e) => e.dataset.cmd).filter((x) => /^(sw|cp)-/.test(x))")
    assert len(ids) == len(set(ids))                                             # each command once
    assert {"sw-new-study", "sw-open-table", "sw-open-folder", "sw-open-study", "sw-save-study", "sw-close-study"} <= set(ids)
    assert not [x for x in ids if x.startswith("cp-")]                          # no second New / Open for a study file
    pg.keyboard.press("Escape")


def test_a_study_round_reads_as_its_table_and_its_goal_undoes(pg):
    """C11 (walkthrough 6, the table's part): the demo after a round - Drone B's Round 1 opens in the four steps with
    the study table's roles (Kp / Ki / Kd parameters, mass / wind scenarios, outputs) and goal (minimise settling time);
    a limit changes its answer; Ctrl+Z takes it back; the Run column never left the screen."""
    from test_sweeps_flow import _condition, _holding, _step
    pg.locator(".ex-card[data-example='smartSweepDemo']").click()
    pg.wait_for_selector(".dm-strip")
    if pg.locator(".dm-reset").is_enabled():
        pg.locator(".dm-reset").click()
        pg.wait_for_function("document.querySelector('.dm-strip').dataset.round === '0'")
    pg.locator(".dm-next").click()
    pg.wait_for_function("document.querySelector('.dm-chart').dataset.points === '1' && "
                         "document.querySelector('[data-shot=demo]').dataset.settled === '1'", timeout=120000)
    pg.wait_for_function("document.querySelectorAll('.sw-nav [data-nav=round][data-round=\"1\"]').length === 3", timeout=30000)
    pg.locator(".sw-nav [data-nav=round][data-round='1']").nth(1).click()          # A, B, C: Drone B
    pg.wait_for_selector(".sw-study-wrap .sw-steps")
    pg.wait_for_function("window.__svSweeps.doc() && window.__svSweeps.doc().columns.some((c) => c.name === 'Kp' && c.role === 'param')")
    _idle(pg)
    roles = {c["name"]: c["role"] for c in pg.evaluate("window.__svSweeps.doc().columns")}
    assert [roles[k] for k in ("Kp", "Ki", "Kd")] == ["param"] * 3
    assert roles["mass"] == roles["wind"] == "hold" and roles["overshoot"] == "output"
    q = pg.evaluate("window.__svSweeps.doc().question")
    assert q["goals"][q["active"]]["optimize"][0]["column"] == "settling_time"
    assert pg.locator(".sw-run").count() == 1                                    # the Run column beside the table
    _step(pg, "goals")
    before = _holding(pg)
    _condition(pg, "energy", "<=", 0.001)                                         # nothing uses that little
    _idle(pg)
    assert _holding(pg) < before or before == 0
    pg.keyboard.press("Control+z")
    pg.wait_for_function(f"document.querySelector('.sw-answer-n') && parseInt(document.querySelector('.sw-answer-n').innerText.replace(/,/g, '')) === {before}")
    assert pg.locator(".sw-run").count() == 1


def test_old_files_open(pg):
    """C11: files saved by 1.27 open - a table's .svsweep (its question) and a study file (its tables)."""
    import shutil
    old = os.path.join(ROOT, "tests", "fixtures", "sweeps", "v1_27")
    work = os.path.join(pg.env["out"], "v1_27")
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "examples", "drones"), work)
    shutil.copy(os.path.join(old, "fixture.svstudy.json"), work)
    _to_sweeps(pg)
    pg.evaluate("p => window.__svRequestStudy(p)", os.path.join(work, "fixture.svstudy.json"))
    pg.wait_for_function("window.__svStudy.state().study && window.__svStudy.state().study.tables.length >= 1")
    assert pg.locator(".sw-nav").count() == 1


def test_results_first_next_runs_saved_and_reopened(pg):
    """3 (walkthrough 1-3): I have results -> the example's question typed in Goals -> 12 of 45 sets hold; the Results' Next runs
    -> Near the best -> Export (a CSV, as before); Study ▾ Save -> a .svsweep; closed and opened again: the same step."""
    from test_features import save_as
    from test_sweeps_flow import _bar_menu, _holding, _step, _tab, _the_goal
    _new_study(pg)
    pg.locator(".ns-have").click()
    goto_folder(pg, EXAMPLES)
    pg.locator(".dialog .dialog-body .fs-row", has_text="drone_tuning.csv").first.click()
    pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".sw-study-wrap")
    _idle(pg)
    _the_goal(pg)                                                                # roll error, overshoot; the least energy
    _step(pg, "results")
    _idle(pg)
    assert _holding(pg) == 12
    assert "12 of 45" in pg.locator(".sw-answer").inner_text()
    _tab(pg, "next")
    pg.wait_for_function("window.__svSweeps.doc().view.center === 'next'")
    side = pg.locator(".sw-next-side")
    for k in side.locator(".sw-kind").all():                                     # only Near the best
        box = k.locator("input")
        if ("Near the best" in k.inner_text()) != box.is_checked():
            box.click()
    side.locator(".btn", has_text="Suggest").click()
    pg.wait_for_selector(".sw-next .sw-table tbody tr")
    n = pg.locator(".sw-next .sw-table tbody tr").count()
    pg.locator(".sw-next-main .btn", has_text="Export the next runs").click()
    pg.locator(".menu.ctx button", has_text="The run list").hover()
    pg.locator(".menu.ctx button", has_text="CSV").click()
    save_as(pg, "near_best.csv")
    pg.wait_for_selector(".toast:has-text('near_best.csv')")
    rows = open(os.path.join(pg.env["out"], "near_best.csv"), encoding="utf-8").read().strip().splitlines()
    assert len(rows) > n and {"kp_roll", "ki_roll", "filter_hz"} <= set(rows[0].split(","))
    step = pg.locator(".sw-step-btn.on .sw-step-n").inner_text()
    _bar_menu(pg, "Study", "Save the study")
    save_as(pg, "walkthrough.svsweep")                                           # one table, a guessed Set up: its own file
    pg.wait_for_selector(".toast:has-text('Saved')")
    _idle(pg)
    pg.locator(".areabar .tab.active .x").click()
    pg.wait_for_function("document.querySelectorAll('.areabar .tab').length === 0")
    _bar_menu(pg, "Open", "Open a saved study")
    goto_folder(pg, pg.env["out"])
    pg.locator(".dialog .fs-row", has_text="walkthrough.svsweep").click()
    pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".sw-study-wrap .sw-steps")
    _idle(pg)
    assert pg.locator(".sw-step-btn.on .sw-step-n").inner_text() == step        # the same place
    assert _holding(pg) == 12


SIM = '''# a test program: one run = one parameters file in (JSON), one CSV row out where the study reads it
import csv, json, os, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
err = (p["a"] - 1.2) ** 2 + (p["b"] - 2.1) ** 2 + 0.05 * p["wind"]
os.makedirs(os.path.dirname(p["out"]), exist_ok=True)
with open(p["out"], "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["run_id", "a", "b", "wind", "err"])
    w.writerow([p["run_id"], p["a"], p["b"], p["wind"], err])
'''


def test_runs_first_round_one_then_round_two(pg):
    """5 (walkthrough 4-5): Start from nothing with a test program -> Next round saves the study (.svstudy.json) and
    runs round 1 -> Round 1 under Tables; a click opens it in the four steps with the goal typed in Set up; Next round
    again -> Round 2 listed, marked new."""
    import sys
    work = os.path.join(pg.env["out"], "runs_first")
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, "sim.py"), "w", encoding="utf-8") as f:
        f.write(SIM)
    from test_features import save_as
    _new_study(pg)
    pg.locator(".ns-nothing").click()
    pg.wait_for_selector("[data-part=setup]")
    for name, lo, hi, step in (("a", "0", "2", "0.5"), ("b", "1", "3", "0.5")):
        pg.locator(".su-add-param").click()
        _field(pg, ".su-new-param", name)
        pg.wait_for_selector(f"tr[data-param={name}]")
        for i, v in ((1, lo), (2, hi), (3, step)):
            _field(pg, f"tr[data-param={name}] input >> nth={i}", v)
    pg.locator(".su-add-scenario").click()
    _field(pg, ".su-new-scenario", "wind")
    pg.wait_for_selector("tr[data-scenario=wind]")
    _field(pg, "tr[data-scenario=wind] input >> nth=1", "0, 5")
    _field(pg, ".su-outputs", "err")
    pg.locator(".su-goal").select_option("err")
    _field(pg, ".su-command", f"{sys.executable} {{{{study_dir}}}}/sim.py {{{{params_file}}}}")
    pg.wait_for_function("document.querySelector('.sw-run .rc-next').dataset.missing === ''")
    pg.locator(".sw-run .lp-next").click()                                       # unsaved: Save as first
    save_as(pg, "runs_first.svstudy.json", work)
    pg.wait_for_function("document.querySelector('.sw-nav [data-nav=round][data-round=\"1\"]')", timeout=120000)
    assert _study(pg, "s.tables[0].objective") == {"expr": "err", "sense": "min"}
    pg.wait_for_selector(".sw-run .lp[data-round='1']:not([data-state=running]) .lp-next:enabled", timeout=120000)   # round 1 finished
    pg.locator(".sw-nav [data-nav=round][data-round='1']").first.click()
    pg.wait_for_selector(".sw-study-wrap .sw-steps")
    pg.wait_for_function("window.__svSweeps.doc() && window.__svSweeps.doc().columns.some((c) => c.name === 'a' && c.role === 'param')")
    _idle(pg)
    roles = {c["name"]: c["role"] for c in pg.evaluate("window.__svSweeps.doc().columns")}
    assert roles["b"] == "param" and roles["wind"] == "hold" and roles["err"] == "output"
    q = pg.evaluate("window.__svSweeps.doc().question")
    assert q["goals"][q["active"]]["optimize"][0]["column"] == "err"            # the goal from Set up
    pg.wait_for_selector(".sw-nav [data-nav=round][data-round='1'].on")         # the round shown
    pg.locator(".sw-run .lp-next").click()
    pg.wait_for_selector(".sw-nav [data-nav=round][data-round='2'] .sw-nav-new", timeout=120000)
    assert pg.locator(".sw-nav [data-nav=round][data-round='1'] .sw-nav-new").count() == 0   # opened: seen


def test_a_table_goal_edited_in_the_area_reaches_the_study(pg):
    """6 (walkthrough 6, Together's half): a study of three drones; Drone B's file opened from the navigator in the
    four steps; a limit set in its Goal step is the study file's table B's constraint and Together's ranking follows;
    the one Ctrl+Z takes both back - the study table in its own words again."""
    from test_sweeps_flow import _condition, _step
    _to_sweeps(pg)
    pg.evaluate("p => window.__svRequestStudy(p)", os.path.join(ROOT, "examples", "drones", "drones.svstudy.json"))
    pg.wait_for_selector("[data-shot='study'][data-settled='1']", timeout=60000)
    pg.wait_for_function("window.__svStudy.state().result && !window.__svStudy.state().busy")
    before = _study(pg, "s.tables.find((t) => t.id === 'B').constraints")
    feasible = pg.evaluate("window.__svStudy.state().result.counts.feasible")
    assert feasible > 0
    pg.wait_for_selector(".sw-nav [data-nav=file-table]:has-text('Drone B')")
    pg.locator(".sw-nav [data-nav=file-table]", has_text="Drone B").click()
    pg.wait_for_function("window.__svSweeps.doc() && window.__svSweeps.doc().columns.some((c) => c.name === 'energy' && c.role === 'output')")
    _idle(pg)
    assert _study(pg, "s.tables.find((t) => t.id === 'B').constraints") == before   # opening is no edit
    _step(pg, "goals")
    _condition(pg, "energy", "<=", 0.001)                                         # nothing uses that little
    _idle(pg)
    pg.wait_for_function("window.__svStudy.state().study.tables.find((t) => t.id === 'B').constraints.some((c) => c.includes('energy'))")
    pg.wait_for_function("window.__svStudy.state().result && !window.__svStudy.state().busy && "
                         f"window.__svStudy.state().result.counts.feasible < {feasible}")   # Together follows
    pg.keyboard.press("Control+z")                                                 # one step: the table and the study
    pg.wait_for_function(f"JSON.stringify(window.__svStudy.state().study.tables.find((t) => t.id === 'B').constraints) === {json.dumps(json.dumps(before, separators=(',', ':')))}")
    pg.wait_for_function(f"window.__svStudy.state().result && !window.__svStudy.state().busy && window.__svStudy.state().result.counts.feasible === {feasible}")
    assert pg.locator(".sw-run").count() == 1
