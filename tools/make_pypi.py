"""T56: build the packages for PyPI - the same code twice (T62):

    signalviewer        `pip install signalviewer`: everything (every reader, PDF / Word reports)
    signalviewer-lite   `pip install signalviewer-lite`: the core, the rest as extras
                        ([parquet] [hdf5] [mavlink] [px4] [ros] [reports] [desktop] [all])

    python tools/make_pypi.py            # -> dist-pypi/: a wheel and an sdist of each
    python tools/make_pypi.py --check    # also installs each wheel in a fresh venv and starts the app

Both install the same `signalviewer` Python package - install one of them, not both.

The repository keeps its layout (backend/app, backend/svcore, frontend/dist); this script stages a
package tree under build/pypi and builds it there:

    signalviewer/                 the Python API and command line (backend/signalviewer)
    signalviewer/launcher.py      `signalviewer` command: the app (run.py, unchanged, from _core)
    signalviewer/_core/app, svcore, run.py, ui/ (the built UI), examples/

`signalviewer/__init__.py` puts `_core` on sys.path, so the app's modules import as in the source
folder. The UI must be built first (frontend/dist, the release does it).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STAGE_ROOT = os.path.join(ROOT, "build", "pypi")
STAGE = STAGE_ROOT                                   # the flavour being staged (stage() sets it)
FLAVOURS = ("signalviewer", "signalviewer-lite")
OUT = os.path.join(ROOT, "dist-pypi")

LAUNCHER = '''"""`signalviewer` command: start the app (the same launcher as `python run.py`)."""
import os
import runpy
import sys


def main() -> None:
    core = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_core")
    os.environ.setdefault("SV_DIST", os.path.join(core, "ui"))
    os.environ.setdefault("SV_EXAMPLES", os.path.join(core, "examples"))
    if core not in sys.path:
        sys.path.insert(0, core)
    sys.argv[0] = "signalviewer"
    runpy.run_path(os.path.join(core, "run.py"), run_name="__main__")


if __name__ == "__main__":
    main()
'''

# pywebview needs a GUI toolkit on Linux (GTK / Qt) and cannot always be installed: an extra -
# without it the app opens in the browser
# T59: the optional parts (backend/svcore/extras.py) - package -> its extra; "all" gets every one
sys.path.insert(0, os.path.join(ROOT, "backend"))
from svcore.extras import EXTRAS  # noqa: E402
OPTIONAL = {pkg: extra for extra, pkgs in EXTRAS.items() for pkg in pkgs}


def requirements():
    req, extra = [], {}
    for line in open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8"):
        spec = line.split("#")[0].strip()
        if not spec:
            continue
        name = re.split(r"[<>=!~ ]", spec)[0]
        if name in OPTIONAL:
            extra.setdefault(OPTIONAL[name], []).append(spec)
        else:
            req.append(spec)
    return req, extra


REPO = "https://github.com/DavidAlpert11/SignalViewer"


def pypi_readme(text, ver):
    """F32: the README's pictures and links are relative to the repository, and PyPI shows them
    broken. Point them at the release's tag (the wheel is published from it)."""
    raw = f"https://raw.githubusercontent.com/DavidAlpert11/SignalViewer/v{ver}/"
    text = re.sub(r'src="(?!https?:|data:)([^"]+)"', lambda m: f'src="{raw}{m.group(1)}"', text)
    text = re.sub(r'href="(?!https?:|#|mailto:)([^"]+)"', lambda m: f'href="{REPO}/blob/v{ver}/{m.group(1)}"', text)
    return re.sub(r"\]\((?!https?:|#|mailto:)([^)\s]+)\)", lambda m: f"]({REPO}/blob/v{ver}/{m.group(1)})", text)


def version():
    src = open(os.path.join(ROOT, "backend", "app", "version.py"), encoding="utf-8").read()
    return re.search(r'__version__\s*=\s*"([^"]+)"', src).group(1)


def flavour_metadata(name, req, extra):
    """(dependencies, extras) of a flavour. Full: every reader and report is a dependency; only the
    desktop window (pywebview needs GTK / Qt on Linux) stays an extra. Lite: the core + extras."""
    extra = dict(extra)
    if name == "signalviewer":
        deps = req + [x for k, xs in extra.items() if k != "desktop" for x in xs]
        opt = {"desktop": extra.get("desktop", [])}
        opt["all"] = list(opt["desktop"])               # "[all]" keeps working: it is the default here
        return deps, opt
    extra["all"] = sorted({x for xs in extra.values() for x in xs})
    return req, extra


