"""Shared e2e browsers: one Playwright driver and one Chromium per kind for the whole run.

Launching Chromium took ~0.85 s per test - as long as a typical test itself. Each test still gets its own
fresh browser *context* (no cookies, storage or pages shared between tests), which is what isolation needs.
A browser that crashed is launched again for the next test, so one crash cannot fail the rest of the run.

    browser     - plain headless Chromium (the app's 2D UI)
    gl_browser  - software WebGL flags (the 3D view, the offline 3D page)
Set SV_CHROMIUM=/path/to/chrome to use an existing browser binary.
"""
import os

import pytest

pw = pytest.importorskip("playwright.sync_api")

PLAIN = ["--no-sandbox"]
GL = ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]


@pytest.fixture(scope="session")
def _playwright():
    with pw.sync_playwright() as p:
        yield p


class _Browsers:
    def __init__(self, p):
        self.p, self.live = p, {}

    def get(self, args):
        key = tuple(args)
        b = self.live.get(key)
        if b is None or not b.is_connected():
            exe = os.environ.get("SV_CHROMIUM")
            b = self.p.chromium.launch(args=list(args), **({"executable_path": exe} if exe else {}))
            self.live[key] = b
        return b

    def close(self):
        for b in self.live.values():
            try:
                b.close()
            except Exception:
                pass


@pytest.fixture(scope="session")
def _browsers(_playwright):
    bs = _Browsers(_playwright)
    yield bs
    bs.close()


@pytest.fixture()
def browser(_browsers):
    return _browsers.get(PLAIN)


@pytest.fixture()
def gl_browser(_browsers):
    return _browsers.get(GL)
