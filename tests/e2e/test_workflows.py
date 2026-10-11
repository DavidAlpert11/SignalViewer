"""
End-to-end tests: one per workflow in section 2 of the requirements document.
They drive the real UI in a headless browser against a real server.

    pip install -r requirements-dev.txt && python -m playwright install chromium
    python -m pytest tests/e2e -q
Set SV_CHROMIUM=/path/to/chrome to use an existing browser binary.
"""
import json, os, socket, subprocess, sys, time, urllib.request

import numpy as np
import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _write_runs(folder):
    t = np.arange(0, 30, 0.01)
    f = lambda tt: 20 + 10 * np.tanh(tt - 5) - 8 * np.tanh(tt - 20)
    paths = []
    for name, sh, g in (("run_a", 0, 1), ("run_b", 0.0, 1.01), ("run_c", 0.6, 0.9)):
        p = os.path.join(folder, f"{name}.csv")
        np.savetxt(p, np.column_stack([t, g * f(t - sh), np.floor(t / 6)]), delimiter=",", header="Time,Speed,Gear", comments="")
        paths.append(p)
    return paths


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    home = tmp_path_factory.mktemp("home")
    data = tmp_path_factory.mktemp("data")
    paths = _write_runs(str(data))
    port = _free_port()
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "run.py"), "--port", str(port), "--no-open"],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(url, timeout=1); break
        except Exception:
            time.sleep(0.25)
    yield {"url": url, "data": str(data), "paths": paths, "home": str(home)}
    proc.terminate()


@pytest.fixture()
def page(server):
    with pw.sync_playwright() as p:
        kw = {"args": ["--no-sandbox"]}
        if os.environ.get("SV_CHROMIUM"):
            kw["executable_path"] = os.environ["SV_CHROMIUM"]
        browser = p.chromium.launch(**kw)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        # fresh state for every test: no autosaved workspace, no open files
        auto = os.path.join(server["home"], ".signalviewer", "autosave.json")
        if os.path.exists(auto):
            os.remove(auto)
        for r in json.loads(urllib.request.urlopen(server["url"] + "/api/runs").read()):
            if r["format"] != "derived":
                urllib.request.urlopen(urllib.request.Request(f"{server['url']}/api/runs/{r['id']}", method="DELETE"))
        pg.goto(server["url"])
        pg.wait_for_selector(".app")
        yield pg
        assert not errors, errors
        browser.close()


def _goto_folder(pg, folder):
    # like a person: wait until the dialog shows its first folder, then type a path
    pg.wait_for_function("document.querySelector('.crumbs input') && document.querySelector('.crumbs input').value !== ''")
    pg.fill(".crumbs input", folder); pg.press(".crumbs input", "Enter")
    pg.wait_for_function(f"document.querySelector('.crumbs input').value === {json.dumps(folder)}")


def _open(pg, folder, names):
    pg.keyboard.press("Control+o")
    _goto_folder(pg, folder)
    row = lambda n: pg.locator(".dialog .dialog-body .fs-row", has_text=n).first
    try:
        row(names[0]).wait_for(timeout=8000)
    except Exception:
        pg.screenshot(path=os.path.join(os.environ.get("SV_E2E_SHOTS", "/tmp"), "e2e_fail.png"))
        print("DIALOG:", pg.locator(".dialog").count(), pg.locator(".crumbs input").input_value() if pg.locator(".crumbs input").count() else None,
              pg.locator(".dialog .dialog-body .fs-row").all_inner_texts()[:5])
        raise
    for i, n in enumerate(names):
        row(n).click(modifiers=["Control"] if i else [])
    pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function(f"document.querySelectorAll('.run-head').length >= {len(names)}")


def _save_as(pg, folder, name):
    _goto_folder(pg, folder)
    pg.fill(".savename input", name); pg.click(".dialog-foot .btn.primary")


def test_quick_view(page, server):
    """Open a file (nothing is plotted until a signal is chosen), plot it, read a value."""
    _open(page, server["data"], ["run_a.csv"])
    page.wait_for_timeout(300)
    assert page.locator(".plot .chip").count() == 0
    page.locator(".sig", has_text="Speed").click()
    page.wait_for_selector(".plot .chip")
    page.keyboard.press("Space")
    page.wait_for_function("document.querySelector('.plot .chip .val') !== null")
    assert float(page.locator(".plot .chip .val").first.inner_text().replace(",", "")) > 0


def test_compare_runs(page, server):
    """Three runs, baseline A, tolerance: B passes, C fails; time alignment improves C."""
    _open(page, server["data"], ["run_a.csv", "run_b.csv", "run_c.csv"])
    page.click("[aria-label='Compare']")
    page.click(".sim-settings-toggle")
    page.locator(".side .arow input").first.fill("1")
    page.wait_for_selector(".sim-row")
    page.locator(".sim-row", has_text="Speed").click()
    page.wait_for_selector("table.cmp2 tbody")
    rows = page.locator("table.cmp2 tbody")
    assert rows.count() == 2
    assert "ok" in rows.nth(0).locator(".pf").get_attribute("class")
    corr_before = float(rows.nth(1).locator("td").nth(3).inner_text())
    rows.nth(1).locator("button").click()
    page.wait_for_timeout(1500)
    assert float(page.locator("table.cmp2 tbody").nth(1).locator("td").nth(3).inner_text()) > corr_before


def test_analysis_derived_signal(page, server):
    """Derivative from the Analysis panel appears in the plot and survives as a formula."""
    _open(page, server["data"], ["run_a.csv"])
    page.locator(".sig", has_text="Speed").click()
    page.click("[aria-label='Analysis']")
    page.click("text=Create signal")
    page.wait_for_selector(".plot .chip:has-text('derivative(')")
    assert page.locator(".dsig-name", has_text="derivative(").count() >= 1


def test_live_mode(page, server):
    """Rows appended to an open file appear while live mode is on."""
    p = os.path.join(server["data"], "live.csv")
    with open(p, "w") as f:
        f.write("Time,V\n" + "".join(f"{i * 0.1:.1f},{i}\n" for i in range(50)))
    _open(page, server["data"], ["live.csv"])
    page.click(".topbar .btn:has-text('Live')")
    with open(p, "a") as f:
        f.write("".join(f"{i * 0.1:.1f},{i}\n" for i in range(50, 80)))
    page.wait_for_function("document.querySelector('.status').innerText.includes('80 samples')", timeout=8000)


def test_share_report_and_session(page, server, tmp_path):
    """Interactive HTML report and a session file, then reopen the session."""
    _open(page, server["data"], ["run_a.csv"])
    page.locator(".sig", has_text="Speed").click()
    page.wait_for_selector(".plot .chip")
    page.click("[aria-label='Report']")
    page.click("text=Create interactive HTML")
    _save_as(page, str(tmp_path), "report.html")
    page.wait_for_selector(".toast:has-text('Saved')", timeout=30000)
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "sv-data" in html and "uPlot" in html
    page.keyboard.press("Control+s")
    _save_as(page, str(tmp_path), "work")
    page.wait_for_timeout(800)
    assert (tmp_path / "work.svsession").exists()
    page.keyboard.press("Control+Shift+O")
    _goto_folder(page, str(tmp_path))
    page.locator(".dialog .dialog-body .fs-row", has_text="work.svsession").click(); page.click(".dialog-foot .btn.primary")
    page.wait_for_selector(".toast:has-text('Session opened')")
    assert page.locator(".plot .chip").count() == 1
