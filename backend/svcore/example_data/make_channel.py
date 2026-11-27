"""CH5 (owner, 2026-11-26): one communication channel recorded twice - TX and RX in two signals of each file - with
every kind of anomaly the Messages page counts (svcore/channel.py) injected at known times, more of some in the
second recording, so the two can be compared.

    channel/link_run1.csv   time, tx_byte, rx_byte    the reference recording
    channel/link_run2.csv   time, tx_byte, rx_byte    the same link on a worse day

The link (the formats of examples/serial_link): TX AA 55 | len | type | payload | sum8, RX EB 90 | type | len |
payload | CRC-16. A handshake (TX 0x01 -> RX 0x81, TX 0x02 -> RX 0x82); TX SETPOINT 0x20 at 50 Hz with a counter in
its first payload byte, HEARTBEAT 0x05 at 1 Hz; TX COMMAND 0x10 at 10 Hz answered by RX ACK 0x90 (the seq echoed)
4-6 ms later; RX ATTITUDE 0xA0 at 50 Hz.

    the link's own faults    run1   run2   how
    bad checksum                1      5   a SETPOINT payload byte flipped on the wire
    broken frame                1      0   a SETPOINT's length byte hit (the frame runs past the next header)
    wrong length                1      0   a SETPOINT one byte longer than all the others
    unknown type                1      2   a TX 0x77 nobody sends otherwise
    silence (device)            1      2   ATTITUDE silent 1 s - the device stopped: its counter stops with it
    no reply                    2      6   COMMANDs whose ACK never came
    sent again                  1      1   a COMMAND sent again 15 ms later, answered once
    late reply                  1      4   an ACK 60 ms late instead of ~5 ms
    reconnect                   1      2   the handshake again
    handshake differs           0      1   a reconnect whose CONFIG comes before HELLO
    lost on the way             1      3   SETPOINTs missing (their counter jumps)
    the sniffer's own (CH12 - the link shows the bytes were fine)
    misread                     1      2   a COMMAND captured with a bad checksum - the device answered it (its id echoed)
    dropped                     1      1   a COMMAND missing from the capture - its ACK is there
    dropout on RX               1      1   0.4 s of RX not captured - ATTITUDE's counter ran on through it; the ACKs
                                           of that time read as no reply, their sequence skips
    found                      23     42   by cause: run1 5 the link's, 8 likely the capture's, 10 no effect seen;
                                           run2 11 / 9 / 22 (svcore/channel.py; test_channel)

Deterministic (no randomness, fixed number formats).    python tools/make_channel.py [folder]
"""
import os
import struct
import sys
from typing import Dict, List, Tuple

from svcore.example_data.make_serial_link import BYTE_S, rx_frame, tx_frame

DURATION = 24.0

RUNS: Dict[str, Dict] = {
    "link_run1.csv": {"checksum": [4.02], "broken": [6.02], "length": [8.02], "unknown": [9.505], "lost": [11.02],
                      "silent": [(13.0, 14.0)], "noreply": [5.1, 15.3], "retry": [7.1], "late": [10.1],
                      "reconnect": [(20.0, False)],
                      "cap_bad": [16.1], "cap_lost": [17.3], "cap_gap": [(21.0, 21.4)]},
    "link_run2.csv": {"checksum": [3.02, 6.42, 9.62, 14.02, 17.22], "broken": [], "length": [], "unknown": [5.505, 16.505],
                      "lost": [4.42, 11.02, 18.62], "silent": [(8.0, 9.0), (15.5, 16.5)],
                      "noreply": [2.1, 6.1, 9.3, 12.1, 13.5, 19.1], "retry": [7.1], "late": [3.3, 10.1, 14.7, 18.1],
                      "reconnect": [(12.6, False), (20.0, True)],
                      "cap_bad": [4.7, 15.1], "cap_lost": [8.3], "cap_gap": [(10.55, 10.95)]},
}


def _near(x: float, at: List[float], tol: float = 0.005) -> bool:
    return any(abs(x - a) < tol for a in at)


