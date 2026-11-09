"""
26.U5: per-signal tolerances in Compare - a signal's own tolerance under its comparison (empty: every
signal's, greyed), "leave out", and a tolerances file signalviewer-cli compare reads (saved, opened).
"""
import json

import pytest

pytest.importorskip("playwright.sync_api")
from test_template_tabs import pg  # noqa: E402,F401


def _row(pg, name):
    return pg.locator(".sim-row", has_text=name).first


def test_a_signal_has_its_own_tolerance_saved_for_the_cli(pg, tmp_path):
    pg.locator(".examples-line button", has_text="three car runs").click()
    pg.wait_for_function("document.querySelectorAll('.run-head').length === 3")
    pg.click("[aria-label='Compare runs']")
    pg.wait_for_selector(".sim-row", timeout=30000)
    pg.locator(".sim-settings-toggle").click()
    pg.locator(".cmp-panel > .tol-fields .afield", has_text="Tolerance (±)").locator("input").fill("2")
    pg.wait_for_selector(".sim-row .sim-pass", timeout=30000)
    _row(pg, "Speed").click()
    own = pg.locator(".tol-signal")
    own.wait_for(timeout=20000)
    field = own.locator(".afield", has_text="Tolerance (±)").locator("input")
    assert field.input_value() == "" and field.get_attribute("placeholder") == "2"     # every signal's, greyed
    field.fill("1000")                                                                  # Speed's own: it passes
    pg.wait_for_function("() => { const r = [...document.querySelectorAll('.sim-row')].find(x => x.textContent.includes('Speed'));"
                         " return r && r.querySelector('.sim-own') && r.querySelector('.sim-pass'); }", timeout=30000)
    assert pg.locator(".cmp2 .pf.bad").count() == 0                                    # the detail follows
    st = pg.evaluate("window.__sv.state().compareTol")
    assert st["default"] == {"abs": 2} and list(st["signals"].values()) == [{"abs": 1000}]
    # leave another out of pass / fail
    rpm = _row(pg, "RPM")
    rpm.click()
    pg.locator(".tol-signal .acheck input").check()
    pg.wait_for_function("() => { const r = [...document.querySelectorAll('.sim-row')].find(x => x.textContent.includes('RPM'));"
                         " return r && r.querySelector('.sim-skip') && !r.querySelector('.sim-pass, .sim-fail'); }", timeout=30000)
    # saved as the command line's file, cleared, opened again
    path = str(tmp_path / "car_tol.json")
    pg.locator(".cmp-panel button", has_text="Save tolerances…").click()
    _pick(pg, path)
    pg.wait_for_function("document.querySelector('.toast') && document.querySelector('.toast').textContent.includes('signalviewer-cli')")
    saved = json.load(open(path, encoding="utf-8"))
    assert saved["default"] == {"abs": 2.0} and sorted(v.get("skip", False) for v in saved["signals"].values()) == [False, True]
    pg.locator(".cmp-panel button", has_text="Clear the tolerances").click()
    pg.wait_for_function("!document.querySelector('.sim-row .sim-pass')", timeout=30000)
    pg.locator(".cmp-panel button", has_text="Open tolerances…").click()
    _pick(pg, path)
    pg.wait_for_selector(".sim-row .sim-own", timeout=30000)
    assert pg.evaluate("window.__sv.state().compareTol.default.abs") == 2


def _pick(pg, path):
    """Answer the app's file dialog with `path` (the dialog itself is tested elsewhere)."""
    pg.wait_for_function("!!window.__sv.state().picker")
    pg.evaluate("p => { const k = window.__sv.state().picker; window.__sv.setState({ picker: null }); k.resolve(p); }", path)
