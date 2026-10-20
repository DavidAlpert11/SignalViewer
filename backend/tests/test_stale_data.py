"""F34: nothing cached is used after the data changed - a derived signal replaced under the same
name, a Python operation whose file changed, a file re-saved with the same size and time stamp."""
import os

import numpy as np
import pytest

from app.store import Store
from svcore import csv_loader

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


def test_replaced_derived_signal_gets_a_new_version_and_fresh_fft():
    st = Store()
    lr = st.open_file(os.path.join(EX, "run_012.csv"))
    src = f"{lr.id}/RPM"
    st.add_derived("lowpass", [src], {"cutoff": 5.0}, "f")
    v1 = st.version("derived/f")
    from svcore.analysis import fft_for
    t, y = st.signal("derived/f")
    a = fft_for("derived/f", v1, t, y, "hanning", None, None)[1].copy()
    st.remove_derived("f")                                          # what /api/derived/restore does
    st.add_derived("lowpass", [src], {"cutoff": 0.2}, "f")          # same name, same source
    v2 = st.version("derived/f")
    assert v1 != v2
    t, y = st.signal("derived/f")
    b = fft_for("derived/f", v2, t, y, "hanning", None, None)[1]
    assert not np.allclose(a, b)                                    # not the old signal's spectrum
    d = next(r for r in st.list() if r["format"] == "derived")
    assert d["signals"][0]["version"] and isinstance(d["signals"][0]["version"], str)


def test_python_operations_reloaded_recompute_their_signals():
    st = Store()
    lr = st.open_file(os.path.join(EX, "run_012.csv"))
    st.add_derived("derivative", [f"{lr.id}/RPM"], {}, "d")
    st.signal("derived/d")
    v1 = st.version("derived/d")
    assert st.invalidate_derived("derivative") == ["d"]
    assert st.version("derived/d") != v1 and st.derived["d"].time is None
    assert len(st.signal("derived/d")[0]) > 0                       # computed again on the next read


def test_run_version_changes_on_reload():
    st = Store()
    lr = st.open_file(os.path.join(EX, "run_012.csv"))
    v1 = st.describe(lr)["version"]
    lr2 = st.reload(lr.id)
    assert st.describe(lr2)["version"] != v1


def test_same_size_same_time_stamp_different_bytes_is_not_the_cached_file(tmp_path, monkeypatch):
    monkeypatch.setattr(csv_loader, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(csv_loader, "CACHE_MIN_BYTES", 0)
    p = tmp_path / "a.csv"
    p.write_text("Time,x\n0,1\n1,2\n2,3\n", encoding="utf-8")
    st0 = os.stat(p)
    r1 = csv_loader.load_csv(str(p), [str(p)])
    assert list(r1.signals["x"].data) == [1, 2, 3]
    p.write_text("Time,x\n0,1\n1,9\n2,3\n", encoding="utf-8")     # one value fixed, same size
    os.utime(p, ns=(st0.st_atime_ns, st0.st_mtime_ns))              # and the same time stamp
    r2 = csv_loader.load_csv(str(p), [str(p)])
    assert list(r2.signals["x"].data) == [1, 9, 3]


def test_live_follow_sees_a_same_size_re_save(tmp_path):
    p = tmp_path / "live.csv"
    rows = [f"{k},{k % 10}" for k in range(5000)]
    p.write_text("Time,x\n" + "\n".join(rows) + "\n", encoding="utf-8")
    st = Store()
    lr = st.open_file(str(p))
    assert csv_loader.append_new_rows(lr.run) == 0                  # nothing new
    rows[10] = "10,9"                                               # early in the file, same size
    p.write_text("Time,x\n" + "\n".join(rows) + "\n", encoding="utf-8")
    os.utime(p, (os.stat(p).st_atime + 5, os.stat(p).st_mtime + 5))
    assert csv_loader.append_new_rows(lr.run) == -1                 # read the whole file again
    os.utime(p, (os.stat(p).st_atime + 5, os.stat(p).st_mtime + 5))
    lr2 = st.reload(lr.id)
    os.utime(p, (os.stat(p).st_atime + 5, os.stat(p).st_mtime + 5))   # only touched now
    assert csv_loader.append_new_rows(lr2.run) == 0
