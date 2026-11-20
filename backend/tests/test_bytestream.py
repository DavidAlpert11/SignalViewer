"""MSG1: messages in a byte stream - framing found by itself, known answers (counts, order, period, checksum errors, a
corrupted byte resynced), columns, a direction column, the derived op and the report part on the demo."""
import os

import numpy as np
import pytest

from svcore import bytestream as bs
from svcore.analysis import OpError, compute
from svcore.example_data import make_serial_link as sl

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "serial_link")


def stream(frames, dt=0.001, gap_at=None):
    t, y, at = [], [], 0.0
    for k, f in enumerate(frames):
        if gap_at is not None and k == gap_at:
            at += 2.0
        for x in f:
            t.append(at)
            y.append(float(x))
            at += dt / 20
        at += dt
    return np.array(t), np.array(y)


def ab(typ, payload):
    return sl.tx_frame(typ, bytes(payload))


def test_crc_and_fletcher_known_values():
    assert bs.crc16_ccitt(b"123456789") == 0x29B1          # CRC-16/CCITT-FALSE check value
    assert bs.crc16_modbus(b"123456789") == 0x4B37         # CRC-16/MODBUS check value
    # Fletcher-16 as UBX: both sums wrap at 256 (not the textbook mod 255): a = 495 % 256, b = sum of the running a
    assert bs.fletcher16(b"abcde") == (495 % 256, (97 + 195 + 294 + 394 + 495) % 256)


def test_length_type_checksum_order_found():
    frames = []
    for k in range(300):
        frames.append(ab(0x20, [k % 256] * 8))
        if k % 3 == 0:
            frames.append(ab(0x10, [1, 2, 3, 4]))
    t, y = stream(frames)
    r = bs.decode([(t, y)])
    assert r["header"] == "AA 55"
    assert r["rule"]["how"] == "length" and r["rule"]["off"] == 2 and r["rule"]["add"] == 5
    assert r["typeOffset"] == 3
    assert r["checksum"]["scheme"] == "sum8" and r["errors"] == 0 and r["resyncs"] == 0 and r["outside"] == 0
    assert r["count"] == 400
    by = {x["type"]: x for x in r["types"]}
    assert by[0x20]["count"] == 300 and by[0x10]["count"] == 100 and by[0x20]["lengths"] == [13] and by[0x10]["lengths"] == [9]
    assert r["order"]["period"] == 4 and r["order"]["sequence"] == [0x20, 0x10, 0x20, 0x20]


def test_checksum_error_and_corrupted_length_resynced():
    frames = [bytearray(ab(0x20, [7] * 8)) for _ in range(200)]
    frames[50][6] ^= 0xFF                                  # a payload byte: a checksum error, the frame still framed
    frames[120][2] = 0x40                                  # the length byte: the walk resyncs, that message is lost
    t, y = stream([bytes(f) for f in frames])
    r = bs.decode([(t, y)])
    assert r["errors"] == 1 and r["resyncs"] == 1
    assert r["count"] == 199
    assert not r["messages"]["ok"][50]


def test_gap_found_and_needle_bytes_all_counted():
    frames = [ab(0x20, [1] * 8) for _ in range(100)]
    t, y = stream(frames, gap_at=60)
    r = bs.decode([(t, y)])
    assert r["count"] == 100 and r["inFrames"] == len(y)    # every byte in a message
    assert len(r["gaps"]) == 1 and r["gaps"][0]["dt"] == pytest.approx(2.0 + 0.001, abs=0.01)


def test_crc16_and_header_after_type():
    frames = [sl.rx_frame(0x82 if k % 2 else 0x81, bytes([k % 256] * (12 if k % 2 else 10))) for k in range(200)]
    t, y = stream(frames)
    r = bs.decode([(t, y)])
    assert r["header"] == "EB 90" and r["checksum"]["scheme"] == "crc16ccitt" and r["errors"] == 0
    assert r["rule"]["how"] == "length" and r["rule"]["off"] == 3 and r["typeOffset"] == 2
    assert r["order"]["period"] == 2


