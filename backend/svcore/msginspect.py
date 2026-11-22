"""MSG4 (owner, 2026-11-21): the guided way from a raw byte signal to the variables in its messages - "the app should
recognise identical patterns that can be the header or the footer and propose the message's template; the user must be
able to define the template, and it must be clear how" (the demo film showed it, but alone it was not clear how).

`inspect` is what the Messages panel's steps 2 and 3 show (backend/app/routes/messages.py /api/messages/inspect):

  patterns   the byte sequences (2-4 bytes) that recur through the stream - each with how often, how regularly (the
             share of gaps that are the usual one) and the role it plays in the structure (header / footer) - the
             candidates the user picks from
  structure  the user's, else the one proposed (protocol.suggest) - and `suggested`
  frames     the first messages by that structure: their bytes in hex, each byte's role (header, length, type,
             field, checksum, footer, payload = not yet a field), the fields' spans, and each field's decoded value -
             so a wrong offset, byte order or scale shows at once, before the recording is made
  summary    the whole stream by the structure: messages, bad (checksum / footer), unknown types, bytes outside
             (every message counts - CLAUDE.md; nothing sampled)
  head       the stream's first bytes, for a stream no structure frames yet (a click there sets the header)
"""
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from svcore import bytestream as bs
from svcore import protocol as P

ROLE_ORDER = ("header", "length", "type", "field", "checksum", "footer", "payload")


def patterns(raw: np.ndarray, top: int = 6, gaps: Optional[np.ndarray] = None) -> List[Dict[str, Any]]:
    """Byte sequences of 2..4 bytes that recur, best first: score = count x regularity (a header comes every message,
    at the same distance when the messages are one length). A longer sequence that is (nearly) always there with a
    shorter one at its start replaces it - "AA 55 10" rather than "AA 55" when the 10 always follows (a footer is
    then often shown with the next header after it: "0D 0A A5 5A")."""
    b = np.asarray(raw, dtype=np.uint8)
    n = len(b)
    if n < 16:
        return []
    pause = gaps if gaps is not None and len(gaps) == n else None
    found: Dict[bytes, Dict[str, Any]] = {}
    for k in (2, 3, 4):
        if n < k + 4:
            continue
        code = np.zeros(n - k + 1, dtype=np.uint64)
        for j in range(k):
            code = code * np.uint64(256) + b[j:n - k + 1 + j].astype(np.uint64)
        vals, counts = np.unique(code, return_counts=True)
        order = np.argsort(counts)[::-1][:12]
        for i in order:
            c = int(counts[i])
            if c < 4:
                break
            seq = int(vals[i]).to_bytes(k, "big")
            if len(set(seq)) == 1 and k > 2:
                continue                                     # 00 00 00: padding, not a pattern
            at = np.flatnonzero(code == vals[i])
            gaps = np.diff(at)
            gaps = gaps[gaps >= k]                            # overlaps of a repeated byte are one place
            if len(gaps) < 3:
                continue
            g, share = bs._mode(gaps)
            found[seq] = {"hex": seq.hex(" ").upper(), "bytes": k, "count": int(len(gaps) + 1), "every": int(g),
                          "regular": round(float(share), 3), "first": int(at[0])}
            # MSG6: right after a pause (a message's start) or right before one (its end) - when the stream has pauses
            bt = bs.by_time(pause, at, k)
            if pause is not None:                    # a pause inside it: the end of one message and the start of the next
                inside = np.zeros(len(at), dtype=bool)
                for j in range(1, k):
                    inside |= pause[np.minimum(at + j, n - 1)]
                found[seq]["across"] = float(np.mean(inside))
            if bt:
                found[seq].update(afterPause=round(bt[0], 3), beforePause=round(bt[1], 3),
                                  time="start" if bt[0] >= 0.6 and bt[0] > bt[1] + 0.3 else "end" if bt[1] >= 0.6 and bt[1] > bt[0] + 0.3 else None)
    # MSG6: a sequence across a pause is two messages' bytes, not a pattern of one
    found = {s: v for s, v in found.items() if v.pop("across", 0.0) < 0.5}
    # a sequence that its longer extension (almost) always continues: keep the longer one
    for seq in sorted(found, key=len):
        for longer in [s for s in found if len(s) > len(seq) and s.startswith(seq)]:
            if found[longer]["count"] >= 0.9 * found[seq]["count"]:
                found[seq]["drop"] = True
                break
    out = [v for v in found.values() if not v.get("drop")]
    for v in out:
        v["score"] = round(v["count"] * (0.25 + v["regular"]) * math.sqrt(v["bytes"]), 2)
    out.sort(key=lambda v: -v["score"])
    return out[:top]


