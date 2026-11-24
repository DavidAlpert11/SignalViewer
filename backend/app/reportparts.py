"""RE2 (owner, 2026-11-19): the report's ready-made parts - `[[tracking]]`, `[[navigation]]`, `[[states]]`,
`[[trajectory]]`, `[[differences]]`, `[[summary]]`. Each looks at the open files, finds what it needs by the
signals' names (commanded / measured pairs, map objects, state signals, the same signal in several files),
computes on every sample (svcore/reportparts.py, svcore/objcompare.py) and writes ordinary Markdown - a sentence,
tables, plots - that replaces the part's marker before the document is parsed. So the page, the PDF and Word
draw it with the code that draws everything else, and *Expand to text* hands the same Markdown to the user.

Generic on purpose: nothing here knows a log format; the names' rules are the app's (desired.ts, objectDetect.ts)
and a part that finds nothing says so in one line.
"""
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from svcore import reportparts as rp
from svcore.docfields import format_value
from app.reportparts_base import (dist, fmt, KNOWN, _label, _name, options, PALETTE, Part, PartError, pct, _runs, S,
                                  secs, _sig, sig_line, table, UNITS)
from app.reportparts_messages import (byte_streams, find_streams, links, messages)

# ------------------------------------------------------------------------------------------------ tracking

def tracking(p: Part, rids: List[str], arg: str, o: Dict):
    st, S_ = p.store, p.S
    ids = [f"{rid}/{n}" for rid in rids for n in st.get(rid).run.signals]
    pairs = rp.setpoint_pairs(ids)
    flt = arg.strip().lower()
    if flt:
        pairs = [q for q in pairs if flt in q["setpoint"].lower() or flt in q["measured"].lower()]
    for sk in o.get("skip", []):
        pairs = [q for q in pairs if sk.lower() not in q["setpoint"].lower() and sk.lower() not in q["measured"].lower()]
    if not pairs:
        p.say("*%s*" % S_["none_trk"])
        return
    tol, outside = o.get("tol"), o.get("outside", 0.0)
    rows = []
    for q in pairs:
        r = rp.tracking(_sig(st, q["setpoint"]), _sig(st, q["measured"]), q["measured"].split("/", 1)[1], tol, st.is_state(q["setpoint"]))
        rows.append((q, r))
    rows.sort(key=lambda x: -(x[1].get("score") or 0))
    p.say(S_["trk_intro"].format(n=len(pairs)))
    head = ([S_["file"]] if len(rids) > 1 else []) + S_["trk_head"] + ([h.format(tol=fmt(tol)) for h in S_["trk_tol"]] if tol else [])
    body = []
    for q, r in rows:
        if r.get("error"):
            continue
        fails = tol is not None and (r.get("outside") or 0) > outside * 100
        sett = r.get("settling")
        settle = S_["not_settled"].format(n=r["unsettled"]) if r.get("steps") and sett is None else secs(sett) if r.get("steps") else "—"
        row = ([_name(st, q["measured"].split("/")[0])] if len(rids) > 1 else []) + [
            rp.bare(q["setpoint"].split("/", 1)[1]), rp.bare(q["measured"].split("/", 1)[1]), fmt(r["rms"]), fmt(r["max"]), secs(r["tmax"]),
            fmt(r["bias"]), secs(r.get("delay")), str(r.get("steps") or 0),
            ("%.0f %%" % r["overshoot"]) if r.get("steps") else "—", settle]
        if tol:
            row += ["%.2g %%" % r["outside"], S_["fail"] if fails else S_["pass"]]
        body.append(row)
        m, s = rp.bare(q["measured"].split("/", 1)[1]), rp.bare(q["setpoint"].split("/", 1)[1])
        if len(rids) > 1:
            m = "%s: %s" % (_name(st, q["measured"].split("/")[0]), m)
        if fails:
            p.hl("fail", 10 + (r.get("outside") or 0), S_["trk_hl_fail"].format(m=m, tol=fmt(tol), out="%.2g" % r["outside"]))
        else:
            p.hl("warn" if r["score"] > 0.1 else "info", r["score"], S_["trk_hl"].format(m=m, s=s, rms=fmt(r["rms"]), max=fmt(r["max"]), t=secs(r["tmax"])))
    p.say(table(head, body))
    if o.get("table"):
        return
    for k, (q, r) in enumerate([x for x in rows if not x[1].get("error")][:o.get("top", 4)]):
        m = q["measured"].split("/", 1)[1]
        cap = S_["trk_cap"].format(max=fmt(r["max"]), t=secs(r["tmax"]), rms=fmt(r["rms"]))
        if r.get("steps"):
            cap += S_["trk_cap_steps"].format(n=r["steps"], o="%.0f" % r["overshoot"], to=secs(r["tOvershoot"]))
        e = p.series(S_["error"], *r["e"])
        p.plot(S_["trk_plot"].format(m=_label(st, q["measured"], rids)),
               [sig_line(q["measured"], _label(st, q["measured"], rids), 0),
                sig_line(q["setpoint"], _label(st, q["setpoint"], rids), 1, style="dash"),
                sig_line(e, S_["error"], 3, axis="right", width=1)], caption=cap)
        del r["e"]


# ------------------------------------------------------------------------------------------------ objects

