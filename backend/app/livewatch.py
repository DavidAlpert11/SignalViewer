"""
Live mode: what was added to the open files since they were read, files saved again, new files
beside them (A1, 2026-11-07: moved out of app/store.py). The watcher works on the Store's open
files and reads them again through it; the Store keeps one-line methods for the routes.
"""
import logging
import os
import threading
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from svcore.bin_loader import append_new_messages
from svcore.csv_loader import append_new_rows
from svcore.tlog_loader import append_tlog
from app.prefs import APP_DIR
from svcore.models import Run

if TYPE_CHECKING:
    from app.store import Store

log = logging.getLogger("signalviewer").getChild(__name__)

UPLOAD_DIR = os.path.join(APP_DIR, "uploads")   # files dropped into a browser are copied here
TIME_SLACK = 2.0   # seconds: see new_files()
# files rewritten as a whole (MAT, ULog, MCAP, HDF5, Parquet): read once unchanged for SETTLE_QUIET
# seconds, and at least every SETTLE_MAX seconds while they keep changing
SETTLE_QUIET = 0.4
SETTLE_MAX = 2.0


def _stat(path: str) -> Optional[Tuple[int, int]]:
    try:
        st = os.stat(path)
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


def run_format(run: Run) -> str:
    return (run.import_settings or {}).get("format") or "csv"


