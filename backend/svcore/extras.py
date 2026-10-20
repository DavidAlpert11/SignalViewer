"""T59: the parts of Signal Viewer that are optional with `pip install signalviewer`.

The installer, the portable packages and `pip install -r requirements.txt` have everything; the
PyPI package installs the core (CSV, MATLAB v5, ArduPilot .bin, the analysis) and the rest as
extras. A reader or a report that needs a missing part says which extra brings it.
"""

# extra -> the packages it adds (tools/make_pypi.py builds the package's extras from this)
EXTRAS = {
    "parquet": ["pyarrow"],                                   # .parquet; also the fast CSV parser
    "hdf5": ["h5py"],                                         # .h5 / .hdf5 and MATLAB v7.3
    "mavlink": ["pymavlink", "pyserial"],                     # .tlog and live MAVLink
    "px4": ["pyulog"],                                        # .ulg
    "ros": ["mcap", "mcap-ros2-support", "lz4", "zstandard"],  # .mcap
    "reports": ["matplotlib", "python-docx", "python-bidi"],  # PDF / Word reports, images
    "desktop": ["pywebview"],                                 # its own window instead of the browser
}


def install_hint(extra: str) -> str:
    return (f'Install it with: pip install "signalviewer[{extra}]" (or "signalviewer[all]"); '
            "from the source folder: pip install -r requirements.txt.")


def missing(what: str, extra: str) -> str:
    """The message for a reader / report whose optional part is not installed."""
    return f"{what} needs a part of Signal Viewer that is not installed. {install_hint(extra)}"