def detect_objects(store, rids: Sequence[str]) -> List[dict]:
    """The addable map objects of these files, best first ("file:name" where two files share a name)."""
    from svcore.objects import addable, detect
    cands = []
    for rid in rids:
        lr = store.get(rid)
        d = detect([(f"{rid}/{n}", n) for n in lr.run.signals], rid, lr.name)
        cands += [dict(c) for c in d["candidates"] if addable(c)]
    names = [c["name"] for c in cands]
    for c in cands:
        if len(rids) > 1 and names.count(c["name"]) > 1:
            c["name"] = "%s:%s" % (store.get(c["runId"]).name, c["name"])
    return cands


GUESS = {"truth": 0, "receiver": 1, "navigation": 2, "other": 3}


def guess_reference(objs: Sequence[dict]) -> Optional[dict]:
    """The reference an engineer would take: the truth (simulation / model), else a receiver (GPS), else the first."""
    return min(objs, key=lambda c: GUESS.get(c.get("cls", "other"), 3)) if objs else None


def navigation(p: Part, rids: List[str], arg: str, o: Dict):
    """Each object against the reference. Several files and no reference chosen: inside each file, against its own
    guessed reference (a truth in run A is not the reference of run B's estimate)."""
    st, S_ = p.store, p.S
    want = o.get("ref") or arg.strip()
    groups = [rids] if want or len(rids) < 2 else [[r] for r in rids]
    done = False
    acc: Dict[Tuple[str, str], List] = {}
    refs: List[str] = []
    for g in groups:
        objs = detect_objects(st, g)
        if len(objs) < 2:
            continue
        if want:
            ref = next((c for c in objs if c["name"].lower() == want.lower()), None) or next((c for c in objs if want.lower() in c["name"].lower()), None)
            if ref is None:
                raise PartError(S_["no_ref"].format(r=want, list=", ".join(c["name"] for c in objs)))
            why = S_["nav_chosen"]
        else:
            ref = guess_reference(objs)
            assert ref is not None                       # two objects or more
            why = S_["nav_guess"].format(cls=ref["cls"])
        _navigation(p, objs, ref, why, o, st.get(g[0]).name if len(groups) > 1 else "", acc)
        refs.append(ref["name"])
        done = True
    if not done:
        p.say("*%s*" % S_["none_nav"])
        return
    if not o.get("table"):
        # one plot per axis (owner: every component on one plot cannot be read): in it every compared object - of
        # every file, so two runs' errors are seen together; horizontal / vertical are left to the tables
        for (q, c), lines in acc.items():
            # the noisiest underneath, the smooth ones on top - a receiver's noise must not hide an estimate's error
            lines = sorted(lines, key=lambda x: -float(np.nanstd(np.diff(np.asarray(x[1][1], dtype=np.float64)))) if len(x[1][1]) > 2 else 0.0)
            p.plot(S_["nav_axis"].format(c=c, q=S_["qty"][q], u=UNITS[q], ref=" / ".join(dict.fromkeys(refs))),
                   [sig_line(p.series("%s %s" % (lab, c), *ts), lab, k) for k, (lab, ts) in enumerate(lines)])


def _navigation(p: Part, objs: List[dict], ref: dict, why: str, o: Dict, file: str, acc: Dict[Tuple[str, str], List]):
    from svcore.objcompare import compare
    st, S_ = p.store, p.S
    what = o.get("what") or ["position", "velocity", "attitude"]
    res = compare(lambda sid: _sig(st, sid), objs, ref["name"], None, what, "ned")
    named = (lambda n: "%s: %s" % (file, n)) if file else (lambda n: n)
    p.say(S_["nav_intro"].format(ref=named(ref["name"]), why=why, n=len(objs) - 1))
    for q in what:
        rows = [r for r in res["stats"] if r["qty"] == q]
        if not rows:
            continue
        u = UNITS[q]
        p.say("**%s** [%s]" % (S_["qty"][q], u))
        p.say(table(S_["nav_head"], [[named(r["object"]), r["comp"], fmt(r["rms"]), fmt(r["mean"]), fmt(r["p95_abs"]), fmt(r["max_abs"]), secs(r["t_max_abs"])] for r in rows]))
        # a highlight per object (its largest component); the worst object of this quantity plotted
        by: Dict[str, List[dict]] = {}
        for r in rows:
            by.setdefault(r["object"], []).append(r)
        for obj, rs in by.items():
            w = max(rs, key=lambda r: r["max_abs"] or 0)
            p.hl("info", 0.5 + (w["p95_abs"] or 0) / (1 + abs(w["p95_abs"] or 0)) * 0.1,
                 S_["nav_hl"].format(o=named(obj), q=S_["qty"][q], max=fmt(w["max_abs"]), u=u, t=secs(w["t_max_abs"]), p95=fmt(w["p95_abs"])))
        # the plots come after every file's tables (navigation): one plot per axis, each object a line
        obs = sorted(by, key=lambda ob: -max(r["rms"] or 0 for r in by[ob]))[:o.get("top", 4)]
        for c in [c for c in res["errors"][q][obs[0]] if c not in ("horizontal error", "vertical error")]:
            for ob in obs:
                if c in res["errors"][q][ob]:
                    acc.setdefault((q, c), []).append((named(ob), res["errors"][q][ob][c]))
    left = ["%s (%s)" % (x.get("object"), x.get("why") or x.get("reason") or "") for q in res.get("left_out", {}).values() for x in q]
    reasons = ["%s: %s" % (S_["qty"].get(q, q), r) for q, r in res.get("reasons", {}).items()]
    if left or reasons:
        p.say(S_["nav_left"].format(list="; ".join(reasons + left)))


# ------------------------------------------------------------------------------------------------ states

