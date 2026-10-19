"""T39: arrays sent from Python (Jupyter, a simulation) into the open app.

The client (signalviewer/push_client.py, numpy only) reads ~/.signalviewer/push.json - the app's
address and a token made fresh at every start, written by run.py readable by the user only - and
posts the arrays as a numpy .npz (read with allow_pickle=False: data only, never code). Only
callers that can read that file can send: a web page cannot (it would need the token; the custom
header also makes a browser ask first, which this server never allows). The data becomes a run
named after the call; sending the same name again replaces it in place, so plots and derived
signals follow. The UI learns about it from /api/push/events."""
import io
import json
import os
import secrets
import threading
import time
from typing import Any, Dict, List

import numpy as np

from app.common import APP_DIR
from svcore.models import Run, Signal

TOKEN = secrets.token_urlsafe(24)
PUSH_FILE = os.path.join(APP_DIR, "push.json")
PREFIX = "python:"                       # file_path of a pushed run (it has no file)

_lock = threading.Lock()
_events: List[Dict[str, Any]] = []       # {"seq", "run", "plot", "name", "new", "age"}; T54: {"seq", "kind": "open", "paths"}
_seq = 0
ON_OPEN: List[Any] = []                  # T54: run.py brings its window to the front when files come from outside


def write_push_file(url: str) -> str:
    """run.py: where the client finds this app. Readable by the user only (0600)."""
    os.makedirs(APP_DIR, exist_ok=True)
    tmp = PUSH_FILE + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"url": url, "token": TOKEN, "pid": os.getpid()}, f)
    os.replace(tmp, PUSH_FILE)
    return PUSH_FILE


def remove_push_file() -> None:
    try:
        with open(PUSH_FILE, encoding="utf-8") as f:
            mine = json.load(f).get("token") == TOKEN       # another instance may have written it since
        if mine:
            os.remove(PUSH_FILE)
    except (OSError, ValueError):
        pass


def parse(body: bytes):
    """The .npz from the client -> (time, {name: values}). ValueError with a reason."""
    try:
        z = np.load(io.BytesIO(body), allow_pickle=False)
        t = np.asarray(z["__time__"], dtype=np.float64).ravel()
        names = json.loads(str(z["__names__"]))
        arrays = {str(n): np.asarray(z[f"s{i}"], dtype=np.float64).ravel() for i, n in enumerate(names)}
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ValueError(f"Not data from the Signal Viewer client ({type(e).__name__}).") from None
    if not arrays:
        raise ValueError("No signals were sent.")
    if not len(t):
        raise ValueError("The time is empty.")
    for n, y in arrays.items():
        if len(y) != len(t):
            raise ValueError(f"{n}: {len(y)} values for {len(t)} times.")
    return t, arrays


def make_run(name: str, t: np.ndarray, arrays: Dict[str, np.ndarray]) -> Run:
    order = np.argsort(t, kind="stable") if np.any(np.diff(t) < 0) else None
    if order is not None:                 # the app expects time in order
        t = t[order]
        arrays = {k: v[order] for k, v in arrays.items()}
    run = Run(file_path=PREFIX + name, csv_display_name=name, time=t,
              signals={k: Signal(name=k, data=v) for k, v in arrays.items()})
    run.compute_metadata()
    run.load_report = {"pushed": True}
    return run


def add_event(run_id: str, name: str, plot: bool, new: bool) -> int:
    global _seq
    with _lock:
        _seq += 1
        _events.append({"seq": _seq, "run": run_id, "name": name, "plot": plot, "new": new, "time": time.time()})
        del _events[:-200]               # the UI asks every second: a short memory is enough
        return _seq


def add_open_event(paths: List[str]) -> int:
    """T54: files to open, from the command line or from a second start (app/instance.py)."""
    global _seq
    with _lock:
        _seq += 1
        _events.append({"seq": _seq, "kind": "open", "paths": list(paths), "time": time.time()})
        del _events[:-200]
        return _seq


def events_since(since: int, opens: bool = False) -> Dict[str, Any]:
    """Events after `since`, each with its age in seconds (the UI's first ask uses it: data sent
    while the page was loading is shown, older data - before a page reload - is not plotted again).
    T54: files to open are not tied to `since`: they are handed out once, to the first ask that
    takes them (`opens`: the page has restored the last work) - a reload does not open them again."""
    now = time.time()
    with _lock:
        out = []
        for e in _events:
            if e.get("kind") == "open":
                if not opens or e.get("taken"):
                    continue
                e["taken"] = True
            elif e["seq"] <= since:
                continue
            out.append({**{k: v for k, v in e.items() if k not in ("time", "taken")}, "age": now - e["time"]})
        return {"seq": _seq, "events": out}
