"""CH2 (owner, 2026-11-26): a communication channel's anomalies - what is out of the ordinary in a link's messages,
beyond their content, each with its time, and how many of each kind.

"I want the app to recognise repeating patterns beyond the message content (header, checksum, a handshake), show
graphically whether there are anomalies, count them and compare the result with similar files."

The patterns themselves are found by `bytestream.decode` (header, length, type, checksum) and `bytestream.exchange`
(request -> reply, the handshake); this module reads what breaks them, on every message (CLAUDE.md: nothing sampled):

    per direction   checksum   a frame whose checksum fails
                    broken     a frame that broke off (its length ran past the next header): the walk resynced
                    length     a frame of a length its type never has otherwise (>= 90 % of the type share one length)
                    unknown    a type the structure does not describe; without a structure, a type seen at most twice
                               among >= 200 messages that is not a handshake step
                    counter    a payload byte that steps by one from message to message of a type (>= 90 %) skips
                               (messages lost on the way) or repeats (the same one sent again)
                    gap        a periodic type silent for more than 3 x its period (a rate drop)
    both ways       unanswered a request whose reply never came (within the link's timeout)
                    retry      a request sent again before its reply came
                    late       a reply far later than usual: over the median + 6 x the MAD and over 2 x the median
                    reconnect  the handshake again after the first one
                    handshake  a handshake whose steps differ from the first one (a step missing, out of order)
"""
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from svcore.bytestream import _payload, exchange

KINDS = ("checksum", "broken", "length", "unknown", "counter", "gap", "unanswered", "retry", "late", "reconnect", "handshake")
GAP_PERIODS = 3.0
LATE_MADS = 6.0


class _Events:
    def __init__(self):
        self.rows: List[Tuple[float, str, str, Optional[int], str]] = []

    def add(self, kind: str, t: float, side: str, typ: Optional[int], detail: str = ""):
        self.rows.append((float(t), kind, side, None if typ is None else int(typ), detail))


def _hex(v: Optional[int]) -> str:
    return "—" if v is None else "0x%02X" % int(v)


def _side(r: Dict, name: str, ev: _Events, known: Optional[Sequence[int]], hs_types: set):
    m = r["messages"]
    t, ty, ln, ok = m["t"], m["type"], m["len"], m["ok"]
    typed = r["typeOffset"] is not None
    if r["checksum"]:
        for i in np.flatnonzero(~ok):
            ev.add("checksum", t[i], name, int(ty[i]) if typed else None, r["checksum"]["scheme"])
    for tb in r.get("broken", ()):
        ev.add("broken", tb, name, None)
    n = len(t)
    for x in r["types"]:
        v = x["type"]
        sel = np.flatnonzero(ty == v) if typed else np.arange(n)
        # a length the type never has otherwise
        if len(x["lengths"]) > 1:
            vals, cnt = np.unique(ln[sel], return_counts=True)
            main = vals[np.argmax(cnt)]
            if cnt.max() >= 0.9 * len(sel):
                for i in sel[ln[sel] != main]:
                    ev.add("length", t[i], name, v if typed else None, "%d bytes (usually %d)" % (ln[i], main))
        # a type the structure does not know, or one seen once or twice in a long stream
        if typed:
            if known is not None:
                if v not in known:
                    for i in sel:
                        ev.add("unknown", t[i], name, v, "not in the structure")
            elif x["count"] <= 2 and n >= 200 and (name, v) not in hs_types:
                for i in sel:
                    ev.add("unknown", t[i], name, v, "seen %d× in %d messages" % (x["count"], n))
        _counter(r, name, ev, sel, v if typed else None)
        _gaps(t[sel], name, ev, v if typed else None, x)


def _counter(r: Dict, name: str, ev: _Events, sel: np.ndarray, v: Optional[int]):
    """A sequence byte (an id, a counter) in the payload: the offset whose byte steps by one most often. A step next to
    a corrupted frame is the checksum's anomaly, one across a silence the gap's - not counted twice."""
    if len(sel) < 10:
        return
    m = r["messages"]
    pays = [_payload(r, int(i)) for i in sel]
    width = min(min(len(p_) for p_ in pays), 8)
    tt = m["t"][sel]
    dt = np.diff(tt)
    keep = np.ones(len(dt), dtype=bool)
    if r["checksum"]:
        ok = m["ok"][sel]
        keep &= ok[1:] & ok[:-1]
    per = float(np.median(dt)) if len(dt) else 0.0
    if per > 0:
        keep &= dt <= GAP_PERIODS * per
    if keep.sum() < 9:
        return
    best = None
    for j in range(width):
        col = np.array([int(p_[j]) for p_ in pays], dtype=np.int64)
        d = np.diff(col) % 256
        f = float(np.mean(d[keep] == 1))
        if f >= 0.9 and (best is None or f > best[0]):
            best = (f, j, col, d)
    if best is None:
        return
    _f, j, col, d = best
    for k in np.flatnonzero((d != 1) & keep):
        if d[k] == 0:
            ev.add("counter", tt[k + 1], name, v, "byte %d repeats %d" % (j, col[k + 1]))
        else:
            ev.add("counter", tt[k + 1], name, v, "byte %d jumps %d → %d (%d missing)" % (j, col[k], col[k + 1], d[k] - 1))