def state_signals(store, rids: Sequence[str]) -> List[str]:
    """The state signals worth a timeline: the run's mode / phase signal first (overview.phase_signal), then any
    signal with text values (a status, a mode by another name), then the numeric states named like a mode / phase."""
    from svcore.overview import PHASE_NAMES, phase_signal
    out: List[str] = []
    for rid in rids:
        names = list(store.get(rid).run.signals)
        lab = [(n, bool(store.labels(f"{rid}/{n}"))) for n in names]
        first = phase_signal(lab)
        # then any text-valued signal (a status, a mode by another name) and the numeric states named like a mode
        texts = [n for n, has in lab if has and n != first and len(store.labels(f"{rid}/{n}") or {}) <= 50]
        named = [n for n in names if n != first and n not in texts and PHASE_NAMES.search(n) and store.is_state(f"{rid}/{n}")]
        cands = ([first] if first else []) + texts + named
        out += [f"{rid}/{n}" for n in cands]
    return out


def states(p: Part, rids: List[str], arg: str, o: Dict):
    st, S_ = p.store, p.S
    cands = state_signals(st, rids)
    flt = arg.strip().lower()
    if flt:
        cands = [c for c in cands if flt in c.split("/", 1)[1].lower()] or \
            [f"{rid}/{n}" for rid in rids for n in st.get(rid).run.signals if flt in n.lower()]
    if not cands:
        p.say("*%s*" % S_["none_st"])
        return
    mn = o.get("min", 0.0)
    steady: List[str] = []
    for sid in cands[:8]:
        rid = sid.split("/")[0]
        t, y = _sig(st, sid)
        run = st.get(rid).run
        end = max(float(t[-1]) if len(t) else 0.0, float(run.end_time or 0.0) + float(run.time_offset or 0.0))
        tl = rp.timeline(t, y, st.labels(sid), end)
        if not tl:
            continue
        if len(tl) == 1 and not flt:                    # never changes: one line, no table and no plot
            steady.append("%s: %s" % (_label(st, sid, rids), tl[0]["label"]))
            continue
        shown = [s for s in tl if s["b"] - s["a"] >= mn]
        dropped = len(tl) - len(shown)
        name = _label(st, sid, rids)
        p.say(S_["st_intro"].format(name=name, n=len(tl), c=max(0, len(tl) - 1),
                                    dropped=S_["st_dropped"].format(n=dropped, min=secs(mn)) if dropped else ""))
        track = _track_of(st, rid)
        rows = []
        for k, s in enumerate(shown[:200]):
            where = "—"
            if track:
                lat = rp.at(track["t"], track["lat"], s["a"]); lon = rp.at(track["t"], track["lon"], s["a"])
                alt = rp.at(track["t"], track["alt"], s["a"]) if track.get("alt") is not None else None
                if lat is not None and lon is not None:
                    d = float(rp.distance_m(track["lat0"], track["lon0"], np.array([lat]), np.array([lon]))[0])
                    where = S_["st_where"].format(alt=fmt(alt) if alt is not None else "—", d=dist(d, p.lang))
            rows.append([str(k + 1), s["label"], secs(s["a"]), secs(s["b"]), secs(s["b"] - s["a"]), where])
        p.say(table(S_["st_head"], rows))
        tot: Dict[str, float] = {}
        for s in tl:
            tot[s["label"]] = tot.get(s["label"], 0.0) + (s["b"] - s["a"])
        whole = sum(tot.values()) or 1.0
        most = max(tot, key=lambda k: tot[k])
        ch: Dict[str, int] = {}
        for a, b in zip(tl, tl[1:]):
            key = "%s → %s" % (a["label"], b["label"])
            ch[key] = ch.get(key, 0) + 1
        top = sorted(ch.items(), key=lambda kv: -kv[1])[:6]
        p.say(S_["st_most"].format(s=most, p="%.0f" % (tot[most] / whole * 100),
                                   list=", ".join("%s ×%d" % kv for kv in top) if top else "—"))
        p.hl("info", 0.3, S_["st_hl"].format(name=name, n=max(0, len(tl) - 1), s=most, p="%.0f" % (tot[most] / whole * 100)))
        if not o.get("table"):
            p.plot(name, [sig_line(sid, name, 0, state=True)])
    if steady:
        p.say(S_["st_steady"].format(list=", ".join(steady)))


def _track_of(store, rid: str) -> Optional[dict]:
    objs = [c for c in detect_objects(store, [rid]) if c.get("pos") == "lla"]
    if not objs:
        return None
    c = guess_reference(objs)
    if c is None:
        return None
    pk = c["picks"]
    t, lat = _sig(store, pk["lat"]["id"])
    _, lon = _sig(store, pk["lon"]["id"])
    alt = None
    if "alt" in pk:
        ta, a = _sig(store, pk["alt"]["id"])
        alt = np.interp(t, ta, a) if len(ta) > 1 else None
    if len(lon) != len(lat):
        tl, lon0 = _sig(store, pk["lon"]["id"])
        lon = np.interp(t, tl, lon0)
    ok = np.flatnonzero(np.isfinite(lat) & np.isfinite(lon) & ~((np.abs(lat) < 1e-9) & (np.abs(lon) < 1e-9)))
    if not len(ok):
        return None
    return {"name": c["name"], "t": t, "lat": lat, "lon": lon, "alt": alt, "lat0": float(lat[ok[0]]), "lon0": float(lon[ok[0]]),
            "latId": pk["lat"]["id"], "lonId": pk["lon"]["id"]}