def test_not_a_byte_stream_says_why():
    t = np.arange(100) * 0.1
    with pytest.raises(bs.StreamError, match="0..255"):
        bs.decode([(t, np.sin(t) * 1000)])
    with pytest.raises(bs.StreamError, match="No repeating messages"):
        bs.decode([(t, (np.arange(100) * 37 % 256).astype(float))])
    with pytest.raises(OpError):
        compute("messages", [(t, np.sin(t))], {"what": "type"})


def test_forced_options():
    frames = [ab(0x20, [1] * 8) for _ in range(50)]
    t, y = stream(frames)
    r = bs.decode([(t, y)], {"header": "AA55", "checksum": "none"})
    assert r["checksum"] is None and r["count"] == 50
    with pytest.raises(bs.StreamError, match="hex"):
        bs.decode([(t, y)], {"header": "AA5"})


def _csv(name, text=False):
    # an empty cell is NaN only when read as floats (dtype=None would make it -1)
    return np.genfromtxt(os.path.join(EX, name), delimiter=",", names=True, dtype=None if text else float, encoding="utf-8")


def test_demo_two_signals_columns_and_mixed():
    d = _csv("link_tx_rx.csv")
    tx = bs.decode([(d["time"], d["tx_byte"].astype(float))])
    rx = bs.decode([(d["time"], d["rx_byte"].astype(float))])
    assert (tx["header"], tx["checksum"]["scheme"], tx["count"], tx["errors"], tx["resyncs"]) == ("AA 55", "sum8", 1829, 2, 1)
    assert (rx["header"], rx["checksum"]["scheme"], rx["count"], rx["errors"]) == ("EB 90", "crc16ccitt", 1992, 2)
    # 1497 setpoints (one resynced), 298 commands + 1 sent again, 29 heartbeats, the handshake twice
    assert {x["type"]: x["count"] for x in tx["types"]} == {0x20: 1497, 0x10: 299, 0x05: 29, 0x01: 2, 0x02: 2}
    assert {x["type"]: x["count"] for x in rx["types"]} == {0xA0: 1423, 0xA1: 285, 0x90: 280, 0x81: 2, 0x82: 2}
    assert {x["type"]: round(x["period"], 3) for x in tx["types"] if x["count"] > 10} == {0x20: 0.02, 0x10: 0.1, 0x05: 1.0}
    assert len(rx["gaps"]) == 1 and rx["gaps"][0]["from"] == pytest.approx(17.99, abs=0.01)
    c = _csv("link_columns.csv")
    cols = bs.decode([(c["time"], c["byte_%d" % i].astype(float)) for i in range(16)])
    assert (cols["count"], cols["errors"], cols["resyncs"]) == (1829, 2, 1)
    m = _csv("link_mixed.csv", text=True)
    d_rx = (m["dir"] == "RX").astype(float)
    both = [(m["time"], m["byte"].astype(float)), (m["time"], d_rx)]
    assert bs.decode(both, {"dir": 1})["count"] == 1992
    assert bs.decode(both, {"dir": 0})["count"] == 1829
    t, y = compute("messages", both, {"what": "interval", "dir": 0})
    assert len(t) == 1829 and np.nanmax(y) == pytest.approx(19.5, abs=0.01)  # the handshake's two HELLOs apart
    t, y = compute("messages", [(d["time"], d["rx_byte"].astype(float))], {"what": "ok"})
    assert int((y == 0).sum()) == 2


def test_demo_writes_what_git_has(tmp_path):
    sl.main(str(tmp_path))
    for f in ("link_tx_rx.csv", "link_mixed.csv", "link_columns.csv"):
        assert (tmp_path / f).read_bytes() == open(os.path.join(EX, f), "rb").read()


