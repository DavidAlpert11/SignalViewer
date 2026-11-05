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


def test_motors_from_servo_functions_and_the_motor_number():
    """With SERVOn_FUNCTION in the log only the motor outputs count (a gimbal on output 5 that moves
    is not a motor), and the finding names the motor (Motor 3 on output 6), not the output."""
    t = np.linspace(0, 60, 600)
    base = 1500 + 20 * np.sin(t)
    sigs = {f"RCOU.C{i} [us]": (t, base.copy()) for i in (1, 2, 4)}
    sigs["RCOU.C6 [us]"] = (t, base + 150)                               # motor 3, working harder
    sigs["RCOU.C5 [us]"] = (t, 1100 + 800 * (np.sin(t / 3) > 0))        # a gimbal / gripper: full swings
    params = {"MOT_PWM_MIN": 1000, "MOT_PWM_MAX": 2000, "SERVO1_FUNCTION": 33, "SERVO2_FUNCTION": 34,
              "SERVO6_FUNCTION": 35, "SERVO4_FUNCTION": 36, "SERVO5_FUNCTION": 7}
    out = check_motors(_Ctx(_Run(sigs), params), "copter")
    sat = [r for r in out if r["code"] == "motorsSat"][0]
    bal = [r for r in out if r["code"] == "motorsBalance"][0]
    assert "RCOU.C5 [us]" not in sat["signals"] and sat["level"] == "ok"
    assert bal["level"] == "warning" and bal["vals"]["motor"] == 3


def test_motor_pwm_range_from_the_throttle_channel_when_zero():
    """MOT_PWM_MAX = 0 (the default) means RC3_MAX: the highest output seen is not full output."""
    t = np.linspace(0, 60, 600)
    sigs = {f"RCOU.C{i} [us]": (t, 1500 + 100 * np.sin(t + i)) for i in (1, 2, 3, 4)}
    out = check_motors(_Ctx(_Run(sigs), {"MOT_PWM_MAX": 0, "MOT_PWM_MIN": 0, "RC3_MIN": 1000, "RC3_MAX": 2000}), "copter")
    assert [r for r in out if r["code"] == "motorsSat"][0]["level"] == "ok"


def test_battery_uses_its_own_limits_not_battery_2s():
    from svcore.health import check_battery
    t = np.linspace(0, 600, 601)
    v = np.linspace(16.8, 14.6, 601)
    r = check_battery(_Ctx(_Run({"BAT[0].Volt [V]": (t, v)}), {"BATT_LOW_VOLT": 0, "BATT2_LOW_VOLT": 15.2}))
    assert r["code"] == "battOk"
    r = check_battery(_Ctx(_Run({"BAT[0].Volt [V]": (t, v)}), {"BATT_LOW_VOLT": 15.2}))
    assert r["code"] == "battLow"


def test_err_resolved_is_not_an_error_and_subsystems_are_named():
    from svcore.bin_loader import ERR_SUBSYS, EVENTS
    assert ERR_SUBSYS[5] == "Radio failsafe" and ERR_SUBSYS[12] == "Crash check"
    assert EVENTS[62] == "EKF_YAW_RESET" and EVENTS[54] == "MOTORS_EMERGENCY_STOPPED"


def test_err_events_levels(tmp_path):
    from svcore.bin_loader import load_bin

    def fmt(typ, name, f, cols):
        size = 3 + struct.calcsize("<" + f.replace("Z", "64s").replace("N", "16s").replace("n", "4s").replace("Q", "Q"))
        return struct.pack("<BBBBB4s16s64s", 0xA3, 0x95, 128, typ, size, name.encode(), f.encode(), cols.encode())
    out = [fmt(128, "FMT", "BBnNZ", "Type,Length,Name,Format,Columns"), fmt(140, "ERR", "QBB", "TimeUS,Subsys,ECode"),
           fmt(131, "MSG", "QZ", "TimeUS,Message")]
    out.append(struct.pack("<BBBQ64s", 0xA3, 0x95, 131, 1_000_000, b"ArduCopter V4.5.5 (142aece2)"))
    for tu, sb, ec in ((2_000_000, 5, 1), (5_000_000, 5, 0), (6_000_000, 10, 6)):
        out.append(struct.pack("<BBBQBB", 0xA3, 0x95, 140, tu, sb, ec))
    p = tmp_path / "err.bin"
    p.write_bytes(b"".join(out))
    r = load_bin(str(p), "err.bin")
    r = r[0] if isinstance(r, tuple) else r
    ev = {e["text"]: e["level"] for e in r._flightlog.events if e["kind"] == "error"}
    assert ev == {"Error: Radio failsafe, code 1": "error", "Error: Radio failsafe, code 0 (cleared)": "info",
                  "Error: Flight mode, code 6": "warning"}


def test_battery_low_only_when_held_for_batt_low_timer():
    """A dip under a burst of throttle is not a low battery: ArduPilot waits BATT_LOW_TIMER seconds."""
    from svcore.health import check_battery
    t = np.arange(0, 300, 0.1)
    v = np.full(len(t), 15.8)
    v[(t > 100) & (t < 103)] = 14.9                        # 3 s under 15.2: a dip
    p = {"BATT_LOW_VOLT": 15.2, "BATT_LOW_TIMER": 10}
    r = check_battery(_Ctx(_Run({"BAT[0].Volt [V]": (t, v)}), p))
    assert r["code"] == "battOk" and r["vals"]["min"] == 14.9
    v[(t > 200) & (t < 215)] = 15.0                        # 15 s under: low
    r = check_battery(_Ctx(_Run({"BAT[0].Volt [V]": (t, v)}), p))
    assert r["code"] == "battLow" and r["vals"]["secs"] == 10 and abs(r["t"] - 200.1) < 0.2
    # BATT_FS_VOLTSRC = 1: the resting voltage is what ArduPilot judges
    rest = np.full(len(t), 15.6)
    r = check_battery(_Ctx(_Run({"BAT[0].Volt [V]": (t, v), "BAT[0].VoltR [V]": (t, rest)}), {**p, "BATT_FS_VOLTSRC": 1}))
    assert r["code"] == "battOk"
