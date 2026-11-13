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
    pg.wait_for_selector(".dm-strip")
    how = pg.locator(".dm-how")
    how.wait_for()
    io = how.locator(".dm-io").all_inner_texts()
    assert '"run_id": "8c068b1aed"' in io[0] and '"Kp":' in io[0]                 # the program's real input
    assert io[1].startswith("Kp,Ki,Kd,wind,overshoot")                            # and its output
    assert how.locator(".dm-copy").count() == 1


def test_a_copy_of_the_demo_runs_the_loop(pg):
    folder = os.path.join(pg.env["out"], "my_loop")
    r = pg.evaluate("async ([s, f]) => (await (await fetch('/api/sweeps/demo/copy', {method: 'POST', headers: {'Content-Type': 'application/json'}, "
                    "body: JSON.stringify({study_path: s, folder: f})})).json())", [DEMO, folder])
    pg.evaluate("p => window.__svRequestStudy(p)", r["path"])
    lp = pg.locator(".lp")
    lp.wait_for()
    assert "demo-sim" in lp.locator(".lp-what code").first.inner_text()            # the exact command shown
    pg.locator(".cp-main", has_text="Nothing has run yet").wait_for()               # after the table is read (it raced "Reading the table...")
    lp.locator(".lp-next").click()
    pg.wait_for_function("document.querySelector('.lp')?.dataset.points === '1' && document.querySelector('.lp').dataset.state !== 'running'",
                         timeout=180000)
    pg.wait_for_selector("[data-shot='study'][data-settled='1']", timeout=60000)
    assert pg.locator(".cp-rank tbody tr[data-rank='1']").count() == 1           # the round's results ranked
    assert pg.locator(".lp-rounds tbody tr").count() == 1
    assert os.path.isdir(os.path.join(folder, "results", "A"))                    # read from where the program wrote them
