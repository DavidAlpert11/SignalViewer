"""CSV files from other locales and loggers: a decimal comma (1,5 with ';' between columns) and
ISO 8601 date-times in the time column."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.csv_loader import detect_decimal_comma, load_csv  # noqa: E402


def _load(p):
    return load_csv(str(p), [str(p)])


def test_decimal_comma_is_read_as_numbers(tmp_path):
    p = tmp_path / "eu.csv"
    p.write_text("time;speed;mode\n0,0;1,5;IDLE\n0,5;-2,25;RUN\n1,0;3;RUN\n")
    r = _load(p)
    assert r.time.tolist() == [0.0, 0.5, 1.0]
    assert r.signals["speed"].data.tolist() == [1.5, -2.25, 3.0] and r.signals["speed"].labels is None
    assert r.signals["mode"].labels == {0: "IDLE", 1: "RUN"}


def test_decimal_point_files_are_untouched(tmp_path):
    p = tmp_path / "us.csv"
    p.write_text("time;speed\n0.0;1.5\n0.5;2.5\n")
    assert not detect_decimal_comma(str(p), ";")
    assert _load(p).signals["speed"].data.tolist() == [1.5, 2.5]
    q = tmp_path / "comma.csv"
    q.write_text("time,speed\n0,1\n1,2\n")              # a comma delimiter is never a decimal comma
    assert not detect_decimal_comma(str(q), ",")


@pytest.mark.parametrize("stamp", ["2026-01-01T10:00:0{}", "2026-01-01T10:00:0{}Z", "2026-01-01 10:00:0{}"])
def test_iso_date_times_are_seconds_since_1970(tmp_path, stamp):
    p = tmp_path / "iso.csv"
    p.write_text("timestamp,a\n" + "".join(f"{stamp.format(i)},{i}\n" for i in range(3)))
    r = _load(p)
    t0 = 1767261600.0                                   # 2026-01-01 10:00:00 UTC
    assert np.allclose(r.time, [t0, t0 + 1, t0 + 2])


def test_first_column_that_does_not_go_up_is_not_the_time(tmp_path):
    """No column named as a time: the first one was the time anyway, and the rows were SORTED by it."""
    p = tmp_path / "t.csv"
    p.write_text("a,b\n5,1\n3,2\n9,3\n")
    r = _load(p)
    assert r.time.tolist() == [0.0, 1.0, 2.0] and r.time_source is None
    assert r.signals["a"].data.tolist() == [5.0, 3.0, 9.0] and r.signals["b"].data.tolist() == [1.0, 2.0, 3.0]
    q = tmp_path / "names.csv"                            # text first: it opened with no data before
    q.write_text("name,v\nfoo,1\nbar,2\n")
    r = _load(q)
    assert r.signals["name"].labels == {0: "foo", 1: "bar"} and r.signals["v"].data.tolist() == [1.0, 2.0]
    m = tmp_path / "mono.csv"                             # a first column that goes up is still the time
    m.write_text("a,b\n1,2\n3,4\n5,6\n")
    assert _load(m).time.tolist() == [1.0, 3.0, 5.0]
    n = tmp_path / "named.csv"                            # a named time column is sorted, as before
    n.write_text("time,a\n0,1\n1,2\n0.5,3\n")
    r = _load(n)
    assert r.time.tolist() == [0.0, 0.5, 1.0] and r.signals["a"].data.tolist() == [1.0, 3.0, 2.0]


def test_row_number_time_goes_on_in_live_mode(tmp_path):
    from svcore.csv_loader import append_new_rows
    p = tmp_path / "live.csv"
    p.write_text("a,b\n5,1\n3,2\n")
    r = _load(p)
    with open(p, "a") as f:
        f.write("7,3\n1,4\n")
    assert append_new_rows(r) == 2
    assert r.time.tolist() == [0.0, 1.0, 2.0, 3.0] and r.signals["a"].data.tolist() == [5.0, 3.0, 7.0, 1.0]
