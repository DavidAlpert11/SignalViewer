"""RE3 (owner, 2026-11-21): the written report in LaTeX - "full LaTeX like Overleaf, and everything offline".

Two ways, one text (ws.report.doc.text - nothing new is saved; which way is the text's own first line):

  Markdown (as before)  + ```latex blocks written as they are, any formula ($...$, $$...$$, align, matrices) - the
                        page, PDF and Word draw them by the computer's TeX when matplotlib cannot (svcore/latex.py);
                        exported as a LaTeX project (.zip: main.tex, figures/, latexmkrc - opens in Overleaf) or
                        typeset to a PDF by the computer's LaTeX.
  A LaTeX document      a text that starts with \\documentclass is LaTeX through and through; [[tab.plot]], [[parts]]
                        and {{ values }} work in it as in Markdown (the app writes each as LaTeX: a figure, the part's
                        sections and tables, the number); the preview is the PDF, TeX's errors are said at the line
                        of the text.

Plots go in as vector PDFs drawn by the same code as the PDF report (report.draw_axes) - every point counts.
"""
import base64
import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from app import report as R
from app.reportdoc import MARK, _block_item, _img_src, parse, parse_inline, resolve
from svcore import latex as TX

HEB = re.compile("[\u0590-\u05FF]")
DOC_START = re.compile(r"^\s*(%[^\n]*\n\s*)*\\documentclass", re.S)
HEB_FONTS = ("David CLM", "Frank Ruehl CLM", "Noto Serif Hebrew", "Noto Sans Hebrew", "Times New Roman", "Arial", "FreeSerif", "DejaVu Sans")
HEB_FILE = "FreeSerif.otf"          # by file: in TeX Live (gnu-freefont) and in the app's built-in bundle (RE4)


def is_latex_doc(text: str) -> bool:
    """A report written in LaTeX: its first line that is not a comment is \\documentclass."""
    return bool(DOC_START.match(text or ""))


# ------------------------------------------------------------------------------------------------ escaping

_SPECIAL = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "#": r"\#", "%": r"\%",
            "_": r"\_", "^": r"\textasciicircum{}", "~": r"\textasciitilde{}"}
# pdfLaTeX has no Unicode fonts: the symbols an engineering report uses, written as LaTeX
_PDF_UNI = {"°": r"\textdegree{}", "±": r"\ensuremath{\pm}", "µ": r"\ensuremath{\mu}", "μ": r"\ensuremath{\mu}",
            "≤": r"\ensuremath{\le}", "≥": r"\ensuremath{\ge}", "≈": r"\ensuremath{\approx}", "×": r"\ensuremath{\times}",
            "÷": r"\ensuremath{\div}", "−": "-", "…": r"\ldots{}", "→": r"\ensuremath{\rightarrow}", "←": r"\ensuremath{\leftarrow}",
            "↑": r"\ensuremath{\uparrow}", "↓": r"\ensuremath{\downarrow}", "⚠": "(!)", "✓": r"\ensuremath{\checkmark}",
            "Δ": r"\ensuremath{\Delta}", "σ": r"\ensuremath{\sigma}", "Ω": r"\ensuremath{\Omega}", "²": r"\textsuperscript{2}",
            "³": r"\textsuperscript{3}", "·": r"\textperiodcentered{}", "–": "--", "—": "---", "•": r"\textbullet{}",
            "\u00a0": "~", "‘": "`", "’": "'", "“": "``", "”": "''"}


def esc(s: str, unicode: bool = True) -> str:
    out = "".join(_SPECIAL.get(c, c) for c in s)
    if not unicode:
        out = "".join(_PDF_UNI.get(c, c if ord(c) < 256 else "?") for c in out)
    return out


