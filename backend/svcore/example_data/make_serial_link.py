"""MSG1 (owner, 2026-11-19): a serial link recorded byte by byte - the messages found by themselves, a dedicated plot
and a report. Two directions, two message formats, on purpose different:

    TX (ground -> vehicle)  header AA 55, a length byte (the payload's), a type byte, the payload, sum8 checksum
    RX (vehicle -> ground)  header EB 90, a type byte, a length byte, the payload, CRC-16 CCITT
    the protocol            see below: a handshake, commands answered by an ACK that echoes their sequence byte,
                            streaming both ways
    faults                  a few corrupted payload bytes (checksum errors), a corrupted length byte (the decoder
                            resyncs), unanswered commands, a retry, RX silent for 1.5 s at 18 s and a reconnect

    link_tx_rx.csv      time, tx_byte, rx_byte      - each direction its own signal (a cell is empty without a byte)
    link_mixed.csv      time, byte, dir             - both directions in one signal, dir (TX / RX) says whose byte
    link_columns.csv    time, byte_0 .. byte_15     - TX only, one message per row (the same stream as columns)

Deterministic (a fixed seed, fixed number formats).    python tools/make_serial_link.py [folder]
"""
import os
import sys
from typing import List, Tuple

import numpy as np

DURATION = 30.0
BYTE_S = 10 / 115200.0                     # one byte at 115200 baud (8N1)


def _crc_ccitt(data: bytes) -> int:
    c = 0xFFFF
    for x in data:
        c ^= x << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c


def tx_frame(typ: int, payload: bytes) -> bytes:
    body = bytes([0xAA, 0x55, len(payload), typ]) + payload
    return body + bytes([sum(body[2:]) & 0xFF])


def rx_frame(typ: int, payload: bytes) -> bytes:
    body = bytes([0xEB, 0x90, typ, len(payload)]) + payload
    c = _crc_ccitt(body[2:])
    return body + bytes([c >> 8, c & 0xFF])


# (owner, 2026-11-19: "a handshake, answers, reply packets") - the protocol of the demo:
#   TX 0x01 HELLO -> RX 0x81 HELLO_ACK, TX 0x02 CONFIG -> RX 0x82 CONFIG_ACK       the handshake, at 0 s and after the dropout
#   TX 0x10 COMMAND [seq, ...] 10 Hz -> RX 0x90 ACK [seq, status] 3-6 ms later      request / reply, the sequence byte echoed
#   TX 0x20 SETPOINT 50 Hz, 0x05 HEARTBEAT 1 Hz; RX 0xA0 ATTITUDE 50 Hz, 0xA1 STATUS 10 Hz   streaming, never answered
#   faults: commands lost (no ACK) at 3 places; one command sent again (a retry, same seq) 20 ms later and answered;
#   RX silent 18.0-19.5 s (the commands sent then unanswered), then a reconnect (the handshake again)
LOST = (77, 141, 222)                    # the commands (by number) whose ACK never comes
RETRY = 101                              # a command not answered at first, sent again 20 ms later
DROP = (18.0, 19.5)


