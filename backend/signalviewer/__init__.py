"""Signal Viewer from Python - the same readers as the app, without the window or the server.

    import signalviewer as sv
    rec = sv.load("flight.bin")            # .csv .mat .bin .tlog .ulg
    rec.signals                            # names
    t, y = rec.signal("ATT.Roll")          # numpy arrays (each signal keeps its own time);
                                           # the unit may be left out: "ATT.Roll [deg]"
    df = rec.to_dataframe(["ATT.Roll", "ATT.Pitch"], t0=10, t1=60)   # one time base (pandas)
    sv.show(t, {"roll": y}, name="from a script")   # into the open app (see push_client)

Map objects and their comparison (L12) - the app's rules and numbers (docs/api.md):

    rec.objects()                          # found objects: name, class, frame, origin, why
    nav = rec.object("XKF1[0]")            # t, lat, lon, alt (NED placed on Earth by its origin), angles, velocity
    cmp = sv.compare_objects(rec, reference="POS", objects=["XKF1[0]", "XKF1[1]"],
                             what=("position", "velocity", "attitude"), frame="ned")
    cmp.values(); cmp.errors(); cmp.stats(); cmp.to_csv("errors.csv"); cmp.to_mat("errors.mat")
    sv.similar(rec)                        # families of similar signals (nav1 / nav2, XKF1[0] / XKF1[1])
    sv.compare_signals(rec, ["nav1.att.roll", "nav2.att.roll"], reference="truth.att.roll")
    sv.map_image(rec, path="map.png"); sv.map_html(rec, path="map.html")
    sv.report(rec, path="report.html", compare=cmp, map=True)   # .pdf / .docx too

From MATLAB or a shell, use the command line instead: `python cli.py --help`.
"""
import contextlib as _contextlib
import os as _os
import sys as _sys
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# T56: installed with pip, the app's own modules (app, svcore), its UI and the examples live in
# signalviewer/_core; from the source folder they are next to this package (backend/).
_CORE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_core")
if _os.path.isdir(_CORE) and _CORE not in _sys.path:
    _sys.path.insert(0, _CORE)

import numpy as np

from app.store import Store
from svcore.analysis import align_to
from svcore.naming import resolve_signal_name

from .push_client import show

__all__ = ["load", "Recording", "show", "Comparison", "compare_objects", "similar", "compare_signals", "map_image", "map_html", "report"]

_COLORS = ["#e5677a", "#3d8bfd", "#2fbf9f", "#9b7bff", "#f07b3f", "#4fc3e8", "#d4a72c", "#8bc34a"]


