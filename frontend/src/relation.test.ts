import { describe, expect, it } from "vitest";
import { defaultPair, pairOf, relation, type At } from "./relation";
import type { MapObject } from "./store";

// a point n / e metres from (lat, lon) - meridian and prime-vertical radii (WGS84), good to a few mm here
const A = 6378137.0, E2 = (1 / 298.257223563) * (2 - 1 / 298.257223563);
function off(lat: number, lon: number, n: number, e: number, alt: number | null = 0, hdg: number | null = null): At {
  const la = (lat * Math.PI) / 180, s2 = Math.sin(la) ** 2;
  const m = (A * (1 - E2)) / (1 - E2 * s2) ** 1.5, nn = A / Math.sqrt(1 - E2 * s2);
  return { lat: lat + ((n / m) * 180) / Math.PI, lon: lon + ((e / (nn * Math.cos(la))) * 180) / Math.PI, alt, hdg };
}

describe("relation (N7) - the same definitions as svcore/relate.py", () => {
  it("500 m north, 20 m up", () => {
    const P = { lat: 32, lon: 35, alt: 100, hdg: 90 }, S = off(32, 35, 500, 0, 120);
    const r = relation(P, S);
    expect(r.horiz).toBeCloseTo(500, 1);
    expect(r.dalt).toBeCloseTo(20, 6);
    expect(r.slant!).toBeCloseTo(Math.hypot(500, 20), 0);
    expect(Math.abs(((r.bearing + 180) % 360) - 180)).toBeLessThan(1e-3);
    expect(r.relBearing).toBeCloseTo(-90, 3);                       // heading east: the secondary is on the left
  });

  it("head-on: closure 100 m/s, closest in 100 s, aspect 180", () => {
    const P = { ...off(32, 35, 0, 0, 1000), hdg: 0 }, S = { ...off(32, 35, 10000, 0, 1000), hdg: 180 };
    const P2 = { ...off(32, 35, 50, 0, 1000), hdg: 0 }, S2 = { ...off(32, 35, 9950, 0, 1000), hdg: 180 };
    const r = relation(P, S, P2, S2, 1);
    expect(r.closure!).toBeCloseTo(100, 1);
    expect(r.tca!).toBeCloseTo(100, 0);
    expect(r.aspect!).toBeCloseTo(180, 3);
    expect(r.hdgDiff).toBeCloseTo(180, 6);
  });

  it("aspect 0 right behind, 90 R / L abeam; opening: no closest approach", () => {
    const P = { ...off(32, 35, 0, 0, 0), hdg: 0 };
    const S = { ...off(32, 35, 1000, 0, 0), hdg: 0 };
    const r = relation(P, S, P, { ...off(32, 35, 1080, 0, 0), hdg: 0 }, 1);
    expect(r.aspect!).toBeCloseTo(0, 3);
    expect(r.tca).toBeNull();
    // the secondary heads west with the primary south of it: the primary is on its left
    const w = relation(P, { ...off(32, 35, 1000, 0, 0), hdg: 270 });
    expect(w.aspect!).toBeCloseTo(90, 2);
    expect(w.aspectSide).toBe("L");
    const e = relation(P, { ...off(32, 35, 1000, 0, 0), hdg: 90 });
    expect(e.aspectSide).toBe("R");
  });

  it("no altitude: nothing vertical", () => {
    const r = relation({ lat: 32, lon: 35, alt: null, hdg: null }, off(32, 35, 0, 300, null));
    expect(r.dalt).toBeNull();
    expect(r.slant).toBeNull();
    expect(r.horiz).toBeCloseTo(300, 1);
    expect(r.relBearing).toBeNull();
  });
});

const o = (id: string, cls?: MapObject["cls"]): MapObject => ({ id, name: id, kind: "aircraft", color: "#000", lat: `r/${id}.lat`, lon: `r/${id}.lon`, cls });
describe("primary / secondary (N7)", () => {
  it("defaults: truth / first navigation; a log: navigation / receiver; one object: no secondary", () => {
    expect(defaultPair([o("gps", "receiver"), o("nav", "navigation"), o("phys", "truth")])).toEqual({ primary: "phys", secondary: "nav" });
    expect(defaultPair([o("GPS", "receiver"), o("POS", "navigation")])).toEqual({ primary: "POS", secondary: "GPS" });
    expect(pairOf({ objects: [o("a")] })).toEqual({ primary: "a", secondary: null });
  });
  it("the plot's own choice wins while its objects exist", () => {
    const objs = [o("phys", "truth"), o("nav", "navigation"), o("gps", "receiver")];
    expect(pairOf({ objects: objs, primaryObject: "gps", relatedObjects: ["phys"] })).toEqual({ primary: "gps", secondary: "phys" });
    expect(pairOf({ objects: objs, primaryObject: "gone" })).toEqual({ primary: "phys", secondary: "nav" });
    expect(pairOf({ objects: objs, primaryObject: "nav" })).toEqual({ primary: "nav", secondary: "phys" });
  });
});
