"""26.A2: in the running app a user's file reader runs in a process of its own - a reader that crashes
Python leaves the app working, and the next file opens."""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, toast_text  # noqa: E402,F401

READERS = '''import os

@reader(extensions=[".kv"], name="kv lines")
def read_kv(path):
    t, v = [], []
    for line in open(path):
        a, b = line.split()
        t.append(float(a)); v.append(float(b))
    return {"time": t, "signals": {"Value": v}}

@reader(extensions=[".boom"], name="crashing reader")
def boom(path):
    os._exit(3)
'''


def test_a_crashing_reader_leaves_the_app_working(pg):
    d = os.path.join(pg.env["home"], ".signalviewer", "readers")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "mine.py"), "w") as f:
        f.write(READERS)
    for name, text in (("a.boom", "x\n"), ("b.kv", "0 1\n0.5 2\n1 3\n")):
        with open(os.path.join(pg.env["data"], name), "w") as f:
            f.write(text)
    pg.keyboard.press("Control+o")
    from test_features import goto_folder
    goto_folder(pg, pg.env["data"])
    pg.locator(".dialog .dialog-body .fs-row", has_text="a.boom").first.click()
    pg.click(".dialog-foot .btn.primary")
    assert "crashed its process" in toast_text(pg)
    open_files(pg, "b.kv")                                     # the server is alive: the next file opens
    names = S(pg, "s.runs.filter(r => r.format !== 'derived').flatMap(r => r.signals.map(x => x.name))")
    assert names == ["Value"], names
