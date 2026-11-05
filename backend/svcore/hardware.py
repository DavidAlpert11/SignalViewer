"""
What an ArduPilot log says about the vehicle's hardware - as ArduPilot's Hardware Report web tool:
the board and firmware (its boot messages), the frame, each IMU / compass / barometer (decoded from
its device id: bus, address, chip), GPS, battery monitor and ESC protocol.

    hardware(params, texts, firmware) -> {"sections": [{"name", "rows": [[label, value], ...]}]}

The chip names come from ArduPilot's own enums (ap_names.json, made from AP_InertialSensor_Backend.h,
AP_Compass_Backend.h, AP_Baro_Backend.h and the parameters' value lists).
"""
import json
import os
import re
from typing import Dict, List, Optional, Tuple

_NAMES: Optional[Dict[str, Dict[str, str]]] = None
BUS = {0: "unknown", 1: "I2C", 2: "SPI", 3: "DroneCAN", 4: "SITL", 5: "MSP", 6: "serial", 7: "WSPI"}


def names() -> Dict[str, Dict[str, str]]:
    global _NAMES
    if _NAMES is None:
        with open(os.path.join(os.path.dirname(__file__), "ap_names.json"), encoding="utf-8") as f:
            _NAMES = json.load(f)
    return _NAMES


def decode_devid(devid: float, kind: str) -> Optional[str]:
    """ArduPilot's 24-bit device id: bus type (3 bits), bus (5), address (8), device type (8)."""
    d = int(devid)
    if d <= 0:
        return None
    bus_type, bus, addr, dev = d & 0x7, (d >> 3) & 0x1F, (d >> 8) & 0xFF, (d >> 16) & 0xFF
    chip = names().get(kind, {}).get(str(dev))
    chip = re.sub(r"^(ACC_|GYR_|INS_|BARO_)", "", chip) if chip else f"type 0x{dev:02X}"
    where = BUS.get(bus_type, f"bus type {bus_type}")
    if bus_type == 3:
        return f"{chip} ({where} node {addr}, bus {bus})"
    return f"{chip} ({where} {bus}, address 0x{addr:02X})"


def _named(table: str, v: Optional[float]) -> str:
    if v is None:
        return ""
    return names().get(table, {}).get(str(int(v)), str(int(v)))


_BANNERS = re.compile(r"^(ChibiOS|NuttX|PX4|Linux)\b|^[A-Za-z][\w-]*\s+[0-9A-F]{8}\s+[0-9A-F]{8}\s+[0-9A-F]{8}|^Frame:|^RCOut:|^IMU\d:|^GPS \d:|^u-blox|^Param space|^RC Protocol:")


def hardware(params: Dict[str, float], texts: List[Tuple[float, str]], firmware: Optional[str]) -> Dict:
    p = params
    sections: List[Dict] = []
    boot: List[List[str]] = []
    if firmware:
        boot.append(["Firmware", firmware])
    seen = set()
    for _t, txt in texts[:300]:
        if _BANNERS.search(txt) and txt not in seen:
            seen.add(txt)
            boot.append(["", txt])
    if boot:
        sections.append({"name": "Board and firmware", "rows": boot})

    frame: List[List[str]] = []
    if p.get("FRAME_CLASS") is not None:
        frame.append(["Frame", f'{_named("frame_class", p["FRAME_CLASS"])} {_named("frame_type", p.get("FRAME_TYPE", 0)) or ""}'.strip()])
    if p.get("Q_FRAME_CLASS") is not None and p.get("Q_ENABLE"):
        frame.append(["VTOL frame", f'{_named("frame_class", p["Q_FRAME_CLASS"])} {_named("frame_type", p.get("Q_FRAME_TYPE", 0)) or ""}'.strip()])
    for key in ("MOT_PWM_TYPE", "Q_M_PWM_TYPE"):
        if p.get(key) is not None:
            frame.append(["ESC protocol", _named("pwm_type", p[key])])
            break
    if p.get("SCHED_LOOP_RATE"):
        frame.append(["Loop rate", f'{int(p["SCHED_LOOP_RATE"])} Hz'])
    if frame:
        sections.append({"name": "Frame", "rows": frame})

    def sensors(title: str, kind: str, keys: List[Tuple[str, str]]):
        rows: List[List[str]] = []
        for label, key in keys:
            v = p.get(key)
            if v:
                s = decode_devid(v, kind)
                if s:
                    rows.append([label, s])
        if rows:
            sections.append({"name": title, "rows": rows})

    sensors("IMUs", "imu", [(f"Accel {i + 1}", k) for i, k in enumerate(("INS_ACC_ID", "INS_ACC2_ID", "INS_ACC3_ID"))]
            + [(f"Gyro {i + 1}", k) for i, k in enumerate(("INS_GYR_ID", "INS_GYR2_ID", "INS_GYR3_ID"))])
    sensors("Compasses", "compass", [(f"Compass {i + 1}", k) for i, k in
                                      enumerate(("COMPASS_DEV_ID", "COMPASS_DEV_ID2", "COMPASS_DEV_ID3"))])
    sensors("Barometers", "baro", [(f"Baro {i + 1}", f"BARO{i + 1}_DEVID") for i in range(3)])

    other: List[List[str]] = []
    for i, key in enumerate(("GPS_TYPE", "GPS_TYPE2", "GPS1_TYPE", "GPS2_TYPE")):
        if p.get(key):
            other.append([f"GPS {1 + (i % 2) if i < 2 else i - 1}", _named("gps_type", p[key])])
    for i, key in enumerate(("BATT_MONITOR", "BATT2_MONITOR")):
        if p.get(key):
            cap = p.get("BATT_CAPACITY" if i == 0 else "BATT2_CAPACITY")
            other.append([f"Battery {i + 1}", f'{_named("batt_monitor", p[key])}' + (f", {int(cap)} mAh" if cap else "")])
    if p.get("INS_HNTCH_ENABLE"):
        other.append(["Harmonic notch", f'mode {int(p.get("INS_HNTCH_MODE", 0))}, {p.get("INS_HNTCH_FREQ", 0):g} Hz'])
    if p.get("INS_LOG_BAT_MASK"):
        other.append(["IMU batch logging", f'mask {int(p["INS_LOG_BAT_MASK"])}, options {int(p.get("INS_LOG_BAT_OPT", 0))}'])
    if other:
        sections.append({"name": "Other", "rows": other})
    return {"sections": sections}
