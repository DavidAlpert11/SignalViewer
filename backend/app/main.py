"""
Signal Viewer - local API server.

Runs only on 127.0.0.1. The React UI (frontend/dist) is served from the same
origin. All heavy work happens here, on full-resolution data; the UI receives
only decimated display points (binary-packed, base64) and computed values.
"""

import json
import logging
import math
import os

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import crashlog
from app.routes import (
    analysis,
    compare,
    data,
    export,
    files,
    fs,
    jobs,
    live,
    maps,
    push,
    pyops,
    session,
    system,
    templates,
    video,
)

# kept importable from here: run.py and the tests use them
from app.routes.system import WATCHDOG, idle_too_long  # noqa: F401

DIST = os.environ.get("SV_DIST") or os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")


class SafeJSONResponse(JSONResponse):
    """JSON cannot carry NaN or infinity: any that slips into a response becomes null
    instead of failing the whole request with a server error."""
    def render(self, content) -> bytes:
        def clean(v):
            if isinstance(v, float):
                return v if math.isfinite(v) else None
            if isinstance(v, dict):
                return {k: clean(x) for k, x in v.items()}
            if isinstance(v, (list, tuple)):
                return [clean(x) for x in v]
            if isinstance(v, np.generic):
                return clean(v.item())
            return v
        return json.dumps(clean(content), ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")



app = FastAPI(default_response_class=SafeJSONResponse, title="Signal Viewer", docs_url="/api/docs")



# =============================================================================
# LOCAL-ONLY GUARD
# =============================================================================
# Binding to 127.0.0.1 keeps other computers out, but not a web page open in the user's own
# browser: with DNS rebinding such a page can make "evil.example" resolve to 127.0.0.1 and then
# read folders, open files and write files through this API. Browsers always send the name
# they used in Host / Origin, so answering only to loopback names closes that door.
# SV_ALLOWED_HOSTS (comma separated names) adds names on purpose, e.g. for the test client.

_LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}



def _hostname(value: str) -> str:
    """'127.0.0.1:8765' -> '127.0.0.1', '[::1]:8765' -> '::1', 'http://localhost:5173' -> 'localhost'."""
    v = value.strip().lower()
    if "://" in v:
        v = v.split("://", 1)[1].split("/", 1)[0]
    if v.startswith("["):
        return v[1:].split("]", 1)[0]
    return v.rsplit(":", 1)[0] if v.count(":") == 1 else v



def _allowed_names() -> set:
    extra = os.environ.get("SV_ALLOWED_HOSTS", "")
    return _LOOPBACK_NAMES | {x.strip().lower() for x in extra.split(",") if x.strip()}



class LocalOnlyMiddleware:
    """Plain ASGI middleware (no buffering, so downloads and long jobs are unaffected)."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.inner(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        ok = _allowed_names()
        host = headers.get("host")
        origin = headers.get("origin")
        bad = None
        if host is None or _hostname(host) not in ok:
            bad = "this server only answers requests addressed to localhost"
        elif origin is not None and (origin == "null" or _hostname(origin) not in ok):
            bad = "requests from other web sites are not accepted"
        if bad is None:
            return await self.inner(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        body = json.dumps({"detail": f"Blocked: {bad}. Open Signal Viewer at http://127.0.0.1:<port>."}).encode()
        await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})



app.add_middleware(LocalOnlyMiddleware)

# T38: what went wrong goes to ~/.signalviewer/logs (Help > Copy error details); a request that
# fails unexpectedly answers with a readable message instead of a bare "Internal Server Error".
crashlog.install()
log = logging.getLogger("signalviewer").getChild(__name__)


@app.exception_handler(Exception)
async def _unexpected_error(request: Request, exc: Exception):
    log.error("unexpected error in %s %s", request.method, request.url.path, exc_info=exc)
    return SafeJSONResponse({"detail": f"Unexpected error: {exc or exc.__class__.__name__}. "
                                       "Help > Copy error details has what is needed to report it."},
                            status_code=500)


# =============================================================================
# API ROUTES (T35: one module per area in app/routes)
# =============================================================================

app.include_router(files.router)
app.include_router(live.router)
app.include_router(data.router)
app.include_router(analysis.router)
app.include_router(compare.router)
app.include_router(export.router)
app.include_router(maps.router)
app.include_router(pyops.router)
app.include_router(push.router)
app.include_router(jobs.router)
app.include_router(system.router)
app.include_router(templates.router)
app.include_router(fs.router)
app.include_router(session.router)
app.include_router(video.router)

# =============================================================================
# STATIC UI
# =============================================================================

if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404)
        candidate = os.path.realpath(os.path.join(DIST, full_path))
        inside = candidate.startswith(os.path.realpath(DIST) + os.sep)     # no "../" out of the UI folder
        if full_path and inside and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(DIST, "index.html"))
