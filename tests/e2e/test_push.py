"""T39: a script sends arrays with the Python client; they appear in the open app's active plot,
and sending the same name again updates the plot."""
import os
import sys
import time

import numpy as np
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, pg  # noqa: E402,F401

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
from signalviewer import push_client  # noqa: E402


def test_sent_data_appears_and_updates(pg):
    home = pg.env["home"]
    for _ in range(50):                                       # run.py writes push.json after start
        if os.path.isfile(os.path.join(home, ".signalviewer", "push.json")):
            break
        time.sleep(0.1)
    t = np.linspace(0, 20, 401)
    r = push_client.show(t, {"altitude": 100 + 5 * t, "speed": np.sin(t)}, name="sim run", home=home)
    pg.wait_for_selector("text=Received from Python: sim run (2 signals)")
    pg.wait_for_function("""() => window.__sv.state().ws.tabs.some(t => t.plots.some(p =>
        p.signals.some(x => x.sig === '%s/altitude')))""" % r["run"])                   # in the plot by itself
    sid = f"{r['run']}/altitude"
    val = ("fetch('/api/cursor', {method: 'POST', headers: {'Content-Type': 'application/json'}, "
           f"body: JSON.stringify({{signals: ['{sid}'], t: 10}})}}).then(r => r.json()).then(j => (j.values || j)['{sid}'])")
    assert abs(pg.evaluate(val) - 150) < 1e-6                                    # 100 + 5 * 10
    push_client.show(t, {"altitude": 200 + 5 * t, "speed": np.cos(t)}, name="sim run", home=home)   # same name: in place
    pg.wait_for_function(f"{val}.then(v => Math.abs(v - 250) < 1e-6)")
    assert len(pg.evaluate("window.__sv.state().runs")) == 1                                       # not a second run
