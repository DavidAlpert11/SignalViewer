"""
Templates: which open file goes into each slot, how well files fit, and a template's tabs with
real signal ids (T11b). The ONE implementation: the UI calls it through /api/templates/* and the
command line (batch reports) uses it directly.

A template is a set of tabs whose signals are stored by NAME together with the file SLOT they
come from ("File", or "Autopilot log" + "Telemetry"). It may include other templates (a
collection; slots with the same id are the same file). `runs` here are the run descriptions of
Store.list() / the UI: {id, path, format, signals: [{name, labels?}]}.

Built-in templates are data (builtin_templates.json). Three of them are "generators" (Quick look,
Compare open files, Position on the map): their tabs are made from the files by the UI and handed
to resolve() as extra tabs.
"""

import json
import os
import re
from typing import Dict, List, Optional, Set

ALL = "*all"                     # slot binding: every open file that has the signal
PALETTE = ["#3D8BFD", "#F2A93B", "#4CC38A", "#E5534B", "#B083F0", "#39C5CF", "#F778BA", "#8B949E"]

_BUILTIN = None


def builtin_templates() -> List[dict]:
    global _BUILTIN
    if _BUILTIN is None:
        with open(os.path.join(os.path.dirname(__file__), "builtin_templates.json"), encoding="utf-8") as f:
            _BUILTIN = json.load(f)
    return _BUILTIN


# ----------------------------------------------------------------------------- names
_UNIT = re.compile(r" \[[^\]]*\]$")
_INST = re.compile(r"^([^.[]+)\[\d+\]\.")


def bare(n: str) -> str:
    """Name without the unit and the instance number: "IMU[0].AccX [m/s/s]" -> "IMU.AccX"."""
    return _INST.sub(r"\1.", _UNIT.sub("", n))


class NameIndex:
    """A file's names: exact set + bare name -> first name in sorted order."""

    def __init__(self, names):
        self.exact = set(names)
        self.bare: Dict[str, str] = {}
        for n in names:
            k = bare(n)
            cur = self.bare.get(k)
            if cur is None or n < cur:
                self.bare[k] = n

    def match(self, wanted: str) -> Optional[str]:
        """Exact first, then loosely (no unit / instance); "A|B" tries A then B."""
        for alt in wanted.split("|"):
            if alt in self.exact:
                return alt
            hit = self.bare.get(bare(alt))
            if hit is not None:
                return hit
        return None


_ix_cache: Dict[tuple, NameIndex] = {}


def index_of(run: dict) -> NameIndex:
    names = tuple(s["name"] for s in run.get("signals", []))
    key = (run.get("id"), len(names), hash(names))
    ix = _ix_cache.get(key)
    if ix is None:
        if len(_ix_cache) > 64:
            _ix_cache.clear()
        ix = _ix_cache[key] = NameIndex(names)
    return ix


def match_signal(names: List[str], wanted: str) -> Optional[str]:
    return NameIndex(names).match(wanted)


def match_count(run: dict, names: List[str]) -> int:
    ix = index_of(run)
    return sum(1 for n in names if ix.match(n))


# ----------------------------------------------------------------------------- structure
def expand(t: dict, all_: List[dict], seen: Optional[Set[str]] = None) -> dict:
    """A template with its included templates (recursively, each once; a loop is cut)."""
    seen = set() if seen is None else seen
    out = {"slots": list(t.get("slots") or []), "tabs": [{**x, "from": t.get("name", "")} for x in t.get("tabs") or []],
           "missing": [], "generators": [t] if t.get("generator") else []}
    seen.add(t.get("id"))
    for inc_id in t.get("includes") or []:
        inc = next((x for x in all_ if x.get("id") == inc_id), None)
        if inc is None:
            out["missing"].append(inc_id)
            continue
        if inc_id in seen:
            continue
        e = expand(inc, all_, seen)
        for s in e["slots"]:
            if not any(x["id"] == s["id"] for x in out["slots"]):
                out["slots"].append(s)
        out["tabs"] += e["tabs"]
        out["missing"] += e["missing"]
        out["generators"] += e["generators"]
    return out


def slot_of(slot: Optional[str], slots: List[dict]) -> str:
    return slot or (slots[0]["id"] if slots else "main")


