"""A file or folder moved to the system's recycle bin (the file dialog's Delete) - so a wrong click can be
taken back from the bin, as in Explorer / Finder. No new dependency (send2trash would do the same): Windows'
shell with undo (SHFileOperationW, FOF_ALLOWUNDO), macOS's ~/.Trash, and the freedesktop trash
($XDG_DATA_HOME/Trash, with its .trashinfo) on Linux - the bin the file managers there show."""

import datetime
import os
import shutil
import sys
import urllib.parse


def _unique(folder: str, name: str) -> str:
    """A name not taken in `folder`: name, then "stem 2.ext", "stem 3.ext"..."""
    stem, ext = os.path.splitext(name)
    cand, k = name, 1
    while os.path.lexists(os.path.join(folder, cand)):
        k += 1
        cand = f"{stem} {k}{ext}"
    return cand


def _windows(path: str) -> str:
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 3, 0x4, 0x10, 0x40, 0x400
    # pFrom is a list ending with two NULs: the string's own and this one
    op = SHFILEOPSTRUCTW(None, FO_DELETE, path + "\0", None,
                         FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI, False, None, None)
    code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))  # type: ignore[attr-defined]  # Windows only
    if code or op.fAnyOperationsAborted:
        raise OSError(f"Windows could not move it to the Recycle Bin (code {code}).")
    return "Recycle Bin"


def _mac(path: str) -> str:
    bin_ = os.path.expanduser("~/.Trash")
    os.makedirs(bin_, exist_ok=True)
    shutil.move(path, os.path.join(bin_, _unique(bin_, os.path.basename(path))))
    return bin_


def _freedesktop(path: str) -> str:
    base = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "Trash")
    files, info = os.path.join(base, "files"), os.path.join(base, "info")
    os.makedirs(files, exist_ok=True)
    os.makedirs(info, exist_ok=True)
    name = _unique(files, os.path.basename(path))
    while os.path.lexists(os.path.join(info, name + ".trashinfo")):     # an info left without its file
        name = _unique(files, name + "_")
    # the .trashinfo first (the spec's order): a file manager can put it back where it was
    with open(os.path.join(info, name + ".trashinfo"), "w", encoding="utf-8") as f:
        f.write("[Trash Info]\nPath=" + urllib.parse.quote(path) + "\nDeletionDate="
                + datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S") + "\n")
    try:
        shutil.move(path, os.path.join(files, name))
    except OSError:
        os.remove(os.path.join(info, name + ".trashinfo"))
        raise
    return base


def to_trash(path: str) -> str:
    """Move `path` (a file or a folder) to the recycle bin; returns where it went (a name or a folder)."""
    path = os.path.abspath(path)
    if os.name == "nt":
        return _windows(path)
    if sys.platform == "darwin":
        return _mac(path)
    return _freedesktop(path)
