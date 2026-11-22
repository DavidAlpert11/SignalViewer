#!/usr/bin/env python3
"""RE4: the small LaTeX bundle the app carries (backend/app/tex/texbundle.zip) - the TeX Live files Signal Viewer's
reports need, so the Tectonic engine beside it (tools/get_tectonic.py) typesets them with no TeX installed and no
internet. A full TeX distribution is hundreds of MB, Tectonic's own bundle ~3 GB; this one is what is used.

How it is made, on a computer WITH TeX Live (CI: ubuntu-24.04, texlive-xetex & co; TeX Live 2023 like Tectonic's):

  1. sample documents the app writes - a Markdown report as LaTeX (English, and Hebrew with --hebrew), a LaTeX
     document using the packages users reach for (those installed), a formula picture - typeset by xelatex
     -recorder: every file TeX reads is listed
  2. the files the LaTeX format is built from (xetex -ini -recorder, the way Tectonic builds it)
  3. fonts xelatex loads by name (not recorded): Latin Modern (OpenType), the AMS Type 1 fonts, FreeSerif (Hebrew)
  4. all of it flat in a zip with tectonic-format-latex.tex and SHA256SUM (Tectonic's bundle fingerprint)
  5. --check: each sample typeset again by Tectonic from the zip alone (-C: never the network)

    python tools/make_tex_bundle.py [--hebrew] [--check] [--out backend/app/tex/texbundle.zip]

The files keep their TeX Live licences (LPPL, OFL, GPL with the font exception...); README-BUNDLE.txt in the zip says
where they come from.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
OUT = os.path.join(ROOT, "backend", "app", "tex", "texbundle.zip")

# the standard classes in every size (the samples use one), and files TeX opens by name
NAMES = ["size10.clo", "size11.clo", "size12.clo", "bk10.clo", "bk11.clo", "bk12.clo", "report.cls", "book.cls",
         "letter.cls", "minimal.cls", "tex-text.tec", "pdftex.map", "dvipdfmx.cfg", "cid-x.map", "glyphlist.txt", "pdfglyphlist.txt", "kanjix.map", "ckx.map"]
# fonts xelatex opens by name (not recorded): every file of the folder (levels up) of each anchor - wherever this
# TeX keeps it (Debian splits /usr/share/texmf and /usr/share/texlive)
FONT_DIRS = [("lmroman10-regular.otf", 0), ("cmmi10.pfb", 1)]
HEB_FONTS = ["FreeSerif.otf", "FreeSerifBold.otf", "FreeSerifItalic.otf", "FreeSans.otf", "FreeSansBold.otf"]
# packages people put in an Overleaf preamble - the ones installed here go in (the app's own needs come first)
COMMON = ["amsmath", "amssymb", "mathtools", "graphicx", "booktabs", "longtable", "tabularx", "array", "multirow",
          "xcolor", "hyperref", "geometry", "float", "caption", "subcaption", "enumitem", "fancyhdr", "titlesec",
          "siunitx", "listings", "tikz", "url", "microtype", "csquotes", "babel"]
SKIP = ("texmf.cnf", "ls-R")


def run(cmd, cwd, timeout=300):
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def kpse(name):
    code, out = run(["kpsewhich", name], ".")
    return out.strip() if code == 0 and out.strip() else None


def samples(folder, hebrew):
    """The documents whose files the bundle must hold - written by the app's own LaTeX code."""
    import numpy as np
    from app import reportlatex as RL
    from app.store import Store
    from svcore import latex as TX
    t = np.arange(4000) * 0.01
    np.savetxt(os.path.join(folder, "f.csv"), np.c_[t, np.sin(t), np.cos(t)], delimiter=",", header="Time,Roll,Pitch", comments="", fmt="%.6f")
    st = Store()
    rid = st.open_file(os.path.join(folder, "f.csv")).id
    plot = {"title": "Roll & Pitch", "caption": "", "mode": "time", "range": None, "signals": [
        {"id": f"{rid}/{n}", "label": n, "color": c, "width": 1.5, "scale": 1, "offset": 0, "state": False, "tOffset": 0}
        for n, c in (("Roll", "#3D8BFD"), ("Pitch", "#F2A93B"))]}
    items = [{"kind": "value", "expr": "max(v0)", "sources": [f"{rid}/Roll"], "fmt": ".2f", "src": "max(Roll)"},
             {"kind": "plots", "plots": [plot], "tab": "T"}]
    md = ("# Flight 12 & co\n\nRoll peaked at **⟦0⟧ deg**, *50 % of it* `code` $x_1^2 + \\alpha$ - see [the site](https://x.org).\n\n"
          "⟦1⟧\n\n| a | b |\n|---|--:|\n| 1 | $\\beta$ |\n\n- one\n  - two\n1. first\n\n> [!WARNING]\n> careful\n\n"
          "```\nverbatim\n```\n\n$$\\begin{align} a &= b \\\\ c &= \\int_0^1 f \\end{align}$$\n\n---\n\n\\newpage\n")
    docs = {"md": {"text": md, "items": items, "lang": "en", "engine": "xelatex"}}
    if hebrew:
        he = ("# דוח טיסה 12\n\nהגלגול Roll rate הגיע ל-**⟦0⟧ מעלות**, *חצי* מהזמן $x^2$.\n\n⟦1⟧\n\n| עמודה | ערך |\n|---|--:|\n| א | 1 |\n\n"
              "- אחד\n- שניים English words\n\n> [!NOTE]\n> הערה\n\n```\ncode\n```\n")
        docs["he"] = {"text": he, "items": items, "lang": "he", "engine": "xelatex"}
    for name, req in docs.items():
        os.makedirs(os.path.join(folder, name))
        RL.write_project(st, req, os.path.join(folder, name))
    have = [p for p in COMMON if kpse(p + ".sty")]
    os.makedirs(os.path.join(folder, "doc"))
    body = ("\\documentclass[11pt]{article}\n" + "".join("\\usepackage{%s}\n" % p for p in have if p not in ("hyperref", "babel"))
            + ("\\usepackage[english]{babel}\n" if "babel" in have else "") + "\\usepackage{hyperref}\n\\begin{document}\n\\tableofcontents\n"
            "\\section{Title}\\label{s} Text \\ref{s} \\cite{x} \\url{https://x.org} $\\mathbb{R}$ \\textbf{b} \\emph{e} \\texttt{t}\n"
            "\\begin{figure}[h]\\centering\\rule{1cm}{1cm}\\caption{c}\\end{figure}\n" +
            ("\\begin{tikzpicture}\\draw (0,0) -- (1,1); \\node at (0,1) {n};\\end{tikzpicture}\n" if "tikz" in have else "") +
            ("\\SI{3}{\\metre\\per\\second}\n" if "siunitx" in have else "") + "\\end{document}\n")
    with open(os.path.join(folder, "doc", "main.tex"), "w", encoding="utf-8") as f:
        f.write(body)
    os.makedirs(os.path.join(folder, "snip"))
    with open(os.path.join(folder, "snip", "main.tex"), "w", encoding="utf-8") as f:
        f.write(TX.SNIP_PRE + "\\[ \\begin{pmatrix}1&0\\\\0&1\\end{pmatrix} \\]\n\\begin{align} a&=b\\end{align}\n"
                "\\begin{tabular}{|l|r|}\\hline a & 1\\\\ \\hline\\end{tabular}\n\\end{document}\n")
    return list(docs) + ["doc", "snip"], have


