"""Sweeps as one study (plan §4.7): the walkthroughs - results first, runs first, the demo on one screen.
Each waits on state (`window.__svSweeps`, `window.__svStudy`, data-* attributes), never on a sleep."""
import json
import os

import re

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
    while pg.locator(".sw-pills .sw-tbl-pill").count():                     # every table closed: the welcome page
        n = pg.locator(".sw-pills .sw-tbl-pill").count()
        pg.locator(".sw-pills .sw-tbl-pill .x").first.click()
        pg.wait_for_function(f"document.querySelectorAll('.sw-pills .sw-tbl-pill').length === {n - 1}")


def _flow(pg, step):
    """One of the five steps (PLAN 2026-11-16 §7a): data, columns, goal, results, next."""
    pg.locator(f".sw-step-btn[data-flow={step}]").click()
    pg.wait_for_selector(f".sw-flow[data-flow={step}]")


def _new_study(pg):
    _to_sweeps(pg)
    pg.evaluate("window.__svSweeps.show('')")
    pg.wait_for_selector(".sw-welcome")
    pg.locator(".areabar .btn", has_text="Open").click()                       # FR6: New study… is in Open ▾ (and Ctrl+K)
    pg.locator(".menu.ctx button", has_text="New study").click()
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
    _flow(pg, "data")                                                           # the navigator: in Data only (§7a)
    pg.locator(".sw-nav [data-nav=setup]").click()
    pg.wait_for_selector("[data-part=setup]")
    assert pg.locator(".sw-nav-done").inner_text().endswith("/3")
    assert pg.locator(".su-params tbody tr[data-param]").count() == 3
    assert [pg.locator(".su-scen tr[data-scenario]").nth(i).get_attribute("data-scenario") for i in range(3)] == \
        ["scenario_wind_mps", "scenario_payload_kg", "scenario_gusts"]
    lo, hi = (float(pg.locator(".su-params tr[data-param=kp_roll] input").nth(i).input_value()) for i in (1, 2))
    assert 0 < lo < hi                                                          # the range seen in the table
    assert _study(pg, "s.launcher.submit.length") == 0                          # no command: still the table's own file
    pg.locator(".su-to-results").click()
    pg.wait_for_selector(".sw-flow[data-flow=results]")
    _flow(pg, "data")
    pg.locator(".sw-nav [data-nav=setup]").click()                              # and back with the table's own item
    pg.wait_for_selector("[data-part=setup]")
    pg.locator(".sw-nav [data-nav=table]", has_text="drone_tuning.csv").click()
    pg.wait_for_selector(".sw-flow[data-flow=data] .sw-raw")                     # its data