class Ctx:
    """One LaTeX project being written: its folder, the figures made, the language and the engine."""

    def __init__(self, folder: str, lang: str, engine: str, S: Dict, words: Dict[str, str], base: str = "",
                 assets: Optional[Dict[str, dict]] = None, convert: bool = False):
        self.folder, self.lang, self.engine, self.S, self.words, self.base = folder, lang, engine, S, words, base
        self.assets = assets or {}
        self.unicode = engine != "pdflatex"
        self.bidi = False                         # polyglossia set up (Hebrew in the report): mark the other language
        self.convert = convert                    # Markdown -> LaTeX source for the editor: no data, no files
        self.n = 0
        if folder and not convert:
            os.makedirs(os.path.join(folder, "figures"), exist_ok=True)

    def name(self, stem: str, ext: str) -> str:
        self.n += 1
        return "figures/%s-%d%s" % (stem, self.n, ext)

    def text(self, s: str) -> str:
        """Plain text: escaped, and the other language's words marked (polyglossia) so each runs its own way."""
        if not self.unicode:
            return esc(s, False)
        if not self.bidi:
            return esc(s)
        if self.lang == "he":
            parts = re.split(r"([A-Za-z][A-Za-z0-9_.:/\-]*(?:[ ]+[A-Za-z0-9][A-Za-z0-9_.:/\-]*)*)", s)
            return "".join(("\\textenglish{%s}" % esc(p)) if k % 2 and not self.convert else esc(p) for k, p in enumerate(parts))
        parts = re.split(r"([\u0590-\u05FF][\u0590-\u05FF\"'\u05f3\u05f4\- ]*[\u0590-\u05FF]|[\u0590-\u05FF])", s)
        return "".join(("\\texthebrew{%s}" % esc(p)) if k % 2 and not self.convert else esc(p) for k, p in enumerate(parts))


# ------------------------------------------------------------------------------------------------ blocks

def inline_tex(nodes, items: List[dict], ctx: Ctx) -> str:
    out = []
    for nd in nodes:
        k = nd[0]
        if k == "text":
            out.append(ctx.text(nd[1]))
        elif k == "b":
            out.append("\\textbf{%s}" % inline_tex(nd[1], items, ctx))
        elif k == "i":
            out.append("\\emph{%s}" % inline_tex(nd[1], items, ctx))
        elif k == "code":
            out.append("\\texttt{%s}" % esc(nd[1], ctx.unicode))
        elif k == "math":
            out.append("$%s$" % nd[1])
        elif k == "br":
            out.append("\\\\\n")
        elif k == "link":
            url = nd[2].replace("\\", "/").replace("%", "\\%").replace("#", "\\#")
            out.append("\\href{%s}{%s}" % (url, inline_tex(nd[1], items, ctx)))
        elif k == "img":
            out.append(picture(nd[2], nd[1], ctx, inline=True))
        elif k == "field":
            it = items[nd[1]] if nd[1] < len(items) else {"error": "?"}
            if ctx.convert:
                out.append("\u27e6%d\u27e7" % nd[1])
            elif it.get("kind") != "value":
                out.append("\\textcolor{red}{%s}" % esc("! " + str(it.get("error") or "a plot goes on a line of its own"), ctx.unicode))
            elif it.get("error"):
                out.append("\\textcolor{red}{%s}" % esc("! %s: %s" % (it.get("src") or "", it["error"]), ctx.unicode))
            elif it.get("text"):
                out.append(ctx.text(str(it["text"])))
    return "".join(out)


