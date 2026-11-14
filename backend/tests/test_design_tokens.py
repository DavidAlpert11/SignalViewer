"""26.U1: the UI's CSS uses the design tokens of index.css - the type scale, the radii, the semantic
colours - not literal values (light and dark themes, Settings > Text size). A rule that needs a new size
or colour adds a token."""
import os
import re

CSS = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "index.css")


def _rules():
    """The CSS without comments; custom-property definitions (the tokens themselves) left out."""
    text = re.sub(r"/\*.*?\*/", "", open(CSS, encoding="utf-8").read(), flags=re.S)
    return re.sub(r"--[\w-]+\s*:[^;{}]*;", "", text)


def test_font_sizes_are_on_the_scale():
    bad = re.findall(r"font-size:\s*([0-9.]+(?:rem|px))", _rules())
    assert not bad, f"use a --fs-* token, not {sorted(set(bad))}"


def test_radii_are_tokens():
    bad = [v for v in re.findall(r"border-radius:\s*([^;}]+)", _rules()) if re.search(r"\b[1-9][0-9]*px\b", v)]
    assert not bad, f"use a --r-* token, not {sorted(set(bad))}"


def test_colours_are_tokens():
    bad = re.findall(r"#[0-9a-fA-F]{3,8}\b", _rules())
    assert not bad, f"use a colour token (index.css), not {sorted(set(bad))}"


STYLES = os.path.join(os.path.dirname(CSS), "styles")
COMPONENT = re.compile(r"\.(btn|iconbtn|chipbtn|linkbtn|linklike|pill|seg|toast|menu)(?![\w-])")
PLACEMENT = re.compile(r"^(margin|align-self|justify-self|flex|order|grid-|position|inset|top|bottom|left|right|z-index|width|max-width|min-width)")


def test_components_are_defined_once():
    """A3: buttons, segmented controls, chips, pills, menus and toasts are defined in index.css only; an area's
    stylesheet may place one (margin, flex, ...) but not restyle it - one way to draw each component."""
    bad = []
    for name in sorted(os.listdir(STYLES)):
        text = re.sub(r"/\*.*?\*/", "", open(os.path.join(STYLES, name), encoding="utf-8").read(), flags=re.S)
        for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
            last = [s.strip().split()[-1] for s in sel.split(",") if s.strip()]
            if not any(COMPONENT.search(s) for s in last):
                continue
            props = [d.split(":")[0].strip() for d in body.split(";") if ":" in d]
            bad += [f"{name}: {sel.strip()} {{{p}}}" for p in props if not PLACEMENT.match(p)]
    assert not bad, "restyle components in index.css (A3), not in an area file:\n" + "\n".join(bad)
