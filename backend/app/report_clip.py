"""
Copy for Confluence: a plot or a tab as a page fragment - the interactive page attached to the Confluence page (the
HTML macro or the Signal Viewer user macro) and a static copy with its picture and values for where scripts are off.
Split out of app/report.py (UX5.5); the page itself is report.build_html.
"""

import base64
import html
import json
from typing import Dict

from app.report import STRINGS, _limit_text, _note_when, build_html, build_image, plot_data



CLIP_WORDS = {
    "en": {"loading": "Loading {name}…", "noPage": "This page shows {name}, attached to a Confluence page: open it there.",
           "missing": "{name} is not attached to this page. Drag the file onto the page (it becomes an attachment), then reload."},
    "he": {"loading": "טוען את {name}…", "noPage": "כאן מוצג {name} המצורף לדף Confluence: פתחו אותו שם.",
           "missing": "{name} לא מצורף לדף הזה. גררו את הקובץ אל הדף (הוא נשמר כקובץ מצורף) וטענו מחדש."},
}

# Confluence names the page in <meta name="ajs-page-id"> (and its context path); /download/attachments/<page>/<name>
# is the attachment's latest version. fetch reads it whatever its download headers say (HTML attachments are
# often forced to download), and the frame shows it from srcdoc.
# Found by place, not by id: the same lines pasted twice must show twice (a script run from markup has
# currentScript; one an editor inserts later runs in order, so the first box not yet taken is its own).
# One script for both ways in (CP2): the box says the attachment's name (data-name), its words' language and -
# in the user macro - the page and the context path Confluence gave it (data-page, data-ctx); else the meta tags.
# No "$" and no "#" in it: the user macro's template is Velocity.
_CLIP_JS = """(function(){var s=document.currentScript,r=s&&s.parentNode&&s.parentNode.classList.contains('sv-clip')&&!s.parentNode.getAttribute('data-sv')?s.parentNode:document.querySelector('.sv-clip:not([data-sv])');
if(!r)return;r.setAttribute('data-sv','1');var f=r.querySelector('iframe'),m=r.querySelector('p'),name=r.getAttribute('data-name'),A=%(words)s;
var W=A[(r.getAttribute('data-lang')||document.documentElement.lang||'en').slice(0,2)]||A.en,h=parseInt(r.getAttribute('data-h'),10);
if(h>=120&&h<=20000)f.style.height=h+'px';
function meta(n){var e=document.querySelector('meta[name="'+n+'"]');return e?e.getAttribute('content'):''}
function say(k){m.textContent=W[k].replace('{name}',name);m.style.display=''}
function fit(){try{var d=f.contentDocument;if(d&&d.body&&d.body.childElementCount)f.style.height=Math.max(160,d.documentElement.scrollHeight)+'px'}catch(e){}}
f.addEventListener('load',function(){fit();try{new ResizeObserver(fit).observe(f.contentDocument.body)}catch(e){}});
var pid=r.getAttribute('data-page')||meta('ajs-page-id')||meta('ajs-latest-page-id'),ctx=r.getAttribute('data-ctx')||meta('ajs-context-path');
if(!pid||!name){say('noPage');return}
say('loading');fetch(ctx+'/download/attachments/'+pid+'/'+encodeURIComponent(name),{credentials:'same-origin'})
.then(function(r){if(!r.ok)throw new Error(r.status);return r.text()})
.then(function(t){f.srcdoc=t;m.style.display='none'},function(){say('missing')})})();"""


def _clip_script() -> str:
    return _CLIP_JS % {"words": json.dumps(CLIP_WORDS, ensure_ascii=False)}


def _clip_height(req: Dict) -> int:
    """The frame's height before its page has measured itself."""
    plots = [p for t in req.get("tabs", []) for p in t.get("plots", [])]
    return 90 + sum(420 + 26 * len(p.get("signals") or []) for p in plots) + 24 * len(req.get("notes") or [])


def build_clip_page(store, req: Dict) -> str:
    """The page attached to Confluence: the report's page of the plot / tab with every sample."""
    return build_html(store, req, clip=True)


def build_clip_macro(req: Dict, name: str) -> str:
    """The HTML macro's few lines: a frame that shows the attachment `name` of the page they are on."""
    return ('<div class="sv-clip" data-name="%s" data-lang="%s"><p style="color:#5a6979;font:13px sans-serif;display:none"></p>'
            '<iframe title="%s" style="width:100%%;height:%dpx;border:0;display:block"></iframe><script>%s</script></div>'
            % (html.escape(name), html.escape(req.get("lang", "en")), html.escape(name), _clip_height(req),
               _clip_script().replace("</", "<\\/")))


# CP2 (owner, 2026-11-22): Confluence Data Center keeps the HTML macro off by default. An administrator installs this
# user macro once instead (General configuration > User Macros) - the same box and script, the page id and context
# path from Confluence itself, the attachment's name a parameter. The copy then puts {signalviewer:file=...} on the
# clipboard, pasted with Insert > Markup.
USER_MACRO = "signalviewer"

