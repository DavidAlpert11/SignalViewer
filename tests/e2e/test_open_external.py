"""T54: a file opened from outside (Explorer's Open with, `SignalViewer file.csv`) while the app runs
goes to that app: the second start hands it over and exits, the page opens it."""
import os
import subprocess
import sys
import time

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import ROOT, env, pg  # noqa: E402,F401


def test_second_start_with_a_file_opens_it_in_the_running_app(pg):
    home = pg.env["home"]
    for _ in range(50):                                        # run.py writes push.json after start
        if os.path.isfile(os.path.join(home, ".signalviewer", "push.json")):
            break
        time.sleep(0.1)
    path = os.path.join(pg.env["data"], "run_b.csv")
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "run.py"), path, "--no-build"],
                       env=dict(os.environ, HOME=home, USERPROFILE=home), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "already running" in r.stdout, r.stdout + r.stderr
    assert time.time() - t0 < 30                               # it handed over, it did not start a second app
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name === 'run_b.csv')", timeout=15000)
    pg.wait_for_selector(".sig:has-text('Speed')")
