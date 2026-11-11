"""
1.26 README pictures of the live HTML page: a flight around Mount Tabor (truth, a navigation solution that
drifts, a GPS) as the page a colleague receives - the plots, the 2D map and the 3D view on one time - and the
3D view alone. Made from the code itself (signalviewer's Python API + app/report.py), shot in Chromium with
software WebGL; no app window, no network (the offline basemap and terrain are bundled).

    python tools/make_live_report_media.py            # docs/images/34_live_page.png, 35_live_3d.png
"""
import math
import os
import sys
import tempfile

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
IMAGES = os.path.join(ROOT, "docs", "images")


def flight_csv(path: str) -> None:
    """A figure-eight around Mount Tabor at ~650-850 m, 300 s at 10 Hz: truth, nav (drifts north, noisy
    attitude), gps (1.5 m noise, 150 ms late)."""
    lat0, lon0 = 32.6870, 35.3900
    t = np.arange(0, 300.0, 0.1)
    w = 2 * math.pi / 300
    e = 2300 * np.sin(w * t)
    n = 1300 * np.sin(2 * w * t)
    alt = 760 + 90 * np.sin(2 * w * t + 0.6) + 40 * np.sin(5 * w * t)
    ve, vn, vu = np.gradient(e, t), np.gradient(n, t), np.gradient(alt, t)
    yaw = np.degrees(np.arctan2(ve, vn)) % 360
    gs = np.hypot(ve, vn)
    turn = np.gradient(np.unwrap(np.radians(yaw)), t)
    roll = np.degrees(np.arctan(gs * turn / 9.81))
    pitch = np.degrees(np.arctan2(vu, gs)) + 2.0
    R = 6378137.0

    def ll(ee, nn):
        return lat0 + np.degrees(nn / R), lon0 + np.degrees(ee / (R * math.cos(math.radians(lat0))))
    rng = np.random.default_rng(7)
    drift = 6.0 * (t / t[-1]) ** 1.5                                   # the navigation solution's north drift
    nav_lat, nav_lon = ll(e + 1.2 * np.sin(t / 23), n + drift)
    lag = 1.5                                                          # 150 ms at 10 Hz
    ge, gn = np.interp(t - 0.15, t, e) + rng.normal(0, 1.5, len(t)), np.interp(t - 0.15, t, n) + rng.normal(0, 1.5, len(t))
    gps_lat, gps_lon = ll(ge, gn)
    tr_lat, tr_lon = ll(e, n)
    cols = {
        "time": t, "truth.lat": tr_lat, "truth.lon": tr_lon, "truth.alt": alt,
        "truth.att.roll": roll, "truth.att.pitch": pitch, "truth.att.yaw": yaw,
        "nav.lat": nav_lat, "nav.lon": nav_lon, "nav.alt": alt + 0.8 * np.sin(t / 17) + rng.normal(0, 0.3, len(t)),
        "nav.att.roll": roll + 0.8 * np.sin(t / 9) + rng.normal(0, 0.25, len(t)), "nav.att.pitch": pitch + rng.normal(0, 0.2, len(t)),
        "nav.att.yaw": (yaw + 1.5 * np.sin(t / 31)) % 360,
        "gps.lat": gps_lat, "gps.lon": gps_lon, "gps.alt": np.interp(t - 0.15, t, alt) + rng.normal(0, 2.5, len(t)),
    }
    del lag
    with open(path, "w", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for i in range(len(t)):
            f.write(",".join(f"{cols[k][i]:.8f}" if k.endswith(("lat", "lon")) else f"{cols[k][i]:.3f}" for k in cols) + "\n")


def page(path_html: str, theme: str = "dark") -> None:
    import signalviewer as sv
    from app import report
    tmp = os.path.join(os.path.dirname(path_html), "tabor_flight.csv")
    flight_csv(tmp)
    rec = sv.load(tmp)
    names = ["truth", "nav", "gps"]
    geo = sv._geo_spec(rec, names, cursor=150.0)
    scene = sv._scene_spec(rec, names, cursor=150.0)
    kinds = {"truth": "aircraft", "nav": "uav", "gps": "drone"}
    for o in scene["scene"]["objects"]:
        o["kind"] = kinds[o["name"]]
    pick = lambda n, r: rec._candidate(n)["picks"][r]["id"]       # noqa: E731
    colors = {o["name"]: o["color"] for o in geo["geo"]["objects"]}

    def line(n, r, label):
        return {"id": pick(n, r), "label": label, "color": colors[n], "width": 1.6, "scale": 1, "offset": 0}
    alt = {"mode": "time", "title": "Altitude (m)", "signals": [line("truth", "alt", "truth"), line("nav", "alt", "nav"), line("gps", "alt", "gps")]}
    roll = {"mode": "time", "title": "Roll (deg)", "signals": [line("truth", "roll", "truth"), line("nav", "roll", "nav")]}
    req = {"format": "html", "title": "Flight test 14 · Mount Tabor", "lang": "en", "theme": theme,
           "tabs": [{"name": "Flight", "plots": [{**scene, "title": "Map · 3D"}, {**geo, "title": "Map · 2D"}, alt, roll]}],
           "replay": {"t": 150.0, "extent": [0, 299.9], "compact": True, "link": True,
                      "events": [{"t": 62.0, "text": "GPS: 9 satellites", "level": "warning"}, {"t": 150.0, "text": "nav drifts north", "level": "note"},
                                 {"t": 231.0, "text": "EKF variance", "level": "error"}]}}
    with open(path_html, "w", encoding="utf-8") as f:
        f.write(report.build_html(rec._store, req))


def shoot(path_html: str) -> None:
    from playwright.sync_api import sync_playwright
    os.makedirs(IMAGES, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pg = b.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
        pg.goto("file://" + path_html)
        pg.wait_for_function("window.__replay && document.querySelectorAll('iframe.mapframe').length === 2")
        pg.wait_for_timeout(4000)
        out = os.path.join(IMAGES, "34_live_page.png")
        pg.screenshot(path=out)
        print("image", os.path.relpath(out, ROOT))
        # the 3D view alone, its own page: following the truth, a bit closer
        pg2 = b.new_page(viewport={"width": 1400, "height": 800}, device_scale_factor=2)
        html = pg.locator("iframe.mapframe").first.get_attribute("srcdoc")
        tmp = path_html.replace(".html", "_3d.html")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(html.replace('"dark":false', '"dark":true'))
        pg2.goto("file://" + tmp)
        pg2.wait_for_timeout(2500)
        pg2.evaluate("() => { const s = document.getElementById('slider'); s.value = 150; s.dispatchEvent(new Event('input')); }")
        pg2.wait_for_timeout(1500)
        pg2.locator('#cam [data-cam="close"]').click()                 # the camera close behind the reference
        pg2.wait_for_timeout(2500)
        out = os.path.join(IMAGES, "35_live_3d.png")
        pg2.screenshot(path=out)
        print("image", os.path.relpath(out, ROOT))
        b.close()


if __name__ == "__main__":
    os.environ.setdefault("SV_OFFLINE", "1")
    d = tempfile.mkdtemp(prefix="sv-live-media-")
    html = os.path.join(d, "live_page.html")
    page(html)
    shoot(html)
