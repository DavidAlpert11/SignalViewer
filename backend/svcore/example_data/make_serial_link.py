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
import math
import os
import struct
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
# MSG2: the payloads carry real values - the structure files beside the recordings (link_tx.svmsg.json,
# link_rx.svmsg.json) turn them into signals:
#   TX 0x20 SETPOINT  roll_cmd i16 LSB first x0.01 deg, pitch_cmd i16 LSB x0.01, yaw_cmd u16 LSB x0.01, throttle u8 %,
#                     flags u8 (bit 0 armed, bit 1 auto)
#   TX 0x10 COMMAND   seq u8, cmd u8, param f32 LSB first;   TX 0x05 HEARTBEAT counter u8
#   RX 0xA0 ATTITUDE  roll i16 MSB first x0.01 deg, pitch i16 MSB x0.01, yaw u16 MSB x0.01, alt i32 LSB x0.01 m,
#                     climb i16 LSB x0.01 m/s
#   RX 0xA1 STATUS    battery u16 LSB mV, current i16 LSB x0.01 A, temp i8 degC, sats u8, mode u8, rssi u8 (-dBm),
#                     errors u16 MSB first
#   RX 0x90 ACK       seq u8, status u8


def roll_cmd(t: float) -> float:
    return 20 * math.sin(2 * math.pi * t / 8)


def setpoint(t: float) -> bytes:
    flags = (1 if t > 1 else 0) | (2 if t > 10 else 0)
    return struct.pack("<hhHBB", round(roll_cmd(t) * 100), round(5 * math.sin(2 * math.pi * t / 5) * 100),
                       round(((90 + 10 * t) % 360) * 100), round(50 + 20 * math.sin(t / 3)), flags)


def attitude(t: float, noise: float) -> bytes:
    alt = 50 + 30 * math.sin(t / 10)
    return struct.pack(">hhH", round((roll_cmd(t - 0.15) * 0.95 + noise) * 100), round(5 * math.sin(2 * math.pi * (t - 0.15) / 5) * 100),
                       round(((90 + 10 * (t - 0.15)) % 360) * 100)) + struct.pack("<ih", round(alt * 100), round(3 * math.cos(t / 10) * 100))


