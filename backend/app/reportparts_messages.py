"""The report's `[[messages]]` part (app/reportparts.py): the byte streams of the open files - defined in Messages or
found by their names (one signal byte by byte, byte columns, a direction column) - their messages, how often, the
packet make-up, requests and replies of a link. Split out of app/reportparts.py (UX5.5).
"""
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from app.reportparts_base import (fmt, _name, Part, PartError, pct, S, secs, _sig, sig_line, table)


# ------------------------------------------------------------------------------------------------ messages

_COLS = re.compile(r"^(.*?)(?:byte|b|data)[_\[]?(\d+)\]?$", re.I)
_DIR = re.compile(r"^(.*[._ ])?(dir|direction|rxtx|tx_rx|rx_tx|txrx|port|channel|src|source)$", re.I)


def hexb(v: int) -> str:
    return "0x%02X" % int(v)


def defined_streams(store, rids: Sequence[str], defs: Sequence[Dict]) -> List[Tuple[str, str, List[str], Dict]]:
    """The streams the user defined (ws.messageStreams, owner 2026-11-19): only TX, only RX, or both with a direction
    column (txValue = its code for TX; the other values are RX). (rid, name, ids, params) each."""
    out: List[Tuple[str, str, List[str], Dict]] = []
    for d in defs or []:
        src = [str(x) for x in d.get("sources") or []]
        if not src or any(x.split("/")[0] not in rids or not _has(store, x) for x in src):
            continue
        rid = src[0].split("/")[0]
        name = src[0].split("/", 1)[1] if len(src) == 1 else "%s…%s" % (src[0].split("/", 1)[1], src[-1].split("/", 1)[1])
        prm = {k: d[k] for k in ("header", "checksum") if d.get(k)}
        carries = d.get("carries") or "tx"
        dir_ = d.get("dir")
        if carries == "pair" and len(src) == 2:         # two signals: the first TX, the second RX
            out.append((rid, "%s TX" % src[0].split("/", 1)[1], src[:1], prm))
            out.append((rid, "%s RX" % src[1].split("/", 1)[1], src[1:], prm))
        elif carries == "both" and dir_ and _has(store, dir_) and len(src) == 1:
            from svcore import bytestream as bs
            vals = bs.directions(_sig(store, dir_)[1])
            tx = d.get("txValue")
            tx = float(tx) if tx is not None else (vals[0] if vals else 0.0)
            out.append((rid, "%s TX" % name, src + [dir_], {**prm, "dir": tx}))
            if d.get("rxValue") is not None:            # MSG5: the user's value for RX (the column's other values left out)
                out.append((rid, "%s RX" % name, src + [dir_], {**prm, "dir": float(d["rxValue"])}))
                continue
            for v in vals:
                if abs(v - tx) > 1e-9:
                    out.append((rid, "%s RX" % name if len(vals) == 2 else "%s RX %g" % (name, v), src + [dir_], {**prm, "dir": v}))
        else:
            out.append((rid, "%s %s" % (name, "RX" if carries == "rx" else "TX"), src, prm))
    return out


def _has(store, sid: str) -> bool:
    try:
        store.signal(sid)
        return True
    except KeyError:
        return False


