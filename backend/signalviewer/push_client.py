"""Send arrays from Python (Jupyter, a simulation, a script) to an open Signal Viewer.

One file, numpy only: copy it next to your notebook (Signal Viewer: Create signals > Python >
Save the Python client...), then:

    from signalviewer_push import show
    show(t, {"altitude": alt, "speed": v}, name="sim run 3")   # a run named "sim run 3"
    show(t, y)                                                  # one signal, named "y"
    show(df)                                                    # a pandas DataFrame: index = time

Sending the same name again replaces that run's data, so the plots update (a simulation can send
every few steps). plot=True puts a new run's signals in the active plot. The app must be running;
it writes its address and a fresh token to ~/.signalviewer/push.json at every start, and only
programs that can read that file can send to it.
"""
import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

__all__ = ["show"]


def _connection(home=None):
    path = os.path.join(home or os.path.expanduser("~"), ".signalviewer", "push.json")
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d["url"], d["token"]
    except (OSError, ValueError, KeyError):
        raise RuntimeError("Signal Viewer is not running (start it, then send again).") from None


def _as_signals(t, signals):
    if signals is None and hasattr(t, "columns") and hasattr(t, "index"):     # pandas DataFrame
        df = t
        return (np.asarray(df.index, dtype=np.float64),
                {str(c): np.asarray(df[c], dtype=np.float64) for c in df.columns})
    if signals is None:
        raise ValueError("Give the time and the signals: show(t, {'name': values}) or show(t, values).")
    if not isinstance(signals, dict):
        signals = {"y": signals}
    arrays = {str(k): np.asarray(v, dtype=np.float64).ravel() for k, v in signals.items()}
    if not arrays:
        raise ValueError("No signals to send.")
    n = len(next(iter(arrays.values())))
    tt = np.arange(n, dtype=np.float64) if t is None else np.asarray(t, dtype=np.float64).ravel()
    for k, v in arrays.items():
        if len(v) != len(tt):
            raise ValueError(f"{k}: {len(v)} values for {len(tt)} times.")
    return tt, arrays


def show(t=None, signals=None, name="Python", replace=True, plot=True, home=None, timeout=60):
    """Send signals to the open Signal Viewer. Returns the app's answer (run id, signal ids)."""
    tt, arrays = _as_signals(t, signals)
    buf = io.BytesIO()
    names = list(arrays)
    np.savez(buf, __time__=tt, __names__=np.array(json.dumps(names)),
             **{f"s{i}": arrays[n] for i, n in enumerate(names)})
    url, token = _connection(home)
    query = urllib.parse.urlencode({"name": name, "replace": str(bool(replace)).lower(),
                                    "plot": str(bool(plot)).lower()})
    req = urllib.request.Request(f"{url}/api/push?{query}", data=buf.getvalue(), method="POST",
                                 headers={"Content-Type": "application/octet-stream", "X-SV-Token": token})
    try:
        # never through a proxy: the app is on this computer (a company proxy setting would swallow it)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e).get("detail", str(e))
        except ValueError:
            msg = str(e)
        raise RuntimeError(f"Signal Viewer: {msg}") from None
    except urllib.error.URLError:
        raise RuntimeError("Signal Viewer is not running (start it, then send again).") from None
