#!/usr/bin/env python3
"""LINK1: play one of the examples' byte streams over UDP or TCP in real time - a stand-in for a device, to try
Live -> Listen to a link (serial / UDP / TCP) without hardware.

    python tools/send_link_demo.py                         # the sensor board to udp 127.0.0.1:5600
    python tools/send_link_demo.py --what nmea             # the GPS receiver's NMEA
    python tools/send_link_demo.py --what tx --to tcp:0.0.0.0:4001    # serve TCP (the app connects: tcp:127.0.0.1:4001)

In the app: Live -> Listen to a link…, connection udp:0.0.0.0:5600, structure: examples/serial_link/sensor.svmsg.json
(or NMEA 0183 for --what nmea; examples/serial_link/link_tx.svmsg.json for tx). Loops until Ctrl+C.
"""
import argparse
import csv
import os
import socket
import time

EX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples")
SOURCES = {"sensor": ("serial_link/sensor_uart.csv", "sensor_byte"), "tx": ("serial_link/link_tx_rx.csv", "tx_byte"),
           "nmea": ("gps_nmea/receiver_uart.csv", "rx_byte")}


def chunks(path, col, every=0.01):
    """(time, bytes) every `every` seconds of the recording - as a device's packets / a UART's reads."""
    out, cur, t0 = [], bytearray(), None
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if not row[col]:
                continue
            t = float(row["time"])
            t0 = t if t0 is None else t0
            if t - t0 >= every and cur:
                out.append((t0, bytes(cur)))
                cur, t0 = bytearray(), t
            cur.append(int(row[col]))
    if cur:
        out.append((t0, bytes(cur)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--what", choices=sorted(SOURCES), default="sensor")
    ap.add_argument("--to", default="udp:127.0.0.1:5600", help="udp:HOST:PORT (send to) or tcp:HOST:PORT (serve)")
    a = ap.parse_args()
    rel, col = SOURCES[a.what]
    data = chunks(os.path.join(EX, rel), col)
    kind, _, rest = a.to.partition(":")
    host, _, port = rest.rpartition(":")
    if kind == "udp":
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send = lambda b: s.sendto(b, (host, int(port)))           # noqa: E731
    else:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host or "0.0.0.0", int(port)))
        srv.listen(1)
        print("waiting for the app on", a.to)
        c, _ = srv.accept()
        send = c.sendall
    print(f"sending {a.what} ({sum(len(b) for _t, b in data)} bytes a loop) to {a.to} - Ctrl+C to stop")
    while True:
        start = time.time()
        for t, b in data:
            wait = start + (t - data[0][0]) - time.time()
            if wait > 0:
                time.sleep(wait)
            send(b)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
