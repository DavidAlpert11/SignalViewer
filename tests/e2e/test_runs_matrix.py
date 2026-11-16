"""Investigation step 5: runs x conditions - parameters that tell runs apart, counts per condition,
the odd one marked, a click opens that run's stretch, two columns against each other.

    python -m pytest tests/e2e/test_runs_matrix.py -q
"""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_conditions import _new, _panel  # noqa: E402
from test_features import S, env, open_files, pg  # noqa: E402,F401

DEMO = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "investigate")


@pytest.fixture(autouse=True)
def _files(pg):
    d = pg.env["data"]
    for f in ("heavy_payload.csv", "light_payload.csv"):
        if not os.path.exists(os.path.join(d, f)):
            shutil.copy(os.path.join(DEMO, f), os.path.join(d, f))
    for mass, bursts in ((1, 1), (2, 1), (3, 1), (4, 5)):            # mass 4: the odd one out
        p = os.path.join(d, f"mc_mass{mass}.csv")
        if not os.path.exists(p):
            with open(p, "w") as fh:
                fh.write("Time,Load\n")
                for i in range(400):
                    t = i * 0.1
                    on = any(abs(t - (5 + 6 * k)) < 1 for k in range(bursts))
                    fh.write(f"{t:.1f},{(8 if on else 1) * mass / 2:.3f}\n")
    yield


def test_matrix_parameters_counts_and_click(pg):
    open_files(pg, "heavy_payload.csv", "light_payload.csv")
    _panel(pg)
    _new(pg, "Roll error", "abs(Roll - DesRoll) > 5")
    pg.click(".cond-save")
    pg.wait_for_function("Object.values(window.__sv.state().condResults).length === 1")
    pg.click(".cond-matrix")
    pg.wait_for_selector(".mx-dialog")
    pg.wait_for_selector(".mx-table th:has-text('Payload_kg')")
    rows = {r.locator(".mx-file").inner_text(): r.locator(".mx-cell").inner_text() for r in pg.locator(".mx-table tbody tr").all()}
    assert rows == {"heavy_payload.csv": "3", "light_payload.csv": "0"}
    pg.select_option(".mx-measure", "total")
    pg.wait_for_function("[...document.querySelectorAll('.mx-cell')].some(td => td.textContent.includes('.'))")
    pg.locator(".mx-table tbody tr", has_text="heavy_payload").locator(".mx-cell").click()
    pg.wait_for_selector(".mx-dialog", state="detached")
    pg.wait_for_function("window.__sv.state().cursor.dual && Math.abs(window.__sv.state().cursor.t1 - 38.46) < 0.05")


def test_odd_run_marked_and_scatter(pg):
    open_files(pg, "mc_mass1.csv", "mc_mass2.csv", "mc_mass3.csv", "mc_mass4.csv")
    _panel(pg)
    _new(pg, "Burst", "Load > 3")
    pg.click(".cond-save")
    pg.wait_for_function("Object.values(window.__sv.state().condResults).length === 1")
    pg.click(".cond-matrix")
    pg.wait_for_selector(".mx-table th:has-text('mass')")
    odd = pg.locator(".mx-cell.odd")
    assert odd.count() == 1 and odd.inner_text() == "5"
    pg.select_option(".mx-x", "p:mass")
    pg.wait_for_selector(".mx-r")
    assert "r = " in pg.inner_text(".mx-r") and "4 runs" in pg.inner_text(".mx-r")


def test_measures_and_name_parameters_to_sweeps(pg):
    """M1: a measure per run (defined while looking at the open runs) and parameters from the file names,
    with no condition at all; Undo takes a measure back; the table opens in Sweeps with them as columns."""
    open_files(pg, "mc_mass1.csv", "mc_mass2.csv", "mc_mass4.csv")
    _panel(pg)
    pg.click(".cond-matrix")
    pg.locator(".mx-dialog").wait_for()
    pg.click(".mx-add-measure")
    pg.select_option(".mx-op", "max")
    pg.fill(".mx-sig", "Load")
    pg.click(".mx-add")
    pg.wait_for_function("document.querySelectorAll('.mx-mval').length === 3 && [...document.querySelectorAll('.mx-mval')].every(td => td.textContent !== '–')")
    vals = sorted(float(x) for x in pg.locator(".mx-mval").all_inner_texts())
    assert vals == [4.0, 8.0, 16.0]                     # 8 x mass / 2
    pg.fill(".mx-pattern input", "mc_mass{mass}"); pg.press(".mx-pattern input", "Enter")
    pg.wait_for_function("[...document.querySelectorAll('.mx-table th')].some(th => th.textContent.trim() === 'mass')")
    assert S(pg, "s.ws.namePattern") == "mc_mass{mass}" and S(pg, "s.ws.measures.length") == 1
    pg.click(".mx-dialog button:has-text('Open in Sweeps')")
    pg.wait_for_function("window.__sv.state().area === 'sweeps'")
    pg.wait_for_selector("text=max Load", timeout=20000)
