"""RE1: the report as a document the user writes - Markdown with plots, tabs and values in it.

    # Flight 12
    Roll peaked at **{{ max(Roll) :.1f }} deg** at {{ tmax(Roll) }} s.
    [[Attitude.Roll and pitch]]
    $$\\omega_n = \\sqrt{k/m}$$

The app sends the text with every `[[...]]` / `{{...}}` replaced by a marker ⟦n⟧ and `items[n]` - what it
resolved it to (plot specs from plotSpec.ts, a value's formula with its signal ids, the notes, the
investigation's sections). Here: parse (a CommonMark subset, below), compute every value on all the data
(svcore/docfields.py), and emit the SAME blocks as the live page (preview and .html), PDF or Word.

The Markdown understood: headings (#), paragraphs, **bold**, *italic*, `code`, [links](url), ![pictures](file),
lists (-, *, 1.) with nesting by indent, tables (| a | b | + |---|), > quotes and > [!NOTE] / [!WARNING] /
[!FINDING] callouts, ``` code blocks, --- rules, \\newpage, $inline$ and $$display$$ math (matplotlib mathtext).
Raw HTML is shown as text (the page stays safe; PDF and Word can draw everything).
"""
import base64
import html
import io
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from app import report as R

log = logging.getLogger("signalviewer").getChild(__name__)

MARK = re.compile("\u27e6(\\d+)\u27e7")
CALLOUTS = ("NOTE", "TIP", "WARNING", "FINDING", "IMPORTANT")
HEB = re.compile("[\u0590-\u05FF]")

# ------------------------------------------------------------------------------------------------ parse

Inline = List[tuple]       # ("text", s) ("b", [..]) ("i", [..]) ("code", s) ("math", tex) ("link", [..], url)
                           # ("img", alt, src) ("field", n) ("br",)


def parse_inline(s: str) -> Inline:
    out: Inline = []
    buf: List[str] = []

    def flush():
        if buf:
            out.append(("text", "".join(buf)))
            buf.clear()

    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n and s[i + 1] in "\\`*_{}[]()#+-.!$|>~":
            buf.append(s[i + 1]); i += 2; continue
        if c == "`":
            j = s.find("`", i + 1)
            if j > i:
                flush(); out.append(("code", s[i + 1:j])); i = j + 1; continue
        if c == "\u27e6":
            m = MARK.match(s, i)
            if m:
                flush(); out.append(("field", int(m.group(1)))); i = m.end(); continue
        if c == "$" and i + 1 < n and s[i + 1] not in " $" and (i == 0 or s[i - 1] != "\\"):
            j = s.find("$", i + 1)
            if j > i + 1 and s[j - 1] != " " and not (j + 1 < n and s[j + 1].isdigit()):
                flush(); out.append(("math", s[i + 1:j])); i = j + 1; continue
        if c == "!" and s.startswith("![", i):
            m = re.match(r"!\[([^\]]*)\]\(([^)\s]+)\)", s[i:])
            if m:
                flush(); out.append(("img", m.group(1), m.group(2))); i += m.end(); continue
        if c == "[":
            m = re.match(r"\[([^\]]+)\]\(([^)\s]+)\)", s[i:])
            if m:
                flush(); out.append(("link", parse_inline(m.group(1)), m.group(2))); i += m.end(); continue
        if c in "*_" and s.startswith(c * 2, i):
            j = s.find(c * 2, i + 2)
            if j > i + 2:
                flush(); out.append(("b", parse_inline(s[i + 2:j]))); i = j + 2; continue
        if c in "*_" and i + 1 < n and s[i + 1] != " " and (c == "*" or i == 0 or not s[i - 1].isalnum()):
            j = i + 1
            while True:
                j = s.find(c, j)
                if j < 0 or (s[j - 1] != " " and not s.startswith(c * 2, j) and (c == "*" or j + 1 >= n or not s[j + 1].isalnum())):
                    break
                j += 1 if not s.startswith(c * 2, j) else 2
            if j > i + 1:
                flush(); out.append(("i", parse_inline(s[i + 1:j]))); i = j + 1; continue
        if c == "\n":
            flush(); out.append(("br",)); i += 1; continue
        buf.append(c); i += 1
    flush()
    return out


_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_LIST = re.compile(r"^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$")


