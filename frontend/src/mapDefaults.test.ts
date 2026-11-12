import { beforeEach, describe, expect, test } from "vitest";
import { useApp } from "./store";
import { setPref } from "./prefs";
import { fmtCoord, fmtDistance, MAP_DEFAULTS, mgrs, newMapFields, newObjectLook, readMapPrefs, resetMapPrefs, setIconFor, setMapPref } from "./mapDefaults";

/* P8: Settings > Map and objects - read through one module; a bad value falls back; new things only */

beforeEach(() => { resetMapPrefs(); });

describe("mapDefaults", () => {
  test("no prefs: the defaults (aircraft for every class, General, 2.5 px, metres)", () => {
    expect(readMapPrefs()).toEqual(MAP_DEFAULTS);
    expect(newObjectLook("navigation")).toEqual({ kind: "aircraft" });
    expect(newMapFields("o1")).toEqual({});
  });
  test("each pref is read", () => {
    setIconFor("navigation", "drone");
    setMapPref("camera", "chase"); setMapPref("relation", "hidden"); setMapPref("modelSize", 18); setMapPref("units", "imperial");
    setMapPref("trackWidth", 4); setMapPref("coords", "dms"); setMapPref("rate", 2); setMapPref("names", "hidden"); setMapPref("storyLength", 45);
    const m = readMapPrefs();
    expect(m.icon).toEqual({ truth: "aircraft", navigation: "drone", receiver: "aircraft", other: "aircraft" });
    expect([m.camera, m.relation, m.modelSize, m.units, m.trackWidth, m.coords, m.rate, m.names, m.storyLength]).toEqual(["chase", "hidden", 18, "imperial", 4, "dms", 2, "hidden", 45]);
    expect(useApp.getState().mapPrefs).toEqual(m);                         // the store's copy follows
    expect(newObjectLook("navigation")).toEqual({ kind: "drone", size: 18 });
    expect(newObjectLook(undefined)).toEqual({ kind: "aircraft", size: 18 });   // unknown class: "other"
    expect(newMapFields("o1")).toEqual({ followObject: "o1", camera: "chase", relHidden: true });
  });
  test("a bad value falls back to the default", () => {
    setPref("sv3.map.camera", "sideways"); setPref("sv3.map.trackWidth", 7); setPref("sv3.map.icon.truth", "rocket");
    const m = readMapPrefs();
    expect([m.camera, m.trackWidth, m.icon.truth]).toEqual(["free", 2.5, "aircraft"]);
  });
  test("drawing: Always flat turns the light drawing on", () => {
    setMapPref("drawing", "flat");
    expect(useApp.getState().mapFlat).toBe(true);
    setMapPref("drawing", "auto");
    expect(useApp.getState().mapFlat).toBe(false);
  });
});

describe("formatters", () => {
  test("distances in metres / km or feet / nautical miles", () => {
    expect(fmtDistance(950, "en", "metric")).toBe("950 m");
    expect(fmtDistance(1240, "en", "metric")).toBe("1.24 km");
    expect(fmtDistance(100, "en", "imperial")).toBe("328 ft");
    expect(fmtDistance(3704, "en", "imperial")).toBe("2.00 NM");
  });
  test("positions: decimal, degrees-minutes-seconds", () => {
    expect(fmtCoord(32.6869444, 35.39, 4, "dd")).toBe("32.6869°, 35.3900°");
    expect(fmtCoord(32.6869444, -35.39, 6, "dms")).toBe("32°41′13.00″N 35°23′24.00″W");
    expect(fmtCoord(-33.5, 151.25, 4, "dms")).toBe("33°30′00″S 151°15′00″E");
  });
  test.each([
    [0, 0, "31N AA 66021 00000"],
    // reference values from GeoTrans (NGA's library, through the Python package "mgrs"), checked once
    [38.889467, -77.035239, "18S UJ 23483 06479"],               // the Washington Monument
    [32.5973, 35.2286, "36S YB 09149 08837"],                    // Megiddo
    [-33.8568, 151.2153, "56H LH 34900 52288"],                  // Sydney Opera House
    [60, 5, "32V KM 76979 58157"],                               // Norway: zone 32, not 31
    [78, 15, "33X WG 00000 58369"],                              // Svalbard: zone 33
  ])("MGRS %f, %f", (lat, lon, want) => {
    expect(mgrs(lat, lon)).toBe(want);
  });
  test("MGRS: shorter, and none at the poles", () => {
    expect(mgrs(38.889467, -77.035239, 3)).toBe("18S UJ 234 064");
    expect(mgrs(85, 0)).toBeNull();
  });
});
