"""T56: build the `signalviewer` package for PyPI (`pip install signalviewer`).

    python tools/make_pypi.py            # -> dist-pypi/signalviewer-X.Y.Z-py3-none-any.whl and .tar.gz
    python tools/make_pypi.py --check    # also installs the wheel in a fresh venv and starts the app

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
STAGE = os.path.join(ROOT, "build", "pypi")
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
OPTIONAL = {"pywebview": "desktop"}


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


def version():
    src = open(os.path.join(ROOT, "backend", "app", "version.py"), encoding="utf-8").read()
    return re.search(r'__version__\s*=\s*"([^"]+)"', src).group(1)


def stage():
    dist = os.path.join(ROOT, "frontend", "dist")
    if not os.path.isfile(os.path.join(dist, "index.html")):
        sys.exit("Build the UI first (cd frontend && npm ci && npm run build).")
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
    for name in ("README.md", "LICENSE"):
        shutil.copy2(os.path.join(ROOT, name), os.path.join(STAGE, name))
    req, extra = requirements()
    q = lambda xs: ", ".join(f'"{x}"' for x in xs)
    extras = "\n".join(f"{k} = [{q(v)}]" for k, v in extra.items())
    toml = f'''[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "signalviewer"
version = "{version()}"
description = "Look at recorded signals - test runs, flight logs (ArduPilot, PX4, MAVLink), simulation output - offline."
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
requires-python = ">=3.9"
dependencies = [{q(req)}]
keywords = ["signals", "plotting", "flight log", "ardupilot", "px4", "mavlink", "telemetry", "csv", "matlab"]
classifiers = [
  "Programming Language :: Python :: 3",
  "Operating System :: OS Independent",
  "Topic :: Scientific/Engineering :: Visualization",
  "Intended Audience :: Science/Research",
]

[project.optional-dependencies]
{extras}

[project.urls]
Homepage = "https://github.com/DavidAlpert11/SignalViewer"
Guide = "https://github.com/DavidAlpert11/SignalViewer/blob/main/docs/GUIDE.md"

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
    shutil.rmtree(OUT, ignore_errors=True)
    subprocess.check_call([sys.executable, "-m", "build", "--outdir", OUT, STAGE])
    return [os.path.join(OUT, f) for f in sorted(os.listdir(OUT))]


def check(wheel):
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
            print("The installed package starts, serves the UI and the examples; the command line, the Python API and the push client work.")
        finally:
            proc.terminate()
            proc.wait(timeout=20)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="install the wheel in a fresh venv and start it")
    args = ap.parse_args()
    stage()
    files = build()
    print("\n".join(files))
    if args.check:
        check(next(f for f in files if f.endswith(".whl")))


if __name__ == "__main__":
    main()
