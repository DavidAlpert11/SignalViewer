"""
Feature conformance suite: one test per feature ID in the requirements catalog
(section 4: D, S, V, C, T, O, P, R, E, K; section 5: N). Each test drives the real UI.

    python -m pytest tests/e2e/test_features.py -q
"""
import json, os, re, shutil, socket, subprocess, sys, time, urllib.request

import numpy as np
import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ----------------------------------------------------------------- fixtures

def set_layout(pg, r, c):
    """T20: the layouts are in the layout button's popover."""
    pg.click(".stage-bar .layout-btn")
    pg.click(f"[aria-label='Layout {r} × {c}']")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _csv(path, header, cols, fmt="%.6g", delim=","):
    np.savetxt(path, np.column_stack(cols), delimiter=delim, header=delim.join(header), comments="", fmt=fmt)


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    home = tmp_path_factory.mktemp("home")
    d = tmp_path_factory.mktemp("data")
    t = np.arange(0, 30, 0.01)
    f = lambda tt: 20 + 10 * np.tanh(tt - 5) - 8 * np.tanh(tt - 20)
    for name, sh, g in (("run_a", 0, 1), ("run_b", 0, 1.01), ("run_c", 0.6, 0.9)):
        _csv(d / f"{name}.csv", ["Time", "Speed", "RPM", "Gear"], [t, g * f(t - sh), 95 * g * f(t - sh), np.floor(t / 6)])
    _csv(d / "semi.csv", ["Time", "A", "B"], [t, np.sin(t), np.cos(t)], delim=";")
    with open(d / "messy.csv", "w") as fh:
        fh.write("Time,Val,Status\n0,1,OK\n0.2,2,OK\nbad,3,X\n0.1,4,OK\n0.3,5,FAIL\n")
    tg = t[:300]
    _csv(d / "geo.csv", ["Time", "Lat", "Lon", "Gear"], [tg, 32.0 + tg * 0.01, 34.8 + tg * 0.012, np.floor(tg)])
    _csv(d / "meta.csv", ["Time", "P"], [t[:100], t[:100] * 2])
    txt = open(d / "meta.csv").read()
    open(d / "meta.csv", "w").write("Rig: 3\nOperator: QA\n" + txt)
    tf = np.arange(4000) / 1000.0
    _csv(d / "tones.csv", ["Time", "Tone50"], [tf, np.sin(2 * np.pi * 50 * tf)])
    n, k = 3000, 300
    tw = np.arange(n) * 0.01
    _csv(d / "wide.csv", ["Time"] + [f"g{i // 30}.s{i:03d}" for i in range(k)], [tw] + [np.sin(tw * (i % 7 + 1)) for i in range(k)])
    try:
        import scipy.io
        scipy.io.savemat(d / "m.mat", {"t": t, "v": np.sin(t), "s": {"w": np.cos(t)}})
    except ImportError:
        pass
    try:                                    # ~70 MB, to see the progress panel
        import pyarrow as pa, pyarrow.csv as pacsv
        tb = np.arange(2_500_000) / 1e4
        pacsv.write_csv(pa.table({"Time": tb, "X": np.sin(tb), "Y": np.cos(tb)}), d / "big.csv")
    except ImportError:
        pass
    port = _free_port()
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "run.py"), "--port", str(port), "--no-open"],
                            env=dict(os.environ, HOME=str(home), USERPROFILE=str(home)),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(url, timeout=1); break
        except Exception:
            time.sleep(0.25)
    yield {"url": url, "data": str(d), "home": str(home), "out": str(tmp_path_factory.mktemp("out"))}
    proc.terminate()


@pytest.fixture()
def pg(env):
    with pw.sync_playwright() as p:
        kw = {"args": ["--no-sandbox"]}
        if os.environ.get("SV_CHROMIUM"):
            kw["executable_path"] = os.environ["SV_CHROMIUM"]
        b = p.chromium.launch(**kw)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=env["url"])
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        auto = os.path.join(env["home"], ".signalviewer", "autosave.json")
        if os.path.exists(auto):
            os.remove(auto)
        for r in json.loads(urllib.request.urlopen(env["url"] + "/api/runs").read()):
            if r["format"] == "derived":
                for s in r["signals"]:
                    urllib.request.urlopen(urllib.request.Request(env["url"] + "/api/derived/" + urllib.request.quote(s["name"], safe=""), method="DELETE"))
            else:
                urllib.request.urlopen(urllib.request.Request(f"{env['url']}/api/runs/{r['id']}", method="DELETE"))
        page.goto(env["url"])
        page.wait_for_selector(".app")
        page.env = env
        yield page
        assert not errors, errors
        b.close()


# ----------------------------------------------------------------- helpers
def S(pg, expr):
    """Read app state: S(pg, 's.ws.tabs.length')."""
    return pg.evaluate(f"(() => {{ const s = window.__sv.state(); return {expr}; }})()")


def goto_folder(pg, folder):
    try:
        pg.wait_for_function("document.querySelector('.crumbs input') && document.querySelector('.crumbs input').value !== ''", timeout=8000)
        pg.fill(".crumbs input", folder); pg.press(".crumbs input", "Enter")
        pg.wait_for_function(f"document.querySelector('.crumbs input').value === {json.dumps(folder)}", timeout=8000)
    except Exception:
        info = pg.evaluate("""() => ({ dialog: !!document.querySelector('.dialog .crumbs'),
            value: document.querySelector('.crumbs input')?.value, error: document.querySelector('.dialog .err, .dialog .error')?.innerText,
            rows: document.querySelectorAll('.dialog .dialog-body .fs-row').length })""")
        pg.screenshot(path="/tmp/goto_fail.png")
        print("DBG goto_folder failed:", folder, info, flush=True)
        raise


def open_files(pg, *names, options=False, clear=True):
    pg.keyboard.press("Control+o")
    goto_folder(pg, pg.env["data"])
    for i, n in enumerate(names):
        row = pg.locator(".dialog .dialog-body .fs-row", has_text=n).first
        row.wait_for()
        row.click(modifiers=["Control"] if i else [])
    if options:
        pg.locator(".dialog-foot input[type=checkbox]").check()
    before = S(pg, "s.runs.filter(r => r.format !== 'derived').length")
    pg.click(".dialog-foot .btn.primary")
    if not options:
        pg.wait_for_function(f"window.__sv.state().runs.filter(r => r.format !== 'derived').length >= {before + len(names)}", timeout=30000)
        if clear:   # the first signal of a first file is plotted automatically; start each test clean
            pg.wait_for_timeout(300)
            pg.click("[aria-label='Clear all plots']")


def save_as(pg, name, folder=None):
    goto_folder(pg, folder or pg.env["out"])
    pg.fill(".savename input", name); pg.click(".dialog-foot .btn.primary")


def chips(pg, plot=0):
    return pg.locator(".plot").nth(plot).locator(".chip .nm").all_inner_texts()


def sig(pg, name, run=None):
    loc = pg.locator(".sig", has_text=name)
    return loc.first if run is None else loc.nth(run)


def menu_item(pg, label):
    pg.locator(".menu.ctx button", has_text=label).first.click()


def toast_text(pg):
    pg.wait_for_selector(".toast")
    return " | ".join(pg.locator(".toast").all_inner_texts())


# =========================================================== D: files & data
def test_D01_open_several_files(pg):
    open_files(pg, "run_a.csv", "run_b.csv")
    assert pg.locator(".run-head").count() == 2


def test_D02_autodetect_delimiter(pg):
    open_files(pg, "semi.csv")
    assert {"A", "B"} <= set(pg.locator(".sig .nm").all_inner_texts())


def test_D03_import_options_live_preview(pg):
    open_files(pg, "meta.csv", options=True)
    pg.wait_for_selector("table.preview")
    pg.locator(".import-grid input[type=number]").first.fill("2")       # skip rows
    pg.wait_for_function("[...document.querySelectorAll('table.preview th')].some(th => th.innerText === 'P')")
    pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function("window.__sv.state().runs.length === 1")
    assert S(pg, "s.runs[0].signals[0].name") == "P"


def test_D04_messy_data_and_load_report(pg):
    open_files(pg, "messy.csv")
    text = toast_text(pg)
    assert "read as states" in text and "sorted" in text      # F20: "text read as states: Status"
    assert S(pg, "s.runs[0].samples") == 4
    # the text column is a state signal with its texts (OK / FAIL), no longer skipped
    assert S(pg, "s.runs[0].signals.find(x => x.name === 'Status').labels['0']") == "OK"


def test_D05_rename_and_description(pg):
    open_files(pg, "run_a.csv")
    pg.locator(".run-head").first.click(button="right"); menu_item(pg, "Description")
    pg.fill(".dialog textarea", "Bench 3"); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function("window.__sv.state().runs[0].description === 'Bench 3'")
    pg.locator(".run-head").first.click(button="right"); menu_item(pg, "Rename")
    pg.fill(".run-head input.run-name", "Baseline"); pg.press(".run-head input.run-name", "Enter")
    pg.wait_for_function("window.__sv.state().runs[0].name === 'Baseline'")


