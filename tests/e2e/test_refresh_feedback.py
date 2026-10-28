"""Q114: what F5 (Refresh all) did, on the file itself: ↻ / ✓ and the time on its row, a mark on the
signals that changed, and a message per file - not changed on the disk / saved again with the same
data / which signals changed. A small change in the data used to leave the user unsure.

    python -m pytest tests/e2e/test_refresh_feedback.py -q
"""
import os
import time

import numpy as np
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, _csv, env, open_files, pg  # noqa: E402,F401


def _write(path, bump=0.0):
    t = np.arange(0, 10, 0.01)
    speed = np.sin(t)
    speed[500] += bump
    _csv(path, ["Time", "Speed", "RPM"], [t, speed, np.cos(t)])


def _refresh(pg):
    before = S(pg, "s.dataVersion")
    pg.mouse.click(5, 300)                 # focus on the page, not in a text box
    pg.keyboard.press("F5")
    pg.wait_for_function(f"window.__sv.state().dataVersion > {before}")
    pg.wait_for_selector(".toast:has-text('Refresh')")
    return " | ".join(pg.locator(".toast").all_inner_texts())


def test_f5_says_what_changed_on_the_file_and_its_signals(pg):
    path = os.path.join(pg.env["data"], "fresh.csv")
    _write(path)
    open_files(pg, "fresh.csv")
    rid = S(pg, "s.runs.find(r => r.name === 'fresh.csv').id")

    time.sleep(0.05)
    _write(path, bump=0.001)               # one sample of one signal
    text = _refresh(pg)
    assert "1 signal changed (Speed)" in text
    assert pg.locator(".run-fresh.new").count() == 1
    assert pg.locator(".sig-changed").count() == 1
    assert "Speed" in pg.locator(".sig", has=pg.locator(".sig-changed")).inner_text()
    title = pg.locator(".run-fresh").get_attribute("title")
    assert "Data read from the disk at" in title and "File last saved at" in title

    text = _refresh(pg)                    # nothing touched
    assert "not changed on the disk" in text and text.count("Refresh") == 1     # replaces the last one
    assert pg.locator(".run-fresh.new").count() == 0 and pg.locator(".sig-changed").count() == 0
    assert S(pg, f"s.runs.find(r => r.id === '{rid}').lastReload.fileChanged") is False

    st = os.stat(path)                     # saved again, the same data
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
    assert "saved again - the data is the same" in _refresh(pg)
