"""O3: atomic writes - a file is replaced whole or not at all.

Writing in place, a crash, a full disk or a power loss in the middle leaves a half-written session,
template or report where the good one was. Here the content goes to a temporary file in the same
folder (same disk, so the rename is atomic), is flushed to the disk, and only then replaces the
target with os.replace. On any error the temporary file is removed and the old file is untouched.

Used through app.common (atomic_write / atomic_open / atomic_path). The body lives here, with no
imports from the app, because app.prefs (settings, templates) and app.userreaders need it too and
app.common imports them.
"""
import os
import shutil
import threading
import time
from contextlib import contextmanager
from typing import IO, Iterator, Optional, Union


def _tmp_for(path: str) -> str:
    # each process and thread its own name (two apps saving at once must not share one), hidden, and
    # with the target's extension: a writer that picks its format from the name still sees ".pdf"
    d, name = os.path.split(path)
    root, ext = os.path.splitext(name)
    return os.path.join(d, f".{root}.{os.getpid()}-{threading.get_ident()}.tmp{ext}")


def _replace(tmp: str, path: str) -> None:
    # Windows: a reader (an antivirus scan, a viewer) holding the target makes the rename fail for a
    # moment - a few short retries before giving up
    for k in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if k == 4:
                raise
            time.sleep(0.05 * (k + 1))


def _sync(tmp: str) -> None:
    # on the disk before the rename: after a power loss the target is the old file or the new one,
    # never a renamed empty one (best effort - some file systems cannot)
    try:
        fd = os.open(tmp, os.O_RDWR)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_text(path: str, text: str, encoding: str = "utf-8") -> None:
    """Plain write of a whole text file (to the temporary path atomic_path gives)."""
    with open(path, "w", encoding=encoding) as f:
        f.write(text)


@contextmanager
def atomic_path(path: str) -> Iterator[str]:
    """A temporary path to write the whole file to (for writers that take a path: PDF, Word);
    it replaces `path` when the block ends without an error. A symbolic link keeps pointing at its
    file (the file it points to is the one replaced) and an existing file keeps its permissions."""
    path = os.path.realpath(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = _tmp_for(path)
    try:
        yield tmp
        _sync(tmp)
        if os.path.exists(path):
            try:
                shutil.copymode(path, tmp)
            except OSError:
                pass
        _replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@contextmanager
def atomic_open(path: str, mode: str = "w", encoding: Optional[str] = "utf-8",
                newline: Optional[str] = None) -> Iterator[IO]:
    """open() for writing, atomically: `with atomic_open(p) as f: json.dump(x, f)`."""
    if "w" not in mode:
        raise ValueError("atomic_open writes a whole file: mode must be 'w' or 'wb'")
    with atomic_path(path) as tmp:
        binary = "b" in mode
        with open(tmp, mode, encoding=None if binary else encoding, newline=None if binary else newline) as f:
            yield f


def atomic_write(path: str, data: Union[str, bytes], encoding: str = "utf-8",
                 newline: Optional[str] = None) -> None:
    """Write `data` (text or bytes) to `path` atomically."""
    with atomic_open(path, "wb" if isinstance(data, bytes) else "w", encoding, newline) as f:
        f.write(data)
