"""1.21: the hardware an ArduPilot log describes (as ArduPilot's Hardware Report)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from svcore.hardware import decode_devid, hardware  # noqa: E402


def test_device_ids_decoded_as_ardupilot():
    # 24-bit ids of a real Pixhawk 6X log: bus type, bus, address, device type
    assert decode_devid(3408146, "imu") == "ICM42688 (SPI 2, address 0x01)"
    assert decode_devid(658953, "compass") == "IST8310 (I2C 1, address 0x0E)"
    assert decode_devid(97539, "compass").endswith("(DroneCAN node 125, bus 0)")
    assert decode_devid(0, "imu") is None
    assert decode_devid((2 << 0) | (1 << 3) | (4 << 8) | (0xEE << 16), "imu") == "type 0xEE (SPI 1, address 0x04)"


def test_hardware_sections_from_parameters_and_boot_messages():
    p = {"FRAME_CLASS": 1, "FRAME_TYPE": 1, "MOT_PWM_TYPE": 6, "SCHED_LOOP_RATE": 400, "INS_GYR_ID": 3408146,
         "COMPASS_DEV_ID": 658953, "BARO1_DEVID": 7798801, "GPS_TYPE": 2, "BATT_MONITOR": 4, "BATT_CAPACITY": 5000}
    texts = [(1.0, "ArduCopter V4.5.5 (142aece2)"), (1.1, "ChibiOS: 6a85082c"), (1.2, "Pixhawk6X 00430021 3132510E 30373734"),
             (2.0, "EKF3 IMU0 is using GPS")]
    h = hardware(p, texts, "ArduCopter V4.5.5 (142aece2)")
    sec = {s["name"]: dict((k or v, v) for k, v in s["rows"]) for s in h["sections"]}
    assert sec["Frame"]["Frame"] == "Quad X" and sec["Frame"]["ESC protocol"] == "DShot600" and sec["Frame"]["Loop rate"] == "400 Hz"
    assert "Pixhawk6X 00430021 3132510E 30373734" in sec["Board and firmware"]
    assert "EKF3 IMU0 is using GPS" not in sec["Board and firmware"]
    assert sec["Other"]["GPS 1"] == "uBlox" and sec["Other"]["Battery 1"].endswith("5000 mAh")
    assert "IMUs" in sec and "Compasses" in sec and "Barometers" in sec