def trajectory(p: Part, rids: List[str], arg: str, o: Dict):
    """Each file's track (its reference object: the truth, else the receiver...) - its facts - and one map with every
    file's track, so two runs of one route are seen together."""
    st, S_ = p.store, p.S
    tracks: List[dict] = []
    for rid in rids:
        objs = [c for c in detect_objects(st, [rid]) if c.get("pos") == "lla"]
        if arg.strip():
            objs = [c for c in objs if arg.strip().lower() in c["name"].lower()]
        if not objs:
            continue
        c = (guess_reference(objs) if not arg.strip() else None) or objs[0]
        tr = _track_of_obj(st, c)
        f = rp.path_facts(tr["t"], tr["lat"], tr["lon"], tr["alt"]) if tr else {}
        if not f:
            continue
        name = c["name"] if len(rids) < 2 or ":" in c["name"] else "%s: %s" % (_name(st, rid), c["name"])
        p.say(S_["tr_intro"].format(o=c["name"], f=_name(st, rid), t0=secs(f["t0"]), t1=secs(f["t1"])))
        rows = [[S_["tr_dur"], secs(f["t1"] - f["t0"]) + (" s" if p.lang == "en" else " ש'"), ""],
                [S_["tr_trav"], dist(f["travelled"], p.lang), ""],
                [S_["tr_far"], dist(f["farthest"], p.lang), secs(f["tFarthest"])]]
        if "highest" in f:
            rows += [[S_["tr_high"], fmt(f["highest"]) + " m", secs(f["tHighest"])], [S_["tr_low"], fmt(f["lowest"]) + " m", ""]]
        if "speed" in f:
            rows.append([S_["tr_speed"], fmt(f["speed"]) + " m/s", ""])
        p.say(table(S_["tr_head"], rows))
        p.hl("info", 0.2, S_["tr_hl"].format(o=name, d=dist(f["travelled"], p.lang), far=dist(f["farthest"], p.lang)))
        pk = c["picks"]
        tracks.append({"name": name, "color": PALETTE[len(tracks) % len(PALETTE)], "lat": pk["lat"]["id"], "lon": pk["lon"]["id"],
                       "alt": pk["alt"]["id"] if "alt" in pk else None, "track": None})
    if not tracks:
        p.say("*%s*" % S_["none_tr"])
        return
    if not o.get("table"):
        p.map(S_["tr_map"] if len(tracks) > 1 else S_["tr_plot"].format(o=tracks[0]["name"]), tracks)


def _track_of_obj(store, c: dict) -> Optional[dict]:
    pk = c["picks"]
    t, lat = _sig(store, pk["lat"]["id"])
    tl, lon = _sig(store, pk["lon"]["id"])
    if len(tl) != len(t):
        lon = np.interp(t, tl, lon)
    alt = None
    if "alt" in pk:
        ta, a = _sig(store, pk["alt"]["id"])
        alt = np.interp(t, ta, a) if len(ta) > 1 else None
    return {"t": t, "lat": lat, "lon": lon, "alt": alt, "latId": pk["lat"]["id"], "lonId": pk["lon"]["id"]}


# ------------------------------------------------------------------------------------------------ overview

def overview(p: Part, rids: List[str], arg: str, o: Dict):
    """Any recording, whatever it holds (owner, 2026-11-19: not only flight logs): each file's size and rate, its data
    quality (svcore/quality.py, the Quality dialog's checks), every numeric signal's statistics on all its samples,
    its state signals, and its first signals plotted - one plot each."""
    from svcore.ops import compute_signal_stats
    from svcore.quality import run_quality
    st, S_ = p.store, p.S
    shown: Dict[str, List[str]] = {}
    for rid in rids:
        lr = st.get(rid)
        run = lr.run
        names = list(run.signals)
        flt = arg.strip().lower()
        if flt:
            names = [n for n in names if flt in n.lower()]
        nums: List[str] = []
        states_: List[str] = []
        streams = set(byte_streams(st, rid))
        for n in names:
            if n not in streams:
                (states_ if st.is_state(f"{rid}/{n}") else nums).append(n)
        t0, t1 = float(run.start_time + (run.time_offset or 0)), float(run.end_time + (run.time_offset or 0))
        rate = (len(run.time) - 1) / (run.end_time - run.start_time) if run.end_time > run.start_time and len(run.time) > 1 else None
        p.say(S_["ov_intro"].format(f=lr.name, n=len(names), d=secs(t1 - t0), t0=secs(t0), t1=secs(t1),
                                    r=(", " + S_["ov_rate"].format(r=fmt(rate))) if rate else ""))
        q = run_quality((n, sg.time if sg.time is not None else run.time, sg.data, st.is_state(f"{rid}/{n}"))
                        for n, sg in ((n, run.signals[n]) for n in names))
        bad = [r for r in q["signals"] if r["issues"]]
        if bad:
            kinds = ", ".join("%s %d" % (S_["ov_kind"].get(k, k), c) for k, c in q["count"].items() if c)
            p.say(S_["ov_quality"].format(n=len(bad), kinds=kinds, list=", ".join(
                "%s (%s)" % (r["name"], ", ".join(S_["ov_kind"].get(k, k) for k in r["issues"])) for r in bad[:8]) + (" …" if len(bad) > 8 else "")))
            p.hl("warn", 2.0, S_["ov_hl"].format(f=lr.name, n=len(bad), kinds=kinds))
        else:
            p.say(S_["ov_clean"])
        rows = []
        for n in nums[:o.get("top", 60)]:
            t, y = _sig(st, f"{rid}/{n}")
            ss = compute_signal_stats(t, y) or {}
            tmax = None
            if len(y) and np.isfinite(y).any():
                tmax = float(t[int(np.nanargmax(y))])
            rows.append([n, fmt(ss.get("min")), fmt(ss.get("max")), fmt(ss.get("mean")), fmt(ss.get("std")), secs(tmax)])
        if rows:
            p.say(table(S_["ov_head"], rows))
            if len(nums) > len(rows):
                p.say(S_["ov_more"].format(n=len(rows), m=len(nums)))
        if streams:
            p.say(S_["ov_streams"].format(list=", ".join(n for n in names if n in streams)))
        if states_:
            p.say(S_["ov_states"].format(list=", ".join("%s (%d)" % (n, len(st.labels(f"{rid}/{n}") or {}) or
                                                                     len(np.unique(_sig(st, f"{rid}/{n}")[1][np.isfinite(_sig(st, f"{rid}/{n}")[1])])))
                                                         for n in states_[:20])))
        for n in nums[:o.get("plots", 4)]:
            shown.setdefault(n, []).append(f"{rid}/{n}")
    # the first signals plotted, one plot each - a signal several files have: every file's line in one plot
    if not o.get("table"):
        for n, ids in shown.items():
            p.plot(n, [sig_line(i, _label(st, i, rids), k) for k, i in enumerate(ids)])


