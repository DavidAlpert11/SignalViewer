"""The offline map: terrain / roads tiles drawn by the app, names drawn by the map, and offline tiles
standing in for online ones that cannot be had.

    python -m pytest tests/e2e/test_offline_map.py -q
"""
import pytest

pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, sig  # noqa: E402,F401


def _map(pg):
    open_files(pg, "geo.csv")
    sig(pg, "Lat").click(); sig(pg, "Lon").click()
    pg.locator(".plot .mode-btn").first.click(); pg.locator(".menu.ctx button", has_text="Map").first.click()
    pg.wait_for_selector(".plot .geo canvas")


def _drawn_pixels(pg):
    return pg.evaluate("""(() => { const c = document.querySelector('.plot .geo canvas');
        const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0;
        for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n })()""")


def test_offline_map_uses_its_own_tiles_and_names(pg):
    asked = []
    pg.on("request", lambda r: asked.append(r.url) if "/api/tiles/" in r.url or "/api/basemap/" in r.url else None)
    pg.evaluate("window.__sv.setState({ geoBase: 'offline' })")
    _map(pg)
    pg.wait_for_function("document.querySelector('.plot .geo canvas') !== null")
    pg.wait_for_timeout(1500)
    assert any("/api/tiles/offline_topo/" in u for u in asked)
    assert not any("/api/tiles/osm/" in u for u in asked)                   # nothing from the internet
    assert any("/api/basemap/places" in u for u in asked)
    assert _drawn_pixels(pg) > 10000
    pg.evaluate("window.__sv.setState({ theme: 'dark' })")
    pg.wait_for_timeout(1200)
    assert any("/api/tiles/offline_topo_dark/" in u for u in asked)


def test_offline_tiles_stand_in_for_unreachable_online_ones(pg):
    # no internet: every online tile fails - the offline map's tiles are drawn in their place
    pg.route("**/api/tiles/osm/**", lambda route: route.fulfill(status=404, body=""))
    asked = []
    pg.on("request", lambda r: asked.append(r.url) if "/api/tiles/" in r.url else None)
    pg.evaluate("window.__sv.setState({ geoBase: 'osm' })")
    _map(pg)
    pg.wait_for_function("true")
    for _ in range(40):
        if any("/api/tiles/offline_topo/" in u for u in asked):
            break
        pg.wait_for_timeout(250)
    assert any("/api/tiles/osm/" in u for u in asked)
    assert any("/api/tiles/offline_topo/" in u for u in asked)
