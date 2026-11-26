"""ArduPilot's own tables for its DataFlash logs (CC21: domain content, apart from the reader): the flight-mode names
per vehicle, the logged events and error subsystems (AP_Logger.h), and the vehicle a log is from (its start-up texts).
svcore/bin_loader.py names a log's modes, events and errors with them; the flight-log profile reads them too."""
from typing import Optional


# Flight-mode names (ArduPilot's mode numbers per vehicle). The vehicle is read from the log's
# own start-up messages ("ArduCopter V4.5.7", "ArduPlane", "ArduRover", "ArduSub").
MODES = {
    "copter": {0: "STABILIZE", 1: "ACRO", 2: "ALT_HOLD", 3: "AUTO", 4: "GUIDED", 5: "LOITER", 6: "RTL",
               7: "CIRCLE", 9: "LAND", 11: "DRIFT", 13: "SPORT", 14: "FLIP", 15: "AUTOTUNE", 16: "POSHOLD",
               17: "BRAKE", 18: "THROW", 19: "AVOID_ADSB", 20: "GUIDED_NOGPS", 21: "SMART_RTL", 22: "FLOWHOLD",
               23: "FOLLOW", 24: "ZIGZAG", 25: "SYSTEMID", 26: "AUTOROTATE", 27: "AUTO_RTL", 28: "TURTLE"},
    "plane": {0: "MANUAL", 1: "CIRCLE", 2: "STABILIZE", 3: "TRAINING", 4: "ACRO", 5: "FBWA", 6: "FBWB",
              7: "CRUISE", 8: "AUTOTUNE", 10: "AUTO", 11: "RTL", 12: "LOITER", 13: "TAKEOFF", 14: "AVOID_ADSB",
              15: "GUIDED", 17: "QSTABILIZE", 18: "QHOVER", 19: "QLOITER", 20: "QLAND", 21: "QRTL",
              22: "QAUTOTUNE", 23: "QACRO", 24: "THERMAL", 25: "LOITER_ALT_QLAND", 26: "AUTOLAND"},
    "rover": {0: "MANUAL", 1: "ACRO", 3: "STEERING", 4: "HOLD", 5: "LOITER", 6: "FOLLOW", 7: "SIMPLE",
              8: "DOCK", 9: "CIRCLE", 10: "AUTO", 11: "RTL", 12: "SMART_RTL", 15: "GUIDED", 16: "INITIALISING"},
    "sub": {0: "STABILIZE", 1: "ACRO", 2: "ALT_HOLD", 3: "AUTO", 4: "GUIDED", 7: "CIRCLE", 9: "SURFACE",
            16: "POSHOLD", 19: "MANUAL", 20: "MOTOR_DETECT", 21: "SURFTRAK"},
}
# AP_Logger.h: LogEvent
EVENTS = {10: "ARMED", 11: "DISARMED", 15: "AUTO_ARMED", 17: "LAND_COMPLETE_MAYBE", 18: "LAND_COMPLETE",
          19: "LOST_GPS", 21: "FLIP_START", 22: "FLIP_END", 25: "SET_HOME", 28: "NOT_LANDED",
          30: "AUTOTUNE_INITIALISED", 31: "AUTOTUNE_OFF", 32: "AUTOTUNE_RESTART", 33: "AUTOTUNE_SUCCESS",
          34: "AUTOTUNE_FAILED", 35: "AUTOTUNE_REACHED_LIMIT", 36: "AUTOTUNE_PILOT_TESTING", 37: "AUTOTUNE_SAVEDGAINS",
          38: "SAVE_TRIM", 41: "FENCE_ENABLE", 42: "FENCE_DISABLE", 46: "GRIPPER_GRAB", 47: "GRIPPER_RELEASE",
          49: "PARACHUTE_DISABLED", 50: "PARACHUTE_ENABLED", 51: "PARACHUTE_RELEASED", 52: "LANDING_GEAR_DEPLOYED",
          53: "LANDING_GEAR_RETRACTED", 54: "MOTORS_EMERGENCY_STOPPED", 55: "MOTORS_EMERGENCY_STOP_CLEARED",
          56: "MOTORS_INTERLOCK_DISABLED", 57: "MOTORS_INTERLOCK_ENABLED", 58: "ROTOR_RUNUP_COMPLETE",
          59: "ROTOR_SPEED_BELOW_CRITICAL", 60: "EKF_ALT_RESET", 61: "LAND_CANCELLED_BY_PILOT", 62: "EKF_YAW_RESET",
          67: "GPS_PRIMARY_CHANGED", 74: "STANDBY_ENABLE", 75: "STANDBY_DISABLE", 85: "EK3_SOURCES_SET_TO_PRIMARY",
          86: "EK3_SOURCES_SET_TO_SECONDARY", 87: "EK3_SOURCES_SET_TO_TERTIARY", 90: "AIRSPEED_PRIMARY_CHANGED",
          163: "SURFACED", 164: "NOT_SURFACED", 165: "BOTTOMED", 166: "NOT_BOTTOMED", 167: "EKF_MAG_OFFSETS_SAVED"}
# events worth a look in the health check (the rest are information - EKF yaw / altitude resets
# happen in most healthy flights, at the first take-off, and an emergency stop is the pilot's own)
EVENT_LEVEL = {19: "warning", 34: "warning", 59: "warning", 51: "error"}
# AP_Logger.h: LogErrorSubsystem (ECode 0 = resolved)
ERR_SUBSYS = {1: "Main", 2: "Radio", 3: "Compass", 4: "Optical flow", 5: "Radio failsafe", 6: "Battery failsafe",
              7: "GPS failsafe", 8: "GCS failsafe", 9: "Fence failsafe", 10: "Flight mode", 11: "GPS", 12: "Crash check",
              13: "Flip", 14: "Autotune", 15: "Parachute", 16: "EKF check", 17: "EKF / inertial nav failsafe",
              18: "Barometer", 19: "CPU load", 20: "ADS-B failsafe", 21: "Terrain", 22: "Navigation",
              23: "Terrain failsafe", 24: "EKF primary", 25: "Thrust loss", 26: "Sensors failsafe", 27: "Leak failsafe",
              28: "Pilot input", 29: "Vibration failsafe", 30: "Internal error", 31: "Dead-reckoning failsafe"}


def vehicle_of(texts) -> Optional[str]:
    for _t, txt in texts[:200]:
        low = txt.lower()
        for key, veh in (("arducopter", "copter"), ("apm:copter", "copter"), ("apm:plane", "plane"),
                         ("apm:rover", "rover"), ("ardupilot copter", "copter"), ("heli", "copter"),
                         ("arduplane", "plane"), ("ardurover", "rover"), ("rover", "rover"), ("ardusub", "sub")):
            if key in low:
                return veh
    return None
