"""T18 / F28 / F30: Settings (theme, text size, how the timeline writes time), kept in the app folder -
not in the browser, whose storage is lost when the app starts on another port - and not changed by
opening a session; the timeline writes time like the axes by default."""
import json
import os
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401


def _settings_file_when(pg, ok, timeout=10.0):
    """W11: the settings file is written 300 ms after a change (prefs.ts) - poll it, not a sleep."""
    import time
    path = os.path.join(pg.env["home"], ".signalviewer", "ui_settings.json")
    end = time.monotonic() + timeout
    d: dict = {}
    while time.monotonic() < end:
        try:
            d = json.load(open(path, encoding="utf-8"))
            if ok(d):
                return d
        except (OSError, ValueError):
            pass
        pg.wait_for_timeout(50)
    return d


def test_settings_kept_and_one_time_format(pg):
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.keyboard.press("Space")                                   # the cursor on
    pg.wait_for_function("window.__sv.state().cursor.t1 !== null")
    t1 = S(pg, "s.cursor.t1")
    clock = pg.locator(".tl-clock").inner_text()
    assert abs(float(clock.split("/")[0]) - t1) < 0.006, (clock, t1)   # seconds, as the cursor (run_a: 30 s)

    pg.click(".topbar [aria-label='Settings']")
    pg.locator(".dialog.settings button[role=radio]", has_text="Clock from the start").click()
    pg.locator(".dialog.settings button[role=radio]", has_text="Dark").click()
    pg.locator(".dialog.settings button[role=radio]", has_text="112%").click()
    pg.keyboard.press("Escape")
    assert pg.locator(".tl-clock").inner_text().split("/")[1].strip() == "29.99"   # under a minute: s.ss from the start
    pg.wait_for_timeout(800)                                      # written to the app folder
    saved = json.load(open(os.path.join(pg.env["home"], ".signalviewer", "ui_settings.json")))
    assert saved["timeFormat"] == "clock" and saved["theme"] == "dark" and saved["uiScale"] == 1.12

    # a reload (a new start) keeps them, also the Inspector's state and the panel width (F30)
    pg.reload(); pg.wait_for_selector(".app")
    assert S(pg, "[s.theme, s.uiScale, s.timeFormat]") == ["dark", 1.12, "clock"]

    # a session saved with other choices does not change them (opened from outside, T54)
    state = pg.evaluate("fetch('/api/autosave').then(r => r.json()).then(j => j.state)")
    state["ui"].update({"theme": "light", "uiScale": 1.25})
    path = os.path.join(pg.env["out"], "other.svsession")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"format": "signalviewer-session", "version": 3, **state}, f)
    tok = json.load(open(os.path.join(pg.env["home"], ".signalviewer", "push.json")))["token"]
    req = urllib.request.Request(pg.env["url"] + "/api/open-external", data=json.dumps({"paths": [path]}).encode(),
                                 headers={"Content-Type": "application/json", "X-SV-Token": tok}, method="POST")
    urllib.request.urlopen(req).read()
    pg.wait_for_function("window.__sv.state().runs.length > 0")
    pg.wait_for_function("window.__sv.state().theme === 'dark' && window.__sv.state().uiScale === 1.12")   # (T2) the page took the session
    assert S(pg, "[s.theme, s.uiScale]") == ["dark", 1.12]


def test_line_defaults_and_apply_to_all(pg):
    """N3: Settings → New lines: the width and style of the lines added from now on (kept in the app
    folder); Apply to all open plots gives them to the lines already drawn - one Undo."""
    open_files(pg, "run_a.csv")
    sig(pg, "Speed").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots[0].signals.length === 1")
    pg.click(".topbar [aria-label='Settings']")
    pg.locator(".set-line-width").fill("3")
    pg.locator(".set-line-style").select_option("dot")
    pg.keyboard.press("Escape")
    assert S(pg, "s.ws.tabs[0].plots[0].signals[0].width") == 1.5          # not restyled silently
    sig(pg, "RPM").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.some((p) => p.signals.some((s) => s.sig.endsWith('/RPM')))")
    rpm = S(pg, "s.ws.tabs[0].plots.flatMap((p) => p.signals).find((s) => s.sig.endsWith('/RPM'))")
    assert rpm["width"] == 3 and rpm["lineStyle"] == "dot"
    pg.wait_for_selector(".legend .sw.ls-dot")                              # the legend shows it dotted (W11: waited for)
    saved = _settings_file_when(pg, lambda d: d.get("lineWidth") == 3 and d.get("lineStyle") == "dot")
    assert saved["lineWidth"] == 3 and saved["lineStyle"] == "dot"
    pg.click(".topbar [aria-label='Settings']")
    pg.locator(".set-lines-apply").click()
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.flatMap((p) => p.signals).every((s) => s.width === 3 && s.lineStyle === 'dot')")
    pg.wait_for_selector(".toast:has-text('restyled')")
    pg.keyboard.press("Escape")
    pg.keyboard.press("Control+z")
    pg.wait_for_function("window.__sv.state().ws.tabs[0].plots.flatMap((p) => p.signals).find((s) => s.sig.endsWith('/Speed')).width === 1.5")
