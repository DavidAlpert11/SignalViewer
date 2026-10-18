"""T31: Create signals > Python - the user's own operations from their folder: make the example,
pick an operation and a signal, set a parameter, preview, create; a broken file is shown."""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, open_files, pg  # noqa: E402,F401


def test_python_operation_from_the_example(pg):
    open_files(pg, "run_a.csv")
    pg.click("[aria-label='Create signals']")
    pg.click(".seg.wide button:has-text('Python')")
    pg.wait_for_selector(".pyops .empty-note")                                # a fresh folder: nothing yet
    pg.click(".pyops-btns button:has-text('Make an example')")
    pg.wait_for_selector(".pyops select option:has-text('Despike')", state="attached")
    folder = pg.inner_text(".pyops-path").split(": ", 1)[1]
    assert os.path.isfile(os.path.join(folder, "example_operations.py"))

    pg.select_option(".pyops select", label="Scaled difference (A - B) x k")  # two inputs: A and B appear
    pg.wait_for_selector(".afield:has(span:text-is('B')) .picker-btn")
    pg.select_option(".pyops select", label="Despike")
    assert pg.inner_text(".pyops-doc").startswith("Samples further than")
    pg.fill(".pyops .afield:has(span:text-is('limit')) input", "2.5")
    pg.click(".afield:has(span:text-is('Signal')) .picker-btn")
    pg.click(".picker-list [role=option]:has-text('Speed')")
    pg.get_by_role("button", name="Create signal", exact=True).click()
    pg.wait_for_function("[...document.querySelectorAll('.dsig-name')].some(e => e.innerText.startsWith('despike(Speed, limit=2.5)'))")

    # a broken file next to it is listed with its line, the example still works
    with open(os.path.join(folder, "broken.py"), "w") as f:
        f.write("x = (\n")
    pg.click(".pyops-btns button:has-text('Reload')")
    pg.wait_for_selector(".pyops-errors:has-text('broken.py')")
    assert "line 1" in pg.inner_text(".pyops-errors")
    assert pg.locator(".pyops select option").count() == 3
