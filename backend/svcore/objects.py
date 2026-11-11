"""
L12: the map objects of a recording, found from its signal names - the SAME rules as the app's
frontend/src/objectDetect.ts (N5, L1-L3), from the SAME tables (svcore/object_names.json). The shared
test vectors (tests/data/object_detect_cases.json) are run by both Vitest and pytest, so the two cannot
drift: a change to the rules is made in both files and the vectors say where they differ.

    from svcore.objects import detect
    d = detect([("r/POS.Lat [deg]", "POS.Lat [deg]"), ...], run_id="r", run_name="flight.bin")
    d["candidates"]   # [{prefix, name, cls, pos, attitude, picks: {role: {...}}, origin?, ...}], best first

An object is a PREFIX that has a latitude and a longitude under it - or a north / east / down, east /
north / up or ECEF x / y / z position (with the origin that places a local one on Earth). Every choice
carries its reason, as data (rule, word, via, origin.rule), for *Why?*.
"""
import json
import os
import re
from typing import Dict, List, Optional, Sequence, Tuple

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "object_names.json"), encoding="utf-8") as _f:
    NAMES = json.load(_f)

POS_ROLES = ["lat", "lon", "alt"]
VEC_ROLES = ["px", "py", "pz"]
ATT_ROLES = ["roll", "pitch", "yaw"]
QUAT = ["qw", "qx", "qy", "qz"]
VEL_ROLES = ["vn", "ve", "vd"]

ALIASES: Dict[str, List[str]] = NAMES["aliases"]
OWN_WORD: Dict[str, str] = NAMES["own_words"]
WORD_ROLE: Dict[str, str] = {}
for _r, _ws in ALIASES.items():
    for _w in _ws:
        WORD_ROLE[_w] = _r
XYZ = {"x": "px", "y": "py", "z": "pz"}
FRAME_WORDS = set(NAMES["frame_words"])
AXIS_WORDS = {"north": "n", "east": "e", "down": "d", "up": "u"}
AXIS_LETTERS = {"n": "n", "e": "e", "d": "d", "u": "u"}
LOCAL_ROLE = {"ned": {"n": "px", "e": "py", "d": "pz"}, "enu": {"e": "px", "n": "py", "u": "pz"}}
GLUED = re.compile(r"^(?:(ecef|ned|enu)([xyz])|([xyz])(ecef|ned|enu))$", re.I)
METRES = set(NAMES["metres"])
POS_SUB = set(NAMES["pos_sub"])
VEL_SUB = set(NAMES["vel_sub"])
VEL_WORDS = {"north": "vn", "east": "ve", "down": "vd", "n": "vn", "e": "ve", "d": "vd"}
NED_VEL: List[List[str]] = NAMES["ned_vel"]
FLAT_VEL: Dict[str, str] = {}
for _t in NED_VEL:
    for _i, _w in enumerate(_t):
        FLAT_VEL[_w] = VEL_ROLES[_i]
FLAT_VEL_LAST = {w.split("_")[-1] for w in FLAT_VEL}
ATT_SUB = set(NAMES["att_sub"])
UNIT_WORDS = set(NAMES["unit_words"])
CLASS_WORDS: Dict[str, List[str]] = NAMES["class_words"]
CLASS_OF: Dict[str, str] = {w: c for c, ws in CLASS_WORDS.items() for w in ws}
ANGLE_WORDS = set(ALIASES["roll"] + ALIASES["pitch"] + ALIASES["yaw"])
KNOWN_GROUPS: Dict[str, Dict] = NAMES["known_groups"]
NED_XYZ_GROUPS = [k for k, v in KNOWN_GROUPS.items() if (v.get("ned") or [None])[0] == "x"]
ATT_GROUPS = set(NAMES["att_groups"])
ORIGIN_WORDS: List[str] = NAMES["origin_words"]
ORIGIN_GROUPS = set(NAMES["origin_groups"])
RANK = {"truth": 0, "navigation": 1, "receiver": 2, "other": 3}