class Recording:
    """One file, read the way the app reads it (same auto-detection, same signal names)."""

    def __init__(self, store: Store, run_id: str):
        self._store, self._id = store, run_id
        lr = store.get(run_id)
        self.name: str = lr.name
        self.path: str = lr.run.file_path
        self.report: Dict = dict(lr.load_report)

    @property
    def signals(self) -> List[str]:
        return list(self._store.get(self._id).run.signals.keys())

    def signal(self, name: str) -> Tuple[np.ndarray, np.ndarray]:
        """(time, values) of one signal, by its name in the app - or without its unit, in any
        case ("ATT.Roll" for "ATT.Roll [deg]") when that is one signal. A name that is not raises
        KeyError with the closest names."""
        full = resolve_signal_name(self.signals, name, self.name)
        t, y = self._store.signal(f"{self._id}/{full}")
        return np.asarray(t, dtype=np.float64), np.asarray(y, dtype=np.float64)

    def table(self, names: Optional[Sequence[str]] = None, t0: Optional[float] = None,
              t1: Optional[float] = None, alignment: str = "linear") -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Signals on ONE time base - the first signal's, inside [t0, t1], full resolution -
        exactly like "Export CSV" in the app. Returns (time, {name: values})."""
        names = list(names) if names else self.signals
        if not names:
            raise ValueError("No signals to put in the table.")
        t_base, y0 = self.signal(names[0])
        i0 = 0 if t0 is None else int(np.searchsorted(t_base, t0, "left"))
        i1 = len(t_base) if t1 is None else int(np.searchsorted(t_base, t1, "right"))
        t = t_base[i0:i1]
        cols = {names[0]: y0[i0:i1]}
        for n in names[1:]:
            ts, ys = self.signal(n)
            cols[n] = np.asarray(align_to(t, ts, ys, alignment), dtype=np.float64)
        return t, cols

    def to_dataframe(self, names: Optional[Sequence[str]] = None, t0: Optional[float] = None,
                     t1: Optional[float] = None, alignment: str = "linear"):
        """`table()` as a pandas DataFrame with a "Time" column."""
        import pandas as pd
        t, cols = self.table(names, t0, t1, alignment)
        return pd.DataFrame({"Time": t, **cols})

    def __repr__(self) -> str:
        return f"<Recording {self.name!r}: {len(self.signals)} signals>"

    # ---- L12: map objects ------------------------------------------------------------------------

    def _sig(self, sid: str) -> Tuple[np.ndarray, np.ndarray]:
        t, y = self._store.signal(sid)
        return np.asarray(t, dtype=np.float64), np.asarray(y, dtype=np.float64)

    def _detect(self) -> Dict:
        from svcore.objects import detect
        run = self._store.get(self._id).run
        return detect([(f"{self._id}/{n}", n) for n in run.signals], self._id, self.name)

    def objects(self, all: bool = False) -> List[Dict]:
        """The objects found in this file - the app's suggestion bar / *Choose…* list, best first. Each: name,
        cls (truth / navigation / receiver / other), frame (lla / ned / enu / ecef), origin (where a local
        position is placed: {via, rule}), addable (what *Add all* takes), signals ({role: name}) and why
        (the reasons, as the app's *Why?* gives them in data). all=False: only what *Add all* would add."""
        from svcore.objects import addable
        out = []
        for c in self._detect()["candidates"]:
            if not all and not addable(c):
                continue
            out.append({"name": c["name"], "cls": c["cls"], "frame": c["pos"], "attitude": c["attitude"],
                        "origin": {"via": c["origin"]["via"], "rule": c["origin"]["rule"], **({"moves": True} if c["origin"].get("moves") else {})} if c.get("origin") else None,
                        "addable": addable(c), "signals": {r: p["name"] for r, p in c["picks"].items()},
                        "why": {"class": c["clsWhy"], "picks": {r: {"rule": p["rule"], "word": p["word"], **({"via": p["via"]} if p.get("via") else {})} for r, p in c["picks"].items()},
                                "missing": c["missing"], **({"badUnit": c["badUnit"]} if c.get("badUnit") else {}), **({"lane": c["lane"]} if c.get("lane") else {}),
                                "nearMisses": [{"name": m["name"], "role": m["role"], "why": m["why"]} for m in c["nearMisses"]]}})
        return out

    def _candidate(self, name: str) -> Dict:
        for c in self._detect()["candidates"]:
            if c["name"] == name:
                return c
        raise KeyError(f"No object named {name!r} in {self.name} (found: {', '.join(c['name'] for c in self._detect()['candidates'])})")

    def object(self, name: str) -> Dict[str, np.ndarray]:
        """One object's arrays on its position's time: t, lat, lon, alt (a NED / ENU / ECEF position placed on
        Earth exactly as the app does), roll / pitch / yaw (its own, as recorded) and vn / ve / vd when it has them,
        aligned onto that time (linear)."""
        from svcore.objcompare import position
        c = self._candidate(name)
        pos = position(self._sig, c)
        t = pos[0][0]
        out: Dict[str, np.ndarray] = {"t": t, "lat": pos[0][1], "lon": np.asarray(align_to(t, *pos[1], "linear"))}
        if len(pos) > 2:
            out["alt"] = np.asarray(align_to(t, *pos[2], "linear"))
        for r in ("roll", "pitch", "yaw", "vn", "ve", "vd"):
            p = c["picks"].get(r)
            if p:
                out[r] = np.asarray(align_to(t, *self._sig(p["id"]), "linear"))
        return out


def load(path: str, settings: Optional[dict] = None) -> Recording:
    """Read a file. `settings` are the CSV import options of the app's Import dialog
    (e.g. {"delimiter": ";", "time_column": "t"}); usually not needed. As in the app's Time axis
    dialog, {"time_scale": 0.001} puts a time logged in milliseconds into seconds (CSV, MAT,
    Parquet, HDF5), and {"own_time_scale": ...} does the same for columns with a time of their own."""
    store = Store()
    # the readers print progress ("[OK] Loaded ...") for the app's console; in a script or a
    # notebook stdout is the user's own output, so it goes to stderr (as on the command line)
    with _contextlib.redirect_stdout(_sys.stderr):
        lr = store.open_file(path, settings)
    return Recording(store, lr.id)


# ---- L12: comparisons, similar signals, maps and reports ------------------------------------------

class Comparison:
    """The result of compare_objects: values(), errors(), stats() as pandas DataFrames; to_csv / to_mat."""

    def __init__(self, res: Dict):
        self.raw = res
        self.reference: str = res["reference"]
        self.frame: str = res["frame"]
        self.left_out: Dict = res["left_out"]
        self.reasons: Dict = res["reasons"]

    @staticmethod
    def _frame(series: Dict[str, Tuple[np.ndarray, np.ndarray]]):
        """Columns on the first column's time (the others aligned onto it, linear) - as the app's export."""
        import pandas as pd
        if not series:
            return pd.DataFrame()
        items = list(series.items())
        t = items[0][1][0]
        cols = {"Time": t}
        for k, (ts, ys) in items:
            cols[k] = ys if ts is t else np.asarray(align_to(t, ts, ys, "linear"))
        return pd.DataFrame(cols)

    def values(self, quantity: Optional[str] = None):
        """Time + each object's components (`quantity`: one of them; default all) - column "object.component"."""
        s = {f"{o}.{c}": ts for q, objs in self.raw["values"].items() if quantity in (None, q) for o, comps in objs.items() for c, ts in comps.items()}
        return self._frame(s)

    def errors(self, quantity: Optional[str] = None):
        """Time + each object's errors against the reference - column "object.component"."""
        s = {f"{o}.{c}": ts for q, objs in self.raw["errors"].items() if quantity in (None, q) for o, comps in objs.items() for c, ts in comps.items()}
        return self._frame(s)

    def stats(self):
        """object × component -> rms, mean, max_abs, p95_abs, t_max_abs, samples (full resolution)."""
        import pandas as pd
        return pd.DataFrame(self.raw["stats"], columns=["object", "qty", "comp", "rms", "mean", "max_abs", "p95_abs", "t_max_abs", "samples"])

    def to_csv(self, path: str, what: str = "errors") -> str:
        """errors (default), values or stats as CSV (UTF-8 with BOM, like the app's CSV)."""
        df = self.stats() if what == "stats" else self.values() if what == "values" else self.errors()
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path

    def to_mat(self, path: str) -> str:
        """errors, values and stats in one .mat (scipy): each column a variable, names made MATLAB-safe."""
        import re as _re
        from scipy.io import savemat
        safe = lambda k: (_re.sub(r"\W", "_", k).strip("_") or "x")[:63]
        d = {}
        for part, df in (("err", self.errors()), ("val", self.values())):
            for k in df.columns:
                d[safe(f"{part}_{k}")] = df[k].to_numpy()
        st = self.stats()
        d["stats_rms"] = st["rms"].to_numpy(dtype=float)
        d["stats_names"] = np.array([f"{o}.{c}" for o, c in zip(st["object"], st["comp"])], dtype=object)
        savemat(path, d)
        return path

    def __repr__(self) -> str:
        return f"<Comparison vs {self.reference} ({self.frame}): {len(self.raw['stats'])} error components>"


def _objects_of(recs) -> Tuple[Callable[[str], Tuple[np.ndarray, np.ndarray]], List[Dict]]:
    """One signal reader and one object list for one or several recordings; with several files an object's
    name is "file:name" where two files have the same name (POS in both)."""
    recs = recs if isinstance(recs, (list, tuple)) else [recs]
    cands, readers = [], {}
    for r in recs:
        readers[r._id] = r
        for c in r._detect()["candidates"]:
            cands.append((r, c))
    names = [c["name"] for _, c in cands]
    out = []
    for r, c in cands:
        c = dict(c)
        if len(recs) > 1 and names.count(c["name"]) > 1:
            c["name"] = f"{r.name}:{c['name']}"
        out.append(c)
    sig = lambda sid: readers[sid.split("/", 1)[0]]._sig(sid)
    return sig, out


def compare_objects(recs, reference: str, objects: Optional[Sequence[str]] = None,
                    what: Sequence[str] = ("position", "velocity", "attitude"), frame: str = "ned") -> Comparison:
    """The app's *Compare objects…* (L8) on one recording or several ([rec_truth, rec_flight]): each object
    against `reference` - positions (NED / ENU / ECEF / LLA / along-across track), velocities and angles,
    values, errors and their statistics. Several files: on their own times as recorded (no offset), the
    compared object read onto the reference's samples (linear), as the app's relation signals."""
    from svcore.objcompare import compare
    sig, objs = _objects_of(recs)
    return Comparison(compare(sig, objs, reference, objects, what, frame))


def similar(rec: "Recording", loose: bool = False) -> List[Dict]:
    """The families of similar signals of a file (L9): [{leaf, how, members: [{name, seg, unit, cls}]}]."""
    from svcore.similar import families
    run = rec._store.get(rec._id).run
    out = []
    for f in families([(n, n) for n in run.signals], loose):
        out.append({"leaf": f["leaf"], "how": f["how"], "unitsDiffer": f["unitsDiffer"],
                    "members": [{k: m[k] for k in ("name", "seg", "unit", "cls")} for m in f["members"]]})
    return out


def compare_signals(rec: "Recording", names: Sequence[str], reference: str):
    """Each signal minus `reference` (angles wrapped to ±180° / ±pi as in the app), on the reference's time:
    a DataFrame with Time, the values and "name - reference" columns; .attrs["stats"] holds the statistics."""
    import pandas as pd
    from svcore.analysis import compute
    from svcore.ops import compute_signal_stats
    from svcore.similar import angle_wrap
    tr, yr = rec.signal(reference)
    cols = {"Time": tr, reference: yr}
    stats = []
    for n in names:
        if n == reference:
            continue
        t, y = rec.signal(n)
        w = angle_wrap(n)
        if w == "ask":
            from svcore.objcompare import angle_units
            w = "2pi" if angle_units({"yaw": (n, t, y)})["yaw"][0] == "rad" else 360
        te, e = compute("sub", [(t, y), (tr, yr)], {"wrap": w} if w else {})
        cols[n] = np.asarray(align_to(tr, t, y, "linear"))
        cols[f"{n} - {reference}"] = np.asarray(align_to(tr, te, e, "linear"))
        s = compute_signal_stats(te, e) or {}
        stats.append({"signal": n, "rms": s.get("rms"), "mean": s.get("mean"), "max_abs": s.get("abs_max"), "p95_abs": s.get("p95_abs"), "t_max_abs": s.get("t_abs_max")})
    df = pd.DataFrame(cols)
    df.attrs["stats"] = stats
    return df


def _geo_spec(rec, objects=None, title: str = "", cursor: Optional[float] = None, base: str = "offline") -> Dict:
    """The map plot of the app for some objects (default: all that *Add all* would add)."""
    want = [o["name"] for o in rec.objects()] if objects in (None, "all") else list(objects)
    objs = []
    for i, n in enumerate(want):
        c = rec._candidate(n)
        if c["pos"] == "lla":
            lat, lon, alt = c["picks"]["lat"]["id"], c["picks"]["lon"]["id"], (c["picks"].get("alt") or {}).get("id")
        else:                                                       # a position in metres: placed on Earth first
            lat, lon, alt = (_derived_lla(rec, c))
        objs.append({"name": n, "color": _COLORS[i % len(_COLORS)], "lat": lat, "lon": lon, "alt": alt})
    return {"mode": "geo", "title": title or rec.name, "signals": [], "geo": {"objects": objs, "base": base, "cursor": cursor, "bounds": None}}


def _derived_lla(rec, c) -> Tuple[str, str, str]:
    """A local / ECEF object's lat / lon / alt as derived signals of the recording's store (the app's frame group)."""
    vec = [f"{c['picks'][r]['id']}" for r in ("px", "py", "pz")]
    params = {"qty": "position", "src": c["pos"], "dst": "lla"}
    srcs = vec
    if c["pos"] != "ecef":
        if not c.get("origin"):
            raise ValueError(f"{c['name']} has no origin")
        params["ref"] = "signals"
        srcs = vec + list(c["origin"]["ids"])
    ids = []
    for k, a in enumerate(("lat", "lon", "alt")):
        d = rec._store.add_derived("frame", srcs, {**params, "axis": k}, f"{c['name']}_lla.{a}")
        ids.append(f"derived/{d.name}")
    return ids[0], ids[1], ids[2]


def map_image(rec: "Recording", objects=None, path: str = "map.png", theme: str = "light", scale: float = 2.0, cursor: Optional[float] = None) -> str:
    """The app's map picture (L11): offline basemap, tracks, objects at `cursor` (else at their end), legend,
    scale bar, north arrow, attribution. path: .png or .svg."""
    from app import mapimage
    fmt = "svg" if path.lower().endswith(".svg") else "png"
    data = mapimage.render(mapimage.map_data(rec._store, _geo_spec(rec, objects, cursor=cursor)), fmt, theme, scale)
    with open(path, "wb") as f:
        f.write(data)
    return path


def map_html(rec: "Recording", objects=None, path: str = "map.html", theme: str = "light") -> str:
    """The standalone offline map page (L11): pan, zoom, a time slider, light / dark - no network needed."""
    from app import mapimage
    text = mapimage.build_html(mapimage.map_data(rec._store, _geo_spec(rec, objects)), theme)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def report(rec: "Recording", path: str, compare: Optional[Comparison] = None, map: bool = True, title: str = "", lang: str = "en") -> str:
    """A report as the app makes it (.html / .pdf / .docx by the extension): the map of the objects, and for a
    comparison its error plots (one per quantity, the errors of every object) and its statistics table."""
    from app import report as reports
    fmt = path.rsplit(".", 1)[-1].lower()
    if fmt not in ("html", "pdf", "docx"):
        raise ValueError("A report is .html, .pdf or .docx")
    tabs = []
    if map:
        tabs.append({"name": "Map", "plots": [_geo_spec(rec, None, title="Map")]})
    sections = []
    if compare is not None:
        plots = []
        for q, objs in compare.raw["errors"].items():
            for comp in next(iter(objs.values()), {}):
                sigs = []
                for i, (o, comps) in enumerate(objs.items()):
                    t, e = comps[comp]
                    sid = rec._store.add_pushed(f"{o}_{comp}", _pushed_run(f"{o} - {compare.reference}: {comp}", t, e))[0].id
                    sigs.append({"id": f"{sid}/{_PUSHED}", "label": f"{o}: {comp}", "color": _COLORS[i % len(_COLORS)], "width": 1.5, "scale": 1, "offset": 0})
                plots.append({"title": f"{q}: {comp} vs {compare.reference}", "mode": "time", "signals": sigs})
        tabs.append({"name": f"vs {compare.reference}", "plots": plots})
        st = compare.stats()
        sections.append({"title": f"Errors against {compare.reference} ({compare.frame.upper()})",
                         "table": {"head": ["object", "quantity", "component", "RMS", "mean", "max |error|", "95% |error|", "t of max (s)"],
                                   "rows": [[r["object"], r["qty"], r["comp"]] + [f"{v:.6g}" if v is not None and v == v else "" for v in (r["rms"], r["mean"], r["max_abs"], r["p95_abs"], r["t_max_abs"])]
                                            for r in st.to_dict("records")]}})
    body = {"path": path, "format": fmt, "title": title or rec.name, "lang": lang, "tabs": tabs, "sections": sections}
    if fmt == "html":
        with open(path, "w", encoding="utf-8") as f:
            f.write(reports.build_html(rec._store, body))
    elif fmt == "pdf":
        reports.build_pdf(rec._store, body, path)
    else:
        reports.build_docx(rec._store, body, path)
    return path


_PUSHED = "error"


def _pushed_run(name: str, t: np.ndarray, y: np.ndarray):
    from svcore.models import Run, Signal
    r = Run(file_path=name, csv_display_name=name, time=np.asarray(t, dtype=np.float64))
    r.signals[_PUSHED] = Signal(name=_PUSHED, data=np.asarray(y, dtype=np.float64), time=np.asarray(t, dtype=np.float64))
    r.compute_metadata()
    return r
