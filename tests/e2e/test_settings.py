"""T18 / F28 / F30: Settings (theme, text size, how the timeline writes time), kept in the app folder -
not in the browser, whose storage is lost when the app starts on another port - and not changed by
opening a session; the timeline writes time like the axes by default."""
import json
import os
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401


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
    pg.wait_for_timeout(2500)                                     # the page took the session
    assert S(pg, "[s.theme, s.uiScale]") == ["dark", 1.12]