def picture(src: str, alt: str, ctx: Ctx, inline: bool = False) -> str:
    """A picture of the user's into figures/ (a pasted one, a file, a data URL); a web address stays a link."""
    if ctx.convert:
        return "\\includegraphics[width=%s]{%s}" % ("0.3\\linewidth" if inline else "\\linewidth", src)
    m = re.match(r"^asset:([\w-]+)$", src)
    if m and m.group(1) in ctx.assets:
        a = ctx.assets[m.group(1)]
        data, mime = base64.b64decode(re.sub(r"[^A-Za-z0-9+/=]", "", str(a.get("data") or ""))), str(a.get("mime") or "image/png")
    else:
        url = _img_src(src, ctx.base)
        if not url:
            return "\\textcolor{red}{%s}" % esc("! picture not found: " + src, ctx.unicode)
        if not url.startswith("data:"):
            return "\\url{%s}" % url
        head, b64 = url.split(",", 1)
        mime, data = head[5:].split(";")[0], base64.b64decode(b64)
    ext = {"image/png": ".png", "image/jpeg": ".jpg"}.get(mime)
    if not ext:                                   # gif / webp / svg: LaTeX reads PNG, JPEG and PDF - made a PNG
        try:
            from PIL import Image
            buf = io.BytesIO()
            Image.open(io.BytesIO(data)).convert("RGBA").save(buf, "PNG")
            data, ext = buf.getvalue(), ".png"
        except Exception:
            return "\\textcolor{red}{%s}" % esc("! a picture LaTeX cannot show: " + alt, ctx.unicode)
    rel = ctx.name("picture", ext)
    with open(os.path.join(ctx.folder, rel), "wb") as f:
        f.write(data)
    if inline:
        return "\\includegraphics[height=1.2em]{%s}" % rel
    return "\\begin{center}\\includegraphics[width=0.9\\linewidth,height=0.4\\textheight,keepaspectratio]{%s}\\end{center}" % rel


def _list_tex(items: List[dict], k: int, depth: int, its: List[dict], ctx: Ctx) -> Tuple[str, int]:
    env = "enumerate" if items[k]["ordered"] else "itemize"
    out = ["\\begin{%s}" % env]
    while k < len(items) and items[k]["depth"] >= depth:
        it = items[k]
        if it["depth"] > depth:
            sub, k = _list_tex(items, k, it["depth"], its, ctx)
            out.append(sub)
            continue
        out.append("  \\item %s" % inline_tex(parse_inline(it["text"]), its, ctx))
        k += 1
    out.append("\\end{%s}" % env)
    return "\n".join(out), k


def table_tex(head: List[str], rows: List[List[str]], aligns: List[str], items: List[dict], ctx: Ctx, cell_md: bool = True) -> str:
    ncol = max([len(head)] + [len(r) for r in rows]) or 1
    spec = "".join({"center": "c", "right": "r"}.get(aligns[j] if j < len(aligns) else "", "l") for j in range(ncol))
    cell = (lambda c: inline_tex(parse_inline(c), items, ctx)) if cell_md else (lambda c: ctx.text(str(c)))
    size = "\\small" if ncol <= 6 else "\\scriptsize"
    lines = ["{%s" % size, "\\begin{longtable}{%s}" % spec, "\\toprule",
             " & ".join("\\textbf{%s}" % cell(c) for c in (head + [""] * ncol)[:ncol]) + " \\\\", "\\midrule", "\\endhead"]
    for r in rows:
        lines.append(" & ".join(cell(c) for c in (r + [""] * ncol)[:ncol]) + " \\\\")
    lines += ["\\bottomrule", "\\end{longtable}}"]
    return "\n".join(lines)


def _plot_tex(it: dict, ctx: Ctx) -> str:
    plt = R._pyplot()
    S = ctx.S
    out = []
    for p in it.get("data") or []:
        if not p["signals"] and p["mode"] not in ("geo", "3d", "spec", "xyz", "env") and not p.get("geo_png"):
            out.append("\\textcolor{red}{%s}" % esc("! %s: %s" % (p["title"] or S["plot"], S["notOpen"]), ctx.unicode))
            continue
        title = ctx.text(p["title"] or S["plot"])
        if it.get("table") != "only":
            if p.get("geo_png"):
                rel = ctx.name("map", ".png")
                with open(os.path.join(ctx.folder, rel), "wb") as f:
                    f.write(base64.b64decode(p["geo_png"]))
            else:
                rel = ctx.name("plot", ".pdf")
                fig = plt.figure(figsize=(7.0, 3.3))
                ax = fig.add_axes((0.09, 0.14, 0.88, 0.78))
                try:
                    R.draw_axes(ax, p, "light")
                    fig.savefig(os.path.join(ctx.folder, rel))
                finally:
                    plt.close(fig)
            cap = title + (" --- " + ctx.text(p["caption"]) if p.get("caption") else "")
            out.append("\\begin{figure}[htbp]\n\\centering\n\\includegraphics[width=\\linewidth]{%s}\n\\caption{%s}\n\\end{figure}" % (rel, cap))
        rows = [s for s in p["signals"] if s.get("stats")]
        if rows and p["mode"] not in ("xy", "spec", "xyz", "geo", "3d") and it.get("table") != "none":
            if it.get("table") == "only":
                out.append("\\subsubsection*{%s}" % title)
            out.append(table_tex([S["signal"], S["min"], S["max"], S["mean"], S["rms"], S["std"]],
                                 [[s["label"]] + ["" if s["stats"].get(k) is None else "%.6g" % s["stats"][k] for k in ("min", "max", "mean", "rms", "std")]
                                  for s in rows], ["", "right", "right", "right", "right", "right"], [], ctx, cell_md=False))
    return "\n\n".join(out)


