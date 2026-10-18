"""T41: the fleet - an index of many flight logs, to search by finding and follow trends.

A folder of logs (.bin / .tlog / .ulg, sub-folders too) is read once into a local SQLite file
(~/.signalviewer/fleet.sqlite, Python's own sqlite3 - no new dependency): per log its vehicle,
firmware, date, duration, flight modes, and the health check's findings with their numbers
("vibration.max" = 38.2). A later scan reads only new and changed files and drops removed ones.
Each log is opened in a Store of its own, so the files open in the app are not touched.

The flight's date: the GPS time in the log (ArduPilot GPS.GWk / GMS, PX4 time_utc_usec,
MAVLink SYSTEM_TIME), else the file's time (said so: date_source "file")."""
import json
import logging
import os
import re
import sqlite3
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from app.common import APP_DIR

log = logging.getLogger("signalviewer").getChild(__name__)

DB_PATH = os.path.join(APP_DIR, "fleet.sqlite")
FLIGHT_EXTS = (".bin", ".tlog", ".ulg")
GPS_EPOCH = 315964800.0          # 1980-01-06 in Unix time
LEAP = 18.0                      # GPS - UTC seconds (since 2017)

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS folders (folder TEXT PRIMARY KEY, added REAL, last_scan REAL);
CREATE TABLE IF NOT EXISTS logs (path TEXT PRIMARY KEY, folder TEXT, name TEXT, size INTEGER,
  mtime_ns INTEGER, format TEXT, vehicle TEXT, firmware TEXT, date REAL, date_source TEXT,
  duration REAL, signals INTEGER, errors INTEGER, warnings INTEGER, error TEXT, indexed REAL);
CREATE TABLE IF NOT EXISTS findings (path TEXT, code TEXT, level TEXT, t REAL, vals TEXT);
CREATE TABLE IF NOT EXISTS metrics (path TEXT, key TEXT, value REAL);
CREATE TABLE IF NOT EXISTS modes (path TEXT, mode TEXT, seconds REAL);
CREATE INDEX IF NOT EXISTS findings_path ON findings(path);
CREATE INDEX IF NOT EXISTS metrics_key ON metrics(key, value);
CREATE INDEX IF NOT EXISTS modes_path ON modes(path);
"""


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
    return _conn


def reset_connection() -> None:
    """Tests: point at another DB_PATH."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None


# ------------------------------------------------------------------ one log

def _ap_field(sigs, msg: str, fld: str):
    """(name, unit) of an ArduPilot field under any of the names the loader gives it: "GPS.GMS"
    (no FMTU), "GPS[0].GMS [s]" (instanced, with units) - the first instance."""
    pat = re.compile(rf"^{msg}(\[(\d+)\])?\.{fld}(?: \[(.*)\])?$")
    hits = sorted((int(m.group(2) or 0), n, m.group(3) or "") for n in sigs for m in [pat.match(n)] if m)
    return (hits[0][1], hits[0][2]) if hits else (None, "")


def flight_date(run) -> Optional[float]:
    """Unix time of the log's first sample from the GPS time it carries, or None."""
    sigs = run.signals

    def first(name: Optional[str]):
        s = sigs.get(name) if name else None
        if s is None:
            return None
        y = np.asarray(s.data, dtype=np.float64)
        t = np.asarray(s.time if s.time is not None else run.time, dtype=np.float64)
        ok = np.flatnonzero(np.isfinite(y) & (y > 0))
        return (float(t[ok[0]]), ok[0], y, t) if len(ok) else None

    # ArduPilot: GPS week + time of week. GMS is ms in the log; with FMTU (modern firmware) the loader
    # applies its multiplier and it arrives in seconds, "GPS[0].GMS [s]" (F11: only "GPS.GMS" was read)
    wk_name, _ = _ap_field(sigs, "GPS", "GWk")
    ms_name, ms_unit = _ap_field(sigs, "GPS", "GMS")
    wk, ms = first(wk_name), sigs.get(ms_name) if ms_name else None
    if wk and ms is not None:
        t0, i, weeks, _ = wk
        tow = np.asarray(ms.data, dtype=np.float64)[i] * (1.0 if ms_unit == "s" else 1e-3)
        return GPS_EPOCH + weeks[i] * 604800.0 + tow - LEAP - (t0 - float(run.start_time or 0.0))
    for name in ("vehicle_gps_position.time_utc_usec", "sensor_gps.time_utc_usec", "SYSTEM_TIME.time_unix_usec"):
        hit = first(name)
        if hit:
            t0, i, y, _ = hit
            return y[i] / 1e6 - (t0 - float(run.start_time or 0.0))
    return None


