"""Investigation step 4 on the Investigate demo (examples/investigate, a known answer): what changed
first around the roll error, and the lag between motor 3 and the roll.

    python -m pytest tests/e2e/test_what_changed.py -q
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


def _around_first_error(pg):
    open_files(pg, "heavy_payload.csv")
    pg.locator(".sig").filter(has=pg.get_by_text("Roll", exact=True)).first.click()   # Roll, not DesRoll
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.some(x => x.sig.endsWith('/Roll'))")
    pg.evaluate("window.__sv.setState({ cursor: { ...window.__sv.state().cursor, on: true, dual: true, t1: 38.46, t2: 39.24, active: 1 } })")
    pg.wait_for_selector(".sel-bar:not([hidden])")
    pg.click(".sel-changed")
    pg.wait_for_selector(".wc-section")
    pg.select_option(".wc-scope", "all")
    pg.wait_for_selector(".wc-row")


def test_what_changed_first_finds_the_built_order(pg):
    _around_first_error(pg)
    names = [n.strip() for n in pg.locator(".wc-row .wc-name").all_inner_texts()]
    assert names[0] == "Wind" and names[1] == "Vibe_Z"
    assert names.index("Motor3") < names.index("Roll")
    assert "not proof of cause" in pg.inner_text(".wc-warn")
    assert S(pg, "Object.keys(s.changeMarks || {}).length") >= 4           # the dashed lines
    pg.locator(".wc-head .iconbtn").click()                                 # closing takes them away
    pg.wait_for_function("window.__sv.state().changeMarks === null")


def test_lag_motor3_to_roll_and_show_aligned(pg):
    _around_first_error(pg)
    pg.locator(".wc-row", has_text="Motor3").locator("input[type=checkbox]").check()
    pg.locator(".wc-row", has_text="Roll").first.locator("input[type=checkbox]").check()
    pg.click(".wc-lag")
    pg.wait_for_selector(".wc-lag-out p")
    text = pg.inner_text(".wc-lag-out p")
    assert "follows Motor3 by" in text
    ms = float(text.split("by ")[1].split(" ms")[0])
    assert 80 <= ms <= 180
    pg.click(".wc-align")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.some(x => x.sig.endsWith('/Roll') && x.tOffset < 0)")
    assert S(pg, "s.ws.tabs[0].plots[0].signals.some(x => x.sig.endsWith('/Motor3'))")