_INST = re.compile(r"\[[^\]]*\]$")


def base_of(prefix: str) -> str:
    return _INST.sub("", prefix)


def _last_word(prefix: str) -> str:
    return _INST.sub("", re.split(r"[./_]", prefix)[-1]).lower()


def is_origin_group(prefix: str) -> bool:
    return bool(prefix) and (_last_word(prefix) in ORIGIN_WORDS or base_of(prefix) in ORIGIN_GROUPS)


def class_of_segment(seg: str) -> Optional[str]:
    """The class of one whole path segment (nav2, ekf_3, gps[1] - a number may follow), or None."""
    return CLASS_OF.get(re.sub(r"[_-]?\d+$", "", _INST.sub("", seg.lower())))


# ---- the path of a name: the same cuts as the app's list (signalGroups.ts pathCuts) -----------------

_UNIT_TAIL = re.compile(r"\s*[\[(][^\[\]()]*[\])]\s*$")
_SEGMENT = re.compile(r"^[^\W\d](?:[\w\- ]*[\w\-])?(?:\[[^\]]*\])*$")


def path_cuts(name: str) -> Optional[Tuple[int, List[int]]]:
    m = _UNIT_TAIL.search(name)
    end = m.start() if m and not re.fullmatch(r"\[\d*\]", m.group(0).strip()) else len(name)
    start = 0
    while start < end and name[start] in "./":
        start += 1
    cuts: List[int] = []
    frm = start
    for i in range(start, end):
        if name[i] not in "./":
            continue
        if not _SEGMENT.match(name[frm:i]):
            return None
        cuts.append(i + 1)
        frm = i + 1
    if not cuts or not _SEGMENT.match(name[frm:end]):
        return None
    return start, cuts


# ---- one name ------------------------------------------------------------------------------------

_BRACKET_UNIT = re.compile(r"\s*[\[(]([^\[\]()]*)[\])]\s*$")


def _join(ps: Sequence[str], extra: Sequence[str]) -> str:
    a, b = ".".join(ps), "_".join(extra)
    return (a + "." + b) if (ps and extra) else (a or b)


def parse_name(name: str) -> Dict:
    """{"hit": {...}} (the role, its word, the object prefix, the sub-group, the unit, the frame / axis),
    {"miss": {...}} (a near miss: why it almost was a role), or {} (no role)."""
    br = _BRACKET_UNIT.search(name)
    if br and re.fullmatch(r"\d*", br.group(1).strip()):
        br = None                                           # "q[0]" is an index, not a unit
    base = name[:br.start()] if br else name
    p = path_cuts(base)
    if p:
        start, cuts = p
        segs = [base[start:cuts[0] - 1]] + [base[c:(cuts[i + 1] - 1 if i + 1 < len(cuts) else len(base))] for i, c in enumerate(cuts)]
    else:
        segs = [base]
    leaf = segs[-1]
    parents = segs[:-1]
    toks = leaf.split("_")
    unit = {"unit": br.group(1).strip(), "from": "brackets"} if br and br.group(1).strip() else None
    if len(toks) > 1 and toks[-1].lower() in UNIT_WORDS:
        unit = {"unit": toks.pop(), "from": "suffix"}
    low = [x.lower() for x in toks]
    # L2: a known flight-log group's own fields (XKF1[0].PN, vehicle_local_position.x / vx, not its "heading")
    kn = KNOWN_GROUPS.get(base_of(parents[0])) if len(parents) == 1 and len(toks) == 1 else None
    if kn:
        if low[0] in (kn.get("skip") or []):
            return {}
        if low[0] in (kn.get("ned") or []):
            return {"hit": {"role": VEC_ROLES[kn["ned"].index(low[0])], "word": toks[0], "prefix": parents[0], "unit": unit, "frame": "ned"}}
        if low[0] in (kn.get("vel") or []):
            return {"hit": {"role": VEL_ROLES[kn["vel"].index(low[0])], "word": toks[0], "prefix": parents[0], "unit": unit}}
    role, word, n = None, "", 0
    for k in (2, 1):
        if len(low) < k:
            continue
        r = WORD_ROLE.get("_".join(low[-k:]))
        if r:
            role, word, n = r, "_".join(toks[-k:]), k
            break
    before = toks[:len(toks) - n]
    if role:
        last = parents[-1].lower() if parents else None
        sub = None
        is_pos = role in POS_ROLES
        top = len(parents) == 1 and (base_of(parents[0]) in KNOWN_GROUPS or base_of(parents[0]) in ATT_GROUPS)
        if not before and last and not top and (last in POS_SUB if is_pos else last in ATT_SUB):
            sub = parents[-1]
            parents = parents[:-1]
        return {"hit": {"role": role, "word": word, "prefix": _join(parents, before), "sub": sub, "unit": unit}}
    lw = low[-1]
    last_seg = parents[-1].lower() if parents else ""
    if lw in VEL_WORDS and last_seg in VEL_SUB and len(toks) == 1:
        return {"hit": {"role": VEL_WORDS[lw], "word": toks[0], "prefix": _join(parents[:-1], []), "sub": parents[-1], "unit": unit}}
    lj = "_".join(low) if lw in FLAT_VEL_LAST else ""
    if lj:
        for w, r in FLAT_VEL.items():
            if lj == w or lj.endswith("_" + w):
                k = len(w.split("_"))
                return {"hit": {"role": r, "word": "_".join(toks[-k:]), "prefix": _join(parents, toks[:-k]), "unit": unit}}
    if lw in XYZ or lw in AXIS_WORDS or lw in AXIS_LETTERS or lw in FRAME_WORDS or GLUED.match(lw):
        pos = _metric_position(toks, parents, unit)
        if pos is not None:
            return pos
    miss = _near_miss(toks, low, parents)
    return {"miss": miss} if miss else {}