class LiveWatcher:
    def __init__(self, store: "Store"):
        self.s = store
        self.lock = threading.Lock()
        self.poll_errors: Dict[str, str] = {}
        self.writing: List[str] = []              # rewritten-as-a-whole files still being written

    def poll_appends(self) -> List[str]:
        """Live mode: read what was added to the open files. Returns the ids that changed.
          * CSV: only the appended rows are parsed;
          * ArduPilot .bin: only the appended messages are decoded;
          * MAT (rewritten as a whole by MATLAB): reloaded once the file has stopped changing for
            one poll, so a half-written file is never read.
        A file that was re-saved from scratch (not appended) is reloaded. Problems (file locked
        while another program saves it, unreadable...) are kept in self.poll_errors for the UI
        instead of failing the whole poll."""
        # one poll at a time: a slow poll (a big file read again) must not be overtaken by the next
        if not self.lock.acquire(blocking=False):
            return []
        try:
            return self._poll()
        finally:
            self.lock.release()

    def _poll(self) -> List[str]:
        changed = []
        self.poll_errors = {}
        self.writing = []
        now = time.time()
        for rid in list(self.s.order):
            lr = self.s.runs.get(rid)
            if lr is None or lr.run.file_path.startswith((UPLOAD_DIR + os.sep, "python:")):
                continue                                     # a copy / data sent from Python (T39): no file to follow
            st = _stat(lr.run.file_path)
            if st is None:
                self.poll_errors[rid] = "The file is no longer there."
                continue
            if st == lr.stat:
                continue                                     # cheap path: untouched since last read
            fmt = run_format(lr.run)
            try:
                if fmt in ("mat", "ulg", "mcap", "hdf5", "parquet"):   # rewritten / closed as a whole
                    # Read it once it has been quiet for a moment - or, if it never stops changing
                    # (saved every second by a running program), every SETTLE_MAX seconds anyway: it
                    # used to wait for two equal polls, so a file saved often was never shown until
                    # the writing stopped. A read of a half-written file fails and is tried again.
                    if lr.pending_stat != st:
                        lr.pending_stat = st
                        lr.pending_since = lr.pending_since or now
                        lr.last_change = now                 # being written: live mode is not idle
                    quiet = now - st[1] / 1e9 >= SETTLE_QUIET
                    overdue = now - lr.pending_since >= SETTLE_MAX
                    if not (quiet or overdue):
                        self.writing.append(rid)
                        continue
                    try:
                        fresh = self.s.reload(rid)
                    except Exception as e:
                        if quiet:                            # settled but unreadable: say so
                            self.poll_errors[rid] = str(e) or e.__class__.__name__
                        else:                                # caught mid-write: next poll
                            self.writing.append(rid)
                        continue
                    fresh.last_change = now
                    fresh.pending_since = 0.0
                    changed.append(rid)
                    continue
                elif fmt == "bin":
                    n = append_new_messages(lr.run)
                elif fmt == "tlog":
                    n = append_tlog(lr.run)
                else:
                    n = append_new_rows(lr.run)
            except Exception:              # any reader problem: reload the whole file instead -
                # correct, but slow for a big file on every poll, so it must be visible
                log.warning("live: reading the appended part of %s failed; reloading the whole file",
                            lr.run.file_path, exc_info=True)
                n = -1
            if n > 0:
                lr.last_change = now
                lr.read_at = now
                if fmt != "csv" or lr.run.byte_offset == st[0]:
                    lr.stat = st                    # (a CSV row still being written is read next time)
                changed.append(rid)
            elif n < 0:
                try:
                    fresh = self.s.reload(rid)
                    fresh.last_change = now
                    changed.append(rid)
                except Exception as e:          # e.g. locked while Excel saves: try again next poll
                    self.poll_errors[rid] = str(e) or e.__class__.__name__
            elif fmt != "csv" or lr.run.byte_offset == st[0]:
                lr.stat = st                    # nothing new and nothing half-written left to read
        return changed

    def activity(self) -> Dict[str, float]:
        """Seconds since each file last received new data in live mode (absent: never)."""
        now = time.time()
        return {rid: round(now - lr.last_change, 2) for rid, lr in self.s.runs.items() if lr.last_change}

    def newer_on_disk(self) -> Dict[str, float]:
        """Q123: the open files saved again since the app read them -> when (epoch s). Only their date
        and size are looked at (a stat each, nothing is read), so the UI can ask every few seconds
        and offer a refresh. Copies and data sent from Python have no file to compare."""
        out: Dict[str, float] = {}
        for rid in list(self.s.order):
            lr = self.s.runs.get(rid)
            if lr is None or lr.stat is None or lr.run.file_path.startswith((UPLOAD_DIR + os.sep, "python:")):
                continue
            st = _stat(lr.run.file_path)
            if st is not None and st != lr.stat:
                out[rid] = st[1] / 1e9
        return out

    def new_files(self, since: float, known: Optional[set] = None) -> List[dict]:
        """Files that appeared (or were first written) after `since` in the folders of the open
        files and look like them (same extension and name pattern: run_012.csv -> run_013.csv;
        an ArduPilot 00000042.BIN -> 00000043.BIN). Used by live mode to offer / open new runs."""
        from app.patterns import name_pattern            # local import: no cycle at start-up
        open_paths = {os.path.normcase(os.path.abspath(lr.run.file_path)) for lr in self.s.runs.values()}
        folders: Dict[str, set] = {}
        for lr in self.s.runs.values():
            p = lr.run.file_path
            if p.startswith(UPLOAD_DIR + os.sep):
                continue
            folders.setdefault(os.path.dirname(os.path.abspath(p)), set()).add(name_pattern(os.path.basename(p)))
        found: list = []
        for folder, pats in folders.items():
            try:
                with os.scandir(folder) as it:
                    for e in it:
                        try:
                            if not e.is_file():
                                continue
                            full = os.path.abspath(e.path)
                            if os.path.normcase(full) in open_paths or (known and full in known):
                                continue
                            if name_pattern(e.name) not in pats:
                                continue
                            st = e.stat()
                            created = max(st.st_mtime, getattr(st, "st_birthtime", 0) or 0)
                            # file-system clocks are coarser than time.time() (a few ms on Linux,
                            # 2 s on FAT): a file written right after `since` can carry a time
                            # slightly before it, so allow some slack
                            if created >= since - TIME_SLACK and st.st_size > 0:
                                found.append({"path": full, "name": e.name, "size": st.st_size, "mtime": st.st_mtime})
                        except OSError:
                            continue
            except OSError:
                continue
        found.sort(key=lambda f: f["mtime"])
        return found
