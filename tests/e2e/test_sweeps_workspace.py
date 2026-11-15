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
