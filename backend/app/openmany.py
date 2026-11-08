"""P4: open several files at once, within a memory budget.

Files were opened one after the other; the loaders spend most of their time in numpy / Arrow, which
let other threads run, so several files read side by side on the cores the machine has. What limits
it is memory: each file needs about its size again while it is read (more for a compressed format),
so a file starts only when the files being read leave room for it in the budget (SV_OPEN_BUDGET_MB;
default half the computer's memory, at most 8 GB). A file bigger than the budget is read alone.

The results come back in the order asked, the files are listed in that order, and two files with the
same name in different folders are named by their folder from the start (as they would be one after
the other).
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List, Optional, Tuple

# bytes in memory per byte of file while it is read (a guess on the safe side, by format)
_FACTOR = {".parquet": 5.0, ".pq": 5.0, ".h5": 2.0, ".hdf5": 2.0, ".mat": 2.0, ".mcap": 3.0, ".ulg": 3.0,
           ".tlog": 3.0, ".bin": 1.5}


def _physical_memory() -> Optional[int]:
    try:
        if hasattr(os, "sysconf"):
            return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (ValueError, OSError):
        pass
    try:                                   # Windows
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):  # type: ignore[attr-defined]
            return int(m.ullTotalPhys)
    except Exception:                      # noqa: BLE001 - no figure: the default below
        pass
    return None


def budget_bytes() -> int:
    env = os.environ.get("SV_OPEN_BUDGET_MB")
    if env:
        return int(float(env) * (1 << 20))
    phys = _physical_memory()
    return min(8 << 30, phys // 2) if phys else 2 << 30


def need_bytes(path: str) -> int:
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    return int(size * _FACTOR.get(os.path.splitext(path)[1].lower(), 2.0))


class _Budget:
    """Bytes in use by the files being read; a file waits until it fits (or nothing else is read)."""

    def __init__(self, limit: int):
        self.limit, self.used, self.active = limit, 0, 0
        self._cv = threading.Condition()

    def take(self, n: int, cancelled: Callable[[], bool]) -> None:
        with self._cv:
            while self.active and self.used + n > self.limit:
                if cancelled():
                    return
                self._cv.wait(0.2)
            self.used += n
            self.active += 1

    def give(self, n: int) -> None:
        with self._cv:
            self.used -= n
            self.active -= 1
            self._cv.notify_all()


def open_many(paths: List[str], open_one: Callable[[str, int], object], cancelled: Callable[[], bool] = lambda: False,
              workers: Optional[int] = None) -> List[Tuple[str, object, Optional[BaseException]]]:
    """open_one(path, index) for every path, several at a time; [(path, result, error)] in the order
    given (the overall progress: `Progress`). An error in one file does not stop the others; once
    cancelled, what has not started yet is not started - the caller raises the cancellation."""
    n = len(paths)
    out: List[Tuple[str, object, Optional[BaseException]]] = [(p, None, None) for p in paths]
    if not n:
        return out
    workers = workers or max(1, min(n, os.cpu_count() or 2, 4))
    budget = _Budget(budget_bytes())

    def run(i: int) -> None:
        p = paths[i]
        need = need_bytes(p)
        budget.take(need, cancelled)
        try:
            if cancelled():
                return
            out[i] = (p, open_one(p, i), None)
        except BaseException as e:          # noqa: BLE001 - kept with its file, raised by the caller if it is a cancel
            out[i] = (p, None, e)
        finally:
            budget.give(need)

    if workers == 1 or n == 1:
        for i in range(n):
            run(i)
    else:
        with ThreadPoolExecutor(workers, thread_name_prefix="open") as ex:
            list(ex.map(run, range(n)))
    return out


class Progress:
    """Overall progress of several files read at once: the mean of each file's own fraction."""

    def __init__(self, n: int, report: Callable[[float, str], None]):
        self.fracs = [0.0] * max(1, n)
        self._lock = threading.Lock()
        self._report = report

    def file(self, i: int) -> Callable[..., None]:
        def sub(frac: float, phase: str = "") -> None:
            with self._lock:
                self.fracs[i] = max(self.fracs[i], min(1.0, float(frac)))
                total = sum(self.fracs) / len(self.fracs)
            self._report(total, phase)
        return sub