def find_streams(store, rids: Sequence[str], defs: Optional[Sequence[Dict]] = None) -> List[Dict]:
    """The byte streams of these files, decoded: the ones the user defined (TX / RX / both with a direction column),
    and in the other signals the ones found by themselves - a byte-by-byte signal (split by a direction column beside
    it), or columns byte_0..byte_N (one message per row). Each: name, rid, ids, params, the decode."""
    from svcore import bytestream as bs
    out: List[Dict] = []
    mine = defined_streams(store, rids, defs or [])
    taken = {i for _r, _n, ids, _p in mine for i in ids}
    for rid, name, ids, prm in mine:
        try:
            out.append({"name": name, "rid": rid, "ids": ids, "params": prm, "r": bs.decode([_sig(store, i) for i in ids], prm)})
        except bs.StreamError as e:
            out.append({"name": name, "rid": rid, "ids": ids, "params": prm, "error": str(e)})
    for rid in rids:
        run = store.get(rid).run
        names = list(run.signals)
        dirs = [n for n in names if _DIR.match(n)]
        groups: Dict[str, List[Tuple[int, str]]] = {}
        for n in names:
            m = _COLS.match(n)
            if m:
                groups.setdefault(m.group(1), []).append((int(m.group(2)), n))
        in_cols: set = set()
        tried: List[Tuple[str, List[str], Dict]] = []
        for pre, cols in groups.items():
            if len(cols) >= 4 and not any(f"{rid}/{n}" in taken for _i, n in cols):
                cols.sort()
                in_cols.update(n for _i, n in cols)
                tried.append(("%s%s…%s" % (pre, cols[0][1][len(pre):], cols[-1][1][len(pre):]), [f"{rid}/{n}" for _i, n in cols], {}))
        for n in names:
            sid = f"{rid}/{n}"
            if n in in_cols or n in dirs or sid in taken or store.is_state(sid):
                continue
            if not bs.is_byte_like(_sig(store, sid)[1]):
                continue
            split = False
            for dn in dirs:
                yd = _sig(store, f"{rid}/{dn}")[1]
                vals = bs.directions(yd)
                if vals:
                    lab = store.labels(f"{rid}/{dn}") or {}
                    for v in vals:
                        tried.append(("%s %s" % (n, lab.get(int(v), lab.get(str(int(v)), "%s=%g" % (dn, v)))), [sid, f"{rid}/{dn}"], {"dir": v}))
                    split = True
                    break
            if not split:
                tried.append((n, [sid], {}))
        for name, ids, prm in tried:
            try:
                r = bs.decode([_sig(store, i) for i in ids], prm)
            except bs.StreamError:
                continue
            out.append({"name": name, "rid": rid, "ids": ids, "params": prm, "r": r})
    return out