def test_report_part_on_the_demo():
    from app.store import Store
    from app.reportparts import Part, find_streams, messages, scan
    st = Store()
    for f in ("link_tx_rx.csv", "link_mixed.csv"):
        st.open_file(os.path.join(EX, f))
    rids = [r for r in st.runs if r != "derived"]
    found = find_streams(st, rids)
    names = sorted(s_["name"] for s_ in found)
    assert names == ["byte RX", "byte TX", "rx_byte", "tx_byte"]
    items, extra = [], {}
    p = Part(st, items, extra, "en")
    messages(p, rids, "", {})
    md = "\n".join(p.md)
    assert "1829 messages" in md and "1992 messages" in md and "AA 55" in md and "EB 90" in md and "crc16ccitt" in md
    assert "0x20" in md and "No messages for" in md
    assert len(items) == 5                                 # latency, order, rate, interval, checksum errors - one plot each
    # the packet's structure (owner, 2026-11-19): the fixed header, the length / type byte, the payload, the checksum
    assert "| Header | 0–1 | fixed AA 55 |" in md and "| Length | 2 |" in md and "| Message type | 3 | 5 kinds: 0x01, 0x02, 0x05, 0x10, 0x20 |" in md
    assert "| Message type | 2 | 5 kinds: 0x81, 0x82, 0x90, 0xA0, 0xA1 |" in md and "crc16ccitt over the bytes from 2" in md
    assert "**The messages in order** (the first 40" in md and "0x01 0x02 0x20 0x20" in md
    assert any(h["level"] == "warn" for h in p.highlights)
    assert {s_["name"] for s_ in scan(st)["streams"]} == set(names)


def test_defined_streams_tx_rx_both():
    """Owner, 2026-11-19: a signal defined as only TX, only RX, or both with a direction column (TX's code given)."""
    from app.store import Store
    from app.reportparts import find_streams
    st = Store()
    a = st.open_file(os.path.join(EX, "link_tx_rx.csv")).id
    m = st.open_file(os.path.join(EX, "link_mixed.csv")).id
    lab = st.labels(f"{m}/dir")
    tx_code = [int(k) for k, v in lab.items() if v == "TX"][0]
    defs = [{"sources": [f"{a}/rx_byte"], "carries": "rx"},
            {"sources": [f"{m}/byte"], "carries": "both", "dir": f"{m}/dir", "txValue": tx_code}]
    got = {s_["name"]: s_["r"]["count"] for s_ in find_streams(st, [a, m], defs)}
    assert got["rx_byte RX"] == 1992 and got["byte TX"] == 1829 and got["byte RX"] == 1992
    assert got["tx_byte"] == 1829                          # not defined: found by itself
    assert "rx_byte" not in got                            # defined: not found twice


def test_requests_replies_handshake_on_the_demo():
    """Owner, 2026-11-19: answers, reply packets, a handshake - known answers from the demo's protocol."""
    d = _csv("link_tx_rx.csv")
    e = bs.exchange(bs.decode([(d["time"], d["tx_byte"])]), bs.decode([(d["time"], d["rx_byte"])]))
    by = {(q["request"], q["reply"]): q for q in e["pairs"]}
    assert set(by) == {(0x01, 0x81), (0x02, 0x82), (0x10, 0x90)}      # streaming (0x20, 0x05, 0xA0, 0xA1): no reply
    c = by[(0x10, 0x90)]
    assert c["how"] == "id" and c["echo"] == {"request": 0, "reply": 0}                # the sequence byte echoed
    assert (c["requests"], c["replies"], len(c["unanswered"]), len(c["orphans"])) == (299, 280, 18, 0)
    assert [round(x, 2) for x in c["retries"]] == [10.22] and [round(x, 2) for x in c["retried"]] == [10.2]
    assert sum(1 for u in c["unanswered"] if 18.0 <= u < 19.5) == 15               # the dropout: 15 commands lost
    assert 0.005 <= c["latency"]["min"] and c["latency"]["max"] <= 0.0081            # 3-6 ms + the bytes on the wire
    hs = e["handshake"]
    assert [round(h["t"], 1) for h in hs] == [0.0, 19.5]                             # opened, and a reconnect
    assert [(x["dir"], x["type"]) for x in hs[1]["steps"]] == [("TX", 1), ("RX", 0x81), ("TX", 2), ("RX", 0x82)]
    t, y = compute("messages", [(d["time"], d["tx_byte"]), (d["time"], d["rx_byte"])], {"what": "latency", "link": True})
    assert len(t) == 284 and np.all(np.diff(t) >= 0)                                 # 2 + 2 + 280 answered