def test_start_from_nothing_types_the_set_up(pg):
    """4 / SF1: New study -> Start from nothing = Send runs: two parameters with ranges, one scenario column, the
    command - each written into the study file; round 1 is ready without an output or a goal (those come from the
    results); Undo takes the last one back."""
    _new_study(pg)
    pg.locator(".ns-nothing").click()
    pg.wait_for_selector("[data-part=setup]")
    assert set(pg.get_attribute("[data-part=setup]", "data-missing").split()) == {"params", "command"}
    assert "missing: the parameters, the command" in pg.locator(".su-send").inner_text()
    assert pg.locator(".su-send-btn").is_disabled()
    assert pg.locator(".su-outputs, .su-goal").count() == 0                       # no outputs, no goal in Send runs
    _flow(pg, "next")                                                           # §7a: the loop is the Next runs step's
    assert set(pg.get_attribute(".sw-run .rc-next", "data-missing").split()) == {"params", "command"}
    assert "cannot run yet" in pg.locator(".sw-run .rc-next").inner_text()
    assert pg.locator(".sw-run .rc-goal[data-goal='0']").count() == 1           # the loop asks for its goal here
    pg.locator(".rc-setup").click()                                              # Send runs: back in Data
    pg.wait_for_selector("[data-part=setup]")
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
    pg.wait_for_function("document.querySelector('[data-part=setup]').dataset.missing === 'command'")
    _field(pg, ".sw-flow[data-flow=data] .su-command", "python sim.py {{params_file}}")      # how to run: Send runs' part 3
    pg.wait_for_function("document.querySelector('[data-part=setup]').dataset.missing === ''")       # round 1 is ready
    assert "16 sets × 2 scenarios = 32 runs" in pg.locator(".su-send").inner_text()
    assert pg.locator(".su-send-btn").is_enabled()
    assert pg.locator(".sw-nav .sw-nav-done.ok").inner_text() == "✓ 3/3"
    assert _study(pg, "s.start") == {"grid": {"a": 4, "b": 4}, "scenarios": {"T1": {"wind": [0, 5]}}}
    assert _study(pg, "s.tables[0].objective") == {"expr": "", "sense": "min"}
    assert _study(pg, "s.launcher.submit") == ["python", "sim.py", "{{params_file}}"]
    _flow(pg, "next")
    assert pg.get_attribute(".sw-run .rc-next", "data-missing") == ""
    assert pg.locator(".lp-next").is_disabled()                                  # no goal: no loop (round 1 is Send runs')
    pg.keyboard.press("Control+z")                                              # the one Undo: the command goes
    pg.wait_for_function("window.__svStudy.state().study.launcher.submit.length === 0")
    assert pg.get_attribute(".sw-run .rc-next", "data-missing") == "command"


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
    _flow(pg, "data")                                                           # the demo opens on Next runs; its tables in Data
    pg.wait_for_function("document.querySelectorAll('.sw-nav [data-nav=round][data-round=\"1\"]').length >= 2", timeout=30000)
    pg.locator(".sw-nav [data-nav=round][data-round='1']").first.click()
    pg.wait_for_selector(".sw-flow[data-flow=data] .sw-raw")
    _idle(pg)
    pg.wait_for_selector(".sw-nav [data-nav=round].on")
    assert pg.locator(".sw-nav [data-nav=round].on").get_attribute("data-round") == "1"
    pg.locator(".sw-nav [data-nav=setup]").click()
    pg.wait_for_selector("[data-part=setup]")


def test_one_flow_the_tables_in_data_running_in_next_runs(pg):
    """PLAN 2026-11-16 §7a: one stepper for every study - the tables (and the problem) only in Data, its column
    resizable; Columns / Goal / Results wait for a table; running only in Next runs (no Run column beside the rest)."""
    _new_study(pg)
    pg.locator(".ns-nothing").click()
    pg.wait_for_selector("[data-part=setup]")
    assert pg.locator(".sw-flow[data-flow=data] .sw-nav").count() == 1
    assert pg.locator(".sw-run").count() == 0
    assert pg.locator(".sw-flow[data-flow=data] .su-command").count() == 1       # SF1: how to run is Send runs'
    for s in ("columns", "goal", "results"):                                    # nothing to show without a table
        assert pg.locator(f".sw-step-btn[data-flow={s}]").is_disabled()
    w = pg.evaluate("document.querySelector('.sw-nav').getBoundingClientRect().width")
    pg.locator(".sw-ws > .resizer").focus()
    pg.keyboard.press("Shift+ArrowRight")                                        # the tables' column: wider
    pg.wait_for_function(f"document.querySelector('.sw-nav').getBoundingClientRect().width > {w + 30}")
    _flow(pg, "next")
    pg.wait_for_selector(".sw-run .rc-next")
    assert pg.locator(".sw-nav").count() == 0
    assert pg.locator(".sw-run .su-command").count() == 0                         # SF1: how to run is in Send runs
    assert pg.locator(".sw-run .rc-goal").count() == 1                            # the loop's goal asked for here
    pg.wait_for_selector(".nx-round1")