def status(t: float, k: int) -> bytes:
    return struct.pack("<Hhb", round(16800 - 40 * t), round((12 + 3 * math.sin(t / 2)) * 100), round(25 + t / 6)) \
        + bytes([12 if t < 18 else 9, 2 if t > 10 else 1, round(70 + 10 * math.sin(t / 4))]) + struct.pack(">H", k // 250)


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
        b = bytearray(tx_frame(0x20, setpoint(t)))
        if k in (233, 811):                              # a byte hit by noise: a checksum error
            b[6] ^= 0x10
        if k == 1102:                                    # the length byte hit: the decoder resyncs
            b[2] = 0x3F
        ev_tx.append((t + 0.0003, bytes(b)))
        if k % 50 == 25:
            ev_tx.append((t + 0.0025, tx_frame(0x05, bytes([(k // 50) & 0xFF]))))
        if k % 5 == 0:
            n = seq
            payload = bytes([n & 0xFF, 1 + n % 3]) + struct.pack("<f", 1.5 * (n % 20))
            ev_tx.append((t + 0.0020, tx_frame(0x10, payload)))
            late = float(rng.uniform(0.003, 0.006))
            if n == RETRY:                               # no answer: the same command again 20 ms later, answered
                ev_tx.append((t + 0.0220, tx_frame(0x10, payload)))
                ev_rx.append((t + 0.0220 + late + 0.002, rx_frame(0x90, bytes([n & 0xFF, 0]))))
            elif n not in LOST and rx_up(t + 0.002 + late):
                ev_rx.append((t + 0.0020 + late + 0.002, rx_frame(0x90, bytes([n & 0xFF, 0]))))
            seq += 1
        if rx_up(t):
            b = bytearray(rx_frame(0xA0, attitude(t, float(rng.normal(0, 0.3)))))
            if k in (402, 1333):
                b[9] ^= 0x01
            ev_rx.append((t + 0.0101, bytes(b)))
            if k % 5 == 2:
                ev_rx.append((t + 0.0131, rx_frame(0xA1, status(t, k))))

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


def _fld(name, offset, type_, endian="le", scale=1, unit="", **kw):
    f = {"name": name, "offset": offset, "type": type_, "endian": endian}
    if scale != 1:
        f["scale"] = scale
    if unit:
        f["unit"] = unit
    f.update(kw)
    return f


# the messages' structure (MSG2) - offsets from the header's first byte: AA 55 | len | type | payload from 4
TX_STRUCTURE = {
    "kind": "binary", "name": "Ground -> vehicle (TX)", "header": "AA55",
    "length": {"offset": 2, "add": 5}, "type": {"offset": 3}, "checksum": {"scheme": "sum8", "from": 2},
    "messages": [
        {"id": 0x01, "name": "HELLO", "fields": [_fld("version", 4, "u8")]},
        {"id": 0x02, "name": "CONFIG", "fields": [_fld("rate", 4, "u8", unit="Hz"), _fld("mode", 5, "u8")]},
        {"id": 0x05, "name": "HEARTBEAT", "fields": [_fld("counter", 4, "u8")]},
        {"id": 0x10, "name": "COMMAND", "fields": [_fld("seq", 4, "u8"), _fld("cmd", 5, "u8", labels={"1": "GOTO", "2": "HOLD", "3": "LAND"}),
                                                    _fld("param", 6, "f32")]},
        {"id": 0x20, "name": "SETPOINT", "fields": [
            _fld("roll_cmd", 4, "i16", "le", 0.01, "deg"), _fld("pitch_cmd", 6, "i16", "le", 0.01, "deg"),
            _fld("yaw_cmd", 8, "u16", "le", 0.01, "deg"), _fld("throttle", 10, "u8", unit="%"),
            _fld("armed", 11, "u8", bits=[0, 1]), _fld("auto", 11, "u8", bits=[1, 1])]},
    ]}
# EB 90 | type | len | payload from 4 - the angles MSB first (big-endian), the altitude LSB first
RX_STRUCTURE = {
    "kind": "binary", "name": "Vehicle -> ground (RX)", "header": "EB90",
    "length": {"offset": 3, "add": 6}, "type": {"offset": 2}, "checksum": {"scheme": "crc16ccitt", "from": 2},
    "messages": [
        {"id": 0x81, "name": "HELLO_ACK", "fields": [_fld("version", 4, "u8")]},
        {"id": 0x82, "name": "CONFIG_ACK", "fields": [_fld("result", 4, "u8")]},
        {"id": 0x90, "name": "ACK", "fields": [_fld("seq", 4, "u8"), _fld("status", 5, "u8")]},
        {"id": 0xA0, "name": "ATTITUDE", "fields": [
            _fld("roll", 4, "i16", "be", 0.01, "deg"), _fld("pitch", 6, "i16", "be", 0.01, "deg"),
            _fld("yaw", 8, "u16", "be", 0.01, "deg"), _fld("alt", 10, "i32", "le", 0.01, "m"), _fld("climb", 14, "i16", "le", 0.01, "m/s")]},
        {"id": 0xA1, "name": "STATUS", "fields": [
            _fld("battery", 4, "u16", "le", 0.001, "V"), _fld("current", 6, "i16", "le", 0.01, "A"), _fld("temp", 8, "i8", unit="degC"),
            _fld("sats", 9, "u8"), _fld("mode", 10, "u8", labels={"1": "MANUAL", "2": "AUTO"}), _fld("rssi", 11, "u8", scale=-1, unit="dBm"),
            _fld("errors", 12, "u16", "be")]},
    ]}


# a third device (owner, 2026-11-20: "a footer"): a sensor board - A5 5A | type | payload | xor8 | 0D 0A - no length
# byte: a message ends at its footer (the payload never holds 0D 0A, as the board escapes it)
SENSOR_STRUCTURE = {
    "kind": "binary", "name": "Sensor board", "header": "A55A", "type": {"offset": 2},
    "checksum": {"scheme": "xor8", "from": 2}, "footer": "0D0A",
    "messages": [
        {"id": 1, "name": "IMU", "fields": [
            _fld("ax", 3, "i16", "le", 0.001, "g"), _fld("ay", 5, "i16", "le", 0.001, "g"), _fld("az", 7, "i16", "le", 0.001, "g"),
            _fld("gx", 9, "i16", "le", 0.01, "deg/s"), _fld("gy", 11, "i16", "le", 0.01, "deg/s"), _fld("gz", 13, "i16", "le", 0.01, "deg/s")]},
        {"id": 2, "name": "BARO", "fields": [_fld("pressure", 3, "u32", "le", 1, "Pa"), _fld("temp", 7, "i16", "le", 0.01, "degC")]},
        {"id": 3, "name": "MAG", "fields": [_fld("mx", 3, "i16", "be", 0.1, "uT"), _fld("my", 5, "i16", "be", 0.1, "uT"), _fld("mz", 7, "i16", "be", 0.1, "uT")]},
    ]}


def sensor_frame(typ: int, payload: bytes) -> bytes:
    x = typ
    for b in payload:
        x ^= b
    return bytes([0xA5, 0x5A, typ]) + payload + bytes([x, 0x0D, 0x0A])


def _no_crlf(pack, *vals):
    """The payload of the values - nudged by one count where it would hold 0D 0A (the board escapes it)."""
    vals = list(vals)
    for _ in range(8):
        b = pack(*vals)
        if b"\r\n" not in b:
            return b
        vals = [v + 1 for v in vals]
    return b


def sensor() -> List[Tuple[float, int]]:
    out: List[Tuple[float, int]] = []
    free = 0.0
    for k in range(2000):                                 # 20 s at 100 Hz
        t = k * 0.01
        fs = [sensor_frame(1, _no_crlf(lambda *v: struct.pack("<6h", *v), round(0.2 * math.sin(t) * 1000), round(0.1 * math.cos(2 * t) * 1000),
                                       round(-1000 + 30 * math.sin(5 * t)), round(20 * math.cos(t) * 100), round(5 * math.sin(3 * t) * 100), round(10 * 100)))]
        if k % 5 == 0:
            fs.append(sensor_frame(2, _no_crlf(lambda p, q: struct.pack("<Ih", p, q), round(101325 - 12 * t * 10), round((24 + t / 10) * 100))))
        if k % 10 == 0:
            fs.append(sensor_frame(3, _no_crlf(lambda *v: struct.pack(">3h", *v), round(250 * math.cos(t / 4)), round(250 * math.sin(t / 4)), -400)))
        for f in fs:
            b = bytearray(f)
            if k == 700 and f[2] == 1:                    # a byte hit: the xor fails
                b[5] ^= 0x04
            at = max(t + 0.0002, free)
            for x in b:
                out.append((round(at, 6), x))
                at += BYTE_S
            free = at + 0.0001
    return out


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
    import json
    with open(os.path.join(folder, "sensor_uart.csv"), "w", newline="\n", encoding="utf-8") as f:
        f.write("time,sensor_byte\n")
        for t, b in sensor():
            f.write("%.6f,%d\n" % (t, b))
    for fn, st in (("link_tx.svmsg.json", TX_STRUCTURE), ("link_rx.svmsg.json", RX_STRUCTURE), ("sensor.svmsg.json", SENSOR_STRUCTURE)):
        with open(os.path.join(folder, fn), "w", newline="\n", encoding="utf-8") as f:
            f.write(json.dumps(st, indent=1) + "\n")
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
