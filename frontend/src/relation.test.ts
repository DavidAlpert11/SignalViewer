import { describe, expect, it } from "vitest";
import { cmpLayout, comparable, defaultPair, errorAlong, errorColor, pairOf, relation, statsCsv, type At } from "./relation";
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

/* ---- L8: Compare objects… - the layout of a quantity's tab and what can be compared ---------------- */

describe("Compare objects (L8)", () => {
  const cell = (title: string, n = 1) => ({ title, ids: Array.from({ length: n }, (_, i) => `${title}${i}`) });
  const vals = ["vN", "vE", "vD"].map((x) => cell(x)), errs = ["eN", "eE", "eD"].map((x) => cell(x)), extra = [cell("h3d"), cell("vert")];
  it("Both: values left, errors right, one row per component, then the extra row", () => {
    const l = cmpLayout("both", vals, errs, extra);
    expect(l.cols).toBe(2);
    expect(l.plots.map((p) => p.title)).toEqual(["vN", "eN", "vE", "eE", "vD", "eD", "h3d", "vert"]);
  });
  it("Values only / errors only: one column; no values (track frame): errors", () => {
    expect(cmpLayout("values", vals, errs, extra)).toEqual({ plots: vals, cols: 1 });
    expect(cmpLayout("errors", vals, errs, extra).plots.map((p) => p.title)).toEqual(["eN", "eE", "eD", "h3d", "vert"]);
    expect(cmpLayout("both", null, errs, extra).cols).toBe(1);
  });
  const o = (id: string, extraFields: object = {}) => ({ id, name: id, kind: "aircraft", color: "#fff", lat: `${id}.lat`, lon: `${id}.lon`, alt: `${id}.alt`, ...extraFields }) as never;
  it("says which objects cannot be compared in velocity / attitude, and why", () => {
    const truth = o("truth", { vel: ["v1", "v2", "v3"], roll: "r", pitch: "p", yaw: "y" });
    const lane = o("lane", { vel: ["a", "b", "c"], roll: "r2", pitch: "p2", yaw: "y2" });
    const gps = o("gps", { attitudeSource: { object: "truth" } });
    const c = comparable(truth, [lane, gps], [truth, lane, gps]);
    expect(c.velocity.reason).toBeUndefined();
    expect(c.velocity.out.map((x) => x.o.name)).toEqual(["gps"]);
    expect(c.attitude.out.map((x) => x.o.name)).toEqual(["gps"]);           // borrows the reference's angles
    expect(comparable(gps, [truth], [truth, gps]).velocity.reason).toMatch(/gps has no velocity/);
  });
  it("statistics as CSV", () => {
    const csv = statsCsv([{ object: "lane 1", qty: "position", comp: "Δnorth", id: "x", s: { rms: 1.5, mean: 1.5, abs_max: 1.5004, p95_abs: 1.5, t_abs_max: 12, samples: 3001 } as never }]);
    expect(csv.split("\n")[1]).toBe('"lane 1","position","Δnorth",1.5,1.5,1.5004,1.5,12,3001');
  });
});

describe("errorAlong (P9)", () => {
  const t = Array.from({ length: 101 }, (_, i) => i * 0.1);
  const truth = { t, lat: t.map(() => 32), lon: t.map((x) => 35 + x * 1e-4) };
  it("a solution 6 m north at the end: p95 near 6 m, one vehicle", () => {
    const nav = { t, lat: t.map((x) => 32 + (6 * x / 10) / 111_320), lon: truth.lon };
    const e = errorAlong(truth, () => 100, nav, () => 100)!;
    expect(e.same).toBe(true);
    expect(e.rows.length).toBe(101);
    expect(e.rows[100].d).toBeCloseTo(6, 1);
    expect(e.p95).toBeGreaterThan(5.3);
    expect(e.median).toBeCloseTo(3, 0);
  });
  it("two vehicles 500 m apart are not one; no overlap in time: none", () => {
    const other = { t, lat: t.map(() => 32 + 500 / 111_320), lon: truth.lon };
    expect(errorAlong(truth, () => 0, other, () => 0)!.same).toBe(false);
    const later = { t: t.map((x) => x + 100), lat: truth.lat, lon: truth.lon };
    expect(errorAlong(truth, () => 0, later, () => 0)).toBeNull();
  });
  it("colours: green, amber at half, red at p95", () => {
    expect([errorColor(0), errorColor(0.5), errorColor(1), errorColor(3)]).toEqual(["rgb(45, 164, 78)", "rgb(242, 169, 59)", "rgb(229, 83, 75)", "rgb(229, 83, 75)"]);
  });
});