def link() -> Tuple[List[Tuple[float, int]], List[Tuple[float, int]], List[Tuple[float, bytes]]]:
    """(time, byte) of each direction, and TX's frames (time of the first byte, bytes)."""
    rng = np.random.default_rng(20261119)
    ev_tx: List[Tuple[float, bytes]] = []
    ev_rx: List[Tuple[float, bytes]] = []

    def handshake(t0: float):
        ev_tx.append((t0, tx_frame(0x01, bytes([1, 0]))))
        ev_rx.append((t0 + 0.004, rx_frame(0x81, bytes([1]))))
        ev_tx.append((t0 + 0.010, tx_frame(0x02, bytes([50, 1, 0, 0]))))
        ev_rx.append((t0 + 0.014, rx_frame(0x82, bytes([0]))))

    def rx_up(t: float) -> bool:
        return not DROP[0] <= t < DROP[1]

    handshake(0.0003)
    handshake(DROP[1] + 0.0003)
    seq = 0
    for k in range(1, int(DURATION * 50)):
        t = k * 0.02
        if DROP[1] <= t < DROP[1] + 0.02:                # the reconnect's handshake takes this tick
            continue
        b = bytearray(tx_frame(0x20, bytes(rng.integers(0, 256, 8).tolist())))
        if k in (233, 811):                              # a byte hit by noise: a checksum error
            b[6] ^= 0x10
        if k == 1102:                                    # the length byte hit: the decoder resyncs
            b[2] = 0x3F
        ev_tx.append((t + 0.0003, bytes(b)))
        if k % 50 == 25:
            ev_tx.append((t + 0.0025, tx_frame(0x05, bytes([seq & 0xFF]))))
        if k % 5 == 0:
            n = seq
            payload = bytes([n & 0xFF]) + bytes(rng.integers(0, 256, 5).tolist())
            ev_tx.append((t + 0.0020, tx_frame(0x10, payload)))
            late = float(rng.uniform(0.003, 0.006))
            if n == RETRY:                               # no answer: the same command again 20 ms later, answered
                ev_tx.append((t + 0.0220, tx_frame(0x10, payload)))
                ev_rx.append((t + 0.0220 + late + 0.002, rx_frame(0x90, bytes([n & 0xFF, 0]))))
            elif n not in LOST and rx_up(t + 0.002 + late):
                ev_rx.append((t + 0.0020 + late + 0.002, rx_frame(0x90, bytes([n & 0xFF, 0]))))
            seq += 1
        if rx_up(t):
            b = bytearray(rx_frame(0xA0, bytes(rng.integers(0, 256, 12).tolist())))
            if k in (402, 1333):
                b[9] ^= 0x01
            ev_rx.append((t + 0.0101, bytes(b)))
            if k % 5 == 2:
                ev_rx.append((t + 0.0131, rx_frame(0xA1, bytes(rng.integers(0, 256, 10).tolist()))))

    def serial(ev: List[Tuple[float, bytes]]):
        out: List[Tuple[float, int]] = []
        frames: List[Tuple[float, bytes]] = []
        free = 0.0
        for t, f in sorted(ev, key=lambda x: x[0]):
            at = max(t, free)                             # one byte at a time on the wire
            frames.append((round(at, 6), f))
            for x in f:
                out.append((round(at, 6), x))
                at += BYTE_S
            free = at + 0.0001
        return out, frames

    tx, frames = serial(ev_tx)
    rx, _f = serial(ev_rx)
    return tx, rx, frames


def main(folder: str):
    os.makedirs(folder, exist_ok=True)
    tx, rx, frames = link()
    both = sorted([(t, b, "TX") for t, b in tx] + [(t, b, "RX") for t, b in rx])
    with open(os.path.join(folder, "link_tx_rx.csv"), "w", newline="\n", encoding="utf-8") as f:
        f.write("time,tx_byte,rx_byte\n")
        for t, b, d in both:
            f.write("%.6f,%s,%s\n" % (t, b if d == "TX" else "", b if d == "RX" else ""))
    with open(os.path.join(folder, "link_mixed.csv"), "w", newline="\n", encoding="utf-8") as f:
        f.write("time,byte,dir\n")
        for t, b, d in both:
            f.write("%.6f,%d,%s\n" % (t, b, d))
    # TX as columns: one message per row (a logger that writes a frame per line)
    rows = [(t, list(fr)) for t, fr in frames]
    width = 16
    with open(os.path.join(folder, "link_columns.csv"), "w", newline="\n", encoding="utf-8") as f:
        f.write("time," + ",".join("byte_%d" % i for i in range(width)) + "\n")
        for t, r in rows:
            f.write("%.6f,%s\n" % (round(t, 6), ",".join(str(x) for x in r[:width]) + "," * (width - min(len(r), width))))


if __name__ == "__main__":
    from svcore.example_data import REPO_EXAMPLES
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO_EXAMPLES, "serial_link"))
