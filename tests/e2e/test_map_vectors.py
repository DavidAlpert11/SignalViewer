"""F6: vectors along the path - an object's two signals (north, east) drawn as arrows along its track; the object
dialog offers a file's own pair by itself (here a CSV's velocity; a log's wind is checked in Vitest).

    python -m pytest tests/e2e/test_map_vectors.py -q
"""
import os
import shutil

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, flat_maps, open_files, pg  # noqa: E402,F401

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_a_csvs_velocity_as_arrows_on_the_map(pg):
    shutil.copy(os.path.join(ROOT, "examples", "three_objects.csv"), pg.env["data"])
    open_files(pg, "three_objects.csv")
    flat_maps(pg)
    pg.locator(".obj-suggest-add").click()
    pg.wait_for_selector(".plot-canvas.geo[data-view]")
    pg.evaluate("(() => { const p = window.__sv.state().ws.tabs[0].plots.find((x) => x.objects && x.objects.length);"
                " window.__sv.setState({ objectDialog: { plotId: p.id, objectId: p.objects[0].id } }); })()")
    pg.locator(".obj-vectors .obj-vec-suggest").click()              # offered by itself: phys/nav vel.north / vel.east
    pg.locator(".obj-save").click()
    obj = "s.ws.tabs[0].plots.find((x) => x.objects && x.objects.length).objects[0]"
    assert S(pg, f"{obj}.vecN").endswith("vel.north") and S(pg, f"{obj}.vecE").endswith("vel.east")
    pg.wait_for_function("(window.__svMapVectors || 0) > 10")
    if os.environ.get("SV_SHOT_DIR"):                                 # a picture for the task's notes
        pg.wait_for_timeout(800); pg.screenshot(path=os.path.join(os.environ["SV_SHOT_DIR"], "vectors_2d.png"))
    # Undo takes the arrows away again (the object's change went through commit)
    pg.keyboard.press("Control+z")
    pg.wait_for_function("window.__svMapVectors === 0")


def test_the_same_arrows_in_3d(pg):
    shutil.copy(os.path.join(ROOT, "examples", "three_objects.csv"), pg.env["data"])
    open_files(pg, "three_objects.csv")
    pg.locator(".obj-suggest-add").click()
    pg.wait_for_selector(".globe3d", timeout=60000)
    pg.evaluate("""(() => { const ws = structuredClone(window.__sv.state().ws);
      const p = ws.tabs[0].plots.find((x) => x.objects && x.objects.length);
      const o = p.objects[0]; const run = o.lat.split('/')[0];
      o.vecN = run + '/phys.vel.north'; o.vecE = run + '/phys.vel.east'; window.__sv.setState({ ws }); })()""")
    pg.wait_for_function("(window.__svGlobeVectors || 0) > 10", timeout=60000)
