"""P3 (owner, 2026-11-12): an ArduPilot log where the firmware wrote ONE message type with a length other
than its FMT declares. Every such message broke the chain, and a long log was refused as "too damaged".
Now the faulty type is found, the chain is repaired, that type alone is left out and the report says so.

Fixtures: tools/make_bad_bin_fixture.py (CTUN, declared 43 bytes; the clean file is cut after the same
messages, to compare with)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.bin_loader import BinFormatError, DataFlash, load_bin  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "tests", "data")
TOOLS = os.path.join(os.path.dirname(__file__), "..", "..", "tools")


def _load(kind):
    return load_bin(os.path.join(DATA, f"bad_len_{kind}.bin"), kind)


@pytest.fixture(scope="module")
def clean():
    run, _ = _load("clean")
    return run


@pytest.mark.parametrize("kind,written", [("longer", 47), ("shorter", 40), ("random", None)])
def test_one_faulty_type_is_left_out_and_the_rest_is_intact(clean, kind, written):
    run, rep = _load(kind)
    assert not [n for n in run.signals if n.startswith("CTUN")]               # its signals are absent
    faulty = rep["faultyMessages"]
    assert [f["name"] for f in faulty] == ["CTUN"] and faulty[0]["declared"] == 43
    assert faulty[0].get("written") == written                                  # both lengths, when one explains it
    others = [n for n in clean.signals if not n.startswith("CTUN")]
    assert sorted(others) == sorted(run.signals)
    for n in others:                                                            # same count, same values
        a, b = clean.signals[n], run.signals[n]
        assert np.array_equal(np.asarray(a.time), np.asarray(b.time)), n
        assert np.array_equal(np.asarray(a.data), np.asarray(b.data), equal_nan=True), n
    assert "corruptBytes" not in rep and "droppedMessages" not in rep          # nothing else was damaged


def _same_except_ctun(clean, run):
    others = [n for n in clean.signals if not n.startswith("CTUN")]
    assert sorted(others) == sorted(run.signals)
    for n in others:
        assert np.array_equal(np.asarray(clean.signals[n].time), np.asarray(run.signals[n].time)), n
        assert np.array_equal(np.asarray(clean.signals[n].data), np.asarray(run.signals[n].data), equal_nan=True), n


def test_more_column_names_than_values_the_owners_fault(clean):
    """Owner, 2026-11-12: a Write() call in the firmware got three more labels than its format and its
    values. The FMT used to be refused, so every CTUN broke the chain and a long log was refused as too
    damaged (and the type written before CTUN was taken for a faulty one). Now its length is used for
    the chain and CTUN alone is left out - its names cannot be matched to its values."""
    run, rep = load_bin(os.path.join(DATA, "bad_names.bin"), "names")
    assert rep["faultyMessages"] == [{"name": "CTUN", "names": 12, "fields": 9}]
    assert not [n for n in run.signals if n.startswith("CTUN")]
    _same_except_ctun(clean, run)
    assert "corruptBytes" not in rep and "droppedMessages" not in rep


def _rebuild(kind_fmt, kind_msg):
    """The example's start with CTUN's FMT changed (kind_fmt: 'names' / 'drop') and its messages (kind_msg)."""
    sys.path.insert(0, TOOLS)
    import make_bad_bin_fixture as m
    with open(m.SRC, "rb") as f:
        src = f.read()
    bad, stop, out = m.type_of(src, "CTUN"), m.count(src), bytearray()
    for k, (typ, msg) in enumerate(m.messages(src)):
        if k >= stop:
            break
        if typ == 128 and msg[3] == bad:
            if kind_fmt == "drop":
                continue
            if kind_fmt == "chars":                  # three more format characters, the names as they were
                fmt = msg[9:25].rstrip(b"\0") + b"fff"
                msg = msg[:4] + bytes([msg[4] + 12]) + msg[5:9] + fmt.ljust(16, b"\0") + msg[25:]
            else:
                msg = msg[:25] + (msg[25:89].rstrip(b"\0") + b",Ex1,Ex2,Ex3")[:64].ljust(64, b"\0")
        elif typ == bad and kind_msg == "shorter":
            msg = msg[:-3]
        elif typ == bad and kind_fmt == "chars":
            msg = msg + bytes(range(12))             # their values: whatever the firmware read
        out += msg
    return bytes(out)


def test_a_type_with_no_fmt_at_all_is_learned_and_skipped(clean, tmp_path):
    p = tmp_path / "nofmt.bin"
    p.write_bytes(_rebuild("drop", "same"))
    run, rep = load_bin(str(p), "nofmt")
    assert rep["faultyMessages"] == [{"name": "#141", "written": 43, "noFormat": True}]
    _same_except_ctun(clean, run)


def test_wrong_names_and_a_wrong_length_together(clean, tmp_path):
    p = tmp_path / "both.bin"
    p.write_bytes(_rebuild("names", "shorter"))
    run, rep = load_bin(str(p), "both")
    assert rep["faultyMessages"] == [{"name": "CTUN", "written": 40, "declared": 43}]
    _same_except_ctun(clean, run)


def test_more_format_characters_than_names(clean, tmp_path):
    """The other reading of the same fault: three characters added to the format, not the names (the
    values written are whatever the firmware found) - the same: chained by its length, left out."""
    p = tmp_path / "chars.bin"
    p.write_bytes(_rebuild("chars", "same"))
    run, rep = load_bin(str(p), "chars")
    assert rep["faultyMessages"] == [{"name": "CTUN", "names": 9, "fields": 12}]
    _same_except_ctun(clean, run)


def test_a_good_fmt_is_not_replaced_by_one_with_wrong_names():
    from svcore.bin_loader import _parse_fmt_payload
    good = bytes([200, 3 + 8 + 4]) + b"ABCD" + b"Qf".ljust(16, b"\0") + b"TimeUS,X".ljust(64, b"\0")
    off = good[:22] + b"TimeUS,X,Y,Z".ljust(64, b"\0")
    assert _parse_fmt_payload(good).names_off is None and _parse_fmt_payload(off).names_off == (4, 2)
    df = DataFlash()
    buf = np.frombuffer(b"\xa3\x95\x80" + good + b"\xa3\x95\x80" + off, dtype=np.uint8)
    df._add_formats(buf, np.array([0, 89]))
    assert df.formats[200].names_off is None


def test_the_clean_log_reports_nothing(clean):
    _run, rep = _load("clean")
    assert "faultyMessages" not in rep and "readableShare" not in rep


def test_a_rare_type_with_header_like_bytes_is_not_taken_for_faulty():
    """False candidates (A3 95 <type> inside a payload) are never 'entered' by the chain, so they do not
    count: a clean log loses no type."""
    with open(os.path.join(DATA, "bad_len_clean.bin"), "rb") as f:
        data = bytearray(f.read())
    df = DataFlash()
    buf = np.frombuffer(bytes(data), dtype=np.uint8)
    pos, _types, _end = df.frame(buf)
    assert not df.misdeclared and not df.unreadable and len(pos)


def test_noise_is_still_refused(tmp_path):
    """A file whose start is a valid FMT but whose rest is noise full of header-like pairs: under 20 % of
    its bytes chain, so it is refused (the limits stay for a file that is mostly damage)."""
    with open(os.path.join(DATA, "bad_len_clean.bin"), "rb") as f:
        data = f.read()
    k = 0
    while data[k + 2] == 128:                                                   # the leading FMT messages
        k += 89
    head = data[:k]
    rnd = np.random.default_rng(3)
    noise = rnd.integers(0, 256, 4_000_000, dtype=np.uint8)
    at = rnd.choice(len(noise) - 3, 60_000, replace=False)                     # many fake headers
    noise[at], noise[at + 1], noise[at + 2] = 0xA3, 0x95, 0x88                  # ATT's type: a known one
    p = tmp_path / "noise.bin"
    p.write_bytes(head + noise.tobytes())
    with pytest.raises(BinFormatError):
        load_bin(str(p), "noise")


def test_the_fixture_script_makes_the_same_files(tmp_path):
    """The fixtures are made by the script, not by hand."""
    sys.path.insert(0, TOOLS)
    import make_bad_bin_fixture as m
    with open(m.SRC, "rb") as f:
        src = f.read()
    with open(os.path.join(DATA, "bad_len_shorter.bin"), "rb") as f:
        assert m.make(src, "shorter") == f.read()