# ------------------------------------------------------------------------------------------------ moments

def moments(p: Part, rids: List[str], arg: str, o: Dict):
    """The moments of each file worth a look, as one time line: the scenario's phases, every change of another
    state (a receiver LOST and back), leaving and returning to the ground, the highest and the farthest points, the
    largest tracking errors, and the recording's own flags (a stuck or saturated signal, a gap, a spike -
    svcore/overview.py, the overview strip's)."""
    st, S_ = p.store, p.S
    M, D = S_["mo"], S_["mo_det"]
    any_found = False
    for rid in rids:
        rows: List[Tuple[float, str, str, str]] = []           # (t, moment, detail, level)
        ov = st.overview(rid)
        ph = ov.get("phaseSignal")
        for s_ in (ov.get("phases") or [])[1:]:
            rows.append((s_["a"], M["phase"].format(s=s_["label"]), "", "info"))
        for sid in state_signals(st, [rid]):
            name = sid.split("/", 1)[1]
            if name == ph:
                continue
            t, y = _sig(st, sid)
            tl = rp.timeline(t, y, st.labels(sid))
            for a, b in list(zip(tl, tl[1:]))[:40]:
                rows.append((b["a"], M["state"].format(name=name, a=a["label"], b=b["label"]), "", "warn"))
        tr = _track_of(st, rid)
        if tr is not None and tr.get("alt") is not None:
            alt = np.asarray(tr["alt"], dtype=np.float64)
            t = tr["t"]
            ok = np.isfinite(alt)
            if ok.sum() > 10:
                base = float(alt[ok][0])
                up = (alt - base > 5.0) & ok
                runs = [(a, b) for a, b in rp._stretches(up) if t[min(b, len(t) - 1)] - t[a] >= 3.0]
                if runs:
                    a0, b0 = runs[0][0], runs[-1][1]
                    rows.append((float(t[a0]), M["takeoff"], D["takeoff"].format(v="5"), "info"))
                    if b0 < len(t):
                        rows.append((float(t[min(b0, len(t) - 1)]), M["landing"], "", "info"))
            f = rp.path_facts(t, tr["lat"], tr["lon"], tr["alt"])
            if "tHighest" in f:
                rows.append((f["tHighest"], M["highest"], D["highest"].format(v=fmt(f["highest"])), "info"))
            if "tFarthest" in f:
                rows.append((f["tFarthest"], M["farthest"], D["farthest"].format(v=dist(f["farthest"], p.lang)), "info"))
        ids = [f"{rid}/{n}" for n in st.get(rid).run.signals]
        errs = []
        for q in rp.setpoint_pairs(ids):
            tk = rp.tracking(_sig(st, q["setpoint"]), _sig(st, q["measured"]), q["measured"].split("/", 1)[1], None, st.is_state(q["setpoint"]))
            if tk.get("tmax") is not None:
                ts_, ys_ = _sig(st, q["setpoint"])
                errs.append((tk["score"], tk["tmax"], rp.bare(q["measured"].split("/", 1)[1]), tk["max"], rp.at(ts_, ys_, tk["tmax"])))
        for sc, tm, m, mx, c in sorted(errs, reverse=True)[:3]:
            rows.append((tm, M["error"].format(m=m), D["error"].format(v=fmt(mx), c=fmt(c)), "warn" if sc > 0.1 else "info"))
        for fl in ov.get("flags") or []:
            k = fl["kind"]
            dur = secs(fl["b"] - fl["a"])
            title = M[k].format(sig=fl.get("signal", ""), edge=S_["edge"].get(fl.get("edge", ""), ""))
            det = D[k].format(v=fmt(fl.get("value")), d=dur)
            rows.append((fl["a"], title, det, "warn"))
        if arg.strip():
            rows = [r for r in rows if arg.strip().lower() in (r[1] + " " + r[2]).lower()]
        if not rows:
            continue
        any_found = True
        rows.sort(key=lambda r: r[0])
        f_name = _name(st, rid)
        p.say(S_["mo_intro"].format(f=f_name, n=len(rows)))
        p.say(table(S_["mo_head"], [[secs(r[0]), r[1], r[2]] for r in rows[:o.get("top", 60)]]))
        for r in rows:
            if r[3] == "warn":
                p.hl("warn", 1.0, S_["mo_hl"].format(f=f_name, what=r[1], t=secs(r[0])))
    if not any_found:
        p.say("*%s*" % S_["mo_none"])


