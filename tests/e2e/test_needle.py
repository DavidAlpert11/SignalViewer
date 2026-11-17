"""The needle (owner, 2026-11-17: "in analysis it is critical to see every point - a skip can hide the problem";
CLAUDE.md: no point is ever left out of a picture). One run far out among 200,000 must be drawn - in the pixels -
in the Sweeps parallel plot above the cap (the Data step and All runs, density: the default). The recordings'
views (time plot, X-Y, 3D, map track, error traces, envelope) are checked in backend/tests/test_needle.py."""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, pg  # noqa: E402,F401
from test_sweeps_big_table import RAW_PLOT, _big_table, _cap  # noqa: E402
from test_sweeps_flow import _idle, _open_table, _step, _tab  # noqa: E402

NEEDLE_ROW, NEEDLE = 123_457, 40.0          # every other run's error is below ~20


# ink in the top of the plot near the error axis (the last axis), left of its tick labels: only a run with an error
# near the top of the axis passes there
INK = """() => {
  const cv = document.querySelector('.pp canvas'), names = [...document.querySelectorAll('.pp-axis-name')];
  const ax = names.find((b) => b.textContent.trim() === 'error');
  const r = cv.getBoundingClientRect(), a = ax.getBoundingClientRect(), dpr = cv.width / r.width;
  const xa = a.left + a.width / 2 - r.left;
  const x0 = Math.round((xa - 120) * dpr), x1 = Math.round((xa - 40) * dpr), y0 = Math.round(40 * dpr), y1 = Math.round(90 * dpr);
  const d = cv.getContext('2d').getImageData(x0, y0, x1 - x0, y1 - y0).data;
  let ink = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i] > 40) ink++;
  return ink;
}"""


def _needle_table(folder):
    df = _big_table(folder)
    df.loc[NEEDLE_ROW, "error"] = NEEDLE
    df.to_csv(os.path.join(folder, "big_sweep.csv"), index=False)


def _drawn(pg):
    pg.wait_for_selector(".pp canvas[data-density='1']", timeout=60000)
    pg.wait_for_function("document.querySelector('.sw-count[data-exact=\"1\"]') && document.querySelector('.pp canvas').dataset.drawing === '0'",
                         timeout=60000)


def test_the_needle_is_drawn_in_the_data_step_and_all_runs(pg, tmp_path):
    _needle_table(tmp_path)
    _cap(pg, "50,000", "Every run (density)")
    _open_table(pg, tmp_path, "big_sweep.csv")
    pg.locator("[role=tab]", has_text=RAW_PLOT).first.click()
    _drawn(pg)
    assert pg.evaluate(INK) > 20, "the needle is not drawn in the Data step's plot"
    assert "200,000 of 200,000" in pg.locator(".sw-plotbar .sw-count").inner_text()
    assert pg.locator(".sw-density").count() == 1                                  # said what the shades are
    _step(pg, "results")
    pg.locator(".sw-show select").select_option("all")
    _tab(pg, "runs")
    _idle(pg)
    _drawn(pg)
    assert pg.evaluate(INK) > 20, "the needle is not drawn in All runs"


def test_a_sample_is_a_choice_and_is_said(pg, tmp_path):
    """Settings: above the cap, a sample instead - said under the plot (a rare run may be missing from it)."""
    _big_table(tmp_path)
    _cap(pg, "50,000", "A sample")
    _open_table(pg, tmp_path, "big_sweep.csv")
    pg.locator("[role=tab]", has_text=RAW_PLOT).first.click()
    pg.wait_for_selector(".sw-sampled:has-text('Drawing 50,000 of 200,000 runs')")
    assert pg.locator(".pp canvas").get_attribute("data-density") == "0"
