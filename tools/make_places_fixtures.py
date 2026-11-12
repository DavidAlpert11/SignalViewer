"""P7: the place files the import tests read (backend/tests/data/places/) - the same three places (a point,
a line, an area) in each format the Places panel imports: KML, KMZ (a zip of that KML), GeoJSON, CSV
(points only). Run again only to change them: python tools/make_places_fixtures.py"""
import json
import os
import zipfile

OUT = os.path.join(os.path.dirname(__file__), "..", "backend", "tests", "data", "places")

POINT = ("Megiddo airfield", 32.5973, 35.2286, 60.0)
LINE = ("Runway 27 approach", [(32.5990, 35.2500), (32.5975, 35.2380), (32.5968, 35.2290)])
AREA = ("Range A", [(32.70, 35.30), (32.72, 35.30), (32.72, 35.34), (32.70, 35.34)])

KML = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Fixture</name>
<Folder><name>Here</name>
<Placemark><name>{POINT[0]}</name><description>tower 122.8</description>
  <Point><coordinates>{POINT[2]},{POINT[1]},{POINT[3]}</coordinates></Point></Placemark>
<Placemark><name>{LINE[0]}</name><LineString><coordinates>
  {" ".join(f"{lo},{la},0" for la, lo in LINE[1])}
</coordinates></LineString></Placemark>
<Placemark><name>{AREA[0]}</name><Polygon><outerBoundaryIs><LinearRing><coordinates>
  {" ".join(f"{lo},{la},0" for la, lo in AREA[1] + [AREA[1][0]])}
</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
<Placemark><name>No position</name><Point><coordinates></coordinates></Point></Placemark>
</Folder></Document></kml>
"""

GEOJSON = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"name": POINT[0], "description": "tower 122.8"},
     "geometry": {"type": "Point", "coordinates": [POINT[2], POINT[1], POINT[3]]}},
    {"type": "Feature", "properties": {"name": LINE[0]}, "geometry": {"type": "LineString", "coordinates": [[lo, la] for la, lo in LINE[1]]}},
    {"type": "Feature", "properties": {"name": AREA[0]},
     "geometry": {"type": "Polygon", "coordinates": [[[lo, la] for la, lo in AREA[1] + [AREA[1][0]]]]}},
    {"type": "Feature", "properties": {"name": "Off the earth"}, "geometry": {"type": "Point", "coordinates": [200, 95]}},
]}

CSV = f"""name,lat,lon,alt
{POINT[0]},{POINT[1]},{POINT[2]},{POINT[3]}
Ground station,32°41'13"N,35°23'24"E,
Bad row,north,east,
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "places.kml"), "w", encoding="utf-8") as f:
        f.write(KML)
    with zipfile.ZipFile(os.path.join(OUT, "places.kmz"), "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", KML)
    with open(os.path.join(OUT, "places.geojson"), "w", encoding="utf-8") as f:
        json.dump(GEOJSON, f, indent=1)
    with open(os.path.join(OUT, "places.csv"), "w", encoding="utf-8", newline="") as f:
        f.write(CSV)


if __name__ == "__main__":
    main()
