"""The frontend's lint gate (oxlint) with a baseline (CC18, like mypy's T36b): the warnings already in the code are
counted per file and rule in tools/oxlint_baseline.json; the check fails only when a file has MORE of a rule than
its baseline - a new warning - so the old ones can be fixed gradually without the gate ever being red for them.
Counted per (file, rule), not per line, so a moved line is not "new".

    python tools/lint_baseline.py            # the check (exit 1 on a new warning, listed)
    python tools/lint_baseline.py --update   # write the baseline from today's warnings (after fixing some)

An error-level rule (rules-of-hooks) fails always, baseline or not."""
import argparse
import collections
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "frontend")
BASELINE = os.path.join(ROOT, "tools", "oxlint_baseline.json")
NPX = shutil.which("npx") or shutil.which("npx.cmd") or "npx"


def diagnostics() -> list:
    out = subprocess.run([NPX, "oxlint", "-f", "json"], cwd=FRONTEND, capture_output=True, text=True)
    try:
        return json.loads(out.stdout)["diagnostics"]
    except (ValueError, KeyError):
        sys.stderr.write(out.stdout + out.stderr)
        raise SystemExit("oxlint gave no JSON - is `npm ci` done in frontend/?")


def counts(diags: list) -> dict:
    c: dict = collections.defaultdict(dict)
    for d in diags:
        f = d["filename"].replace("\\", "/")
        c[f][d["code"]] = c[f].get(d["code"], 0) + 1
    return {f: dict(sorted(r.items())) for f, r in sorted(c.items())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true", help="write the baseline from today's warnings")
    a = ap.parse_args()
    diags = diagnostics()
    errors = [d for d in diags if d.get("severity") == "error"]
    now = counts([d for d in diags if d.get("severity") != "error"])
    if a.update:
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump(now, f, indent=1, sort_keys=True)
            f.write("\n")
        print(f"baseline: {sum(sum(r.values()) for r in now.values())} warnings in {len(now)} files")
        return 1 if errors else 0
    try:
        with open(BASELINE, encoding="utf-8") as f:
            base = json.load(f)
    except FileNotFoundError:
        base = {}
    new = [(f, rule, n, base.get(f, {}).get(rule, 0)) for f, r in now.items() for rule, n in r.items()
           if n > base.get(f, {}).get(rule, 0)]
    for d in errors:
        print(f"error {d['filename']}: {d['code']} - {d['message']}")
    for f, rule, n, was in new:
        lines = [str(lb["span"]["line"]) for d in diags if d["filename"].replace("\\", "/") == f and d["code"] == rule
                 for lb in d.get("labels", [])[:1] if "span" in lb and "line" in lb["span"]]
        print(f"new warning {f}: {rule} ({was} -> {n}; lines {', '.join(lines)})")
    fixed = sum(max(0, n - now.get(f, {}).get(rule, 0)) for f, r in base.items() for rule, n in r.items())
    total = sum(sum(r.values()) for r in now.values())
    print(f"oxlint: {total} warnings, none new" if not new and not errors else
          "oxlint: fix the new ones (or, for a deliberate one, a comment + `python tools/lint_baseline.py --update`)")
    if fixed and not new:
        print(f"  {fixed} fewer than the baseline - `python tools/lint_baseline.py --update` to lock that in")
    return 1 if new or errors else 0


if __name__ == "__main__":
    sys.exit(main())
