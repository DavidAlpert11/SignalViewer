"""P1 (2026-11-12): Tacview's CSV import - the second way out (Tacview Standard).

Tacview's page "Real-life CSV data": one file per object; the FILE NAME is
``Model name (Pilot name) [Color].csv``; columns by header in any order: ``Time`` (seconds from the
start), ``Longitude``, ``Latitude`` (degrees), ``Altitude`` (metres MSL), ``Roll``, ``Pitch``, ``Yaw``
(degrees); comma separated, a point as the decimal mark. Load: File -> Open the first, File -> Merge the
others (or drag them in together).

The objects come from the same sample() as the ACMI (svcore/acmi.py): the same time grid, the same
"no position" rule, the same models and colours. A stretch where an object is absent is not written
(Tacview reads a blank cell as "unchanged", which would freeze the object in place)."""
from __future__ import annotations

import os
import re
from typing import Dict, List, Sequence

from svcore.acmi import MODELS, AcmiObject, _num, acmi_color, sample


def _safe(name: str) -> str:
    """A name fit for a file name on Windows, macOS and Linux (and for Tacview's parser: no brackets
    or parentheses, which it reads as the colour and the pilot)."""
    s = re.sub(r'[\\/:*?"<>|()\[\]\x00-\x1f]', " ", name)
    s = " ".join(s.split()).strip(". ")
    return s or "Object"


def write_csvs(objects: Sequence[AcmiObject], folder: str, rate: float = 10.0,
               left_out: List[str] | None = None) -> List[str]:
    """Write one CSV per object into `folder`; returns the paths, in the objects' order."""
    grid, rows, left = sample(objects, rate)
    if left_out is not None:
        left_out.extend(left)
    t0 = float(grid[0])
    os.makedirs(folder, exist_ok=True)
    used: Dict[str, int] = {}
    paths: List[str] = []
    for r in rows:
        o = r["o"]
        model = MODELS.get(o.get("kind", ""), "C172")
        base = f"{_safe(model)} ({_safe(str(o.get('name') or 'Object'))}) [{acmi_color(o.get('color', ''))}]"
        k = used.get(base.lower(), 0) + 1
        used[base.lower()] = k
        name = base if k == 1 else f"{_safe(model)} ({_safe(str(o.get('name') or 'Object'))} {k}) [{acmi_color(o.get('color', ''))}]"
        path = os.path.join(folder, name + ".csv")
        head = "Time,Longitude,Latitude,Altitude" + (",Roll,Pitch,Yaw" if r["att"] is not None else "")
        lines = [head]
        for a, b in r["spans"]:
            for i in range(a, b):
                cells = [_num(grid[i] - t0, 3), _num(r["lon"][i], 7), _num(r["lat"][i], 7), _num(r["alt"][i], 2)]
                if r["att"] is not None:
                    cells += [_num(((ang[i] + 180) % 360) - 180 if q < 2 else ang[i], 2) for q, ang in enumerate(r["att"])]
                lines.append(",".join(cells))
        tmp = path + ".part"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, path)
        paths.append(path)
    return paths