def test_D06_replace_file_keeps_plots(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    rid = S(pg, "s.runs[0].id")
    pg.locator(".run-head").first.click(button="right"); menu_item(pg, "Replace")
    goto_folder(pg, pg.env["data"])
    pg.locator(".dialog .dialog-body .fs-row", has_text="run_c.csv").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function("window.__sv.state().runs[0].name === 'run_c.csv'")
    assert S(pg, "s.runs[0].id") == rid and len(chips(pg)) == 1


def test_D07_remove_file_removes_its_signals(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.locator(".run-head").first.click(button="right"); menu_item(pg, "Remove")
    pg.wait_for_function("window.__sv.state().runs.length === 0")
    assert chips(pg) == []


def test_D08_reload_from_disk(pg):
    open_files(pg, "run_a.csv")
    pg.locator(".run-head").first.hover()
    pg.locator(".run-head [aria-label='Reload from disk']").click()
    pg.wait_for_timeout(500)
    assert S(pg, "s.runs.length") == 1


def test_D09_D10_live_mode_and_follow(pg):
    p = os.path.join(pg.env["data"], "live.csv")
    with open(p, "w") as f:
        f.write("Time,V\n" + "".join(f"{i * 0.1:.1f},{i}\n" for i in range(50)))
    open_files(pg, "live.csv")
    pg.click(".topbar .btn:has-text('Live')")
    pg.locator(".stage-bar select[aria-label='Follow']").select_option("10")
    with open(p, "a") as f:
        f.write("".join(f"{i * 0.1:.1f},{i}\n" for i in range(50, 300)))
    pg.wait_for_function("window.__sv.state().runs[0].samples === 300", timeout=8000)
    pg.wait_for_timeout(1500)
    r = S(pg, "Object.values(s.ranges)[0]")
    assert r and abs(r[1] - 29.9) < 0.01 and abs(r[1] - r[0] - 10) < 0.01


def test_D11_file_time_offset(pg):
    open_files(pg, "run_a.csv")
    pg.locator(".run-head").first.click(button="right"); menu_item(pg, "Time offset")
    pg.fill(".dialog input", "2.5"); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".badge-off")
    assert S(pg, "s.runs[0].timeOffset") == 2.5 and abs(S(pg, "s.runs[0].start") - 2.5) < 1e-9


def test_D12_link_files(pg):
    open_files(pg, "run_a.csv", "run_b.csv", "run_c.csv")
    pg.click(".side-head [aria-label='Link files']")
    sig(pg, "RPM").click()
    pg.wait_for_function("document.querySelectorAll('.plot .chip').length === 3")


# =========================================================== S: signals
def test_S01_tree_with_counts(pg):
    open_files(pg, "run_a.csv")
    assert pg.locator(".run-head .run-meta").first.inner_text() == "3"


def test_S02_smart_search(pg):
    open_files(pg, "run_a.csv")
    pg.fill(".filter input", "sepeed")                      # one typo
    pg.wait_for_function("document.querySelectorAll('.sig').length === 1")
    assert pg.locator(".sig .nm").inner_text() == "Speed"
    pg.fill(".filter input", "rp")                          # substring
    assert pg.locator(".sig .nm").all_inner_texts() == ["RPM"]


def test_S03_prefix_groups(pg):
    open_files(pg, "wide.csv")
    assert pg.locator(".grp-head").count() == 10
    pg.fill(".filter input", "s123")
    pg.wait_for_function("document.querySelectorAll('.sig').length === 1")


def test_S04_signal_properties(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.locator(".plot .chip").first.click()
    fields = pg.locator(".inspector .field input")
    pg.locator(".inspector .swatches button").nth(3).click()
    pg.locator(".inspector .field", has_text="Scale").locator("input").fill("2"); pg.keyboard.press("Enter")
    pg.locator(".inspector .field", has_text="Time offset").locator("input").fill("1.5"); pg.keyboard.press("Enter")
    ps = S(pg, "s.ws.tabs[0].plots[0].signals[0]")
    assert ps["scale"] == 2 and ps["tOffset"] == 1.5 and ps["color"] == "#9B7BFF"


def test_S05_state_display(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Gear").click()
    pg.locator(".plot .chip").first.click()
    assert "few whole-number" in pg.locator(".inspector").inner_text()      # discrete detected
    pg.locator(".inspector .seg").get_by_role("button", name="State lane", exact=True).click()
    pg.wait_for_selector(".chip .tag")


def test_S06_context_menu(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click(); sig(pg, "RPM").click()
    pg.locator(".plot .chip").first.click(button="right")
    labels = pg.locator(".menu.ctx button").all_inner_texts()
    for want in ("Move down", "Copy to a new plot", "Use as X axis", "Create signal", "Remove"):
        assert any(want in l for l in labels), want
    assert not any("Derivative" in l for l in labels)            # T21b: in the submenu, not repeated
    menu_item(pg, "Move down")
    assert chips(pg) == ["RPM", "Speed"]
    pg.locator(".plot .chip").first.click(button="right")
    pg.locator(".menu.ctx button", has_text="Create signal").hover()
    menu_item(pg, "Derivative")
    pg.wait_for_function("document.querySelectorAll('.plot .chip').length === 3")


def test_create_signal_submenu_from_the_file_list(pg):
    """T21b: the file list's signal menu has the same "Create signal ▸" - a click opens it too, and
    "Other operations…" opens Create signals with that signal chosen."""
    open_files(pg, "run_a.csv")
    sig(pg, "RPM").click(button="right")
    pg.locator(".menu.ctx button", has_text="Create signal").click()          # click opens it as well
    pg.wait_for_selector(".menu.ctx.sub")
    menu_item(pg, "Other operations")
    pg.wait_for_function("window.__sv.state().panel === 'analysis'")
    pg.wait_for_function("!window.__sv.state().analysisSeed")             # the panel took the signal
    assert "RPM" in pg.locator(".analysis").inner_text()


def test_S07_drag_chip_to_other_plot(pg):
    open_files(pg, "run_a.csv")
    set_layout(pg, 2, 1)
    sig(pg, "Speed").click(); sig(pg, "RPM").click()
    pg.locator(".plot").first.locator(".chip", has_text="RPM").drag_to(pg.locator(".plot").nth(1))
    assert chips(pg, 0) == ["Speed"] and chips(pg, 1) == ["RPM"]


# =========================================================== V: views & plots
def test_V01_tabs(pg):
    pg.click("[aria-label='New tab']"); pg.click("[aria-label='New tab']")
    assert pg.locator(".tab").count() == 3
    pg.locator(".tab").first.click(button="right"); menu_item(pg, "Close other tabs")
    assert pg.locator(".tab").count() == 1
    pg.locator(".tab").first.dblclick(); pg.fill(".tab input", "Speed"); pg.press(".tab input", "Enter")
    assert pg.locator(".tab").first.inner_text().startswith("Speed")
    pg.locator(".tab").first.click(button="right"); menu_item(pg, "Duplicate tab")
    assert pg.locator(".tab").count() == 2


def test_V02_free_layout_max_9_and_resize(pg):
    open_files(pg, "run_a.csv")
    pg.click(".stage-bar .pick-wrap .btn")
    assert pg.locator(".gridpick-cells button[aria-label='4 × 4']").is_disabled()
    assert pg.locator(".gridpick-cells button[aria-label='4 × 3']").is_disabled()
    assert not pg.locator(".gridpick-cells button[aria-label='3 × 3']").is_disabled()
    pg.locator(".gridpick-cells button[aria-label='1 × 6']").click()
    assert pg.locator(".plot").count() == 6 and S(pg, "[s.ws.tabs[0].rows, s.ws.tabs[0].cols]") == [1, 6]
    pg.click(".stage-bar .pick-wrap .btn")                     # typed
    pg.locator(".gridpick-type input").nth(0).fill("3"); pg.locator(".gridpick-type input").nth(1).fill("2")
    pg.click(".gridpick-type .btn")
    assert S(pg, "[s.ws.tabs[0].rows, s.ws.tabs[0].cols]") == [3, 2]
    set_layout(pg, 1, 2)
    g = pg.locator(".gutter-v").first.bounding_box()
    pg.mouse.move(g["x"] + 4, g["y"] + 50); pg.mouse.down(); pg.mouse.move(g["x"] + 200, g["y"] + 50); pg.mouse.up()
    sizes = S(pg, "s.ws.tabs[0].colSizes")
    assert sizes and sizes[0] > sizes[1]


def test_V02b_shrinking_layout_removes_plots_with_undo(pg):
    open_files(pg, "run_a.csv")
    set_layout(pg, 2, 2)
    for k, name in ((1, "Speed"), (4, "RPM")):
        pg.keyboard.press(str(k)); sig(pg, name).click()
    set_layout(pg, 1, 1)
    assert pg.locator(".plot").count() == 1 and chips(pg) == ["Speed"]
    pg.locator(".toast button:has-text('Undo')").click()
    assert pg.locator(".plot").count() == 4 and chips(pg, 3) == ["RPM"]


def test_V03_active_plot_keys(pg):
    set_layout(pg, 2, 2)
    pg.keyboard.press("3")
    assert S(pg, "s.ws.tabs[0].active") == 2


def test_V04_plot_modes(pg):
    open_files(pg, "tones.csv")
    sig(pg, "Tone50").click()
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="FFT").first.click()
    pg.wait_for_function("[...document.querySelectorAll('.chip .val')].some(e => e.innerText.startsWith('50'))")
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="X-Y").first.click()
    pg.wait_for_selector(".xpick .picker-btn")


def test_V05_titles(pg):
    open_files(pg, "run_a.csv")
    pg.locator(".plot-title").first.dblclick()
    pg.fill(".plot-head input", "Engine"); pg.press(".plot-head input", "Enter")
    assert pg.locator(".plot-title").first.inner_text() == "Engine"


def test_V06_link_x_and_y(pg):
    pg.click(".stage-bar .btn:has-text('Y')")
    assert S(pg, "s.ws.tabs[0].linkY") is True and S(pg, "s.ws.tabs[0].linkX") is True


def test_V07_axis_limits(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.locator(".plot-more").first.click(); pg.click("text=Axis limits")
    inputs = pg.locator(".dialog input.num")
    for i, v in enumerate(["5", "10", "0", "50"]):
        inputs.nth(i).fill(v)
    pg.click(".dialog-foot .btn.primary")
    assert S(pg, "s.ws.tabs[0].plots[0].ylim") == [0, 50] and S(pg, "Object.values(s.ranges)[0]") == [5, 10]
    pg.keyboard.press("r")
    assert S(pg, "Object.values(s.ranges)[0]") == [5, 10]          # reset returns to the limits


def test_V08_zoom_pan_back(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")
    box = pg.locator(".plot .u-over").first.bounding_box()
    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    pg.mouse.wheel(0, -300); pg.wait_for_timeout(200)
    r1 = S(pg, "Object.values(s.ranges)[0]")
    pg.keyboard.down("Alt"); pg.mouse.down(); pg.mouse.move(box["x"] + box["width"] / 2 - 150, box["y"] + 100); pg.mouse.up(); pg.keyboard.up("Alt")   # T19: pan is Alt
    r2 = S(pg, "Object.values(s.ranges)[0]")
    assert r2[0] > r1[0] and abs((r2[1] - r2[0]) - (r1[1] - r1[0])) < 1e-6        # panned, same width
    pg.keyboard.press("Backspace")
    assert S(pg, "Object.values(s.ranges)[0]") == r1


def test_V09_decimation_status(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("document.querySelector('.status').innerText.match(/Showing|All points/)")


def test_V10_theme(pg):
    before = pg.evaluate("document.documentElement.dataset.theme")
    pg.click("[aria-label='Theme']")
    assert pg.evaluate("document.documentElement.dataset.theme") != before


def test_V11_clear_plot_and_all(pg):
    open_files(pg, "run_a.csv")
    set_layout(pg, 2, 1)
    sig(pg, "Speed").click(); pg.keyboard.press("2"); sig(pg, "RPM").click()
    pg.locator(".plot-more").first.click(); pg.click("text=Clear plot")
    assert chips(pg, 0) == [] and chips(pg, 1) == ["RPM"]
    pg.click("[aria-label='Clear all plots']")
    assert chips(pg, 1) == []
    pg.keyboard.press("Control+z")
    assert chips(pg, 1) == ["RPM"]
    # T06: the toast says it can be undone, and its Undo works too
    pg.click("[aria-label='Clear all plots']")
    assert pg.locator(".toast", has_text="Plots cleared").count() == 1     # replaced, not stacked
    pg.locator(".toast", has_text="Plots cleared").locator("button", has_text="Undo").click()
    assert chips(pg, 1) == ["RPM"]
    # a stale Undo must never undo a later change: the next change takes the toast away
    pg.click("[aria-label='Clear all plots']")
    pg.keyboard.press("Control+z")
    pg.wait_for_function("!document.querySelector('.toast')?.textContent?.includes('Plots cleared')")


# =========================================================== C / T: cursor & stats
def test_C01_C02_C03_cursor(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.keyboard.press("Space")
    pg.locator(".ctime input").first.fill("10"); pg.keyboard.press("Enter")
    assert S(pg, "s.cursor.t1") == 10
    pg.keyboard.press("d")
    pg.wait_for_selector("table.vals th:has-text('Δ/ΔT')")
    pg.locator(".inspector .seg button", has_text="All plots").click()
    assert S(pg, "s.inspectorScope") == "all"


def test_C04_cursor_play(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.keyboard.press("Space")
    t0 = S(pg, "s.cursor.t1")
    pg.keyboard.press("p"); pg.wait_for_timeout(800); pg.keyboard.press("p")
    assert S(pg, "s.cursor.t1") > t0


def test_T01_T02_T03_region_stats_and_copy(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.keyboard.press("d")
    pg.wait_for_selector(".inspector h3:has-text('Between cursors')")
    pg.click(".inspector [aria-label='Copy table']")
    clip = pg.evaluate("navigator.clipboard.readText()")
    assert clip.startswith("signal\tmin") and "Speed" in clip


# =========================================================== O: operations
def test_O01_O04_unary_filter_preview(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.click("[aria-label='Create signals']")
    pg.locator(".analysis .afield select").first.select_option("lowpass")
    pg.click("text=Preview")
    pg.wait_for_function("window.__sv.state().preview !== null")
    pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("document.querySelectorAll('.plot .chip').length === 2")
    assert S(pg, "s.preview") is None


def test_O02_O03_O05_binary_multi_delete(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click(); sig(pg, "RPM").click()
    pg.click("[aria-label='Create signals']")
    pg.click(".seg.wide button:has-text('Two signals')"); pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.click(".seg.wide button:has-text('Several')")
    pg.click(".msp-top .linklike:has-text('From the active plot')")       # an explicit choice, never implicit
    pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 2")
    pg.locator(".dsig").first.locator("button[aria-label='Remove']").click()
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 1")


# =========================================================== P: compare
def test_P01_to_P08_compare(pg):
    open_files(pg, "run_a.csv", "run_b.csv", "run_c.csv")
    pg.click("[aria-label='Compare runs']")
    assert pg.locator(".side select").first.input_value() == S(pg, "s.runs[0].id")   # first file is the baseline
    pg.click(".sim-settings-toggle"); pg.locator(".side .arow input").first.fill("1")
    pg.wait_for_function("document.querySelectorAll('.sim-row').length === 3", timeout=20000)   # P-04: all shared signals
    names = pg.locator(".sim-row .sim-name").all_inner_texts()
    assert set(n.strip("!") for n in names) == {"Speed", "RPM", "Gear"}
    pcts = [float(x.strip("%").replace(",", "")) for x in pg.locator(".sim-row .sim-pct").all_inner_texts()]
    assert pcts == sorted(pcts)                                         # least similar first
    pg.click(".sim-head .linklike")
    pcts2 = [float(x.strip("%").replace(",", "")) for x in pg.locator(".sim-row .sim-pct").all_inner_texts()]
    assert pcts2 == sorted(pcts2, reverse=True)                          # toggled
    pg.locator(".sim-row", has_text="Speed").click()                     # P-01..P-03 detail + plot
    pg.wait_for_selector("table.cmp2 tbody")
    assert pg.locator("table.cmp2 tbody").count() == 2 and len(chips(pg)) == 3
    pg.locator("table.cmp2 tbody").nth(1).locator("button").click()     # P-06 auto shift
    pg.wait_for_selector(".toast:has-text('shifted')")
    pg.click("text=Plot differences")                                    # P-05, P-07
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.filter(p => p.signals.length).length >= 2")
    pg.click(".cmp-panel .btn:has-text('Export CSV')"); save_as(pg, "cmp.csv")   # P-08
    pg.wait_for_selector(".toast:has-text('cmp.csv')")
    pg.click("text=Table of all signals")
    pg.wait_for_selector(".cmp-dialog")
    pg.locator(".cmp-row", has_text="RPM").click()
    assert pg.locator(".cmp-sub tbody tr").count() == 3
    pg.keyboard.press("Escape")


def test_similarity_list_filters_and_cache(pg):
    open_files(pg, "run_a.csv", "run_c.csv")
    pg.click("[aria-label='Compare runs']")
    pg.wait_for_selector(".sim-row")
    total = pg.locator(".sim-row").count()
    pills = {p.split()[0]: int(p.split()[-1]) for p in pg.locator(".sim-pills .pill").all_inner_texts()}
    assert pills["All"] == total == pills["Different"] + pills["Close"] + pills["Same"]
    pg.locator(".pill", has_text="Different").click()
    assert pg.locator(".sim-row").count() == pills["Different"]
    pg.locator(".cmp-panel .acheck input").nth(1).uncheck()
    pg.wait_for_selector(".sim-row", state="detached", timeout=3000)     # one file left: no list
    pg.locator(".cmp-panel .acheck input").nth(1).check()
    pg.wait_for_selector(".sim-row", timeout=2000)                       # cached: immediate


def test_bulk_pick_without_plotting(pg):
    open_files(pg, "wide.csv")
    assert chips(pg) == []
    pg.click("[aria-label='Create signals']"); pg.click(".seg.wide button:has-text('Several')")
    pg.fill(".msp-filter input", "g2.")
    pg.click(".msp-actions .btn:has-text('Choose these')")
    assert pg.locator(".msp-count").inner_text().startswith("30")
    pg.fill(".msp-filter input", "g02.")                                # no exact match: no bulk choice
    assert pg.locator(".msp-actions").count() == 0
    pg.fill(".msp-filter input", "")
    pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 1")


# =========================================================== R: reports
def test_R01_to_R06_reports(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.click("[aria-label='Report']")
    pg.locator(".side .afield input").first.fill("Run report"); pg.locator(".side .afield input").first.blur()
    pg.click(".side .btn:has-text('Preview')")
    pg.wait_for_selector("iframe.preview-frame")
    pg.keyboard.press("Escape")
    for label, name in (("Create interactive HTML", "r.html"), ("PDF", "r.pdf"), ("Word", "r.docx")):
        pg.locator(".side .btn", has_text=label).first.click(); save_as(pg, name)
        pg.wait_for_function(f"[...document.querySelectorAll('.toast')].some(t => t.innerText.includes('{name}'))", timeout=40000)
    html = open(os.path.join(pg.env["out"], "r.html"), encoding="utf-8").read()
    assert "Run report" in html and "sv-data" in html


# =========================================================== E / K: sessions & keys
def test_E01_E02_session_and_locate_missing(pg):
    src = os.path.join(pg.env["data"], "run_b.csv")
    moved_dir = os.path.join(pg.env["out"], "moved"); os.makedirs(moved_dir, exist_ok=True)
    tmp = os.path.join(pg.env["data"], "run_tmp.csv"); shutil.copy(src, tmp)
    open_files(pg, "run_tmp.csv")
    sig(pg, "Speed").click()
    pg.keyboard.press("Control+s"); save_as(pg, "sess")
    pg.wait_for_selector(".toast:has-text('Saved')")
    shutil.move(tmp, os.path.join(moved_dir, "run_tmp.csv"))
    pg.locator(".run-head").first.click(button="right"); menu_item(pg, "Remove")
    pg.keyboard.press("Control+Shift+O")
    goto_folder(pg, pg.env["out"])
    pg.locator(".dialog .dialog-body .fs-row", has_text="sess.svsession").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".toast:has-text('not found')")
    pg.locator(".toast button:has-text('Locate')").click()
    goto_folder(pg, moved_dir)
    pg.locator(".dialog .dialog-body .fs-row", has_text="run_tmp.csv").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function("document.querySelectorAll('.plot .chip').length === 1", timeout=15000)


def test_K01_help_screen(pg):
    pg.keyboard.press("?")
    pg.wait_for_selector("table.keys tr")          # the help screen's code loads on first use
    assert pg.locator("table.keys tr").count() >= 25


# =========================================================== N: new features
def test_N01_command_palette(pg):
    open_files(pg, "run_a.csv")
    pg.keyboard.press("Control+k"); pg.keyboard.type("sped")
    assert "Speed" in pg.locator(".pal-item").first.inner_text()


def test_N02_undo_redo(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.keyboard.press("Control+z"); assert chips(pg) == []
    pg.keyboard.press("Control+y"); assert chips(pg) == ["Speed"]


def test_N03_drop_files_on_window(pg):
    content = open(os.path.join(pg.env["data"], "run_a.csv")).read()
    pg.evaluate("""(text) => {
        const dt = new DataTransfer(); dt.items.add(new File([text], 'dropped.csv', { type: 'text/csv' }));
        for (const type of ['dragenter', 'dragover', 'drop']) window.dispatchEvent(new DragEvent(type, { dataTransfer: dt, bubbles: true }));
    }""", content)
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name === 'dropped.csv')", timeout=15000)


def test_N04_progress_and_cancel(pg):
    if not os.path.exists(os.path.join(pg.env["data"], "big.csv")):
        pytest.skip("pyarrow not installed")
    pg.keyboard.press("Control+o"); goto_folder(pg, pg.env["data"])
    pg.locator(".dialog .dialog-body .fs-row", has_text="big.csv").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".job", timeout=5000)
    pg.click(".job .btn")
    pg.wait_for_selector(".job", state="detached")
    assert S(pg, "s.runs.length") == 0


def test_N05_autosave_restore(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_timeout(1500)
    pg.reload(); pg.wait_for_selector(".plot .chip")
    assert chips(pg) == ["Speed"]


def test_N06_export_csv(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.locator(".plot-more").first.click(); pg.click("text=Export data"); save_as(pg, "d.csv")
    pg.wait_for_selector(".toast:has-text('d.csv')")
    assert open(os.path.join(pg.env["out"], "d.csv"), encoding="utf-8-sig").readline().startswith("Time,Speed")


def test_N07_text_size(pg):
    pg.keyboard.press("Control+=")
    assert pg.evaluate("getComputedStyle(document.documentElement).fontSize") != "13px"


def test_N13_matlab(pg):
    if not os.path.exists(os.path.join(pg.env["data"], "m.mat")):
        pytest.skip("scipy not installed")
    open_files(pg, "m.mat")
    assert {"v", "s.w"} <= set(pg.locator(".sig .nm").all_inner_texts())


def test_N16_hebrew_rtl(pg):
    pg.click(".topbar .btn:has-text('עברית')")
    assert pg.evaluate("document.documentElement.dir") == "rtl"


def test_N20_images(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    for fmt in ("PNG", "SVG"):
        pg.locator(".plot-more").first.click(); pg.click(f"text=Save image ({fmt})"); save_as(pg, f"img.{fmt.lower()}")
        pg.wait_for_selector(f".toast:has-text('img.{fmt.lower()}')")
    pg.locator(".plot-more").first.click(); pg.click("text=Copy image")
    pg.wait_for_selector(".toast:has-text('copied')")


# ======================================================= additions from review
def test_batch_edit_selected_signals(pg):
    open_files(pg, "run_a.csv")
    for n in ("Speed", "RPM", "Gear"):
        sig(pg, n).click()
    pg.locator(".plot .chip").nth(0).click()
    pg.locator(".plot .chip").nth(1).click(modifiers=["Control"])
    pg.wait_for_selector(".inspector h3:has-text('2 signals selected')")
    f = pg.locator(".inspector .section", has_text="selected").locator(".field", has_text="Scale").locator("input")
    f.fill("3"); pg.keyboard.press("Enter")
    scales = S(pg, "s.ws.tabs[0].plots[0].signals.map(x => x.scale)")
    assert scales == [3, 3, 1]
    pg.click("[aria-label='Create signals']")
    pg.locator(".seg.wide button", has_text="Each of several").click()
    pg.click(".msp-top .linklike:has-text('From the legend selection')")
    pg.locator(".analysis .afield select").first.select_option("affine")
    pg.locator(".analysis .afield input[type=number]").nth(0).fill("2")
    pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 2")


def test_legend_names_follow_file_rule(pg):
    a = os.path.join(pg.env["out"], "A"); b = os.path.join(pg.env["out"], "B")
    os.makedirs(a, exist_ok=True); os.makedirs(b, exist_ok=True)
    shutil.copy(os.path.join(pg.env["data"], "run_a.csv"), os.path.join(a, "test.csv"))
    shutil.copy(os.path.join(pg.env["data"], "run_c.csv"), os.path.join(b, "test.csv"))
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    assert chips(pg) == ["Speed"]                                          # one file: no file name
    pg.click("[aria-label='Create signals']"); pg.get_by_role("button", name="Create signal", exact=True).click()    # a derived signal is not a file
    pg.wait_for_function("document.querySelectorAll('.plot .chip').length === 2")
    assert chips(pg)[0] == "Speed"
    pg.click("[aria-label='Data']")
    for k, folder in enumerate((a, b)):
        pg.click(".side-head .btn:has-text('Open files')"); goto_folder(pg, folder)
        pg.locator(".dialog .dialog-body .fs-row", has_text="test.csv").click(); pg.click(".dialog-foot .btn.primary")
        # wait until this file is open before opening the next one
        pg.wait_for_function(f"window.__sv.state().runs.filter(r => r.format !== 'derived').length === {2 + k}", timeout=25000)
        pg.wait_for_selector(".job", state="detached")
    try:
        pg.wait_for_function("window.__sv.state().runs.filter(r => r.format !== 'derived').length === 3", timeout=8000)
    except Exception:
        print("DBG runs:", S(pg, "s.runs.map(r => r.path)"), "toasts:", pg.locator(".toast").all_inner_texts(), "dialog:", pg.locator(".dialog").count())
        pg.screenshot(path="/tmp/legend_dbg.png"); raise
    names = pg.locator(".run-head .run-name").all_inner_texts()
    assert "A/test.csv" in names and "B/test.csv" in names and "run_a.csv" in names
    # several files (T46): the chip shows the file's tag; the tooltip names the file
    chip = pg.locator(".plot").first.locator(".chip").first
    assert chips(pg)[0] == "Speed" and chip.locator(".file-tag").inner_text() in ("A", "B", "C")
    assert "run_a.csv" in (chip.get_attribute("title") or "")


def test_formula_editor(pg):
    open_files(pg, "run_a.csv")
    pg.click("[aria-label='Create signals']"); pg.click(".seg.wide button:has-text('Formula')")
    pg.click(".fx-input"); pg.keyboard.type("2*Spe"); pg.keyboard.press("Tab")        # autocomplete
    assert pg.locator(".fx-input").input_value() == "2*Speed"
    pg.keyboard.type(" - RPMM/95")
    pg.wait_for_selector(".fx-err:has-text('Did you mean RPM')")
    pg.fill(".fx-input", "2*Speed - RPM/95 + where(Gear > 2, 1, 0)")
    pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("[...document.querySelectorAll('.dsig-name')].some(e => e.innerText.startsWith('2*Speed'))")


def test_frame_conversion(pg):
    """T17b: Create signals > Frames - three components in, one derived signal per target axis;
    attitude pickers appear only when the body frame is involved."""
    open_files(pg, "run_a.csv")
    for n in ("Speed", "RPM", "Gear"):
        sig(pg, n).click()
    pg.click("[aria-label='Create signals']"); pg.click(".seg.wide button:has-text('Frames')")
    assert pg.locator(".analysis .picker-btn").count() == 6                  # X Y Z + roll pitch yaw
    pg.locator(".seg.wide button", has_text="Quaternion").click()
    assert pg.locator(".analysis .picker-btn").count() == 7
    pg.locator(".analysis label:has-text('To frame') select").select_option("ecef")
    assert pg.locator(".analysis .picker-btn").count() == 9                  # + vehicle lat / lon
    pg.locator(".seg.wide button", has_text="Position").click()             # LLA -> NED by default
    assert pg.locator(".analysis .picker-btn").count() == 3
    assert pg.locator(".analysis h3:has-text('Reference point')").count() == 1
    pg.locator(".seg.wide button", has_text="Manual").click()
    assert pg.locator(".analysis input[type=number]").count() == 3
    create = pg.get_by_role("button", name="Create 3 signals", exact=True)
    assert create.is_disabled()                                              # reference not filled in
    pg.locator(".analysis label:has-text('From frame') select").select_option("ned")
    pg.locator(".analysis label:has-text('To frame') select").select_option("enu")
    assert pg.locator(".analysis h3:has-text('Reference point')").count() == 0   # same origin: no reference
    pg.locator(".seg.wide button", has_text="Vector").click()
    pg.locator(".analysis label:has-text('From frame') select").select_option("ned")
    pg.locator(".analysis label:has-text('To frame') select").select_option("enu")
    assert pg.locator(".analysis .picker-btn").count() == 3                  # no attitude for NED -> ENU
    assert pg.locator(".analysis .picker-btn").first.inner_text() == "Speed"  # the active plot, in order
    # preview: three dashed lines in the active plot, or a small chart per axis
    pg.get_by_role("button", name="Preview", exact=True).click()
    pg.wait_for_function("(window.__sv.state().preview?.lines || []).length === 3")
    assert pg.locator(".pv-key-item").all_inner_texts() == ["enu_Vec_ned.E", "enu_Vec_ned.N", "enu_Vec_ned.U"]
    pg.locator(".seg.wide button", has_text="A plot per axis").click()       # time plots under the grid
    pg.get_by_role("button", name="Preview", exact=True).click()
    pg.wait_for_function("document.querySelectorAll('.pv-plot canvas').length >= 3")
    assert pg.locator(".pv-plot .plot-title").all_inner_texts() == ["enu_Vec_ned.E", "enu_Vec_ned.N", "enu_Vec_ned.U"]
    assert len(pg.evaluate("window.__sv.state().ws.tabs[0].plots")) == 1           # not part of the workspace
    pg.get_by_role("button", name="Create 3 signals", exact=True).click()
    # one nested group "enu_Vec_ned" with E / N / U, added to the plot in one step
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 1")
    pg.wait_for_function("document.querySelectorAll('.pv-plot').length === 0")    # creating clears the preview
    assert pg.locator(".dsig-name").inner_text() == "enu_Vec_ned E, N, U"
    pg.wait_for_function("document.querySelectorAll('.plot .chip').length === 6")
    assert {c["sig"] for c in pg.evaluate("window.__sv.state().ws.tabs[0].plots[0].signals")} >= {
        "derived/enu_Vec_ned.E", "derived/enu_Vec_ned.N", "derived/enu_Vec_ned.U"}
    pg.locator(".dsig.grp .chev-btn").click()
    assert pg.locator(".dsig.deep .dsig-name").all_inner_texts() == ["E", "N", "U"]
    # again, each axis in a plot of its own
    pg.locator(".analysis label:has-text('Add the result to') select").select_option("each")
    pg.get_by_role("button", name="Create 3 signals", exact=True).click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.length === 4")
    assert [p["signals"][0]["sig"] for p in pg.evaluate("window.__sv.state().ws.tabs[0].plots")[1:]] == [
        "derived/enu_Vec_ned_2.E", "derived/enu_Vec_ned_2.N", "derived/enu_Vec_ned_2.U"]
    pg.click("[aria-label='Data']")                                           # nested in the file list too
    assert pg.locator(".grp-head .nm").all_inner_texts()[-2:] == ["enu_Vec_ned", "enu_Vec_ned_2"]


def test_frames_suggested_from_names(pg):
    """T30: Frames fills in what the names suggest (a GPS position -> NED; an IMU acceleration ->
    NED with the log's attitude); the user only confirms."""
    d = pg.env["data"]
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_test_bin.py"), os.path.join(d, "frames.bin"), "--seconds", "10"],
                   check=True, capture_output=True)
    open_files(pg, "frames.bin")
    pg.click("[aria-label='Create signals']")
    pg.locator(".analysis .seg.wide button", has_text="Frames").click()
    chips = pg.locator(".frame-sugs .chip-btn")
    chips.first.wait_for()
    assert chips.all_inner_texts()[:2] == ["GPS[0]: LLA → NED", "IMU[0]: Body → NED"]
    assert "on" in chips.first.get_attribute("class")
    pickers = pg.locator(".analysis .picker-btn")
    assert pickers.nth(0).inner_text().startswith("GPS[0].Lat") and pickers.nth(2).inner_text().startswith("GPS[0].Alt")
    chips.nth(1).click()                                                       # the acceleration, with the attitude
    assert pickers.nth(0).inner_text().startswith("IMU[0].AccX")
    assert pickers.nth(3).inner_text().startswith("ATT.Roll")
    assert pg.locator(".analysis label:has-text('Angles in') select").input_value() == "deg"
    pg.get_by_role("button", name="Create 3 signals", exact=True).click()
    pg.wait_for_function("window.__sv.state().runs.some(r => r.format === 'derived' && r.signals.some(s => s.name === 'ned_Vec_body.N'))")


def test_fft_motor_orders(pg):
    """T16b: an FFT plot marks 1x / 2x / 3x the mean rotation rate of an RPM signal (and the
    blade-pass frequency), over the spectrum's window."""
    import numpy as np
    t = np.arange(0, 4, 0.001)
    p = os.path.join(pg.env["data"], "motor.csv")
    np.savetxt(p, np.column_stack([t, 6000 + 0 * t, np.sin(2 * np.pi * 100 * t) + 0.5 * np.sin(2 * np.pi * 200 * t)]),
               delimiter=",", header="Time,ESC.RPM,IMU.AccZ", comments="", fmt="%.6g")
    open_files(pg, "motor.csv")
    pg.locator(".sig", has_text="IMU.AccZ").first.click()
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="FFT").first.click()
    sel = pg.locator(".plot select[aria-label='Motor orders']")
    sel.select_option(label="ESC.RPM")
    pg.wait_for_function("document.querySelector('.plot-canvas[data-orders]')?.dataset.orders === '100.000'")   # 6000 rpm = 100 Hz
    assert S(pg, "s.ws.tabs[0].plots[0].fftOrders.unit") == "rpm"
    pg.locator(".plot select[aria-label='Propeller blades']").select_option("2")
    assert S(pg, "s.ws.tabs[0].plots[0].fftOrders.blades") == 2
    sel.select_option("")                                                       # off again
    pg.wait_for_function("!document.querySelector('.plot-canvas[data-orders]')")


def test_zoom_keys_layout_button_and_split(pg):
    """T19: for one drag Shift zooms the values and Ctrl a box, whatever the zoom mode; T20: one
    layout button with the common layouts and any size; dropping a signal on a plot's right edge
    splits it."""
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")
    assert S(pg, "s.zoomMode") == "x"
    box = pg.locator(".plot .u-over").first.bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    def drag(mod):
        pg.mouse.move(cx - 80, cy - 60)
        if mod: pg.keyboard.down(mod)
        pg.mouse.down(); pg.mouse.move(cx, cy, steps=5); pg.mouse.move(cx + 80, cy + 60, steps=5); pg.mouse.up()
        if mod: pg.keyboard.up(mod)
        pg.wait_for_timeout(150)
    drag("Shift")
    assert S(pg, "Object.keys(s.yRanges).length") == 1 and S(pg, "Object.keys(s.ranges).length") == 0   # values only
    pg.keyboard.press("r")
    drag("Control")
    assert S(pg, "Object.keys(s.yRanges).length") == 1 and S(pg, "Object.keys(s.ranges).length") == 1   # a box
    # the layout button shows the layout and opens the popover
    assert pg.locator(".stage-bar .layout-btn").inner_text().strip() == "1 × 1"
    set_layout(pg, 2, 2)
    assert S(pg, "[s.ws.tabs[0].rows, s.ws.tabs[0].cols]") == [2, 2]
    pg.click(".stage-bar .layout-btn")
    pg.fill(".gridpick input[aria-label='Rows']", "1"); pg.fill(".gridpick input[aria-label='Columns']", "1")
    pg.locator(".gridpick button", has_text="Apply").click()
    assert S(pg, "[s.ws.tabs[0].rows, s.ws.tabs[0].cols, s.ws.tabs[0].plots.length]") == [1, 1, 1]
    # drop RPM on the plot's right edge: a new plot to its right, the grid grows a column
    plot = pg.locator(".plot").first
    pb = plot.bounding_box()
    sig(pg, "RPM").drag_to(plot, target_position={"x": pb["width"] - 12, "y": pb["height"] / 2})
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.length === 2")
    t = S(pg, "s.ws.tabs[0]")
    assert (t["rows"], t["cols"]) == (1, 2) and t["plots"][1]["signals"][0]["sig"].endswith("/RPM") and t["active"] == 1
    assert [x["sig"].split("/")[1] for x in t["plots"][0]["signals"]] == ["Speed"]


def test_middle_click_closes_tab_and_clear_selection_bar(pg):
    """Middle click on a tab closes it (on mousedown / up: on Windows a middle press over the tab
    strip starts autoscroll and no auxclick follows). Searching alone shows no checkboxes; a
    selection bar says what is selected and what it is for; "Plot them" is one undo step."""
    open_files(pg, "run_a.csv")
    pg.click("[aria-label='New tab']")
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 2")
    pg.locator(".tabs .tab").last.click(button="middle")
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 1")
    pg.fill(".filter input", "e")                                              # Speed, Gear
    pg.wait_for_selector(".pick-bar")
    assert pg.locator(".sig-pick").count() == 0                               # no checkboxes just for searching
    pg.fill(".filter input", "")
    sig(pg, "Speed").click(modifiers=["Control"])
    sig(pg, "Gear").click(modifiers=["Control"])
    bar = pg.locator(".pick-actions")
    assert bar.locator(".pick-count").inner_text() == "2 signals selected"
    assert pg.locator(".sig-pick").count() >= 2                               # now they show (and can be unticked)
    assert "Ctrl+click" in bar.locator(".pick-hint").inner_text()
    before = S(pg, "s.past.length")
    bar.get_by_role("button", name="Plot them").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 2")
    assert S(pg, "s.past.length") == before + 1


def test_signal_list_unit_rate_and_picture(pg):
    """T22: each row shows its unit apart from the name (never cut off), its sample rate (wide
    panel, and the tooltip) and a small picture; only rows on screen ask for pictures."""
    t = np.arange(0, 20, 0.01)                                              # 100 Hz
    p = os.path.join(pg.env["data"], "wide_list.csv")
    _csv(p, ["Time"] + [f"Sig{i:03d} [m/s]" for i in range(150)], [t] + [np.sin(t + i) for i in range(150)])
    asked = []
    pg.on("request", lambda r: asked.append(len(json.loads(r.post_data)["signals"])) if r.url.endswith("/api/sparks") else None)
    open_files(pg, "wide_list.csv")
    row = sig(pg, "Sig000")
    row.wait_for()
    assert row.locator(".sig-unit").inner_text() == "m/s" and row.locator(".nm").inner_text() == "Sig000"
    assert "100 Hz" in row.get_attribute("title") and "2,000" in row.get_attribute("title")
    pg.wait_for_function("document.querySelector('.sig .sig-spark path')?.getAttribute('d')?.length > 20")
    assert 0 < sum(asked) < 80                                            # the rows on screen, not all 150
    rs = pg.locator(".resizer").first                                       # a wider panel shows the rate too
    rs.focus(); pg.keyboard.press("Shift+ArrowRight"); pg.keyboard.press("Shift+ArrowRight")
    pg.wait_for_function("getComputedStyle(document.querySelector('.sig .sig-rate')).display !== 'none'")
    assert row.locator(".sig-rate").inner_text() == "100 Hz"


def test_compare_same_segment_across_runs(pg):
    """T10b: Compare runs over a segment - the same value + occurrence of a state signal in each
    file, compared from each one's own start; clicking a signal shows them aligned in a new tab."""
    open_files(pg, "run_a.csv", "run_b.csv", "run_c.csv")
    pg.click("[aria-label='Compare runs']")
    pg.locator(".cmp-panel .seg.wide button", has_text="A segment").click()
    pg.locator(".seg-pick label:has-text('State signal') select").select_option("Gear")
    pg.locator(".seg-pick label:has-text('Value') select").select_option("2")
    pg.wait_for_function("document.querySelectorAll('.seg-wins li').length === 3")
    assert pg.locator(".seg-wins li .when").all_inner_texts() == ["at 12 s, 6 s long"] * 3
    pg.locator(".seg-pick label:has-text('Which one') select").select_option("2")      # Gear is 2 only once
    pg.wait_for_function("[...document.querySelectorAll('.seg-wins li')].every(li => li.classList.contains('missing'))")
    assert "fewer than two files" in pg.locator(".cmp-panel").inner_text().lower()
    pg.locator(".seg-pick label:has-text('Which one') select").select_option("1")
    pg.wait_for_selector(".sim-row:has-text('Speed')", timeout=20000)
    pg.locator(".sim-row", has_text="Speed").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name === 'Gear = 2 · #1')")
    sigs = S(pg, "s.ws.tabs.find(t => t.name === 'Gear = 2 · #1').plots[0].signals.map(x => x.tOffset)")
    assert sigs == [-12, -12, -12]
    tab_id = S(pg, "s.ws.tabs.find(t => t.name === 'Gear = 2 · #1').id")
    assert S(pg, f"s.ranges['{tab_id}']") == [0, 6]                         # from the segment start, its length


def test_smart_start_card(pg):
    """T29: the first file into an empty workspace gets a card: the best-fitting template (opened
    on request only) and, for a flight log, the worst findings of its health check."""
    d = pg.env["data"]
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_test_bin.py"), os.path.join(d, "start.bin"), "--seconds", "40"],
                   check=True, capture_output=True)
    open_files(pg, "start.bin")
    card = pg.locator(".start-card")
    card.wait_for(timeout=20000)
    assert "ArduPilot" in card.locator(".start-tpl b").inner_text()
    rows = card.locator(".hrow")
    assert 1 <= rows.count() <= 3 and "error" in rows.first.get_attribute("class")      # the worst first
    assert S(pg, "s.ws.tabs.every(t => t.plots.every(p => !p.signals.length))")         # nothing applied by itself
    rows.first.locator(".pchange.span").first.click()                                  # jump to the finding
    pg.wait_for_function("window.__sv.state().cursor.dual")
    card.get_by_role("button", name="Open it").click()
    pg.wait_for_function("!document.querySelector('.start-card .start-tpl')")       # T48: the findings stay
    assert S(pg, "s.ws.tabs.some(t => t.plots.some(p => p.signals.length))")
    pg.locator(".start-card .dialog-head button, .start-card button.iconbtn").first.click()
    pg.wait_for_function("!document.querySelector('.start-card')")
    # not again once the workspace has plots
    open_files(pg, "run_a.csv", clear=False)
    pg.wait_for_timeout(1500)
    assert pg.locator(".start-card").count() == 0


def test_live_mavlink(pg):
    """T12: Live > MAVLink records the link to a .tlog, opens it and follows it in live mode;
    Disconnect keeps the recording."""
    import socket as _s, threading
    from pymavlink.dialects.v20 import ardupilotmega as mavlink
    port = _free_port()                                   # a TCP port number is free for UDP as well, in practice
    pg.click(".live-more")
    pg.locator(".mav-section input[list]").fill(f"udpin:127.0.0.1:{port}")
    pg.get_by_role("button", name="Connect and record").click()
    pg.wait_for_function("window.__sv.state().mavlink?.running === true")
    stop = threading.Event()

    def vehicle():
        sock = _s.socket(_s.AF_INET, _s.SOCK_DGRAM)
        mav = mavlink.MAVLink(None, srcSystem=1, srcComponent=1)
        t0 = time.time()
        while not stop.is_set():
            ms = int((time.time() - t0) * 1000)
            sock.sendto(mav.heartbeat_encode(2, 3, 81, 4, 4).pack(mav), ("127.0.0.1", port))
            sock.sendto(mav.attitude_encode(ms, ms / 1000.0, 0, 0, 0, 0, 0).pack(mav), ("127.0.0.1", port))
            time.sleep(0.05)
        sock.close()

    th = threading.Thread(target=vehicle, daemon=True)
    th.start()
    try:
        pg.wait_for_function("window.__sv.state().runs.some(r => r.format === 'tlog')", timeout=15000)
        pg.wait_for_function("window.__sv.state().streaming", timeout=10000)
        n1 = S(pg, "s.runs.find(r => r.format === 'tlog').samples")
        pg.wait_for_function(f"window.__sv.state().runs.find(r => r.format === 'tlog').samples > {n1 + 10}", timeout=10000)
        assert pg.locator(".mav-pill").is_visible()
        pg.click(".mav-pill")
        pg.get_by_role("button", name="Disconnect", exact=True).click()
        pg.wait_for_function("window.__sv.state().mavlink?.running === false")
        path = S(pg, "s.mavlink.path")
        assert path.endswith(".tlog") and os.path.getsize(path) > 0
        assert S(pg, "s.runs.some(r => r.path === s.mavlink.path)")      # the recording stays open
    finally:
        stop.set(); th.join(2)


PAINTED = """(sel) => { const c = document.querySelector(sel); if (!c || !c.width) return false;
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    for (let i = 3; i < d.length; i += 4) if (d[i]) return true; return false; }"""


def test_xyz_plot_and_place_on_map(pg):
    """T17c: a plain 3D plot of any three signals (no map), its options, and putting the track on
    a new map plot from a typed-in origin - three derived signals and an object."""
    open_files(pg, "run_a.csv")
    for n in ("Speed", "RPM", "Gear"):
        sig(pg, n).click()
    pg.locator(".plot.active .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="XYZ").first.click()
    pg.wait_for_function(PAINTED, arg=".plot.active .xyz-canvas")                # the box and the track are drawn
    assert "Drag: rotate" in pg.locator(".plot.active .xyz-hint").inner_text()
    eq = pg.locator(".plot.active button", has_text="Equal scale")
    assert eq.get_attribute("aria-pressed") == "true"
    eq.click()
    assert eq.get_attribute("aria-pressed") == "false"
    box = pg.locator(".plot.active .xyz-canvas").bounding_box()                  # rotating keeps it drawn
    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    pg.mouse.down(); pg.mouse.move(box["x"] + box["width"] / 2 + 80, box["y"] + box["height"] / 2 + 30); pg.mouse.up()
    assert pg.evaluate(PAINTED, ".plot.active .xyz-canvas")
    pg.locator(".plot.active button", has_text="Place on map").click()
    dlg = pg.locator(".dialog[aria-label='Place on map']")
    dlg.locator("label:has-text('Origin') select").select_option("manual")    # no GPS in this file
    for k, v in zip(("Latitude", "Longitude", "Altitude"), ("32.1", "34.8", "10")):
        dlg.locator(f"input[aria-label='{k}']").fill(v)
    dlg.locator("label:has-text('Show on') select").select_option("new-geo")
    dlg.get_by_role("button", name="Place", exact=True).click()
    pg.wait_for_selector(".dialog[aria-label='Place on map']", state="detached")
    pg.wait_for_function("""window.__sv.state().ws.tabs.some(t => t.plots.some(p => p.mode === 'geo'
        && (p.objects || []).length === 1 && p.objects[0].lat.startsWith('derived/')))""")
    assert pg.locator(".obj-chip").count() == 1


def test_globe_without_webgl_falls_back(pg):
    """A computer without WebGL (Chrome / Edge 139+ no longer fall back to software): the 3D view
    shows the objects' tracks in metres on the 2D canvas instead of nothing."""
    open_files(pg, "geo.csv")
    p2 = pg.context.new_page()
    p2.add_init_script("""(() => { const get = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function (k, ...a) { return /webgl/i.test(k) ? null : get.call(this, k, ...a); }; })()""")
    try:
        p2.goto(pg.url); p2.wait_for_selector(".app")
        p2.evaluate("fetch('/api/runs').then(r => r.json()).then(runs => window.__sv.setState({ runs }))")
        p2.wait_for_function("window.__sv.state().runs.some(r => r.name.startsWith('geo'))")
        rid = p2.evaluate("window.__sv.state().runs.find(r => r.name.startsWith('geo')).id")
        p2.evaluate(f"""window.__sv.setState({{ ws: (() => {{ const ws = structuredClone(window.__sv.state().ws); const p = ws.tabs[0].plots[0];
            p.mode = '3d'; p.objects = [{{ id: 'a', name: 'Test', kind: 'uav', color: '#ff3030', lat: '{rid}/Lat', lon: '{rid}/Lon' }}];
            return ws; }})() }})""")
        p2.wait_for_selector(".g3-nowebgl")
        p2.wait_for_function(PAINTED, arg=".xyz-canvas")
        assert "No WebGL" in p2.locator(".g3-nowebgl").inner_text()
    finally:
        p2.close()


def test_play_draw_mode_and_clear_everything(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.locator(".timeline select[aria-label='What the plots show']").select_option("draw")   # the timeline
    pg.keyboard.press("p"); pg.wait_for_timeout(400); pg.keyboard.press("p")
    assert S(pg, "s.playMode") == "draw" and S(pg, "s.cursor.t1") > 0
    pg.click(".topbar .menubar-btn:has-text('File')"); pg.click(".menu.ctx button:has-text('Clear everything')")
    pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".welcome")
    assert S(pg, "s.runs.length") == 0


def test_layout_picker_not_clipped(pg):
    pg.click(".stage-bar .pick-wrap .btn")
    box = pg.locator(".gridpick").bounding_box()
    assert pg.locator(".gridpick-type input").first.is_visible() and box["height"] > 120



def test_no_automatic_plot_and_linked_remove(pg):
    open_files(pg, "run_a.csv", "run_b.csv", clear=False)
    pg.wait_for_timeout(400)
    assert chips(pg) == []                                                # nothing plotted on open
    pg.click(".link-toggle")
    sig(pg, "RPM").click()
    assert len(chips(pg)) == 2
    pg.locator(".plot .chip").first.locator(".rm").click()               # removing one removes the linked one
    assert chips(pg) == []


# ======================================================= round: ideas
def test_hover_readout_without_cursor(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")
    box = pg.locator(".plot .u-over").first.bounding_box()
    pg.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
    pg.wait_for_selector(".chip .val.hov")
    assert pg.locator(".hover-t").inner_text().startswith("t =")
    pg.mouse.move(box["x"] - 40, box["y"] - 40)
    pg.wait_for_selector(".chip .val.hov", state="detached")


def test_units_from_names(pg):
    p = os.path.join(pg.env["data"], "units.csv")
    t = np.arange(0, 5, 0.01)
    _csv(p, ["Time", "Speed [km/h]", "imu[1]"], [t, t * 10, t])
    open_files(pg, "units.csv")
    sig(pg, "Speed").click()                         # T22: the row shows the name, the unit on its own
    pg.keyboard.press("Space")
    pg.wait_for_function("[...document.querySelectorAll('.chip .val')].some(e => e.innerText.endsWith('km/h'))")
    sig(pg, "imu[1]").click()                       # "[1]" is not a unit
    pg.wait_for_function("[...document.querySelectorAll('.chip .val')].length === 2")
    assert not any(v.endswith("1") and " " in v for v in pg.locator(".chip .val").all_inner_texts()[1:])


def test_templates_save_and_apply(pg):
    open_files(pg, "run_a.csv", "run_b.csv")
    set_layout(pg, 2, 1)
    pg.keyboard.press("1"); sig(pg, "Speed").click()
    pg.keyboard.press("2"); sig(pg, "RPM").click()
    pg.locator(".tab").first.click(button="right"); menu_item(pg, "Save as template")
    pg.locator(".tpl-editor input").first.fill("Engine check")              # the library opens on a new template of this tab
    assert pg.locator(".tpl-used-files li").all_inner_texts()[0].startswith("run_a.csv")   # one file, found from the tab
    pg.locator(".tpl-editor .btn.primary").click()
    pg.wait_for_selector(".toast:has-text('saved')")
    pg.wait_for_selector(".tpl-details h3:has-text('Engine check')")
    pg.wait_for_selector(".tpl-found")                       # the counts come from the server (T11b): wait for them
    assert pg.locator(".tpl-found").all_inner_texts() == ["2 of 2 signals"]
    pg.locator(".tpl-slot select").first.select_option(label="All files that fit (overlaid)")
    pg.locator(".tpl-actions .btn.primary").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 2")
    sigs = S(pg, "s.ws.tabs[1].plots.map(p => p.signals.length)")
    assert S(pg, "s.ws.tabs[1].name") == "Engine check" and sigs == [2, 2]     # both files, each in its slot


def test_recent_files_on_welcome(pg):
    open_files(pg, "run_a.csv")
    pg.click(".topbar .menubar-btn:has-text('File')"); pg.click(".menu.ctx button:has-text('Clear everything')"); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".recent-row")
    pg.locator(".recent-open", has_text="run_a.csv").first.click()
    pg.wait_for_function("window.__sv.state().runs.length === 1")


def test_import_settings_remembered_per_folder(pg):
    folder = os.path.join(pg.env["out"], "meta_folder"); os.makedirs(folder, exist_ok=True)
    shutil.copy(os.path.join(pg.env["data"], "meta.csv"), os.path.join(folder, "m1.csv"))
    shutil.copy(os.path.join(pg.env["data"], "meta.csv"), os.path.join(folder, "m2.csv"))
    shutil.copy(os.path.join(pg.env["data"], "run_a.csv"), os.path.join(folder, "plain.csv"))
    pg.keyboard.press("Control+o"); goto_folder(pg, folder)
    pg.locator(".dialog .dialog-body .fs-row", has_text="m1.csv").click()
    pg.locator(".dialog-foot input[type=checkbox]").check(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector("table.preview")
    pg.locator(".import-grid input[type=number]").first.fill("2"); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function("window.__sv.state().runs.length === 1")
    pg.keyboard.press("Control+o"); goto_folder(pg, folder)                 # same folder, no options
    pg.locator(".dialog .dialog-body .fs-row", has_text="m2.csv").click(); pg.click(".dialog-foot .btn.primary")
    try:
        pg.wait_for_selector(".toast:has-text('remembered')", timeout=6000)
    except Exception:
        print("DBG toasts:", pg.locator(".toast").all_inner_texts(), "runs:", S(pg, "s.runs.map(r => [r.name, r.samples, JSON.stringify(r.report)])"))
        raise
    pg.keyboard.press("Control+o"); goto_folder(pg, folder)
    pg.locator(".dialog .dialog-body .fs-row", has_text="plain.csv").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function("window.__sv.state().runs.length === 3")
    assert S(pg, "s.runs.find(r => r.name === 'plain.csv').samples") == 3000   # NOT misread by the folder memory


def test_regression_fft_plot_survives_signal_swap(pg):
    """Swapping the signals of an FFT plot (e.g. from the similarity list) once blanked the whole app."""
    open_files(pg, "run_a.csv", "run_c.csv")
    sig(pg, "Speed").click()
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="FFT").first.click()
    pg.wait_for_timeout(600)
    pg.click("[aria-label='Compare runs']")
    pg.wait_for_selector(".sim-row")
    pg.locator(".sim-row", has_text="RPM").click()
    pg.wait_for_timeout(1000)
    assert pg.locator(".rail button").count() >= 4            # the app is still there
    assert pg.locator(".plot-error").count() == 0
    assert len(chips(pg)) == 2


def test_values_on_plot_toggle(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.keyboard.press("Space")
    box = pg.locator(".inspector input[type=checkbox]").first
    box.check()
    assert box.is_checked() and S(pg, "s.valuesOnPlot") is True
    box.uncheck()
    assert S(pg, "s.valuesOnPlot") is False


def test_escape_closes_dialogs_wherever_focus_is(pg):
    open_files(pg, "run_a.csv", "run_b.csv")
    pg.click("[aria-label='Compare runs']")
    pg.wait_for_selector(".sim-row")
    pg.click(".cmp-panel .btn:has-text('Table of all signals')")
    pg.wait_for_selector(".cmp-dialog")
    pg.locator(".cmp-row").first.click()                 # focus leaves the dialog's input
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".cmp-dialog", state="detached")


def test_regression_second_cursor_visible_after_play_and_zoom(pg):
    """Cursor 2 was placed after cursor 1 without checking the shown range (off-screen after Play)."""
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.keyboard.press("Space")
    pg.locator(".ctime input").first.fill("29.9"); pg.keyboard.press("Enter")     # cursor 1 at the very end
    pg.keyboard.press("d")
    t1, t2 = S(pg, "s.cursor.t1"), S(pg, "s.cursor.t2")
    assert 0 <= t2 <= 30 and t2 < t1                       # inside the range, before cursor 1
    pg.keyboard.press("d")                                  # off again
    pg.wait_for_selector(".plot .u-over")
    box = pg.locator(".plot .u-over").first.bounding_box()
    pg.mouse.move(box["x"] + box["width"] * 0.2, box["y"] + 50); pg.mouse.wheel(0, -600); pg.wait_for_timeout(300)
    r = S(pg, "Object.values(s.ranges)[0]")
    pg.keyboard.press("d")                                  # zoomed in: both cursors inside the view
    t1, t2 = S(pg, "s.cursor.t1"), S(pg, "s.cursor.t2")
    assert r[0] <= t1 <= r[1] and r[0] <= t2 <= r[1]


def test_change_many_variables_from_search(pg):
    """Search "sig_0", pick all results (or one file's), change the variables THEMSELVES."""
    t = np.arange(0, 10, 0.01)
    names = [f"sig_{a}_{b}" for a in range(2) for b in range(1, 4)]
    for fname, gain in (("fa.csv", 1.0), ("fb.csv", 2.0)):
        _csv(os.path.join(pg.env["data"], fname), ["Time"] + names, [t] + [gain * np.sin(t + i) for i in range(len(names))])
    open_files(pg, "fa.csv", "fb.csv")
    pg.fill(".filter input", "sig_0")
    pg.wait_for_selector(".pick-bar")
    assert pg.locator(".pick-bar").inner_text().startswith("6 results")
    pg.locator(".pick-bar select").select_option(index=1)                 # only in the first file
    assert pg.locator(".pick-count").inner_text().startswith("3")
    pg.click(".pick-bar .linklike")                                         # all results (both files)
    assert pg.locator(".pick-count").inner_text().startswith("6")
    pg.locator(".sig-wrap", has_text="sig_0_3").nth(1).locator("input").uncheck()   # leave one out by hand
    pg.click(".pick-actions .btn:has-text('Change them')")
    pg.wait_for_selector(".tf-dialog")
    pg.locator(".tf-dialog select").select_option("abs")
    inputs = pg.locator(".tf-dialog .arow input")
    inputs.nth(0).fill("10"); inputs.nth(1).fill("5")
    assert pg.locator(".tf-result").inner_text() == "y = 10·abs(x) + 5"
    pg.click(".tf-dialog .btn.primary")
    pg.wait_for_selector(".toast:has-text('applied to 5')")
    changed = S(pg, "s.runs.flatMap(r => r.signals.filter(x => x.transform).map(x => r.name + ':' + x.name))")
    assert len(changed) == 5 and "fb.csv:sig_0_3" not in changed and pg.locator(".tf-badge").count() >= 5
    rid = S(pg, "s.runs.find(r => r.name === 'fa.csv').id")
    st = json.loads(urllib.request.urlopen(urllib.request.Request(pg.env["url"] + "/api/stats",
        json.dumps({"signals": [f"{rid}/sig_0_1"]}).encode(), {"Content-Type": "application/json"})).read())["stats"][f"{rid}/sig_0_1"]
    assert abs(st["min"] - 5) < 0.05 and abs(st["max"] - 15) < 0.05      # 10·|sin| + 5
    pg.locator(".toast", has_text="applied to 5").locator("button", has_text="Undo").click()
    pg.wait_for_function("window.__sv.state().runs.every(r => r.signals.every(x => !x.transform))")
    # re-apply, then reload: the change is kept with the workspace
    pg.click(".pick-actions .btn:has-text('Change them')"); pg.locator(".tf-dialog .arow input").nth(0).fill("3"); pg.click(".tf-dialog .btn.primary")
    pg.wait_for_selector(".toast:has-text('applied')")
    pg.wait_for_timeout(1500)
    pg.reload(); pg.wait_for_selector(".run-head")
    pg.wait_for_function("window.__sv.state().runs.flatMap(r => r.signals).filter(x => x.transform && x.transform.scale === 3).length === 5")


def test_regression_select_all_takes_only_search_results(pg):
    """A plotted signal (no 'r' in its name) was silently pre-chosen, and "select all" ADDED the
    search results to it: the operation then also ran on the plotted signal."""
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()                                   # plotted; must NOT be chosen silently
    pg.click("[aria-label='Create signals']")
    pg.locator(".seg.wide button", has_text="Each of several").click()
    assert pg.locator(".msp-count").inner_text().startswith("0")
    pg.fill(".msp-filter input", "r")
    pg.click(".msp-actions .btn:has-text('Choose these')")
    chosen = pg.locator(".msp-chip").all_inner_texts()
    assert sorted(c.split("·")[0].strip() for c in chosen) == ["Gear", "RPM"]
    pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 2")
    names = pg.locator(".dsig-name").all_inner_texts()
    assert not any("Speed" in n for n in names), names


def test_edit_original_steps_and_undo_all(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.click("[aria-label='Create signals']")
    pg.locator(".seg.wide button", has_text="Edit the original").click()
    pg.locator(".analysis .afield select").first.select_option("abs")
    pg.click("text=Apply to the original")
    pg.wait_for_function("window.__sv.state().runs[0].signals.find(x => x.name === 'Speed').transform?.expr === 'abs(x)'")
    pg.locator(".analysis .afield select").first.select_option("smooth")
    pg.click("text=Apply to the original")                     # steps add up
    pg.wait_for_function("window.__sv.state().runs[0].signals.find(x => x.name === 'Speed').transform?.expr === 'smooth(abs(x), 10)'")
    assert S(pg, "s.runs[0].signals.filter(x => !x.transform).length") == 2   # nothing else touched
    pg.locator(".seg.wide button", has_text="New signal").click()
    pg.get_by_role("button", name="Create signal", exact=True).click(); pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 2")
    pg.click(".bulk-undo .btn:has-text('Remove all edits')")
    pg.wait_for_function("window.__sv.state().runs[0].signals.every(x => !x.transform)")
    pg.click(".bulk-undo .btn:has-text('Delete all derived')")
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 0")
    pg.locator(".toast", has_text="derived signals deleted").locator("button:has-text('Undo')").click()
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 2")


def test_delete_all_derived_undo_never_overwrites_later_changes(pg):
    """F12: the Undo of "Delete all derived" restored the old workspace directly and stayed on screen
    after later changes - clicking it then wiped them. Now it goes with the next change, and when used
    it puts the signals back into the plots as an undo step."""
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.click("[aria-label='Create signals']")
    pg.locator(".seg.wide button", has_text="New signal").click()
    pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 1")
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.plots.some(p => p.signals.some(s => s.sig.startsWith('derived/'))))")
    in_plots = "window.__sv.state().ws.tabs.some(t => t.plots.some(p => p.signals.some(s => s.sig.startsWith('derived/'))))"
    # 1) Undo right away: the derived signal is back in its plot, and Ctrl+Z takes that back
    pg.click(".bulk-undo .btn:has-text('Delete all derived')")
    pg.wait_for_function(f"!({in_plots})")
    pg.locator(".toast", has_text="derived signals deleted").locator("button:has-text('Undo')").click()
    pg.wait_for_function(in_plots)
    # 2) a change after the delete: the Undo is gone, the change stays
    pg.click(".bulk-undo .btn:has-text('Delete all derived')")
    pg.wait_for_function(f"!({in_plots})")
    pg.wait_for_function("window.__sv.state().toasts.some(t => t.text.includes('derived signals deleted'))")
    # the change and the check in ONE call: toasts also go by themselves after a few seconds
    still = pg.evaluate("""() => { const st = window.__sv.state();
        st.commit(ws => { ws.tabs[0].name = 'after'; return ws; });
        return window.__sv.state().toasts.some(t => t.text.includes('derived signals deleted')); }""")
    assert not still, "the Undo of the delete must go with the next workspace change"
    assert S(pg, "s.ws.tabs[0].name") == "after"


def test_ctrl_shift_selection_in_file_list(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click(modifiers=["Control"])
    sig(pg, "Gear").click(modifiers=["Shift"])
    assert pg.locator(".pick-count").inner_text().startswith("3")
    assert chips(pg) == []                                     # selecting does not plot
    sig(pg, "RPM").click(modifiers=["Control"])                # toggle one off
    assert pg.locator(".pick-count").inner_text().startswith("2")
    pg.click(".pick-actions .btn:has-text('Change them')")
    pg.wait_for_selector(".tf-dialog")
    pg.locator(".tf-dialog .arow input").nth(0).fill("2"); pg.click(".tf-dialog .btn.primary")
    pg.wait_for_function("window.__sv.state().runs[0].signals.filter(x => x.transform).length === 2")
    assert pg.locator(".tf-badge").count() == 2


def test_refresh_and_live_follow_the_file(pg):
    """Refresh after editing the file, live mode with appended rows and with a full re-save."""
    p = os.path.join(pg.env["data"], "edit_me.csv")
    def save(n, v):
        open(p, "w", encoding="utf-8-sig", newline="").write("Time,A\r\n" + "".join(f"{i * 0.01:.2f},{v}\r\n" for i in range(n)))
    save(400, "1.0")
    open_files(pg, "edit_me.csv")
    sig(pg, "A").click()
    stat_max = lambda: json.loads(urllib.request.urlopen(urllib.request.Request(pg.env["url"] + "/api/stats",
        json.dumps({"signals": [S(pg, "s.runs[0].signals[0].id")]}).encode(), {"Content-Type": "application/json"})).read())["stats"].popitem()[1]["max"]
    time.sleep(1.1); save(400, "5.0")
    pg.locator(".run-head").first.hover(); pg.locator(".run-head [aria-label='Reload from disk']").click()
    pg.wait_for_selector(".toast:has-text('reloaded')")
    assert stat_max() == 5.0
    pg.click(".topbar .btn:has-text('Live')")
    with open(p, "a", newline="") as f:
        f.write("".join(f"{5 + i * 0.01:.2f},9.0\r\n" for i in range(30)))
    pg.wait_for_function("window.__sv.state().runs[0].samples === 430", timeout=8000)
    time.sleep(1.1); save(430, "2.0")                                    # full re-save, same row count
    pg.wait_for_function("window.__sv.state().dataVersion > 0", timeout=4000)
    for _ in range(40):
        if stat_max() == 2.0: break
        pg.wait_for_timeout(200)
    assert stat_max() == 2.0


def test_dragged_copy_is_marked_and_can_switch_to_the_original(pg):
    p = os.path.join(pg.env["data"], "dragged.csv")
    open(p, "w").write("Time,A\n" + "".join(f"{i * 0.01:.2f},1.0\n" for i in range(300)))
    # a modified time that matches no file on disk: the original cannot be found -> a copy
    pg.evaluate("""(text) => {
        const dt = new DataTransfer(); dt.items.add(new File([text], 'dragged.csv', { type: 'text/csv', lastModified: 1000 }));
        for (const type of ['dragenter', 'dragover', 'drop']) window.dispatchEvent(new DragEvent(type, { dataTransfer: dt, bubbles: true }));
    }""", open(p).read())
    pg.wait_for_selector(".badge-copy")                                  # the list says it is a copy
    pg.locator(".run-head").first.hover(); pg.locator(".run-head [aria-label='Reload from disk']").click()
    pg.wait_for_selector(".toast:has-text('opened as a copy')")
    pg.locator(".toast button:has-text('Choose the original')").first.click()
    goto_folder(pg, pg.env["data"])
    pg.locator(".dialog .dialog-body .fs-row", has_text="dragged.csv").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".badge-copy", state="detached")
    assert S(pg, "s.runs[0].path") == p


def test_dragged_file_opens_from_the_original(pg):
    """No copy when the original can be found: same name, size and modified time."""
    open_files(pg, "run_a.csv")                                  # its folder is now a known place
    p = os.path.join(pg.env["data"], "located.csv")
    text = "Time,A\n" + "".join(f"{i * 0.01:.2f},1.0\n" for i in range(200))
    open(p, "w", newline="").write(text)
    mtime_ms = int(os.stat(p).st_mtime * 1000)
    pg.evaluate("""([text, ms]) => {
        const dt = new DataTransfer(); dt.items.add(new File([text], 'located.csv', { type: 'text/csv', lastModified: ms }));
        for (const type of ['dragenter', 'dragover', 'drop']) window.dispatchEvent(new DragEvent(type, { dataTransfer: dt, bubbles: true }));
    }""", [text, mtime_ms])
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name === 'located.csv')", timeout=10000)
    run = S(pg, "s.runs.find(r => r.name === 'located.csv')")
    assert run["path"] == p and not run.get("copy") and pg.locator(".badge-copy").count() == 0


def test_file_dialog_sorts_by_last_modified(pg):
    folder = os.path.join(pg.env["out"], "sorted"); os.makedirs(folder, exist_ok=True)
    now = time.time()
    for i, name in enumerate(["a_old.csv", "z_new.csv", "m_mid.csv"]):
        f = os.path.join(folder, name); open(f, "w").write("Time,A\n0,1\n")
        os.utime(f, (now - [300, 10, 100][i],) * 2)
    for name, age in (("dir_newest", 5), ("dir_oldest", 400)):          # folders mix in by date
        d = os.path.join(folder, name); os.makedirs(d, exist_ok=True); os.utime(d, (now - age,) * 2)
    pg.keyboard.press("Control+o"); goto_folder(pg, folder)
    names = lambda: [x.strip() for x in pg.locator(".dialog .dialog-body .fs-row span:first-of-type").all_inner_texts()]
    pg.wait_for_selector(".dialog .dialog-body .fs-row:has-text('a_old.csv')")
    assert names() == ["dir_newest", "z_new.csv", "m_mid.csv", "a_old.csv", "dir_oldest"]   # newest first, mixed
    pg.click(".fs-sort button:has-text('Name')")
    assert names() == ["dir_newest", "dir_oldest", "a_old.csv", "m_mid.csv", "z_new.csv"]   # by name: folders first
    pg.keyboard.press("Escape")
    pg.keyboard.press("Control+o"); goto_folder(pg, folder)
    pg.wait_for_selector(".dialog .dialog-body .fs-row:has-text('a_old.csv')")
    assert names()[2] == "a_old.csv"                               # the choice is remembered


def test_open_with_new_files(pg):
    """Same work, new runs: layout, formulas and edits carry over to new input files."""
    folder = os.path.join(pg.env["out"], "runs"); os.makedirs(folder, exist_ok=True)
    t = np.arange(0, 10, 0.01); now = time.time()
    for name, gain, age, cols in (("run_012.csv", 1.0, 300, ["Speed", "RPM"]), ("run_013.csv", 3.0, 20, ["Speed", "RPM"]),
                                  ("run_014.csv", 2.0, 100, ["Speed", "RPM"]), ("partial.csv", 1.0, 10, ["Speed"])):
        f = os.path.join(folder, name)
        _csv(f, ["Time"] + cols, [t] + [gain * (i + 1) * np.sin(t) for i in range(len(cols))])
        os.utime(f, (now - age,) * 2)
    pg.keyboard.press("Control+o"); goto_folder(pg, folder)
    pg.locator(".dialog .dialog-body .fs-row", has_text="run_012.csv").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".sig")
    sig(pg, "Speed").click(); sig(pg, "RPM").click()
    rid = S(pg, "s.runs[0].id")
    post = lambda url, body: json.loads(urllib.request.urlopen(urllib.request.Request(pg.env["url"] + url, json.dumps(body).encode(), {"Content-Type": "application/json"})).read())
    post("/api/transforms", {"signals": [f"{rid}/RPM"], "transform": {"scale": 10}})
    pg.click("[aria-label='Create signals']"); pg.click(".seg.wide button:has-text('Formula')")
    pg.fill(".fx-input", "2*Speed"); pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("document.querySelectorAll('.dsig').length === 1")
    pg.click("[aria-label='Data']")
    chips_before = chips(pg)
    pg.locator(".side-head [aria-label='Replace the input files…']").click()
    pg.wait_for_selector(".rt-dialog")
    pg.wait_for_selector(".rt-status.ok")
    assert pg.locator(".rt-pick select").input_value().endswith("run_013.csv")       # newest with the same pattern
    assert "All 2 signals" in pg.locator(".rt-status").inner_text()
    pg.locator(".rt-pick select").select_option(os.path.join(folder, "partial.csv"))  # a file without RPM
    pg.wait_for_selector(".rt-status.missing:has-text('RPM')")
    pg.locator(".rt-pick select").select_option(os.path.join(folder, "run_013.csv"))
    pg.wait_for_selector(".rt-status.ok")
    pg.click(".rt-dialog .btn.primary")
    pg.wait_for_selector(".toast:has-text('Opened with 1 new files')")
    run = S(pg, "s.runs.find(r => r.format !== 'derived')")
    assert run["path"].endswith("run_013.csv") and run["name"] == "run_013.csv" and run["id"] == rid
    assert len(chips(pg)) == len(chips_before) == 3                                    # layout kept (incl. the formula)
    pg.click("[aria-label='Create signals']"); assert pg.locator(".dsig").count() == 1; pg.click("[aria-label='Data']")
    rpm = post("/api/stats", {"signals": [f"{rid}/RPM"]})["stats"][f"{rid}/RPM"]
    assert abs(rpm["max"] - 60) < 0.5                                                  # run_013's RPM (3*2) x the edit (10)
    pg.locator(".toast button:has-text('Back to the previous files')").click()
    pg.wait_for_function("window.__sv.state().runs.some(r => r.path.endsWith('run_012.csv'))")


def test_open_saved_session_with_new_files_from_welcome(pg):
    folder = os.path.join(pg.env["out"], "runs2"); os.makedirs(folder, exist_ok=True)
    t = np.arange(0, 5, 0.01); now = time.time()
    for name, gain, age in (("bench_001.csv", 1.0, 200), ("bench_002.csv", 4.0, 10)):
        f = os.path.join(folder, name); _csv(f, ["Time", "Speed"], [t, gain * np.sin(t)]); os.utime(f, (now - age,) * 2)
    pg.keyboard.press("Control+o"); goto_folder(pg, folder)
    pg.locator(".dialog .dialog-body .fs-row", has_text="bench_001.csv").click(); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".sig"); sig(pg, "Speed").click()
    pg.keyboard.press("Control+s"); save_as(pg, "bench_session")
    pg.wait_for_selector(".toast:has-text('bench_session')")
    pg.click(".topbar .menubar-btn:has-text('File')"); pg.click(".menu.ctx button:has-text('Clear everything')"); pg.click(".dialog-foot .btn.primary")
    pg.wait_for_selector(".recent-row:has-text('bench_session')")
    pg.locator(".recent-row", has_text="bench_session").locator("[aria-label='With new files…']").click()
    pg.wait_for_selector(".rt-dialog .rt-status.ok")
    assert pg.locator(".rt-pick select").input_value().endswith("bench_002.csv")
    pg.click(".rt-dialog .btn.primary")
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name === 'bench_002.csv')")
    assert len(chips(pg)) == 1


# ======================================================= round: arrows, 3x3, map, states only, refresh
def test_layout_3x3_quick_button(pg):
    open_files(pg, "run_a.csv")
    set_layout(pg, 3, 3)
    assert pg.locator(".plot").count() == 9 and S(pg, "[s.ws.tabs[0].rows, s.ws.tabs[0].cols]") == [3, 3]
    pg.keyboard.press("9")
    assert S(pg, "s.ws.tabs[0].active") == 8


def test_arrow_keys_jump_between_samples_without_interpolation(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")
    pg.keyboard.press("Space")
    pg.evaluate("window.__sv.state().set({cursor: {...window.__sv.state().cursor, t1: 10.004}})")   # between samples
    pg.keyboard.press("ArrowRight")
    pg.wait_for_function("Math.abs(window.__sv.state().cursor.t1 - 10.01) < 1e-9")
    pg.keyboard.press("ArrowRight"); pg.keyboard.press("ArrowRight")
    pg.wait_for_function("Math.abs(window.__sv.state().cursor.t1 - 10.03) < 1e-9")
    pg.keyboard.press("ArrowLeft")
    pg.wait_for_function("Math.abs(window.__sv.state().cursor.t1 - 10.02) < 1e-9")
    pg.keyboard.press("Shift+ArrowRight")
    pg.wait_for_function("Math.abs(window.__sv.state().cursor.t1 - 10.12) < 1e-9")
    # the value read is the recorded one
    rid = S(pg, "s.runs[0].id")
    pg.wait_for_function("window.__sv.state().cvals['%s/Speed'] !== undefined" % rid)
    t = np.arange(0, 30, 0.01)
    expect = 20 + 10 * np.tanh(10.12 - 5) - 8 * np.tanh(10.12 - 20)
    assert abs(S(pg, "s.cvals['%s/Speed'][0]" % rid) - expect) < 1e-3


def test_arrow_keys_move_the_cursor_that_was_clicked_last(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_selector(".plot .u-over")
    pg.keyboard.press("Space"); pg.keyboard.press("d")
    pg.wait_for_function("window.__sv.state().cursor.dual")
    pg.evaluate("window.__sv.state().set({cursor: {...window.__sv.state().cursor, t1: 5, t2: 8, active: 2}})")
    pg.keyboard.press("ArrowRight")
    pg.wait_for_function("Math.abs(window.__sv.state().cursor.t2 - 8.01) < 1e-9")
    assert S(pg, "s.cursor.t1") == 5


def test_map_plot_draws_track_on_world_outline(pg):
    open_files(pg, "geo.csv")
    sig(pg, "Lat").click(); sig(pg, "Lon").click()
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="Map").first.click()
    pg.wait_for_selector(".plot .geo canvas")
    assert S(pg, "s.ws.tabs[0].plots[0].xSignal.endsWith('/Lon')")          # Lon chosen as the X (longitude) signal
    assert chips(pg) == ["Lat"]
    pg.wait_for_timeout(600)
    # pixels were drawn (land outline / track), not an empty canvas
    assert pg.evaluate("""(() => { const c = document.querySelector('.plot .geo canvas');
        const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0;
        for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n })()""") > 1000
    pg.keyboard.press("Space")                                               # cursor marker needs cursor values
    pg.wait_for_function("Object.keys(window.__sv.state().cvals).length >= 2")


def test_states_show_markers_only_no_line(pg):
    open_files(pg, "geo.csv")
    sig(pg, "Gear").click()
    pg.locator(".plot .chip").first.click(button="right"); menu_item(pg, "State lane")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals[0].state === true")
    pg.wait_for_selector(".chip .tag")
    # the series line itself is hidden (only the state lane is drawn)
    assert pg.evaluate("document.querySelectorAll('.plot .u-legend .u-series').length >= 0")
    pg.locator(".plot .chip").first.click(button="right"); menu_item(pg, "Line")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals[0].state === false")


def test_map_lon_and_lat_are_both_selectable(pg):
    open_files(pg, "geo.csv")
    sig(pg, "Lat").click(); sig(pg, "Lon").click()
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="Map").first.click()
    pg.wait_for_selector(".plot .geo canvas")
    # swap them with the two pickers: longitude <- Lat, latitude <- Lon
    pg.locator(".plot .xpick [aria-label='Lon']").first.click()
    pg.get_by_role("option", name="Lat").first.click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].xSignal.endsWith('/Lat')")
    pg.locator(".plot .xpick [aria-label='Lat']").first.click()
    pg.get_by_role("option", name="Lon").first.click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals[0].sig.endsWith('/Lon')")


def test_side_panel_can_be_resized_and_keeps_its_width(pg):
    open_files(pg, "run_a.csv")
    w0 = pg.evaluate("document.querySelector('aside.side').getBoundingClientRect().width")
    h = pg.locator(".resizer").first
    box = h.bounding_box()
    pg.mouse.move(box["x"] + 3, box["y"] + 200); pg.mouse.down(); pg.mouse.move(box["x"] + 123, box["y"] + 200, steps=5); pg.mouse.up()
    w1 = pg.evaluate("document.querySelector('aside.side').getBoundingClientRect().width")
    assert w1 > w0 + 80
    h.dblclick()
    assert abs(pg.evaluate("document.querySelector('aside.side').getBoundingClientRect().width") - 280) < 2


def test_reload_redraws_the_graph(pg, env=None):
    p = os.path.join(pg.env["data"], "reload_me.csv")
    with open(p, "w") as f:
        f.write("Time,V\n" + "".join(f"{i * 0.1:.1f},{i}\n" for i in range(100)))
    open_files(pg, "reload_me.csv")
    sig(pg, "V").click()
    pg.wait_for_function("Object.values(window.__sv.state().decimation)[0]?.total === 100")
    time.sleep(1.1)
    with open(p, "w") as f:
        f.write("Time,V\n" + "".join(f"{i * 0.1:.1f},{-i}\n" for i in range(180)))
    pg.locator(".run-head").first.hover()
    pg.locator(".run-head [aria-label='Reload from disk']").click()
    pg.wait_for_function("Object.values(window.__sv.state().decimation)[0]?.total === 180", timeout=8000)


# =========================================================== zoom modes, refresh all, live, text values
def test_zoom_y_only_and_back(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.click(".stage-bar .zoom-btn")                                         # T19: the zoom mode is in a menu
    pg.locator(".zoom-seg button", has_text="Y").first.click()
    assert S(pg, "s.zoomMode") == "y"
    box = pg.locator(".plot .u-over").first.bounding_box()
    pg.mouse.move(box["x"] + 100, box["y"] + 30); pg.mouse.down()
    pg.mouse.move(box["x"] + 130, box["y"] + 120, steps=6); pg.mouse.up()
    pg.wait_for_function("Object.values(window.__sv.state().yRanges).some(r => r)")
    assert not any(S(pg, "Object.values(s.ranges)"))                  # time window untouched
    pg.keyboard.press("Backspace")
    pg.wait_for_function("!Object.values(window.__sv.state().yRanges).some(r => r)")
    pg.keyboard.press("z")                                              # Y -> XY
    assert S(pg, "s.zoomMode") == "xy"


def test_refresh_all_reads_changed_files(pg):
    src = os.path.join(pg.env["data"], "refresh_me.csv")
    with open(src, "w") as fh:
        fh.write("Time,A\n0,1\n1,2\n")
    open_files(pg, "refresh_me.csv")
    time.sleep(0.05)
    with open(src, "a") as fh:
        fh.write("2,3\n3,4\n")
    pg.keyboard.press("F5")
    pg.wait_for_function("window.__sv.state().runs.find(r => r.name === 'refresh_me.csv').samples === 4")


def test_live_follows_growing_text_column(pg):
    src = os.path.join(pg.env["data"], "live_states.csv")
    with open(src, "w") as fh:
        fh.write("Time,Mode\n0,IDLE\n1,IDLE\n")
    open_files(pg, "live_states.csv")
    sig(pg, "Mode").click()
    assert S(pg, "s.ws.tabs[0].plots[0].signals[0].state") is True          # a text signal starts as a lane
    pg.click(".live-btn")
    pg.wait_for_function("window.__sv.state().streaming === true")
    with open(src, "a") as fh:
        fh.write("2,ARMED\n3,FLYING\n")
    pg.wait_for_function("window.__sv.state().runs[0].samples === 4", timeout=15000)
    labels = S(pg, "s.runs[0].signals.find(x => x.name === 'Mode').labels")
    assert set(labels.values()) == {"IDLE", "ARMED", "FLYING"}
    pg.click(".live-btn")
    pg.wait_for_function("window.__sv.state().streaming === false")


def test_flight_log_panel_only_for_logs(pg):
    open_files(pg, "run_a.csv")
    assert pg.locator(".rail-log").count() == 0                              # CSV only: no Log button
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import make_test_bin as mk
    mk.FMTS.clear()
    with open(os.path.join(pg.env["data"], "flight.bin"), "wb") as fh:
        fh.write(mk.header() + mk.body(1.0, 25.0, 50))
    open_files(pg, "flight.bin", clear=False)
    pg.wait_for_selector(".rail-log .rail-badge")                            # errors in the log
    pg.click(".rail-log")
    pg.locator(".log-tabs button").nth(1).click()                            # Health is first; then Events
    pg.locator(".log-row", has_text="ARMED").first.click()
    pg.wait_for_function("window.__sv.state().cursor.on && Math.abs(window.__sv.state().cursor.t1 - 4) < 1e-6")
    pg.locator(".log-tabs button").nth(2).click()
    pg.locator(".chipbtn", has_text="Changed in flight").click()
    assert pg.locator(".prow:not(.head)").count() == 1
    pg.locator(".pchange").first.click()
    pg.wait_for_function("Math.abs(window.__sv.state().cursor.t1 - 11) < 1e-6")


def test_transform_expression_autocomplete_and_checks(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click(button="right"); menu_item(pg, "Scale, offset or function")
    pg.locator(".tf-dialog select").first.select_option("custom")
    inp = pg.locator(".tf-dialog input.fx-input")
    inp.fill(""); inp.type("smo")
    # (the suggestions and the argument hint update a moment after typing: wait for what is expected)
    pg.wait_for_function("(document.querySelector('.fx-suggest')?.textContent || '').includes('smooth(x, n=10)')")
    pg.keyboard.press("Tab"); pg.keyboard.type("x, ")
    pg.wait_for_function("document.querySelector('.tf-dialog input.fx-input').value === 'smooth(x, )'")   # caret inside the parentheses
    pg.wait_for_function("(document.querySelector('.fx-sig .cur')?.textContent || '').includes('n=10')")  # the argument being typed
    inp.fill("RPM * 2")
    pg.wait_for_function("(document.querySelector('.tf-dialog .fx-err')?.textContent || '').includes('x')")
    assert pg.locator(".tf-dialog .btn.primary").is_disabled()
    # the expression is checked a moment after typing: wait for the new verdict, not the previous one
    inp.fill("smoth(x, 5)")
    pg.wait_for_function("(document.querySelector('.tf-dialog .fx-err')?.textContent || '').includes('smooth')")   # did you mean
    inp.fill("lowpass(x, 2) * 1e3")
    pg.wait_for_function("!document.querySelector('.tf-dialog .fx-err')")
    pg.keyboard.press("Enter")
    pg.wait_for_function("window.__sv.state().runs[0].signals.find(s => s.name === 'Speed').transform?.expr === 'lowpass(x, 2) * 1e3'")


def test_same_flight_sync_health_notes_spectrogram(pg):
    d = pg.env["data"]
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_same_flight.py"), d], check=True, capture_output=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_test_bin.py"), os.path.join(d, "faults.bin"), "--seconds", "40"],
                   check=True, capture_output=True)
    open_files(pg, "flight.bin")
    open_files(pg, "flight.tlog", clear=False)
    # offered automatically, and in the dialog: three methods that agree
    pg.wait_for_selector(".toast >> text=same flight")
    pg.locator(".run-head", has_text="flight.tlog").first.click(button="right")
    menu_item(pg, "Align time with another file…")
    pg.wait_for_selector(".sync-row")
    assert pg.locator(".sync-row").count() == 3
    pg.locator(".sync-row").first.locator("button", has_text="Apply").first.click()
    pg.wait_for_function("Math.abs(window.__sv.state().runs.find(r => r.name === 'flight.tlog').timeOffset - 37.22) < 0.05")
    # health of a log with planted faults
    open_files(pg, "faults.bin", clear=False)
    pg.click(".rail-log")
    pg.locator(".log-file select").select_option(label="faults.bin")
    pg.wait_for_selector(".hrow.error")
    assert "63" in pg.locator(".hrow.error").first.inner_text()
    pg.locator(".hrow.error").first.locator(".pchange.span").first.click()
    pg.wait_for_function("window.__sv.state().cursor.dual && window.__sv.state().cursor.t1 === 30")
    # a note at the cursor
    pg.keyboard.press("n")
    pg.locator(".dialog textarea, .dialog input").first.fill("vibration burst")
    pg.locator(".dialog .btn.primary").click()
    pg.wait_for_function("(window.__sv.state().ws.notes || []).some(n => n.text === 'vibration burst' && n.t === 30)")
    # a spectrogram plot draws its image
    pg.click(".topbar [aria-label='Templates']"); menu_item(pg, "Open a template")   # templates: top bar / file panel, for any file
    pg.locator(".tpl-item", has_text="ArduPilot · Vibration").click()
    pg.locator(".tpl-actions .btn.primary").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.at(-1).plots.some(p => p.mode === 'spec')")
    pg.wait_for_selector(".spec-wrap canvas")
    pg.wait_for_function("""(() => { const c = document.querySelector('.spec-wrap canvas'); if (!c || !c.width) return false;
      const d = c.getContext('2d').getImageData(c.width / 2, c.height / 2, 1, 1).data; return d[3] > 0; })()""", timeout=15000)


def test_templates_share_mode_lane_and_compare_views(pg):
    d = pg.env["data"]
    if not os.path.exists(os.path.join(d, "flight.tlog")):
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_same_flight.py"), d], check=True, capture_output=True)
    open_files(pg, "flight.bin")
    open_files(pg, "flight.tlog", clear=False)
    pg.keyboard.press("Control+k"); pg.keyboard.type("template"); pg.keyboard.press("Enter")
    pg.wait_for_selector(".tpl-lib")
    pg.locator(".tpl-item", has_text="Attitude & altitude").click()
    # two file slots, each given the right file automatically
    # (the slots are filled after the template's match comes back: wait for that, do not read once -
    # reading at once failed now and then in whole-suite runs, 2026-10-17/18)
    pg.wait_for_function("""() => [...document.querySelectorAll('.tpl-slot select')].slice(0, 2)
        .map(e => e.options[e.selectedIndex]?.text).join('|') === 'flight.bin (bin)|flight.tlog (tlog)'""")
    pg.locator(".tpl-actions .btn.primary").click()
    pg.wait_for_function("(window.__sv.state().ws.tabs.at(-1).sharedStates || []).length === 2")
    tab = S(pg, "s.ws.tabs.at(-1)")
    roll = tab["plots"][0]["signals"]
    assert roll[0]["sig"].endswith("/ATT.Roll") and roll[1]["sig"].endswith("/ATTITUDE.roll [rad]") and abs(roll[1]["scale"] - 57.29578) < 1e-6
    # the mode lanes show on every plot: each plot asks the server for both lanes' states
    assert all(s.endswith(("MODE.Mode", "HEARTBEAT.custom_mode")) for s in tab["sharedStates"])
    # a lane can be shared from a chip's menu, and unshared again
    pg.locator(".plot .chip").first.click(button="right")
    assert pg.locator(".menu.ctx button", has_text="every plot").count() == 0     # ATT.Roll is not a state


def test_align_csv_and_mat_by_name_moment_and_cursors(pg):
    import scipy.io
    d = pg.env["data"]
    rng = np.random.default_rng(3); walk = np.cumsum(rng.normal(0, 0.4, 140))
    T = lambda t: 3 * np.sin(0.9 * t) + 2 * np.sin(0.23 * t + 1) + np.interp(t, np.arange(0, 70, 0.5), walk)
    ta = np.arange(0, 60, 0.01); tb = np.arange(5, 55, 0.02); tc = np.arange(2, 58, 0.05)
    _csv(os.path.join(d, "devA.csv"), ["Time", "Speed", "Trigger"], [ta, T(ta), (ta >= 12).astype(float)])
    _csv(os.path.join(d, "devB.csv"), ["Time", "Speed", "TrigIn"], [tb + 987.654, T(tb), 5 * (tb >= 12)])
    scipy.io.savemat(os.path.join(d, "devC.mat"), {"t": tc - 4.5, "Speed_mps": T(tc), "Trig": (tc >= 12).astype(float)})
    open_files(pg, "devA.csv")
    open_files(pg, "devB.csv", clear=False)
    open_files(pg, "devC.mat", clear=False)
    # B: automatically, by the signal with the same name
    pg.locator(".run-head", has_text="devB.csv").first.click(button="right")
    menu_item(pg, "Align time with another file…")
    pg.locator(".sync-dialog select").first.select_option(label="devA.csv")
    pg.wait_for_selector(".sync-row >> text=Same name")
    pg.locator(".sync-row").first.locator("button", has_text="Apply").first.click()
    pg.wait_for_function("Math.abs(window.__sv.state().runs.find(r => r.name === 'devB.csv').timeOffset + 987.654) < 0.02")
    # C: by a moment (the trigger's rise) in the dialog
    pg.locator(".run-head", has_text="devC.mat").first.click(button="right")
    menu_item(pg, "Align time with another file…")
    pg.locator(".sync-dialog select").first.select_option(label="devA.csv")
    pg.locator(".sync-ways button", has_text="By a moment").click()
    for k, name in ((0, "Trigger"), (1, "Trig")):
        pg.locator(".sync-manual-body .picker-btn").nth(k).click(); pg.keyboard.type(name); pg.keyboard.press("Enter")
    pg.locator(".sync-manual-body .btn", has_text="Find the moment").click()
    pg.wait_for_selector(".sync-row >> text=Rises through a level")
    pg.locator(".sync-row").first.locator("button", has_text="Apply").first.click()
    pg.wait_for_function("Math.abs(window.__sv.state().runs.find(r => r.name === 'devC.mat').timeOffset - 4.5) < 0.06")
    # and by the cursors, from the file's menu (undo the previous first)
    pg.evaluate("window.__sv.setState({ cursor: { on: true, dual: true, t1: 20.0, t2: 19.0, active: 1 } })")
    pg.locator(".run-head", has_text="devC.mat").first.click(button="right")
    pg.locator(".menu.ctx button", has_text="T2 falls on T1").click()
    pg.wait_for_function("Math.abs(window.__sv.state().runs.find(r => r.name === 'devC.mat').timeOffset - 5.5) < 0.07")


def test_template_library_collections_and_quick_look(pg):
    open_files(pg, "run_a.csv", "run_b.csv")
    pg.click(".topbar [aria-label='Templates']"); menu_item(pg, "Open a template")
    pg.wait_for_selector(".tpl-lib")
    # any file: a quick look of one file
    pg.locator(".tpl-item", has_text="Quick look").click()
    pg.locator(".tpl-slot select").first.select_option(label="run_b.csv")
    pg.locator(".tpl-actions .btn.primary").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.length === 1 && window.__sv.state().ws.tabs[0].name.startsWith('Quick look')")  # replaced the empty tab
    assert all("/" in x["sig"] for x in S(pg, "s.ws.tabs[0].plots.flatMap(p => p.signals)"))
    # a template of that tab, then a collection that includes it and "Compare open files"
    pg.locator(".tab").first.click(button="right"); menu_item(pg, "Save as template")
    pg.locator(".tpl-editor input").first.fill("Speed set")
    pg.locator(".tpl-editor .btn.primary").click()
    pg.wait_for_selector(".tpl-details h3:has-text('Speed set')")
    pg.locator(".tpl-side-top .btn.primary").click(); menu_item(pg, "A collection of templates")
    pg.locator(".tpl-editor input").first.fill("All my views")
    inc = pg.locator(".tpl-editor select[aria-label='Include a template']")
    inc.select_option(label="Speed set"); inc.select_option(label="Compare open files")
    pg.locator(".tpl-editor .btn.primary").click()
    pg.wait_for_selector(".tpl-details h3:has-text('All my views')")
    n0 = S(pg, "s.ws.tabs.length")
    pg.locator(".tpl-actions .btn.primary").click()
    pg.wait_for_function(f"window.__sv.state().ws.tabs.length > {n0 + 1}")
    names = S(pg, f"s.ws.tabs.slice({n0}).map(t => t.name)")
    assert names[0].startswith("Quick look") and any(n.startswith("Compare") for n in names)   # "Speed set" kept its tab's name
    cmp_tab = S(pg, f"s.ws.tabs.slice({n0}).find(t => t.name.startsWith('Compare'))")
    assert all(len(p["signals"]) == 2 for p in cmp_tab["plots"])           # every shared signal from both files
    # a template cannot include one that includes it (no loops)
    pg.click(".topbar [aria-label='Templates']"); menu_item(pg, "Open a template")
    pg.locator(".tpl-item", has_text="Speed set").click(); pg.locator(".tpl-actions .btn", has_text="Edit").click()
    opts = pg.locator(".tpl-editor select[aria-label='Include a template'] option").all_inner_texts()
    assert not any("All my views" in o for o in opts)


def test_inspector_starts_closed_and_respects_the_user(pg):
    """T08: closed at start; the cursor opens it; once the user closes it with its button,
    the cursor no longer does (a chip click - an explicit request - still does)."""
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    assert pg.locator(".inspector").count() == 0
    pg.keyboard.press("Space")
    pg.wait_for_selector(".inspector")
    pg.keyboard.press("Space")
    pg.click(".topbar [aria-label^='Inspector']")                 # the user closes it on purpose
    assert pg.locator(".inspector").count() == 0
    pg.keyboard.press("Space")
    pg.wait_for_timeout(300)
    assert pg.locator(".inspector").count() == 0                  # their choice wins
    pg.locator(".plot .chip").first.click()
    pg.wait_for_selector(".inspector")
    pg.reload(); pg.wait_for_selector(".app")
    assert S(pg, "s.inspectorOpen") is False                     # remembered: "closed"


def test_segments_of_a_state_signal(pg):
    """T10: show a mode signal as states -> its segments in the Inspector; a row zooms to it
    and puts the two cursors on its edges (the Between-cursors statistics then cover it)."""
    p = os.path.join(pg.env["data"], "modes.csv")
    rows = [f"{i * 0.1:.1f},{'HOVER' if i < 100 else 'CRUISE' if i < 250 else 'LAND'},{i}" for i in range(300)]
    with open(p, "w") as f:
        f.write("Time,Mode,Alt\n" + "\n".join(rows) + "\n")
    open_files(pg, "modes.csv")
    sig(pg, "Mode").click()
    pg.locator(".plot .chip").first.click()
    pg.locator(".inspector .seg").get_by_role("button", name="State lane", exact=True).click()
    pg.wait_for_selector(".segments")
    totals = pg.locator(".seg-totals").inner_text()
    assert "CRUISE" in totals and "HOVER" in totals and "LAND" in totals
    pg.click(".segments .seg-toggle")
    pg.locator(".seg-list button", has_text="CRUISE").click()
    c = S(pg, "s.cursor")
    assert c["dual"] and abs(c["t1"] - 10.0) < 1e-6 and abs(c["t2"] - 25.0) < 1e-6


def test_limits_pass_fail_in_the_inspector(pg):
    """T13: limits on the plotted value -> fail with its violations (a row zooms to one) /
    pass; undoable; kept with the workspace."""
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.locator(".plot .chip").first.click()
    hi = pg.locator(".limits input[aria-label='Upper limit (empty: none)']")
    hi.fill("25"); hi.press("Enter")
    pg.wait_for_selector(".lim-result.fail")
    assert S(pg, "s.ws.tabs[0].plots[0].signals[0].limits.hi") == 25
    pg.locator(".limits .seg-list button").first.click()
    assert S(pg, "s.cursor.dual") is True
    hi.fill("1000"); hi.press("Enter")
    pg.wait_for_selector(".lim-result.pass")
    pg.keyboard.press("Control+z")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals[0].limits.hi === 25")
    pg.wait_for_timeout(1500)                                  # autosave
    pg.reload(); pg.wait_for_selector(".run-head")
    assert S(pg, "s.ws.tabs[0].plots[0].signals[0].limits.hi") == 25


def test_envelope_of_several_runs(pg):
    """T14: the same signal from three runs -> Envelope mode shows the band and its summary;
    the mode change is undoable."""
    open_files(pg, "run_a.csv", "run_b.csv", "run_c.csv")
    pg.click(".side-head [aria-label='Link files']")
    sig(pg, "Speed").click()
    pg.wait_for_function("document.querySelectorAll('.plot .chip').length === 3")
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="Envelope").first.click()
    pg.wait_for_function("(document.querySelector('.env-caption')?.textContent || '').includes('3 runs')")
    assert pg.locator(".env-canvas canvas").count() >= 1
    assert S(pg, "s.ws.tabs[0].plots[0].mode") == "env"
    pg.keyboard.press("Control+z")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].mode !== 'env'")
