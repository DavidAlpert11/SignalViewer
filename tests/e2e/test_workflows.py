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
    # T48: it opens ready to look at - Compare open files, each run in its colour
    page.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.length === 3))", timeout=20000)


def test_open_the_two_flights_example(page, server):
    """T44: the same mission flown twice - both files open, with the same signals."""
    page.locator(".examples-line button", has_text="flown twice").click()
    page.wait_for_function("document.querySelectorAll('.run-head').length === 2")
    assert page.locator(".run-head", has_text="uav_flight_windy").count() == 1
    page.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.length >= 2))", timeout=20000)   # T48


def test_open_the_ardupilot_example(page, server):
    """T45: the flight-log example opens with the vibration warning from its health check; T48: and
    with its ArduPilot view already open (the card keeps only the findings)."""
    page.locator(".examples-line button", has_text="ArduPilot").click()
    card = page.locator(".start-card")
    card.wait_for(timeout=20000)
    page.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.length))", timeout=20000)
    page.wait_for_selector(".start-card .hrow")
    assert "warning" in card.locator(".hrow").first.get_attribute("class")
    assert card.locator(".start-tpl").count() == 0


def test_compare_open_files_gives_each_file_its_colour(page, server):
    """F13: a template without stored colours (Compare open files) gave every signal the same
    colour - the runs could not be told apart. Now each file has one colour, the same in every plot."""
    _open(page, server["data"], ["run_a.csv", "run_b.csv", "run_c.csv"])
    page.locator(".tpl-strip .chipbtn", has_text="Compare open files").click()      # T48: opens at once
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
    files = page.evaluate("[...document.querySelectorAll('.dialog .dialog-body .fs-row')].filter((r) => r.querySelector('.size').textContent).length")
    assert files >= 3 and page.locator(".dialog .dialog-body .fs-row.on").count() == files
    page.keyboard.press("Escape")
    page.wait_for_selector(".scrim", state="detached")
    page.keyboard.press("Control+s")                     # the session picker goes somewhere else
    _goto_folder(page, server["home"])
    page.keyboard.press("Escape")
    page.wait_for_selector(".scrim", state="detached")
    page.keyboard.press("Control+o")
    page.wait_for_function(f"document.querySelector('.crumbs input') && document.querySelector('.crumbs input').value === {json.dumps(server['data'])}")


def test_relisting_the_same_folder_keeps_the_selection(page, server):
    """The folder shown, listed again (the path typed while it was loading, Enter on it, a refresh),
    cleared what was picked meanwhile - Open stayed disabled (seen as a flaky e2e after F21)."""
    page.keyboard.press("Control+o")
    _goto_folder(page, server["data"])
    page.locator(".dialog .dialog-body .fs-row", has_text="run_a.csv").first.click()
    page.press(".crumbs input", "Enter")                      # the same folder again
    page.wait_for_timeout(500)
    assert page.locator(".dialog .dialog-body .fs-row.on").count() == 1
    assert page.locator(".dialog-foot .btn.primary").is_enabled()


def test_file_dialog_places(page, server):
    """T24 (owner): the file dialog lists the folders of the open files, recent folders and pinned
    favourites - one click goes back to a folder you work in. Pins are kept (settings.json)."""
    page.evaluate("fetch('/api/fs/favourites', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paths: [] }) })")
    _open(page, server["data"], ["run_a.csv"])
    page.keyboard.press("Control+o")
    _goto_folder(page, server["home"])
    places = page.locator(".fs-places")
    places.locator(".fs-place-go", has_text=os.path.basename(server["data"])).first.click()   # under Open files
    page.wait_for_function(f"document.querySelector('.crumbs input').value === {json.dumps(server['data'])}")
    page.locator(".fs-pin").click()                                    # pin the data folder
    places.locator("h3", has_text="Favourites").wait_for()
    page.wait_for_function("document.querySelector('.fs-pin').getAttribute('aria-pressed') === 'true'")
    page.keyboard.press("Escape")
    page.wait_for_selector(".scrim", state="detached")
    page.reload(); page.wait_for_selector(".topbar")
    page.keyboard.press("Control+o")
    _goto_folder(page, server["home"])
    page.locator(".fs-places h3", has_text="Favourites").wait_for()
    fav = page.locator(".fs-places .fs-place:has(.fs-unpin)").filter(has_text=os.path.basename(server["data"]))
    fav.first.wait_for()                                               # still pinned after a reload
    fav.first.locator(".fs-place-go").click()
    page.wait_for_function(f"document.querySelector('.crumbs input').value === {json.dumps(server['data'])}")
    page.locator(".fs-pin").click()                                    # unpin
    page.wait_for_function("document.querySelector('.fs-pin').getAttribute('aria-pressed') === 'false'")
    page.keyboard.press("Escape")


