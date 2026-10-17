"""T35: the API lives in app/routes (one module per area), included by app/main.py.
Guards for the split: every area's router is included, no route is defined twice, and the UI's
catch-all route stays LAST (registered earlier it would answer /api/... requests)."""
import importlib
import os
import pkgutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.routing import APIRoute  # noqa: E402

import app.routes as routes_pkg  # noqa: E402
from app.main import app  # noqa: E402


def _flat(routes):
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
        elif hasattr(r, "original_router"):          # newer FastAPI keeps included routers nested
            yield from _flat(r.original_router.routes)


def test_every_route_module_is_included():
    # by endpoint function: older FastAPI copies each route into the app when a router is
    # included, newer FastAPI keeps the router nested - the endpoint is the same either way
    served = {r.endpoint for r in _flat(app.routes)}
    for m in pkgutil.iter_modules(routes_pkg.__path__):
        mod = importlib.import_module(f"app.routes.{m.name}")
        mine = [r for r in mod.router.routes if isinstance(r, APIRoute)]
        assert mine, f"app/routes/{m.name}.py has no routes"
        missing = [r.path for r in mine if r.endpoint not in served]
        assert not missing, f"app/routes/{m.name}.py is not included in main.py ({missing[:3]})"


def test_no_route_twice():
    seen = set()
    for r in _flat(app.routes):
        for meth in r.methods:
            assert (meth, r.path) not in seen, f"{meth} {r.path} is defined twice"
            seen.add((meth, r.path))


def test_ui_catch_all_is_last():
    routes = list(_flat(app.routes))
    if any(r.path == "/{full_path:path}" for r in routes):   # only when the UI is built
        assert routes[-1].path == "/{full_path:path}"


def test_main_still_exports_what_run_py_uses():
    from app import main
    assert isinstance(main.WATCHDOG, dict) and callable(main.idle_too_long) and callable(main._hostname)
