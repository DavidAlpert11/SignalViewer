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


def test_borders_over_the_offline_map_and_the_satellite_photos(pg):
    """1.20.1 (a user's request): *Borders* beside the layer - country borders and names over the
    offline map and the satellite photos; turned off, the base layer changes; the street maps have
    no such switch (their tiles draw their own)."""
    pg.evaluate("window.__sv.setState({ geoBase: 'satellite', geoBorders: true })")
    _map(pg)
    box = pg.locator(".plot .geo-borders input")
    box.wait_for()
    assert box.is_checked()
    pg.wait_for_timeout(1200)
    on = _drawn_pixels(pg)
    box.uncheck()
    pg.wait_for_function("window.__sv.state().geoBorders === false")
    pg.wait_for_timeout(800)
    sig_on = pg.evaluate("document.querySelector('.plot .geo canvas').toDataURL().length")
    box.check(); pg.wait_for_timeout(800)
    assert pg.evaluate("document.querySelector('.plot .geo canvas').toDataURL().length") != sig_on
    assert on > 10000
    pg.evaluate("window.__sv.setState({ geoBase: 'osm' })")
    pg.wait_for_selector(".plot .geo-borders", state="detached")
def _wait_for_tiles(pg, asked, prefix, tries=40):
    for _ in range(tries):
        if any(prefix in u for u in asked):
            return True
        pg.wait_for_timeout(250)
    return False


def test_automatic_map_is_offline_and_online_layers_are_marked(pg):
    """O1: a new user's map (Automatic) asks only for the offline map's tiles and shows no online sign;
    choosing an online layer shows the sign beside the layer menu."""
    asked = []
    pg.on("request", lambda r: asked.append(r.url) if "/api/tiles/" in r.url else None)
    assert pg.evaluate("window.__sv.state().geoBase") == "auto"
    _map(pg)
    assert _wait_for_tiles(pg, asked, "/api/tiles/offline_topo")
    online = ("/api/tiles/osm/", "/api/tiles/esri/", "/api/tiles/light", "/api/tiles/dark", "/api/tiles/satellite/", "/api/tiles/topo/")
    assert not any(o in u for u in asked for o in online)
    assert pg.locator(".net-badge").count() == 0
    pg.route("**/api/tiles/osm/**", lambda route: route.fulfill(status=404, body=""))   # no real download in tests
    pg.locator(".plot select[aria-label='Map']").first.select_option("osm")
    pg.wait_for_selector(".net-badge", timeout=5000)
    assert _wait_for_tiles(pg, asked, "/api/tiles/osm/")


def test_never_use_the_network_turns_online_layers_off(pg):
    """O1: with "Never use the network" an online layer chosen before falls back to the offline map,
    the online options are disabled and no online tile is asked for."""
    asked = []
    pg.on("request", lambda r: asked.append(r.url) if "/api/tiles/" in r.url else None)
    pg.evaluate("window.__sv.setState({ geoBase: 'osm', offlineOnly: true })")
    _map(pg)
    assert _wait_for_tiles(pg, asked, "/api/tiles/offline_topo")
    assert not any("/api/tiles/osm/" in u for u in asked)
    assert pg.locator(".net-badge").count() == 0
    assert pg.locator(".plot select[aria-label='Map'] option[value='osm']").first.is_disabled()
    # the setting is kept with the user's settings (Settings dialog), read by the backend too
    for _ in range(40):                                   # written shortly after the change (one request per burst)
        if pg.evaluate("fetch('/api/settings').then(r => r.json()).then(j => j.settings.offlineOnly)") is True:
            break
        pg.wait_for_timeout(250)
    else:
        raise AssertionError("offlineOnly was not saved with the settings")
