"""26.U5: one rule for tolerances - the Compare panel and `signalviewer-cli compare` read the same file
and judge a signal the same way, so the GUI and CI give the same result.

The file (the format `cli compare --tolerances` has read since T58):
    {"default": {"abs": 0.5, "pct": 2, "time": 0.05, "outside_pct": 0.1},
     "signals": {"Speed": {"abs": 1}, "Gear": {"skip": true}, "ATT.Roll": {"as": "roll_deg"}}}
  abs          allowed |difference|, in the signal's unit
  pct          allowed difference in % of the baseline's value
  time         seconds a run may be early or late (the baseline's band is its lowest / highest within +-time)
  outside_pct  share of samples (%) that may be outside and still pass (default 0: every sample)
  skip         leave the signal out of the judgement
  as           the run's name for this signal (cli compare; the panel pairs signals by name)
A signal's entry is merged over the default. Keys are signal names, with or without their unit."""
from typing import Any, Dict, Optional, Tuple

from svcore.naming import without_unit

NUMBERS = ("abs", "pct", "time", "outside_pct")


def _entry(v: Any, where: str) -> Dict[str, Any]:
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise ValueError(f'{where}: expected {{"abs": .., "pct": ..}}, not {v!r}')
    out: Dict[str, Any] = {}
    for k, x in v.items():
        if k in NUMBERS:
            if x is None or x == "":
                continue
            try:
                f = float(x)
            except (TypeError, ValueError):
                f = float("nan")
            if k == "outside_pct" and not 0.0 <= f <= 100.0:
                raise ValueError(f"{where}: outside_pct is the share of samples allowed outside, from 0 to 100 (%), not {x!r}")
            if not f >= 0:
                raise ValueError(f"{where}: {k} is a number of 0 or more, not {x!r}")
            out[k] = f
        elif k == "skip":
            if x:
                out[k] = True
        else:
            out[k] = x                     # "as", and keys of later versions: kept as written
    return out


def parse(d: Any) -> Dict[str, Any]:
    """The tolerances as {"default": {...}, "signals": {name: {...}}}, checked; ValueError says what is wrong."""
    if d is None:
        return {"default": {}, "signals": {}}
    if not isinstance(d, dict):
        raise ValueError('expected {"default": {...}, "signals": {...}}')
    sigs = d.get("signals") or {}
    if not isinstance(sigs, dict):
        raise ValueError('"signals" is {"name": {"abs": ..}, ...}')
    return {"default": _entry(d.get("default"), "default"),
            "signals": {str(k): _entry(v, str(k)) for k, v in sigs.items()}}


def from_fields(abs_: Optional[float], pct: Optional[float], time: Optional[float]) -> Dict[str, Any]:
    """The tolerances of the older requests (one tolerance for every signal)."""
    return parse({"default": {"abs": abs_, "pct": pct, "time": time or None}})


def entry_key(tol: Dict[str, Any], name: str) -> Optional[str]:
    """The key of `name`'s own entry: the same name, else the same without its unit, else either in any case."""
    sigs = tol.get("signals") or {}
    if name in sigs:
        return name
    w = without_unit(name)
    for fold in (lambda s: s, str.casefold):
        hits = [k for k in sigs if fold(k) == fold(name) or fold(without_unit(k)) == fold(w)]
        if len(hits) == 1:
            return hits[0]
    return None


def for_signal(tol: Dict[str, Any], name: str, key: Optional[str] = None) -> Dict[str, Any]:
    """The default with the signal's own entry over it (`key`: the entry already resolved)."""
    k = key if key is not None else entry_key(tol, name)
    return {**(tol.get("default") or {}), **((tol.get("signals") or {}).get(k) or {} if k else {})}


def has_limit(t: Dict[str, Any]) -> bool:
    return t.get("abs") is not None or t.get("pct") is not None or bool(t.get("time"))


def any_limit(tol: Dict[str, Any]) -> bool:
    return has_limit(tol.get("default") or {}) or any(has_limit(v) for v in (tol.get("signals") or {}).values())


def judge(row: Dict[str, Any], t: Dict[str, Any]) -> Tuple[Optional[bool], Optional[float]]:
    """(pass, % of samples outside) of one compared run (a row of svcore.compare.compare made with t's
    abs / pct / time): pass when every sample is within, or all but outside_pct % of them (T65).
    (None, None) without a limit or when the row has no verdict."""
    if t.get("skip") or not has_limit(t) or "pass" not in row or row.get("withinPct") is None:
        return None, None
    outside = 100.0 - float(row["withinPct"])
    allowed = t.get("outside_pct")
    return bool(row["pass"]) or (allowed is not None and outside <= float(allowed) + 1e-9), outside
