"""
U1 (owner, 2026-11-07): choose which tabs a template opens. A template may name its default tabs
(`defaultTabs`): opened right after a file loads with no question, the rest offered by "+N more"
beside the tab bar's +. A chip of a template with several tabs asks which tabs (unless Settings
says to open the default tabs at once); the library pre-checks the default tabs, with All / None.

One server per test, each with its own empty home; any page error fails.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REVIEW_TABS = 10            # ArduPilot · Full review: Attitude, Rates, Step response, ... Flight


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def pg(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    port = _free_port()
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "run.py"), "--port", str(port), "--no-open"],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(url, timeout=1)
            break
        except Exception:
            time.sleep(0.25)
    with pw.sync_playwright() as p:
        kw = {"args": ["--no-sandbox"]}
        if os.environ.get("SV_CHROMIUM"):
            kw["executable_path"] = os.environ["SV_CHROMIUM"]
        browser = p.chromium.launch(**kw)
        page = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US").new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector(".app")
        yield page
        browser.close()
    proc.terminate()
    assert not errors, errors


def tab_names(pg):
    return pg.evaluate("window.__sv.state().ws.tabs.map((t) => t.name)")


def open_ardupilot_example(pg):
    pg.locator(".examples-line button", has_text="ArduPilot").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.length))", timeout=30000)
    pg.wait_for_selector(".more-tabs.has", timeout=10000)                 # U9: the views menu "▾" with their number


def test_auto_open_takes_the_default_tabs_and_offers_the_rest(pg):
    open_ardupilot_example(pg)
    assert tab_names(pg) == ["Attitude", "Flight"]                 # the built-in review's defaultTabs
    more = pg.locator(".more-tabs")
    assert more.inner_text().strip() == str(REVIEW_TABS - 2)
    assert more.get_attribute("aria-label").startswith(f"+{REVIEW_TABS - 2} more from ArduPilot")
    more.click()
    assert pg.locator(".menu.ctx button", has_text="Open a template or collection").count() == 1   # one menu for views
    pg.locator(".menu.ctx button", has_text="Vibration").first.click()
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 3", timeout=20000)
    assert tab_names(pg)[-1] == "Vibration"
    assert pg.evaluate("window.__sv.state().ws.moreTabs[0].tabs.length") == REVIEW_TABS - 3
    # Undo takes the tab back AND puts it back on offer (one step)
    pg.evaluate("window.__sv.state().undo()")
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 2")
    assert pg.evaluate("window.__sv.state().ws.moreTabs[0].tabs.length") == REVIEW_TABS - 2
    # Open all: every tab, and the offer goes
    pg.locator(".more-tabs").click()
    pg.locator(".menu.ctx button", has_text=f"Open all {REVIEW_TABS - 2}").click()
    pg.wait_for_function(f"window.__sv.state().ws.tabs.length === {REVIEW_TABS}", timeout=30000)
    pg.wait_for_selector(".more-tabs.has", state="detached")
    # Hebrew / RTL: the offer is translated and stays beside the tabs
    pg.evaluate("window.__sv.state().undo()")
    pg.wait_for_selector(".more-tabs.has")
    pg.get_by_role("button", name="עברית").click()
    pg.wait_for_function("document.documentElement.dir === 'rtl'")
    assert "עוד" in pg.locator(".more-tabs").get_attribute("aria-label")


def test_chip_asks_which_tabs_unless_settings_say_defaults(pg):
    open_ardupilot_example(pg)
    pg.locator(".tpl-strip-fold").click()                          # U7: folded once something is plotted
    pg.locator(".tpl-chips .chipbtn", has_text="Rates (PID)").click()
    dlg = pg.locator(".tab-choice")
    dlg.wait_for(timeout=10000)
    boxes = dlg.locator("input[type=checkbox]")
    assert boxes.count() == 2 and all(boxes.nth(i).is_checked() for i in range(2))   # no defaultTabs: all, as before
    dlg.locator(".linkbtn", has_text="None").click()
    assert dlg.locator(".btn.primary").is_disabled()
    dlg.locator("li", has_text="Step response").locator("input").check()
    dlg.locator(".btn.primary").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 3", timeout=20000)
    assert tab_names(pg)[-1] == "Step response"
    # two templates with tabs left: one button, a section each
    assert pg.locator(".more-tabs").count() == 1
    assert pg.locator(".more-tabs").get_attribute("aria-label").startswith(f"+{REVIEW_TABS - 2 + 1} more tabs")
    # Settings: open the default tabs at once - the chip asks nothing (and it is kept)
    pg.evaluate("window.__sv.setState({ tplTabChoice: 'defaults' })")
    pg.locator(".tpl-chips .chipbtn", has_text="Rates (PID)").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 5", timeout=20000)
    assert pg.locator(".tab-choice").count() == 0


def template_strip(pg):
    """26.U3: with something plotted the template strip is folded to one line - unfold it."""
    fold = pg.locator(".tpl-strip-fold")
    if fold.count() and fold.get_attribute("aria-expanded") != "true":
        fold.click()


def test_library_prechecks_default_tabs(pg):
    open_ardupilot_example(pg)
    template_strip(pg); pg.locator(".tpl-strip-head .linkbtn").click()
    pg.locator(".tpl-lib").wait_for()
    pg.locator(".tpl-item", has_text="ArduPilot · Full review").first.click()
    lst = pg.locator(".tpl-details .tpl-tabs")
    lst.wait_for()
    checked = [lst.locator("li").nth(i).inner_text().split("\n")[0] for i in range(lst.locator("li").count())
               if lst.locator("li").nth(i).locator("input").is_checked()]
    assert checked == ["Attitude", "Flight"] and lst.locator("li").count() == REVIEW_TABS
    assert lst.locator(".tpl-default").count() == 2
    pg.locator(".tpl-details .tpl-tabs-bulk .linkbtn", has_text="All").click()
    assert lst.locator("input:checked").count() == REVIEW_TABS