def _roles(L: int, proto: Dict, m: Optional[Dict]) -> Tuple[List[str], List[Optional[int]]]:
    """Each byte's role in a frame of length L, and the field index it belongs to (None when not a field)."""
    hl = len(bytes.fromhex(re.sub(r"[^0-9a-fA-F]", "", str(proto.get("header") or ""))))
    ft = len(bytes.fromhex(re.sub(r"[^0-9a-fA-F]", "", str(proto.get("footer") or ""))))
    cs = proto.get("checksum")
    ck = 0 if not cs else (1 if cs.get("scheme") in bs.SCHEMES_1 else 2)
    role = ["payload"] * L
    fld: List[Optional[int]] = [None] * L
    for j, f in enumerate((m or {}).get("fields") or []):
        size = P.field_size(f)
        for x in range(int(f.get("offset", 0)), min(L, int(f.get("offset", 0)) + size)):
            role[x], fld[x] = "field", j
    for x in range(min(hl, L)):
        role[x] = "header"
    lo = (proto.get("length") or {}).get("offset")
    if lo is not None and lo < L:
        role[int(lo)] = "length"
    to = (proto.get("type") or {}).get("offset")
    if to is not None and to < L:
        role[int(to)] = "type"
    for x in range(max(0, L - ft - ck), max(0, L - ft)):
        role[x] = "checksum"
    for x in range(max(0, L - ft), L):
        role[x] = "footer"
    for x in range(L):
        if role[x] != "field":
            fld[x] = None
    return role, fld


