"""
T52: a NEW user - an empty home folder, no ~/.signalviewer at all. The other e2e files reuse a
profile that earlier tests filled (templates folder, recent files...), so first-run problems were
invisible: F14 ("The templates folder is not available" on a first run) was found by hand.

One server per test, each with its own empty home; any page error or console error fails.
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


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def fresh(tmp_path):
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
        pg = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US").new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.goto(url)
        pg.wait_for_selector(".app")
        yield pg, str(home)
        browser.close()
    proc.terminate()
    assert not errors, errors


def test_first_run(fresh):
    pg, home = fresh
    # the welcome screen with its examples, nothing open
    pg.locator(".examples-line").wait_for()
    assert pg.evaluate("window.__sv.state().runs.length") == 0
    # the template library has no error line (F14)
    pg.locator("button", has_text="Templates").first.click()
    pg.get_by_text("Open a template or collection…").click()
    pg.locator(".tpl-lib").wait_for()
    assert pg.locator(".tpl-lib .hint.err").count() == 0, pg.locator(".tpl-lib .hint.err").all_inner_texts()
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".scrim", state="detached")
    # the file dialog opens (in the home folder), takes the keyboard (F18), lists the places (T24)
    pg.keyboard.press("Control+o")
    pg.wait_for_function("document.querySelector('.crumbs input') && document.querySelector('.crumbs input').value !== ''")
    pg.locator(".fs-places h3", has_text="This computer").wait_for(timeout=10000)   # the places come a moment later (a bare count was flaky)
    assert pg.locator(".fs-places h3", has_text="This computer").count() == 1
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".scrim", state="detached")
    # Hebrew and back
    pg.get_by_role("button", name="עברית").click()
    pg.wait_for_function("document.documentElement.dir === 'rtl'")
    pg.get_by_role("button", name="English").click()
    pg.wait_for_function("document.documentElement.dir === 'ltr'")


@pytest.mark.parametrize("example", ["a drone flight", "the same mission flown twice", "three car runs to compare", "an ArduPilot flight log"])
def test_each_example_opens_ready(fresh, example):
    """T48: an example opens with its view applied - for a new user too."""
    pg, _ = fresh
    pg.locator(".examples-line button", has_text=example).click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.length || (p.objects || []).length))",
                         timeout=30000)
