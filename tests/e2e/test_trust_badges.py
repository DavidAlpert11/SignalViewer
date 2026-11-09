"""
26.U6: trust badges - a result that rests on an assumption says so where it is shown (a derived
signal read between another signal's samples: "≈" on its legend chip, "interpolated" in the list of
derived signals, the tooltip says how), and the network: what leaves the PC is said in the status bar.
"""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg  # noqa: E402,F401


def _write(folder):
    with open(os.path.join(folder, "fast.csv"), "w") as f:
        f.write("time,X\n" + "".join(f"{i / 100:.2f},{i % 7}\n" for i in range(600)))
    with open(os.path.join(folder, "slow.csv"), "w") as f:      # another rate and other sample times
        f.write("time,Y\n" + "".join(f"{0.005 + i * 0.03:.3f},{i / 10:.1f}\n" for i in range(200)))


def test_interpolated_result_is_marked(pg):
    _write(pg.env["data"])
    open_files(pg, "fast.csv", "slow.csv")
    ids = S(pg, "Object.fromEntries(s.runs.filter(r => r.format !== 'derived').map(r => [r.name, r.id]))")
    pg.evaluate("""async ([a, b]) => {
        const r = await (await fetch('/api/derived', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ op: 'add', sources: [a + '/X', b + '/Y'], params: {}, name: 'X+Y' }) })).json();
        window.__sv.setState({ runs: r.runs });
        window.__sv.state().commit((ws) => { ws.tabs[0].plots[0].signals = [{ sig: r.id, color: '#0072B2', width: 1.5, scale: 1, offset: 0 }]; return ws; });
    }""", [ids["fast.csv"], ids["slow.csv"]])
    badge = pg.locator(".plot .chip .trust.compact")
    badge.wait_for()
    assert "info" in badge.get_attribute("class")                                 # how values were read: quiet
    assert "read between their samples" in badge.get_attribute("title")
    pg.click("[aria-label='Create signals']")
    mark = pg.locator(".dsig .dsig-quality")
    mark.wait_for()
    assert mark.inner_text() == "interpolated" and "How this was computed" in mark.get_attribute("title")


def test_the_network_is_said_in_the_status_bar(pg):
    assert pg.locator(".status .net-state").count() == 0                          # the default: nothing is sent
    pg.evaluate("window.__sv.setState({ offlineOnly: true })")
    assert pg.locator(".status .net-state.off").inner_text() == "Network off"
    pg.evaluate("window.__sv.setState({ offlineOnly: false, geoBase: 'osm' })")
    assert pg.locator(".status .net-state").count() == 0                          # no map on screen
    pg.evaluate("window.__sv.state().commit((ws) => { ws.tabs[0].plots[0].mode = 'geo'; return ws; })")
    assert "Online map" in pg.locator(".status .net-state.online").inner_text()
    pg.evaluate("window.__sv.setState({ geoBase: 'auto' })")
    assert pg.locator(".status .net-state").count() == 0