def test_file_dialog_recent_folders_and_empty_folder(page, server):
    """T24: a folder files were opened from is under Recent folders once they are closed; a folder
    with nothing to open says so (and how many other files it holds)."""
    page.evaluate("fetch('/api/fs/favourites', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paths: [] }) })")
    _open(page, server["data"], ["run_b.csv"])
    page.evaluate("Promise.all(window.__sv.state().runs.map((r) => fetch('/api/runs/' + r.id, { method: 'DELETE' })))")
    page.reload(); page.wait_for_selector(".topbar")
    other = os.path.join(server["home"], "notes")
    os.makedirs(other, exist_ok=True)
    open(os.path.join(other, "notes.docx"), "w").write("x")          # not a data file
    page.keyboard.press("Control+o")
    _goto_folder(page, other)
    page.locator(".fs-empty").wait_for()
    assert "1" in page.locator(".fs-empty").inner_text()               # 1 file of another type
    page.locator(".fs-places h3", has_text="Recent folders").wait_for()
    page.locator(".fs-places .fs-place-go", has_text=os.path.basename(server["data"])).first.click()
    page.wait_for_function(f"document.querySelector('.crumbs input').value === {json.dumps(server['data'])}")
    page.keyboard.press("Escape")


def test_quick_open(page, server):
    """T24: Ctrl+P lists favourites, recent files and recent folders; a file opens, a folder opens
    the file dialog there."""
    page.evaluate("fetch('/api/fs/favourites', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paths: [] }) })")
    _open(page, server["data"], ["run_c.csv"])
    page.evaluate("Promise.all(window.__sv.state().runs.map((r) => fetch('/api/runs/' + r.id, { method: 'DELETE' })))")
    page.reload(); page.wait_for_selector(".topbar")
    page.keyboard.press("Control+p")
    page.locator(".palette-input").fill("run_c")
    page.locator(".pal-item", has_text="run_c.csv").first.click()
    page.wait_for_function("window.__sv.state().runs.some((r) => r.name === 'run_c.csv')")
    page.keyboard.press("Control+p")
    page.locator(".palette-input").fill(os.path.basename(server["data"]))
    page.locator(".pal-item", has_text="Recent folders").first.click()
    page.wait_for_function(f"document.querySelector('.crumbs input') && document.querySelector('.crumbs input').value === {json.dumps(server['data'])}")


def test_each_file_has_a_colour_and_a_tag(page, server):
    """T46 (owner): with several files, signals of the same name were hard to tell apart - the
    legend cut off the file name. Each file has a colour and a tag (A, B...) shown on its chips;
    the same signal from two files in one plot is coloured by file."""
    _open(page, server["data"], ["run_a.csv", "run_b.csv"])
    runs = page.evaluate("window.__sv.state().runs.filter((r) => r.format !== 'derived').map((r) => [r.id, r.tag, r.color])")
    assert sorted(r[1] for r in runs) == ["A", "B"] and len({r[2] for r in runs}) == 2
    colour = {rid: c for rid, _, c in runs}
    sp = page.locator(".sig", has_text="Speed")
    sp.nth(0).click(); sp.nth(1).click()
    page.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 2")
    sigs = page.evaluate("window.__sv.state().ws.tabs[0].plots[0].signals.map((s) => [s.sig.split('/')[0], s.color])")
    assert all(c == colour[rid] for rid, c in sigs)                  # coloured by file
    chips = page.locator(".plot .chip")
    assert sorted(chips.locator(".file-tag").all_inner_texts()) == ["A", "B"]
    assert "run_a.csv" in (chips.first.get_attribute("title") or "") or "run_b.csv" in (chips.first.get_attribute("title") or "")
    # the file's tag can be changed (file menu) and the plot coloured by file (plot menu)
    page.locator(".run-head", has_text="run_a.csv").click(button="right")
    page.locator(".menu.ctx button", has_text="Short tag").click()
    page.locator(".dialog input").fill("base")
    page.keyboard.press("Enter")
    page.wait_for_function("window.__sv.state().runs.some((r) => r.tag === 'base')")
    page.locator(".plot .file-tag", has_text="base").wait_for()


