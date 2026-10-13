"""Signal Viewer command line - see backend/signalviewer/cli.py, or run: python cli.py --help"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from signalviewer.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
