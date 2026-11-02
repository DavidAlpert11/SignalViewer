"""A file that keeps growing while it is read (a logger writing to it): the read stops where the file
was when it began, the text columns stay, the next refresh / live mode reads the rest - once."""
import numpy as np
import pytest

from svcore import csv_loader


def _write(path, a, b, partial=""):
    with open(path, "a") as f:
        for i in range(a, b):
            f.write(f"{i * 0.1:.1f},{i},{'ON' if i % 2 else 'OFF'}\n")
        f.write(partial)


@pytest.fixture
def growing(tmp_path, monkeypatch):
    """Every progress report of the parser appends 1000 more rows (faster than any reader)."""
    p = tmp_path / "g.csv"
    p.write_text("Time,n,state\n")
    _write(p, 0, 5000)
    monkeypatch.setattr(csv_loader, "PART_BYTES", 4096)           # many parts -> many reports
    monkeypatch.setattr(csv_loader, "CACHE_ENABLED", False)
    state = {"next": 5000, "on": True}
    real = csv_loader._progress

    def grow(frac, phase="read"):
        if state["on"] and state["next"] < 200000:     # (bounded: a regression fails, not hangs)
            _write(p, state["next"], state["next"] + 1000)
            state["next"] += 1000
        real(frac, phase)
    monkeypatch.setattr(csv_loader, "_progress", grow)
    return p, state


def test_the_read_stops_where_the_file_was(growing):
    p, state = growing
    run = csv_loader.load_csv(str(p), [str(p)])
    assert len(run.time) == 5000 and run.time[-1] == pytest.approx(499.9)
    assert "state" in run.signals                                    # the text pass saw the same rows
    assert run.byte_offset < p.stat().st_size                         # the rest is left for later
    # live mode reads the rest, every row once
    state["on"] = False
    assert csv_loader.append_new_rows(run) > 0
    n = run.signals["n"].data
    assert len(n) == state["next"] and np.array_equal(n, np.arange(state["next"]))


@pytest.mark.parametrize("eol", ["\n", "\r\n"])
def test_a_half_written_last_line_waits_while_the_file_grows(tmp_path, monkeypatch, eol):
    # bytes, not write_text: on Windows write_text turns "\n" into "\r\n" and the lengths below are
    # bytes (the release build of 1.18.0 failed on that); both line ends are tested on every platform
    p = tmp_path / "h.csv"
    done = f"Time,n{eol}0.0,0{eol}0.1,1{eol}"
    p.write_bytes((done + "0.2,2").encode())                       # the writer is in the middle of a row
    real = csv_loader.os.path.getsize
    monkeypatch.setattr(csv_loader.os.path, "getsize", lambda x: real(x) + (10 if str(x) == str(p) else 0))
    assert csv_loader._complete_part(str(p), real(p)) == len(done.encode())
    monkeypatch.setattr(csv_loader.os.path, "getsize", real)
    # stopped without a final line break: its last row counts
    assert csv_loader._complete_part(str(p), real(p)) == real(p)


def test_refresh_after_a_read_of_a_growing_file_is_not_unchanged(tmp_path, monkeypatch):
    """The store keeps the file's size from BEFORE the read: grown meanwhile = newer on the disk."""
    from app.store import Store
    p = tmp_path / "s.csv"
    p.write_text("Time,n\n")
    _write_plain = lambda a, b: p.open("a").write("".join(f"{i * 0.1:.1f},{i}\n" for i in range(a, b)))
    _write_plain(0, 100)
    real = csv_loader.load_csv

    def load_and_grow(*a, **k):
        r = real(*a, **k)
        _write_plain(100, 200)                                        # written while it was read
        return r
    monkeypatch.setattr("app.store.load_csv", load_and_grow)
    s = Store()
    lr = s.open_file(str(p), {})
    assert s.newer_on_disk()                                          # offered again
    monkeypatch.setattr("app.store.load_csv", real)
    assert s.reload_all()["reloaded"] == [lr.id]
    assert len(s.runs[lr.id].run.time) == 200
