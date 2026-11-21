"""RE3 (owner, 2026-11-21): LaTeX for the report - "full LaTeX like Overleaf, but everything must work offline".

The app carries no TeX of its own (a TeX distribution is hundreds of MB): it uses the one on this computer - TeX Live,
MiKTeX or MacTeX, installed once, then offline (MiKTeX: install the packages beforehand or the full set; its
"install missing packages on the fly" needs the internet). Without one the report is still written as a LaTeX
project (.zip) - for Overleaf or another computer - and the page, PDF and Word work as before.

  status()          what is installed: the engines (xelatex, lualatex, pdflatex), latexmk, and the converters a
                    formula / a LaTeX block needs to be drawn in the page (dvisvgm, dvipng, pdftoppm, Ghostscript)
  compile_dir()     a project folder -> its PDF (latexmk when there is one, else the engine twice); a failure raises
                    LatexError with TeX's own message and the line
  snippet()         a formula or a block drawn by real LaTeX - SVG for the page, PNG for Word / the PDF - for what
                    matplotlib's mathtext cannot read (align, matrices, tables, \\text{...})

The folder searched besides the PATH: Settings key `texDir`, the environment variable SV_TEX, and where TeX Live /
MiKTeX / MacTeX install by default.
"""
import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

ENGINES = ("xelatex", "lualatex", "pdflatex")
TOOLS = ENGINES + ("latex", "latexmk", "dvisvgm", "dvipng", "pdftoppm", "gs", "gswin64c", "mgs")
_found: Dict[str, Optional[str]] = {}
_extra_dir: Optional[str] = None


class LatexError(RuntimeError):
    """TeX stopped: its message, the line of main.tex (and of the user's text when known), the log's tail."""

    def __init__(self, message: str, line: Optional[int] = None, log: str = ""):
        super().__init__(message)
        self.line = line
        self.log = log


def set_dir(folder: Optional[str]) -> None:
    """The folder of the TeX programs chosen in Settings (texDir); the search starts again."""
    global _extra_dir
    _extra_dir = folder or None
    _found.clear()


def _dirs() -> List[str]:
    out = [d for d in (_extra_dir, os.environ.get("SV_TEX")) if d]
    if sys.platform.startswith("win"):
        la, pf = os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", r"C:\Program Files")
        out += [os.path.join(la, "Programs", "MiKTeX", "miktex", "bin", "x64"), os.path.join(pf, "MiKTeX", "miktex", "bin", "x64")]
        out += sorted(glob.glob(r"C:\texlive\20*\bin\windows") + glob.glob(r"C:\texlive\20*\bin\win*"), reverse=True)
    else:
        out += ["/Library/TeX/texbin", "/usr/texbin", "/opt/homebrew/bin", "/usr/local/bin"]
        out += sorted(glob.glob("/usr/local/texlive/20*/bin/*"), reverse=True)
    return out


def find(tool: str) -> Optional[str]:
    if tool not in _found:
        hit = shutil.which(tool)
        if not hit:
            for d in _dirs():
                for name in (tool, tool + ".exe"):
                    p = os.path.join(d, name)
                    if os.path.isfile(p) and os.access(p, os.X_OK):
                        hit = p
                        break
                if hit:
                    break
        _found[tool] = hit
    return _found[tool]


def best_engine(unicode: bool = True) -> Optional[str]:
    """XeLaTeX first (Unicode, Hebrew and any system font), then LuaLaTeX, then pdfLaTeX (no Hebrew)."""
    for e in ENGINES if unicode else ("pdflatex", "xelatex", "lualatex"):
        if find(e):
            return e
    return None


def status() -> Dict[str, Any]:
    eng = {e: find(e) for e in ENGINES}
    conv = {t: find(t) for t in ("latex", "latexmk", "dvisvgm", "dvipng", "pdftoppm")}
    gs = find("gs") or find("gswin64c") or find("mgs")
    best = best_engine()
    can_snip = bool((conv["latex"] and (conv["dvisvgm"] or conv["dvipng"])) or ((eng["pdflatex"] or best) and (conv["pdftoppm"] or gs)))
    return {"engines": eng, "tools": {**conv, "ghostscript": gs}, "best": best, "snippets": can_snip,
            "folder": os.path.dirname(best and find(best) or "") or None,
            "hint": None if best else "No LaTeX on this computer: install TeX Live (tug.org/texlive), MiKTeX (miktex.org) or "
                                      "MacTeX once - then it works offline. Meanwhile the LaTeX project (.zip) opens in Overleaf."}


