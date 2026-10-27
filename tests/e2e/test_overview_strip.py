"""Investigation step 7: the run at a glance - phases and automatic flags above the plots.

    python -m pytest tests/e2e/test_overview_strip.py -q
"""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401

DEMO = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "investigate")


@pytest.fixture(autouse=True)
def _demo(pg):
    for f in ("heavy_payload.csv", "light_payload.csv"):
        dst = os.path.join(pg.env["data"], f)
        if not os.path.exists(dst):
            shutil.copy(os.path.join(DEMO, f), dst)
    yield


def test_phases_flags_and_going_there(pg):
    open_files(pg, "heavy_payload.csv")
    pg.wait_for_selector(".ov-strip .ov-phase")
    assert pg.locator(".ov-phase").all_inner_texts() == ["TAKEOFF", "AUTO", "LOITER", "LAND"]
    assert "3 flags" in pg.inner_text(".ov-summary")
    flags = pg.locator(".ov-flag")
    assert flags.count() == 3 and "Motor3 flat at its limit" in flags.first.get_attribute("title")
    flags.first.click()
    pg.wait_for_function("window.__sv.state().cursor.dual && Math.abs(window.__sv.state().cursor.t1 - 38.3) < 0.2")
    pg.locator(".ov-phase", has_text="LOITER").click()
    pg.wait_for_function("window.__sv.state().cursor.t1 === 100")


def test_quiet_run_hide_and_show(pg):
    open_files(pg, "light_payload.csv")
    pg.wait_for_selector(".ov-strip .ov-phase")
    assert "0 flags" in pg.inner_text(".ov-summary") and pg.locator(".ov-flag").count() == 0
    pg.click(".ov-hide")
    pg.wait_for_selector(".ov-show")
    assert pg.locator(".ov-strip").count() == 0
    pg.click(".ov-show")
    pg.wait_for_selector(".ov-strip")
