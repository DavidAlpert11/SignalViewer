"""Owner (2026-11-13): the loop from inside the app - the demo explains itself (its real input / output) and can be
copied to a folder; the copy opens as an ordinary study whose Run the loop proposes, runs the program, reads the
results from the folder and ranks them."""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, pg  # noqa: E402,F401

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEMO = os.path.join(ROOT, "examples", "smart_sweep_demo", "demo.svstudy.json")


def test_the_demo_explains_itself(pg):
    pg.locator(".ex-card[data-example='smartSweepDemo']").click()
    pg.wait_for_selector(".dm-strip")                                            # it opens on Next runs (§7a)
    pg.locator(".sw-step-btn[data-flow=data]").click()
    pg.locator(".sw-nav [data-nav=about]").click()                               # C9: the study's About page, in Data
    how = pg.locator(".dm-how")
    how.wait_for()
    io = how.locator(".dm-io").all_inner_texts()
    assert '"run_id": "8c068b1aed"' in io[0] and '"Kp":' in io[0]                 # the program's real input
    assert io[1].startswith("Kp,Ki,Kd,wind,overshoot")                            # and its output
    assert how.locator(".dm-copy").count() == 1
    # owner (2026-11-16): the wrapper that runs a round, and the same run by hand from the demo's folder
    assert "sweep_wrapper.py --list {{params_files}}" in io[2]
    assert "python sweep_wrapper.py --spec grid.txt" in io[3]
    how.locator(".dm-inputs").click()                                            # the inputs: the set-up
    pg.locator(".su [data-param='Kp']").wait_for()
    assert pg.locator(".su-scen [data-scenario='wind']").count() == 1             # the demo's scenarios shown


def test_the_inputs_as_text_and_a_wrapper(pg):
    """Owner (2026-11-16): the inputs typed as 'name: values' (MATLAB-style ranges, text values); a wrapper on this PC
    runs a round; the example wrapper copied beside the study."""
    folder = os.path.join(pg.env["out"], "my_wrapper")
    r = pg.evaluate("async ([s, f]) => (await (await fetch('/api/sweeps/demo/copy', {method: 'POST', headers: {'Content-Type': 'application/json'}, "
                    "body: JSON.stringify({study_path: s, folder: f})})).json())", [DEMO, folder])
    os.remove(os.path.join(folder, "sweep_wrapper.py"))
    pg.evaluate("p => window.__svRequestStudy(p)", r["path"])
    pg.locator(".cp-main", has_text="Nothing has run yet").wait_for()
    pg.locator(".sw-step-btn[data-flow=data]").click()
    pg.locator(".sw-nav [data-nav=setup]").click()
    sec1 = pg.locator(".su-sec[data-section='1']")
    sec1.locator(".su-as-text").click()
    text = sec1.locator(".su-params-text")
    assert "Kp: 0.5:0.225:5" in text.input_value()
    text.fill("Kp: 1, 2, 5, 8:0.5:10\nKi: 0:0.1:2\nKd: 0.05:0.1:2.05")
    sec1.locator(".su-as-text").click()                                          # blur writes; back to the table
    pg.locator(".su [data-param='Kp'] input[aria-label='Values']").wait_for()
    assert pg.locator(".su [data-param='Kp'] input[aria-label='Values']").input_value() == "1, 2, 5, 8, 8.5, 9, 9.5, 10"
    sec2 = pg.locator(".su-sec[data-section='2']")
    sec2.locator(".su-as-text").click()
    sec2.locator(".su-scen-text").fill("wind: 0:5:10\nmode: calm, gusty")
    sec2.locator(".su-as-text").click()
    pg.locator(".su-scen [data-scenario='mode']").wait_for()
    assert "calm, gusty" in pg.locator(".su-scen [data-scenario='mode'] input").nth(1).input_value()
    # how to run: a wrapper on this PC, the example copied beside the study
    pg.locator(".sw-step-btn[data-flow=next]").click()
    pg.locator(".su-where [data-where='wrapper']").click()
    assert "sweep_wrapper.py --list {{params_files}}" in pg.locator(".su-command").input_value()
    pg.locator(".su-wrapper-copy").click()
    pg.wait_for_function("document.body.innerText.includes('sweep_wrapper.py is beside the study')")
    assert os.path.isfile(os.path.join(folder, "sweep_wrapper.py"))

def test_a_copy_of_the_demo_runs_the_loop(pg):
    folder = os.path.join(pg.env["out"], "my_loop")
    r = pg.evaluate("async ([s, f]) => (await (await fetch('/api/sweeps/demo/copy', {method: 'POST', headers: {'Content-Type': 'application/json'}, "
                    "body: JSON.stringify({study_path: s, folder: f})})).json())", [DEMO, folder])
    pg.evaluate("p => window.__svRequestStudy(p)", r["path"])
    pg.locator(".cp-main", has_text="Nothing has run yet").wait_for()               # after the table is read (it raced "Reading the table...")
    pg.locator(".sw-step-btn[data-flow=next]").click()                           # §7a: the loop is Next runs
    lp = pg.locator(".lp")
    lp.wait_for()
    assert "sweep_wrapper.py --list" in lp.locator(".lp-what code").first.inner_text()   # the exact command shown: the wrapper
    assert os.path.isfile(os.path.join(folder, "sweep_wrapper.py")) and os.path.isfile(os.path.join(folder, "grid.txt"))
    lp.locator(".lp-next").click()
    pg.wait_for_function("document.querySelector('.lp')?.dataset.points === '1' && document.querySelector('.lp').dataset.state !== 'running'",
                         timeout=180000)
    assert pg.locator(".lp-rounds tbody tr").count() == 1
    pg.locator(".sw-step-btn[data-flow=results]").click()
    pg.wait_for_selector("[data-shot='study'][data-settled='1']", timeout=60000)
    assert pg.locator(".cp-rank tbody tr[data-rank='1']").count() == 1           # the round's results ranked
    assert os.path.isdir(os.path.join(folder, "results", "A"))                    # read from where the program wrote them