def _item_tex(it: dict, ctx: Ctx) -> str:
    kind = it.get("kind")
    if it.get("error"):
        return "\\textcolor{red}{%s}" % esc("! " + str(it["error"]), ctx.unicode)
    if kind == "plots":
        return _plot_tex(it, ctx)
    if kind == "sections":
        out = []
        for sec in R._process_first(it.get("sections") or []):
            out.append("\\subsection*{%s}" % ctx.text(str(sec.get("title") or "")))
            if sec.get("text"):
                out.append("\n\n".join(ctx.text(x) for x in str(sec["text"]).split("\n") if x.strip()))
            if sec.get("items"):
                out.append("\\begin{itemize}\n%s\n\\end{itemize}" % "\n".join("  \\item " + ctx.text(str(x)) for x in sec["items"]))
            tb = sec.get("table")
            if tb and tb.get("rows"):
                out.append(table_tex([str(h) for h in tb.get("head") or []], [[str(c) for c in r] for r in tb["rows"]], [], [], ctx, cell_md=False))
        return "\n\n".join(out)
    if kind == "notes":
        notes = sorted(it.get("notes") or [], key=lambda n: n.get("t") or 0)
        head = "" if it.get("bare") else "\\subsection*{%s}\n" % ctx.text(ctx.S["notes"])
        if not notes:
            return head
        return head + "\\begin{itemize}\n%s\n\\end{itemize}" % "\n".join(
            "  \\item \\textbf{%s} %s" % (esc(R._note_when(n), ctx.unicode), ctx.text(str(n.get("text") or ""))) for n in notes)
    return ""


CALLOUT_COLOR = {"NOTE": "blue!60!black", "TIP": "blue!60!black", "WARNING": "orange!80!black", "IMPORTANT": "orange!80!black", "FINDING": "red!70!black"}