def test_compare_keeps_file_colours(page, server):
    """T46: Compare runs coloured files by their position among the CHECKED runs - unchecking one
    recoloured the others. A file has one colour everywhere now."""
    _open(page, server["data"], ["run_a.csv", "run_b.csv", "run_c.csv"])
    colour = dict(page.evaluate("window.__sv.state().runs.filter((r) => r.format !== 'derived').map((r) => [r.name, r.color])"))
    page.locator("button[aria-label='Compare runs']").click()
    dot = lambda name: page.locator(".run-row, label", has_text=name).locator(".run-dot").first.evaluate("(e) => getComputedStyle(e).backgroundColor")
    def rgb(h):
        return f"rgb({int(h[1:3], 16)}, {int(h[3:5], 16)}, {int(h[5:7], 16)})"
    page.wait_for_selector(".run-dot")
    assert dot("run_c.csv") == rgb(colour["run_c.csv"])
    page.locator("label", has_text="run_a.csv").locator("input[type=checkbox]").first.uncheck()
    assert dot("run_c.csv") == rgb(colour["run_c.csv"])


def test_second_value_axis(page, server):
    """T47: a signal in other units gets the right value axis - offered when it is added (a toast),
    or from the chip menu; back to the left the same way."""
    path = os.path.join(server["data"], "units.csv")
    t = np.arange(0, 20, 0.1)
    np.savetxt(path, np.column_stack([t, 40 + 10 * np.sin(t), 15 - t / 40]), delimiter=",", header="Time,Speed [km/h],Batt [V]", comments="")
    _open(page, server["data"], ["units.csv"])
    plot = page.locator(".plot").first
    if not page.evaluate("window.__sv.state().ws.tabs[0].plots[0].signals.length"):
        page.locator(".sig", has_text="Speed").first.click()
    page.locator(".sig", has_text="Batt").first.click()                 # km/h, then V
    toast = page.locator(".toast", has_text="one value axis")
    toast.wait_for()
    toast.get_by_role("button", name="To the right axis").click()
    page.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.some((s) => s.axis === 'right')")
    page.wait_for_function("document.querySelector('.plot').querySelectorAll('.u-axis').length === 3")
    plot.locator(".chip", has_text="Batt").click(button="right")
    page.locator(".menu.ctx button", has_text="Back to the left axis").click()
    page.wait_for_function("!window.__sv.state().ws.tabs[0].plots[0].signals.some((s) => s.axis === 'right')")
    page.wait_for_function("document.querySelector('.plot').querySelectorAll('.u-axis').length === 2")
    os.remove(path)                                                    # the other tests list this folder


def test_template_chip_opens_at_once_or_asks(page, server):
    """T48: a template chip opens its template in one click when nothing has to be chosen; with a
    choice to make (Quick look with two files: of which?) it opens the library as before."""
    _open(page, server["data"], ["run_a.csv"])
    page.evaluate("window.__sv.state().clearAllPlots ? 0 : 0")
    page.locator("[aria-label='Clear all plots']").click()
    page.locator(".tpl-strip .chipbtn", has_text="Quick look").click()
    page.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.plots.some((p) => p.signals.length))")
    assert page.locator(".dialog").count() == 0
    page.locator(".toast", has_text="Quick look").wait_for()
    _open(page, server["data"], ["run_b.csv"])
    page.locator(".tpl-strip .chipbtn", has_text="Quick look").click()
    page.locator(".dialog", has_text="Templates").wait_for()               # which file? - the library asks