def _cells(line: str) -> List[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    parts = re.split(r"(?<!\\)\|", line)
    return [p.strip().replace("\\|", "|") for p in parts]


def parse(text: str) -> List[dict]:
    """Blocks: heading, para, list, table, quote, code, math, hr, pagebreak."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: List[dict] = []
    para: List[str] = []
    i = 0

    def end_para():
        if para:
            joined = ""
            for k, ln in enumerate(para):
                hard = ln.endswith("  ") or ln.endswith("\\")
                piece = ln.rstrip().rstrip("\\") if hard else ln.strip()
                joined += piece + ("\n" if hard and k < len(para) - 1 else (" " if k < len(para) - 1 else ""))
            blocks.append({"t": "para", "text": joined.strip()})
            para.clear()

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("```") or s.startswith("~~~"):
            end_para()
            fence, body = s[:3], []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence):
                body.append(lines[i]); i += 1
            blocks.append({"t": "code", "text": "\n".join(body)})
            i += 1
            continue
        if s.startswith("$$"):
            end_para()
            rest = s[2:]
            if rest.endswith("$$") and len(rest) >= 2:
                blocks.append({"t": "math", "tex": rest[:-2].strip()}); i += 1; continue
            body = [rest] if rest else []
            i += 1
            while i < len(lines) and not lines[i].strip().endswith("$$"):
                body.append(lines[i].strip()); i += 1
            if i < len(lines):
                body.append(lines[i].strip()[:-2])
            blocks.append({"t": "math", "tex": " ".join(x for x in body if x).strip()})
            i += 1
            continue
        if not s:
            end_para(); i += 1; continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", s)
        if m:
            end_para(); blocks.append({"t": "heading", "level": len(m.group(1)), "text": m.group(2)}); i += 1; continue
        if s in ("\\newpage", "\\pagebreak"):
            end_para(); blocks.append({"t": "pagebreak"}); i += 1; continue
        if re.match(r"^(\*\s*){3,}$|^(-\s*){3,}$|^(_\s*){3,}$", s) and not para:
            blocks.append({"t": "hr"}); i += 1; continue
        if "|" in s and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]) and not para:
            head = _cells(s)
            aligns = []
            for c in _cells(lines[i + 1]):
                aligns.append("center" if c.startswith(":") and c.endswith(":") else "right" if c.endswith(":") else "left" if c.startswith(":") else "")
            rows = []
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(_cells(lines[i])); i += 1
            blocks.append({"t": "table", "head": head, "rows": rows, "align": aligns})
            continue
        if s.startswith(">"):
            end_para()
            body = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                body.append(re.sub(r"^\s*>\s?", "", lines[i])); i += 1
            kind = None
            if body:
                mm = re.match(r"^\[!(\w+)\]\s*(.*)$", body[0].strip())
                if mm and mm.group(1).upper() in CALLOUTS:
                    kind = mm.group(1).upper()
                    body = ([mm.group(2)] if mm.group(2) else []) + body[1:]
            blocks.append({"t": "quote", "kind": kind, "blocks": parse("\n".join(body))})
            continue
        m = _LIST.match(ln)
        if m and not para:
            items: List[dict] = []
            while i < len(lines):
                m = _LIST.match(lines[i])
                if m and items and not m.group(1) and m.group(2)[0].isdigit() != items[0]["ordered"]:
                    break                              # a numbered list right after a bulleted one: a list of its own
                if m:
                    items.append({"depth": len(m.group(1).replace("\t", "    ")) // 2, "ordered": m.group(2)[0].isdigit(),
                                  "text": m.group(3)})
                    i += 1
                    continue
                if lines[i].strip() and lines[i][:1] in " \t" and items:     # a continuation line of the item
                    items[-1]["text"] += " " + lines[i].strip(); i += 1; continue
                break
            blocks.append({"t": "list", "items": items})
            continue
        para.append(ln)
        i += 1
    end_para()
    return blocks


# ------------------------------------------------------------------------------------------------ resolve

def _block_item(b: dict, items: List[dict]) -> Optional[int]:
    """A paragraph that is one marker of a plot / tab / notes / sections item: drawn as a block."""
    if b["t"] != "para":
        return None
    m = MARK.fullmatch(b["text"].strip())
    if m and int(m.group(1)) < len(items) and items[int(m.group(1))].get("kind") != "value":
        return int(m.group(1))
    return None


def resolve(store, req: Dict, progress=None, for_html: bool = True) -> Tuple[List[dict], List[dict]]:
    """Parse the text and compute what it shows: (blocks, items) - each value item gets "text" / "error",
    each plots item its plot data (for the page, or for pictures)."""
    from svcore.docfields import evaluate_fields
    items: List[dict] = [dict(x) for x in (req.get("items") or [])]
    blocks = parse(str(req.get("text") or ""))
    values = [(k, it) for k, it in enumerate(items) if it.get("kind") == "value"]
    if values:
        for (k, it), res in zip(values, evaluate_fields([it for _, it in values], field_context(store))):
            items[k].update(res)
    plots = [it for it in items if it.get("kind") == "plots"]
    total, done = max(1, sum(len(it.get("plots") or []) for it in plots)), 0
    for it in plots:
        data = []
        for spec in it.get("plots") or []:
            pd = R.plot_data(store, {**spec, "notes": req.get("notes") or [], "lang": req.get("lang", "en")}, for_html=for_html)
            data.append(pd)
            done += 1
            if progress:
                progress(0.05 + 0.6 * done / total, "plots")
        it["data"] = data
    return blocks, items


def field_context(store):
    from svcore.analysis import compute
    from svcore.docfields import Context

    def condition(c: dict, rid: str) -> dict:
        res = store.evaluate_condition(str(c.get("text") or ""), str(c.get("exit") or ""), float(c.get("minDur") or 0),
                                       float(c.get("mergeGap") or 0), [rid])
        return res.get(rid) or {"error": "The condition could not be evaluated in this file."}

    def derive(expr: str, sigs, states):
        return compute("expr", sigs, {"expr": expr, "alignment": "linear"}, states)

    def is_state(sid: str) -> bool:
        try:
            return bool(store.is_state(sid))
        except Exception:                      # a closed signal is said by the read itself
            return False
    return Context(store.signal, is_state, condition, derive, list(store.runs) if hasattr(store, "runs") else [])


# ------------------------------------------------------------------------------------------------ math

_math_cache: Dict[Tuple[str, str, int], Any] = {}


def math_svg(tex: str, size: int = 14) -> str:
    """mathtext as inline SVG coloured by the text around it (light and dark)."""
    key = ("svg", tex, size)
    if key not in _math_cache:
        from matplotlib import mathtext
        from matplotlib.font_manager import FontProperties
        buf = io.BytesIO()
        try:
            mathtext.math_to_image("$%s$" % tex, buf, prop=FontProperties(size=size), format="svg")
            svg = buf.getvalue().decode("utf-8")
            svg = svg[svg.find("<svg"):]
            svg = re.sub(r"<metadata>.*?</metadata>", "", svg, flags=re.S)
            svg = re.sub(r'style="fill: ?#ffffff"', 'style="fill:none"', svg)      # the figure's white ground: the page's own shows
            svg = svg.replace("<svg ", '<svg class="math" fill="currentColor" role="img" aria-label="%s" ' % html.escape(tex, quote=True), 1)
            _math_cache[key] = svg
        except Exception as e:                 # a formula mathtext cannot read: said where it is
            _math_cache[key] = '<span class="field-err" title="%s">$%s$</span>' % (html.escape(str(e).split("\n")[0], quote=True), html.escape(tex))
    return _math_cache[key]


def math_png(tex: str, size: int = 13, dpi: int = 200) -> Optional[bytes]:
    key = ("png", tex, size)
    if key not in _math_cache:
        from matplotlib import mathtext
        from matplotlib.font_manager import FontProperties
        buf = io.BytesIO()
        try:
            mathtext.math_to_image("$%s$" % tex, buf, prop=FontProperties(size=size), dpi=dpi, format="png")
            _math_cache[key] = buf.getvalue()
        except Exception:
            _math_cache[key] = None
    return _math_cache[key]


# ------------------------------------------------------------------------------------------------ HTML

DOC_CSS = """
.doc{max-width:900px}
.doc h1,.doc h2,.doc h3,.doc h4{color:var(--ink-strong);line-height:1.25;margin:1.4em 0 .5em}
.doc h1{font-size:26px}.doc h2{font-size:20px}.doc h3{font-size:16.5px}.doc h4{font-size:15px}
.doc p,.doc li{max-width:75ch}.doc p{margin:0 0 .8em}
.doc code{font-family:"IBM Plex Mono",Consolas,monospace;font-size:.92em;background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:0 4px}
.doc pre{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px 12px;overflow:auto;direction:ltr;text-align:left}
.doc pre code{border:0;padding:0;background:none}
.doc blockquote{margin:0 0 1em;padding:6px 14px;border-inline-start:3px solid var(--line);color:var(--muted)}
.doc .callout{border-radius:6px;background:var(--panel);color:var(--ink);border-inline-start-width:4px}
.doc .callout-title{font-weight:600;margin:0 0 4px}
.doc .callout-NOTE,.doc .callout-TIP{border-inline-start-color:#3d8bfd}.doc .callout-WARNING,.doc .callout-IMPORTANT{border-inline-start-color:#e3a008}
.doc .callout-FINDING{border-inline-start-color:#c0392b}
.doc table.md{width:auto;min-width:40%;margin:4px 0 14px}.doc table.md td,.doc table.md th{white-space:normal;text-align:start;direction:inherit}
.doc table.md td:not(:first-child){direction:inherit;text-align:start}
.doc hr{border:0;border-top:1px solid var(--line);margin:22px 0}
.doc img.pic{max-width:100%;height:auto;border-radius:6px}
.doc .val{font-variant-numeric:tabular-nums;unicode-bidi:isolate;direction:ltr;font-weight:600;color:var(--ink-strong)}
.doc .field-err{unicode-bidi:isolate;color:#c0392b;background:rgba(192,57,43,.1);border-radius:4px;padding:0 4px;font-size:.92em}
.doc .math{vertical-align:middle;max-width:100%;height:auto}
.doc .mathblock{text-align:center;margin:10px 0 14px;direction:ltr}
.doc .mathblock .math{transform-origin:center}
.doc .pagebreak{break-after:page}
.doc .plot h2{margin:0 0 6px;font-size:16px}
@media print{.doc .pagebreak{border:0}}
"""


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def _err(text: str) -> str:
    return '<span class="field-err">⚠ %s</span>' % _esc(text)


def _img_src(src: str, base: str) -> Optional[str]:
    """A picture of the user's: a web address as it is, a file embedded (the page stays one offline file)."""
    if re.match(r"^(https?:|data:)", src):
        return src
    path = src if os.path.isabs(src) or not base else os.path.join(base, src)
    if not os.path.isfile(path):
        return None
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "svg": "svg+xml", "webp": "webp"}.get(ext)
    if not mime:
        return None
    with open(path, "rb") as f:
        return "data:image/%s;base64,%s" % (mime, base64.b64encode(f.read()).decode("ascii"))


def inline_html(nodes: Inline, items: List[dict], base: str = "") -> str:
    out = []
    for nd in nodes:
        k = nd[0]
        if k == "text":
            out.append(_esc(nd[1]))
        elif k == "b":
            out.append("<strong>%s</strong>" % inline_html(nd[1], items, base))
        elif k == "i":
            out.append("<em>%s</em>" % inline_html(nd[1], items, base))
        elif k == "code":
            out.append("<code>%s</code>" % _esc(nd[1]))
        elif k == "math":
            out.append(math_svg(nd[1]))
        elif k == "br":
            out.append("<br>")
        elif k == "link":
            url = nd[2] if re.match(r"^(https?:|mailto:|#)", nd[2]) else "#"
            out.append('<a href="%s">%s</a>' % (html.escape(url, quote=True), inline_html(nd[1], items, base)))
        elif k == "img":
            src = _img_src(nd[2], base)
            out.append('<img class="pic" alt="%s" src="%s">' % (html.escape(nd[1], quote=True), html.escape(src, quote=True))
                       if src else _err("picture not found: %s" % nd[2]))
        elif k == "field":
            it = items[nd[1]] if nd[1] < len(items) else {"error": "?"}
            if it.get("kind") != "value":
                out.append(_err(it.get("error") or it.get("label") or "a plot goes on a line of its own"))
            elif it.get("error"):
                out.append(_err("%s: %s" % (it.get("src") or "", it["error"])))
            elif it.get("text"):
                out.append('<span class="val" title="%s">%s</span>' % (html.escape(it.get("src") or "", quote=True), _esc(it["text"])))
    return "".join(out)


def _list_html(items: List[dict], k: int, depth: int, its: List[dict], base: str) -> Tuple[str, int]:
    tag = "ol" if items[k]["ordered"] else "ul"
    out = ["<%s>" % tag]
    while k < len(items) and items[k]["depth"] >= depth:
        it = items[k]
        if it["depth"] > depth:
            sub, k = _list_html(items, k, it["depth"], its, base)
            out[-1] = out[-1][:-5] + sub + "</li>" if out[-1].endswith("</li>") else out[-1] + sub
            continue
        out.append('<li dir="auto">%s</li>' % inline_html(parse_inline(it["text"]), its, base))
        k += 1
    out.append("</%s>" % tag)
    return "".join(out), k


def blocks_html(blocks: List[dict], items: List[dict], S: Dict, theme: str, plots_out: List[dict], base: str = "",
                words: Optional[Dict[str, str]] = None) -> str:
    """The document's body; every plot drawn goes into `plots_out` (the page's one tab, in order)."""
    words = words or {}
    out = []
    for b in blocks:
        t = b["t"]
        k = _block_item(b, items)
        if k is not None:
            out.append(_item_html(items[k], S, theme, plots_out))
        elif t == "heading":
            out.append('<h%d dir="auto">%s</h%d>' % (b["level"], inline_html(parse_inline(b["text"]), items, base), b["level"]))
        elif t == "para":
            out.append('<p dir="auto">%s</p>' % inline_html(parse_inline(b["text"]), items, base))
        elif t == "list":
            out.append(_list_html(b["items"], 0, b["items"][0]["depth"] if b["items"] else 0, items, base)[0])
        elif t == "table":
            al = b.get("align") or []

            def cell(tag, c, j):
                a = al[j] if j < len(al) and al[j] else ""
                return '<%s dir="auto"%s>%s</%s>' % (tag, ' style="text-align:%s"' % a if a else "", inline_html(parse_inline(c), items, base), tag)
            head = "".join(cell("th", c, j) for j, c in enumerate(b["head"]))
            rows = "".join("<tr>%s</tr>" % "".join(cell("td", c, j) for j, c in enumerate(r)) for r in b["rows"])
            out.append('<table class="md"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (head, rows))
        elif t == "quote":
            inner = blocks_html(b["blocks"], items, S, theme, plots_out, base, words)
            if b.get("kind"):
                title = words.get("callout" + b["kind"], b["kind"].title())
                out.append('<blockquote class="callout callout-%s" dir="auto"><p class="callout-title">%s</p>%s</blockquote>'
                           % (b["kind"], _esc(title), inner))
            else:
                out.append('<blockquote dir="auto">%s</blockquote>' % inner)
        elif t == "code":
            out.append("<pre><code>%s</code></pre>" % _esc(b["text"]))
        elif t == "math":
            out.append('<div class="mathblock">%s</div>' % math_svg(b["tex"], 17))
        elif t == "hr":
            out.append("<hr>")
        elif t == "pagebreak":
            out.append('<div class="pagebreak"></div>')
    return "".join(out)


def _item_html(it: dict, S: Dict, theme: str, plots_out: List[dict]) -> str:
    kind = it.get("kind")
    if it.get("error"):
        return '<p dir="auto">%s</p>' % _err(it["error"])
    if kind == "plots":
        parts = []
        for p in it.get("data") or []:
            if not p["signals"] and p["mode"] not in ("geo", "3d", "spec", "xyz", "env"):
                parts.append('<p dir="auto">%s</p>' % _err("%s: %s" % (p["title"] or S["plot"], S["notOpen"])))
                continue
            table = R._stats_table(p["signals"], S) if p["mode"] not in ("xy", "spec", "xyz", "geo", "3d") and it.get("table") != "none" else ""
            if it.get("table") == "only":
                parts.append('<section class="tableonly"><h3 dir="auto">%s</h3>%s</section>' % (_esc(p["title"]), table))
                continue
            parts.append(R.plot_section_html(p, len(plots_out), S, theme, table))
            plots_out.append(p)
        return "".join(parts)
    if kind == "sections":
        return R._sections_html(R._process_first(it.get("sections") or []))
    if kind == "notes":
        return R._notes_html(it.get("notes") or [], S).replace("<h2>%s</h2>" % S["notes"], "" if it.get("bare") else "<h2>%s</h2>" % S["notes"])
    return ""


def build_doc_html(store, req: Dict, progress=None) -> str:
    """The written report as the live page (the preview shows exactly this; the .html file is this)."""
    lang = req.get("lang", "en")
    S = R.STRINGS.get(lang, R.STRINGS["en"])
    blocks, items = resolve(store, req, progress, for_html=True)
    title = req.get("title") or next((b["text"] for b in blocks if b["t"] == "heading" and b["level"] == 1), "") or "Signal Viewer report"
    if blocks and blocks[0]["t"] == "heading" and blocks[0]["level"] == 1:
        blocks = blocks[1:]                      # the first heading is the page's title (its header)
    plots: List[dict] = []
    body = blocks_html(blocks, items, S, req.get("theme", "light"), plots, req.get("base") or "", req.get("words") or {})
    for p in plots:
        for s in p["signals"]:
            s.pop("stats", None)
    payload_tabs = [{"name": "", "plots": [{k: v for k, v in p.items() if k not in ("spec", "xyz", "geo_png", "geo_html")} for p in plots]}]
    replay = R._replay(req.get("replay")) if plots else None
    payload = {"lang": lang, "strings": {"toggle": S["toggle"], **({k: S[k] for k in ("rpPlay", "rpPause", "rpStory", "rpStoryHint", "rpStoryPrev", "rpStoryNext", "rpStoryStay")} if replay else {})},
               "tabs": payload_tabs, **({"replay": replay} if replay else {})}
    return R.fill_page({**req, "title": title}, S, payload, replay, intro="", nav="",
                       panes='<div class="tabpane doc">%s</div>' % body, summary="", css=DOC_CSS)


# ------------------------------------------------------------------------------------------------ text (PDF / Word)

def plain(nodes: Inline, items: List[dict], math: bool = True) -> str:
    """The text of a line as PDF draws it (bold / italic dropped; math kept as $..$ for mathtext)."""
    out = []
    for nd in nodes:
        k = nd[0]
        if k in ("text", "code"):
            out.append(nd[1])
        elif k in ("b", "i", "link"):
            out.append(plain(nd[1], items, math))
        elif k == "math":
            out.append("$%s$" % nd[1] if math else nd[1])
        elif k == "br":
            out.append("\n")
        elif k == "img":
            out.append("[%s]" % (nd[1] or nd[2]))
        elif k == "field":
            it = items[nd[1]] if nd[1] < len(items) else {}
            if it.get("kind") != "value":
                out.append("[%s]" % (it.get("error") or "-"))
            elif it.get("error"):
                out.append("[%s: %s]" % (it.get("src") or "", it["error"]))
            else:
                out.append(it.get("text") or "")
    return "".join(out)


def _plain_err(it: dict) -> str:
    return "⚠ " + str(it.get("error"))


# ------------------------------------------------------------------------------------------------ PDF

def build_doc_pdf(store, req: Dict, path: str, progress=None):
    """A4 pages that flow: text, lists, tables, math, the plots with their statistics."""
    import textwrap
    plt = R._pyplot()
    from matplotlib.backends.backend_pdf import PdfPages
    lang = req.get("lang", "en")
    S = R.STRINGS.get(lang, R.STRINGS["en"])
    blocks, items = resolve(store, req, progress, for_html=False)
    title = req.get("title") or next((b["text"] for b in blocks if b["t"] == "heading" and b["level"] == 1), "") or "Signal Viewer report"
    ink, muted = "#0f1822", "#5a6979"
    PT = 1 / (11.69 * 72)                       # one point in figure height
    TOP, BOTTOM = 0.93, 0.07
    class Flow:                                  # where the next line goes: the page being drawn and the height on it
        fig: Any = None
        y: float = TOP
        n: int = 0
    st = Flow()

    def rtl_of(text: str) -> bool:
        m = re.search(r"[A-Za-z\u0590-\u05FF]", text)
        return bool(m and HEB.match(m.group(0)))

    def new_page():
        if st.fig is not None:
            pdf.savefig(st.fig); plt.close(st.fig)
        st.n += 1
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.text(0.1, 0.965, R._bidi(title), ha="left", fontsize=8, color=muted)
        fig.text(0.9, 0.965, R._bidi("%s %d" % (S["page"], st.n)), ha="right", fontsize=8, color=muted)
        st.fig, st.y = fig, TOP

    def need(h: float):
        if st.fig is None or st.y - h < BOTTOM:
            new_page()

    def text(s: str, size: float = 10.5, weight: str = "normal", color: str = ink, indent: float = 0.0, family: Optional[str] = None,
             gap: float = 0.4):
        width = max(20, int((0.8 - indent) * 8.27 * 72 / (0.52 * size)))
        for para in s.split("\n"):
            rtl = rtl_of(para)
            # a formula is never split between lines: its spaces held while the line is wrapped
            held = re.sub(r"\$[^$]+\$", lambda m: m.group(0).replace(" ", "\u00a0"), para)
            for line in [x.replace("\u00a0", " ") for x in textwrap.wrap(held, width, break_long_words=False)] or [""]:
                h = size * 1.45 * PT
                need(h)
                x, ha = (0.9 - indent, "right") if rtl else (0.1 + indent, "left")
                if rtl and HEB.search(line) and re.search(r"\$[^$]+\$", line):
                    # matplotlib's math layout has no Hebrew letters: the words and the formulas drawn one after
                    # another from the right, each by its own font
                    fig = st.fig
                    r = fig.canvas.get_renderer()
                    for part in [x for x in re.split(r"(\$[^$]+\$)", line) if x.strip()]:
                        try:
                            tx = fig.text(x, st.y, part.strip() if part.startswith("$") else part, ha="right", va="top", fontsize=size, weight=weight, color=color)
                            x -= tx.get_window_extent(r).width / fig.bbox.width + (0.004 if part.startswith("$") else 0)
                        except Exception:              # a formula mathtext cannot read: as text
                            tx.set_text(part.replace("$", ""))
                    st.y -= h
                    continue
                try:
                    st.fig.text(x, st.y, R._bidi(line), ha=ha, va="top", fontsize=size, weight=weight, color=color, family=family)
                except Exception:                     # a formula mathtext cannot read: the line without it
                    st.fig.text(x, st.y, R._bidi(line.replace("$", "")), ha=ha, va="top", fontsize=size, weight=weight, color=color)
                st.y -= h
        st.y -= size * gap * PT

    def table(head: List[str], rows: List[List[str]], size: float = 8.5):
        h = (len(rows) + 1) * size * 2.0 * PT
        need(min(h, TOP - BOTTOM))
        rtl = any(rtl_of(c) for c in head)
        ncol = max(len(head), max((len(r) for r in rows), default=0))
        hd = (head + [""] * ncol)[:ncol]
        cells = [(r + [""] * ncol)[:ncol] for r in rows] or [[""] * ncol]
        if rtl:
            hd, cells = hd[::-1], [r[::-1] for r in cells]
        h = min(h, st.y - BOTTOM)
        tax = st.fig.add_axes((0.1, st.y - h, 0.8, h)); tax.axis("off")
        tbl = tax.table(cellText=[[R._bidi(c) for c in r] for r in cells], colLabels=[R._bidi(c) for c in hd], loc="upper center", cellLoc="center")
        tbl.auto_set_font_size(False); tbl.set_fontsize(size); tbl.scale(1, 1.25)
        for (r, _c), cl in tbl.get_celld().items():
            cl.set_edgecolor("#d5dce4")
            if r == 0:
                cl.set_facecolor("#eef2f5"); cl.set_text_props(weight="bold", color=ink)
        st.y -= h + 10 * PT

    def plot(p: dict, with_table: str):
        h = 0.34
        if with_table != "only":
            need(h + 0.05)
            text(p["title"] or S["plot"], 12, "bold", gap=0.2)
            ax = st.fig.add_axes((0.1, st.y - h + 0.02, 0.8, h - 0.04))
            if p.get("geo_png"):
                ax.imshow(R._png_array(p["geo_png"])); ax.set_axis_off()
            else:
                R.draw_axes(ax, p, "light")
            st.y -= h + 6 * PT
            if p.get("caption"):
                text(p["caption"], 9.5, color=muted)
        else:
            text(p["title"] or S["plot"], 11, "bold", gap=0.2)
        rows = [s for s in p["signals"] if s.get("stats")]
        if rows and p["mode"] not in ("xy",) and with_table != "none":
            cols = [S["signal"], S["min"], S["max"], S["mean"], S["rms"], S["std"]]
            table(cols, [[s["label"]] + ["" if s["stats"].get(k) is None else "%.6g" % s["stats"][k] for k in ("min", "max", "mean", "rms", "std")]
                         for s in rows])

    def walk(bs: List[dict], indent: float = 0.0, color: str = ink):
        for b in bs:
            t = b["t"]
            k = _block_item(b, items)
            if k is not None:
                it = items[k]
                if it.get("error"):
                    text(_plain_err(it), color="#c0392b", indent=indent)
                elif it.get("kind") == "plots":
                    for p in it.get("data") or []:
                        if p["signals"] or p.get("env") is not None or p.get("geo_png"):
                            plot(p, it.get("table") or "")
                elif it.get("kind") == "sections":
                    for sec in R._process_first(it.get("sections") or []):
                        text(str(sec.get("title") or ""), 13, "bold", gap=0.3)
                        for line in R._section_lines(sec):
                            text(line, 9.5, indent=indent, gap=0.1)
                elif it.get("kind") == "notes":
                    if not it.get("bare"):
                        text(S["notes"], 13, "bold", gap=0.3)
                    for nt in sorted(it.get("notes") or [], key=lambda n: n.get("t") or 0):
                        text("•  %s  %s" % (R._note_when(nt), nt.get("text", "")), 10, indent=indent, gap=0.1)
                continue
            if t == "heading":
                text(plain(parse_inline(b["text"]), items), {1: 20, 2: 16, 3: 13.5}.get(b["level"], 12), "bold", gap=0.5)
            elif t == "para":
                text(plain(parse_inline(b["text"]), items), indent=indent, color=color)
            elif t == "list":
                num: Dict[int, int] = {}
                for it in b["items"]:
                    num[it["depth"]] = num.get(it["depth"], 0) + 1
                    for d in [d for d in num if d > it["depth"]]:
                        num.pop(d)
                    mark = "%d." % num[it["depth"]] if it["ordered"] else "•"
                    text("%s  %s" % (mark, plain(parse_inline(it["text"]), items)), indent=indent + 0.03 * (it["depth"] + 1), gap=0.1, color=color)
                st.y -= 4 * PT
            elif t == "table":
                table([plain(parse_inline(c), items, False) for c in b["head"]], [[plain(parse_inline(c), items, False) for c in r] for r in b["rows"]])
            elif t == "quote":
                if b.get("kind"):
                    text((req.get("words") or {}).get("callout" + b["kind"], b["kind"].title()), 10.5, "bold", indent=indent + 0.03, gap=0.1)
                walk(b["blocks"], indent + 0.03, muted)
            elif t == "code":
                text(b["text"], 9, family="monospace", indent=indent + 0.02)
            elif t == "math":
                text("$%s$" % b["tex"], 14)
            elif t == "hr":
                need(12 * PT)
                st.fig.add_artist(plt.Line2D([0.1, 0.9], [st.y - 4 * PT] * 2, color="#d5dce4", lw=0.8))
                st.y -= 12 * PT
            elif t == "pagebreak":
                st.y = BOTTOM - 1

    with PdfPages(path) as pdf:
        new_page()
        if not (blocks and blocks[0]["t"] == "heading" and blocks[0]["level"] == 1):
            text(title, 22, "bold", gap=0.3)
        walk(blocks)
        pdf.savefig(st.fig); plt.close(st.fig)


# ------------------------------------------------------------------------------------------------ Word

def build_doc_docx(store, req: Dict, path: str, progress=None):
    try:
        import docx  # noqa: F401
    except ImportError:
        raise R.ReportNeedsExtra(R.missing("Word reports", "reports")) from None
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor
    lang = req.get("lang", "en")
    S = R.STRINGS.get(lang, R.STRINGS["en"])
    words = req.get("words") or {}
    blocks, items = resolve(store, req, progress, for_html=False)
    base = req.get("base") or ""
    doc = Document()

    def rtlize(par, text: str):
        m = re.search(r"[A-Za-z\u0590-\u05FF]", text)
        if m and HEB.match(m.group(0)):            # each paragraph its own direction, as the page does
            ppr = par._p.get_or_add_pPr()
            b = OxmlElement("w:bidi"); b.set(qn("w:val"), "1"); ppr.append(b)
            par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for r in par.runs:
                rpr = r._r.get_or_add_rPr()
                rt = OxmlElement("w:rtl"); rt.set(qn("w:val"), "1"); rpr.append(rt)
        return par

    def runs(par, nodes: Inline, bold=False, italic=False):
        for nd in nodes:
            k = nd[0]
            if k == "text":
                r = par.add_run(nd[1]); r.bold, r.italic = bold or None, italic or None
            elif k == "b":
                runs(par, nd[1], True, italic)
            elif k == "i":
                runs(par, nd[1], bold, True)
            elif k == "link":
                runs(par, nd[1], bold, italic)
            elif k == "code":
                r = par.add_run(nd[1]); r.font.name = "Consolas"
            elif k == "br":
                par.add_run().add_break()
            elif k == "math":
                png = math_png(nd[1], 12)
                if png:
                    par.add_run().add_picture(io.BytesIO(png), height=Pt(13))
                else:
                    par.add_run("$%s$" % nd[1])
            elif k == "img":
                src = _img_src(nd[2], base)
                if src and src.startswith("data:image/") and ";base64," in src and "svg" not in src:
                    par.add_run().add_picture(io.BytesIO(base64.b64decode(src.split(",", 1)[1])), width=Inches(6.0))
                else:
                    par.add_run("[%s]" % (nd[1] or nd[2]))
            elif k == "field":
                r = par.add_run(plain([nd], items))
                it = items[nd[1]] if nd[1] < len(items) else {}
                if it.get("error") or it.get("kind") != "value":
                    r.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)
                else:
                    r.bold = True

    def para(nodes: Inline, style: Optional[str] = None):
        p = doc.add_paragraph(style=style) if style else doc.add_paragraph()
        runs(p, nodes)
        return rtlize(p, plain(nodes, items))

    def small_table(head: List[str], rows: List[List[str]]):
        t = doc.add_table(rows=1, cols=max(1, len(head)))
        t.style = "Light Grid Accent 1"
        for c, h in enumerate(head):
            t.rows[0].cells[c].text = h
        for r in rows:
            cells = t.add_row().cells
            for c, v in enumerate(r[:len(head)]):
                cells[c].text = v
        for row in t.rows:
            for cell in row.cells:
                for par in cell.paragraphs:
                    for r in par.runs:
                        r.font.size = Pt(9)

    def walk(bs: List[dict], quoted: bool = False):
        for b in bs:
            t = b["t"]
            k = _block_item(b, items)
            if k is not None:
                it = items[k]
                if it.get("error"):
                    p = doc.add_paragraph(); r = p.add_run(_plain_err(it)); r.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)
                elif it.get("kind") == "plots":
                    for p in it.get("data") or []:
                        if not (p["signals"] or p.get("env") is not None or p.get("geo_png")):
                            continue
                        rtlize(doc.add_heading(p["title"] or S["plot"], 3), p["title"] or "")
                        if it.get("table") != "only":
                            png = base64.b64decode(p["geo_png"]) if p.get("geo_png") else \
                                R.figure_bytes(R.render_figure(p, "light", size=(7, 5) if p["mode"] == "xyz" else (9, 3.6), dpi=170), "png")
                            doc.add_picture(io.BytesIO(png), width=Inches(6.3))
                            if p.get("caption"):
                                rtlize(doc.add_paragraph(p["caption"]), p["caption"])
                        rows = [s for s in p["signals"] if s.get("stats")]
                        if rows and p["mode"] != "xy" and it.get("table") != "none":
                            small_table([S["signal"], S["min"], S["max"], S["mean"], S["rms"], S["std"]],
                                        [[s["label"]] + ["" if s["stats"].get(c) is None else f"{s['stats'][c]:.6g}" for c in ("min", "max", "mean", "rms", "std")]
                                         for s in rows])
                elif it.get("kind") == "sections":
                    for sec in R._process_first(it.get("sections") or []):
                        rtlize(doc.add_heading(str(sec.get("title") or ""), 2), str(sec.get("title") or ""))
                        for line in str(sec.get("text") or "").split("\n"):
                            if line.strip():
                                rtlize(doc.add_paragraph(line), line)
                        for x in sec.get("items") or []:
                            rtlize(doc.add_paragraph(str(x), style="List Bullet"), str(x))
                        tb = sec.get("table")
                        if tb and tb.get("rows"):
                            small_table([str(h) for h in tb.get("head") or []], [[str(c) for c in r] for r in tb["rows"]])
                elif it.get("kind") == "notes":
                    if not it.get("bare"):
                        rtlize(doc.add_heading(S["notes"], 2), S["notes"])
                    for nt in sorted(it.get("notes") or [], key=lambda n: n.get("t") or 0):
                        s = f"{R._note_when(nt)}  {nt.get('text', '')}"
                        rtlize(doc.add_paragraph(s, style="List Bullet"), s)
                continue
            if t == "heading":
                nodes = parse_inline(b["text"])
                h = doc.add_heading(level=min(b["level"] - 1, 9) if b["level"] > 1 else 0)
                runs(h, nodes)
                rtlize(h, plain(nodes, items))
            elif t == "para":
                p = para(parse_inline(b["text"]), "Quote" if quoted else None)
            elif t == "list":
                for it in b["items"]:
                    style = ("List Number" if it["ordered"] else "List Bullet") + ("" if it["depth"] == 0 else " %d" % min(3, it["depth"] + 1))
                    para(parse_inline(it["text"]), style)
            elif t == "table":
                head = [plain(parse_inline(c), items, False) for c in b["head"]]
                tbl = doc.add_table(rows=1, cols=max(1, len(head)))
                tbl.style = "Light Grid Accent 1"
                for c, cell_text in enumerate(b["head"]):
                    runs(tbl.rows[0].cells[c].paragraphs[0], parse_inline(cell_text))
                for r in b["rows"]:
                    cells = tbl.add_row().cells
                    for c, cell_text in enumerate(r[:len(head)]):
                        runs(cells[c].paragraphs[0], parse_inline(cell_text))
                doc.add_paragraph()
            elif t == "quote":
                if b.get("kind"):
                    p = doc.add_paragraph()
                    r = p.add_run(words.get("callout" + b["kind"], b["kind"].title())); r.bold = True
                    rtlize(p, r.text)
                walk(b["blocks"], True)
            elif t == "code":
                p = doc.add_paragraph()
                r = p.add_run(b["text"]); r.font.name = "Consolas"; r.font.size = Pt(9)
            elif t == "math":
                eq = math_png(b["tex"], 15)
                p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if eq:
                    p.add_run().add_picture(io.BytesIO(eq), height=Pt(22))
                else:
                    p.add_run("$$%s$$" % b["tex"])
            elif t == "hr":
                doc.add_paragraph("―" * 30).alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif t == "pagebreak":
                doc.add_page_break()

    if not (blocks and blocks[0]["t"] == "heading" and blocks[0]["level"] == 1) and req.get("title"):
        rtlize(doc.add_heading(req["title"], 0), req["title"])
    walk(blocks)
    doc.save(path)


def build_doc(store, req: Dict, fmt: str, path: str, progress=None) -> Optional[str]:
    """One entry for the job: the page's text for html (written by the caller), else the file written here."""
    if fmt == "html":
        return build_doc_html(store, req, progress)
    if fmt == "pdf":
        build_doc_pdf(store, req, path, progress)
    elif fmt == "docx":
        build_doc_docx(store, req, path, progress)
    return None
