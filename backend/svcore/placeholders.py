"""W17: the one small placeholder engine of the launcher block - `{{name}}` filled from a run's values.

No Jinja, no new dependency: a placeholder is `{{ name }}` (spaces allowed); there are no loops or filters.
Values are escaped for the file format the template is written in:

* ``xml``  - & < > " ' as entities (a value is safe inside an element or an attribute);
* ``json`` - a number as a JSON number, a text as the inside of a JSON string (the template writes the
  quotes: ``"name": "{{name}}"``; a number: ``"Kp": {{Kp}}``);
* ``raw``  - as it is (INI, plain text, a command line's arguments).

An unknown placeholder is an error that names it and lists the names that are known.
"""
import json
import math
import os
import re
from typing import Any, Dict, List, Mapping, Sequence
from xml.sax.saxutils import escape

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.\-\[\] ]*?)\s*\}\}")


class PlaceholderError(ValueError):
    pass


def fmt_for(path: str) -> str:
    """The escaping a template file's name asks for: .xml -> xml, .json -> json, else raw."""
    ext = os.path.splitext(path)[1].lower()
    return "xml" if ext == ".xml" else "json" if ext == ".json" else "raw"


def _text(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)
    return str(v)


def _escape(v: Any, fmt: str) -> str:
    if fmt == "xml":
        return escape(_text(v), {'"': "&quot;", "'": "&apos;"})
    if fmt == "json":
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            if isinstance(v, float) and not math.isfinite(v):
                raise PlaceholderError(f"{v} cannot be written in JSON.")
            return json.dumps(v)
        return json.dumps(str(v), ensure_ascii=False)[1:-1]
    return _text(v)


def names(template: str) -> List[str]:
    """The placeholders a template uses, each once, in order."""
    return list(dict.fromkeys(m.group(1).strip() for m in PLACEHOLDER.finditer(template)))


def render(template: str, values: Mapping[str, Any], fmt: str = "raw", where: str = "the template") -> str:
    """The template with every placeholder replaced; an unknown one is a PlaceholderError naming it."""
    unknown = [n for n in names(template) if n not in values]
    if unknown:
        known = ", ".join(sorted(values)) or "none"
        raise PlaceholderError(f"{where}: unknown placeholder {', '.join('{{' + u + '}}' for u in unknown)} "
                               f"(known here: {known}). Check the spelling against the table's column names.")
    return PLACEHOLDER.sub(lambda m: _escape(values[m.group(1).strip()], fmt), template)


def render_args(args: Sequence[str], values: Mapping[str, Any], lists: Mapping[str, Sequence[str]] = {},
                where: str = "submit") -> List[str]:
    """A command line as an argument list (no shell): each argument rendered raw; an argument that is exactly
    one list placeholder (`{{study_cli}}`) becomes several arguments."""
    out: List[str] = []
    for a in args:
        m = PLACEHOLDER.fullmatch(a.strip())
        if m and m.group(1).strip() in lists:
            out += list(lists[m.group(1).strip()])
            continue
        out.append(render(a, {**values, **{k: " ".join(v) for k, v in lists.items()}}, "raw", where))
    return out


def run_values(values: Dict[str, Any], run_id: str, table: str, round_no: int) -> Dict[str, Any]:
    """What a run's template may use: its columns (the table's own names) and run_id, table, round."""
    return {**values, "run_id": run_id, "table": table, "round": round_no}