def _metric_position(toks: List[str], parents: List[str], unit) -> Optional[Dict]:
    tk: List[str] = []
    for x in toks:
        m = GLUED.match(x)
        tk += ([m.group(1), m.group(2)] if m.group(1) else [m.group(3), m.group(4)]) if m else [x]
    lo = [x.lower() for x in tk]

    def is_axis(w):
        return w in XYZ or w in AXIS_WORDS
    fw = aw = word = ""
    pre: List[str] = []
    ps = list(parents)
    subs: List[str] = []
    last, prev = lo[-1], (lo[-2] if len(lo) >= 2 else "")
    if len(lo) >= 2 and is_axis(last) and prev in FRAME_WORDS:
        fw, aw, word, pre = prev, last, tk[-1], tk[:-2]
    elif len(lo) >= 2 and last in FRAME_WORDS and is_axis(prev):
        fw, aw, word, pre = last, prev, tk[-2], tk[:-2]
    elif len(lo) == 1 and (is_axis(last) or last in AXIS_LETTERS):
        aw, word = last, tk[0]
        seg1 = ps[-1].lower() if ps else ""
        if seg1 in FRAME_WORDS:
            fw = seg1
            subs.insert(0, ps[-1])
            ps = ps[:-1]
        elif seg1 not in POS_SUB:
            return None
    else:
        return None
    if pre and pre[-1].lower() in POS_SUB:
        pre = pre[:-1]
    if not pre and ps and ps[-1].lower() in POS_SUB:
        subs.insert(0, ps[-1])
        ps = ps[:-1]
    prefix = _join(ps, pre)
    sub = ".".join(subs) if subs else None
    if fw == "ecef":
        return {"hit": {"role": XYZ[aw], "word": word, "prefix": prefix, "sub": sub, "unit": unit, "frame": "ecef"}} if aw in XYZ else {}
    if fw in ("ned", "enu"):
        r = XYZ[aw] if aw in XYZ else LOCAL_ROLE[fw].get(AXIS_WORDS.get(aw) or AXIS_LETTERS.get(aw, ""))
        return {"hit": {"role": r, "word": word, "prefix": prefix, "sub": sub, "unit": unit, "frame": fw}} if r else {}
    if aw in XYZ:
        return {"miss": {"role": "px", "why": "noframe", "detail": "_".join(tk), "prefix": prefix}}
    return {"hit": {"role": "px", "word": word, "prefix": prefix, "sub": sub, "unit": unit, "axis": AXIS_WORDS.get(aw) or AXIS_LETTERS[aw]}}


