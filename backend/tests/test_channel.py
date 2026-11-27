"""CH2: a channel's anomalies (svcore/channel.py) - each kind injected once into a clean link and found, counted, at
its time; nothing found in the clean link."""
import struct

import numpy as np
import pytest

from svcore.bytestream import decode
from svcore.channel import KINDS, anomalies, count_signal
from svcore.example_data.make_serial_link import rx_frame, tx_frame

BYTE_S = 10 / 115200.0


def _serial(ev):
    t_out, b_out, free = [], [], 0.0
    for t, f in sorted(ev, key=lambda x: x[0]):
        at = max(t, free)
        for x in f:
            t_out.append(at)
            b_out.append(x)
            at += BYTE_S
        free = at + 0.0001
    return np.array(t_out), np.array(b_out, dtype=np.float64)


def link(fault=None, n=600):
    """A clean link: a handshake, TX SETPOINT 0x20 at 50 Hz with a counter byte, COMMAND 0x10 at 10 Hz answered by
    RX ACK 0x90 (the seq echoed) 4 ms later, RX ATTITUDE 0xA0 at 50 Hz - and one fault."""
    tx, rx = [], []

    def hs(t0, order=((0x01, 0x81), (0x02, 0x82))):
        for k, (a, b) in enumerate(order):
            tx.append((t0 + 0.01 * k, tx_frame(a, bytes([1, 0]))))
            rx.append((t0 + 0.01 * k + 0.004, rx_frame(b, bytes([1]))))
    hs(0.0)
    seq = 0
    for k in range(1, n):
        t = k * 0.02
        cnt = k & 0xFF
        if fault == "counter" and k >= 300:
            cnt = (k + 3) & 0xFF                          # 3 messages lost on the way: the counter jumps
        f = bytearray(tx_frame(0x20, bytes([cnt, 7, 9, 3])))
        if fault == "checksum" and k == 200:
            f[6] ^= 0x10
        if fault == "broken" and k == 250:
            f[2] = 0x3F                                   # the length byte hit: the frame runs past the next header
        if fault == "length" and k == 260:
            f = bytearray(tx_frame(0x20, bytes([cnt, 7, 9, 3, 0])))
        if not (fault == "gap" and 400 <= k < 440):       # SETPOINT silent 0.8 s
            tx.append((t, bytes(f)))
        if fault == "unknown" and k == 333:
            tx.append((t + 0.005, tx_frame(0x77, bytes([1, 2]))))
        if k % 5 == 0:
            p = bytes([seq & 0xFF, 1]) + struct.pack("<f", 1.0)
            tx.append((t + 0.002, tx_frame(0x10, p)))
            lat = 0.004 + 0.0002 * (seq % 5)
            if fault == "late" and seq == 50:
                lat = 0.06
            if fault == "retry" and seq == 40:
                tx.append((t + 0.012, tx_frame(0x10, p)))
                rx.append((t + 0.012 + lat, rx_frame(0x90, bytes([seq & 0xFF, 0]))))
            elif not (fault == "unanswered" and seq in (30, 31)):
                rx.append((t + 0.002 + lat, rx_frame(0x90, bytes([seq & 0xFF, 0]))))
            seq += 1
        rx.append((t + 0.01, rx_frame(0xA0, bytes([5, 6, 7, k % 3]))))
    if fault == "reconnect":
        hs(n * 0.02 + 0.5)
    if fault == "handshake":
        hs(n * 0.02 + 0.5, ((0x02, 0x82), (0x01, 0x81)))
    return _serial(tx), _serial(rx)


def run(fault=None, **kw):
    (ta, ya), (tb, yb) = link(fault)
    return anomalies([("TX", decode([(ta, ya)])), ("RX", decode([(tb, yb)]))], **kw)


def test_a_clean_link_has_no_anomaly_and_its_patterns_are_found():
    r = run()
    assert r["total"] == 0 and set(r["counts"]) == set(KINDS)
    assert [s["header"] for s in r["sides"]] == ["AA 55", "EB 90"]
    assert [s["checksum"] for s in r["sides"]] == ["sum8", "crc16ccitt"]
    pair = [p for p in r["pairs"] if p["request"] == 0x10][0]
    assert pair["reply"] == 0x90 and pair["how"] == "id" and pair["mean"] == pytest.approx(0.0044, abs=0.0005)
    assert [(s["dir"], s["type"]) for s in r["handshake"][0]["steps"]] == [("TX", 1), ("RX", 0x81), ("TX", 2), ("RX", 0x82)]


@pytest.mark.parametrize("fault,kind,n,when", [
    ("checksum", "checksum", 1, 4.0), ("broken", "broken", 1, 5.0), ("length", "length", 1, 5.2),
    ("unknown", "unknown", 1, 6.665), ("counter", "counter", 1, 6.0), ("gap", "gap", 1, 7.98),
    ("unanswered", "unanswered", 2, 3.102), ("retry", "retry", 1, 4.112), ("late", "late", 1, 5.102),
    ("reconnect", "reconnect", 1, 12.5)])
