"""
Reports as documents to print or send: PDF (A4 pages - a title page, a page per plot with its statistics, the
summary) and Word. Split out of app/report.py (UX5.5); the plots' data, their figures and the words are report.py's.
"""

import base64
import io
from datetime import datetime
from typing import Dict, List, Optional

from svcore.extras import missing
from app.report import (STRINGS, ReportNeedsExtra, _bidi, _count_plots, _limit_text, _note_when, _png_array,
                        _process_first, _pyplot, _section_lines, _story_parts, draw_axes, figure_bytes, plot_data,
                        render_figure)


def _collect(store, req: Dict, progress=None) -> List[Dict]:
    items, done, total = [], 0, _count_plots(req)
    for tab in req.get("tabs", []):
        for p in tab.get("plots", []):
            pdata = plot_data(store, {**p, "notes": req.get("notes") or [], "lang": req.get("lang", "en")}, for_html=False)
            if pdata["signals"] or pdata.get("env") is not None or pdata.get("geo_png"):   # Envelope: "env"; a map: its image
                items.append(pdata)
            done += 1
            if progress:
                progress(0.05 + 0.6 * done / total, "plots")
    return items


def build_pdf(store, req: Dict, path: str, progress=None):
    """A4 pages: a title page (title, date, introduction), then one page per plot with
    heading, chart, caption and full-resolution statistics, then the summary."""
    import textwrap
    plt = _pyplot()
    from matplotlib.backends.backend_pdf import PdfPages
    lang = req.get("lang", "en")
    S = STRINGS.get(lang, STRINGS["en"])
    rtl = lang == "he"
    ha, X = ("right", 0.9) if rtl else ("left", 0.1)
    ink, muted = "#0f1822", "#5a6979"
    story_secs, story_pics = _story_parts(store, req)              # P10: the flight in N moments
    req = {**req, "sections": _process_first(story_secs + list(req.get("sections") or []))}
    items = _collect(store, req, progress)
    title = req.get("title") or "Signal Viewer report"
    total = 1 + len(items) + (1 if req.get("summary") or req.get("notes") else 0) + len(req.get("sections") or []) + (1 if story_pics else 0)

    def page(n):
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.text(X, 0.965, _bidi(title), ha=ha, fontsize=8, color=muted)
        fig.text(1 - X if rtl else 0.9, 0.965, _bidi("%s %d / %d" % (S["page"], n, total)),
                 ha="left" if rtl else "right", fontsize=8, color=muted)
        return fig

    def paragraphs(fig, text, y, size=10.5, width=88, color=ink):
        for para in (text or "").split("\n"):
            for line in textwrap.wrap(para, width) or [""]:
                fig.text(X, y, _bidi(line), ha=ha, va="top", fontsize=size, color=color)
                y -= 0.0175 * size / 10
        return y

    n = 1
    with PdfPages(path) as pdf:
        fig = page(n)
        fig.text(X, 0.86, _bidi(title), ha=ha, va="top", fontsize=22, weight="bold", color=ink)
        fig.text(X, 0.815, _bidi("%s %s" % (S["generated"], datetime.now().strftime("%Y-%m-%d %H:%M"))), ha=ha, fontsize=9, color=muted)
        paragraphs(fig, req.get("intro"), 0.77)
        pdf.savefig(fig); plt.close(fig)

        for sec in req.get("sections") or []:          # investigation: findings, steps, conditions...
            lines: Optional[List[str]] = _section_lines(sec)
            while lines is not None:
                n += 1
                fig = page(n)
                fig.text(X, 0.92, _bidi(str(sec.get("title") or "")), ha=ha, va="top", fontsize=14, weight="bold", color=ink)
                y, rest = 0.875, None
                for k, line in enumerate(lines):
                    if y < 0.08:
                        rest = lines[k:]
                        break
                    y = paragraphs(fig, line, y, size=9.5)
                pdf.savefig(fig); plt.close(fig)
                lines = rest
        if story_pics:                                  # P10: the 3D picture at the first four moments, two per row
            n += 1
            fig = page(n)
            for k, (cap, png) in enumerate(story_pics):
                ax = fig.add_axes((0.06 + (k % 2) * 0.46, 0.52 - (k // 2) * 0.42, 0.42, 0.36))
                ax.imshow(plt.imread(io.BytesIO(png), format="png")); ax.set_axis_off()
                ax.set_title(_bidi(cap), fontsize=9, color=ink)
            pdf.savefig(fig); plt.close(fig)

        for i, p in enumerate(items):
            if progress:
                progress(0.65 + 0.33 * i / max(1, len(items)), "pages")
            n += 1
            fig = page(n)
            fig.text(X, 0.92, _bidi(p["title"] or "%s %d" % (S["plot"], i + 1)), ha=ha, va="top", fontsize=14, weight="bold", color=ink)
            ax = fig.add_axes([0.1, 0.52, 0.82, 0.36])
            if p.get("geo_png"):                               # L11: the map as the server drew it
                ax.imshow(_png_array(p["geo_png"])); ax.set_axis_off()
            else:
                draw_axes(ax, p, "light")
            y = 0.47
            if p["caption"]:
                y = paragraphs(fig, p["caption"], y, size=9.5, color=muted) - 0.01
            rows = [s for s in p["signals"] if s.get("stats")]
            if rows and p["mode"] != "xy":
                cols = [S["signal"], S["min"], S["max"], S["mean"], S["rms"], S["std"]]
                cells = [[_bidi(s["label"])] + ["" if s["stats"].get(k) is None else "%.6g" % s["stats"][k]
                          for k in ("min", "max", "mean", "rms", "std")] for s in rows]
                if any(s.get("limits") for s in rows):
                    cols = cols + [S["limits"]]
                    cells = [c + [_bidi(_limit_text(s, S))] for c, s in zip(cells, rows)]
                if rtl:  # columns read right-to-left
                    cols, cells = cols[::-1], [r[::-1] for r in cells]
                h = min(0.04 * (len(rows) + 1), y - 0.08)
                tax = fig.add_axes([0.1, y - h, 0.82, h]); tax.axis("off")
                tbl = tax.table(cellText=cells, colLabels=[_bidi(c) for c in cols], loc="upper center", cellLoc="center")
                tbl.auto_set_font_size(False); tbl.set_fontsize(8.5); tbl.scale(1, 1.25)
                for (r, c), cell in tbl.get_celld().items():
                    cell.set_edgecolor("#d5dce4")
                    if r == 0:
                        cell.set_facecolor("#eef2f5"); cell.set_text_props(weight="bold", color=ink)
            pdf.savefig(fig); plt.close(fig)

        notes = sorted(req.get("notes") or [], key=lambda n: n.get("t") or 0)
        if req.get("summary") or notes:
            n += 1
            fig = page(n)
            y = 0.9
            if req.get("summary"):
                fig.text(X, y, _bidi(S["summary"]), ha=ha, va="top", fontsize=16, weight="bold", color=ink)
                y = paragraphs(fig, req["summary"], y - 0.04) - 0.03
            if notes:
                fig.text(X, y, _bidi(S["notes"]), ha=ha, va="top", fontsize=14, weight="bold", color=ink)
                paragraphs(fig, "\n".join(f"{_note_when(nt)}  {nt.get('text', '')}" for nt in notes), y - 0.04)
            pdf.savefig(fig); plt.close(fig)


def build_docx(store, req: Dict, path: str, progress=None):
    try:
        import docx  # noqa: F401
    except ImportError:
        raise ReportNeedsExtra(missing("Word reports", "reports")) from None
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    from docx.shared import Inches, Pt
    lang = req.get("lang", "en")
    S = STRINGS.get(lang, STRINGS["en"])
    rtl = lang == "he"
    doc = Document()

    def rtlize(par):
        if rtl:
            ppr = par._p.get_or_add_pPr()
            b = OxmlElement("w:bidi"); b.set(qn("w:val"), "1"); ppr.append(b)
            par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for r in par.runs:
                rpr = r._r.get_or_add_rPr()
                rt = OxmlElement("w:rtl"); rt.set(qn("w:val"), "1"); rpr.append(rt)
        return par

    story_secs, story_pics = _story_parts(store, req)              # P10: the flight in N moments
    req = {**req, "sections": _process_first(story_secs + list(req.get("sections") or []))}
    rtlize(doc.add_heading(req.get("title") or "Signal Viewer report", 0))
    rtlize(doc.add_paragraph(f"{S['generated']} {datetime.now().strftime('%Y-%m-%d %H:%M')}"))
    for para in (req.get("intro") or "").split("\n"):
        if para.strip():
            rtlize(doc.add_paragraph(para))
    for sec in req.get("sections") or []:              # investigation: findings, steps, conditions...
        rtlize(doc.add_heading(str(sec.get("title") or ""), 1))
        for para in str(sec.get("text") or "").split("\n"):
            if para.strip():
                rtlize(doc.add_paragraph(para))
        for it in sec.get("items") or []:
            rtlize(doc.add_paragraph(str(it), style="List Bullet"))
        tb = sec.get("table")
        if tb and tb.get("rows"):
            head = [str(h) for h in tb.get("head") or []]
            t = doc.add_table(rows=1, cols=max(1, len(head)))
            t.style = "Light Grid Accent 1"
            for c, h in enumerate(head):
                t.rows[0].cells[c].text = h
            for r in tb["rows"]:
                cells = t.add_row().cells
                for c, v in enumerate(r[:len(head)]):
                    cells[c].text = str(v)
    if story_pics:                                     # P10: the 3D picture at the first four moments, two per row
        grid = doc.add_table(rows=(len(story_pics) + 1) // 2, cols=2)
        for kp, (cap, png) in enumerate(story_pics):
            cell = grid.rows[kp // 2].cells[kp % 2]
            cell.paragraphs[0].add_run().add_picture(io.BytesIO(png), width=Inches(3.0))
            rtlize(cell.add_paragraph(cap))
    items = _collect(store, req, progress)
    for i, p in enumerate(items):
        if progress:
            progress(0.65 + 0.33 * i / max(1, len(items)), "pages")
        rtlize(doc.add_heading(p["title"] or f"{S['plot']} {i + 1}", 1))
        png = base64.b64decode(p["geo_png"]) if p.get("geo_png") else \
            figure_bytes(render_figure(p, "light", size=(7, 5) if p["mode"] == "xyz" else (9, 3.6), dpi=170), "png")
        doc.add_picture(io.BytesIO(png), width=Inches(6.3))
        if p["caption"]:
            rtlize(doc.add_paragraph(p["caption"]))
        rows = [s for s in p["signals"] if s.get("stats")]
        if rows and p["mode"] != "xy":
            cols = [S["signal"], S["min"], S["max"], S["mean"], S["rms"], S["std"]]
            with_limits = any(s.get("limits") for s in rows)
            if with_limits:
                cols = cols + [S["limits"]]
            t = doc.add_table(rows=1, cols=len(cols))
            t.style = "Light Grid Accent 1"
            for c, name in enumerate(cols):
                t.rows[0].cells[c].text = name
            for s in rows:
                cells = t.add_row().cells
                cells[0].text = s["label"]
                for c, k in enumerate(("min", "max", "mean", "rms", "std"), start=1):
                    v = s["stats"].get(k)
                    cells[c].text = "" if v is None else f"{v:.6g}"
                if with_limits:
                    cells[len(cols) - 1].text = _limit_text(s, S)
            for row in t.rows:
                for cell in row.cells:
                    for par in cell.paragraphs:
                        for r in par.runs:
                            r.font.size = Pt(8.5)
    if req.get("summary"):
        rtlize(doc.add_heading(S["summary"], 1))
        for para in req["summary"].split("\n"):
            if para.strip():
                rtlize(doc.add_paragraph(para))
    notes = sorted(req.get("notes") or [], key=lambda n: n.get("t") or 0)
    if notes:
        rtlize(doc.add_heading(S["notes"], 1))
        for nt in notes:
            rtlize(doc.add_paragraph(f"{_note_when(nt)}  {nt.get('text', '')}", style="List Bullet"))
    doc.save(path)