_GLUE_A = re.compile(r"^(.*[a-z0-9])(Lat|Lon|Lng|Alt|Roll|Pitch|Yaw|Heading|Latitude|Longitude|Altitude)$")
_GLUE_B = re.compile(r"^([Ll]at|[Ll]on|[Ll]ng|[Aa]lt|[Rr]oll|[Pp]itch|[Yy]aw|[Hh]eading|[Ll]atitude|[Ll]ongitude|[Aa]ltitude)([A-Z0-9].*)$")


def _edit1(a: str, b: str) -> bool:
    if a == b:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i + 1:] == b[i + 1:] if len(a) == len(b) else a[i:] == b[i + 1:]


def _near_miss(toks: List[str], low: List[str], parents: List[str]) -> Optional[Dict]:
    for i in range(len(low) - 1):
        r = WORD_ROLE.get(low[i])
        if r and r in OWN_WORD:
            return {"role": r, "why": "suffix", "detail": "_" + "_".join(toks[i + 1:]), "prefix": _join(parents, toks[:i])}
    leaf = "_".join(toks)
    g = _GLUE_A.match(leaf) or _GLUE_B.match(leaf)
    if g:
        w = (g.group(2) if g.group(2).lower() in WORD_ROLE else g.group(1)).lower()
        r = WORD_ROLE.get(w)
        if r:
            return {"role": r, "why": "glued", "detail": leaf, "prefix": _join(parents, [])}
    lw = leaf.lower()
    if 5 <= len(lw) <= 11 and re.fullmatch(r"[a-z]+", lw):
        for w, r in WORD_ROLE.items():
            if len(w) >= 5 and abs(len(w) - len(lw)) <= 1 and _edit1(lw, w):
                return {"role": r, "why": "spelling", "detail": f"{leaf} ≈ {w}", "prefix": _join(parents, [])}
    return None


def classify(prefix: str) -> Dict:
    """The class of a prefix: the known group, else the deepest whole segment that is a class word."""
    if base_of(prefix) in KNOWN_GROUPS:
        return {"cls": KNOWN_GROUPS[base_of(prefix)]["cls"], "known": base_of(prefix)}
    segs = [_INST.sub("", s).lower() for s in re.split(r"[./_]", prefix) if s]
    for s in reversed(segs):
        m = re.fullmatch(r"([a-z]+?)(\d+)?", s)
        c = m and CLASS_OF.get(m.group(1))
        if c:
            return {"cls": c, "word": s}
    return {"cls": "other"}


# ---- the objects of a file -----------------------------------------------------------------------

