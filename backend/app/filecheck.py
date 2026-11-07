"""
What a file is and whether it can be opened, before a loader runs - so the user is told in plain
words (unsupported type, empty, binary with a text extension, a known format with the wrong
extension, why a CSV could not be read). A1 (2026-11-07): moved out of app/store.py, which still
exports these names (LoadError is imported from there everywhere).
"""
import logging
import os
from typing import Dict, List, Optional

from svcore.csv_loader import CSVImportSettings, _read_head_lines, detect_delimiter
from app import userreaders

log = logging.getLogger("signalviewer").getChild(__name__)


class LoadError(Exception):
    """A file that cannot be opened. `code` + `params` let the UI show the reason in its own
    language (the English message stays as the fallback)."""
    def __init__(self, message: str, code: Optional[str] = None, **params):
        super().__init__(message)
        self.code = code
        self.params = params


SUPPORTED_EXTS = (".csv", ".txt", ".tsv", ".dat", ".mat", ".bin", ".tlog", ".ulg", ".mcap", ".h5", ".hdf5", ".parquet", ".pq",
                  ".asc", ".log")       # T40b: CAN logs (with a .dbc)
TEXT_EXTS = (".csv", ".txt", ".tsv", ".dat", ".asc", ".log")
_KIND_EXT = {"mat": ".mat", "ulg": ".ulg", "bin": ".bin", "hdf5": ".h5", "mcap": ".mcap", "parquet": ".parquet"}
# the extensions a signature may have: HDF5 is also MATLAB v7.3 (T27)
_KIND_OK = {"mat": (".mat",), "hdf5": (".h5", ".hdf5", ".mat"), "ulg": (".ulg",), "bin": (".bin",), "mcap": (".mcap",), "parquet": (".parquet", ".pq")}


def sniff_kind(head: bytes) -> Optional[str]:
    """What a file is by its first bytes, for the formats that have a clear signature."""
    if head.startswith(b"MATLAB"):
        return "mat"
    if head.startswith(b"\x89HDF\r\n\x1a\n"):         # HDF5: .h5 / .hdf5, or a MATLAB v7.3 .mat
        return "hdf5"
    if head.startswith(b"\x89MCAP"):                  # ROS 2 / Foxglove recording
        return "mcap"
    if head.startswith(b"PAR1"):                       # Parquet (T40)
        return "parquet"
    if head.startswith(b"ULog\x01\x12\x35"):
        return "ulg"
    if head.startswith(b"\xa3\x95\x80"):          # ArduPilot DataFlash: starts with an FMT message
        return "bin"
    return None


def _text_with_zero_block(head: bytes) -> bool:
    """Text with a run of zero bytes in it (a file cut by a power loss, a half-finished copy)
    is still text: without the zeros it is printable lines. Real binary files are not (T33)."""
    rest = head.replace(b"\x00", b"")
    if len(rest) < 16 or b"\n" not in rest:
        return False
    printable = sum(1 for b in rest if b in (9, 10, 13) or 32 <= b < 127 or b >= 0xC2)
    return printable >= 0.95 * len(rest)


def _can_csv(path: str) -> bool:
    """A .csv that is a CAN frame log (time,id,data) - opened with the .dbc, not as a table -
    only when a .dbc sits next to it."""
    d = os.path.dirname(path)
    try:
        if not any(f.lower().endswith(".dbc") for f in os.listdir(d)):
            return False
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            head = [h.strip().lower() for h in f.readline().split(",")]
    except OSError:
        return False
    return len(head) <= 6 and any(h in ("id", "can_id", "arbitration_id") for h in head) and any(h in ("data", "payload") for h in head)


def check_file(path: str, settings: Optional[dict] = None) -> None:
    """Cheap checks BEFORE a loader runs, so the user is told what is wrong in plain words:
    unsupported type, empty file, a binary file with a text extension, or a known format
    with the wrong extension. Raises LoadError."""
    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)
    own = ext not in SUPPORTED_EXTS and bool(userreaders.for_ext(ext))   # T60: a format of the user's
    if ext not in SUPPORTED_EXTS and not own:
        raise LoadError(f"Unsupported file type ({ext or 'no extension'}). Supported: "
                        + ", ".join(e[1:].upper() for e in SUPPORTED_EXTS) + ".",
                        "unsupported", ext=ext or "-", supported=", ".join(e[1:].upper() for e in SUPPORTED_EXTS))
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError as e:
        raise LoadError(f"The file cannot be read: {e.strerror or e}", "unreadable", reason=str(e.strerror or e)) from None
    if size == 0:
        raise LoadError("The file is empty.", "empty")
    if own:                                        # the user's reader decides what its files look like
        return
    kind = sniff_kind(head)
    if kind and ext not in _KIND_OK[kind]:
        raise LoadError(f"{name} looks like a {_KIND_EXT[kind]} file, but its extension is {ext}. "
                        f"Rename it to {_KIND_EXT[kind]} and open it again.", "wrongExt", ext=ext, real=_KIND_EXT[kind])
    if ext in TEXT_EXTS:
        enc = str((settings or {}).get("encoding") or "").lower().replace("-", "").replace("_", "")
        wide = enc.startswith(("utf16", "utf32")) or head.startswith((b"\xff\xfe", b"\xfe\xff"))
        if not wide and b"\x00" in head and not _text_with_zero_block(head):
            raise LoadError("This is a binary file, not text: it cannot be read as CSV.", "binaryText")


def _text_file(path: str) -> bool:
    """A .tlog that is a TEXT table (a telemetry export with columns), not a MAVLink recording:
    read as CSV. A MAVLink .tlog starts with an 8-byte time stamp and binary packets."""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return False
    if not head or b"\x00" in head:
        return False
    try:
        text = head.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = head.decode("cp1252")
        except UnicodeDecodeError:
            return False
    printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in text) / max(1, len(text))
    return printable > 0.97 and "\n" in text and any(d in text for d in (",", ";", "\t", " "))


def _display_names(paths: List[str]) -> Dict[str, str]:
    """File name, plus parent folder when two files share a name."""
    names = {}
    base_count: Dict[str, int] = {}
    for p in paths:
        b = os.path.basename(p)
        base_count[b] = base_count.get(b, 0) + 1
    for p in paths:
        b = os.path.basename(p)
        names[p] = b if base_count[b] == 1 else f"{os.path.basename(os.path.dirname(p))}/{b}"
    return names


def _csv_failure(path: str, s: CSVImportSettings) -> LoadError:
    """Why a text file could not be read, as precisely as a quick look at its first lines allows."""
    generic = LoadError("Could not read this file as CSV. Check the delimiter, header row and time column.", "csvFailed")
    try:
        skip = s.skip_rows or 0
        lines = [ln for ln in _read_head_lines(path, 60, s.encoding, skip=skip) if ln.strip()]
        if len(lines) <= 1:
            return LoadError("The file has a header row but no data rows.", "csvNoRows")
        delim = s.delimiter or detect_delimiter(path, skip_rows=skip)
        numeric = False
        for ln in lines[1:]:
            for cell in ln.rstrip("\r\n").split(delim):
                try:
                    float(cell.strip().replace(",", ".") if delim != "," else cell.strip())
                    numeric = True
                    break
                except ValueError:
                    continue
            if numeric:
                break
        if not numeric:
            return LoadError("No numeric values were found in this file.", "csvNoNumbers")
    except Exception:                   # only a better reason was looked for; the generic one stands
        log.debug("could not find a specific reason for %s", path, exc_info=True)
    return generic
