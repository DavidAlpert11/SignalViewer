import os
import re


def name_pattern(name: str) -> str:
    """run_012.csv and run_013.csv share a pattern: digit runs become '#'."""
    stem, ext = os.path.splitext(name.lower())
    return re.sub(r"\d+", "#", stem) + ext