def slot_names(slot_id: str, slots: List[dict], tabs: List[dict]) -> List[str]:
    """The signal names a slot asks for, over the given tabs (each once, in order)."""
    out: List[str] = []
    for tab in tabs:
        for p in tab.get("plots", []):
            out += [s["name"] for s in p.get("signals", []) if slot_of(s.get("slot"), slots) == slot_id]
            if p.get("xSignal") and slot_of(p.get("xSlot"), slots) == slot_id:
                out.append(p["xSignal"])
            for o in p.get("objects") or []:
                out += [r["name"] for r in (o.get("roles") or {}).values() if r and slot_of(r.get("slot"), slots) == slot_id]
    return list(dict.fromkeys(out))


def data_runs(runs: List[dict]) -> List[dict]:
    return [r for r in runs if r.get("format") != "derived"]


def base_name(p: str) -> str:
    return re.split(r"[\\/]", p or "")[-1] or p


def same_name_run(slot: dict, names: List[str], runs: List[dict], taken: Set[str]) -> Optional[dict]:
    """The open file with the same name as the one the slot was saved from (and some of its signals)."""
    if not slot.get("file"):
        return None
    want = slot["file"].lower()
    return next((r for r in data_runs(runs) if r["id"] not in taken and base_name(r.get("path", "")).lower() == want
                 and (not names or match_count(r, names) > 0)), None)


def auto_bind(e: dict, runs: List[dict], prefer: Optional[str] = None) -> Dict[str, str]:
    """A file for every slot: the same file as when saved, else the one with most of the slot's
    signals (a preferred format and `prefer` break ties), each file used once while others are left."""
    data = data_runs(runs)
    bind: Dict[str, str] = {}
    taken: Set[str] = set()
    for g in e["generators"]:
        if g.get("generator") == "compare":
            bind[g["slots"][0]["id"]] = ALL
    names_of = {s["id"]: slot_names(s["id"], e["slots"], e["tabs"]) for s in e["slots"]}
    order = sorted(e["slots"], key=lambda s: -len(names_of[s["id"]]))         # stable, like the UI's sort
    for s in order:
        if s["id"] in bind:
            continue
        same = same_name_run(s, names_of[s["id"]], runs, taken)
        if same:
            bind[s["id"]] = same["id"]
            taken.add(same["id"])
    for s in order:
        if s["id"] in bind:
            continue
        names = names_of[s["id"]]
        best, best_score = None, -1.0
        for r in data:
            share = match_count(r, names) / len(names) if names else 0.5
            score = share + (0.25 if r.get("format") in (s.get("formats") or []) else 0) \
                + (0.3 if r["id"] == prefer else 0) - (1 if r["id"] in taken else 0)
            if score > best_score:
                best_score, best = score, r
        if best is not None and (best_score > 0 or not names):
            bind[s["id"]] = best["id"]
            taken.add(best["id"])
        else:
            bind[s["id"]] = ""
    return bind


def fit(t: dict, all_: List[dict], runs: List[dict]) -> Optional[float]:
    """0..1: how well the open files fit a template. None for a template made only of generators
    that look at the files' contents (the UI decides those: it knows the position roles)."""
    data = data_runs(runs)
    if not data:
        return 0.0
    e = expand(t, all_)
    if e["generators"] and not e["tabs"]:
        return None if all(g.get("generator") == "objects" for g in e["generators"]) else 1.0
    found = total = 0
    bind = auto_bind(e, runs)
    for s in e["slots"]:
        names = slot_names(s["id"], e["slots"], e["tabs"])
        b = bind.get(s["id"])
        runs_for = data if b == ALL else [r for r in data if r["id"] == b]
        total += len(names)
        found += max((match_count(r, names) for r in runs_for), default=0)
    return found / total if total else 0.0


def slot_report(e: dict, runs: List[dict]) -> List[dict]:
    """Per slot: the names it asks for and how many each open file has (the binding dialog)."""
    out = []
    for s in e["slots"]:
        names = slot_names(s["id"], e["slots"], e["tabs"])
        out.append({"id": s["id"], "names": len(names), "counts": {r["id"]: match_count(r, names) for r in data_runs(runs)}})
    return out


