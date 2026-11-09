"""26.A5: the app's guesses are shown and can be corrected - "Read between samples as" in a numeric
signal's menu (what was detected; a state / a value, by name, undoable), and the object dialog's
"Automatic" angle unit says what it takes the angles to be and why."""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig, object_form  # noqa: E402,F401
from test_map_objects import _files  # noqa: E402,F401


def _until(pg, rid, ok, tries=40):
    for _ in range(tries):
        d = pg.evaluate(f"fetch('/api/discrete?sig={rid}/Gear').then(r => r.json())")
        if ok(d):
            return True
        pg.wait_for_timeout(250)
    return False


def test_read_as_a_value_and_undo(pg):
    open_files(pg, "run_a.csv")                                   # Gear: floor(t / 6) - whole numbers, few levels
    rid = S(pg, "s.runs.find(r => r.format !== 'derived').id")
    sig(pg, "Gear").click(button="right")
    pg.locator(".menu.ctx button", has_text="Read between samples as").click()
    sub = pg.locator(".menu.ctx.sub")
    sub.wait_for()
    assert "Automatic - a state" in sub.inner_text()
    sub.locator("button", has_text="A value").click()
    pg.wait_for_function("window.__sv.state().ws.readAs?.Gear === 'value'")
    # the backend follows the workspace: Gear is read as a value there now
    assert _until(pg, rid, lambda d: d["readAs"] == "value" and d["discrete"] is False)
    pg.keyboard.press("Control+z")
    pg.wait_for_function("!window.__sv.state().ws.readAs")
    assert _until(pg, rid, lambda d: d["readAs"] is None and d["discrete"] is True)
    sig(pg, "Speed").click(button="right")                       # a value: the menu says so
    pg.locator(".menu.ctx button", has_text="Read between samples as").click()
    assert "Automatic - a value" in pg.locator(".menu.ctx.sub").inner_text()


def test_object_dialog_says_what_automatic_angles_are(pg):
    open_files(pg, "obj_aircraft.csv")                           # ATT.Yaw is 90: beyond 2 pi -> degrees
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="Map").first.click()
    pg.locator(".obj-add").click(); object_form(pg)
    opt = pg.locator(".obj-dialog option[value='auto']")
    pg.wait_for_function("document.querySelector(\".obj-dialog option[value='auto']\").textContent.includes('degrees')")
    assert "goes beyond 2π" in opt.inner_text()
