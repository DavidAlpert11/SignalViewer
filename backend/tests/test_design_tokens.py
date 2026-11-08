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