def _binary(t: np.ndarray, raw: np.ndarray, proto: Dict, n: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    data = raw.tobytes()
    toff = (proto.get("type") or {}).get("offset")
    by_id = {int(m["id"]) if toff is not None else 0: m for m in proto["messages"]}
    every, report = P.frames_binary(data, proto)                  # the whole stream: every message counted
    counts: Dict[str, int] = {}
    for _p, _L, mid, status in every:
        if status == "ok":
            nm = str(by_id[mid].get("name") or mid)
            counts[nm] = counts.get(nm, 0) + 1
    frames = []
    for p, L, mid, status in every[:n]:
        m = by_id.get(mid)
        role, fld = _roles(L, proto, m)
        values: List[Any] = []
        for f in (m or {}).get("fields") or []:
            if f.get("type") == "ascii":                 # MSG8: its text
                values.append(P.ascii_values(raw, np.asarray([p], dtype=np.int64), f)[2][0])
                continue
            try:
                v = float(P._value(raw, np.asarray([p], dtype=np.int64), f)[0]) if p + int(f.get("offset", 0)) < len(raw) else math.nan
            except Exception:                                   # a field past the frame's end: said, not raised
                v = math.nan
            values.append(None if not math.isfinite(v) else v)
        frames.append({"t": float(t[p]), "at": int(p), "len": int(L), "id": int(mid), "message": str((m or {}).get("name") or ""),
                       "status": status, "bytes": [int(x) for x in data[p:p + L]], "roles": role, "fields": fld, "values": values})
    summary = {"messages": int(report["frames"]), "bad": int(report["bad"]), "outside": int(report["outside"]),
               "unknown": {str(k): int(v) for k, v in report["unknown"].items()}, "byMessage": counts, "bytes": int(len(raw))}
    return frames, summary


def _text(t: np.ndarray, raw: np.ndarray, proto: Dict, n: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    text = raw.tobytes().decode("latin-1")
    start, sep = str(proto.get("start") or "$"), str(proto.get("sep") or ",")
    by_id = {str(m["id"]).upper(): m for m in proto["messages"]}
    all_ = P.sentences(text, start, proto.get("end") or None)
    counts: Dict[str, int] = {}
    bad = 0
    unknown: Dict[str, int] = {}
    shown: List[Dict[str, Any]] = []
    for pos, line in all_:
        ok = not (proto.get("checksum") == "nmea" and P.nmea_ok(line) is False)
        parts = line[len(start):].split("*")[0].split(sep)
        sid = parts[0].strip().upper()
        m = by_id.get(sid) or by_id.get(sid[2:])
        if not ok:
            bad += 1
        elif m is None:
            unknown[sid] = unknown.get(sid, 0) + 1
        else:
            nm = str(m.get("name") or m["id"])
            counts[nm] = counts.get(nm, 0) + 1
        if len(shown) < n:
            values: List[Any] = []
            for f in (m or {}).get("fields") or []:
                ix = int(f["index"])
                s = parts[ix] if ix < len(parts) else ""
                if f.get("type") == "text":
                    values.append(s.strip() or None)
                    continue
                hemi = f.get("hemi")
                v = P._num(s, f.get("type", "number"), parts[int(hemi)] if hemi is not None and int(hemi) < len(parts) else "")
                v = v * float(f.get("scale", 1) or 1) + float(f.get("add", 0) or 0)
                values.append(None if not math.isfinite(v) else v)
            shown.append({"t": float(t[min(pos, len(t) - 1)]) if len(t) else 0.0, "at": int(pos), "text": line, "parts": parts,
                          "id": sid, "message": str((m or {}).get("name") or ""),
                          "status": "bad" if not ok else ("ok" if m is not None else "unknown"), "values": values})
    summary = {"messages": int(sum(counts.values())), "bad": bad, "outside": 0, "unknown": unknown, "byMessage": counts,
               "bytes": int(len(raw))}
    return shown, summary


def inspect(signals: Sequence[Tuple[np.ndarray, np.ndarray]], params: Optional[Dict] = None,
            structure: Optional[Dict] = None, n: int = 10) -> Dict[str, Any]:
    """What steps 2 and 3 show: the patterns, the structure (given or proposed), the first frames with each byte's role
    and each field's value, and the whole stream's counts. Never raises for a stream it cannot frame: says why."""
    params = params or {}
    t, raw = P.stream_of(signals, params)
    out: Dict[str, Any] = {"bytes": int(len(raw)), "head": [int(x) for x in raw[:64]],
                           "text": bool(P.looks_text(raw)), "patterns": [], "frames": [], "summary": None}
    if not out["text"]:
        g = bs.pauses(t)
        out["patterns"] = patterns(raw, gaps=g)
        out["pauses"] = g is not None              # MSG6: the stream's pauses tell a message's start from its end
    suggested = False
    if not structure:
        try:
            structure = P.suggest(signals, params)
            suggested = True
        except (bs.StreamError, P.ProtocolError) as e:
            out["error"] = str(e)
            return out
    try:
        proto = P.check(dict(structure))
    except P.ProtocolError as e:
        out.update(structure=structure, suggested=suggested, error=str(e))
        return out
    out.update(structure=proto, suggested=suggested)
    frames, summary = (_text if proto["kind"] == "text" else _binary)(t, raw, proto, n)
    out.update(frames=frames, summary=summary)
    hdr = re.sub(r"[^0-9a-fA-F]", "", str(proto.get("header") or "")).upper()
    ftr = re.sub(r"[^0-9a-fA-F]", "", str(proto.get("footer") or "")).upper()
    for p in out["patterns"]:
        h = p["hex"].replace(" ", "")
        # the header itself; a message's start (the header and the bytes that always follow it: a type, a length);
        # the footer; else a pattern the structure does not use yet
        p["role"] = ("header" if hdr and (h == hdr or hdr.startswith(h)) else "start" if hdr and h.startswith(hdr)
                     else "footer" if ftr and (ftr.endswith(h) or h.startswith(ftr)) else "")
    # the tail of a message's start ("90 A0 0C" inside "EB 90 A0 0C", always together) says nothing more: left out -
    # never the header or the footer themselves
    pats = out["patterns"]
    out["patterns"] = [p for p in pats if p["role"] or not any(
        q is not p and q["bytes"] > p["bytes"] and q["hex"].endswith(p["hex"]) and q["count"] >= 0.9 * p["count"] for q in pats)]
    if not frames:
        out["error"] = "No message matches the structure: check the header and how long a message is."
    return out
