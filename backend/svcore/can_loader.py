"""T40b: CAN bus logs decoded with .dbc files (svcore/dbc.py) - our own readers, MIT.

Log formats:
  * candump log (`candump -l`):      (1436509052.249713) can0 123#DEADBEEF   (FD: 123##1DEADBEEF)
  * candump screen output:           (1436509052.249713)  can0  123   [4]  DE AD BE EF
  * Vector ASC (classic CAN lines):     0.010000 1  123x  Rx   d 8 01 02 03 04 05 06 07 08
  * CSV with a time, an id and a data column (data as hex bytes): time,id,data / 0.01,0x123,DEADBEEF

The .dbc files used: every .dbc next to the log and in the readers folder (T60); a message in
several of them is taken from the first (the log's folder first). Without any .dbc the reader
says where to put one. Frames whose id is in no .dbc are counted in the load report.
"""
import csv
import io
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from svcore.dbc import DbcError, decode_message, frame_key, parse_dbc
from svcore.models import Run, Signal

CAN_EXTS = (".asc", ".log")

_CANDUMP_LOG = re.compile(r"^\((\d+(?:\.\d+)?)\)\s+(\S+)\s+([0-9A-Fa-f]{1,8})(##?)([0-9A-Fa-f.]*|R\d*)\s*$")
_CANDUMP_SCREEN = re.compile(r"^(?:\((\d+(?:\.\d+)?)\)\s+)?(\S+)\s+([0-9A-Fa-f]{1,8})\s+\[(\d+)\]\s*((?:[0-9A-Fa-f]{2}\s*)*)")
_ASC = re.compile(r"^\s*(\d+(?:\.\d+)?)\s+(\d+)\s+([0-9A-Fa-f]+)(x?)\s+(Rx|Tx)\s+d\s+(\d+)\s*((?:[0-9A-Fa-f]{2}\s*)*)", re.I)


class CanError(ValueError):
    pass


def _frames_text(text: str) -> Tuple[List[Tuple[float, int, bool, bytes, str]], str]:
    """(time, id, extended, data, channel) for every frame line, and the format found."""
    out: List[Tuple[float, int, bool, bytes, str]] = []
    fmt = ""
    lines = text.splitlines()
    head = "\n".join(lines[:5]).lower()
    if "," in (lines[0] if lines else "") and "id" in head.split("\n")[0]:
        return _frames_csv(text), "csv"
    for line in lines:
        m = _CANDUMP_LOG.match(line)
        if m:
            fmt = fmt or "candump"
            ident, payload = m.group(3), m.group(5)
            if payload.startswith("R"):                       # remote request: no data
                continue
            if m.group(4) == "##":                            # CAN FD: one flags nibble, then the data
                payload = payload[1:]
            payload = payload.replace(".", "")
            out.append((float(m.group(1)), int(ident, 16), len(ident) > 3, bytes.fromhex(payload), m.group(2)))
            continue
        m = _ASC.match(line)
        if m:
            fmt = fmt or "asc"
            data = bytes.fromhex(m.group(7).replace(" ", ""))[:int(m.group(6))]
            out.append((float(m.group(1)), int(m.group(3), 16), bool(m.group(4)), data, m.group(2)))
            continue
        m = _CANDUMP_SCREEN.match(line)
        if m and m.group(1):                                  # without a time stamp there is no time axis
            fmt = fmt or "candump"
            ident = m.group(3)
            out.append((float(m.group(1)), int(ident, 16), len(ident) > 3,
                        bytes.fromhex(m.group(5).replace(" ", ""))[:int(m.group(4))], m.group(2)))
    return out, fmt


def _frames_csv(text: str) -> List[Tuple[float, int, bool, bytes, str]]:
    rows = list(csv.reader(io.StringIO(text)))
    head = [h.strip().lower() for h in rows[0]]
    def col(*names):
        return next((i for i, h in enumerate(head) for n in names if h == n or h.startswith(n)), None)
    it, ii, idd = col("time", "timestamp", "t"), col("id", "can_id", "arbitration"), col("data", "payload", "bytes")
    ich = col("channel", "bus")
    if it is None or ii is None or idd is None:
        raise CanError("A CAN .csv needs a time, an id and a data column (e.g. time,id,data).")
    out = []
    for r in rows[1:]:
        try:
            ident = r[ii].strip()
            can_id = int(ident, 0) if ident.lower().startswith("0x") else int(ident, 16)
            data = bytes.fromhex(r[idd].replace(" ", "").replace("0x", ""))
            out.append((float(r[it]), can_id, can_id > 0x7FF or len(ident.lower().replace("0x", "")) > 3, data,
                        r[ich].strip() if ich is not None else ""))
        except (ValueError, IndexError):
            continue
    return out