def stage(name="signalviewer"):
    global STAGE
    dist = os.path.join(ROOT, "frontend", "dist")
    if not os.path.isfile(os.path.join(dist, "index.html")):
        sys.exit("Build the UI first (cd frontend && npm ci && npm run build).")
    STAGE = os.path.join(STAGE_ROOT, name)
    shutil.rmtree(STAGE, ignore_errors=True)
    pkg = os.path.join(STAGE, "signalviewer")
    core = os.path.join(pkg, "_core")
    ign = shutil.ignore_patterns("__pycache__", "*.pyc", "tests")
    shutil.copytree(os.path.join(ROOT, "backend", "signalviewer"), pkg, ignore=ign)
    shutil.copytree(os.path.join(ROOT, "backend", "app"), os.path.join(core, "app"), ignore=ign)
    shutil.copytree(os.path.join(ROOT, "backend", "svcore"), os.path.join(core, "svcore"), ignore=ign)
    shutil.copytree(dist, os.path.join(core, "ui"))
    shutil.copytree(os.path.join(ROOT, "examples"), os.path.join(core, "examples"), ignore=ign)
    shutil.copy2(os.path.join(ROOT, "run.py"), os.path.join(core, "run.py"))
    with open(os.path.join(pkg, "launcher.py"), "w", encoding="utf-8") as f:
        f.write(LAUNCHER)
    shutil.copy2(os.path.join(ROOT, "LICENSE"), os.path.join(STAGE, "LICENSE"))
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        readme = pypi_readme(f.read(), version())
    with open(os.path.join(STAGE, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme)
    req, extra = requirements()
    q = lambda xs: ", ".join(f'"{x}"' for x in xs)
    unknown = sorted(set(OPTIONAL) - {re.split(r"[<>=!~ ]", x)[0] for xs in extra.values() for x in xs})
    if unknown:                                       # extras.py names a package requirements.txt lacks
        sys.exit(f"svcore/extras.py lists packages that are not in requirements.txt: {', '.join(unknown)}")
    req, extra = flavour_metadata(name, req, extra)
    extras = "\n".join(f"{k} = [{q(v)}]" for k, v in extra.items())
    desc = ("Look at recorded signals - test runs, flight logs (ArduPilot, PX4, MAVLink), CAN, simulation output - offline."
            + ("" if name == "signalviewer" else " The light install: the core, every other reader as an extra."))
    toml = f'''[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "{name}"
version = "{version()}"
description = "{desc}"
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
requires-python = ">=3.9"
dependencies = [{q(req)}]
keywords = ["signals", "plotting", "time series", "flight log", "flight test", "ardupilot", "px4", "mavlink",
            "ulog", "ros2", "mcap", "telemetry", "csv", "parquet", "hdf5", "matlab", "offline"]
classifiers = [
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3 :: Only",
  "Operating System :: OS Independent",
  "Environment :: Web Environment",
  "Framework :: FastAPI",
  "Topic :: Scientific/Engineering",
  "Topic :: Scientific/Engineering :: Visualization",
  "Intended Audience :: Science/Research",
  "Intended Audience :: Developers",
  "Natural Language :: English",
  "Natural Language :: Hebrew",
]

[project.optional-dependencies]
{extras}

[project.urls]
Homepage = "{REPO}"
Documentation = "{REPO}/blob/main/docs/GUIDE.md"
Changelog = "{REPO}/blob/main/CHANGELOG.md"
Issues = "{REPO}/issues"
Releases = "{REPO}/releases"

[project.scripts]
signalviewer = "signalviewer.launcher:main"
signalviewer-cli = "signalviewer.cli:main"

[tool.setuptools.packages.find]
include = ["signalviewer*"]

[tool.setuptools.package-data]
"*" = ["**/*"]
'''
    with open(os.path.join(STAGE, "pyproject.toml"), "w", encoding="utf-8") as f:
        f.write(toml)
    # package-data globs only reach folders that are packages: make every folder of the tree one
    for d, _, files in os.walk(pkg):
        if "__init__.py" not in files:
            open(os.path.join(d, "__init__.py"), "w").close()


def build():
    """Both flavours into dist-pypi/."""
    shutil.rmtree(OUT, ignore_errors=True)
    for name in FLAVOURS:
        stage(name)
        subprocess.check_call([sys.executable, "-m", "build", "--outdir", OUT, STAGE])
    return [os.path.join(OUT, f) for f in sorted(os.listdir(OUT))]


def check(wheel, lite=False):
    """Install the wheel in a fresh venv, start the app, ask it for the UI and the examples."""
    with tempfile.TemporaryDirectory() as tmp:
        venv = os.path.join(tmp, "venv")
        subprocess.check_call([sys.executable, "-m", "venv", venv])
        bin_ = os.path.join(venv, "Scripts" if os.name == "nt" else "bin")
        py = os.path.join(bin_, "python")
        subprocess.check_call([py, "-m", "pip", "install", "-q", wheel])
        home = os.path.join(tmp, "home")
        os.makedirs(home)
        env = dict(os.environ, HOME=home, USERPROFILE=home)
        port = 8899
        exe = os.path.join(bin_, "signalviewer")
        proc = subprocess.Popen([exe, "--port", str(port), "--no-open", "--browser"], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=tmp)
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(120):
                try:
                    page = urllib.request.urlopen(base + "/", timeout=2).read().decode()
                    break
                except OSError:
                    time.sleep(0.5)
            else:
                raise SystemExit("The installed app did not start:\n" + proc.stdout.read1().decode(errors="replace"))
            assert "<div id=\"root\"" in page, "no UI page"
            ex = urllib.request.urlopen(base + "/api/examples", timeout=5).read().decode()
            assert "uav_flight.csv" in ex, ex
            out = subprocess.run([os.path.join(bin_, "signalviewer-cli"), "info",
                                  os.path.join(ROOT, "examples", "run_012.csv")], env=env,
                                 capture_output=True, text=True, timeout=120)
            assert out.returncode == 0 and "Speed" in out.stdout, out.stdout + out.stderr
            # the Python API and the push client from the installed package
            code = ("import signalviewer as sv, sys; r = sv.load(sys.argv[1]); assert any(n.startswith('Speed') for n in r.signals);"
                    " import signalviewer.push_client")
            subprocess.check_call([py, "-c", code, os.path.join(ROOT, "examples", "run_012.csv")], env=env, cwd=tmp)
            req = urllib.request.Request(base + "/api/push/save-client", method="POST",
                                         data=('{"path": %s}' % json.dumps(tmp)).encode(),
                                         headers={"Content-Type": "application/json"})
            saved = json.loads(urllib.request.urlopen(req, timeout=5).read())["path"]
            assert os.path.isfile(saved), saved
            pq = os.path.join(tmp, "t.parquet")
            code = "import signalviewer as sv, sys; print(sv.load(sys.argv[1]).signals)"
            out = subprocess.run([os.path.join(bin_, "signalviewer-cli"), "info", os.path.join(ROOT, "examples", "copter_flight.bin")],
                                 env=env, capture_output=True, text=True, timeout=120)
            assert out.returncode == 0 and "ATT.Roll" in out.stdout, out.stdout + out.stderr
            if lite:
                # T59 / T62: the light install has the core; an optional part names its extra
                with open(pq, "wb") as f:            # the reader asks for pyarrow before it reads a byte
                    f.write(b"PAR1")
                out = subprocess.run([py, "-c", code, pq], env=env, capture_output=True, text=True, timeout=120)
                assert out.returncode != 0 and 'signalviewer-lite[parquet]' in out.stderr, out.stdout + out.stderr
                subprocess.check_call([py, "-m", "pip", "install", "-q", wheel + "[all]"])
            # with everything (the full package as installed, the light one with [all]) Parquet opens
            subprocess.check_call([py, "-c", "import pyarrow as pa, pyarrow.parquet as q, sys; q.write_table("
                                   "pa.table({'time': [0.0, 1.0, 2.0], 'x': [1.0, 2.0, 3.0]}), sys.argv[1])", pq])
            out = subprocess.run([py, "-c", code, pq], env=env, capture_output=True, text=True, timeout=120)
            assert out.returncode == 0 and "'x'" in out.stdout, out.stdout + out.stderr
            for mod in ("pyarrow", "h5py", "pymavlink", "pyulog", "mcap", "matplotlib", "docx"):
                if not lite:                         # the full package brings every reader and report
                    subprocess.check_call([py, "-c", f"import {mod}"])
            print(f"{os.path.basename(wheel)}: starts, serves the UI and the examples; the command line, the Python API and"
                  " the push client work; " + ("without extras an optional reader names its extra, and [all] brings it."
                                               if lite else "every reader and report is installed."))
        finally:
            proc.terminate()
            proc.wait(timeout=20)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="install the wheel in a fresh venv and start it")
    args = ap.parse_args()
    files = build()
    print("\n".join(files))
    if args.check:
        for f in files:
            if f.endswith(".whl"):
                check(f, lite=os.path.basename(f).startswith("signalviewer_lite"))


if __name__ == "__main__":
    main()