def _gaps(tt: np.ndarray, name: str, ev: _Events, v: Optional[int], x: Dict):
    """A periodic type that goes silent: an interval over 3 x its period (median), the type steady otherwise."""
    if len(tt) < 20 or not x.get("period"):
        return
    d = np.diff(tt)
    per = float(np.median(d))
    if per <= 0 or float(np.mean(np.abs(d - per) <= 0.5 * per)) < 0.8:      # not sent on its own clock
        return
    for k in np.flatnonzero(d > GAP_PERIODS * per):
        ev.add("gap", tt[k], name, v, "silent %.3g s (period %.3g s)" % (d[k], per))


def _late(q: Dict, ev: _Events):
    lat = np.asarray(q["lat"], dtype=np.float64)
    if len(lat) < 10:
        return
    med = float(np.median(lat))
    mad = max(float(np.median(np.abs(lat - med))), 0.05 * med, 1e-6)
    lim = max(med + LATE_MADS * mad, 2 * med)
    for k in np.flatnonzero(lat > lim):
        ev.add("late", q["t"][k], q["from"], q["request"], "%.3g ms (usually %.3g ms)" % (lat[k] * 1000, med * 1000))


def anomalies(sides: Sequence[Tuple[str, Dict]], known: Optional[Dict[str, Sequence[int]]] = None,
              timeout: float = 0.5) -> Dict:
    """The anomalies of a channel: one or two directions [(name, decode result)] - two are paired with
    `bytestream.exchange` (requests and replies, the handshake). `known`: per direction, the type ids its structure
    describes (else a rare type is the unknown one). Returns the events (time order; columns t, kind, dir, type,
    detail), the counts per kind and per direction, and the patterns found: per direction the framing, the
    request -> reply pairs and the handshake."""
    ev = _Events()
    ex = exchange(sides[0][1], sides[1][1], (sides[0][0], sides[1][0]), timeout) if len(sides) == 2 else None
    hs_types = {(s["dir"], s["type"]) for h in (ex or {}).get("handshake", []) for s in h["steps"]}
    for name, r in sides:
        _side(r, name, ev, (known or {}).get(name), hs_types)
    pairs: List[Dict] = []
    hs: List[Dict] = []
    if ex:
        for q in ex["pairs"]:
            for u in q["unanswered"]:
                ev.add("unanswered", u, q["from"], q["request"], "no %s %s" % (q["to"], _hex(q["reply"])))
            for u in q["retries"]:
                ev.add("retry", u, q["from"], q["request"], "")
            _late(q, ev)
            lt = q["latency"] or {}
            pairs.append({"from": q["from"], "to": q["to"], "request": q["request"], "reply": q["reply"], "how": q["how"],
                          "requests": q["requests"], "replies": q["replies"], "mean": lt.get("mean"), "max": lt.get("max")})
        hs = ex["handshake"]
        if hs:
            first = [(s["dir"], s["type"]) for s in hs[0]["steps"]]
            for h in hs[1:]:
                steps = [(s["dir"], s["type"]) for s in h["steps"]]
                ev.add("reconnect", h["t"], h["steps"][0]["dir"], h["steps"][0]["type"], "")
                if steps != first:
                    ev.add("handshake", h["t"], h["steps"][0]["dir"], h["steps"][0]["type"],
                           " → ".join("%s %s" % (d, _hex(x)) for d, x in steps))
    rows = sorted(ev.rows, key=lambda e: (e[0], KINDS.index(e[1])))
    counts = {k: 0 for k in KINDS}
    by_dir: Dict[str, Dict[str, int]] = {name: {} for name, _r in sides}
    for _t, k, d, _ty, _x in rows:
        counts[k] += 1
        by_dir.setdefault(d, {})[k] = by_dir.get(d, {}).get(k, 0) + 1
    t0 = min((float(r["messages"]["t"][0]) for _n, r in sides if r["count"]), default=0.0)
    t1 = max((float(r["messages"]["t"][-1]) for _n, r in sides if r["count"]), default=0.0)
    return {"kinds": list(KINDS), "counts": counts, "byDir": by_dir, "total": len(rows), "span": [t0, t1],
            "events": {"t": [e[0] for e in rows], "kind": [e[1] for e in rows], "dir": [e[2] for e in rows],
                       "type": [e[3] for e in rows], "detail": [e[4] for e in rows]},
            "sides": [{"name": name, "count": r["count"], "header": r["header"], "framing": r["framing"],
                       "typeOffset": r["typeOffset"], "checksum": (r["checksum"] or {}).get("scheme"),
                       "types": [{"type": x["type"], "count": x["count"], "rate": x["rate"]} for x in r["types"]]}
                      for name, r in sides],
            "pairs": pairs, "timeout": timeout,
            "handshake": [{"t": h["t"], "steps": [{"dir": s["dir"], "type": s["type"], "t": s["t"]} for s in h["steps"]]} for h in hs]}


def count_signal(res: Dict) -> Tuple[np.ndarray, np.ndarray]:
    """The anomalies so far (a step at each one) - the op `messages`, what `anomalies`: they line up with the data
    on the timeline. Starts at 0 at the channel's first message, ends at its last."""
    t = np.asarray(res["events"]["t"], dtype=np.float64)
    t0, t1 = res["span"]
    tt = np.concatenate([[t0], t, [max(t1, t[-1] if len(t) else t1)]])
    yy = np.concatenate([[0.0], np.arange(1, len(t) + 1, dtype=np.float64), [float(len(t))]])
    return tt, yy