def test_one_open_menu_and_each_command_once(pg):
    """C10: one Open ▾ (New study, a table, a folder, a saved study of either kind) - no second submenu; the palette
    lists each Sweeps command once; a study file's Save / Undo are the area bar's (the panel has none of its own)."""
    _to_sweeps(pg)
    pg.locator(".areabar .btn", has_text="Open").first.click()
    items = [x.strip() for x in pg.locator(".menu button").all_inner_texts() if x.strip()]
    assert items == ["New study…", "Open a table", "Open a folder of tables", "From a folder of recordings…", "Open a saved study"]
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
    _flow(pg, "data")
    pg.wait_for_function("document.querySelectorAll('.sw-nav [data-nav=round][data-round=\"1\"]').length === 3", timeout=30000)
    pg.locator(".sw-nav [data-nav=round][data-round='1']").nth(1).click()          # A, B, C: Drone B
    pg.wait_for_selector(".sw-flow[data-flow=data] .sw-raw")
    pg.wait_for_function("window.__svSweeps.doc() && window.__svSweeps.doc().columns.some((c) => c.name === 'Kp' && c.role === 'param')")
    _idle(pg)
    roles = {c["name"]: c["role"] for c in pg.evaluate("window.__svSweeps.doc().columns")}
    assert [roles[k] for k in ("Kp", "Ki", "Kd")] == ["param"] * 3
    assert roles["mass"] == roles["wind"] == "hold" and roles["overshoot"] == "output"
    q = pg.evaluate("window.__svSweeps.doc().question")
    assert q["goals"][q["active"]]["optimize"][0]["column"] == "settling_time"
    _step(pg, "goals")
    before = _holding(pg)
    _condition(pg, "energy", "<=", 0.001)                                         # nothing uses that little
    _idle(pg)
    assert _holding(pg) < before or before == 0
    pg.keyboard.press("Control+z")
    pg.wait_for_function(f"document.querySelector('.sw-answer-n') && parseInt(document.querySelector('.sw-answer-n').innerText.replace(/,/g, '')) === {before}")
    _flow(pg, "next")                                                           # the demo's loop, beside this table's proposal
    pg.wait_for_selector(".sw-run .dm-next")


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
    assert pg.locator(".sw-steps").count() == 1


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
    pg.wait_for_function("window.__svSweeps.doc().view.center === 'next'")       # kept with the table: it opens there again
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
    pg.locator(".sw-pills .sw-tbl-pill.on .x").click()
    pg.wait_for_function("document.querySelectorAll('.sw-pills .sw-tbl-pill').length === 0")
    _bar_menu(pg, "Open", "Open a saved study")
    goto_folder(pg, pg.env["out"])
    pg.locator(".dialog .fs-row", has_text="walkthrough.svsweep").click()
    pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".sw-study-wrap .sw-steps")
    _idle(pg)
    pg.wait_for_selector(".sw-flow[data-flow=next]")                             # the same place: Next runs
    assert pg.locator(".sw-step-btn.on .sw-step-n").inner_text() == step
    _step(pg, "results")
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
    """5 / SF1 (walkthrough 4-5): Start from nothing with a test program -> Send round 1 saves the study (.svstudy.json)
    and runs it -> its results come in as a table in Data, the roles from Send runs (what varies = param, the scenario
    = hold, the rest = output); the goal said in its Goal step reaches the study; Next round in Next runs -> Round 2
    listed, marked new. Clear ▾ > Everything then closes the study too, and its Undo opens it again."""
    import sys
    work = os.path.join(pg.env["out"], "runs_first")
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, "sim.py"), "w", encoding="utf-8") as f:
        f.write(SIM)
    from test_features import save_as, menu_item
    from test_sweeps_flow import _optimize
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
    _field(pg, ".su-command", f"{sys.executable} {{{{study_dir}}}}/sim.py {{{{params_file}}}}")
    pg.wait_for_function("document.querySelector('[data-part=setup]').dataset.missing === ''")
    pg.locator(".su-send-btn").click()                                           # unsaved: Save as first
    save_as(pg, "runs_first.svstudy.json", work)
    # the first results: a regular table in Data, shown at once (the user was on Send runs)
    pg.wait_for_selector(".sw-flow[data-flow=data] .sw-raw", timeout=120000)
    pg.wait_for_function("window.__svSweeps.doc() && window.__svSweeps.doc().columns.some((c) => c.name === 'a' && c.role === 'param')")
    _idle(pg)
    roles = {c["name"]: c["role"] for c in pg.evaluate("window.__svSweeps.doc().columns")}
    assert roles["b"] == "param" and roles["wind"] == "hold" and roles["err"] == "output" and roles["run_id"] == "id"
    pg.wait_for_function("document.querySelector('.sw-step-btn[data-flow=columns]').innerText.includes('2 parameters')")   # its counts follow
    pg.wait_for_selector(".sw-nav [data-nav=round][data-round='1'].on")         # the round shown
    assert _study(pg, "s.tables[0].objective.expr") == ""
    _flow(pg, "next")
    assert pg.locator(".sw-next-side > .rc-goal[data-goal='0'] .rc-to-goal").count() == 1   # the loop asks for its goal, first
    assert pg.locator(".sw-run .lp-next").is_disabled()
    pg.locator(".rc-to-goal").click()                                            # the table's Goal step
    pg.wait_for_selector(".sw-flow[data-flow=goal]")
    _optimize(pg, "err", "min")
    pg.wait_for_function("window.__svStudy.state().study.tables[0].objective.expr === 'err'")
    _flow(pg, "next")
    pg.locator(".sw-run .lp-next").click()
    pg.wait_for_selector(".sw-run .lp[data-round='2']:not([data-state=running]) .lp-next:enabled", timeout=120000)
    _flow(pg, "data")
    pg.wait_for_selector(".sw-nav [data-nav=round][data-round='2'] .sw-nav-new", timeout=120000)
    assert pg.locator(".sw-nav [data-nav=round][data-round='1'] .sw-nav-new").count() == 0   # opened: seen
    # SF1: Clear ▾ > Everything closes the study as well (asked first); the notice's Undo opens it all again
    pg.locator(".sw-clear-btn").click()
    menu_item(pg, "Everything")
    pg.locator(".dialog-foot .btn").last.click()
    pg.wait_for_selector(".sw-welcome")
    assert not pg.evaluate("window.__svStudy.state().open")
    pg.locator(".toast button:has-text('Undo')").click()
    pg.wait_for_function("window.__svStudy.state().open && window.__svStudy.state().path.endsWith('runs_first.svstudy.json')")
    pg.wait_for_function("!!window.__svSweeps.doc()")                           # the tables too


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
    _flow(pg, "data")
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
    _flow(pg, "results")                                                         # the systems together: a tab of Results
    pg.locator(".sw-center-tabs [data-tab=together]").click()
    pg.wait_for_selector("[data-shot='study']")