def link(f: Dict) -> Tuple[List[Tuple[float, bytes]], List[Tuple[float, bytes]]]:
    tx: List[Tuple[float, bytes]] = []
    rx: List[Tuple[float, bytes]] = []

    def handshake(t0: float, swapped: bool):
        steps = ((0x02, 0x82, bytes([50, 1, 0, 0])), (0x01, 0x81, bytes([1, 0]))) if swapped else \
            ((0x01, 0x81, bytes([1, 0])), (0x02, 0x82, bytes([50, 1, 0, 0])))
        for k, (a, b, pay) in enumerate(steps):
            tx.append((t0 + 0.01 * k + 0.0003, tx_frame(a, pay)))
            rx.append((t0 + 0.01 * k + 0.0043, rx_frame(b, bytes([1]))))

    handshake(0.0, False)
    for t0, swapped in f["reconnect"]:
        handshake(t0, swapped)
    seq = 0
    att = 0                                               # ATTITUDE's counter (its first payload byte)
    for k in range(2, int(DURATION * 50)):
        t = round(k * 0.02, 6)
        if not _near(t + 0.02, f["lost"]):
            pay = bytearray([k & 0xFF]) + struct.pack("<hh", (k * 7) % 2000 - 1000, (k * 3) % 900)
            if _near(t + 0.02, f["length"]):
                pay += b"\x00"
            b = bytearray(tx_frame(0x20, bytes(pay)))
            if _near(t + 0.02, f["checksum"]):
                b[6] ^= 0x10
            if _near(t + 0.02, f["broken"]):
                b[2] = 0x3F
            tx.append((t + 0.0003, bytes(b)))
        if k % 50 == 25:
            tx.append((t + 0.0025, tx_frame(0x05, bytes([(k // 50) & 0xFF]))))
        if _near(t + 0.005, f["unknown"]):
            tx.append((t + 0.005, tx_frame(0x77, bytes([0xDE, 0xAD]))))
        if k % 5 == 0:
            n = seq
            cmd = bytes([n & 0xFF, 1 + n % 3]) + struct.pack("<f", 0.5 * (n % 10))
            tc = t + 0.002
            c = bytearray(tx_frame(0x10, cmd))
            if _near(t + 0.1, f["cap_bad"], 0.01):            # the sniffer misread a byte: the device answers it all the same
                c[6] ^= 0x04
            if not _near(t + 0.1, f["cap_lost"], 0.01):        # the sniffer dropped it: its ACK is there
                tx.append((tc, bytes(c)))
            lat = 0.004 + 0.0005 * (n % 5)
            if _near(t + 0.1, f["late"], 0.01):
                lat = 0.06
            if _near(t + 0.1, f["retry"], 0.01):
                tx.append((tc + 0.015, tx_frame(0x10, cmd)))
                rx.append((tc + 0.015 + lat, rx_frame(0x90, bytes([n & 0xFF, 0]))))
            elif not _near(t + 0.1, f["noreply"], 0.01):
                rx.append((tc + lat, rx_frame(0x90, bytes([n & 0xFF, 0]))))
            seq += 1
        if not any(a <= t < b for a, b in f["silent"]):        # the device silent: its counter stops with it
            rx.append((t + 0.0101, rx_frame(0xA0, bytes([att & 0xFF]) + struct.pack(">hhH", (k * 11) % 3000 - 1500, (k * 5) % 1000, (k * 13) % 36000))))
            att += 1
    # the sniffer's own dropout on RX: the device kept sending (its counter ran on), nothing of it was captured
    rx = [(t, fr) for t, fr in rx if not any(a <= t < b for a, b in f["cap_gap"])]
    return tx, rx


def _serial(ev: List[Tuple[float, bytes]]) -> List[Tuple[float, int]]:
    out: List[Tuple[float, int]] = []
    free = 0.0
    for t, f in sorted(ev, key=lambda x: x[0]):
        at = max(t, free)
        for x in f:
            out.append((round(at, 6), x))
            at += BYTE_S
        free = at + 0.0001
    return out


def main(folder: str):
    os.makedirs(folder, exist_ok=True)
    for name, f in RUNS.items():
        tx, rx = link(f)
        both = sorted([(t, b, 0) for t, b in _serial(tx)] + [(t, b, 1) for t, b in _serial(rx)])
        with open(os.path.join(folder, name), "w", newline="\n", encoding="utf-8") as fh:
            fh.write("time,tx_byte,rx_byte\n")
            for t, b, d in both:
                fh.write("%.6f,%s,%s\n" % (t, b if d == 0 else "", b if d == 1 else ""))


if __name__ == "__main__":
    from svcore.example_data import REPO_EXAMPLES
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO_EXAMPLES, "channel"))
