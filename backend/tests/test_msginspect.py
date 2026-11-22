"""MSG4: the guided view of a byte stream - the patterns that recur (header / footer candidates), the first messages
byte by byte with each byte's role and each field's value, the whole stream counted by the structure."""
import json
import os

import numpy as np

from svcore import msginspect as M
from svcore import protocol as P

EX = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


def _csv(folder, name):
    return np.genfromtxt(os.path.join(EX, folder, name), delimiter=",", names=True)


def _struct(name):
    return json.load(open(os.path.join(EX, "serial_link", name), encoding="utf-8"))


def test_patterns_find_the_header_first():
    d = _csv("serial_link", "link_tx_rx.csv")
    r = M.inspect([(d["time"], d["rx_byte"])])
    assert r["suggested"] and r["structure"]["header"] == "EB90"
    top = r["patterns"][0]
    assert top["hex"] == "EB 90" and top["role"] == "header" and top["count"] >= 1990
    assert any(p["role"] == "start" for p in r["patterns"])           # header + type + length of the common message


def test_frames_roles_and_values_by_the_users_structure():
    d = _csv("serial_link", "link_tx_rx.csv")
    st = _struct("link_rx.svmsg.json")
    r = M.inspect([(d["time"], d["rx_byte"])], None, st, n=40)
    assert not r["suggested"]
    full = P.parse([(d["time"], d["rx_byte"])], st)["report"]
    assert r["summary"]["messages"] == full["frames"] and r["summary"]["bad"] == full["bad"] == 2
    assert r["summary"]["byMessage"]["ATTITUDE"] == full["messages"]["ATTITUDE"]
    att = next(f for f in r["frames"] if f["message"] == "ATTITUDE")
    assert att["roles"][:4] == ["header", "header", "type", "length"] and att["roles"][-2:] == ["checksum", "checksum"]
    assert len(att["bytes"]) == att["len"] == len(att["roles"]) == len(att["fields"])
    names = [f["name"] for f in next(m for m in st["messages"] if m["name"] == "ATTITUDE")["fields"]]
    alt = att["values"][names.index("alt")]
    assert 49 < alt < 81                                               # i32 LSB first, cm -> m: the real value
    j = names.index("alt")
    assert [x for x, f in zip(att["roles"], att["fields"]) if f == j] == ["field"] * 4


def test_footer_and_text_streams():
    d = _csv("serial_link", "sensor_uart.csv")
    r = M.inspect([(d["time"], d["sensor_byte"])], None, _struct("sensor.svmsg.json"))
    f = r["frames"][0]
    assert f["roles"][-2:] == ["footer", "footer"] and f["roles"][-3] == "checksum"
    assert any(p["role"] == "footer" for p in r["patterns"])
    text = "".join("$GPGGA,12000%d.00,3200.0000,N,03448.0000,E,1,08,0.9,10.0,M,0.0,M,,*00\r\n" % i for i in range(8))
    b = np.frombuffer(text.encode(), dtype=np.uint8).astype(float)
    r = M.inspect([(np.arange(len(b)) * 1e-3, b)], None, dict(P.NMEA, checksum=None), n=3)
    assert r["text"] and len(r["frames"]) == 3 and r["frames"][0]["message"] == "GGA"
    assert abs(r["frames"][0]["values"][1] - 32.0) < 1e-9 and r["summary"]["messages"] == 8


def test_a_stream_it_cannot_frame_says_why():
    rng = np.random.default_rng(1)
    b = rng.integers(0, 256, 3000).astype(float)
    r = M.inspect([(np.arange(len(b)) * 1e-3, b)])
    assert r["error"] and r["frames"] == [] and len(r["head"]) == 64
    bad = M.inspect([(np.arange(len(b)) * 1e-3, b)], None, {"kind": "binary", "header": "AA55", "size": 8,
                                                         "messages": [{"id": 0, "name": "M", "fields": []}]})
    assert bad["frames"] == [] and "header" in bad["error"]


def _burst_stream(pause, cut, hdr=(0xA5, 0x5A), ftr=(0x0D, 0x0A), n=300, seed=3):
    """Messages header + 8 bytes + footer, 0.1 ms per byte and `pause` s between messages; the recording starts
    `cut` bytes into the first message (as one that was already running)."""
    rng = np.random.default_rng(seed)
    t, b, now = [], [], 0.0
    for _ in range(n):
        for x in list(hdr) + list(rng.integers(0, 256, 8)) + list(ftr):
            b.append(float(x))
            t.append(now)
            now += 0.0001
        now += pause
    return np.array(t)[cut:], np.array(b)[cut:]


def test_the_time_tells_the_header_from_the_footer():
    """MSG6 (owner, 2026-11-22: "the automatic detection took the footer for the header too - maybe by time: the
    footer ends a message"). Started inside a message, the bytes alone frame from the footer as well as from the
    header; the pauses between messages say which opens one: the header comes right after a pause."""
    from svcore import bytestream as bs
    for cut in range(1, 11):
        for hdr, ftr in (((0xA5, 0x5A), (0x0D, 0x0A)), ((0x0D, 0x0A), (0xA5, 0x5A))):
            bs._CACHE.clear()
            r = bs.decode([_burst_stream(0.01, cut, hdr, ftr)])
            assert r["header"] == "%02X %02X" % hdr, (cut, hdr, r["header"])
            assert r["byTime"] == {"after": 1.0, "before": 0.0}
    # steps 2 and 3: the footer is a pattern of its own that ends a message, the header one that starts it
    out = M.inspect([_burst_stream(0.01, 5)])
    assert out["pauses"] and out["structure"]["header"] == "A55A" and out["structure"]["footer"] == "0D0A"
    pats = {p["hex"]: p for p in out["patterns"]}
    assert pats["A5 5A"]["time"] == "start" and pats["0D 0A"]["time"] == "end"
    assert "0D 0A A5 5A" not in pats                       # across a pause: two messages' bytes, not one pattern


def test_no_pauses_no_time():
    """Sent back to back at a steady rate: the time says nothing, nothing is read from it."""
    from svcore import bytestream as bs
    t, b = _burst_stream(0.0, 0)
    assert bs.pauses(t) is None
    out = M.inspect([(t, b)])
    assert not out["pauses"] and all("time" not in p for p in out["patterns"])
    # bytes stamped in packets (one time per message): the packets are the bursts
    tp = np.repeat(np.arange(300) * 0.01, 12)
    assert bs.pauses(tp) is not None and bs.pauses(tp).sum() == 300
