"""MSG2 (owner, 2026-11-20: "for example raw NMEA messages of a receiver, parsed into recordings at once"): a GPS
receiver's output, a car driving a loop for 3 minutes:

    receiver.nmea       the raw sentences as the receiver wrote them ($GPGGA / $GPRMC 5 Hz, $GPVTG $GPGSA $GPGSV 1 Hz,
                        and $PDEMO 1 Hz - a maker's own sentence, not NMEA's: the app proposes its fields by place).
                        Opened as a file: a recording at once (lat, lon, alt, speed... - a track on the map)
    receiver_uart.csv   the same receiver recorded byte by byte from its serial port (time, rx_byte): *Decode as
                        messages…* recognises NMEA, proposes its structure, and makes the same recording
    faults              the fix lost for 5 s at 60 s (empty position, status V), one sentence with a wrong checksum

Deterministic.    python tools/make_gps_nmea.py [folder]
"""
import math
import os
import sys
from typing import List, Tuple

LAT0, LON0, R = 32.0800, 34.7800, 6378137.0
DURATION = 180.0
BYTE_S = 10 / 115200.0


def _cs(body: str) -> str:
    x = 0
    for c in body:
        x ^= ord(c)
    return "%02X" % x


def _s(body: str, bad: bool = False) -> str:
    cs = _cs(body)
    if bad:
        cs = "%02X" % (int(cs, 16) ^ 0x21)
    return "$%s*%s" % (body, cs)


def _hms(t: float) -> str:
    s = 12 * 3600 + t
    return "%02d%02d%05.2f" % (int(s // 3600), int(s % 3600 // 60), s % 60)


def _deg(v: float, lat: bool) -> Tuple[str, str]:
    a = abs(v)
    d = int(a)
    m = (a - d) * 60
    return (("%02d%07.4f" if lat else "%03d%07.4f") % (d, m)), ("N" if v >= 0 else "S") if lat else ("E" if v >= 0 else "W")


def track(t: float) -> Tuple[float, float, float, float, float]:
    """lat, lon, alt, speed (m/s), course (deg): a rounded loop ~1.2 km around, 15 m/s, slower in the turns."""
    w = 2 * math.pi / 90.0                               # one loop every 90 s
    a, b = 300.0, 150.0
    n, e = a * math.sin(w * t), b * math.sin(2 * w * t)
    vn, ve = a * w * math.cos(w * t), 2 * b * w * math.cos(2 * w * t)
    lat = LAT0 + math.degrees(n / R)
    lon = LON0 + math.degrees(e / (R * math.cos(math.radians(LAT0))))
    alt = 35 + 4 * math.sin(w * t)
    return lat, lon, alt, math.hypot(vn, ve), (math.degrees(math.atan2(ve, vn)) + 360) % 360


def sentences() -> List[Tuple[float, str]]:
    out: List[Tuple[float, str]] = []
    for k in range(int(DURATION * 5)):
        t = k * 0.2
        lat, lon, alt, v, crs = track(t)
        lost = 60.0 <= t < 65.0
        la, ns = _deg(lat, True)
        lo, ew = _deg(lon, False)
        sats = 9 + int(2 * math.sin(t / 20))
        if lost:
            gga = "GPGGA,%s,,,,,0,%02d,,,M,,M,," % (_hms(t), 3)
            rmc = "GPRMC,%s,V,,,,,,,190526,,," % _hms(t)
        else:
            gga = "GPGGA,%s,%s,%s,%s,%s,1,%02d,%.1f,%.1f,M,18.2,M,," % (_hms(t), la, ns, lo, ew, sats, 0.9 + 0.1 * math.sin(t / 7), alt)
            rmc = "GPRMC,%s,A,%s,%s,%s,%s,%.2f,%.1f,190526,,,A" % (_hms(t), la, ns, lo, ew, v / 0.514444, crs)
        out.append((t, _s(gga, bad=(k == 500))))
        out.append((t + 0.03, _s(rmc)))
        if k % 5 == 0:
            out.append((t + 0.06, _s("GPVTG,%.1f,T,,M,%.2f,N,%.2f,K,A" % (crs, v / 0.514444, v * 3.6))))
            out.append((t + 0.09, _s("GPGSA,A,%d,04,07,09,16,21,26,27,30,,,,,%.1f,%.1f,%.1f" % (1 if lost else 3, 1.6, 0.9, 1.3))))
            out.append((t + 0.12, _s("GPGSV,1,1,%02d,04,45,120,42,07,30,200,38,09,60,310,45,16,20,040,35" % sats)))
            out.append((t + 0.15, _s("PDEMO,%.1f,%.2f,%d" % (31 + t / 60, 12.1 - t / 900, k // 5))))
    return out


def main(folder: str):
    os.makedirs(folder, exist_ok=True)
    ss = sentences()
    with open(os.path.join(folder, "receiver.nmea"), "w", newline="\r\n", encoding="ascii") as f:
        for _t, s in ss:
            f.write(s + "\n")
    with open(os.path.join(folder, "receiver_uart.csv"), "w", newline="\n", encoding="ascii") as f:
        f.write("time,rx_byte\n")
        free = 0.0
        for t, s in ss:
            at = max(t, free)
            for c in (s + "\r\n").encode("ascii"):
                f.write("%.6f,%d\n" % (at, c))
                at += BYTE_S
            free = at


if __name__ == "__main__":
    from svcore.example_data import REPO_EXAMPLES
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO_EXAMPLES, "gps_nmea"))