def _modes(fl, start: float, end: float) -> Dict[str, float]:
    """Seconds spent in each flight mode (from the log's mode events)."""
    ev = sorted((e for e in (fl.events if fl else []) if e.get("kind") == "mode"), key=lambda e: e["t"])
    out: Dict[str, float] = {}
    for k, e in enumerate(ev):
        stop = ev[k + 1]["t"] if k + 1 < len(ev) else end
        name = str(e.get("text") or "?").strip()[:40]
        out[name] = out.get(name, 0.0) + max(0.0, min(stop, end) - max(e["t"], start))
    return out


def _firmware(fl) -> Optional[str]:
    """The firmware text: FlightLogInfo (.tlog / .ulg) has it as an attribute, the ArduPilot
    DataFlash reader only through log_info()."""
    if fl is None:
        return None
    fw = getattr(fl, "firmware", None)
    if fw is None and hasattr(fl, "log_info"):
        try:
            fw = (fl.log_info() or {}).get("firmware")
        except Exception:                        # optional: the log is indexed without it
            log.debug("firmware not read", exc_info=True)
    return str(fw) if fw else None


def index_file(path: str) -> Dict[str, Any]:
    """Read one log and return its index row (never raises: a log that cannot be read gets an
    'error' and stays listed, so it is not read again until it changes)."""
    from app.store import Store                    # late: app.store imports a lot
    from svcore.health import health
    st = os.stat(path)
    row: Dict[str, Any] = {"path": path, "name": os.path.basename(path), "size": st.st_size,
                           "mtime_ns": st.st_mtime_ns, "format": os.path.splitext(path)[1][1:].lower(),
                           "indexed": time.time(), "findings": [], "metrics": {}, "modes": {}}
    try:
        lr = Store().open_file(path)
        run = lr.run
        fl = getattr(run, "_flightlog", None)
        start, end = float(run.start_time or 0.0), float(run.end_time or 0.0)
        date = flight_date(run)
        row.update(vehicle=getattr(fl, "vehicle", None), firmware=_firmware(fl),
                   duration=round(end - start, 3), signals=len(run.signals),
                   date=date if date is not None else st.st_mtime - (end - start),
                   date_source="gps" if date is not None else "file")
        h = health(run) or {"findings": [], "errors": 0, "warnings": 0}
        row.update(errors=h["errors"], warnings=h["warnings"])
        for f in h["findings"]:
            row["findings"].append({"code": f["code"], "level": f["level"], "t": f.get("t"), "vals": f.get("vals") or {}})
            for k, v in (f.get("vals") or {}).items():
                if isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v):
                    row["metrics"][f"{f['code']}.{k}"] = float(v)
        row["metrics"]["duration"] = row["duration"]
        row["modes"] = _modes(fl, start, end)
    except Exception as e:                          # unreadable: listed with the reason
        row.update(error=str(e) or e.__class__.__name__, date=st.st_mtime, date_source="file")
    return row


def _store(row: Dict[str, Any], folder: str) -> None:
    db = _db()
    p = row["path"]
    db.execute("DELETE FROM logs WHERE path=?", (p,))
    db.execute("DELETE FROM findings WHERE path=?", (p,))
    db.execute("DELETE FROM metrics WHERE path=?", (p,))
    db.execute("DELETE FROM modes WHERE path=?", (p,))
    db.execute("INSERT INTO logs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (p, folder, row["name"], row["size"], row["mtime_ns"], row["format"], row.get("vehicle"),
                row.get("firmware"), row.get("date"), row.get("date_source"), row.get("duration"),
                row.get("signals"), row.get("errors", 0), row.get("warnings", 0), row.get("error"), row["indexed"]))
    db.executemany("INSERT INTO findings VALUES (?,?,?,?,?)",
                   [(p, f["code"], f["level"], f["t"], json.dumps(f["vals"])) for f in row["findings"]])
    db.executemany("INSERT INTO metrics VALUES (?,?,?)", [(p, k, v) for k, v in row["metrics"].items()])
    db.executemany("INSERT INTO modes VALUES (?,?,?)", [(p, m, s) for m, s in row["modes"].items()])


# ------------------------------------------------------------------ folders

def _logs_in(folder: str) -> List[str]:
    out = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        out += [os.path.join(root, f) for f in files if f.lower().endswith(FLIGHT_EXTS)]
    return sorted(out)


