"""T38: a UI error reaches the local log, and Help > "Copy error details" puts the version,
the system and the end of the log (with that error) on the clipboard."""
import json
import time
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import env, pg  # noqa: E402,F401


def test_ui_error_is_logged_and_copy_error_details_has_it(pg):
    # a synthetic error event: it reaches the app's handler like a real one, without failing the
    # fixture's "no page errors" check
    pg.evaluate("""window.dispatchEvent(new ErrorEvent("error",
        { message: "probe e2e 31337", error: new Error("probe e2e 31337") }))""")
    url = pg.env["url"] + "/api/diagnostics"
    for _ in range(50):                                   # wait for the END state: the error in the log
        if "probe e2e 31337" in json.loads(urllib.request.urlopen(url).read())["text"]:
            break
        time.sleep(0.1)
    else:
        pytest.fail("the UI error did not reach the log")

    pg.evaluate("window.__sv.setState({ helpOpen: true })")
    pg.click(".help-foot button")
    pg.wait_for_selector("text=Error details copied")
    clip = pg.evaluate("navigator.clipboard.readText()")
    assert clip.startswith("Signal Viewer ") and "System:" in clip and "probe e2e 31337" in clip
