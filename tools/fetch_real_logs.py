"""A5: download the public flight logs the real-log tests use (backend/tests/test_real_logs.py).

    python tools/fetch_real_logs.py            # into ~/.cache/signalviewer-test-logs (or SV_REAL_LOGS_CACHE)

Each one is pinned to a commit of its project and checked against its SHA-256. They are NOT copied
into this repository (their licences: PX4 pyulog BSD-3-Clause, ArduPilot pymavlink LGPL-3.0,
ArduPilot UAV Log Viewer GPL-3.0); the tests read them from the cache and skip when they are not there.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "backend", "tests"))

from test_real_logs import PUBLIC_LOGS, cache_dir, fetch  # noqa: E402


def main() -> int:
    print(f"cache: {cache_dir()}")
    for name, (url, _, licence) in sorted(PUBLIC_LOGS.items()):
        path = fetch(name, download=True)
        print(f"  ok  {name:24s} {os.path.getsize(path) / 1e6:6.2f} MB  ({licence})")
    print("now: cd backend && python -m pytest -q tests/test_real_logs.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
