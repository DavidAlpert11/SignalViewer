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
    assert box.evaluate("e => e.value.slice(e.selectionStart, e.selectionEnd)") == "flight"
    pg.keyboard.type("flight_07")
    pg.keyboard.press("Enter")
    dlg.locator(".fs-row", has_text="flight_07.csv").wait_for()
    assert os.path.isfile(os.path.join(work, "flight_07.csv")) and not os.path.exists(os.path.join(work, "flight.csv"))
    assert dlg.locator(".fs-row.on", has_text="flight_07.csv").count() == 1      # still the one picked
    pg.locator(".fs-dialog").focus()
    pg.keyboard.press("Delete")                                                  # Delete: asked first, in the dialog
    dlg.locator(".fs-confirm", has_text="recycle bin").wait_for()
    dlg.locator(".fs-confirm-ok").click()
    dlg.locator(".fs-note", has_text="recycle bin").wait_for()
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