def test_each_anomaly_is_found_counted_and_placed(fault, kind, n, when):
    r = run(fault)
    assert r["counts"][kind] == n, r["counts"]
    ev = r["events"]
    first = [ev["t"][i] for i in range(r["total"]) if ev["kind"][i] == kind][0]
    assert first == pytest.approx(when, abs=0.03)
    # the others stay quiet - but a retry repeats its seq, a broken frame is a message lost, and the replies that never
    # came are missing from the reply's own sequence: the counter says so too
    others = {k: v for k, v in r["counts"].items() if v and k != kind}
    assert set(others) <= {"retry": {"counter"}, "broken": {"counter"}, "unanswered": {"counter"}}.get(fault, set()), others


def test_a_handshake_out_of_order_is_its_own_anomaly():
    r = run("handshake")
    assert r["counts"]["reconnect"] == 1 and r["counts"]["handshake"] == 1
    i = r["events"]["kind"].index("handshake")
    assert "TX 0x02 → RX 0x82 → TX 0x01" in r["events"]["detail"][i]


def test_unknown_is_read_against_the_structure_when_there_is_one():
    r = run(None, known={"TX": [0x01, 0x02, 0x10], "RX": [0x81, 0x82, 0x90, 0xA0]})
    assert r["counts"]["unknown"] == r["sides"][0]["types"][0]["count"]      # every 0x20: not described
    assert r["byDir"]["TX"]["unknown"] > 0 and "unknown" not in r["byDir"]["RX"]


def test_the_count_so_far_steps_at_each_anomaly():
    r = run("unanswered")
    t, y = count_signal(r)
    assert y[0] == 0 and y[-1] == r["total"] == 3 and np.all(np.diff(y) >= 0)
    assert t[0] == pytest.approx(r["span"][0]) and t[-1] == pytest.approx(r["span"][1])


def test_the_op_messages_anomalies_both_ways():
    from svcore.bytestream import messages_signal
    (ta, ya), (tb, yb) = link("unanswered")
    t, y = messages_signal([(ta, ya), (tb, yb)], {"what": "anomalies", "link": True})
    assert y[-1] == 3                                   # 2 unanswered + the replies' sequence that skips them


def test_the_serial_link_example_counts():
    """The demo's faults (make_serial_link): 2 + 2 checksum errors, one broken frame, 18 commands unanswered (3 lost +
    15 in RX's dropout), one retry, the dropout's gaps on RX, one reconnect."""
    import os
    from svcore.example_data import REPO_EXAMPLES
    import csv
    rows = list(csv.reader(open(os.path.join(REPO_EXAMPLES, "serial_link", "link_tx_rx.csv"))))[1:]
    t = np.array([float(r[0]) for r in rows])
    a = np.array([float(r[1]) if r[1] else np.nan for r in rows])
    b = np.array([float(r[2]) if r[2] else np.nan for r in rows])
    r = anomalies([("TX", decode([(t, a)])), ("RX", decode([(t, b)]))])
    c = r["counts"]
    assert (c["checksum"], c["broken"], c["unanswered"], c["retry"], c["reconnect"], c["handshake"]) == (4, 1, 18, 1, 1, 0)
    assert c["gap"] == 3 and c["late"] == 0


def _counts(path):
    import csv
    rows = list(csv.reader(open(path)))[1:]
    t = np.array([float(r[0]) for r in rows])
    a = np.array([float(r[1]) if r[1] else np.nan for r in rows])
    b = np.array([float(r[2]) if r[2] else np.nan for r in rows])
    return anomalies([("TX", decode([(t, a)])), ("RX", decode([(t, b)]))])


def test_the_channel_example_writes_what_git_has_with_every_kind(tmp_path):
    """CH5: the two recordings of one link (make_channel.py's table): every anomaly kind in one of them, the counts
    different between them."""
    import os
    from svcore.example_data import REPO_EXAMPLES
    from svcore.example_data.make_channel import main
    main(str(tmp_path))
    ex = os.path.join(REPO_EXAMPLES, "channel")
    for f in ("link_run1.csv", "link_run2.csv"):
        assert (tmp_path / f).read_bytes() == open(os.path.join(ex, f), "rb").read()
    one, two = _counts(os.path.join(ex, "link_run1.csv")), _counts(os.path.join(ex, "link_run2.csv"))
    assert one["counts"] == {"checksum": 1, "broken": 1, "length": 1, "unknown": 1, "counter": 5, "gap": 1, "unanswered": 2,
                             "retry": 1, "late": 1, "reconnect": 1, "handshake": 0}
    assert two["counts"] == {"checksum": 5, "broken": 0, "length": 0, "unknown": 2, "counter": 10, "gap": 2, "unanswered": 6,
                             "retry": 1, "late": 4, "reconnect": 2, "handshake": 1}
    assert all(one["counts"][k] or two["counts"][k] for k in KINDS)