def recorded(fls):
    out = set()
    with open(fls, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("INPUT /"):
                out.add(os.path.realpath(line[6:].strip()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--hebrew", action="store_true", help="a Hebrew report too (needs bidi + polyglossia installed): fail without them")
    ap.add_argument("--check", action="store_true", help="typeset every sample with Tectonic from the zip alone")
    ap.add_argument("--tectonic", default=os.path.join(ROOT, "backend", "app", "tex", "tectonic" + (".exe" if os.name == "nt" else "")))
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    for tool in ("xelatex", "xetex", "kpsewhich"):
        if not shutil.which(tool):
            print("%s is needed (TeX Live) to make the bundle." % tool)
            return 1
    if a.hebrew and not (kpse("bidi.sty") and kpse("polyglossia.sty")):
        print("--hebrew: bidi.sty and polyglossia.sty must be installed (Debian: texlive-lang-arabic, texlive-xetex).")
        return 1
    work = tempfile.mkdtemp(prefix="sv-texbundle-")
    try:
        names, have = samples(work, a.hebrew)
        files = set()
        for n in names:
            d = os.path.join(work, n)
            for _ in range(2):
                code, log = run(["xelatex", "-recorder", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], d)
            if code:
                print("The sample %s did not typeset with xelatex:\n%s" % (n, log[-1500:]))
                return 1
            files |= recorded(os.path.join(d, "main.fls"))
        fmt = os.path.join(work, "fmt")
        os.makedirs(fmt)
        with open(os.path.join(fmt, "tectonic-format-latex.tex"), "w") as f:
            f.write("\\input xelatex.ini\n")
        code, log = run(["xetex", "-ini", "-etex", "-recorder", "-interaction=nonstopmode", "tectonic-format-latex.tex"], fmt)
        if code:
            print("The LaTeX format did not build:\n" + log[-1500:])
            return 1
        files |= recorded(os.path.join(fmt, "tectonic-format-latex.fls"))
        files = {p for p in files if not p.startswith(os.path.realpath(work)) and os.path.basename(p) not in SKIP and not p.endswith(".fmt")}
        for n in NAMES:
            p = kpse(n)
            if p:
                files.add(p)
        code, tree = run(["kpsewhich", "-var-value", "TEXMFDIST"], ".")
        tree = tree.strip()
        for anchor, up in FONT_DIRS:
            at = kpse(anchor)
            if not at:
                print("%s is not installed: the bundle needs it." % anchor)
                return 1
            top = os.path.dirname(at)
            for _ in range(up):
                top = os.path.dirname(top)
            for root, _d, fs in os.walk(top):
                files.update(os.path.join(root, f) for f in fs if f.endswith((".otf", ".pfb")))
        if a.hebrew:                      # FreeSerif: the Hebrew font when the computer has none of the usual ones
            sysfonts = {}
            for d in ("/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts")):
                for root, _d, fs in os.walk(d):
                    for fn in fs:
                        sysfonts.setdefault(fn, os.path.join(root, fn))
            for f in HEB_FONTS:
                p = kpse(f) or sysfonts.get(f)
                if not p:
                    print("%s was not found (Debian: fonts-freefont-otf) - Hebrew needs it." % f)
                    return 1
                files.add(p)
        by_name = {}
        for p in sorted(files):
            b = os.path.basename(p)
            if b in by_name and open(by_name[b], "rb").read() != open(p, "rb").read():
                print("Two different files named %s: %s, %s" % (b, by_name[b], p))
                return 1
            by_name[b] = p
        code, ver = run(["xetex", "--version"], ".")
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        digest = hashlib.sha256()
        for b in sorted(by_name):
            digest.update(b.encode() + b"\0" + hashlib.sha256(open(by_name[b], "rb").read()).digest())
        readme = ("Signal Viewer's LaTeX bundle (tools/make_tex_bundle.py): %d files from %s\n%s\nPackages of the LaTeX "
                  "document sample: %s\nEach file keeps its TeX Live licence (LPPL, OFL, GPL with the font exception...).\n"
                  % (len(by_name), tree, ver.splitlines()[0] if ver else "", ", ".join(have)))
        with zipfile.ZipFile(a.out + ".part", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for b in sorted(by_name):
                z.write(by_name[b], b)
            z.write(os.path.join(fmt, "tectonic-format-latex.tex"), "tectonic-format-latex.tex")
            z.writestr("SHA256SUM", digest.hexdigest() + "\n")
            z.writestr("README-BUNDLE.txt", readme)
            z.writestr("FILES.txt", "\n".join(sorted(by_name)) + "\n")
        os.replace(a.out + ".part", a.out)
        raw = sum(os.path.getsize(p) for p in by_name.values())
        print("Wrote %s: %d files, %.1f MB (%.1f MB uncompressed)" % (a.out, len(by_name), os.path.getsize(a.out) / 1e6, raw / 1e6))
        if a.check:
            if not os.path.isfile(a.tectonic):
                print("--check: no Tectonic at %s (tools/get_tectonic.py)" % a.tectonic)
                return 1
            cache = os.path.join(work, "tt-cache")
            env = dict(os.environ, TECTONIC_CACHE_DIR=cache)
            for n in names:
                d = os.path.join(work, "check-" + n)
                shutil.copytree(os.path.join(work, n), d)           # the sources and figures/ (xelatex's output is overwritten)
                for junk in ("main.pdf", "main.aux", "main.toc", "main.out"):
                    if os.path.exists(os.path.join(d, junk)):
                        os.remove(os.path.join(d, junk))
                from svcore.latex import bundle_arg   # a Windows path: a file:// URL
                p = subprocess.run([a.tectonic, "-b", bundle_arg(os.path.abspath(a.out)), "-C", "--keep-logs", "main.tex"], cwd=d, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
                ok = p.returncode == 0 and os.path.isfile(os.path.join(d, "main.pdf"))
                print("  Tectonic, %s: %s" % (n, "ok" if ok else "FAILED"))
                if not ok:
                    print(p.stdout.decode("utf-8", "replace")[-2500:])
                    return 1
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
