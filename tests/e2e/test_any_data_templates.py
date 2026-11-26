"""CC15: the *Any data* templates made from the files themselves - Actuator effort and saturation, Frequency content,
Many runs as an envelope - and the template library's groups, any data first, the flight logs after.

    python -m pytest tests/e2e/test_any_data_templates.py -q
"""
import math
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, menu_item, open_files, pg  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _files(pg):
    d = pg.env["data"]
    for k in range(3):
        p = os.path.join(d, f"loop_run{k}.csv")
        if not os.path.exists(p):
            with open(p, "w") as f:
                f.write("Time,Pos_cmd,Pos,u,motor_rpm,Temp\n")
                for i in range(400):
                    t = i * 0.01
                    cmd = 1.0 if t > 0.5 else 0.0
                    pos = cmd * (1 - math.exp(-(t - 0.5) * (4 + k))) if t > 0.5 else 0.0
                    u = min(1.0, 3 * (cmd - pos))                      # an effort that saturates at 1
                    f.write(f"{t:.2f},{cmd},{pos:.5f},{u:.5f},{3000 + 500 * u:.1f},{20 + 0.01 * i + k:.3f}\n")
    yield


def _open_template(pg, name):
    pg.click(".stage-bar .more-tabs"); menu_item(pg, "Open a template")   # the views menu
    pg.locator(".tpl-item", has_text=name).first.click()
    pg.locator(".tpl-actions .btn.primary").click()


def test_the_library_lists_any_data_first_then_the_flight_logs(pg):
    open_files(pg, "loop_run0.csv")
    pg.click(".stage-bar .more-tabs"); menu_item(pg, "Open a template")
    pg.wait_for_selector(".tpl-lib .tpl-group")
    pg.locator(".tpl-fitonly input").uncheck()                     # every template, not only those that fit
    groups = [g for g in pg.eval_on_selector_all(".tpl-lib .tpl-group", "els => els.map(e => e.textContent.trim())")]
    assert groups[0] in ("Any data", "My templates")
    flight = [k for k, g in enumerate(groups) if g.startswith("Flight logs")]
    assert flight and min(flight) > groups.index("Any data")
    for name in ("Actuator effort and saturation", "Frequency content", "Many runs as an envelope"):
        assert pg.locator(".tpl-item", has_text=name).count() == 1


def test_actuator_effort_and_frequency_content(pg):
    open_files(pg, "loop_run0.csv")
    _open_template(pg, "Actuator effort and saturation")
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name.startsWith('Actuator effort'))")
    tab = next(t for t in S(pg, "s.ws.tabs") if t["name"].startswith("Actuator effort"))
    names = sorted(s["sig"].split("/", 1)[1] for p in tab["plots"] for s in p["signals"])
    assert names == ["motor_rpm", "u"]                             # the command (Pos_cmd) is not an effort
    _open_template(pg, "Frequency content")
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name.startsWith('Frequency content'))")
    tabs = [t for t in S(pg, "s.ws.tabs") if t["name"].startswith("Frequency content")]
    assert all(p["mode"] == "fft" for t in tabs for p in t["plots"])
    assert sum(len(t["plots"]) for t in tabs) == 5                 # every signal, four a tab


def test_many_runs_as_an_envelope(pg):
    open_files(pg, "loop_run0.csv", "loop_run1.csv")
    pg.click(".stage-bar .more-tabs"); menu_item(pg, "Open a template")
    pg.wait_for_selector(".tpl-lib .tpl-item")
    assert pg.locator(".tpl-item", has_text="Many runs as an envelope").count() == 0   # two runs: not an envelope yet
    pg.keyboard.press("Escape")
    open_files(pg, "loop_run2.csv", clear=False)
    _open_template(pg, "Many runs as an envelope")
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name.startsWith('Envelope'))")
    tabs = [t for t in S(pg, "s.ws.tabs") if t["name"].startswith("Envelope")]
    plots = [p for t in tabs for p in t["plots"]]
    assert all(p["mode"] == "env" for p in plots) and len(plots) == 5
    assert all(len(p["signals"]) == 3 for p in plots)             # one line per run