def detect(signals: Sequence[Tuple[str, str]], run_id: str = "", run_name: str = "") -> Dict:
    """The candidates of one file from its (id, name) signals: {"candidates", "incomplete", "nearMisses"}."""
    groups: Dict[str, Dict] = {}
    order: List[str] = []

    def get(prefix):
        g = groups.get(prefix)
        if g is None:
            g = groups[prefix] = {"prefix": prefix, "picks": {}, "frames": {}, "loose": {}}
            order.append(prefix)
        return g

    def score(x):
        return (0 if x["exact"] else 2) + (0 if x["rule"] == "prefix" else 1)

    def better(a, b):
        return a is None or score(b) < score(a) or (score(b) == score(a) and len(b["name"]) < len(a["name"]))
    misses: List[Dict] = []
    for sid, name in signals:
        res = parse_name(name)
        if "miss" in res:
            m = res["miss"]
            misses.append({"id": sid, "name": name, "role": m["role"], "why": m["why"], "detail": m["detail"], "prefix": m["prefix"]})
            continue
        hit = res.get("hit")
        if not hit:
            continue
        g = get(hit["prefix"])
        pick = {"role": hit["role"], "id": sid, "name": name, "rule": "subgroup" if hit.get("sub") else "prefix", "word": hit["word"],
                "exact": OWN_WORD.get(hit["role"]) == hit["word"].lower()}
        if hit.get("sub"):
            pick["via"] = hit["sub"]
        if hit.get("unit"):
            pick["unit"] = hit["unit"]
        if hit.get("axis") and not hit.get("frame"):
            if better(g["loose"].get(hit["axis"]), pick):
                g["loose"][hit["axis"]] = pick
            continue
        into = g["frames"].setdefault(hit["frame"], {}) if hit.get("frame") else g["picks"]
        if better(into.get(hit["role"]), pick):
            into[hit["role"]] = pick
    for g in groups.values():
        lo = g["loose"]
        if not (lo.get("n") and lo.get("e") and (lo.get("d") or lo.get("u"))):
            continue
        fr = "ned" if lo.get("d") else "enu"
        into = g["frames"].setdefault(fr, {})
        for a, r in LOCAL_ROLE[fr].items():
            p = lo.get(a)
            if p and better(into.get(r), {**p, "role": r}):
                into[r] = {**p, "role": r}

    def has_pos(g):
        return bool(g["picks"].get("lat") and g["picks"].get("lon")) or any(all(f.get(r) for r in VEC_ROLES) for f in g["frames"].values())
    prefixes = {p for p in order if has_pos(groups[p]) and not is_origin_group(p)}

    def lla(p):
        g = groups.get(p)
        return g if g and g["picks"].get("lat") and g["picks"].get("lon") and g["picks"].get("alt") else None

    def parent_of(p):
        i = max(p.rfind("."), p.rfind("_"))
        return "" if i < 0 else p[:i]
    origins = [(p, parent_of(p)) for p in order if is_origin_group(p) and base_of(p) not in ORIGIN_GROUPS and lla(p)]

    def origin_of(prefix, kn):
        def make(p, rule):
            g = lla(p)
            o = {"ids": [g["picks"]["lat"]["id"], g["picks"]["lon"]["id"], g["picks"]["alt"]["id"]], "via": p, "rule": rule}
            if kn and kn.get("originMoves"):
                o["moves"] = True
            return o
        for w in ORIGIN_WORDS:
            for sep in (".", "_"):
                p = prefix + sep + w if prefix else w
                if lla(p):
                    return make(p, "own")
        for p in (kn or {}).get("origin") or []:
            if lla(p):
                return make(p, "known")

        def above(a):
            return a == "" or prefix.startswith(a + ".") or prefix.startswith(a + "_")
        best = None
        for p, owner in origins:
            if owner == prefix:
                continue
            ok = above(owner) or (owner != "" and parent_of(owner) == parent_of(prefix) and re.sub(r"\d+$", "", _last_word(owner)) in CLASS_OF)
            if ok and (best is None or len(owner) > best[1]):
                best = (p, len(owner))
        return make(best[0], "sibling") if best else None

    candidates: List[Dict] = []
    incomplete: List[Dict] = []
    for prefix in order:
        g = groups[prefix]
        if is_origin_group(prefix):
            continue
        if not has_pos(g):
            has = [r for r in g["picks"] if r in ("lat", "lon")]
            if has:
                incomplete.append({"runId": run_id, "prefix": prefix, "has": has, "missing": [r for r in ("lat", "lon") if r not in g["picks"]]})
            continue
        picks: Dict[str, Dict] = {}
        pos = "lla"
        if g["picks"].get("lat") and g["picks"].get("lon"):
            for r in POS_ROLES:
                if g["picks"].get(r):
                    picks[r] = g["picks"][r]
        else:
            pos = next(f for f in ("ned", "enu", "ecef") if g["frames"].get(f) and all(g["frames"][f].get(r) for r in VEC_ROLES))
            picks.update(g["frames"][pos])
        for r in ATT_ROLES + QUAT:
            if g["picks"].get(r):
                picks[r] = g["picks"][r]
        if g["picks"].get("vn") and g["picks"].get("ve"):
            for r in VEL_ROLES:
                if g["picks"].get(r):
                    picks[r] = g["picks"][r]
        kn = KNOWN_GROUPS.get(base_of(prefix))
        if kn and kn.get("attFrom") and not any(picks.get(r) for r in ATT_ROLES) and not all(picks.get(r) for r in QUAT) \
                and not (kn.get("unlessAlso") and any(base_of(p) == kn["unlessAlso"] and p in prefixes for p in order)):
            for a in kn["attFrom"]:
                src = next((groups[p] for p in order if base_of(p) == a and (any(groups[p]["picks"].get(r) for r in ATT_ROLES)
                                                                            or all(groups[p]["picks"].get(r) for r in QUAT))), None)
                if not src:
                    continue
                for r in ATT_ROLES + QUAT:
                    if src["picks"].get(r):
                        picks[r] = {**src["picks"][r], "rule": "known", "via": src["prefix"]}
                break
        angles = any(picks.get(r) for r in ATT_ROLES)
        if not angles:
            for r in ATT_ROLES:
                picks.pop(r, None)
        if angles or not all(picks.get(r) for r in QUAT):
            for r in QUAT:
                picks.pop(r, None)
        attitude = "angles" if angles else "quaternion" if picks.get("qw") else "none"
        missing = (["alt"] if pos == "lla" and not picks.get("alt") else []) + \
            (ATT_ROLES if attitude == "none" else [r for r in ATT_ROLES if not picks.get(r)] if attitude == "angles" else [])
        c = classify(prefix)
        cand = {"key": f"{run_id}|{prefix}", "runId": run_id, "prefix": prefix,
                "name": prefix or re.sub(r"\.[^.]+$", "", run_name), "cls": c["cls"],
                "clsWhy": {k: v for k, v in (("word", c.get("word")), ("known", c.get("known"))) if v},
                "pos": pos, "picks": picks, "attitude": attitude, "full": attitude != "none" and (pos != "lla" or bool(picks.get("alt"))),
                "missing": missing, "nearMisses": []}
        if pos in ("ned", "enu"):
            o = origin_of(prefix, kn)
            if o:
                cand["origin"] = o
        if pos != "lla":
            u = next((picks[r]["unit"]["unit"] for r in VEC_ROLES if picks.get(r, {}).get("unit") and picks[r]["unit"]["unit"].lower() not in METRES), None)
            if u:
                cand["badUnit"] = u
        if kn and kn.get("lane"):
            m = re.search(r"\[(\d+)\]$", prefix)
            cand["lane"] = {"ekf": kn["lane"], "n": int(m.group(1)) if m else 0}
        candidates.append(cand)
    by_prefix = {c["prefix"]: c for c in candidates}
    loose: List[Dict] = []
    for m in misses:
        up = m["prefix"][:m["prefix"].rfind(".")] if "." in m["prefix"] else ""
        hit = by_prefix.get(m["prefix"]) or by_prefix.get(up)
        nm = {k: v for k, v in m.items() if k != "prefix"}
        if hit:
            if len(hit["nearMisses"]) < 8:
                hit["nearMisses"].append(nm)
        elif len(loose) < 20:
            loose.append(nm)
    at = {id(c): i for i, c in enumerate(candidates)}
    candidates.sort(key=lambda c: (-int(c["full"]), RANK[c["cls"]], KNOWN_GROUPS.get(base_of(c["prefix"]), {}).get("order", 50), at[id(c)]))
    return {"candidates": candidates, "incomplete": incomplete, "nearMisses": loose}


def addable(c: Dict) -> bool:
    """As the app's *Add all*: LLA or ECEF, or NED / ENU with its origin; never a position in another unit."""
    return not c.get("badUnit") and (c["pos"] in ("lla", "ecef") or bool(c.get("origin")))
