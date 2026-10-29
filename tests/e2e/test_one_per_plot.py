"""Several selected signals, one into each plot: a true position's X, Y, Z each in a plot of its own,
then the flight computer's X, Y, Z one into each of those plots - paired by the part of the name that
differs, else by order.

    python -m pytest tests/e2e/test_one_per_plot.py -q
"""
import os

import numpy as np
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, _csv, clear_plots, env, menu_item, open_files, pg, sig  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _nav(pg):
    t = np.arange(0, 10, 0.05)
    p = os.path.join(pg.env["data"], "nav.csv")
    if not os.path.exists(p):
        _csv(p, ["Time", "TruePos_X", "TruePos_Y", "TruePos_Z", "NavPos_X", "NavPos_Y", "NavPos_Z", "Est_N", "Est_E", "Est_D"],
             [t, t, 2 * t, -t, t + .1, 2 * t + .1, -t + .1, t + .2, 2 * t + .2, -t + .2])
    yield


def _pick(pg, *names):
    pg.fill(".filter input", "")
    for i, n in enumerate(names):
        sig(pg, n).click(modifiers=["Control"])
    pg.wait_for_function(f"window.__sv.state().listSel.length === {len(names)}")


def _plots(pg):
    return S(pg, "s.ws.tabs.find(t => t.id === s.ws.activeTab).plots.map(p => p.signals.map(x => x.sig.split('/')[1]))")


def test_each_in_a_new_plot_then_one_into_each_by_name(pg):
    open_files(pg, "nav.csv")
    _pick(pg, "TruePos_X", "TruePos_Y", "TruePos_Z")
    pg.click(".pick-more")
    menu_item(pg, "Each in a new plot")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.filter(p => p.signals.length).length === 3")
    assert _plots(pg) == [["TruePos_X"], ["TruePos_Y"], ["TruePos_Z"]]
    # the flight computer's, picked in another order: still X with X
    _pick(pg, "NavPos_Z", "NavPos_X", "NavPos_Y")
    pg.click(".pick-more")
    menu_item(pg, "One into each plot of this tab (3)")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.every(p => p.signals.length === 2)")
    assert _plots(pg) == [["TruePos_X", "NavPos_X"], ["TruePos_Y", "NavPos_Y"], ["TruePos_Z", "NavPos_Z"]]
    assert "by name" in pg.locator(".toast").last.inner_text()
    pg.locator(".toast").last.get_by_role("button", name="Undo").click()        # one undo step
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.every(p => p.signals.length === 1)")


def test_names_that_do_not_pair_go_in_order_and_extra_ones_get_new_plots(pg):
    open_files(pg, "nav.csv")
    _pick(pg, "TruePos_X", "TruePos_Y")
    sig(pg, "TruePos_X").click(button="right")
    menu_item(pg, "Each in a new plot")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.filter(p => p.signals.length).length === 2")
    _pick(pg, "Est_N", "Est_E", "Est_D")                                     # N/E/D against X/Y: by order
    sig(pg, "Est_N").click(button="right")
    menu_item(pg, "One into each plot of this tab (2)")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.filter(p => p.signals.length).length === 3")
    assert _plots(pg)[:3] == [["TruePos_X", "Est_N"], ["TruePos_Y", "Est_E"], ["Est_D"]]
    text = pg.locator(".toast").last.inner_text()
    assert "in order" in text and "1 more in new plots" in text


def _nav_fault(pg):
    """True and flight-computer position with a flight mode; the computer's X drifts off in AUTO."""
    p = os.path.join(pg.env["data"], "nav_fault.csv")
    if not os.path.exists(p):
        t = np.arange(0, 90, 0.05)
        r = np.random.default_rng(2)
        tx, ty, tz = 20 * np.sin(t / 9), 15 * np.cos(t / 7), -30 - 5 * np.sin(t / 5)
        nx = tx + r.normal(0, .3, len(t)) + np.where((t > 40) & (t < 55), 1.5 * np.sin((t - 40) / 15 * np.pi), 0)
        mode = np.where(t < 15, "TAKEOFF", np.where(t < 75, "AUTO", "LAND"))
        with open(p, "w") as f:
            f.write("Time,Mode,TruePos_X,TruePos_Y,TruePos_Z,NavPos_X,NavPos_Y,NavPos_Z\n")
            for i in range(len(t)):
                f.write(f"{t[i]:.2f},{mode[i]},{tx[i]:.4f},{ty[i]:.4f},{tz[i]:.4f},{nx[i]:.4f},"
                        f"{ty[i] + r.normal(0, .3):.4f},{tz[i] + r.normal(0, .5):.4f}\n")