def _run(cmd: List[str], cwd: str, timeout: float) -> Tuple[int, str]:
    kw: Dict[str, Any] = {}
    if sys.platform.startswith("win"):
        kw["creationflags"] = 0x08000000                    # CREATE_NO_WINDOW: no console flashing
    env = dict(os.environ, max_print_line="1000", error_line="254", half_error_line="238")   # long log lines unbroken
    try:
        p = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout, env=env, **kw)
    except subprocess.TimeoutExpired:
        return 124, "LaTeX did not finish in %d s (an endless loop, or a package waiting to be installed)." % timeout
    except OSError as e:
        return 127, str(e)
    return p.returncode, p.stdout.decode("utf-8", "replace")


_ERR_FLE = re.compile(r"^(?:\./)?([^:\n]+\.tex):(\d+): (.+)$", re.M)


def parse_log(log: str) -> Tuple[str, Optional[int]]:
    """TeX's first error and its line: `file.tex:12: message` (file-line-error), else `! message` ... `l.12`."""
    m = _ERR_FLE.search(log)
    line: Optional[int]
    if m:
        msg, line = m.group(3).strip(), int(m.group(2))
    else:
        b = re.search(r"^! (.+)$", log, re.M)
        if not b:
            miss = re.search(r"File `([^']+)' not found", log)
            if miss:
                return "The package file %s is not installed (offline: install it with your TeX distribution's package manager)." % miss.group(1), None
            tail = [x for x in log.strip().splitlines() if x.strip()][-3:]
            return ("LaTeX stopped: " + " / ".join(tail)) if tail else "LaTeX stopped without a message.", None
        msg = b.group(1).strip()
        ln = re.search(r"^l\.(\d+)", log[b.end():], re.M)
        line = int(ln.group(1)) if ln else None
    miss = re.search(r"File `([^']+)' not found", log)
    if miss and "not found" in msg:
        msg = "%s is not installed - install it with your TeX distribution's package manager (MiKTeX Console / tlmgr)." % miss.group(1)
    return msg, line


def compile_dir(folder: str, main: str = "main.tex", engine: Optional[str] = None, timeout: float = 240) -> str:
    """main.tex of `folder` -> main.pdf (its path). LatexError with TeX's message when it stops."""
    engine = engine or best_engine()
    if not engine or not find(engine):
        raise LatexError(status()["hint"] or "No LaTeX engine found.")
    base = os.path.splitext(main)[0]
    flags = ["-interaction=nonstopmode", "-halt-on-error", "-file-line-error"]
    mk = find("latexmk")
    log = ""
    if mk:
        opt = {"xelatex": "-xelatex", "lualatex": "-lualatex", "pdflatex": "-pdf"}[engine]
        code, log = _run([mk, opt, "-f-", "-silent", "-norc"] + ["-latexoption=" + f for f in flags] + [main], folder, timeout)
        if code and os.path.isfile(os.path.join(folder, base + ".log")):
            with open(os.path.join(folder, base + ".log"), encoding="utf-8", errors="replace") as f:
                log = f.read()
    else:
        code = 0
        for _ in range(2):                                   # twice: the table of contents, the references
            code, log = _run([find(engine) or engine] + flags + [main], folder, timeout)
            if code:
                break
    pdf = os.path.join(folder, base + ".pdf")
    if code or not os.path.isfile(pdf):
        msg, line = parse_log(log)
        if line is None:
            line = _runaway_line(log, os.path.join(folder, main))
        raise LatexError(msg, line, log[-4000:])
    return pdf


def _runaway_line(log: str, main: str) -> Optional[int]:
    """"File ended while scanning..." has no line: the runaway argument's first words, found in main.tex."""
    m = re.search(r"Runaway argument\?\s*\n\{?([^\n]{3,})", log)
    if not m:
        return None
    words = re.split(r"\s+", re.sub(r"\\par\b.*$", "", m.group(1)).strip())
    needle = " ".join(words[:2]).strip()
    if not needle:
        return None
    try:
        with open(main, encoding="utf-8") as f:
            for i, ln in enumerate(f, start=1):
                if needle in ln or (words and words[0] in ln and len(words[0]) >= 3):
                    return i
    except OSError:
        pass
    return None


# ------------------------------------------------------------------------------------------------ snippets

_cache: Dict[Tuple[str, str, str], Any] = {}
SNIP_PRE = "\\documentclass[12pt]{article}\n\\usepackage{amsmath,amssymb}\n\\pagestyle{empty}\n\\begin{document}\n"


DISPLAY_ENVS = re.compile(r"^\\begin\{(align|equation|gather|multline|flalign|alignat|eqnarray)\*?\}")


def is_display_env(tex: str) -> bool:
    """A formula that is a display environment of its own (align, equation...): written as it is, not in \\[ \\]."""
    return bool(DISPLAY_ENVS.match(tex.strip()))


