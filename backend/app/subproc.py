"""One worker process for the user's own code (T31 operations, 26.A2 file readers).

The code runs in a separate process started on first use: a crash in it ends only that process, and a
call that takes longer than its timeout is stopped by killing it; the next call starts a new one. The
process is started with "spawn" (the same on every OS; nothing of the server is copied into it).
"""
import logging
import multiprocessing as mp
import threading
from typing import Any, Callable, Optional

log = logging.getLogger("signalviewer").getChild(__name__)


class WorkerGone(Exception):
    """The call did not finish: `timed_out` (stopped) or the process crashed (`exitcode`)."""

    def __init__(self, timed_out: bool, exitcode: Optional[int]):
        super().__init__("timed out" if timed_out else f"crashed (exit code {exitcode})")
        self.timed_out, self.exitcode = timed_out, exitcode


class Worker:
    def __init__(self, target: Callable[..., None], name: str, args: Callable[[], tuple]):
        """target(conn, *args()) is the process's loop; args() is read at each start (the folder)."""
        self._target, self._name, self._args = target, name, args
        self._lock = threading.Lock()
        self._proc: Optional[Any] = None
        self._conn: Optional[Any] = None

    def stop(self) -> None:
        """The next call starts a new process (which reads the user's files again)."""
        with self._lock:
            self._kill()

    def call(self, msg: tuple, timeout: float) -> Any:
        """Send msg, wait at most timeout seconds for the answer. One call at a time."""
        with self._lock:
            if self._proc is None or not self._proc.is_alive():
                self._kill()
                ctx = mp.get_context("spawn")
                parent, child = ctx.Pipe()
                self._proc = ctx.Process(target=self._target, args=(child, *self._args()), daemon=True, name=self._name)
                self._proc.start()
                child.close()
                self._conn = parent
            assert self._conn is not None
            try:
                self._conn.send(msg)
                if not self._conn.poll(timeout):
                    self._kill()
                    raise WorkerGone(True, None)
                return self._conn.recv()
            except (EOFError, BrokenPipeError, ConnectionResetError):
                if self._proc is not None:
                    self._proc.join(2)                         # gone: wait for its exit code
                code = self._proc.exitcode if self._proc is not None else None
                self._kill()
                raise WorkerGone(False, code) from None

    def _kill(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
                self._proc.join(2)
            except Exception:                # already gone
                log.debug("stopping %s", self._name, exc_info=True)
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
        self._proc, self._conn = None, None
