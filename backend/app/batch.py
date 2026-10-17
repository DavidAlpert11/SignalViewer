"""
Batch reports (T11b): one report per file from a template, without the app.

    python cli.py report --template "ArduPilot · Full review" --out reports/ logs/*.bin

The template is matched to each file with the same code the app uses (svcore/templates.py), and
the report is drawn by the same builders (app/report.py) - so a batch report shows what opening
the template on that file in the app and making a report would show.
"""

import logging
import contextlib
import json
import os
import re
import sys
from typing import Dict, List, Optional

from svcore import templates as tplm

log = logging.getLogger("signalviewer").getChild(__name__)

FORMATS = {"html": ".html", "pdf": ".pdf", "docx": ".docx"}


class BatchError(ValueError):
    pass


def all_templates() -> List[dict]:
    """Built-in templates + the user's (the app's templates folder)."""
    from app import prefs
    mine = []
    try:
        mine = prefs.list_templates()
    except Exception:                      # an unreadable folder: the built-in ones still work
        log.warning("the templates folder could not be read", exc_info=True)
    return tplm.builtin_templates() + mine


def find_template(ref: str, all_: List[dict]) -> dict:
    """A template by file (.json), id, or name (case-insensitive; a unique start of a name also works)."""
    if ref.lower().endswith(".json") and os.path.isfile(ref):
        with open(ref, encoding="utf-8") as f:
            t = json.load(f)
        t = t["templates"][0] if isinstance(t, dict) and "templates" in t else t      # an export file: its first
        t.setdefault("id", "file:" + os.path.basename(ref))
        return t
    low = ref.strip().lower()
    for key in ("id", "name"):
        hit = [t for t in all_ if str(t.get(key, "")).lower() == low]
        if hit:
            return hit[0]
    hit = [t for t in all_ if str(t.get("name", "")).lower().startswith(low)]
    if len(hit) == 1:
        return hit[0]
    names = ", ".join(f'"{t["name"]}"' for t in (hit or all_)[:12] if not str(t.get("name", "")).startswith("@"))
    raise BatchError(f'No single template matches "{ref}". ' + (f"Did you mean: {names}" if hit else f"Some of them: {names}"))


def _report_tabs(resolved: dict) -> List[dict]:
    """Resolved template tabs -> the report's plot specs (what plotSpec.ts sends from the app)."""
    out = []
    for tab in resolved["tabs"]:
        plots = []
        for p in tab["plots"]:
            mode = p.get("mode") or "time"
            if mode == "3d":
                continue                                     # the globe has no report drawing
            xs = p.get("xSignal")
            plots.append({
                "title": p.get("title") or "", "caption": p.get("caption") or "",
                "mode": "xy" if mode == "geo" else mode, "xSignal": xs, "xLabel": xs.split("/", 1)[-1] if xs else "",
                "xyAlign": p.get("xyAlign") or "linear", "fftWindow": p.get("fftWindow") or "hanning",
                "fftMethod": p.get("fftMethod") or "fft", "fftLog": p.get("fftLog", True), "xyzEqual": True, "xyzFlipZ": False,
                "range": None, "specN": p.get("specN"),
                "signals": [{"id": s["sig"], "label": s.get("label") or s["sig"].split("/", 1)[-1], "color": s["color"],
                             "width": s.get("width") or 1.5, "scale": s.get("scale", 1) if s.get("scale") is not None else 1,
                             "offset": s.get("offset") or 0, "state": bool(s.get("state")), "tOffset": s.get("tOffset") or 0,
                             "limits": s.get("limits")} for s in p["signals"]],
            })
        if plots:
            out.append({"name": tab.get("name", ""), "plots": plots})
    return out


def _target(out_dir: str, path: str, ext: str, taken: set) -> str:
    stem = re.sub(r'[\\/:*?"<>|]+', "_", os.path.splitext(os.path.basename(path))[0]) or "report"
    name, k = stem + ext, 2
    while name.lower() in taken:
        name, k = f"{stem} ({k}){ext}", k + 1
    taken.add(name.lower())
    return os.path.join(out_dir, name)


def batch_reports(template_ref: str, files: List[str], out_dir: str, fmt: str = "html", lang: str = "en",
                  theme: str = "light", title: Optional[str] = None, log=print) -> List[Dict]:
    """One report per file. Returns [{file, report?, tabs, plots, missing, error?}]; a file that
    cannot be read or has nothing the template asks for is reported and skipped, not fatal."""
    from app import report as reports
    from app.store import Store

    ext = FORMATS.get(fmt)
    if not ext:
        raise BatchError("--format must be html, pdf or docx.")
    all_ = all_templates()
    t = find_template(template_ref, all_)
    e = tplm.expand(t, all_)
    if e["generators"] and not e["tabs"]:
        raise BatchError(f'"{t["name"]}" makes its tabs from the files shown in the app (quick look, compare, map); '
                         "choose a template with its own tabs.")
    os.makedirs(out_dir, exist_ok=True)
    tname = t["name"][1:] if str(t.get("name", "")).startswith("@") else t.get("name", "")
    results, taken = [], set()
    for path in files:
        store = Store()                                       # one file at a time: a fresh, empty store
        res: Dict = {"file": path}
        try:
            with contextlib.redirect_stdout(sys.stderr):      # the readers print progress
                store.open_file(os.path.abspath(path))
            runs = store.list()
            bind = tplm.auto_bind(e, runs)
            resolved = tplm.fill_colors(tplm.resolve(t, all_, bind, runs))
            tabs = _report_tabs(resolved)
            res.update(tabs=len(tabs), plots=sum(len(x["plots"]) for x in tabs), missing=resolved["missing"])
            if not tabs:
                res["error"] = "none of the template's signals are in this file"
                log(f"skip {path}: {res['error']}")
                results.append(res)
                continue
            target = _target(out_dir, path, ext, taken)
            body = {"path": target, "format": fmt, "lang": lang, "theme": theme, "notes": [], "intro": "", "summary": "",
                    "title": title or f"{os.path.basename(path)} · {tname}", "tabs": tabs}
            if fmt == "html":
                with open(target, "w", encoding="utf-8") as f:
                    f.write(reports.build_html(store, body))
            elif fmt == "pdf":
                reports.build_pdf(store, body, target)
            else:
                reports.build_docx(store, body, target)
            res["report"] = target
            log(f"{target}: {res['plots']} plots" + (f" ({len(res['missing'])} signals not in the file)" if res["missing"] else ""))
        except Exception as ex:                              # a bad file must not stop the batch
            res["error"] = str(ex) or ex.__class__.__name__
            log(f"skip {path}: {res['error']}")
        results.append(res)
    return results