def messages(p: Part, rids: List[str], arg: str, o: Dict, defs: Optional[Sequence[Dict]] = None):
    """MSG1: each byte stream's messages - the framing found, a table per type, the order, the gaps; one plot per
    quantity (messages per second by type, the interval by type, the checksum errors) with every stream's lines."""
    from svcore import bytestream as bs
    st, S_ = p.store, p.S
    force = {k: o[k] for k in ("header", "length", "type", "checksum") if k in o}
    streams = find_streams(st, rids, defs)
    for s_ in [x for x in streams if x.get("error")]:
        p.say("⚠ **%s**: %s" % (s_["name"], s_["error"]))
    streams = [x for x in streams if not x.get("error")]
    if force:                                            # forced framing: decode the byte-like signals again with it
        again = []
        for s_ in streams:
            try:
                again.append({**s_, "r": bs.decode([_sig(st, i) for i in s_["ids"]], {**s_["params"], **force})})
            except bs.StreamError as e:
                raise PartError("%s: %s" % (s_["name"], e))
        streams = again
    flts = [x.strip() for x in arg.lower().split(",") if x.strip()]     # MSG3: "tx_byte, rx_byte" - either
    if flts:
        streams = [s_ for s_ in streams if any(f in s_["name"].lower() for f in flts)]
    if not streams:
        p.say("*%s*" % S_["none_msg"])
        return
    rate_lines: List[dict] = []
    int_lines: List[dict] = []
    err_lines: List[dict] = []
    seq_lines: List[Tuple[dict, float, float]] = []
    k = 0
    for s_ in streams:
        r, name = s_["r"], s_["name"]
        file = " (%s)" % _name(st, s_["rid"]) if len(rids) > 1 else ""
        cs = r["checksum"]
        cst = S_["msg_cs"].format(s=cs["scheme"], e=r["errors"]) if cs else S_["msg_nocs"]
        lost = S_["msg_lost"].format(r=r["resyncs"], o=r["outside"]) if r["resyncs"] or r["outside"] else ""
        p.say(S_["msg_intro"].format(name=name, file=file, n=r["count"], d=secs(r["duration"]), bytes=r["bytes"], h=r["header"], cs=cst) + lost)
        p.say(S_["msg_struct"])
        p.say(table(S_["msg_struct_head"], structure(r, S_)))
        rows = [[hexb(x["type"]) if r["typeOffset"] is not None else "—", str(x["count"]), pct(x["share"]),
                 ", ".join(str(v) for v in x["lengths"]), fmt(x["rate"]), secs(x["period"]),
                 "—" if x["jitter"] is None else "0" if x["jitter"] < 1e-9 else "%.3g" % (x["jitter"] * 1000), secs(x["maxInterval"]), secs(x["first"]), secs(x["last"]),
                 str(x["errors"]) if cs else "—"] for x in r["types"]]
        p.say(table(S_["msg_head"], rows))
        od = r["order"]
        if od["period"]:
            seq = " ".join(hexb(v) for v in od["sequence"][:24]) + (" …" if len(od["sequence"]) > 24 else "")
            p.say(S_["msg_order"].format(p=od["period"], seq=seq, f=pct(od["fit"])))
        elif od["transitions"]:
            p.say(S_["msg_trans"].format(list=", ".join("%s → %s (%d)" % (hexb(x["from"]), hexb(x["to"]), x["count"]) for x in od["transitions"][:6])))
        if r["typeOffset"] is not None and r["count"] > 1:
            ty = r["messages"]["type"]
            k_ = min(40, len(ty))
            p.say(S_["msg_seq"].format(n=k_, t=secs(float(r["messages"]["t"][0])), list=" ".join(hexb(v) for v in ty[:k_])))
        if r["gaps"]:
            p.say(S_["msg_gaps"].format(list=", ".join(S_["msg_gap"].format(dt=secs(g["dt"]), a=secs(g["from"])) for g in r["gaps"])))
        label = name + file
        if r["errors"]:
            p.hl("warn", 5 + r["errors"], S_["msg_hl_err"].format(name=label, e=r["errors"], n=r["count"]))
        for g in r["gaps"][:2]:
            p.hl("warn", 3 + g["dt"], S_["msg_hl_gap"].format(name=label, dt=secs(g["dt"]), a=secs(g["from"])))
        if r["resyncs"]:
            p.hl("info", 1 + r["resyncs"], S_["msg_hl_resync"].format(name=label, r=r["resyncs"]))
        p.hl("info", 0.5, S_["msg_hl"].format(name=label, n=r["count"], k=len(r["types"]), h=r["header"]))
        m = r["messages"]
        t = np.asarray(m["t"], dtype=np.float64)
        if len(t) < 2:
            continue
        edges = np.arange(math.floor(t[0]), math.ceil(t[-1]) + 1.0, 1.0)
        if len(edges) < 2:
            edges = np.array([t[0], t[0] + 1.0])
        for x in r["types"][:8]:
            sel = m["type"] == x["type"] if r["typeOffset"] is not None else np.ones(len(t), dtype=bool)
            tt = t[sel]
            lab = "%s %s" % (name, hexb(x["type"])) if r["typeOffset"] is not None else name
            cnt, _e = np.histogram(tt, edges)
            rate_lines.append(sig_line(p.series(lab, edges[:-1] + 0.5, cnt.astype(np.float64)), lab, k))
            if len(tt) > 1:
                int_lines.append(sig_line(p.series(lab + " Δt", tt[1:], np.diff(tt)), lab, k))
            k += 1
        if r["typeOffset"] is not None:
            span = min(2.0, float(t[-1] - t[0]))
            seq_lines.append((sig_line(p.series(name + " type", t, m["type"].astype(np.float64)), name, len(seq_lines), state=True), t[0], span))
        if cs and r["errors"]:
            err_lines.append(sig_line(p.series(name + " errors", t, np.cumsum(~m["ok"]).astype(np.float64)), name, len(err_lines)))
    lat_lines = links(p, streams, rids)
    anomaly_table(p, streams, rids)
    if o.get("table"):
        return
    if lat_lines:
        p.plot(S_["msg_lat"], lat_lines, caption=S_["msg_lat_cap"])
    if seq_lines:
        t0 = min(x[1] for x in seq_lines)
        span = max(x[2] for x in seq_lines)
        p.plot(S_["msg_seq_plot"].format(s="%g" % span), [x[0] for x in seq_lines], rng=[float(t0), float(t0 + span)], caption=S_["msg_seq_cap"])
    if rate_lines:
        p.plot(S_["msg_rate"], rate_lines, caption=S_["msg_rate_cap"])
    if int_lines:
        p.plot(S_["msg_int"], int_lines, caption=S_["msg_int_cap"])
    if err_lines:
        p.plot(S_["msg_err"], err_lines)


