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
                               among >= 200 messages, on its own (rare messages of several types within 1 s of
                               each other are a handshake's steps)
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


CAUSES = ("link", "capture", "none")
Row = Tuple[float, str, str, Optional[int], str, Dict]


class _Events:
    def __init__(self):
        self.rows: List[Row] = []

    def add(self, kind: str, t: float, side: str, typ: Optional[int], detail: str = "", **ref):
        """ref: what the cause needs to know (the message index, the counter's offset and missing values...)"""
        self.rows.append((float(t), kind, side, None if typ is None else int(typ), detail, ref))


def _hex(v: Optional[int]) -> str:
    return "—" if v is None else "0x%02X" % int(v)


def _side(r: Dict, name: str, ev: _Events, known: Optional[Sequence[int]], hs_types: set):
    m = r["messages"]
    t, ty, ln, ok = m["t"], m["type"], m["len"], m["ok"]
    typed = r["typeOffset"] is not None
    if r["checksum"]:
        for i in np.flatnonzero(~ok):
            ev.add("checksum", t[i], name, int(ty[i]) if typed else None, r["checksum"]["scheme"], i=int(i))
    for tb in r.get("broken", ()):
        ev.add("broken", tb, name, None)
    n = len(t)
    # the rare messages (a type seen at most twice): a few of them close together are a handshake's steps, even with
    # one direction alone - only a rare message on its own is an unknown one
    rare = {x["type"] for x in r["types"] if x["count"] <= 2}
    rare_at = [(float(t[i]), int(ty[i])) for i in np.flatnonzero(np.isin(ty, list(rare)))] if typed and rare else []
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
                    if not _with_others(t[i], v, rare_at):
                        ev.add("unknown", t[i], name, v, "seen %d× in %d messages" % (x["count"], n))
        j = _counter(r, name, ev, sel, v if typed else None)
        _gaps(r, sel, name, ev, v if typed else None, x, j)


def _with_others(at: float, v: int, rare_at: List[Tuple[float, int]]) -> bool:
    return any(abs(tt - at) <= 1.0 and ty != v for tt, ty in rare_at)


def _counter(r: Dict, name: str, ev: _Events, sel: np.ndarray, v: Optional[int]) -> Optional[int]:
    """A sequence byte (an id, a counter) in the payload: the offset whose byte steps by one most often. A step next to
    a corrupted frame is the checksum's anomaly, one across a silence the gap's - not counted twice."""
    if len(sel) < 10:
        return None
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
        return None
    best = None
    for j in range(width):
        col = np.array([int(p_[j]) for p_ in pays], dtype=np.int64)
        d = np.diff(col) % 256
        f = float(np.mean(d[keep] == 1))
        if f >= 0.9 and (best is None or f > best[0]):
            best = (f, j, col, d)
    if best is None:
        return None
    _f, j, col, d = best
    for k in np.flatnonzero((d != 1) & keep):
        if d[k] == 0:
            ev.add("counter", tt[k + 1], name, v, "byte %d repeats %d" % (j, col[k + 1]), j=j, repeat=True, missing=[], since=float(tt[k]))
        else:
            ev.add("counter", tt[k + 1], name, v, "byte %d jumps %d → %d (%d missing)" % (j, col[k], col[k + 1], d[k] - 1), j=j,
                   repeat=False, missing=[int((col[k] + x) % 256) for x in range(1, int(d[k]))], since=float(tt[k]))
    return j


def _gaps(r: Dict, sel: np.ndarray, name: str, ev: _Events, v: Optional[int], x: Dict, j: Optional[int]):
    """A periodic type that goes silent: an interval over 3 x its period (median), the type steady otherwise. With a
    counter in the type, how far it moved across the silence: as many as the periods missed - the device kept
    sending (the capture missed them); by one - the device itself stopped."""
    tt = r["messages"]["t"][sel]
    if len(tt) < 20 or not x.get("period"):
        return
    d = np.diff(tt)
    per = float(np.median(d))
    if per <= 0 or float(np.mean(np.abs(d - per) <= 0.5 * per)) < 0.8:      # not sent on its own clock
        return
    for k in np.flatnonzero(d > GAP_PERIODS * per):
        moved = None
        if j is not None:
            a, b = _payload(r, int(sel[k])), _payload(r, int(sel[k + 1]))
            if len(a) > j and len(b) > j:
                moved = int((int(b[j]) - int(a[j])) % 256)
        ev.add("gap", tt[k], name, v, "silent %.3g s (period %.3g s)" % (d[k], per), to=float(tt[k + 1]),
               periods=int(round(d[k] / per)), moved=moved)


def _late(q: Dict, ev: _Events):
    lat = np.asarray(q["lat"], dtype=np.float64)
    if len(lat) < 10:
        return
    med = float(np.median(lat))
    mad = max(float(np.median(np.abs(lat - med))), 0.05 * med, 1e-6)
    lim = max(med + LATE_MADS * mad, 2 * med)
    for k in np.flatnonzero(lat > lim):
        ev.add("late", q["t"][k], q["from"], q["request"], "%.3g ms (usually %.3g ms)" % (lat[k] * 1000, med * 1000))


# ------------------------------------------------------------------------------------------------ the cause

def _ids(r: Dict, typ: int, off: int) -> Tuple[np.ndarray, np.ndarray]:
    """The times and the id byte (payload offset `off`) of every message of a type, a corrupted one too (-1: too short)."""
    m = r["messages"]
    idx = np.flatnonzero(m["type"] == typ)
    vals = []
    for i in idx:
        p_ = _payload(r, int(i))
        vals.append(int(p_[off]) if len(p_) > off else -1)
    return m["t"][idx], np.asarray(vals, dtype=np.int64)


def _causes(sides: Dict[str, Dict], ex: Optional[Dict], rows: List[Row], timeout: float) -> List[Tuple[str, str]]:
    """CH12 (owner, 2026-11-27: "sometimes the signals are a sniffer's, not part of the traffic: a bug only in the
    sniffing while the bytes between the devices were fine - if the pattern carries on despite the anomaly, it is
    probably the sniffer's"): each anomaly's cause, from how the link itself behaved around it -

        link      the link shows it: a request sent again, no reply and then a reconnect, the device's counter stopped
                  with a silence, a late reply, a handshake again
        capture   the other side proves the bytes were fine on the wire - a request with a bad checksum answered (its id
                  echoed), a request missing from the capture whose reply is there, a reply to a broken frame, the
                  device's counter running on through a silence
        none      nothing reacted: the link carried on as if nothing happened (the capture's, most likely - but the
                  link alone cannot prove it)

    Returns (cause, why) per row."""
    pairs = [q for q in (ex or {}).get("pairs", []) if q["how"] == "id" and q["echo"]]
    reconnects = [h["t"] for h in (ex or {}).get("handshake", [])[1:]]
    cache: Dict[Tuple[str, int, int], Tuple[np.ndarray, np.ndarray]] = {}

    def ids(side: str, typ: int, off: int):
        k = (side, typ, off)
        if k not in cache:
            cache[k] = _ids(sides[side], typ, off)
        return cache[k]

    def reconnected(end: float) -> bool:
        """the handshake came again right as a silence ended (the link was re-made)"""
        return any(end - timeout <= h <= end + 1.0 for h in reconnects)

    def silent_until_reconnect(q: Dict, t0: float) -> bool:
        """no reply of this pair from t0 until the handshake came again, within 2 s: the link was down"""
        nxt = [h for h in reconnects if t0 < h <= t0 + 2.0]
        return bool(nxt) and not any(t0 < x <= nxt[0] for x in q["t"])

    def as_request(side: str, typ: Optional[int]):
        return next((q for q in pairs if q["from"] == side and q["request"] == typ), None)

    def as_reply(side: str, typ: Optional[int]):
        return next((q for q in pairs if q["to"] == side and q["reply"] == typ), None)

    def own_counter(side: str, typ: Optional[int]) -> bool:
        """the counter is the device's own: both directions known (a reply's sequence number may be the requester's,
        echoed) and this type is not a reply that echoes its request's id"""
        return ex is not None and as_reply(side, typ) is None

    gaps: List[Tuple[str, float, float, Tuple[str, str]]] = []
    out: List[Tuple[str, str]] = []
    for t, kind, side, typ, _detail, ref in rows:            # the gaps first: what falls in one follows its cause
        if kind == "gap":
            if reconnected(ref["to"]):
                c = ("link", "the handshake came again right after it")
            elif own_counter(side, typ) and ref.get("moved") is not None and ref["moved"] >= max(2, ref["periods"] - 1):
                c = ("capture", "the device's counter ran on through it: it kept sending, the capture missed them")
            elif own_counter(side, typ) and ref.get("moved") == 1:
                c = ("link", "the device's counter stopped with it: the device itself did not send")
            else:
                c = ("none", "the link carried on after it")
            gaps.append((side, t, ref["to"], c))

    # a silence in the same direction at the same time as one the device's own counter explains follows it (a reply type's
    # silence there is the same capture dropout - its own numbers are echoed, they prove nothing by themselves)
    gaps = [(s_, a, b, c) if c[0] != "none" else
            next(((s_, a, b, c2) for s2, a2, b2, c2 in gaps if s2 == s_ and c2[0] != "none" and a2 <= b and a <= b2), (s_, a, b, c))
            for s_, a, b, c in gaps]

    def in_gap(side: str, t: float) -> Optional[Tuple[str, str]]:
        return next((c for s_, a, b, c in gaps if s_ == side and a <= t <= b), None)

    for t, kind, side, typ, _detail, ref in rows:
        if kind in ("retry", "late", "reconnect", "handshake"):
            out.append(("link", "the devices did it"))
        elif kind == "gap":
            out.append(next(c for s_, a, _b, c in gaps if s_ == side and a == t))
        elif kind == "checksum":
            q, qr = as_request(side, typ), as_reply(side, typ)
            if q:
                tr, vr = ids(side, q["request"], q["echo"]["request"])
                me = int(vr[np.argmin(np.abs(tr - t))])
                tb, vb = ids(q["to"], q["reply"], q["echo"]["reply"])
                answered = bool(np.any((tb > t) & (tb <= t + timeout) & (vb == me)))
                again = bool(np.any((tr > t) & (tr <= t + 3 * timeout) & (vr == me)))
                out.append(("link", "sent again: the device did not take it") if again else
                           ("capture", "answered (its id echoed): the device read it whole") if answered else
                           ("link", "no reply came: the device did not take it"))
            elif qr:
                tb, vb = ids(side, qr["reply"], qr["echo"]["reply"])
                me = int(vb[np.argmin(np.abs(tb - t))])
                tr, vr = ids(qr["from"], qr["request"], qr["echo"]["request"])
                again = bool(np.any((tr > t) & (tr <= t + 3 * timeout) & (vr == me)))
                out.append(("link", "its request was sent again") if again else ("none", "the link carried on after it"))
            else:
                out.append(("none", "the link carried on after it"))
        elif kind == "broken":
            orphan = any(t < o <= t + timeout for q in (ex or {}).get("pairs", []) for o in q["orphans"])
            out.append(("capture", "a reply came for it: it was whole on the wire") if orphan else
                       ("none", "the link carried on after it"))
        elif kind == "counter":
            g = in_gap(side, t)
            q, qr = as_request(side, typ), as_reply(side, typ)
            if ref.get("repeat"):
                out.append(("link", "the same one sent again"))
            elif g:
                out.append(g)
            elif q and q["echo"]["request"] == ref["j"]:
                tb, vb = ids(q["to"], q["reply"], q["echo"]["reply"])
                near = (tb >= ref["since"]) & (tb <= t + timeout)
                seen = sum(1 for v in ref["missing"] if np.any(near & (vb == v)))
                out.append(("capture", "their replies are there: the requests were on the wire") if seen == len(ref["missing"]) else
                           ("none", "the link carried on after it"))
            elif qr and qr["echo"]["reply"] == ref["j"]:
                tr, vr = ids(qr["from"], qr["request"], qr["echo"]["request"])
                again = any(np.sum((tr >= ref["since"]) & (tr <= t + 3 * timeout) & (vr == v)) > 1 for v in ref["missing"])
                out.append(("link", "their requests were sent again") if again else
                           ("none", "the link carried on after it"))
            else:
                out.append(("none", "the link carried on after it"))
        elif kind == "unanswered":
            q = ref["q"]
            g = in_gap(q["to"], t)
            out.append(("link", "no reply until the handshake came again") if silent_until_reconnect(q, t) else
                       g if g else ("none", "not sent again: the link carried on"))
        else:                                                # length, unknown
            out.append(("none", "the link carried on after it"))
    return out


# ------------------------------------------------------------------------------------------------ two clocks

CLOCK_MAX = 24 * 3600.0


def _id_columns(r: Dict, typ: int) -> List[Tuple[int, np.ndarray, bool]]:
    """The payload bytes of a type that take many values (an id, a sequence number): (offset, values per message,
    whether it counts up by one like a sequence number)."""
    m = r["messages"]
    idx = np.flatnonzero(m["type"] == typ) if r["typeOffset"] is not None else np.arange(len(m["t"]))
    if len(idx) < 5:
        return []
    pays = [_payload(r, int(i)) for i in idx]
    width = min(min(len(p_) for p_ in pays), 8)
    out = []
    for j in range(width):
        col = np.array([int(p_[j]) for p_ in pays], dtype=np.int64)
        if len(np.unique(col)) >= min(16, max(5, len(col) // 2)):
            out.append((j, col, float(np.mean(np.diff(col) % 256 == 1)) >= 0.8))
    return out


def clock_offset(ra: Dict, rb: Dict) -> Optional[Dict]:
    """CH9 (owner, 2026-11-27: "TX from one file, RX from another"): two loggers' clocks apart. A request type of A and
    a reply type of B carrying the same id byte: every pair of the same id gives a delay (reply - request); when most
    requests share one delay (to 2 ms) that is the clocks' offset plus the reply time. Returns the delay to move B by
    so the fastest of those replies comes 1 ms after its request: {shift, pairs, of, request, reply} - else None."""
    best = None
    ta_all, tb_all = ra["messages"], rb["messages"]
    for x in np.unique(ta_all["type"]).tolist():
        ca = _id_columns(ra, int(x))
        if not ca:
            continue
        tx = ta_all["t"][ta_all["type"] == x] if ra["typeOffset"] is not None else ta_all["t"]
        for y in np.unique(tb_all["type"]).tolist():
            ty_ = tb_all["t"][tb_all["type"] == y] if rb["typeOffset"] is not None else tb_all["t"]
            if not 0.5 <= len(ty_) / len(tx) <= 2:
                continue
            for _j, va, sa in ca:
                for _k, vb, sb in _id_columns(rb, int(y)):
                    d = []
                    for v in np.intersect1d(va, vb):
                        dd = np.subtract.outer(ty_[vb == v], tx[va == v]).ravel()
                        d.append(dd[np.abs(dd) <= CLOCK_MAX])
                    if not d:
                        continue
                    dd = np.concatenate(d)
                    if len(dd) < 5:
                        continue
                    key = np.round(dd / 0.002).astype(np.int64)          # 2 ms bins
                    vals, cnt = np.unique(key, return_counts=True)
                    near = np.abs(key - vals[np.argmax(cnt)]) <= 2       # the peak and its neighbours (jitter)
                    n = int(near.sum())
                    # an echoed sequence number on both sides first: values that merely follow each other (a measured
                    # value after its command) also line up, at their own lag
                    score = (sa and sb, n)
                    if n >= max(5, 0.6 * min(len(tx), len(ty_))) and (best is None or score > best[0]):
                        best = (score, float(dd[near].min()), int(x), int(y), int(min(len(tx), len(ty_))))
    if best is None:
        return None
    (_seq, n), fastest, x, y, of = best
    return {"shift": fastest - 0.001, "pairs": n, "of": of, "request": x, "reply": y}


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
                ev.add("unanswered", u, q["from"], q["request"], "no %s %s" % (q["to"], _hex(q["reply"])), q=q)
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
    # CH9: hardly anything answered in time - two clocks apart? (then every request would read as unanswered)
    clock = None
    if ex is not None and sum(q["replies"] for q in ex["pairs"]) < 0.5 * max(1, sum(q["requests"] for q in ex["pairs"])):
        guess = clock_offset(sides[0][1], sides[1][1])
        if guess and abs(guess["shift"]) > timeout:
            clock = guess
    rows = sorted(ev.rows, key=lambda e: (e[0], KINDS.index(e[1])))
    why = _causes(dict(sides), ex, rows, timeout)
    counts = {k: 0 for k in KINDS}
    by_dir: Dict[str, Dict[str, int]] = {name: {} for name, _r in sides}
    by_cause: Dict[str, Dict[str, int]] = {k: {c: 0 for c in CAUSES} for k in KINDS}
    for (_t, k, d, _ty, _x, _ref), (c, _w) in zip(rows, why):
        counts[k] += 1
        by_dir.setdefault(d, {})[k] = by_dir.get(d, {}).get(k, 0) + 1
        by_cause[k][c] += 1
    t0 = min((float(r["messages"]["t"][0]) for _n, r in sides if r["count"]), default=0.0)
    t1 = max((float(r["messages"]["t"][-1]) for _n, r in sides if r["count"]), default=0.0)
    return {"kinds": list(KINDS), "counts": counts, "byDir": by_dir, "total": len(rows), "span": [t0, t1],
            "events": {"t": [e[0] for e in rows], "kind": [e[1] for e in rows], "dir": [e[2] for e in rows],
                       "type": [e[3] for e in rows], "detail": [e[4] for e in rows],
                       "cause": [c for c, _w in why], "why": [w for _c, w in why]},
            "causes": by_cause, "byCause": {c: sum(by_cause[k][c] for k in KINDS) for c in CAUSES},
            "sides": [{"name": name, "count": r["count"], "header": r["header"], "framing": r["framing"],
                       "typeOffset": r["typeOffset"], "checksum": (r["checksum"] or {}).get("scheme"),
                       "types": [{"type": x["type"], "count": x["count"], "rate": x["rate"]} for x in r["types"]]}
                      for name, r in sides],
            "pairs": pairs, "timeout": timeout, "clock": clock,
            "handshake": [{"t": h["t"], "steps": [{"dir": s["dir"], "type": s["type"], "t": s["t"]} for s in h["steps"]]} for h in hs]}


def count_signal(res: Dict) -> Tuple[np.ndarray, np.ndarray]:
    """The anomalies so far (a step at each one) - the op `messages`, what `anomalies`: they line up with the data
    on the timeline. Starts at 0 at the channel's first message, ends at its last."""
    t = np.asarray(res["events"]["t"], dtype=np.float64)
    t0, t1 = res["span"]
    tt = np.concatenate([[t0], t, [max(t1, t[-1] if len(t) else t1)]])
    yy = np.concatenate([[0.0], np.arange(1, len(t) + 1, dtype=np.float64), [float(len(t))]])
    return tt, yy


# ------------------------------------------------------------------------------------------------ similar files

def compare_files(rows: Sequence[Tuple[str, Dict]]) -> Dict:
    """CH10 (owner, 2026-11-27: "a comparison with other similar files - whether there are anomalies between them - with
    graphical indications, automatically"): the same channel in several recordings [(file, anomalies(...))].

    stands out  a file whose count of a kind is far above the others' (over twice their median and 3 more): what
                happened in that recording and not in the others
    patterns    what differs in the channel itself: a header / checksum / framing not the others', a message type only
                some files have, a type's rate or a reply's mean time more than a fifth / a half off the others'"""
    out_s: List[Dict] = []
    out_p: List[Dict] = []
    if len(rows) < 2:
        return {"standsOut": out_s, "patterns": out_p}
    for k in KINDS:
        vals = [r["counts"][k] for _n, r in rows]
        for i, (name, _r) in enumerate(rows):
            others = vals[:i] + vals[i + 1:]
            med = float(np.median(others))
            if vals[i] > 2 * med and vals[i] >= med + 3:
                out_s.append({"file": name, "kind": k, "value": vals[i], "others": med})
    n = len(rows)
    for side in range(max(len(r["sides"]) for _n, r in rows)):
        have = [(name, r["sides"][side]) for name, r in rows if len(r["sides"]) > side]
        for what in ("header", "checksum", "framing"):
            vals_ = [str(s_[what]) for _n, s_ in have]
            common = max(set(vals_), key=vals_.count)
            for name, s_ in have:
                if str(s_[what]) != common:
                    out_p.append({"file": name, "what": what, "dir": s_["name"], "value": str(s_[what]), "others": common})
        types: Dict[int, Dict[str, Dict]] = {}
        for name, s_ in have:
            for x in s_["types"]:
                types.setdefault(x["type"], {})[name] = x
        for v, by in types.items():
            if len(by) <= n // 2:
                for name in by:
                    out_p.append({"file": name, "what": "type", "dir": have[0][1]["name"], "type": v, "count": by[name]["count"]})
            elif len(by) < len(have):
                for name, _s in have:
                    if name not in by:
                        out_p.append({"file": name, "what": "notype", "dir": have[0][1]["name"], "type": v})
            rates = {name: x["rate"] for name, x in by.items() if x.get("rate")}
            if len(rates) >= 2 and min(x["count"] for x in by.values()) >= 10:
                for name, rt in rates.items():
                    med = float(np.median([q for nm, q in rates.items() if nm != name]))
                    if med > 0 and abs(rt - med) > 0.2 * med:
                        out_p.append({"file": name, "what": "rate", "dir": have[0][1]["name"], "type": v, "value": rt, "others": med})
    lat: Dict[Tuple[str, int, int], Dict[str, float]] = {}
    for name, r in rows:
        for q in r["pairs"]:
            if q.get("mean") is not None and q["replies"] >= 5:
                lat.setdefault((q["from"], q["request"], q["reply"]), {})[name] = q["mean"]
    for (d, x, y), by_ in lat.items():
        if len(by_) < 2:
            continue
        for name, mean in by_.items():
            med = float(np.median([m_ for nm, m_ in by_.items() if nm != name]))
            if med > 0 and abs(mean - med) > 0.5 * med:
                out_p.append({"file": name, "what": "latency", "dir": d, "type": x, "reply": y, "value": mean, "others": med})
    return {"standsOut": out_s, "patterns": out_p}