def test_the_error_in_every_plot_with_two_lines(pg):
    _nav_fault(pg)
    open_files(pg, "nav_fault.csv")
    _pick(pg, "TruePos_X", "TruePos_Y", "TruePos_Z")
    pg.click(".pick-more"); menu_item(pg, "Each in a new plot")
    _pick(pg, "NavPos_X", "NavPos_Y", "NavPos_Z")
    pg.click(".pick-more"); menu_item(pg, "One into each plot of this tab (3)")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.every(p => p.signals.length === 2)")
    pg.locator(".plot-more").first.click()
    menu_item(pg, "Error in every plot with two lines (3)")
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 2 && window.__sv.state().ws.activeTab === window.__sv.state().ws.tabs[1].id")
    tab = S(pg, "s.ws.tabs[1]")
    assert tab["name"] == "Errors" and len(tab["plots"]) == 3
    sigs = [p["signals"][0]["sig"].split("/")[1] for p in tab["plots"]]
    assert sigs == ["NavPos_X − TruePos_X", "NavPos_Y − TruePos_Y", "NavPos_Z − TruePos_Z"]
    titles = [p["title"] for p in tab["plots"]]
    assert all(x.startswith("RMS ") for x in titles)
    assert "worst in AUTO" in titles[0] and "worst in" not in titles[1] + titles[2]      # only where it stands out
    assert 40 < S(pg, "s.cursor.t1") < 55                                    # on the largest error: X's drift
    pg.evaluate("window.__sv.setState({ ws: { ...window.__sv.state().ws, activeTab: window.__sv.state().ws.tabs[0].id } })")
    pg.locator(".plot-more").first.click()                                  # the same again: the signals are reused
    menu_item(pg, "Error in every plot with two lines (3)")
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 3")
    assert S(pg, "s.runs.find(r => r.format === 'derived').signals.length") == 3


def test_a_template_takes_the_conditions_to_the_next_flight(pg):
    """Conditions made while looking into one flight go with a template saved from it; opening the
    template on another flight's file (a fresh start, nothing else open) adds them, counted there."""
    import shutil
    from test_conditions import _new, _panel
    demo = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "investigate")
    for f in ("heavy_payload.csv", "light_payload.csv"):
        if not os.path.exists(os.path.join(pg.env["data"], f)):
            shutil.copy(os.path.join(demo, f), os.path.join(pg.env["data"], f))
    open_files(pg, "heavy_payload.csv")
    sig(pg, "Roll").click()
    _panel(pg)
    _new(pg, "Motor3 at limit", "Motor3 > 1990")
    pg.click(".cond-save")
    pg.wait_for_function("(window.__sv.state().ws.conditions || []).length === 1")
    pg.locator("nav.rail button").first.click()                             # back to the files (the template strip)
    pg.locator(".tpl-strip-save").click()
    pg.wait_for_selector(".tpl-editor")
    pg.locator(".tpl-editor input").first.fill("Payload check")
    pg.locator(".tpl-editor .btn.primary").click()
    pg.wait_for_selector(".tpl-details h3:has-text('Payload check')")
    assert "1 conditions" in pg.inner_text(".tpl-details .tpl-conds")
    pg.keyboard.press("Escape")
    # a fresh start: nothing open, no conditions - then only the next flight
    rid = S(pg, "s.runs.find(r => r.name === 'heavy_payload.csv').id")
    pg.evaluate(f"fetch('/api/runs/{rid}', {{method: 'DELETE'}})")
    pg.evaluate("window.__sv.setState({ runs: [], ws: { ...window.__sv.state().ws, conditions: [] }, condResults: {} })")
    open_files(pg, "light_payload.csv", clear=False)
    pg.click(".areabar [aria-label='Templates']"); menu_item(pg, "Open a template")
    pg.locator(".tpl-item", has_text="Payload check").click()
    pg.wait_for_selector(".tpl-details .btn.primary:not([disabled])")
    pg.locator(".tpl-details .btn.primary").click()
    pg.wait_for_function("(window.__sv.state().ws.conditions || []).some(c => c.name === 'Motor3 at limit')")
    assert "1 conditions added" in pg.locator(".toast").last.inner_text()
    pg.wait_for_function("Object.values(window.__sv.state().condResults).length === 1")
    light = S(pg, "s.runs.find(r => r.name === 'light_payload.csv').id")
    assert S(pg, f"Object.values(s.condResults)[0]['{light}'].count") == 0      # the light flight: never at the limit