def blocks_tex(blocks: List[dict], items: List[dict], ctx: Ctx, title_first: bool = True) -> str:
    out: List[str] = []
    for bi, b in enumerate(blocks):
        t = b["t"]
        k = _block_item(b, items) if not ctx.convert else None
        if k is not None:
            out.append(_item_tex(items[k], ctx))
            continue
        if ctx.convert and t == "para" and MARK.fullmatch(b["text"].strip()):
            out.append(b["text"].strip())               # a reference on its own line stays one
            continue
        if t == "heading":
            body = inline_tex(parse_inline(b["text"]), items, ctx)
            if b["level"] == 1 and bi == 0 and title_first:
                out.append("\\begin{center}{\\LARGE\\bfseries %s}\\end{center}" % body)
            else:
                cmd = {1: "section", 2: "section", 3: "subsection", 4: "subsubsection"}.get(b["level"], "paragraph")
                out.append("\\%s{%s}" % (cmd, body))
        elif t == "para":
            nodes = parse_inline(b["text"])
            if len(nodes) == 1 and nodes[0][0] == "img":
                out.append(picture(nodes[0][2], nodes[0][1], ctx))
            else:
                out.append(inline_tex(nodes, items, ctx))
        elif t == "list":
            out.append(_list_tex(b["items"], 0, b["items"][0]["depth"] if b["items"] else 0, items, ctx)[0])
        elif t == "table":
            out.append(table_tex(b["head"], b["rows"], b.get("align") or [], items, ctx))
        elif t == "quote":
            inner = blocks_tex(b["blocks"], items, ctx, False)
            if b.get("kind"):
                title = ctx.text(ctx.words.get("callout" + b["kind"], b["kind"].title()))
                col = CALLOUT_COLOR.get(b["kind"], "gray")
                out.append("\\begin{svcallout}{%s}{%s}\n%s\n\\end{svcallout}" % (col, title, inner))
            else:
                out.append("\\begin{quote}\n%s\n\\end{quote}" % inner)
        elif t == "code":
            if (b.get("lang") or "").lower() in ("latex", "tex"):
                out.append(b["text"])                   # LaTeX written as it is
            else:
                env = "verbatim"
                v = "\\begin{%s}\n%s\n\\end{%s}" % (env, b["text"], env)
                out.append("\\begin{english}\n%s\n\\end{english}" % v if ctx.bidi and ctx.lang == "he" and not ctx.convert else v)
        elif t == "math":
            out.append(b["tex"] if TX.is_display_env(b["tex"]) else "\\[ %s \\]" % b["tex"])
        elif t == "hr":
            out.append("\\par\\noindent\\rule{\\linewidth}{0.4pt}\\par")
        elif t == "pagebreak":
            out.append("\\newpage")
    return "\n\n".join(x for x in out if x is not None)


# ------------------------------------------------------------------------------------------------ preamble

def preamble(lang: str, engine: str, title: str, hebrew: bool = False) -> str:
    """Packages every TeX Live / MiKTeX basic install has (nothing to fetch offline); Hebrew (polyglossia, bidi) only
    when the report is in Hebrew or has Hebrew in it."""
    lines = ["% Made by Signal Viewer - a LaTeX project: main.tex, figures/ (plots as vector PDF).",
             "%% Compile with %s%s." % ({"xelatex": "XeLaTeX", "lualatex": "LuaLaTeX", "pdflatex": "pdfLaTeX"}[engine],
                                         " (Overleaf: Menu -> Compiler -> XeLaTeX)" if engine == "xelatex" else ""),
             "\\documentclass[11pt,a4paper]{article}"]
    if engine == "pdflatex":
        lines += ["\\usepackage[utf8]{inputenc}", "\\usepackage[T1]{fontenc}", "\\usepackage{lmodern}", "\\usepackage{textcomp}"]
    lines += ["\\usepackage[margin=2.2cm]{geometry}", "\\usepackage{amsmath,amssymb}", "\\usepackage{graphicx}",
              "\\usepackage{booktabs,longtable}", "\\usepackage[table]{xcolor}", "\\usepackage{hyperref}",
              "\\hypersetup{colorlinks=true,linkcolor=blue!50!black,urlcolor=blue!50!black}"]
    if engine != "pdflatex":
        lines += ["\\usepackage{fontspec}"]
    if engine != "pdflatex" and (hebrew or lang == "he"):     # hyperref before polyglossia (bidi must come after it)
        feat = "Script=Hebrew" + (",Renderer=HarfBuzz" if engine == "lualatex" else "")
        font = "\\IfFontExistsTF{%s}{\\newfontfamily\\hebrewfont{%s}[%s,BoldFont=FreeSerifBold.otf]}{\\newfontfamily\\hebrewfont{%s}[%s]}" % (
            HEB_FILE, HEB_FILE, feat, HEB_FONTS[-1], feat)
        for f in reversed(HEB_FONTS[:-1]):           # the first Hebrew font this computer has
            font = "\\IfFontExistsTF{%s}{\\newfontfamily\\hebrewfont{%s}[%s]}{%s}" % (f, f, feat, font)
        lines += ["\\usepackage{polyglossia}",
                  "\\setdefaultlanguage{%s}" % ("hebrew" if lang == "he" else "english"),
                  "\\setotherlanguage{%s}" % ("english" if lang == "he" else "hebrew"), font]
    lines += ["\\setlength{\\parindent}{0pt}", "\\setlength{\\parskip}{0.55em}",
              # a callout: a coloured rule above and below, its title in colour (#1 kept for the end: \\svcol)
              "\\newenvironment{svcallout}[2]{\\par\\noindent\\def\\svcol{#1}\\textcolor{\\svcol}{\\rule{\\linewidth}{0.6pt}}\\par\\nopagebreak"
              "\\textbf{\\textcolor{\\svcol}{#2}}\\par}{\\par\\nopagebreak\\noindent\\textcolor{\\svcol}{\\rule{\\linewidth}{0.6pt}}\\par}",
              "\\title{%s}" % title, "\\date{}"]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------------ the project