# ------------------------------------------------------------------------------------------------ differences

_COUNTER = re.compile(r"(^|[._ \[])(time|timestamp|timeus|time_us|timems|time_boot_ms|t|tow|gms|gwk|lineno|seq|counter|index|sample)($|[._ \]])", re.I)


_BASE_WORDS = re.compile(r"(^|[^a-z])(ref|reference|base|baseline|golden|gold|nominal|master|expected)([^a-z]|$)", re.I)


def guess_base(store, rids: Sequence[str]) -> str:
    """The baseline an engineer would take: the file whose name says so (ref, baseline, golden, nominal...), else
    the first opened."""
    return next((r for r in rids if _BASE_WORDS.search(os.path.splitext(store.get(r).name)[0])), rids[0])


def pick_base(store, rids: Sequence[str], want: str) -> str:
    if not want:
        return guess_base(store, rids)
    w = want.lower()
    hit = next((r for r in rids if store.get(r).name.lower() == w), None) or next((r for r in rids if w in store.get(r).name.lower()), None)
    if hit is None:
        raise PartError(S["en"]["no_base"].format(b=want, list=", ".join(store.get(r).name for r in rids)))
    return hit


def differences(p: Part, rids: List[str], arg: str, o: Dict):
    st, S_ = p.store, p.S
    if len(rids) < 2:
        p.say("*%s*" % S_["none_diff"])
        return
    base = pick_base(st, rids, o.get("base") or arg.strip())
    others = [r for r in rids if r != base]
    key = lambda n: rp.bare(n).strip().lower()           # the same signal whatever its unit's spelling (Compare's C13)
    bnames = {key(n): n for n in st.get(base).run.signals}
    onames = {r: {key(n): n for n in st.get(r).run.signals} for r in others}
    common = [k for k in bnames if all(k in onames[r] for r in others)]
    only = sorted({st.get(base).name + ": " + bnames[k] for k in bnames if k not in common}
                  | {st.get(r).name + ": " + n for r in others for k, n in onames[r].items() if k not in bnames})
    small, large = o.get("small", 0.02), o.get("large", 0.10)
    rows, skipped = [], 0
    for k in common:
        name = bnames[k]
        bid = f"{base}/{name}"
        if _COUNTER.search(name):
            skipped += 1
            continue
        tb, yb = _sig(st, bid)
        state = st.is_state(bid)
        blab = st.labels(bid)
        worst = None
        for r in others:
            oid = f"{r}/{onames[r][k]}"
            to, yo = _sig(st, oid)
            olab = st.labels(oid)
            if blab or olab:                             # text states: each file numbers its texts its own way
                yb, yo, common_lab = _same_codes(yb, blab or {}, yo, olab or {})
            d: Optional[Dict] = {"overall": 0.0, "peak": 0.0, "same": True}
            if not (len(tb) == len(to) and np.array_equal(tb, to) and np.allclose(yb, yo, equal_nan=True, rtol=0, atol=0)):
                d = rp.difference((tb, yb), (to, yo), name, state)
            if d is None:
                continue
            d.update({"name": name, "rid": r, "oid": oid, "bid": bid, "state": state})
            if blab or olab:
                d["labels"] = common_lab
            if worst is None or max(d["peak"], d["overall"]) > max(worst["peak"], worst["overall"]):
                worst = d
        if worst is not None:
            rows.append(worst)
    if not rows:
        p.say("*%s*" % S_["diff_same"])
        return
    lv = {"same": 0, "small": 0, "large": 0}
    for d in rows:
        d["level"] = "same" if d.get("same") else rp.level(d, small, large)
        lv[d["level"]] += 1
    rows.sort(key=lambda d: -max(d["peak"], d["overall"]))
    base_name = st.get(base).name
    others_name = ", ".join(st.get(r).name for r in others)
    p.say(S_["diff_intro"].format(others=others_name, base=base_name, n=len(rows), same=lv["same"], small=lv["small"], large=lv["large"]))
    notes = []
    if only:
        notes.append(S_["diff_only"].format(list=", ".join(only[:12]) + (" …" if len(only) > 12 else "")))
    if skipped:
        notes.append(S_["diff_skip"].format(n=skipped))
    if notes:
        p.say(" ".join(notes))
    differ = [d for d in rows if d["level"] != "same"]
    if not differ:
        p.say("*%s*" % S_["diff_same"])
        return
    # the top: one per family (IMU.AccX / AccY / AccZ is one row on top; all are in the table at the end)
    top, fams = [], set()
    for d in differ:
        fam = d["name"].rsplit(".", 1)[0] if "." in d["name"] else d["name"]
        if fam in fams:
            continue
        fams.add(fam)
        top.append(d)
        if len(top) >= o.get("top", 6):
            break
    reg = rp.region([d for d in top if d["level"] == "large"] or top)
    if reg:
        line = S_["diff_region"].format(a=secs(reg["a"]), b=secs(reg["b"]))
        if reg.get("first") is not None:
            line += S_["diff_first"].format(name=reg["firstName"], t=secs(reg["first"]))
            p.hl("warn", 5.0, S_["diff_hl_region"].format(a=secs(reg["a"]), b=secs(reg["b"]), name=reg["firstName"], t=secs(reg["first"])))
        p.say(line)
    p.say(S_["diff_how"])

    def row(d):
        return [d["name"], st.get(d["rid"]).name, pct(d["overall"]), pct(d["peak"]),
                "%s – %s" % (secs(d["region"][0]), secs(d["region"][1])) if d.get("region") else "—",
                secs(d.get("first")), "—" if d.get("shape") is None else "%.2f" % d["shape"]]
    p.say(table(S_["diff_head"], [row(d) for d in top]))
    for d in top:
        if d["level"] == "large":
            p.hl("warn", d["peak"], S_["diff_hl"].format(name=d["name"], base=base_name, a=secs(d["region"][0]), b=secs(d["region"][1]), p=pct(d["peak"])))
    if not o.get("table"):
        # where the files differ, over the whole time: each top signal's difference as % of how much it moves
        lines = []
        for j, d in enumerate(top):
            tb, yb = _sig(st, d["bid"])
            to, yo = _sig(st, d["oid"])
            if d.get("labels") is not None:              # text states on one numbering, as compared
                yb, yo, _ = _same_codes(yb, st.labels(d["bid"]) or {}, yo, st.labels(d["oid"]) or {})
            a, b = max(tb[0], to[0]), min(tb[-1], to[-1])
            m = (tb >= a) & (tb <= b)
            t = tb[m]
            y1 = rp.on_grid(to, yo, t, d["state"])
            per = rp.angle_period(d["name"], [yb, yo])
            dd = y1 - yb[m]
            if per:
                dd = (dd + per / 2) % per - per / 2
            lines.append(sig_line(p.series(d["name"], t, np.abs(dd) / d["span"] * 100.0), d["name"], j))
        p.plot(S_["diff_where"], lines, rng=None, caption=S_["diff_where_cap"])
        # each top signal zoomed on its own region (with a margin), every file's line
        for d in top:
            a, b = d["region"]
            w = max(b - a, 1.0)
            rng = [max(d["t0"], a - 0.5 * w), min(d["t1"], b + 0.5 * w)]
            ids = [d["bid"]] + [f"{r}/{onames[r][key(d['name'])]}" for r in others]
            p.plot(S_["diff_plot"].format(name=d["name"], a=secs(a), b=secs(b)),
                   [sig_line(i, _label(st, i, rids), k, state=d["state"]) for k, i in enumerate(ids)], rng=rng,
                   caption=S_["diff_cap"].format(others=others_name, base=base_name, o=pct(d["overall"]), p=pct(d["peak"])))
    # states whose sequence differs
    seqs = []
    for d in differ:
        if d.get("state") and d.get("sequences") and d["sequences"][0] != d["sequences"][1]:
            lab = d.get("labels") or st.labels(d["bid"]) or {}
            nm = lambda v: lab.get(int(v), fmt(v)) if float(v).is_integer() else fmt(v)
            seqs.append("- %s - %s: %s; %s: %s" % (d["name"], base_name, " → ".join(nm(v) for v in d["sequences"][0][:12]),
                                                   st.get(d["rid"]).name, " → ".join(nm(v) for v in d["sequences"][1][:12])))
    if seqs:
        p.say(S_["diff_states"] + "\n\n" + "\n".join(seqs[:8]))
    # parameters that differ (a log's parameters, the file's settings, numbers in its name) - often the cause
    try:
        from svcore.investigate import run_params
        pb = run_params(st.get(base).run)
        po = {r: run_params(st.get(r).run) for r in others}
        diffp = [k for k in sorted(pb) if any(k in po[r] and not _same(pb[k], po[r][k]) for r in others)]
        if diffp:
            p.say(S_["diff_params"].format(n=len(diffp)))
            p.say(table([S_["param"], base_name] + [st.get(r).name for r in others],
                        [[k, fmt(pb[k])] + [fmt(po[r].get(k)) for r in others] for k in diffp[:25]]))
    except Exception:                                    # parameters are a help, never a reason to fail the part
        pass
    rest = [d for d in differ if d not in top]
    if rest:
        p.say(S_["diff_rest"].format(n=len(rest)))
        p.say(table(S_["diff_head"], [row(d) for d in rest[:300]]))