def _times(ts: Sequence[float], n: int = 12) -> str:
    return ", ".join(secs(x) for x in list(ts)[:n]) + (" …" if len(ts) > n else "")


def links(p: Part, streams: List[Dict], rids: Sequence[str]) -> List[dict]:
    """Both directions of a link (two streams of one file: TX and RX, or one signal split by its direction): which
    message answers which, the latency, what went unanswered or was sent again, the handshake and reconnects."""
    from svcore import bytestream as bs
    S_ = p.S
    lines: List[dict] = []
    by: Dict[str, List[Dict]] = {}
    for s_ in streams:
        by.setdefault(s_["rid"], []).append(s_)
    for rid, ss in by.items():
        if len(ss) != 2:
            continue
        # the side that sends (TX) first
        ss = sorted(ss, key=lambda x: (0 if re.search(r"tx|send|out|up", x["name"], re.I) else 1, x["name"]))
        a, b = ss[0]["name"], ss[1]["name"]
        e = bs.exchange(ss[0]["r"], ss[1]["r"], (a, b))
        hs = e["handshake"]
        if hs:
            seq = lambda h: " → ".join("%s %s" % (x["dir"], hexb(x["type"])) for x in h["steps"])
            p.say(S_["msg_hs"].format(t=secs(hs[0]["t"]), seq=seq(hs[0])))
            for h in hs[1:]:
                p.say(S_["msg_hs_again"].format(t=secs(h["t"]), seq=seq(h)))
                p.hl("warn", 4, S_["msg_hl_reconnect"].format(a=a, b=b, t=secs(h["t"])))
        if not e["pairs"]:
            p.say(S_["msg_link_none"].format(a=a, b=b))
            continue
        p.say(S_["msg_link"].format(a=a, b=b, to=secs(e["timeout"])))
        rows = []
        for q in e["pairs"]:
            lt = q["latency"] or {}
            ms = lambda v: "—" if v is None else "%.3g" % (v * 1000)
            rows.append(["%s %s" % (q["from"], hexb(q["request"])), "%s %s" % (q["to"], hexb(q["reply"])),
                         S_["msg_by_id"].format(j=q["echo"]["request"]) if q["echo"] else S_["msg_by_next"],
                         str(q["requests"]), str(q["replies"]), str(len(q["unanswered"])), str(len(q["retries"])),
                         ms(lt.get("mean")), ms(lt.get("p95")), ms(lt.get("max")), secs(lt.get("tmax")), str(len(q["orphans"]))])
        p.say(table(S_["msg_link_head"], rows))
        for k, q in enumerate(e["pairs"]):
            req = hexb(q["request"])
            if q["unanswered"]:
                p.say(S_["msg_unans"].format(req=req, n=len(q["unanswered"]), list=_times(q["unanswered"])))
                p.hl("warn", 4 + len(q["unanswered"]), S_["msg_hl_unans"].format(a=a, b=b, n=len(q["unanswered"]), m=q["requests"] - len(q["retries"]), req=req))
            if q["retries"]:
                p.say(S_["msg_retry"].format(req=req, list=_times(q["retries"])))
                p.hl("info", 2 + len(q["retries"]), S_["msg_hl_retry"].format(a=a, b=b, req=req, n=len(q["retries"])))
            lt = q["latency"]
            if lt and q["replies"] >= 5:
                p.hl("info", 1, S_["msg_hl_lat"].format(a=a, b=b, req=req, mean="%.3g" % (lt["mean"] * 1000), max="%.3g" % (lt["max"] * 1000), t=secs(lt["tmax"])))
                lab = "%s → %s" % (req, hexb(q["reply"]))
                if len(rids) > 1:
                    lab = "%s: %s" % (_name(p.store, rid), lab)
                lines.append(sig_line(p.series(lab + " latency", q["t"], q["lat"]), lab, len(lines)))
    return lines


def channels(streams: List[Dict]) -> List[Tuple[str, str, List[Tuple[str, Dict]]]]:
    """The channels of these streams: a file's two streams are one link (TX first, as `links`), else each stream alone.
    (rid, name, [(direction, decode)]) each."""
    by: Dict[str, List[Dict]] = {}
    for s_ in streams:
        by.setdefault(s_["rid"], []).append(s_)
    out = []
    for rid, ss in by.items():
        if len(ss) == 2:
            ss = sorted(ss, key=lambda x: (0 if re.search(r"tx|send|out|up", x["name"], re.I) else 1, x["name"]))
            out.append((rid, "%s ↔ %s" % (ss[0]["name"], ss[1]["name"]), [("TX", ss[0]["r"]), ("RX", ss[1]["r"])]))
        else:
            out += [(rid, s_["name"], [("TX", s_["r"])]) for s_ in ss]
    return out


