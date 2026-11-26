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

sys.path.insert(0, os.path.dirname(__file__))
from test_features import set_language  # noqa: E402  (CC1: the language is chosen in Settings)

pw = pytest.importorskip("playwright.sync_api")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(tmp_path, browser, **extra_env):
    home = tmp_path / "home"
    home.mkdir()
    port = _free_port()
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), **extra_env)
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "run.py"), "--port", str(port), "--no-open"],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(url, timeout=1)
            break
        except Exception:
            time.sleep(0.25)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(url)
    pg.wait_for_selector(".app")
    yield pg, str(home)
    ctx.close()
    proc.terminate()
    assert not errors, errors


@pytest.fixture()
def fresh(tmp_path, browser):
    yield from _start(tmp_path, browser)


@pytest.fixture()
def packaged(tmp_path, browser):
    """A new user of a package: its examples folder without the recordings (svcore/example_data writes them)."""
    import shutil
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    from svcore.example_data import ignore_generated
    src, shipped = os.path.join(ROOT, "examples"), tmp_path / "examples"
    shutil.copytree(src, shipped, ignore=ignore_generated(src))
    assert not (shipped / "copter_flight.bin").exists()
    yield from _start(tmp_path, browser, SV_EXAMPLES=str(shipped))


def test_first_run(fresh):
    pg, home = fresh
    # the welcome screen with its examples, nothing open
    pg.locator(".examples-line").first.wait_for()          # one line per area since the review
    assert pg.evaluate("window.__sv.state().runs.length") == 0
    # the template library has no error line (F14)
    pg.locator(".more-tabs").click()                                     # U9: opening a view: "+ ▾"
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
    set_language(pg, "he")
    pg.wait_for_function("document.documentElement.dir === 'rtl'")
    set_language(pg, "en")
    pg.wait_for_function("document.documentElement.dir === 'ltr'")


@pytest.mark.parametrize("example", ["flight", "twoFlights", "car", "ardupilot"])
def test_each_example_opens_ready(fresh, example):
    """T48: an example opens with its view applied - for a new user too (FR11: from its card, or Help -> Examples)."""
    from test_features import open_example
    pg, _ = fresh
    pg.wait_for_selector(".ex-card")
    open_example(pg, example)
    pg.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.length || (p.objects || []).length))",
                         timeout=30000)


def test_a_package_writes_the_examples_recordings_on_first_use(packaged):
    """Owner, 2026-11-18: the packages carry no example recordings; a card writes its files (once per version, in
    ~/.signalviewer/examples) and opens them as before - a flight log, and a folder summed up in Sweeps."""
    pg, home = packaged
    pg.locator(".ex-card[data-example='ardupilot']").click()
    pg.wait_for_function("window.__sv.state().runs.some((r) => r.format === 'bin')", timeout=60000)
    path = pg.evaluate("window.__sv.state().runs[0].path")
    assert path.startswith(os.path.join(home, ".signalviewer", "examples")) and os.path.getsize(path) > 100_000, path
    pg.locator(".brand").click()                                        # back to the welcome screen
    pg.locator(".ex-card[data-example='monteCarlo']").click()          # CC16: the Monte-Carlo folder
    pg.wait_for_selector(".sw-steps", timeout=60000)                    # the folder's table in Sweeps
    made = os.path.join(os.path.dirname(path), "simulation", "montecarlo")
    assert len([f for f in os.listdir(made) if f.endswith(".csv")]) == 24 and os.path.isfile(os.path.join(made, "measures.json"))
