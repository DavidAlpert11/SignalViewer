#!/usr/bin/env python3
"""RE4: fetch the Tectonic LaTeX engine the app carries (backend/app/tex/tectonic[.exe]) - one pinned release, its
SHA-256 checked. Run when building a package (build.yml does it on each OS); the app then typesets LaTeX with it and
the bundle tools/make_tex_bundle.py makes, offline, when the computer has no TeX of its own.

    python tools/get_tectonic.py              # this computer's platform
    python tools/get_tectonic.py --platform windows-x64 --out DIR

Tectonic: MIT licence, https://tectonic-typesetting.github.io (its licence is written beside the binary).
"""
import argparse
import hashlib
import io
import os
import platform
import shutil
import sys
import tarfile
import urllib.request
import zipfile

VERSION = "0.17.0"
URL = "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40{v}/tectonic-{v}-{a}"
ASSETS = {   # platform -> (asset, sha256)
    "windows-x64": ("x86_64-pc-windows-msvc.zip", "f61ce51f0b0ade1015b7de7ef368541c5424e9756ecbd0d7af97d6d48030845f"),
    "linux-x64": ("x86_64-unknown-linux-musl.tar.gz", "8533d07f9ccbd7a65824b9e0459041bca34af1eb33daba48f59215593753a3b7"),
    "macos-arm64": ("aarch64-apple-darwin.tar.gz", "a3f1cac7c5678f01661a92212f58480ae3b0634115d880dbc59e2953ded45667"),
    "macos-x64": ("x86_64-apple-darwin.tar.gz", "7c90ef5b6ddb1eb1937e4337add5237b79338e4b9676459fa91187d24d6cdf80"),
}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "backend", "app", "tex")
LICENCE = """Tectonic {v} - https://github.com/tectonic-typesetting/tectonic - MIT licence:

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice
and this permission notice shall be included in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
"""


def this_platform() -> str:
    m = platform.machine().lower()
    if sys.platform.startswith("win"):
        return "windows-x64"
    if sys.platform == "darwin":
        return "macos-arm64" if m in ("arm64", "aarch64") else "macos-x64"
    return "linux-x64"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--platform", choices=sorted(ASSETS), default=this_platform())
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    asset, sha = ASSETS[a.platform]
    url = URL.format(v=VERSION, a=asset)
    print("Tectonic %s for %s: %s" % (VERSION, a.platform, url))
    with urllib.request.urlopen(url, timeout=300) as r:
        data = r.read()
    got = hashlib.sha256(data).hexdigest()
    if got != sha:
        print("SHA-256 does not match (%s, expected %s) - not used." % (got, sha))
        return 1
    os.makedirs(a.out, exist_ok=True)
    name = "tectonic.exe" if a.platform.startswith("windows") else "tectonic"
    if asset.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            body = z.read(name)
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
            member = next(m for m in t.getmembers() if os.path.basename(m.name) == "tectonic" and m.isfile())
            f = t.extractfile(member)
            assert f is not None
            body = f.read()
    dest = os.path.join(a.out, name)
    with open(dest + ".part", "wb") as f:
        f.write(body)
    shutil.move(dest + ".part", dest)
    os.chmod(dest, 0o755)
    with open(os.path.join(a.out, "TECTONIC-LICENSE.txt"), "w", encoding="utf-8") as f:
        f.write(LICENCE.format(v=VERSION))
    print("Wrote %s (%.1f MB)" % (dest, len(body) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
