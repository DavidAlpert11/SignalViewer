#!/usr/bin/env python3
"""P3 (2026-11-12): ArduPilot logs where ONE message type is written with a length different from
its FMT - the firmware fault the owner met - made from examples/copter_flight.bin.

    python tools/make_bad_bin_fixture.py            # writes tests/data/bad_len_*.bin

(a) bad_len_longer.bin   every CTUN message has 4 extra bytes after it (written 47, declared 43)
(b) bad_len_shorter.bin  every CTUN message is cut by 3 bytes (written 40, declared 43)
(c) bad_len_random.bin   every CTUN payload replaced by random bytes of a random length
(d) bad_names.bin        CTUN's FMT lists 3 more column names than its format has fields - the owner's
                         firmware fault (2026-11-12): three labels added to a Write() call, its values
                         not; the messages themselves are written as the format says

Only the start of the source is used (about 500 KB, cut at a message boundary) so the files stay small.
The source's messages are walked by their FMT lengths (the example is a clean log)."""
import os
import random
import struct
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "examples", "copter_flight.bin")
OUT = os.path.join(ROOT, "tests", "data")
TYPE_NAME = "CTUN"
LIMIT = 500_000


def messages(data: bytes):
    """(type, bytes) of each message of a clean log, in order."""
    lengths = {128: 89}
    i, n = 0, len(data)
    while i + 3 <= n:
        if data[i] != 0xA3 or data[i + 1] != 0x95:
            raise ValueError(f"not a clean log at byte {i}")
        typ = data[i + 2]
        if typ == 128:
            t, ln = struct.unpack_from("<BB", data, i + 3)
            lengths[t] = ln
        ln = lengths[typ]
        if i + ln > n:
            break
        yield typ, data[i:i + ln]
        i += ln


def type_of(data: bytes, name: str) -> int:
    for typ, m in messages(data):
        if typ == 128 and m[5:9].rstrip(b"\0").decode() == name:
            return m[3]
    raise ValueError(f"{name} not in the log")


def count(data: bytes) -> int:
    """How many messages make the first LIMIT bytes (every file is cut after the same messages)."""
    size = 0
    for k, (_typ, m) in enumerate(messages(data)):
        if size >= LIMIT:
            return k
        size += len(m)
    return k + 1


def make(data: bytes, kind: str, seed: int = 7) -> bytes:
    bad = type_of(data, TYPE_NAME)
    stop = count(data)
    rnd = random.Random(seed)
    out = bytearray()
    for k, (typ, m) in enumerate(messages(data)):
        if k >= stop:
            break
        if kind == "names" and typ == 128 and m[3] == bad:
            cols = m[25:89].rstrip(b"\0") + b",Ex1,Ex2,Ex3"
            out += m[:25] + cols[:64].ljust(64, b"\0")           # the FMT's 64-byte column list
        elif typ != bad or kind in ("clean", "names"):
            out += m
        elif kind == "longer":
            out += m + bytes([0x11, 0x22, 0x33, 0x44])
        elif kind == "shorter":
            out += m[:-3]
        else:                                     # random: a header, then 0..60 random bytes
            body = bytes(rnd.randrange(256) for _ in range(rnd.randint(0, 60)))
            out += m[:3] + body.replace(b"\xa3\x95", b"\xa3\x94")   # no fake headers inside
    return bytes(out)


def main() -> int:
    with open(SRC, "rb") as f:
        data = f.read()
    os.makedirs(OUT, exist_ok=True)
    for kind in ("longer", "shorter", "random", "names"):
        path = os.path.join(OUT, "bad_names.bin" if kind == "names" else f"bad_len_{kind}.bin")
        with open(path, "wb") as f:
            f.write(make(data, kind))
        print(path, os.path.getsize(path))
    # the clean start of the same log, cut at the same place, to compare the signals with
    clean = make(data, "clean")
    with open(os.path.join(OUT, "bad_len_clean.bin"), "wb") as f:
        f.write(clean)
    return 0


if __name__ == "__main__":
    sys.exit(main())