def anomaly_table(p: Part, streams: List[Dict], rids: Sequence[str]):
    """CH4: the anomalies of each channel (svcore/channel.py) - a row per file and channel, a column per kind found;
    with several files, each cell against the first file's (the same channel in similar recordings)."""
    from svcore.channel import KINDS, anomalies
    S_ = p.S
    rows = [(rid, name, anomalies(sides)) for rid, name, sides in channels(streams)]
    if not rows:
        return
    kinds = [k for k in KINDS if any(r["counts"][k] for _i, _n, r in rows)]
    if not kinds:
        p.say(S_["msg_anom_none"])
        return
    files = len({rid for rid, _n, _r in rows}) > 1
    base = rows[0][2]
    def cell(v: int, b: int, first: bool) -> str:
        return str(v) if first or not files or v == b else "%d (%+d)" % (v, v - b)
    out = []
    for k_, (rid, name, r) in enumerate(rows):
        out.append([_name(p.store, rid), name, cell(r["total"], base["total"], k_ == 0)]
                   + [cell(r["counts"][k], base["counts"][k], k_ == 0) for k in kinds])
    p.say(S_["msg_anom_files"].format(n=len({rid for rid, _n, _r in rows}), f=_name(p.store, rows[0][0])) if files else S_["msg_anom"])
    p.say(table(S_["msg_anom_head"] + [S_["msg_anom_k"][k] for k in kinds], out))


def structure(r: Dict, S_: Dict[str, Any]) -> List[List[str]]:
    """The packet's parts: the fixed header, the length / type bytes, the payload (per type), the checksum."""
    from svcore.bytestream import SCHEMES_1
    F, W = S_["msg_f"], S_["msg_w"]
    rule, toff, cs = r["rule"], r["typeOffset"], r["checksum"]
    k = (1 if cs["scheme"] in SCHEMES_1 else 2) if cs else 0
    rows = [[F["header"], "0–1", W["header"].format(h=r["header"])]]
    fields = []
    if rule["how"] == "length":
        fields.append((rule["off"], [F["length"], str(rule["off"]), W["length"].format(a=rule["add"])]))
    if toff is not None:
        kinds = ", ".join(hexb(x["type"]) for x in sorted(r["types"], key=lambda x: x["type"]))
        fields.append((toff, [F["type"], str(toff), W["type_len" if rule["how"] == "type" else "type"].format(n=len(r["types"]), list=kinds)]))
    fields.sort()
    rows += [f for _o, f in fields]
    start = max([1] + [o for o, _f in fields]) + 1
    lens = sorted({L for x in r["types"] for L in x["lengths"]})
    if len(lens) == 1:
        rows.append([F["payload"], "%d–%d" % (start, lens[0] - k - 1), W["payload_fixed"].format(n=lens[0] - k - start)])
    else:
        per = ", ".join(S_["msg_per"].format(t=hexb(x["type"]) if toff is not None else "?", n=x["lengths"][0] - k - start)
                        for x in sorted(r["types"], key=lambda x: x["type"]))
        rows.append([F["payload"], "%d…" % start, W["payload"].format(list=per)])
    if cs:
        a = 2 if cs["over"].startswith("without") else 0
        rows.append([F["checksum"], S_["msg_last"][k - 1], W["checksum"].format(s=cs["scheme"], a=a)])
    else:
        rows.append([F["checksum"], "—", W["none"]])
    if rule["how"] == "fixed":
        rows.append(["", "", W["fixed"].format(n=rule["len"])])
    return rows


def byte_streams(store, rid: str, defs: Optional[Sequence[Dict]] = None) -> List[str]:
    """The names of a file's signals that are byte streams (the overview leaves their statistics out)."""
    out: List[str] = []
    for s_ in find_streams(store, [rid], defs):
        out += [i.split("/", 1)[1] for i in s_["ids"]]
    return out
