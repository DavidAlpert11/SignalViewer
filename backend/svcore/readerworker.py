"""26.A2: the worker process that runs the user's own file readers (svcore/readers.py).

A reader is the user's code: a bug that crashes Python (a C extension, os._exit) or an endless loop
used to take the whole app down or hold the file's opening forever. Here it runs in a process of its
own; the server (app/userreaders.py) stops it after a timeout or when it crashes and starts a new one.
The reader's result (arrays, lists, labels) comes back through the pipe and is turned into a Run in
the server (readers.to_run), exactly as before.

Protocol on the pipe: ("list",) -> {"readers": [{id, name, extensions, file, path}], "errors": [...]};
("read", reader_id, path) -> ("ok", result) | ("err", message)."""
from typing import Any, Dict

from svcore import readers as rd


def main(conn, folder: str) -> None:
    found, errors = rd.load_folder(folder)
    by_id: Dict[str, Any] = {r["id"]: r for r in found}
    while True:
        try:
            msg = conn.recv()
        except (EOFError, OSError):
            return                         # the app went away
        try:
            if msg[0] == "list":
                conn.send({"readers": [{k: v for k, v in r.items() if k != "fn"} for r in found], "errors": errors})
            elif msg[0] == "read":
                _, rid, path = msg
                r = by_id.get(rid)
                if r is None:
                    conn.send(("err", f"The reader {rid} is not in your readers folder any more."))
                    continue
                try:
                    conn.send(("ok", r["fn"](path)))
                except Exception as e:
                    conn.send(("err", f'The reader "{r["name"]}" failed: {rd._short(e, r["path"])}'))
            else:
                conn.send(("err", f"unknown request {msg[0]!r}"))
        except (BrokenPipeError, OSError):
            return
