"""A run's recording found from its row (M3): a folder and a file name made from the row - `flight_{run_id}.bin`
({run_id} is the run-id column, any other column name in braces is that column; `*` matches anything), or, with
no pattern, the file whose name ends with the run's number. Looked up only when a set's runs are shown - nothing
is read ahead, only the folder's names are listed."""
import fnmatch
import os
import re
from typing import Iterable, List, Optional, Tuple

import pandas as pd

MAX_FILES = 50_000          # a folder of a whole archive: names enough, never a long stall


class RecordingsError(ValueError):
    pass


def _text(v) -> str:
    """A cell as it appears in a file name: 7.0 -> "7"."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _files(folder: str, exts: Optional[Iterable[str]]) -> List[str]:
    ok = tuple(e.lower() for e in exts) if exts else None
    out: List[str] = []
    for root, dirs, names in os.walk(folder):
        dirs.sort()
        for n in sorted(names):
            if ok is None or n.lower().endswith(ok):
                out.append(os.path.join(root, n))
                if len(out) >= MAX_FILES:
                    return out
    return out


def find_recordings(rows: pd.DataFrame, id_col: Optional[str], folder: str, pattern: str = "",
                    exts: Optional[Iterable[str]] = None) -> Tuple[List[Optional[str]], List[str]]:
    """Each row's recording (None: not found) and the names wanted for the rows not found."""
    folder = os.path.expanduser(folder.strip())
    if not os.path.isdir(folder):
        raise RecordingsError(f"The recordings folder {folder} does not exist - choose it again in the set's details.")
    pattern = pattern.strip()
    keys = re.findall(r"\{([^{}]+)\}", pattern)
    for k in keys:
        if k == "run_id" and not id_col:
            raise RecordingsError("The name pattern uses {run_id}, but no column has the role Run id - give one in the Columns step.")
        if k != "run_id" and k not in rows.columns:
            raise RecordingsError(f"The name pattern uses {{{k}}}, but the table has no column {k}.")
    if not pattern and not id_col:
        raise RecordingsError("No column has the role Run id - give one in the Columns step, or a name pattern.")
    files = _files(folder, exts)
    lower = [(os.path.basename(f).lower(), os.path.splitext(os.path.basename(f))[0].lower(), f) for f in files]
    per_run: List[Optional[str]] = []
    wanted: List[str] = []
    for _, row in rows.iterrows():
        if pattern:
            want = re.sub(r"\{([^{}]+)\}", lambda m: _text(row[id_col if m.group(1) == "run_id" else m.group(1)]), pattern)
            w = want.lower()
            hit = next((f for name, stem, f in lower if fnmatch.fnmatchcase(name, w) or fnmatch.fnmatchcase(stem, w)), None)
        else:
            n = _text(row[id_col])
            want = f"…{n}"
            end = re.compile(rf"(?:^|\D)0*{re.escape(n.lstrip('0') or '0')}$")
            hit = next((f for _, stem, f in lower if end.search(stem)), None)
        per_run.append(hit)
        if hit is None:
            wanted.append(want)
    return per_run, wanted