def _same_codes(yb, lb: Dict[int, str], yo, lo: Dict[int, str]):
    """Two text-valued signals on one numbering: the base file's codes kept, the other's texts mapped onto them
    (a text only the other file has gets a new code)."""
    by_text = {v: k for k, v in lb.items()}
    common = dict(lb)
    nxt = max(list(lb) + [-1]) + 1
    remap = {}
    for code, text in lo.items():
        if text not in by_text:
            by_text[text] = nxt
            common[nxt] = text
            nxt += 1
        remap[code] = by_text[text]
    yo = np.asarray(yo, dtype=np.float64).copy()
    src = yo.copy()
    for code, new in remap.items():
        yo[src == code] = new
    return yb, yo, common


def _same(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a)))
    except (TypeError, ValueError):
        return a == b


# ------------------------------------------------------------------------------------------------ summary

def summary(p: Part, highlights: List[Dict], o: Dict):
    S_ = p.S
    if not highlights:
        p.say("*%s*" % S_["sum_none"])
        return
    order = {"fail": 0, "warn": 1, "info": 2}
    hs = sorted(highlights, key=lambda h: (order.get(h["level"], 3), -h["score"]))[:o.get("top", 7)]
    mark = {"fail": "✖", "warn": "⚠", "info": "•"}
    p.say(S_["sum_intro"])
    p.say("\n".join("- %s %s" % (mark.get(h["level"], "•"), h["text"]) for h in hs))


