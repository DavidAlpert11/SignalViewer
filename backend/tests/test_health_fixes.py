"""Fixes found on real logs (flight.tlog of pymavlink, old Copter 3.2 / 3.3 DataFlash logs):
clipping counters that restart, the motor named by its output channel, old GPS on the boot time,
'APM:Copter' recognised as a copter."""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from svcore.health import check_clipping, check_motors, _Ctx  # noqa: E402


class _Run:
    def __init__(self, sigs):
        self.sigs = sigs
        self.signals = list(sigs)

    def get_signal_data(self, n):
        return self.sigs[n]


def test_clipping_counts_rises_across_a_counter_restart():
    t = np.arange(10.0)
    y = np.array([0, 0, 50, 120, 120, 0, 0, 30, 30, 0], float)     # rises to 120, restart, rises 30, restart
    r = check_clipping(_Ctx(_Run({"VIBRATION.clipping_0": (t, y)}), {}))
    assert r["vals"]["count"] == 150
    assert r["level"] == "error" and r["t"] == 2.0


def test_clipping_still_zero_when_flat():
    t = np.arange(10.0)
    r = check_clipping(_Ctx(_Run({"VIBE[0].Clip": (t, np.full(10, 7.0))}), {}))
    assert r["vals"]["count"] == 0 and r["level"] == "ok"


def test_motor_balance_names_the_output_channel():
    t = np.linspace(0, 60, 600)
    base = 1500 + 20 * np.sin(t)
    sigs = {f"SERVO_OUTPUT_RAW[0].servo{i}_raw [us]": (t, base.copy()) for i in (1, 2, 3, 4)}
    sigs["SERVO_OUTPUT_RAW[0].servo7_raw [us]"] = (t, base + 150)      # the hard-working one is on output 7
    out = check_motors(_Ctx(_Run(sigs), {"MOT_PWM_MIN": 1000, "MOT_PWM_MAX": 2000}), "copter")
    bal = [r for r in out if r["code"] == "motorsBalance"][0]
    assert bal["level"] == "warning" and bal["vals"]["motor"] == 7


def _old_copter_bin(path):
    """A minimal Copter 3.2-style log: GPS with TimeMS (week time) and T (boot ms), MSG 'APM:Copter'."""
    def fmt(typ, name, f, cols):
        size = 3 + struct.calcsize("<" + f.replace("Z", "64s").replace("N", "16s").replace("n", "4s"))
        return struct.pack("<BBBBB4s16s64s", 0xA3, 0x95, 128, typ, size, name.encode(), f.encode(), cols.encode())
    out = [fmt(128, "FMT", "BBnNZ", "Type,Length,Name,Format,Columns"),
           fmt(130, "GPS", "BIHBI", "Status,TimeMS,Week,NSats,T"),
           fmt(131, "MSG", "QZ", "TimeUS,Message")]
    out.append(struct.pack("<BBBQ64s", 0xA3, 0x95, 131, 1_000_000, b"APM:Copter V3.3-dev (ae3192b8)"))
    for k in range(50):                                     # 5 Hz from 10 s after boot
        out.append(struct.pack("<BBBBIHBI", 0xA3, 0x95, 130, 3, 231_058_000 + 200 * k, 1824, 9, 10_000 + 200 * k))
    with open(path, "wb") as f:
        f.write(b"".join(out))


def test_old_gps_on_boot_time_and_apm_copter(tmp_path):
    from svcore import bin_loader
    p = str(tmp_path / "old.bin")
    _old_copter_bin(p)
    from app.store import Store
    run = Store().open_file(p).run
    name = [n for n in run.signals if n.startswith("GPS") and "NSats" in n][0]
    t, _ = run.get_signal_data(name)
    assert abs(t[0] - 10.0) < 1e-6 and abs(t[-1] - 19.8) < 1e-6      # boot time, not 231058 s
    assert bin_loader.vehicle_of([(0.0, "APM:Copter V3.3-dev")]) == "copter"
    assert bin_loader.vehicle_of([(0.0, "APM:Plane V3.5")]) == "plane"
    assert run._flightlog.vehicle == "copter"
