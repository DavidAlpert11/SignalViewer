"""AU1-AU4: the *Found in this file* line - what the app does by itself from the signal names, one click each:
command / response pairs, truth vs navigation errors (Compare objects… opened on 6dof and ins), modes as bands,
sensors in copies; the file's menu lists the same; *Why?* names the matched signals; Help -> Name your signals.

    python -m pytest tests/e2e/test_found.py -q
"""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg  # noqa: E402,F401

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def run(pg):
    shutil.copy(os.path.join(ROOT, "examples", "automations", "platform_run.csv"), pg.env["data"])
    open_files(pg, "platform_run.csv")
    pg.locator(".found-bar").wait_for()
    return pg


def test_found_line_offers_every_find(run):
    pg = run
    bar = pg.locator(".found-bar")
    assert "Found in platform_run.csv" in bar.inner_text()
    assert "2 objects found: 6dof, ins" in bar.inner_text()
    for chip in ("pairs", "truthnav", "states", "copies", "effort"):
        assert bar.locator(f".found-{chip}").count() == 1, chip
    assert "3 command / response pairs" in bar.locator(".found-pairs").inner_text()
    bar.locator(".found-why").click()                                  # Why?: the matched names
    assert "ctrl.roll_cmd → ctrl.roll" in bar.locator(".found-why-pairs").inner_text()
    assert "6dof ↔ ins" in bar.locator(".found-why-truthnav").inner_text()
    assert "imu[0] / imu[1]" in bar.locator(".found-why-copies").inner_text()
    bar.locator(".found-names").click()                                # ... and the page of the names
    pg.locator(".dialog.naming").wait_for()
    assert pg.locator(".naming-row").count() == 8
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".dialog.naming", state="detached")


def test_pairs_chip_plots_them_and_goes(run):
    pg = run
    pg.locator(".found-bar .found-pairs").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.length === 3 && t.plots.every((p) => p.signals.length === 2))")
    pg.wait_for_selector(".found-bar .found-pairs", state="detached")         # used: its chip goes
    assert pg.locator(".found-bar .found-states").count() == 1              # the others stay


def test_truth_vs_navigation_opens_compare_on_them(run):
    pg = run
    pg.locator(".found-bar .found-truthnav").click()
    pg.wait_for_selector(".cmpobj")                                          # Compare objects… open
    geo = "s.ws.tabs.flatMap((t) => t.plots).find((p) => (p.mode === 'geo' || p.mode === '3d'))"
    assert sorted(o["name"] for o in S(pg, f"{geo}.objects")) == ["6dof", "ins"]
    ref = pg.locator(".cmpobj .cmpobj-ref").evaluate("(e) => e.options[e.selectedIndex].text")
    assert ref == "6dof"                                                     # the truth is the reference
    pg.locator(".cmpobj .rel-errors").click()                                 # its errors over time
    pg.wait_for_selector(".cmpobj", state="detached")
    pg.wait_for_function("window.__sv.state().runs.some((r) => r.format === 'derived' && r.signals.length >= 3)")


def test_modes_and_copies(run):
    pg = run
    pg.locator(".found-bar .found-states").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.some((s) => s.sig.endsWith('/mode'))))")
    pg.locator(".found-bar .found-copies").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.length === 3 && t.plots.every((p) => p.signals.length === 2 && p.signals[0].sig.includes('imu[0]')))")


def test_hidden_line_is_remembered_and_the_file_menu_still_lists_the_finds(run):
    pg = run
    pg.locator(".found-bar .found-hide").click()
    pg.wait_for_selector(".found-bar", state="detached")
    pg.wait_for_function("window.__sv.state().objSuggestHidden.length === 1")
    pg.evaluate("window.__sv.setState({ objSuggestHidden: [] })")           # this run of the app forgets...
    pg.wait_for_timeout(300)
    assert pg.locator(".found-bar").count() == 0                            # ... the name is remembered
    pg.locator(".run-head", has_text="platform_run.csv").first.click(button="right")
    pg.locator(".menu.ctx button", has_text="Found in this file").first.hover()
    pg.locator(".menu.ctx.sub button", has_text="command / response pairs").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.length === 3 && t.plots.every((p) => p.signals.length === 2))")