USER_MACRO_HEAD = """## Signal Viewer - an interactive plot or tab attached to this page (the .html file that "Copy for Confluence" saves).
## Installed ONCE by a Confluence administrator: General configuration > User Macros > Create a User Macro
##   Macro Name: signalviewer      Visibility: Visible to all users      Macro Title: Signal Viewer
##   Macro Body Processing: No macro body      Template: this whole text.
## Then, in a page: drag the .html file onto the page (an attachment), Insert > Markup, paste what Signal Viewer copied
## ({signalviewer:file=plot.html}) - or Insert > Other macros > Signal Viewer and type the file's name.
## @param file:title=Attachment (.html)|type=string|required=true|desc=The .html file Signal Viewer saved, attached to this page
## @param height:title=Height (px)|type=int|default=600|desc=Its height until the plot has measured itself
"""


def build_user_macro_template() -> str:
    """The user macro's Velocity template (Confluence Data Center / Server): the administrator pastes it once."""
    box = ('<div class="sv-clip" data-name="$!generalUtil.htmlEncode($!paramfile)" data-page="$!content.id" '
           'data-ctx="$!req.contextPath" data-h="$!generalUtil.htmlEncode($!paramheight)">'
           '<p style="color:#5a6979;font:13px sans-serif;display:none"></p>'
           '<iframe title="$!generalUtil.htmlEncode($!paramfile)" style="width:100%;height:600px;border:0;display:block"></iframe>'
           '<script>' + _clip_script().replace("</", "<\\/") + '</script></div>\n')
    return USER_MACRO_HEAD + box


def build_clip_markup(req: Dict, name: str) -> str:
    """What the user macro's way copies: the macro in Confluence's wiki markup (Insert > Markup)."""
    return "{%s:file=%s|height=%d}" % (USER_MACRO, name, _clip_height(req))


_CLIP_TD = "padding:3px 8px;border-top:1px solid #d5dce4;text-align:right;white-space:nowrap;direction:ltr"


def build_clip_static(store, req: Dict) -> str:
    """The copy without scripts: each plot's picture, its statistics table and the notes - inline styles only
    (an editor that receives a paste keeps those and drops style sheets)."""
    lang = req.get("lang", "en")
    S = STRINGS.get(lang, STRINGS["en"])
    rtl = lang == "he"
    start, end = ("right", "left") if rtl else ("left", "right")
    td = _CLIP_TD                                                  # numbers left to right (-10.9, not 10.9-)
    parts = []
    if req.get("title"):
        parts.append('<h2 style="margin:0 0 8px">%s</h2>' % html.escape(req["title"]))
    for tab in req.get("tabs", []):
        for p in tab.get("plots", []):
            pd = plot_data(store, {**p, "lang": lang}, for_html=False)
            sc = max(1.0, min(4.0, float(req.get("scale") or 1)))          # CP7: Settings -> Copied pictures
            png = base64.b64encode(build_image(store, p, "png", "light", sc)).decode("ascii")
            parts.append('<h3 style="margin:14px 0 4px">%s</h3>' % html.escape(pd["title"]))
            if pd.get("caption"):
                parts.append('<p style="margin:0 0 6px;color:#5a6979;white-space:pre-wrap">%s</p>' % html.escape(pd["caption"]))
            parts.append('<p><img alt="%s" width="800" style="max-width:100%%;height:auto" src="data:image/png;base64,%s"></p>'
                         % (html.escape(pd["title"]), png))
            if pd["mode"] in ("time", "fft") and pd["signals"]:
                keys = ("min", "max", "mean", "rms", "std")
                head = "".join('<th style="%s;color:#5a6979;font-weight:500">%s</th>' % (td, S[k]) for k in (*keys, "samples"))
                lim = any(s.get("limits") for s in pd["signals"])
                if lim:
                    head += '<th style="%s;color:#5a6979;font-weight:500">%s</th>' % (td, S["limits"])
                rows = []
                for s in pd["signals"]:
                    st = s.get("stats") or {}
                    cells = "".join('<td style="%s">%s</td>' % (td, "" if st.get(k) is None else f"{st[k]:.6g}") for k in keys)
                    cells += '<td style="%s">%s</td>' % (td, "" if st.get("samples") is None else f"{int(st['samples']):,}")
                    if lim:
                        r = s.get("limits")
                        col = "" if not r else (";color:#1f8a4c;font-weight:600" if r["pass"] else ";color:#c0392b;font-weight:600")
                        cells += '<td style="%s%s">%s</td>' % (td, col, html.escape(_limit_text(s, S)))
                    sw = '<span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:%s;margin-%s:6px"></span>' % (
                        html.escape(s["color"] or "#3D8BFD"), end)
                    rows.append('<tr><td style="%s;text-align:%s;direction:%s">%s%s</td>%s</tr>' % (td, start, "rtl" if rtl else "ltr", sw, html.escape(s["label"]), cells))
                parts.append('<table style="border-collapse:collapse;font-size:12.5px"><thead><tr><th style="%s;text-align:%s;color:#5a6979;'
                             'font-weight:500">%s</th>%s</tr></thead><tbody>%s</tbody></table>' % (td, start, S["signal"], head, "".join(rows)))
    notes = sorted(req.get("notes") or [], key=lambda n: n.get("t") or 0)
    if notes:
        parts.append('<h3 style="margin:14px 0 4px">%s</h3><ul>%s</ul>' % (S["notes"], "".join(
            '<li><span style="color:#5a6979">%s</span> %s</li>' % (html.escape(_note_when(n)), html.escape(n.get("text", ""))) for n in notes)))
    return '<div dir="%s" style="font-family:Segoe UI,system-ui,sans-serif;color:#1f2a36">%s</div>' % ("rtl" if rtl else "ltr", "".join(parts))
