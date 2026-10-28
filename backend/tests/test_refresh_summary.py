"""What a refresh changed (F5 / Refresh all / a file's ↻): the file list says when the data was read,
whether the file had changed on the disk, and which signals changed - small changes were invisible."""
import os
import time

import numpy as np

from app.store import Store
from svcore.reload_diff import compare


def _write(p, speed, rpm, n=200, extra=False):
    t = np.arange(n) * 0.01
    cols = ["Time", "Speed", "RPM"] + (["Gear"] if extra else [])
    rows = [[t[i], speed[i], rpm[i]] + ([1] if extra else []) for i in range(n)]
    p.write_text(",".join(cols) + "\n" + "\n".join(",".join(f"{v:.6g}" for v in r) for r in rows) + "\n")


def _bump_mtime(p):
    st = os.stat(p)
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))


def test_compare_names_and_samples():
    s = compare({"A": "1", "B": "2"}, {"A": "1", "B": "3"}, ["A", "B"], ["A", "B", "C"], 10, 12)
    assert s["changed"] == ["B"] and s["added"] == ["C"] and not s["same"] and s["notCompared"] == 0
    assert compare({"A": "1"}, {"A": "1"}, ["A"], ["A"], 5, 5)["same"]


def test_refresh_all_says_unchanged_same_data_and_what_changed(tmp_path):
    st = Store()
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    sp, rpm = np.linspace(0, 10, 200), np.linspace(0, 900, 200)
    _write(a, sp, rpm)
    _write(b, sp, rpm)
    ra, rb = st.open_file(str(a), {}).id, st.open_file(str(b), {}).id
    assert st.describe(st.runs[ra])["readAt"] > 0 and "lastReload" not in st.describe(st.runs[ra])

    res = st.reload_all()                                       # nothing touched
    assert set(res["unchanged"]) == {ra, rb}
    d = {x["id"]: x for x in res["details"]}
    assert d[ra]["same"] and not d[ra]["fileChanged"]

    _bump_mtime(a)                                              # saved again, same data
    sp2 = sp.copy(); sp2[150] += 0.01                           # one sample of one signal
    _write(b, sp2, rpm, n=200)
    _bump_mtime(b)
    res = st.reload_all()
    d = {x["id"]: x for x in res["details"]}
    assert d[ra]["fileChanged"] and d[ra]["same"]
    assert d[rb]["fileChanged"] and d[rb]["changed"] == ["Speed"] and not d[rb]["same"]
    desc = st.describe(st.runs[rb])
    assert desc["lastReload"]["changed"] == ["Speed"] and desc["fileTime"] > 0


def test_a_forced_refresh_counts_new_rows_and_new_columns(tmp_path):
    st = Store()
    p = tmp_path / "c.csv"
    _write(p, np.zeros(200), np.zeros(200))
    rid = st.open_file(str(p), {}).id
    before = st.runs[rid].read_at
    time.sleep(0.01)
    _write(p, np.zeros(250), np.zeros(250), n=250, extra=True)
    fresh, s = st.refresh(rid)
    assert fresh is not None and fresh.read_at > before
    assert s["samplesBefore"] == 200 and s["samplesAfter"] == 250 and s["added"] == ["Gear"]
    assert not s["same"]


def test_what_changed_stays_after_a_refresh_that_finds_nothing(tmp_path):
    """Q114b: ↻ then ✓ - the second refresh must not hide what changed and when."""
    st = Store()
    p = tmp_path / "d.csv"
    sp, rpm = np.linspace(0, 10, 200), np.zeros(200)
    _write(p, sp, rpm)
    rid = st.open_file(str(p), {}).id
    opened = st.describe(st.runs[rid])["dataAt"]
    assert opened > 0 and "lastUpdate" not in st.describe(st.runs[rid])
    st.reload_all()                                             # nothing: the data is as opened
    assert st.describe(st.runs[rid])["dataAt"] == opened
    sp2 = sp.copy(); sp2[10] += 0.5
    _write(p, sp2, rpm); _bump_mtime(p)
    st.reload_all()
    d = st.describe(st.runs[rid])
    changed_at = d["dataAt"]
    assert changed_at > opened and d["lastUpdate"]["changed"] == ["Speed"]
    st.reload_all()                                             # nothing new
    d = st.describe(st.runs[rid])
    assert d["lastReload"]["same"] and not d["lastReload"]["fileChanged"]
    assert d["dataAt"] == changed_at and d["lastUpdate"]["changed"] == ["Speed"]
