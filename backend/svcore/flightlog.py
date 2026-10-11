"""
What the Log panel shows for any flight log - ArduPilot .bin, MAVLink .tlog, PX4 .ulg: parameters
(value at start, every change, default when known) and events (messages, mode changes, events,
errors) in time order. Each reader fills one of these and puts it on the Run as `_flightlog`.
"""
import re
from typing import Dict, List, Optional, Tuple

import numpy as np

_ERR_WORDS = re.compile(r"crash|emergency|critical|panic|fail|error|lost|terminat|thrust loss|ekf.*(variance|lane switch)", re.I)
_WARN_WORDS = re.compile(r"prearm|arm:|warn|unhealthy|glitch|timeout|bad |low|check|disabled|not ready|vibration|clipping", re.I)
_FIRMWARE = re.compile(r"(Ardu\w+|Rover|Blimp|AntennaTracker|PX4)\b.*?V?\d+\.\d+", re.I)


def message_level(text: str) -> str:
    """'error' / 'warning' / 'info' from the words of a log text (when the log has no severity)."""
    if _ERR_WORDS.search(text):
        return "error"
    if _WARN_WORDS.search(text):
        return "warning"
    return "info"


def f32(v) -> float:
    """A float32 value as written (0.15, not 0.15000000596)."""
    return float(f"{float(v):.7g}")


class FlightLogInfo:
    def __init__(self):
        self.vehicle: Optional[str] = None
        self.firmware: Optional[str] = None
        self.params: Dict[str, float] = {}
        self.param_first: Dict[str, Tuple[float, float, Optional[float]]] = {}
        self.param_changes: Dict[str, List[Tuple[float, float]]] = {}
        self.events: List[dict] = []
        self.texts: List[Tuple[float, str]] = []

    def set_param(self, t: float, name: str, value: float, default: Optional[float] = None):
        value = f32(value)
        if name not in self.param_first:
            self.param_first[name] = (t, value, None if default is None else f32(default))
        elif value != self.params.get(name):
            self.param_changes.setdefault(name, []).append((t, value))
        self.params[name] = value

    def add_event(self, t: float, kind: str, text: str, level: Optional[str] = None):
        self.events.append({"t": float(t), "kind": kind, "text": text, "level": level or message_level(text)})
        if kind == "msg":
            self.texts.append((float(t), text))
            if self.firmware is None and _FIRMWARE.match(text):
                self.firmware = text

    def sort_events(self):
        self.events.sort(key=lambda e: e["t"])

    def log_info(self) -> dict:
        params = []
        for nm in sorted(self.param_first):
            _t0, v0, d = self.param_first[nm]
            params.append({"name": nm, "value": self.params.get(nm, v0), "first": v0, "default": d,
                           "changes": [[t, v] for t, v in self.param_changes.get(nm, [])]})
        return {"vehicle": self.vehicle, "firmware": self.firmware, "params": params, "events": self.events,
                "hasDefaults": any(p["default"] is not None for p in params)}


def text_codes(values, labels: Optional[Dict[int, str]] = None):
    """Text values -> (float codes, {code: text}) - same as CSV text columns."""
    from svcore.csv_loader import encode_text
    return encode_text(values, labels)


def finite_float(a) -> np.ndarray:
    return np.asarray(a, dtype=np.float64)