def test_columns_with_their_own_time(page, server):
    """A telemetry export where each value has its own time column (found by name): the value is
    drawn against its own time, the time columns are not listed as signals, and a note says so."""
    path = os.path.join(server["data"], "telemetry.csv")
    with open(path, "w") as f:
        f.write("Speed_time,Speed,Volt_time,Volt\n")
        for i in range(40):
            f.write(f"{i * 0.1},{10 + i}," + (f"{5 + i * 0.5},{16 - i * 0.05}" if i < 8 else ",") + "\n")
    try:
        _open(page, server["data"], ["telemetry.csv"])
        page.locator(".toast", has_text="time column of their own").wait_for()
        names = page.evaluate("window.__sv.state().runs.filter((r) => r.format !== 'derived')[0].signals.map((s) => s.name)")
        assert sorted(names) == ["Speed", "Volt"]
        rid = page.evaluate("window.__sv.state().runs.filter((r) => r.format !== 'derived')[0].id")
        post = lambda url, body: page.evaluate(f"fetch('{url}', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({json.dumps(body)}) }}).then((r) => r.json())")
        assert post("/api/data", {"signals": [f"{rid}/Volt"]})["series"][0]["total"] == 8          # its own 8 rows
        v = post("/api/cursor", {"signals": [f"{rid}/Volt"], "t": 5.0})["values"][f"{rid}/Volt"]
        assert v is not None and abs(v - 16.0) < 1e-6                                               # at its own time 5.0
    finally:
        os.remove(path)


def test_clearer_controls(page, server):
    """T49 (part): the file list's signal menu adds OR removes (it said "Add the result" for a
    signal); "Clear everything" asks with a button that says so; the zoom mode is not a second
    bare "X" next to the link button."""
    page.set_viewport_size({"width": 1100, "height": 760})
    _open(page, server["data"], ["run_a.csv"])
    page.locator("[aria-label='Clear all plots']").click()
    page.locator(".sig", has_text="Speed").first.click(button="right")
    page.locator(".menu.ctx button", has_text="Add to the active plot").click()
    page.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    page.locator(".sig", has_text="Speed").first.click(button="right")
    page.locator(".menu.ctx button", has_text="Remove from the active plot").click()
    page.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 0")
    assert "Zoom" in page.locator(".zoom-btn").inner_text()
    page.locator("button[aria-label='Clear everything']").click()
    ok = page.locator(".dialog .btn.primary")
    assert ok.inner_text() == "Clear everything" and "danger" in ok.get_attribute("class")
    page.keyboard.press("Escape")


def test_builtin_templates_in_hebrew(page, server):
    """T51: in Hebrew the built-in templates (and the tabs they make) are named in Hebrew."""
    _open(page, server["data"], ["run_a.csv"])
    page.get_by_role("button", name="עברית").click()
    page.wait_for_function("document.documentElement.dir === 'rtl'")
    chip = page.locator(".tpl-strip .chipbtn", has_text="מבט מהיר")
    chip.wait_for()
    page.locator("[aria-label='ניקוי כל הגרפים'], [aria-label='Clear all plots']").first.click()
    chip.click()
    page.wait_for_function("window.__sv.state().ws.tabs.some((t) => t.name.startsWith('מבט מהיר'))")
    page.get_by_role("button", name="English").click()


def test_small_window_file_header(page, server):
    """T50: with several files in a small window the file panel's header was crowded - "Link" cut,
    touching "Open files". The link toggle is an icon now, and the title never gives way."""
    page.set_viewport_size({"width": 1100, "height": 700})
    _open(page, server["data"], ["run_a.csv", "run_b.csv", "run_c.csv"])
    page.locator(".link-toggle").wait_for()
    fits = page.evaluate("""(() => { const h = document.querySelector('.side-head'), t = h.querySelector('h2');
        return t.scrollWidth <= t.clientWidth + 1 && h.scrollWidth <= h.clientWidth + 1; })()""")
    assert fits
    page.locator(".link-toggle").click()
    page.wait_for_function("window.__sv.state().linkRuns === true")
    page.locator(".link-toggle").click()