def _body(tex: str, kind: str) -> str:
    t = tex.strip()
    if kind == "inline":
        return "$%s$" % t
    if kind == "math":
        return t if is_display_env(t) else "\\[ %s \\]" % t
    return t                                                   # a LaTeX block: as written


def snippet(tex: str, kind: str = "math", fmt: str = "svg") -> Any:
    """A formula (kind inline / math) or a LaTeX block drawn by the computer's TeX: SVG text or PNG bytes; None when
    there is no TeX (or nothing to convert with); a LatexError (cached) when TeX could not read it."""
    key = (tex, kind, fmt)
    if key in _cache:
        hit = _cache[key]
        if isinstance(hit, LatexError):
            raise hit
        return hit
    try:
        res = _snippet(tex, kind, fmt)
    except LatexError as e:
        _cache[key] = e
        raise
    _cache[key] = res
    if len(_cache) > 400:
        _cache.pop(next(iter(_cache)))
    return res


def _snippet(tex: str, kind: str, fmt: str) -> Any:
    doc = SNIP_PRE + _body(tex, kind) + "\n\\end{document}\n"
    with tempfile.TemporaryDirectory(prefix="sv-tex-") as d:
        with open(os.path.join(d, "s.tex"), "w", encoding="utf-8") as f:
            f.write(doc)
        latex, dsvg, dpng = find("latex"), find("dvisvgm"), find("dvipng")
        if latex and ((fmt == "svg" and dsvg) or (fmt == "png" and dpng)):
            code, log = _run([latex, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "s.tex"], d, 30)
            if code or not os.path.isfile(os.path.join(d, "s.dvi")):
                raise LatexError(parse_log(log)[0])
            if fmt == "svg":
                code, _o = _run([dsvg or "dvisvgm", "--no-fonts", "--exact-bbox", "-o", "s.svg", "s.dvi"], d, 30)
                p = os.path.join(d, "s.svg")
                if not code and os.path.isfile(p):
                    with open(p, encoding="utf-8") as f:
                        return f.read()
            else:
                code, _o = _run([dpng or "dvipng", "-D", "300", "-T", "tight", "-bg", "Transparent", "-o", "s.png", "s.dvi"], d, 30)
                p = os.path.join(d, "s.png")
                if not code and os.path.isfile(p):
                    with open(p, "rb") as f:
                        return f.read()
        # through a PDF: pdfLaTeX (or another engine), then pdftoppm / Ghostscript, cropped, ink kept on transparent
        eng = find("pdflatex") or best_engine()
        to_png = find("pdftoppm")
        gs = find("gs") or find("gswin64c") or find("mgs")
        if not eng or not (to_png or gs):
            return None
        code, log = _run([eng, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "s.tex"], d, 60)
        if code or not os.path.isfile(os.path.join(d, "s.pdf")):
            raise LatexError(parse_log(log)[0])
        if to_png:
            code, _o = _run([to_png, "-png", "-r", "300", "-singlefile", "s.pdf", "s"], d, 30)
        else:
            code, _o = _run([gs or "gs", "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pnggray", "-r300", "-sOutputFile=s.png", "s.pdf"], d, 30)
        p = os.path.join(d, "s.png")
        if code or not os.path.isfile(p):
            return None
        png = _ink_png(p)
        if fmt == "png":
            return png
        import base64
        h, w = _png_size(png)
        return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="%.1fpt" height="%.1fpt" '
                'viewBox="0 0 %d %d"><image width="%d" height="%d" xlink:href="data:image/png;base64,%s"/></svg>'
                % (w * 72 / 300, h * 72 / 300, w, h, w, h, base64.b64encode(png).decode("ascii")))


def _png_size(png: bytes) -> Tuple[int, int]:
    import struct
    w, h = struct.unpack(">II", png[16:24])
    return h, w


def _ink_png(path: str) -> bytes:
    """A rendered page -> only its ink, cropped, black on transparent (the page colours it: dark themes invert it)."""
    import io

    import numpy as np
    from matplotlib import image as mpimg
    a = mpimg.imread(path)
    g = a if a.ndim == 2 else a[..., :3].mean(axis=2)
    if g.max() > 1.0:
        g = g / 255.0
    ink = 1.0 - g
    ys, xs = np.nonzero(ink > 0.02)
    if not len(ys):
        ys, xs = np.array([0, g.shape[0] - 1]), np.array([0, g.shape[1] - 1])
    pad = 6
    y0, y1 = max(0, ys.min() - pad), min(g.shape[0], ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(g.shape[1], xs.max() + pad + 1)
    alpha = ink[y0:y1, x0:x1]
    rgba = np.zeros(alpha.shape + (4,), dtype=np.float32)
    rgba[..., 3] = alpha
    buf = io.BytesIO()
    mpimg.imsave(buf, rgba, format="png")
    return buf.getvalue()


def digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
