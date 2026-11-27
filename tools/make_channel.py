"""CH5: the channel example - one link recorded twice with every anomaly kind injected (backend/svcore/example_data/
make_channel.py).    python tools/make_channel.py [folder]"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from svcore.example_data import REPO_EXAMPLES  # noqa: E402
from svcore.example_data.make_channel import main  # noqa: E402

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO_EXAMPLES, "channel"))
