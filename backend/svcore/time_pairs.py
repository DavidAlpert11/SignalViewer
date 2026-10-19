"""
Columns that carry their own time (owner, 2026-10-19: telemetry exports where "the time column and
the value column can be told apart by their names"). A value column gets its own time column when:

  1. a column is named like the value plus a time word:  Speed_time, Speed.time, Speed time,
     time_Speed, t_Speed, Speed_t, Speed_timestamp, SpeedTime ...  (units in [] / () ignored);
  2. a group (message) has a time column of its own:      ATTITUDE.time_boot_ms / ATTITUDE.timestamp
     is the time of every ATTITUDE.* column;
  3. time and value columns alternate:                    time, Speed, time, RPM, time, Alt
     (duplicate headers: time, time_1, time_2 ...) - each value takes the time column before it.

A rule that matches a column wins over the later ones (its own pair, then its group, then the
alternation). Columns no rule claims keep the file's main time column, as before.
"""
import re
from typing import Dict, List, Optional

import numpy as np

TIME_WORDS = ("time", "t", "timestamp", "ts", "tstamp")
# a group's own time (MAVLink / ArduPilot style field names included)
GROUP_TIME_WORDS = TIME_WORDS + ("time_boot_ms", "time_usec", "time_us", "timeus", "time_ms", "time_unix_usec", "time_s", "sec")
_MAV_TIME_WORDS = ("time_boot_ms", "time_usec", "time_unix_usec", "timeus")
_UNIT = re.compile(r"\s*[\[(][^\])]*[\])]\s*$")
_NUMBERED_TIME = re.compile(r"^(time|t|timestamp|ts)([ _.]?\d+)?$")
_SEPS = ("_", ".", " ", "-")


def _norm(name: str) -> str:
    return _UNIT.sub("", str(name)).strip().lower()


def is_time_name(name: str) -> bool:
    """A bare time column: time, t, timestamp... with an optional number (time_2, time.1)."""
    return bool(_NUMBERED_TIME.match(_norm(name)))


def _own_time_names(value: str) -> List[str]:
    v = _norm(value)
    out = []
    for w in TIME_WORDS:
        for sep in _SEPS:
            out += [f"{v}{sep}{w}", f"{w}{sep}{v}"]
        if len(w) >= 4:                                   # SpeedTime / TimeSpeed (not "tSpeed")
            out += [f"{v}{w}", f"{w}{v}"]
    return out


def find_time_pairs(names: List[str], main_time: Optional[str] = None) -> Dict[str, str]:
    """{value column: its time column} for the columns that have a time column of their own.
    `main_time` is the file's main time column (it can be one of the pairs' times too)."""
    by_norm: Dict[str, str] = {}
    for n in names:
        by_norm.setdefault(_norm(n), n)
    time_cols = set()
    pairs: Dict[str, str] = {}
    # 1. own pairs by name
    for n in names:
        if is_time_name(n):
            continue
        for cand in _own_time_names(n):
            hit = by_norm.get(cand)
            if hit and hit != n:
                pairs[n] = hit
                time_cols.add(hit)
                break
    # 2. a group's time column: "<group><sep><time word>"
    # ("." - a message and its fields - takes every time word; "_" only the unmistakable MAVLink
    # ones, so a data column such as gps_time does not become the time of gps_lat)
    groups: Dict[str, str] = {}
    for n in names:
        low = _norm(n)
        for sep, words in ((".", GROUP_TIME_WORDS), ("_", _MAV_TIME_WORDS)):
            for w in words:
                if low.endswith(sep + w) and len(low) > len(sep + w):
                    groups.setdefault(low[:-len(w)], n)
                    break
    if groups:
        for n in names:
            if n in pairs or n in time_cols or n in groups.values() or is_time_name(n):
                continue
            low = _norm(n)
            for prefix, tcol in groups.items():
                if low.startswith(prefix) and len(low) > len(prefix):
                    pairs[n] = tcol
                    time_cols.add(tcol)
                    break
    # 3. alternating time / value columns (two bare time columns or more, the first column one)
    bare = [i for i, n in enumerate(names) if is_time_name(n) and n not in time_cols]
    if len(bare) >= 2 and bare[0] == 0:
        current = None
        for n in names:
            if is_time_name(n) and n not in time_cols:
                current = n
                continue
            if current and n not in pairs and n not in time_cols and n not in groups.values():
                pairs[n] = current
    # the main time needs no own time; a pair onto itself is not a pair
    return {v: t for v, t in pairs.items() if v != t and v != main_time}


def clean_pair(t: np.ndarray, y: np.ndarray):
    """A value with its own time: rows without a time dropped (shorter columns are padded with
    empty cells), sorted by time. Returns (t, y)."""
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y)
    n = min(len(t), len(y))
    t, y = t[:n], y[:n]
    ok = np.isfinite(t)
    if not ok.all():
        t, y = t[ok], y[ok]
    if len(t) > 1 and np.any(np.diff(t) < 0):
        order = np.argsort(t, kind="stable")
        t, y = t[order], y[order]
    return t, y
