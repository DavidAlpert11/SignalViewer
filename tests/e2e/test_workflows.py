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
    page.click("[aria-label='Compare runs']")
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
    page.click("[aria-label='Create signals']")
    page.get_by_role("button", name="Create signal", exact=True).click()
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


def test_file_browser_autocomplete(page, server):
    """T03: type part of a path - suggestions, Tab completes, a chosen file opens;
    breadcrumbs go up; letters typed on the list filter it."""
    data = server["data"]
    sub = os.path.join(data, "flights_2026")
    os.makedirs(sub, exist_ok=True)
    np.savetxt(os.path.join(sub, "hover_test.csv"), np.column_stack([np.arange(10.0), np.arange(10.0)]),
               delimiter=",", header="Time,Alt", comments="")
    pg = page
    pg.keyboard.press("Control+o")
    pg.wait_for_function("document.querySelector('.crumbs input') && document.querySelector('.crumbs input').value !== ''")
    box = ".crumbs input"
    pg.fill(box, os.path.join(data, "fli"))
    pg.wait_for_selector(".fs-complete li")
    assert "flights_2026" in pg.locator(".fs-complete").inner_text()
    pg.press(box, "Tab")                       # one match: the folder opens, typing goes on inside it
    pg.wait_for_function(f"document.querySelector('.crumbs input').value.startsWith({json.dumps(sub)})")
    pg.locator(".dialog .dialog-body .fs-row", has_text="hover_test.csv").wait_for()
    # breadcrumbs: the parent folder is one click away
    pg.locator(".fs-crumb .linkbtn", has_text=os.path.basename(data)).click()
    pg.wait_for_function(f"document.querySelector('.crumbs input').value === {json.dumps(data)}")
    # type-to-filter on the list
    pg.locator(".dialog .dialog-body .fs-row").first.focus()
    pg.keyboard.type("run_b")
    pg.wait_for_function("(document.querySelector('.fs-filter')?.textContent || '').includes('run_b')")
    names = pg.locator(".dialog .dialog-body .fs-row").all_inner_texts()
    assert len(names) == 1 and "run_b.csv" in names[0]
    pg.keyboard.press("Escape")                # first Esc clears the filter, the dialog stays
    pg.wait_for_function("!document.querySelector('.fs-filter')")
    assert pg.locator(".dialog").count() == 1
    # a full file name + Enter on its suggestion opens it
    pg.fill(box, os.path.join(sub, "hover"))
    pg.wait_for_selector(".fs-complete li")
    pg.press(box, "ArrowDown"); pg.press(box, "Enter")
    pg.wait_for_function("document.querySelectorAll('.run-head').length >= 1")
    assert pg.locator(".run-head", has_text="hover_test").count() == 1


def test_open_an_example_from_the_welcome_screen(page, server):
    """T09: one click on the welcome screen opens the three car runs."""
    page.locator(".examples-line button", has_text="three car runs").click()
    page.wait_for_function("document.querySelectorAll('.run-head').length === 3")
    assert page.locator(".run-head", has_text="run_013").count() == 1


def test_open_the_two_flights_example(page, server):
    """T44: the same mission flown twice - both files open, with the same signals."""
    page.locator(".examples-line button", has_text="flown twice").click()
    page.wait_for_function("document.querySelectorAll('.run-head').length === 2")
    assert page.locator(".run-head", has_text="uav_flight_windy").count() == 1


def test_open_the_ardupilot_example(page, server):
    """T45: the flight-log example opens with the smart-start card - an ArduPilot template and the
    vibration warning from its health check."""
    page.locator(".examples-line button", has_text="ArduPilot").click()
    card = page.locator(".start-card")
    card.wait_for(timeout=20000)
    assert "ArduPilot" in card.locator(".start-tpl b").inner_text()
    assert "warning" in card.locator(".hrow").first.get_attribute("class")


def test_compare_open_files_gives_each_file_its_colour(page, server):
    """F13: a template without stored colours (Compare open files) gave every signal the same
    colour - the runs could not be told apart. Now each file has one colour, the same in every plot."""
    _open(page, server["data"], ["run_a.csv", "run_b.csv", "run_c.csv"])
    page.locator(".tpl-strip .chipbtn", has_text="Compare open files").click()
    page.locator(".dialog .btn.primary", has_text="Open").click()
    page.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.length === 3))")
    plots = page.evaluate("""window.__sv.state().ws.tabs.flatMap((t) => t.plots).filter((p) => p.signals.length)
        .map((p) => p.signals.map((s) => [s.sig.split('/')[0], s.color]))""")
    assert len(plots) >= 2                                  # Speed and Gear
    colour_of_run = {}
    for plot in plots:
        assert len({c for _, c in plot}) == len(plot)       # different colours in each plot
        for run, c in plot:
            assert colour_of_run.setdefault(run, c) == c    # a file keeps its colour across plots