def scan(folder: str, progress: Optional[Callable[[float, str], None]] = None,
         cancelled: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
    """Index a folder: new and changed logs are read, unchanged ones skipped, removed ones dropped."""
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        raise ValueError(f"Not a folder: {folder}")
    files = _logs_in(folder)
    with _lock:
        db = _db()
        known = {r["path"]: (r["size"], r["mtime_ns"]) for r in
                 db.execute("SELECT path, size, mtime_ns FROM logs WHERE folder=?", (folder,))}
        db.execute("INSERT OR IGNORE INTO folders VALUES (?,?,NULL)", (folder, time.time()))
        db.commit()
    res: Dict[str, Any] = {"folder": folder, "read": 0, "unchanged": 0, "removed": 0, "failed": 0, "total": len(files)}
    for i, p in enumerate(files):
        if cancelled and cancelled():
            break
        if progress:
            progress(i / max(1, len(files)), os.path.basename(p))
        try:
            st = os.stat(p)
        except OSError:
            continue
        if known.get(p) == (st.st_size, st.st_mtime_ns):
            res["unchanged"] += 1
            continue
        row = index_file(p)
        with _lock:
            _store(row, folder)
            _db().commit()
        res["read"] += 1
        res["failed"] += 1 if row.get("error") else 0
    gone = set(known) - set(files)
    with _lock:
        db = _db()
        for p in gone:
            for table in ("logs", "findings", "metrics", "modes"):
                db.execute(f"DELETE FROM {table} WHERE path=?", (p,))
        db.execute("UPDATE folders SET last_scan=? WHERE folder=?", (time.time(), folder))
        db.commit()
    res["removed"] = len(gone)
    if progress:
        progress(1.0, "")
    return res


def remove_folder(folder: str) -> None:
    folder = os.path.abspath(folder)
    with _lock:
        db = _db()
        paths = [r["path"] for r in db.execute("SELECT path FROM logs WHERE folder=?", (folder,))]
        for p in paths:
            for table in ("findings", "metrics", "modes"):
                db.execute(f"DELETE FROM {table} WHERE path=?", (p,))
        db.execute("DELETE FROM logs WHERE folder=?", (folder,))
        db.execute("DELETE FROM folders WHERE folder=?", (folder,))
        db.commit()


def folders() -> List[Dict[str, Any]]:
    with _lock:
        db = _db()
        return [{**dict(r), "logs": db.execute("SELECT COUNT(*) FROM logs WHERE folder=?", (r["folder"],)).fetchone()[0]}
                for r in db.execute("SELECT * FROM folders ORDER BY folder")]


# ------------------------------------------------------------------ questions

def keys() -> List[Dict[str, Any]]:
    """The numbers there are to search and trend by, with how many logs have each."""
    with _lock:
        return [dict(r) for r in _db().execute(
            "SELECT key, COUNT(*) AS logs, MIN(value) AS min, MAX(value) AS max FROM metrics GROUP BY key ORDER BY key")]


def query(text: str = "", level: str = "", code: str = "", key: str = "", above: Optional[float] = None,
          below: Optional[float] = None, mode: str = "", limit: int = 500) -> List[Dict[str, Any]]:
    """Logs matching every given condition, newest first: name / vehicle / firmware text, a finding
    code at a level (error / warning / any), a number above / below a value, a flight mode."""
    sql = "SELECT * FROM logs WHERE 1=1"
    args: List[Any] = []
    if text:
        sql += " AND (name LIKE ? OR path LIKE ? OR IFNULL(vehicle,'') LIKE ? OR IFNULL(firmware,'') LIKE ?)"
        args += [f"%{text}%"] * 4
    if level in ("error", "warning"):
        lv = ("error",) if level == "error" else ("error", "warning")
        sql += f" AND path IN (SELECT path FROM findings WHERE level IN ({','.join('?' * len(lv))})" + \
               (" AND code=?" if code else "") + ")"
        args += list(lv) + ([code] if code else [])
    elif code:
        sql += " AND path IN (SELECT path FROM findings WHERE code=?)"
        args.append(code)
    if key and (above is not None or below is not None):
        sql += " AND path IN (SELECT path FROM metrics WHERE key=?" + (" AND value>?" if above is not None else "") + \
               (" AND value<?" if below is not None else "") + ")"
        args += [key] + ([above] if above is not None else []) + ([below] if below is not None else [])
    if mode:
        sql += " AND path IN (SELECT path FROM modes WHERE mode=? AND seconds>0)"
        args.append(mode)
    sql += " ORDER BY date DESC LIMIT ?"
    args.append(int(limit))
    with _lock:
        db = _db()
        rows = [dict(r) for r in db.execute(sql, args)]
        for r in rows:
            r["findings"] = [{"code": f["code"], "level": f["level"], "t": f["t"], "vals": json.loads(f["vals"] or "{}")}
                             for f in db.execute("SELECT * FROM findings WHERE path=? ORDER BY level='ok', level='warning'",
                                                 (r["path"],))]
            r["metrics"] = {m["key"]: m["value"] for m in db.execute("SELECT key, value FROM metrics WHERE path=?", (r["path"],))}
            r["modes"] = {m["mode"]: m["seconds"] for m in db.execute("SELECT mode, seconds FROM modes WHERE path=?", (r["path"],))}
    return rows


def trend(key: str) -> List[Dict[str, Any]]:
    """One number over all indexed logs, by flight date (for the trend plot)."""
    with _lock:
        return [dict(r) for r in _db().execute(
            "SELECT l.path, l.name, l.date, l.date_source, m.value FROM metrics m JOIN logs l ON l.path=m.path "
            "WHERE m.key=? ORDER BY l.date", (key,))]
