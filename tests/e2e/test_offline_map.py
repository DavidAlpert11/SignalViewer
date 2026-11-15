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


PIXELS = """(() => { const c = document.querySelector('.plot .geo canvas');
        const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0;
        for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n })()"""


def _drawn_pixels(pg):
    return pg.evaluate(PIXELS)


def _wait_pixels(pg, n, timeout=15000):
    """T2: the map has drawn more than n pixels (instead of a fixed sleep)."""
    pg.wait_for_function(f"{PIXELS} > {n}", timeout=timeout)


def _wait_redrawn(pg, before, timeout=10000):
    """T2: the map's picture is no longer `before` (its data URL's length)."""
    pg.wait_for_function("b => document.querySelector('.plot .geo canvas').toDataURL().length !== b", arg=before, timeout=timeout)


def test_offline_map_uses_its_own_tiles_and_names(pg):
    asked = []
    pg.on("request", lambda r: asked.append(r.url) if "/api/tiles/" in r.url or "/api/basemap/" in r.url else None)
    pg.evaluate("window.__sv.setState({ geoBase: 'offline' })")
    _map(pg)
    pg.wait_for_function("document.querySelector('.plot .geo canvas') !== null")
    _wait_for_tiles(pg, asked, "/api/tiles/offline_topo/"); _wait_for_tiles(pg, asked, "/api/basemap/places"); _wait_pixels(pg, 10000)
    assert any("/api/tiles/offline_topo/" in u for u in asked)
    assert not any("/api/tiles/osm/" in u for u in asked)                   # nothing from the internet
    assert any("/api/basemap/places" in u for u in asked)
    assert _drawn_pixels(pg) > 10000
    pg.evaluate("window.__sv.setState({ theme: 'dark' })")
    _wait_for_tiles(pg, asked, "/api/tiles/offline_topo_dark/")
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
    """1.20.1 (a user's request): *Borders* beside the layer (since M1 in the map's background picker) - country borders and names over the
    offline map and the satellite photos; turned off, the base layer changes; the street maps have
    no such switch (their tiles draw their own)."""
    pg.evaluate("window.__sv.setState({ geoBase: 'satellite', geoBorders: true })")
    _map(pg)
    pg.locator(".map-layers-btn").first.click()          # M1: Borders lives in the map's background picker
    box = pg.locator(".plot .ml-borders input")
    box.wait_for()
    assert box.is_checked()
    _wait_pixels(pg, 10000)
    on = _drawn_pixels(pg)
    shown = pg.evaluate("document.querySelector('.plot .geo canvas').toDataURL().length")
    box.uncheck()
    pg.wait_for_function("window.__sv.state().geoBorders === false")
    _wait_redrawn(pg, shown)
    sig_on = pg.evaluate("document.querySelector('.plot .geo canvas').toDataURL().length")
    box.check(); _wait_redrawn(pg, sig_on)
    assert pg.evaluate("document.querySelector('.plot .geo canvas').toDataURL().length") != sig_on
    assert on > 10000
    pg.evaluate("window.__sv.setState({ geoBase: 'osm' })")
    pg.wait_for_selector(".plot .ml-borders", state="detached")
def _pick(pg, base):
    """M1: choose a map background in the picker (top-end of the map)."""
    pg.locator(".map-layers-btn").first.click()
    pg.locator(f".ml-card[data-base='{base}'] .ml-pick").first.click()
    pg.wait_for_function(f"window.__sv.state().geoBase === '{base}'")
    pg.keyboard.press("Escape")


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
    assert pg.locator(".map-layers-btn .ml-cloud").count() == 0
    pg.route("**/api/tiles/osm/**", lambda route: route.fulfill(status=404, body=""))   # no real download in tests
    _pick(pg, "osm")                                                    # M1: the background picker
    pg.wait_for_selector(".map-layers-btn .ml-cloud", timeout=5000)
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
    assert pg.locator(".map-layers-btn .ml-cloud").count() == 0
    pg.locator(".map-layers-btn").first.click()
    assert pg.locator(".ml-card[data-base=osm] .ml-pick").first.is_disabled()
    assert "Never use the network" in pg.locator(".ml-net").first.inner_text()
    pg.keyboard.press("Escape")
    # the setting is kept with the user's settings (Settings dialog), read by the backend too
    for _ in range(40):                                   # written shortly after the change (one request per burst)
        if pg.evaluate("fetch('/api/settings').then(r => r.json()).then(j => j.settings.offlineOnly)") is True:
            break
        pg.wait_for_timeout(250)
    else:
        raise AssertionError("offlineOnly was not saved with the settings")