def looks_like_can(path: str) -> bool:
    """Cheap test on the first lines (a .log is not always a CAN log)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            head = [f.readline() for _ in range(40)]
    except OSError:
        return False
    return any(_CANDUMP_LOG.match(x) or _ASC.match(x) or (_CANDUMP_SCREEN.match(x) and x.startswith("(")) for x in head)


def find_dbcs(path: str, extra_folders: List[str]) -> List[str]:
    out = []
    for d in [os.path.dirname(os.path.abspath(path))] + extra_folders:
        try:
            out += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.lower().endswith(".dbc")]
        except OSError:
            pass
    return out


def load_can(path: str, display_name: str, dbc_folders: Optional[List[str]] = None) -> Tuple[Optional[Run], Dict[str, Any]]:
    dbcs = find_dbcs(path, dbc_folders or [])
    if not dbcs:
        raise CanError(f"No CAN database (.dbc) for {os.path.basename(path)}: put the .dbc next to the log, "
                       "or in your readers folder (signalviewer-cli readers shows where).")
    db: Dict[int, Dict[str, Any]] = {}
    used = []
    for p in dbcs:
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                msgs = parse_dbc(f.read(), os.path.basename(p))
        except (OSError, DbcError) as e:
            raise CanError(str(e)) from None
        for k, m in msgs.items():
            if not m["skip"] and k not in db:
                db[k] = m
        used.append(os.path.basename(p))
    with open(path, encoding="utf-8", errors="replace") as f:
        frames, fmt = _frames_text(f.read())
    if not frames:
        raise CanError(f"{os.path.basename(path)} has no CAN frames this reader knows (candump, Vector ASC, CSV).")
    t_all = np.array([x[0] for x in frames], dtype=np.float64)
    keys = np.array([frame_key(x[1], x[2]) for x in frames], dtype=np.int64)
    channels = sorted({x[4] for x in frames if x[4]})
    t0 = float(t_all.min())                                   # candump times are Unix seconds: start at 0
    sigs: Dict[str, Signal] = {}
    unknown: Dict[str, int] = {}
    counts: Dict[str, int] = {}
    for k in np.unique(keys):
        idx = np.flatnonzero(keys == k)
        msg = db.get(int(k))
        if msg is None:
            unknown[hex(int(k) & 0x1FFFFFFF)] = int(len(idx))
            continue
        width = max(max(len(frames[i][3]) for i in idx), 8)
        data = np.zeros((len(idx), width), dtype=np.uint8)
        lens = np.zeros(len(idx), dtype=np.int64)
        for r, i in enumerate(idx):
            d = frames[i][3]
            data[r, :len(d)] = np.frombuffer(d, dtype=np.uint8)
            lens[r] = len(d)
        t = t_all[idx] - t0
        order = np.argsort(t, kind="stable")
        t, data, lens = t[order], data[order], lens[order]
        counts[msg["name"]] = int(len(idx))
        for name, tt, y, labels in decode_message(msg, t, data, lens):
            sigs[name] = Signal(name=name, data=y, time=tt, labels=dict(labels) if labels else None)
    report: Dict[str, Any] = {"format": fmt, "dbc": used, "frames": len(frames), "messages": counts}
    if channels:
        report["channels"] = channels
    if unknown:
        report["unknownIds"] = dict(sorted(unknown.items(), key=lambda kv: -kv[1])[:20])
    if t0 > 1e8:
        report["startUnixTime"] = t0
    if not sigs:
        return None, report
    longest = max((s.time for s in sigs.values() if s.time is not None), key=len)
    run = Run(file_path=path, csv_display_name=display_name, time=longest)
    run.signals = sigs
    run.compute_metadata()
    run.start_time = min(float(s.time[0]) for s in sigs.values() if s.time is not None and len(s.time))
    run.end_time = max(float(s.time[-1]) for s in sigs.values() if s.time is not None and len(s.time))
    run.import_settings = {"format": "can"}
    return run, report
