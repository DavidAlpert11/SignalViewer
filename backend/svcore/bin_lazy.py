"""The values of a big DataFlash log read when a signal is first used (CC21: from svcore/bin_loader.py): where each
field's bytes are in the file (LazyField) and the file itself (_BinSource - still the same bytes?)."""
import os
from typing import Optional

import numpy as np


def _gather(buf: np.ndarray, pos: np.ndarray, off: int, dt: str) -> np.ndarray:
    """One field of the messages starting at `pos`: its bytes only, as `dt`."""
    w = np.dtype(dt).itemsize
    pos = pos.astype(np.int64) + off
    if w <= 4:
        # an unaligned 1-byte-stride view of the file as `dt`: numpy gathers the values directly
        # (about twice as fast as copying byte rows for 2- and 4-byte fields - most of a log)
        view = np.ndarray(shape=(len(buf) - w + 1,), dtype=dt, buffer=buf, offset=0, strides=(1,))
        return view[pos]
    win = np.lib.stride_tricks.as_strided(buf, shape=(len(buf) - w + 1, w), strides=(1, 1), writeable=False)
    return np.ascontiguousarray(win[pos]).view(dt).reshape(-1)


class _BinSource:
    """The file a lazy log reads its values from, and how to tell that it is still the same file
    (the bytes just before the end of what was read - like live mode's rewrite check)."""
    def __init__(self, path: str):
        self.path = path
        self.byte_offset = 0
        self.tail_sig: Optional[bytes] = None

    def open(self) -> np.ndarray:
        try:
            with open(self.path, "rb") as f:
                size = f.seek(0, 2)
                if size < self.byte_offset:
                    raise OSError
                f.seek(max(0, self.byte_offset - 64))
                if f.read(min(64, self.byte_offset)) != (self.tail_sig or b""):
                    raise OSError
        except OSError:
            raise ValueError(f"{os.path.basename(self.path)} changed or is gone since it was opened: "
                             "refresh it (F5) to read it again.") from None
        return np.memmap(self.path, dtype=np.uint8, mode="r")


class LazyField:
    """Where one field's values are in the log: read when the signal is first used (big logs).
    Holds the positions of its messages in time order; the values are exactly what an eager read
    gives (same dtype, same multipliers applied the same way)."""
    __slots__ = ("src", "pos", "off", "dt", "out", "fmult", "mult")

    def __init__(self, src: _BinSource, pos: np.ndarray, off: int, dt: str, out, fmult: float, mult: float):
        self.src, self.pos, self.off, self.dt, self.out, self.fmult, self.mult = src, pos, off, dt, out, fmult, mult

    def __len__(self) -> int:
        return len(self.pos)

    @property
    def nbytes(self) -> int:
        return len(self.pos) * np.dtype(self.out).itemsize

    def read(self) -> np.ndarray:
        buf = self.src.open()
        try:
            y = _gather(buf, self.pos, self.off, self.dt).astype(self.out)
        finally:
            del buf                                   # unmapped: the file is not held open
        if self.fmult != 1.0:
            y *= self.fmult
        if self.mult != 1.0:
            y *= self.mult
        return y

    def concat(self, more: "LazyField") -> "LazyField":
        return LazyField(self.src, np.concatenate([self.pos, more.pos]), self.off, self.dt, self.out, self.fmult, self.mult)