def test_satellite_with_roads_is_one_layer(pg):
    """M2: *Satellite + roads* - one layer of the app (the photo with the roads composed over it in the backend),
    marked online, with the photo layers' *Borders* switch in the picker (M1)."""
    pg.route("**/api/tiles/satroads/**", lambda route: route.fulfill(status=404, body=""))   # no real download in tests
    asked = []
    pg.on("request", lambda r: asked.append(r.url) if "/api/tiles/" in r.url else None)
    pg.evaluate("window.__sv.setState({ geoBase: 'satroads', geoBorders: true })")
    _map(pg)
    assert _wait_for_tiles(pg, asked, "/api/tiles/satroads/")
    assert not any("/api/tiles/satellite/" in u or "/api/tiles/sat_roads/" in u for u in asked)
    pg.wait_for_selector(".map-layers-btn .ml-cloud", timeout=5000)
    pg.locator(".map-layers-btn").first.click()
    assert pg.locator(".ml-card[data-base=satroads].on").count() == 1
    assert pg.locator(".ml-borders input").first.is_checked()


def test_the_background_picker_is_one_place_and_downloads_nothing(pg):
    """M1: the picker's thumbnails: the offline map drawn by the app; an online layer only from the disk
    (`cached=1`) - opening it asks the internet for nothing; choosing sets the app's layer."""
    asked = []
    pg.on("request", lambda r: asked.append(r.url) if "/api/tiles/" in r.url else None)
    _map(pg)
    pg.locator(".map-layers-btn").first.click()
    pg.wait_for_selector(".map-layers-pop .ml-card[data-base=auto].on")
    for b in ("auto", "osm", "esri", "light", "dark", "satellite", "satroads", "topo"):
        assert pg.locator(f".ml-card[data-base={b}]").count() == 1, b
    _wait_for_tiles(pg, asked, "cached=1")
    online = [u for u in asked if any(f"/api/tiles/{b}/" in u for b in ("osm", "esri", "light", "dark", "satellite", "satroads", "topo"))]
    assert online and all("cached=1" in u for u in online), online
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".map-layers-pop", state="detached")


def test_my_maps_an_mbtiles_file_draws_offline(pg, env):
    """M4: Add a map… -> an MBTiles file -> a card in the picker, chosen, its tiles drawn through the app; removed again."""
    import io
    import os
    import sqlite3

    from PIL import Image
    path = os.path.join(env["data"], "our_gis.mbtiles")
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE metadata (name text, value text)")
    con.execute("CREATE TABLE tiles (zoom_level integer, tile_column integer, tile_row integer, tile_data blob)")
    con.executemany("INSERT INTO metadata VALUES (?, ?)", [("name", "Our GIS"), ("format", "png"), ("maxzoom", "16")])
    b = io.BytesIO(); Image.new("RGB", (256, 256), (200, 30, 30)).save(b, "PNG")
    for z in range(0, 17):
        con.execute("INSERT INTO tiles VALUES (?, ?, ?, ?)", (z, 0, 0, b.getvalue()))
    con.commit(); con.close()
    asked = []
    pg.on("request", lambda r: asked.append(r.url) if "/api/tiles/my" in r.url else None)
    _map(pg)
    pg.locator(".map-layers-btn").first.click()
    pg.locator(".ml-actions button", has_text="Add a map").click()
    pg.locator(".mymap-dialog .mm-path").fill(path)
    pg.locator(".mymap-dialog .mm-add").click()
    pg.wait_for_function("window.__sv.state().geoBase.startsWith('my:')")
    src = pg.evaluate("window.__sv.state().geoBase")
    assert _wait_for_tiles(pg, asked, "/api/tiles/my")
    pg.locator(".map-layers-btn").first.click()
    card = pg.locator(f".ml-card[data-base='{src}']")
    assert card.count() == 1 and "Our GIS" in card.inner_text()
    assert pg.locator(".map-layers-btn .ml-cloud").count() == 0           # a file is not online
    card.locator(".ml-remove").click()
    pg.wait_for_function("window.__sv.state().geoBase === 'auto'")
    pg.wait_for_selector(f".ml-card[data-base='{src}']", state="detached")


def test_keep_this_area_offline_refuses_what_the_terms_forbid(pg):
    """M3: the dialog estimates the area (the recordings' area by default) and refuses a layer whose servers forbid
    bulk downloading, with the reason; the ground heights may be kept. Nothing is downloaded here."""
    pg.route("**/api/tiles/osm/**", lambda route: route.fulfill(status=404, body=""))
    pg.evaluate("window.__sv.setState({ geoBase: 'osm' })")
    _map(pg)
    pg.locator(".map-layers-btn").first.click()
    pg.locator(".ml-actions button", has_text="Keep this area offline").click()
    dlg = pg.locator(".keep-dialog")
    dlg.locator("select").select_option("osm")
    pg.wait_for_function("(document.querySelector('.keep-dialog .keep-est') || {}).textContent?.includes('forbid bulk')")
    assert dlg.locator(".keep-start").is_disabled()
    dlg.locator("select").select_option("terrarium")
    pg.wait_for_function("(document.querySelector('.keep-dialog .keep-est') || {}).textContent?.includes('kept already')")
    assert "tiles" in dlg.locator(".keep-est").first.inner_text()
    assert int(dlg.locator(".keep-est").first.get_attribute("data-tiles")) > 0
    assert "No area kept yet" in dlg.inner_text()
    pg.keyboard.press("Escape")
    pg.wait_for_selector(".keep-dialog", state="detached")