# ----------------------------------------------------------------------------- resolve
def resolve(t: dict, all_: List[dict], bind: Dict[str, str], runs: List[dict], chosen: Optional[List[int]] = None,
            extra_tabs: Optional[List[dict]] = None) -> dict:
    """A template's tabs with real signal ids for these files: what the UI turns into workspace
    tabs and the batch report draws. Plots with nothing found are dropped (named in `dropped`);
    `missing` lists names no bound file has. A signal colour is None when the template has none
    (or the name was found in several files): the caller picks one."""
    e = expand(t, all_)
    tabs = [x for i, x in enumerate(e["tabs"]) if chosen is None or i in chosen] + list(extra_tabs or [])
    data = data_runs(runs)
    missing: Dict[str, None] = {}

    def ids(name: str, slot: Optional[str]) -> List[str]:
        b = bind.get(slot_of(slot, e["slots"]))
        files = data if b == ALL else [r for r in data if r["id"] == b]
        out = [f"{r['id']}/{hit}" for r in files for hit in [index_of(r).match(name)] if hit]
        if not out:
            missing[name.split("|")[0]] = None
        return out

    res: Dict[str, list] = {"tabs": [], "dropped": [], "missing": []}
    for tt in tabs:
        plots = []
        for tp in tt.get("plots", []):
            p = {"title": tp.get("title", ""), "mode": tp.get("mode") or "time", "signals": [], "ylim": tp.get("ylim"),
                 **{k: tp[k] for k in ("xyAlign", "fftWindow", "fftMethod", "fftLog", "specN", "caption") if tp.get(k) is not None}}
            if tp.get("xSignal"):
                p["xSignal"] = (ids(tp["xSignal"], tp.get("xSlot")) or [None])[0]
            for s in tp.get("signals", []):
                got = ids(s["name"], s.get("slot"))
                for sid in got:
                    one = len(got) == 1
                    p["signals"].append({"sig": sid, "color": s.get("color") if one else None, "width": s.get("width", 1.5),
                                         "scale": s.get("scale", 1), "offset": s.get("offset", 0), "state": s.get("state"),
                                         "tOffset": s.get("tOffset"), "label": s.get("label") if one else None,
                                         **({"limits": s["limits"]} if s.get("limits") else {})})
            for to in tp.get("objects") or []:
                roles = to.get("roles") or {}

                def role(k):
                    r = roles.get(k)
                    return (ids(r["name"], r.get("slot")) or [None])[0] if r else None
                lat, lon = role("lat"), role("lon")
                if not lat or not lon:                       # an object without its position is left out
                    continue
                p.setdefault("objects", []).append({
                    "name": to.get("name", ""), "kind": to.get("kind") or "aircraft", "color": to.get("color"), "lat": lat, "lon": lon,
                    **{k: role(k) for k in ("alt", "yaw", "pitch", "roll", "qw", "qx", "qy", "qz")},
                    **{k: to.get(k) for k in ("angleUnit", "altRef", "trail", "size")}})
            keep = any(not x.get("state") for x in p["signals"]) or (p["mode"] == "geo" and p.get("xSignal") and p["signals"]) \
                or p.get("objects")
            if keep:
                plots.append(p)
            else:
                res["dropped"].append(f"{tt.get('name', '')} › {tp.get('title', '')}")
        if not plots:
            continue
        lanes = [i for ln in tt.get("lanes") or [] for i in ids(ln["name"], ln.get("slot"))[:2]]
        rows = max(1, -(-len(plots) // tt.get("cols", 1))) if len(plots) < len(tt.get("plots", [])) else tt.get("rows", 1)
        res["tabs"].append({"name": tt.get("name", ""), "rows": rows, "cols": tt.get("cols", 1),
                            "rowSizes": tt.get("rowSizes") if rows == tt.get("rows") else None, "colSizes": tt.get("colSizes"),
                            "linkX": tt.get("linkX", True), "linkY": tt.get("linkY"), "sharedStates": lanes or None, "plots": plots})
    res["missing"] = list(missing)
    return res


def fill_colors(resolved: dict) -> dict:
    """Give every signal without a colour one from the palette, per plot (batch reports; the UI
    uses its own next-colour rule)."""
    for tab in resolved["tabs"]:
        for p in tab["plots"]:
            used = {s["color"] for s in p["signals"] if s["color"]}
            free = [c for c in PALETTE if c not in used] or PALETTE
            k = 0
            for s in p["signals"]:
                if not s["color"]:
                    s["color"] = free[k % len(free)]
                    k += 1
    return resolved
