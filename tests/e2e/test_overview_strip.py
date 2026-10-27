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
    assert pg.locator(".ov-row .ov-phase").all_inner_texts() == ["TAKEOFF", "AUTO", "LOITER", "LAND"]
    assert "3 flags" in pg.inner_text(".ov-head")
    flags = pg.locator(".ov-flag")
    assert flags.count() == 3 and "Motor3 flat at its limit" in flags.first.get_attribute("title")
    flags.first.click()
    pg.wait_for_function("window.__sv.state().cursor.dual && Math.abs(window.__sv.state().cursor.t1 - 38.3) < 0.2")
    pg.locator(".ov-phase", has_text="LOITER").dblclick()                 # double-click: zoom there
    pg.wait_for_function("window.__sv.state().cursor.t1 === 100")


def test_quiet_run_hide_and_show(pg):
    open_files(pg, "light_payload.csv")
    pg.wait_for_selector(".ov-strip .ov-phase")
    assert "0 flags" in pg.inner_text(".ov-head") and pg.locator(".ov-flag").count() == 0
    pg.click(".ov-hide")
    pg.wait_for_selector(".ov-show")
    assert pg.locator(".ov-strip").count() == 0
    pg.click(".ov-show")
    pg.wait_for_selector(".ov-strip")


def test_rows_and_a_combined_selection_saved_as_a_condition(pg):
    from test_conditions import _new, _panel
    open_files(pg, "heavy_payload.csv")
    pg.wait_for_selector(".ov-row .ov-phase")
    _panel(pg)
    _new(pg, "Motor sat", "Motor3 > 1990")
    pg.click(".cond-save")
    pg.wait_for_function("Object.values(window.__sv.state().condResults).length === 1")
    pg.click(".ov-add")
    pg.locator(".menu.ctx button", has_text="Motor sat").click()
    pg.wait_for_function("(window.__sv.state().ws.overviewRows || []).length === 2")
    pg.wait_for_selector(".ov-row[data-row^='c:'] .ov-phase")
    # or in one row: AUTO or LOITER (next to each other: one stretch)
    pg.locator(".ov-phase", has_text="AUTO").click()
    pg.locator(".ov-phase", has_text="LOITER").click(modifiers=["Control"])
    pg.wait_for_selector(".ov-selbar")
    assert "AUTO ∨ LOITER" in pg.inner_text(".ov-seltext") and "1 stretches" in pg.inner_text(".ov-seltext")
    # and across rows: AUTO and Motor sat
    pg.locator(".ov-phase", has_text="AUTO").click()
    pg.locator(".ov-row[data-row^='c:'] .ov-phase").first.click(modifiers=["Control"])
    pg.wait_for_function("(window.__sv.state().stripSel?.iv || []).length === 3")
    assert "Mode = AUTO ∧ Motor sat" in pg.inner_text(".ov-seltext")
    pg.click(".ov-save")
    pg.wait_for_function("(window.__sv.state().ws.conditions || []).length === 2")
    c = S(pg, "s.ws.conditions[1]")
    assert c["text"] == 'Mode == "AUTO" and (Motor3 > 1990)'
    pg.wait_for_function("(() => { const s = window.__sv.state(); const r = s.condResults[s.ws.conditions[1].id]; return r && Object.values(r)[0].count === 3; })()")
    # a row's menu: remove it
    pg.locator(".ov-label", has_text="Motor sat").click()
    pg.locator(".menu.ctx button", has_text="Remove the row").click()
    pg.wait_for_function("(window.__sv.state().ws.overviewRows || []).length === 1")
