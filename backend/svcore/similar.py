"""L12: the families of similar signals of one file (L9) in Python - the same rules as the app's
frontend/src/similar.ts: names equal but for one path segment that differs by an instance (GPS[0] / GPS[1]),
a number (nav1 / nav2) or a class word (truth / nav); `loose`: also 1-2 edits, or the same leaf under
different parents. Names only, no data."""
import re
from typing import Dict, List, Optional, Sequence, Tuple

from svcore.objects import ANGLE_WORDS, class_of_segment, path_cuts

_UNIT = re.compile(r"\s*\[([^\]]*)\]\s*$")
_INST = re.compile(r"^(.*?)\[(\d+)\]$")
_NUM = re.compile(r"^(.*?)[_-]?(\d+)$")


def _split(name: str) -> Optional[Tuple[List[str], str]]:
    p = path_cuts(name)
    if not p:
        return None
    m = _UNIT.search(name)
    unit = m.group(1).strip() if m and not re.fullmatch(r"\d*", m.group(1)) else ""
    end = m.start() if (m and unit) else len(name)
    start, cuts = p
    segs, frm = [], start
    for c in cuts:
        segs.append(name[frm:c - 1])
        frm = c
    segs.append(name[frm:end].strip())
    return segs, unit


def _edits(a: str, b: str) -> int:
    if abs(len(a) - len(b)) > 2:
        return 3
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
        if min(cur) > 2:
            return 3
        prev = cur
    return prev[len(b)]


def families(signals: Sequence[Tuple[str, str]], loose: bool = False) -> List[Dict]:
    """[{key, leaf, how, members: [{id, name, seg, unit, cls}], unitsDiffer}] - as similar.ts findFamilies."""
    parsed = [(sid, name, sp) for sid, name in signals for sp in [_split(name)] if sp]
    buckets: Dict[str, list] = {}
    for x in parsed:
        segs = x[2][0]
        for i in range(len(segs) - 1):
            key = f"{i}|" + ".".join("*" if j == i else g for j, g in enumerate(segs))
            buckets.setdefault(key, []).append((x, i))
    out: List[Dict] = []
    in_family: set = set()
    for key, all_ in buckets.items():
        if len(all_) < 2:
            continue
        left = list(all_)
        groups = []

        def take(b, how, star):
            if len(b) >= 2:
                groups.append((b, how, star))
                for y in b:
                    left.remove(y)
        for rx, how, fmt in ((_INST, "instance", "{}[*]"), (_NUM, "number", "{}*")):
            m: Dict[str, list] = {}
            for y in list(left):
                r = rx.match(y[0][2][0][y[1]])
                if r and r.group(1):
                    m.setdefault(r.group(1).lower(), []).append(y)
            for k, b in m.items():
                first = rx.match(b[0][0][2][0][b[0][1]])
                take(b, how, fmt.format(first.group(1) if first else k))
        take([y for y in left if class_of_segment(y[0][2][0][y[1]])], "class", "*")
        if loose and len(left) >= 2:
            segs0 = [y[0][2][0][y[1]] for y in left]
            if all(s == segs0[0] or _edits(s.lower(), segs0[0].lower()) <= 2 for s in segs0):
                take(list(left), "edit", "*")
        for b, how, star in groups:
            segs = [y[0][2][0][y[1]] for y in b]
            if len(set(segs)) != len(segs):
                continue
            i = b[0][1]
            leaf = ".".join(star if j == i else g for j, g in enumerate(b[0][0][2][0]))
            members = [{"id": y[0][0], "name": y[0][1], "seg": y[0][2][0][i], "unit": y[0][2][1], "cls": class_of_segment(y[0][2][0][i])} for y in b]
            in_family.update(m["id"] for m in members)
            out.append({"key": f"{key}|{how}|{star}", "leaf": leaf, "how": how, "members": members,
                        "unitsDiffer": len({m["unit"].lower() for m in members}) > 1})
    if loose:
        by_leaf: Dict[str, list] = {}
        for x in parsed:
            if x[0] not in in_family:
                by_leaf.setdefault(x[2][0][-1].lower(), []).append(x)
        for lf, b in by_leaf.items():
            if 2 <= len(b) <= 12:
                members = [{"id": x[0], "name": x[1], "seg": ".".join(x[2][0][:-1]), "unit": x[2][1], "cls": class_of_segment(x[2][0][0])} for x in b]
                out.append({"key": f"leaf|{lf}", "leaf": "*." + b[0][2][0][-1], "how": "leaf", "members": members,
                            "unitsDiffer": len({m["unit"].lower() for m in members}) > 1})
    return out


def reference_of(f: Dict) -> Dict:
    return next((m for m in f["members"] if m["cls"] == "truth"), f["members"][0])


def angle_wrap(name: str):
    """360 / "2pi" for an angle leaf with deg / rad, "ask" for an angle without a unit, else None (similar.ts)."""
    m = _UNIT.search(name)
    unit = m.group(1).strip().lower() if m else ""
    base = re.split(r"[./]", name[:m.start()] if m else name)[-1]
    word = re.sub(r"\[\d+\]$", "", base.lower()).split("_")[-1]
    if word not in ANGLE_WORDS:
        return None
    if re.fullmatch(r"deg|degs|degree|degrees|°", unit):
        return 360
    if re.fullmatch(r"rad|rads|radian|radians", unit):
        return "2pi"
    return None if unit else "ask"