def test_every_tab_is_reachable_with_many_tabs(page, server):
    """F22 (owner): with many tabs the strip scrolls with a hidden scrollbar - the hidden tabs could
    not be reached. Now: an "All tabs" list, the active tab kept in view, Ctrl+PageUp / PageDown,
    the wheel over the strip, and "Go to tab" in the palette."""
    page.set_viewport_size({"width": 1100, "height": 760})
    for _ in range(24):
        page.get_by_role("button", name="New tab").click()
    page.wait_for_function("window.__sv.state().ws.tabs.length === 25")
    active = lambda: page.evaluate("(() => { const w = window.__sv.state().ws; return w.tabs.findIndex((t) => t.id === w.activeTab); })()")
    in_view = lambda: page.evaluate("""(() => { const a = document.querySelector('.tab.active').getBoundingClientRect(),
        s = document.querySelector('.tabs').getBoundingClientRect(); return a.left >= s.left - 1 && a.right <= s.right + 1; })()""")
    assert active() == 24 and in_view()
    page.locator(".tabs-all").click()                       # shown only when the tabs do not fit
    page.locator(".menu.ctx button", has_text="Tab 2").first.click()
    page.wait_for_function("window.__sv.state().ws.tabs.findIndex((t) => t.id === window.__sv.state().ws.activeTab) === 1")
    assert in_view()
    page.keyboard.press("Control+PageUp"); page.keyboard.press("Control+PageUp")      # wraps to the last
    page.wait_for_function("window.__sv.state().ws.tabs.findIndex((t) => t.id === window.__sv.state().ws.activeTab) === 24")
    assert in_view()
    before = page.evaluate("document.querySelector('.tabs').scrollLeft")
    box = page.locator(".tabs").bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + box["height"] / 2); page.mouse.wheel(0, -500)
    page.wait_for_function(f"document.querySelector('.tabs').scrollLeft < {before}")
    page.keyboard.press("Control+k"); page.keyboard.type("go to tab 7"); page.keyboard.press("Enter")
    page.wait_for_function("window.__sv.state().ws.tabs.findIndex((t) => t.id === window.__sv.state().ws.activeTab) === 6")
    # the controls on the right keep their room
    assert page.locator(".search-trigger").bounding_box()["width"] >= 149


def test_plot_menu_closes_like_every_menu(page, server):
    """F17: the plot's ⋯ menu closed only when the mouse entered it and left again - never by Esc
    or a click elsewhere."""
    _open(page, server["data"], ["run_a.csv"])
    page.locator(".sig", has_text="Speed").first.click()
    page.wait_for_selector(".plot .chip")
    menu = page.locator(".plot .menu")
    page.locator(".plot-more").first.click(); menu.wait_for()
    page.keyboard.press("Escape"); menu.wait_for(state="detached")
    page.locator(".plot-more").first.click(); menu.wait_for()
    page.locator(".plot-body").first.click(position={"x": 200, "y": 100}); menu.wait_for(state="detached")


def test_dialogs_take_the_keyboard(page, server):
    """F18: the file dialog left the focus on the button behind it - Esc did nothing until a click,
    and Tab walked through the app behind the scrim. Every modal dialog takes the focus now."""
    inside = "(() => { const d = [...document.querySelectorAll('.scrim > .dialog')].pop(); return !!d && d.contains(document.activeElement); })()"
    page.keyboard.press("Control+o")
    page.wait_for_selector(".scrim > .dialog")
    page.wait_for_function(inside)
    for _ in range(25):
        page.keyboard.press("Tab")
        assert page.evaluate(inside)
    page.keyboard.press("Escape")
    page.wait_for_selector(".scrim", state="detached")
    page.locator("button[aria-label='Clear everything']").click()
    page.wait_for_function(inside)
    page.keyboard.press("Escape")
    page.wait_for_selector(".scrim", state="detached")


def test_opening_an_open_file_reads_it_again(page, server):
    """F19: opening a file that is already open added a second copy without a word. Now it is read
    again from the disk, and "Open another copy" is offered."""
    _open(page, server["data"], ["run_a.csv"])
    page.keyboard.press("Control+o")
    _goto_folder(page, server["data"])
    page.locator(".dialog .dialog-body .fs-row", has_text="run_a.csv").first.dblclick()
    toast = page.locator(".toast", has_text="Already open")
    toast.wait_for()
    assert page.evaluate("window.__sv.state().runs.filter((r) => r.format !== 'derived').length") == 1
    toast.get_by_role("button", name="Open another copy").click()
    page.wait_for_function("window.__sv.state().runs.filter((r) => r.format !== 'derived').length === 2")


def test_several_files_at_once_suggest_compare(page, server):
    """F20: three files opened together got a suggestion for the FIRST file only (or none) and a
    toast per file. Now the card offers Compare open files for all of them."""
    _open(page, server["data"], ["run_a.csv", "run_b.csv", "run_c.csv"])
    card = page.locator(".start-card")
    card.wait_for(timeout=15000)
    assert "3 files" in card.locator("h3").inner_text()
    assert "Compare open files" in card.locator(".start-tpl b").inner_text()
    card.get_by_role("button", name="Open it").click()
    page.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.length === 3))")


def test_file_dialog_range_select_and_own_folders(page, server):
    """F21: Shift+click selects a range (it acted like Ctrl), Ctrl+A selects every file shown, and
    each use of the dialog keeps its own last folder (saving elsewhere moved where Open starts)."""
    page.keyboard.press("Control+o")
    _goto_folder(page, server["data"])
    row = lambda n: page.locator(".dialog .dialog-body .fs-row", has_text=n).first
    page.locator(".dialog .fs-sort button", has_text="Name").click()
    row("run_a.csv").click()
    row("run_c.csv").click(modifiers=["Shift"])
    assert page.locator(".dialog .dialog-body .fs-row.on").count() == 3
    row("run_b.csv").click()
    page.locator(".dialog").first.focus(); page.keyboard.press("Control+a")
    assert page.locator(".dialog .dialog-body .fs-row.on").count() == 3
    page.keyboard.press("Escape")
    page.wait_for_selector(".scrim", state="detached")
    page.keyboard.press("Control+s")                     # the session picker goes somewhere else
    _goto_folder(page, server["home"])
    page.keyboard.press("Escape")
    page.wait_for_selector(".scrim", state="detached")
    page.keyboard.press("Control+o")
    page.wait_for_function(f"document.querySelector('.crumbs input') && document.querySelector('.crumbs input').value === {json.dumps(server['data'])}")
