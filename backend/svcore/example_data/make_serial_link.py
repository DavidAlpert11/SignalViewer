"""MSG1 (owner, 2026-11-19): a serial link recorded byte by byte - the messages found by themselves, a dedicated plot
and a report. Two directions, two message formats, on purpose different:

    TX (ground -> vehicle)  header AA 55, a length byte (the payload's), a type byte, the payload, sum8 checksum
                            types 0x20 setpoint 50 Hz, 0x10 command 10 Hz, 0x01 heartbeat 1 Hz
    RX (vehicle -> ground)  header EB 90, a type byte, a length byte, the payload, CRC-16 CCITT
                            types 0x82 attitude 50 Hz, 0x81 status 10 Hz, 0x83 acknowledge 1 Hz
    faults                  a few corrupted payload bytes (checksum errors), a corrupted length byte (the decoder
                            resyncs), RX silent for 1.5 s at 18 s (a dropout)

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


def link() -> Tuple[List[Tuple[float, int]], List[Tuple[float, int]], List[Tuple[float, bytes]]]:
    """(time, byte) of each direction, and TX's frames (time of the first byte, bytes)."""
    rng = np.random.default_rng(20261119)
    tx: List[Tuple[float, int]] = []
    rx: List[Tuple[float, int]] = []
    frames: List[Tuple[float, bytes]] = []
    seq = 0
    for k in range(int(DURATION * 50)):
        t = k * 0.02
        frames_tx = [tx_frame(0x20, bytes(rng.integers(0, 256, 8).tolist()))]
        if k % 5 == 0:
            frames_tx.append(tx_frame(0x10, bytes([seq & 0xFF]) + bytes(rng.integers(0, 256, 5).tolist())))
            seq += 1
        if k % 50 == 0:
            frames_tx.append(tx_frame(0x01, bytes([1, 0])))
        at = t + 0.0003
        for f in frames_tx:
            b = bytearray(f)
            if k in (233, 811):                          # a byte hit by noise: a checksum error
                b[6] ^= 0x10
            if k == 1102 and f[3] == 0x20:               # the length byte hit: the decoder resyncs
                b[2] = 0x3F
            frames.append((round(at, 6), bytes(b)))
            for x in b:
                tx.append((round(at, 6), x))
                at += BYTE_S
            at += 0.0002
        if 18.0 <= t < 19.5:                             # RX silent: a dropout
            continue
        frames_rx = [rx_frame(0x82, bytes(rng.integers(0, 256, 12).tolist()))]
        if k % 5 == 2:
            frames_rx.append(rx_frame(0x81, bytes(rng.integers(0, 256, 10).tolist())))
        if k % 50 == 7:
            frames_rx.append(rx_frame(0x83, bytes([0x10, seq & 0xFF])))
        at = t + 0.0061
        for f in frames_rx:
            b = bytearray(f)
            if k in (402, 1333):
                b[9] ^= 0x01
            for x in b:
                rx.append((round(at, 6), x))
                at += BYTE_S
            at += 0.0002
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
