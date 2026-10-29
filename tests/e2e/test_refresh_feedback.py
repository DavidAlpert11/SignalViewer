"""Q123: the file list shows when the version on screen was saved to the disk; when the file is saved
again it turns amber and a click (or F5) reads it; the message after F5 says, per file, whether it was
read again and when its new version was saved. (A user pressed F5, the message went by, and with small
changes in the data it was not clear whether the file had been read again.)

    python -m pytest tests/e2e/test_refresh_feedback.py -q
"""
import os
from datetime import datetime

import numpy as np
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, _csv, env, open_files, pg  # noqa: E402,F401


def _write(path, bump=0.0, at=None):
    t = np.arange(0, 10, 0.01)
    speed = np.sin(t)
    speed[500] += bump
    _csv(path, ["Time", "Speed", "RPM"], [t, speed, np.cos(t)])
    if at is not None:
        os.utime(path, (at, at))


def _hhmm(ts):
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def test_saved_time_newer_on_disk_and_the_refresh_message(pg):
    path = os.path.join(pg.env["data"], "fresh.csv")
    first = datetime.now().replace(hour=8, minute=15, second=0, microsecond=0).timestamp()
    _write(path, at=first)
    open_files(pg, "fresh.csv")
    rid = S(pg, "s.runs.find(r => r.name === 'fresh.csv').id")
    chip = pg.locator(".run-ftime")
    assert chip.inner_text().strip() == "08:15"                     # the file's saved time, not when it was opened
    tip = chip.get_attribute("title")
    assert "File saved at 08:15:00" in tip and "Read by the app at" in tip

    later = first + 3600 + 30 * 60                                  # 09:45: saved again by another program
    _write(path, bump=0.001, at=later)
    pg.wait_for_selector("button.run-ftime.newer", timeout=10000)   # noticed without reading the file
    assert "Saved again at 09:45:00" in pg.locator("button.run-ftime.newer").get_attribute("title")
    pg.click("button.run-ftime.newer")                             # read it
    pg.wait_for_function(f"Math.abs(window.__sv.state().runs.find(r => r.id === '{rid}').fileTime - {later}) < 1")
    pg.wait_for_selector("button.run-ftime.newer", state="detached")
    assert pg.locator(".run-ftime").inner_text().strip() == "09:45"

    pg.mouse.click(5, 300)
    pg.keyboard.press("F5")                                         # nothing new
    pg.wait_for_selector(".toast:has-text('not changed on the disk')")
    assert "saved at 09:45:00" in pg.locator(".toast", has_text="not changed").inner_text()

    _write(path, bump=0.002, at=later + 60)
    pg.keyboard.press("F5")
    pg.wait_for_selector(".toast:has-text('read again - saved at 09:46:00')")
    assert pg.locator(".toast", has_text="fresh.csv").count() == 1   # the last message is replaced