def _engine_for(req: Dict, text: str, local: bool) -> str:
    want = str(req.get("engine") or "")
    if want in TX.ENGINES or want == TX.BUILTIN:
        return want
    if not local:
        return "xelatex"                              # the project for Overleaf / another computer
    hebrew = bool(HEB.search(text)) or req.get("lang") == "he"
    e = TX.best_engine(unicode=True)
    if e == "pdflatex" and hebrew and TX.builtin():
        return TX.BUILTIN                             # pdfLaTeX has no Hebrew: the app's own XeLaTeX (Tectonic)
    if e == "pdflatex" and hebrew:
        raise TX.LatexError("Hebrew needs XeLaTeX or LuaLaTeX (in TeX Live / MiKTeX); only pdfLaTeX was found on this computer.")
    return e or "xelatex"


def write_project(store, req: Dict, folder: str, local: bool = True, progress=None) -> Tuple[str, str, Dict[int, int]]:
    """main.tex and figures/ in `folder`. Returns (main.tex path, engine, line map: main.tex line -> the text's line;
    only for a LaTeX document, where the user's lines are main.tex's)."""
    lang = req.get("lang", "en")
    S = R.STRINGS.get(lang, R.STRINGS["en"])
    text = str(req.get("text") or "")
    engine = _engine_for(req, text, local)
    flav = TX.flavour(engine)                        # the built-in Tectonic is XeLaTeX
    ctx = Ctx(folder, lang, flav, S, req.get("words") or {}, req.get("base") or "", req.get("assets") or {})
    linemap: Dict[int, int] = {}
    if is_latex_doc(text):
        ctx.bidi = ctx.unicode and bool(re.search(r"\\usepackage(\[[^\]]*\])?\{polyglossia\}", text)) and (lang == "he" or bool(HEB.search(text)))
        body = _latex_doc(store, req, ctx, linemap, progress)
    else:
        blocks, items = resolve(store, req, progress, for_html=False)
        hebrew = lang == "he" or bool(HEB.search(text)) or any(HEB.search(str(it.get("text") or "")) for it in items)
        ctx.bidi = ctx.unicode and hebrew
        title = req.get("title") or next((b["text"] for b in blocks if b["t"] == "heading" and b["level"] == 1), "") or "Signal Viewer report"
        body = preamble(lang, flav, esc(MARK.sub("", title), ctx.unicode), hebrew) + "\n\\begin{document}\n\n" + blocks_tex(blocks, items, ctx) + "\n\n\\end{document}\n"
    main = os.path.join(folder, "main.tex")
    with open(main, "w", encoding="utf-8") as f:
        f.write(body)
    with open(os.path.join(folder, "latexmkrc"), "w", encoding="utf-8") as f:     # Overleaf and latexmk pick the engine
        f.write("$pdf_mode = %d;\n" % {"xelatex": 5, "lualatex": 4, "pdflatex": 1}[flav])
    return main, engine, linemap


