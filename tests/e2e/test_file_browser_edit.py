"""PLAN 2026-11-16 §7b (a friend's request: "like a browser"): the file dialog makes a folder, renames a file and
moves one to the recycle bin - inline, in the dialog; a folder outside the user's own folders is refused, said
plainly. The test's home folder is a temporary one (its bin: ~/.local/share/Trash)."""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, goto_folder, pg  # noqa: E402,F401


def _open_dialog(pg, folder):
    pg.click("[aria-label='Data']") if pg.locator(".side-head .btn[aria-label='Open files']").count() == 0 else None
    pg.click(".side-head .btn[aria-label='Open files']")
    goto_folder(pg, folder)


def test_new_folder_rename_and_delete_in_the_dialog(pg):
    work = os.path.join(pg.env["home"], "work")
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, "flight.csv"), "w") as f:
        f.write("Time,V\n0,1\n1,2\n")
    _open_dialog(pg, work)
    dlg = pg.locator(".fs-dialog")
    dlg.locator(".fs-new-folder").click()                                        # New folder: a name typed in the list
    dlg.locator(".fs-name-in").fill("tests 2026")
    dlg.locator(".fs-name-in").press("Enter")
    dlg.locator(".fs-row", has_text="tests 2026").wait_for()
    assert os.path.isdir(os.path.join(work, "tests 2026"))
    row = dlg.locator(".fs-item", has_text="flight.csv")
    row.locator(".fs-row").click()
    row.hover()
    row.locator(".fs-rename").click()                                            # Rename: the name without its extension chosen
    box = dlg.locator(".fs-name-in")
    box.wait_for()                                                               # the END state: the name chosen in the box
    pg.wait_for_function("() => { const e = document.querySelector('.fs-dialog .fs-name-in');"
                         " return e && e.value.slice(e.selectionStart, e.selectionEnd) === 'flight'; }", timeout=10000)
    pg.keyboard.type("flight_07")
    pg.keyboard.press("Enter")
    dlg.locator(".fs-row", has_text="flight_07.csv").wait_for()
    assert os.path.isfile(os.path.join(work, "flight_07.csv")) and not os.path.exists(os.path.join(work, "flight.csv"))
    dlg.locator(".fs-row.on", has_text="flight_07.csv").wait_for()              # still the one picked
    assert dlg.locator(".fs-row.on", has_text="flight_07.csv").count() == 1
    pg.locator(".fs-dialog").focus()
    pg.keyboard.press("Delete")                                                  # Delete: asked first, in the dialog
    dlg.locator(".fs-confirm", has_text="recycle bin").wait_for()
    dlg.locator(".fs-confirm-ok").click()
    dlg.locator(".fs-note", has_text="recycle bin").wait_for()
    dlg.locator(".fs-row", has_text="flight_07.csv").wait_for(state="detached")  # the list read again
    assert not os.path.exists(os.path.join(work, "flight_07.csv"))
    assert os.path.isfile(os.path.join(pg.env["home"], ".local", "share", "Trash", "files", "flight_07.csv"))   # in the bin
    assert pg.locator(".fs-dialog").count() == 1                                 # the dialog stays open


def test_outside_the_users_folders_is_refused_plainly(pg):
    _open_dialog(pg, pg.env["data"])                                             # the test data: not under the home folder
    dlg = pg.locator(".fs-dialog")
    dlg.locator(".fs-new-folder").click()
    dlg.locator(".fs-name-in").fill("x")
    dlg.locator(".fs-name-in").press("Enter")
    dlg.locator(".fs-note.error", has_text="own folders").wait_for()
    assert not os.path.exists(os.path.join(pg.env["data"], "x"))
    pg.keyboard.press("Escape")


def test_a_click_while_another_folder_loads_is_not_lost(pg):
    """FB1 (2026-11-23, found by test_messages' direction-column test after the serial-link example): Enter on a
    new folder left the old folder's list clickable until the new one arrived; a file clicked there (the same name
    in both folders) was picked, then dropped when the new list came - Open stayed disabled. While another folder
    loads, the old list takes no clicks; the click lands on the new folder's file."""
    a, b = (os.path.join(pg.env["home"], n) for n in ("fb_a", "fb_b"))
    for d in (a, b):
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "same.csv"), "w") as f:
            f.write("Time,V\n0,1\n1,2\n")
    _open_dialog(pg, a)
    pg.locator(".fs-dialog .dialog-body .fs-row", has_text="same.csv").first.wait_for()   # the END state: A is listed
    held = []                                                                    # B's listing waits for the test

    def hold(route):
        if b in (route.request.post_data or ""):
            held.append(route)
        else:
            route.continue_()
    pg.route("**/api/fs/list", hold)
    pg.fill(".crumbs input", b)
    pg.press(".crumbs input", "Enter")
    old = pg.locator(".fs-dialog .dialog-body .fs-row", has_text="same.csv").first
    old.wait_for()                                                               # still folder A's row
    pg.locator(".fs-dialog .dialog-body[aria-busy='true']").wait_for()           # the END state: B is loading (the click
                                                                                 # before it reached a list not yet locked)
    with pytest.raises(Exception):                                               # A's list takes no click now
        old.click(timeout=1500)
    assert held, "the listing of B was not asked for"
    held[0].continue_()
    pg.unroute("**/api/fs/list")
    pg.locator(".fs-dialog .dialog-body .fs-row", has_text="same.csv").first.click()
    assert pg.locator(".dialog-foot .btn.primary").is_enabled()
    pg.click(".dialog-foot .btn.primary")
    pg.wait_for_function("window.__sv.state().runs.some(r => r.path.includes('fb_b'))", timeout=30000)
    assert not pg.evaluate("window.__sv.state().runs.some(r => r.path.includes('fb_a'))")
