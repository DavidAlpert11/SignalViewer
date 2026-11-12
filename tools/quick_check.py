"""The quick check after every change (W11): tsc, Vitest, the backend tests, mypy - in that order,
stopping at the first failure. Cross-platform (Windows, macOS, Linux); no e2e (see docs/dev/E2E_MAP.md).

    python tools/quick_check.py            # all four
    python tools/quick_check.py --skip mypy,vitest

Exit code 0 = all green, otherwise the failing step's code."""
import argparse
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NPX = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
STEPS = [
    ("tsc", [NPX, "tsc", "-b"], os.path.join(ROOT, "frontend")),
    ("vitest", [NPX, "vitest", "run"], os.path.join(ROOT, "frontend")),
    ("pytest", [sys.executable, "-m", "pytest", "-q", "-x"], os.path.join(ROOT, "backend")),
    ("mypy", [sys.executable, "-m", "mypy", "--config-file", "../pyproject.toml", "app", "svcore", "signalviewer"],
     os.path.join(ROOT, "backend")),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip", default="", help="comma-separated steps to skip: " + ", ".join(s[0] for s in STEPS))
    a = ap.parse_args()
    skip = {x.strip() for x in a.skip.split(",") if x.strip()}
    for name, cmd, cwd in STEPS:
        if name in skip:
            print(f"-- {name}: skipped", flush=True)
            continue
        print(f"-- {name}: {' '.join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd))}", flush=True)
        t0 = time.monotonic()
        code = subprocess.call(cmd, cwd=cwd)
        print(f"-- {name}: {'ok' if code == 0 else 'FAILED (exit %d)' % code} in {time.monotonic() - t0:.1f} s", flush=True)
        if code != 0:
            return code
    print("-- all green", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