def test_three_equal_starts_each_one_click(pg):
    """M34 FR6: the empty Sweeps screen - I have results, Start from nothing, A folder of recordings - each one click,
    the examples under them; a study with tables does not read "needs a table"; no "1 tables"."""
    _to_sweeps(pg)
    pg.evaluate("window.__svSweeps.show('')")
    pg.wait_for_selector(".sw-welcome .sw-start")
    boxes = pg.eval_on_selector_all(".sw-welcome .sw-start", "els => els.map((e) => [Math.round(e.getBoundingClientRect().width), Math.round(e.getBoundingClientRect().height)])")
    assert len(boxes) == 3 and len({tuple(b) for b in boxes}) == 1, boxes                      # three equal buttons
    for sel in (".sw-try-gains", ".sw-try-demo", ".sw-try-folder"):              # the examples arrive with the list of examples
        pg.wait_for_selector(f".sw-welcome {sel}")
    for start, examples in (("have", 3), ("nothing", 1), ("folder", 1)):
        assert pg.locator(f".sw-way[data-start={start}] .sw-welcome-actions .btn").count() == examples
    pg.locator(".sw-way[data-start=have] .sw-start").click()                     # one click: the table's file dialog
    pg.wait_for_selector(".dialog .crumbs"); pg.keyboard.press("Escape")
    pg.locator(".sw-way[data-start=folder] .sw-start").click()                   # one click: the folder's dialog
    pg.wait_for_selector(".dialog .crumbs"); pg.keyboard.press("Escape")
    pg.wait_for_selector(".dialog", state="detached")
    pg.locator(".sw-way[data-start=nothing] .sw-start").click()                  # one click: Send runs, empty
    pg.wait_for_selector(".su")


def test_a_study_with_tables_does_not_need_a_table(pg):
    """FR6: steps 2 and 3 of a study with tables (none open) do not read "needs a table"; the status line counts
    its tables in good grammar."""
    pg.locator(".ex-card[data-example='commonGains']").click()
    pg.wait_for_selector(".sw-steps .sw-step-btn[data-flow='columns']", timeout=60000)
    pg.wait_for_function("document.querySelector('footer.status').innerText.includes('Study:')")
    steps = pg.locator(".sw-steps").inner_text()
    assert "needs a table" not in steps, steps
    status = pg.locator("footer.status").inner_text()
    assert not re.search(r"\b1 tables\b", status), status
    assert "3 tables" in status, status