def _latex_doc(store, req: Dict, ctx: Ctx, linemap: Dict[int, int], progress=None) -> str:
    """A LaTeX document: each marker becomes LaTeX - a value its number, a plot a figure, a part its sections (the
    part's Markdown parsed and written as LaTeX) - line by line, so TeX's error line is found in the user's text."""
    text = str(req.get("text") or "")
    items: List[dict] = [dict(x) for x in (req.get("items") or [])]
    used = sorted({int(k) for k in MARK.findall(text) if int(k) < len(items)})
    blocks_of = [k for k in used if items[k].get("kind") != "value" and not (items[k].get("kind") == "part" and items[k].get("part") == "toc")]
    md = "\n\n".join("SVSEP%d\n\n\u27e6%d\u27e7" % (k, k) for k in blocks_of)
    blocks, items2 = resolve(store, {**req, "text": md, "items": items}, progress, for_html=False)
    per: Dict[int, List[dict]] = {}
    cur: Optional[int] = None
    for b in blocks:
        m = re.fullmatch(r"SVSEP(\d+)", b.get("text", "").strip()) if b["t"] == "para" else None
        if m:
            cur = int(m.group(1)); per[cur] = []; continue
        if cur is not None:
            per[cur].append(b)
    rep: Dict[int, str] = {}
    for k in used:
        it = items2[k]
        if it.get("kind") == "value":
            rep[k] = ("\\textcolor{red}{%s}" % esc("! %s: %s" % (it.get("src") or "", it["error"]), ctx.unicode)) if it.get("error") else ctx.text(str(it.get("text") or ""))
        elif it.get("kind") == "part" and it.get("part") == "toc":
            rep[k] = "\\tableofcontents"
        else:
            rep[k] = blocks_tex(per.get(k, []), items2, ctx, title_first=False)
    # pictures kept in the session: \includegraphics{asset:<id>} -> a file in figures/
    def asset(m):
        return m.group(1) + picture_file(m.group(2), ctx) + "}"
    out_lines: List[str] = []
    begun = False
    for i, line in enumerate(text.split("\n"), start=1):
        if not begun and "\\begin{document}" in line and not line.lstrip().startswith("%"):
            # what the app writes needs these: loaded unless the user's preamble has them - on the same line, so
            # TeX's line numbers stay the user's
            line = line.replace("\\begin{document}", NEEDS + "\\begin{document}", 1)
            begun = True
        line = re.sub(r"(\\includegraphics(?:\[[^\]]*\])?\{)asset:([\w-]+)\}", asset, line)
        new = MARK.sub(lambda m: rep.get(int(m.group(1)), ""), line)
        for piece in new.split("\n"):
            out_lines.append(piece)
            linemap[len(out_lines)] = i
    return "\n".join(out_lines) + "\n"


NEEDS = ("\\makeatletter" + "".join("\\@ifpackageloaded{%s}{}{\\usepackage%s{%s}}" % (p, o, p) for p, o in
                                    (("graphicx", ""), ("booktabs", ""), ("longtable", ""), ("xcolor", "[table]"), ("amsmath", ""), ("hyperref", "")))
         + "\\@ifundefined{svcallout}{\\newenvironment{svcallout}[2]{\\par\\noindent\\textbf{#2}\\par}{\\par}}{}\\makeatother")


def picture_file(aid: str, ctx: Ctx) -> str:
    a = ctx.assets.get(aid)
    if not a:
        return "asset-missing"
    rel = ctx.name("picture", ".jpg" if str(a.get("mime")) == "image/jpeg" else ".png")
    data = base64.b64decode(re.sub(r"[^A-Za-z0-9+/=]", "", str(a.get("data") or "")))
    if str(a.get("mime")) not in ("image/png", "image/jpeg"):
        from PIL import Image
        buf = io.BytesIO()
        Image.open(io.BytesIO(data)).convert("RGBA").save(buf, "PNG")
        data = buf.getvalue()
    with open(os.path.join(ctx.folder, rel), "wb") as f:
        f.write(data)
    return rel


