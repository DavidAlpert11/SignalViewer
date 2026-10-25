"""Two objects that move while you watch: a demo of live mode on the map and in 3D.

    python tools/live_demo.py                  # writes into ./live_demo, runs 10 minutes
    python tools/live_demo.py D:\\temp\\demo --minutes 30 --rate 5

It writes two CSV files and keeps appending rows to them, as a logger would:
    live_aircraft.csv   an aircraft flying circles (2 km radius, 300 m, banked)
    live_ship.csv       a ship sailing a slow zig-zag, rolling in the waves
Columns: Time, GPS.Lat, GPS.Lng, GPS.Alt, ATT.Yaw, ATT.Pitch, ATT.Roll, Speed [m/s] - the names the
map recognises, so a new map object fills itself in. Angles in degrees.

In Signal Viewer: open both files, make a plot a Map (or 3D), add an object from each file
(Fill from: the file), press Live. Stop with Ctrl+C; run again to start new files.
"""
import argparse
import math
import os
import time

R_EARTH = 6371000.0
HEADER = "Time,GPS.Lat,GPS.Lng,GPS.Alt,ATT.Yaw,ATT.Pitch,ATT.Roll,Speed [m/s]\n"


def offset(lat0, lon0, north_m, east_m):
    """A point north_m / east_m metres from (lat0, lon0)."""
    lat = lat0 + math.degrees(north_m / R_EARTH)
    lon = lon0 + math.degrees(east_m / (R_EARTH * math.cos(math.radians(lat0))))
    return lat, lon


def aircraft(t, lat0, lon0):
    r, v = 2000.0, 40.0                         # circle radius [m], speed [m/s]
    w = v / r                                   # rad/s
    a = w * t
    lat, lon = offset(lat0, lon0, r * math.sin(a), r * math.cos(a) - r)
    heading = (90.0 - math.degrees(a + math.pi / 2)) % 360.0        # flying anticlockwise, tangent
    alt = 300.0 + 20.0 * math.sin(t / 25.0)
    pitch = math.degrees(math.atan2(20.0 / 25.0 * math.cos(t / 25.0), v))
    roll = -math.degrees(math.atan(v * w / 9.81))                    # a coordinated turn
    return lat, lon, alt, heading, pitch, roll, v


class Ship:
    """Integrates its own track: a zig-zag about north-east at 8 m/s."""
    def __init__(self, lat0, lon0):
        self.n, self.e, self.t = 0.0, 0.0, 0.0
        self.lat0, self.lon0 = offset(lat0, lon0, -3000.0, 1500.0)   # starts away from the aircraft

    def at(self, t):
        v = 8.0
        heading = 45.0 + 25.0 * math.sin(t / 60.0)
        dt = t - self.t
        self.n += v * math.cos(math.radians(heading)) * dt
        self.e += v * math.sin(math.radians(heading)) * dt
        self.t = t
        lat, lon = offset(self.lat0, self.lon0, self.n, self.e)
        roll = 6.0 * math.sin(t * 2 * math.pi / 8.0)                 # waves: 8 s period
        pitch = 2.0 * math.sin(t * 2 * math.pi / 5.5)
        return lat, lon, 0.0, heading, pitch, roll, v


def row(t, vals):
    return f"{t:.2f}," + ",".join(f"{x:.7f}" if i < 2 else f"{x:.3f}" for i, x in enumerate(vals)) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default="live_demo")
    ap.add_argument("--minutes", type=float, default=10.0, help="how long to keep writing")
    ap.add_argument("--rate", type=float, default=5.0, help="rows per second in each file")
    ap.add_argument("--history", type=float, default=20.0, help="seconds already in the files at the start")
    ap.add_argument("--lat", type=float, default=32.08)
    ap.add_argument("--lon", type=float, default=34.70)
    a = ap.parse_args()

    os.makedirs(a.folder, exist_ok=True)
    pa, ps = os.path.join(a.folder, "live_aircraft.csv"), os.path.join(a.folder, "live_ship.csv")
    ship = Ship(a.lat, a.lon)
    dt = 1.0 / a.rate
    with open(pa, "w", newline="") as fa, open(ps, "w", newline="") as fs:
        fa.write(HEADER)
        fs.write(HEADER)
        t = 0.0
        while t < a.history:                                         # some track to start with
            fa.write(row(t, aircraft(t, a.lat, a.lon)))
            fs.write(row(t, ship.at(t)))
            t += dt
        fa.flush()
        fs.flush()
        print(f"Writing {pa}\n        {ps}\n{a.rate:g} rows/s for {a.minutes:g} min - open both in Signal Viewer, "
              f"add a map object from each, press Live. Ctrl+C stops.", flush=True)
        start, t0 = time.time(), t
        try:
            while time.time() - start < a.minutes * 60:
                t = t0 + (time.time() - start)
                # whole rows only, written at once: a reader never sees half a line
                fa.write(row(t, aircraft(t, a.lat, a.lon)))
                fs.write(row(t, ship.at(t)))
                fa.flush()
                fs.flush()
                time.sleep(dt)
        except KeyboardInterrupt:
            pass
    print("Stopped.")


if __name__ == "__main__":
    main()
