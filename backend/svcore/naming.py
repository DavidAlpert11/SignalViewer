"""
Signal Viewer - Canonical Naming
=====================================
Single source of truth for all display names.

Format rules:
- Signal label: "signal_name — csv_display_name"
- Derived: "signal_name — Derived"
- CSV with duplicate filename: "parent/filename.csv"
"""

import difflib
import os
import re
from typing import Dict, Iterable, List


def get_csv_display_name(filepath: str, all_paths: List[str]) -> str:
    """
    Get display name for a CSV file.
    
    CANONICAL RULES (task_add.md fix):
    - If filename is unique: "filename.csv"
    - If filename is duplicate: "parent_folder/filename.csv"
    - NEVER show internal paths like "Downloads/signals/"
    
    Args:
        filepath: Full path to CSV file
        all_paths: List of all loaded CSV paths
        
    Returns:
        Display name string (just filename or parent/filename)
    """
    basename = os.path.basename(filepath)
    basenames = [os.path.basename(p) for p in all_paths]
    
    # Only add parent folder if the FILENAME (not full path) is duplicated
    if basenames.count(basename) > 1:
        # Get immediate parent folder name only (not full path)
        parent = os.path.basename(os.path.dirname(filepath))
        if parent and parent not in [".", ""]:
            return f"{parent}/{basename}"
    
    # Default: just the filename
    return basename


_UNIT = re.compile(r"\s+\[[^\]]*\]$")


def without_unit(name: str) -> str:
    """\"ATT.Roll [deg]\" -> \"ATT.Roll\"; a name without a unit is returned as it is."""
    return _UNIT.sub("", name)


class SignalNameError(KeyError):
    """A name a script asked for that is not one signal of the file; str() is the message."""

    def __str__(self) -> str:                    # KeyError would print the message in quotes
        return str(self.args[0]) if self.args else ""


def resolve_signal_name(names: Iterable[str], wanted: str, where: str = "the file") -> str:
    """The signal `wanted` means, the way people write it in scripts (F31): the exact name, else
    the name without its unit (\"ATT.Roll\" for \"ATT.Roll [deg]\"), else either of those in any
    case. More than one match is an error - never a guess. Raises SignalNameError with the closest
    names when nothing matches."""
    names = list(names)
    if wanted in names:
        return wanted
    w = without_unit(wanted.strip())
    for key in (lambda s: s, str.casefold):
        hits = [n for n in names if key(n) == key(wanted.strip()) or key(without_unit(n)) == key(w)]
        if len(hits) == 1:
            return hits[0]
        if hits:
            shown = ", ".join(repr(n) for n in sorted(hits)[:6])
            raise SignalNameError(f"{wanted!r} matches several signals in {where}: {shown}. Write the full name.")
    bare: Dict[str, str] = {}
    for n in names:
        bare.setdefault(without_unit(n).casefold(), n)
    close = difflib.get_close_matches(w.casefold(), list(bare), n=3, cutoff=0.6)
    hint = (" Did you mean " + " or ".join(repr(bare[c]) for c in close) + "?") if close else ""
    raise SignalNameError(f"No signal named {wanted!r} in {where}.{hint} Every name: .signals in Python, `info` on the command line.")