RUN = {"overview": overview, "moments": moments, "messages": messages, "tracking": tracking, "navigation": navigation, "states": states, "trajectory": trajectory, "differences": differences}


def expand_all(store, text: str, items: List[dict], lang: str) -> Tuple[str, Dict[str, Tuple[np.ndarray, np.ndarray]]]:
    """Every part item of the document -> its Markdown in place of its marker (the summary last, from the others'
    highlights). Returns the new text and the inline series the parts' plots draw."""
    extra: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    highlights: List[Dict] = []
    later: List[int] = []
    out = text
    for k, it in enumerate(list(items)):
        if it.get("kind") != "part":
            continue
        if it.get("part") in ("summary", "toc"):
            later.append(k)
            continue
        out = out.replace("\u27e6%d\u27e7" % k, _one(store, k, it, items, extra, lang, highlights))
    for k in later:
        if items[k].get("part") == "toc":
            continue
        out = out.replace("\u27e6%d\u27e7" % k, _one(store, k, items[k], items, extra, lang, highlights))
    for k in later:                                      # the table of contents last: the parts' headings are in
        if items[k].get("part") == "toc":
            out = out.replace("\u27e6%d\u27e7" % k, toc_markdown(out, S.get(lang, S["en"])))
            items[k] = {"kind": "done"}
    return out, extra


def heading_id(text: str) -> str:
    """The anchor of a heading in the page (app/reportdoc.py gives each h2 / h3 this id; [[toc]] links to it)."""
    return "h-" + (re.sub(r"[^\w\u0590-\u05FF]+", "-", text.strip().lower()).strip("-") or "x")


def toc_markdown(text: str, S_: Dict[str, Any]) -> str:
    """[[toc]]: the document's headings (## and ###, after the title) as a list of links - the page's links jump."""
    from app.reportdoc import parse, MARK
    lines = []
    for b in parse(text):
        if b["t"] == "heading" and b["level"] in (2, 3):
            t = MARK.sub("", b["text"]).strip()
            if t:
                lines.append("%s- [%s](#%s)" % ("  " * (b["level"] - 2), t.replace("[", "(").replace("]", ")"), heading_id(t)))
    if not lines:
        return "\n\n*%s*\n\n" % S_["toc_none"]
    return "\n\n**%s**\n\n%s\n\n" % (S_["toc"], "\n".join(lines))


def _one(store, k: int, it: dict, items: List[dict], extra, lang: str, highlights: List[Dict]) -> str:
    part = str(it.get("part") or "")
    p = Part(store, items, extra, lang)
    p.base = str(it.get("mapBase") or "")
    try:
        o = options(part, it.get("opts") or [])
        rids = _runs(store, it.get("runs"))
        if part == "summary":
            summary(p, highlights, o)
        elif part == "messages":
            messages(p, rids, str(it.get("arg") or ""), o, it.get("streams"))
        else:
            RUN[part](p, rids, str(it.get("arg") or ""), o)
    except PartError as e:
        msg = str(e)
        if " " not in msg.strip():                       # an option word
            msg = p.S["bad_opt"].format(part=part, o=msg, known=KNOWN.get(part, ""))
        items[k] = {"kind": "error", "error": msg}
        return "\u27e6%d\u27e7" % k
    except KeyError as e:                                 # a file closed meanwhile
        items[k] = {"kind": "error", "error": "%s: %s" % (part, e)}
        return "\u27e6%d\u27e7" % k
    highlights += p.highlights
    items[k] = {"kind": "done"}
    return "\n\n" + "\n\n".join(p.md) + "\n\n"


class WithExtra:
    """The Store, plus the parts' inline series ("auto/<n>/<label>") for plot_data - nothing added to the Store."""

    def __init__(self, store, extra: Dict[str, Tuple[np.ndarray, np.ndarray]]):
        self._s, self._x = store, extra

    def signal(self, sid: str):
        if sid in self._x:
            return self._x[sid]
        return self._s.signal(sid)

    def labels(self, sid: str):
        return None if sid in self._x else self._s.labels(sid)

    def __getattr__(self, name):
        return getattr(self._s, name)


# ------------------------------------------------------------------------------------------------ the library

def scan(store, rids: Optional[Sequence[str]] = None, defs: Optional[Sequence[Dict]] = None) -> Dict:
    """What the parts would find - for the Report screen's library: the files, the pairs, the objects with the
    guessed reference, the state signals, the tracks."""
    rids = _runs(store, rids)
    ids = [f"{rid}/{n}" for rid in rids for n in store.get(rid).run.signals]
    pairs = rp.setpoint_pairs(ids)
    objs = detect_objects(store, rids) if rids else []
    ref = guess_reference(objs)
    return {"files": [{"id": r, "name": store.get(r).name} for r in rids],
            "pairs": [{"setpoint": q["setpoint"].split("/", 1)[1], "measured": q["measured"].split("/", 1)[1],
                       "file": store.get(q["measured"].split("/")[0]).name} for q in pairs],
            "objects": [{"name": c["name"], "cls": c["cls"], "pos": c["pos"]} for c in objs],
            "reference": ref["name"] if ref else None,
            "base": store.get(guess_base(store, rids)).name if rids else None,
            "states": [{"name": s.split("/", 1)[1], "file": store.get(s.split("/")[0]).name} for s in state_signals(store, rids)],
            "tracks": sum(1 for c in objs if c.get("pos") == "lla"),
            "streams": [{"name": s_["name"], "file": store.get(s_["rid"]).name, "count": s_["r"]["count"]} for s_ in find_streams(store, rids, defs) if not s_.get("error")]}
