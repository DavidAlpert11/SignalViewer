"""T41: the fleet panel - add a folder of flight logs, search by a finding and a number, the trend,
open a flight at a finding."""
import os
import subprocess
import sys

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg  # noqa: E402,F401

TOOLS = os.path.join(os.path.dirname(__file__), "..", "..", "tools")


@pytest.fixture(scope="module")
def flights(env):
    d = os.path.join(env["data"], "flights")
    if not os.path.isdir(d):
        os.makedirs(d)
        subprocess.run([sys.executable, os.path.join(TOOLS, "make_test_bin.py"), os.path.join(d, "f1.bin"),
                        "--seconds", "20", "--imu-hz", "50"], check=True, capture_output=True)
        subprocess.run([sys.executable, os.path.join(TOOLS, "make_test_tlog.py"), os.path.join(d, "f2.tlog"),
                        "--seconds", "20"], check=True, capture_output=True)
    return d


def test_fleet_search_trend_and_open_at_a_finding(pg, flights):
    pg.click("nav.rail [aria-label='Fleet']")
    pg.click(".fleet-btns button:has-text('Add a folder…')")
    goto_folder(pg, flights)
    pg.click(".dialog button:has-text('Use this folder')")
    pg.wait_for_selector("text=The fleet is up to date.")
    pg.wait_for_selector(".fleet-count:has-text('2 flights')")
    assert pg.inner_text(".fleet-folder").count("2 logs") == 1

    pg.select_option(".fleet-row select[aria-label='Level']", "error")                # only the .bin has errors
    pg.wait_for_selector(".fleet-count:has-text('1 flight')")
    assert pg.locator(".fleet-name").all_inner_texts() == ["f1.bin"]
    pg.select_option(".fleet-row select[aria-label='Level']", "")
    pg.wait_for_selector(".fleet-count:has-text('2 flights')")                       # wait for the NEW list, not the last one

    pg.select_option(".fleet-row select[aria-label='Number']", "vibration.max")      # a number: the trend appears
    pg.wait_for_selector(".fleet-trend circle >> nth=1", state="attached")
    vals = pg.evaluate("fetch('/api/fleet/trend?key=vibration.max').then(r => r.json()).then(j => j.points.map(p => [p.name, p.value]))")
    hi = max(v for n, v in vals if n == "f1.bin")
    lo = max(v for n, v in vals if n == "f2.tlog")
    assert hi > lo
    pg.fill(".fleet-limit", str((hi + lo) / 2))                                    # between the two: the .bin only
    pg.wait_for_selector(".fleet-count:has-text('1 flight')")
    pg.wait_for_function("document.querySelectorAll('.fleet-trend circle.over').length === 1")

    pg.click(".fleet-line:has-text('f1.bin')")
    pg.click(".fleet-findings li >> nth=0 >> button:has-text('Open here')")
    pg.wait_for_function("window.__sv.state().runs.some(r => r.path.endsWith('f1.bin'))")
    pg.wait_for_function("window.__sv.state().panel === 'log' && window.__sv.state().cursor.on")