def build_zip(store, req: Dict, path: str, progress=None) -> None:
    """The LaTeX project as one .zip (main.tex, figures/, latexmkrc) - Overleaf: New project -> Upload project."""
    with tempfile.TemporaryDirectory(prefix="sv-texzip-") as d:
        write_project(store, req, d, local=False, progress=progress)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _dirs, files in os.walk(d):
                for fn in sorted(files):
                    full = os.path.join(root, fn)
                    z.write(full, os.path.relpath(full, d).replace(os.sep, "/"))


def build_pdf(store, req: Dict, path: str, progress=None) -> None:
    """The report typeset by this computer's LaTeX. A TeX error: LatexError said at the line of the text."""
    with tempfile.TemporaryDirectory(prefix="sv-texpdf-") as d:
        main, engine, linemap = write_project(store, req, d, local=True, progress=progress)
        if progress:
            progress(0.7, "latex")
        try:
            pdf = TX.compile_dir(d, "main.tex", engine)
        except TX.LatexError as e:
            raise TX.LatexError(where(e, main, linemap), e.line, e.log) from None
        shutil.copyfile(pdf, path)


def where(e: "TX.LatexError", main: str, linemap: Dict[int, int]) -> str:
    """TeX's message with where it is: the line of the user's LaTeX text, else the generated main.tex's line text."""
    if e.line is None:
        return "LaTeX: %s" % e
    if linemap:
        return "LaTeX, line %d of the report: %s" % (linemap.get(e.line, e.line), e)
    try:
        with open(main, encoding="utf-8") as f:
            src = f.read().split("\n")[e.line - 1].strip()
    except Exception:
        src = ""
    return "LaTeX: %s (in: %s)" % (e, src[:120]) if src else "LaTeX: %s" % e


# ------------------------------------------------------------------------------------------------ preview / convert

_pdfs: Dict[str, str] = {}                          # token -> the preview PDF's path (the last few kept)


def preview(store, req: Dict) -> Dict[str, Any]:
    """A LaTeX document's preview: typeset now; the PDF served by token (or TeX's error at the line of the text)."""
    st = TX.status()
    if not st["best"]:
        return {"tex": True, "pdf": None, "error": st["hint"], "line": None}
    d = tempfile.mkdtemp(prefix="sv-texprev-")
    linemap: Dict[int, int] = {}
    try:
        main, engine, linemap = write_project(store, req, d, local=True)
        pdf = TX.compile_dir(d, "main.tex", engine, timeout=120)
    except TX.LatexError as e:
        shutil.rmtree(d, ignore_errors=True)
        line = linemap.get(e.line, e.line) if e.line else None
        return {"tex": True, "pdf": None, "error": ("Line %d: %s" % (line, e)) if line else str(e), "line": line, "log": e.log[-1500:]}
    token = TX.digest(json.dumps([req.get("text"), len(_pdfs)]) + d)
    _pdfs[token] = pdf
    while len(_pdfs) > 4:                            # the older previews' folders removed
        old = _pdfs.pop(next(iter(_pdfs)))
        shutil.rmtree(os.path.dirname(old), ignore_errors=True)
    return {"tex": True, "pdf": token, "engine": engine, "error": None}


def preview_pdf(token: str) -> Optional[str]:
    p = _pdfs.get(token)
    return p if p and os.path.isfile(p) else None


def to_latex(text: str, lang: str, words: Dict[str, str], title: str = "") -> str:
    """A Markdown report -> the same report as a LaTeX document to edit (Report -> Written in: LaTeX). Markers
    (⟦n⟧ - the page puts back its [[...]] / {{...}}) stay where they are; a ```latex block goes in as it is."""
    S = R.STRINGS.get(lang, R.STRINGS["en"])
    blocks = parse(text)
    ctx = Ctx("", lang, "xelatex", S, words, convert=True)
    t = title or next((b["text"] for b in blocks if b["t"] == "heading" and b["level"] == 1), "") or "Report"
    return (preamble(lang, "xelatex", ctx.text(MARK.sub("", t)).strip(), bool(HEB.search(text))) + "\n\\begin{document}\n\n"
            + blocks_tex(blocks, [], ctx) + "\n\n\\end{document}\n")
