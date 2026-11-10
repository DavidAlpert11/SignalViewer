import { describe, expect, it } from "vitest";
import { attitudeOf, derivedAttitude, guessRoles, trackKey, trackOfClass, trackRequest } from "./mapObjects";
import { addable, firstSource, isAdded, linkAttitudes, objectSources, whyLines } from "./objectAdd";
import { detectObjects } from "./objectDetect";
import type { MapObject, Plot } from "./store";
import type { SignalInfo } from "./api";

const obj = (id: string, extra: Partial<MapObject> = {}): MapObject => ({ id, name: id, kind: "aircraft", color: "#000", lat: `r/${id}.lat`, lon: `r/${id}.lon`, ...extra });
const nav = obj("nav", { yaw: "r/nav.att.yaw", pitch: "r/nav.att.pitch", roll: "r/nav.att.roll", cls: "navigation" });

describe("attitude source (N5, owner's decision 3)", () => {
  it("own angles win; motion; borrowed from an object with its own angles", () => {
    expect(attitudeOf(nav, [nav]).kind).toBe("own");
    const gps = obj("gps", { attitudeSource: "motion" });
    expect(attitudeOf(gps, [nav, gps]).kind).toBe("motion");
    const b = obj("gps", { attitudeSource: { object: "nav" } });
    expect(attitudeOf(b, [nav, b])).toEqual({ kind: "borrowed", from: nav });
    expect(derivedAttitude(b, [nav, b])).toBe(true);
    expect(derivedAttitude(nav, [nav])).toBe(false);
  });

  it("an old object with no angles and no source is unchanged ('none': its course, drawn filled)", () => {
    const old = obj("old");
    expect(attitudeOf(old, [old]).kind).toBe("none");
    expect(trackRequest(old, [old]).attitude).toBeNull();
    expect(derivedAttitude(old, [old])).toBe(false);
  });

  it("a source gone or without angles falls back to motion; no chains", () => {
    const a = obj("a", { attitudeSource: { object: "gone" } });
    expect(attitudeOf(a, [a]).kind).toBe("motion");
    const m = obj("m", { attitudeSource: "motion" });
    const c = obj("c", { attitudeSource: { object: "m" } });
    expect(attitudeOf(c, [m, c]).kind).toBe("motion");
  });

  it("the request sends the borrowed object's angle signals, or asks the server for a motion attitude", () => {
    const b = obj("gps", { attitudeSource: { object: "nav" } });
    expect(trackRequest(b, [nav, b])).toMatchObject({ lat: "r/gps.lat", yaw: "r/nav.att.yaw", roll: "r/nav.att.roll", attitude: null });
    const m = obj("gps", { attitudeSource: "motion", minSpeed: 2 });
    expect(trackRequest(m, [m])).toMatchObject({ attitude: "motion", minSpeed: 2 });
    expect(trackRequest(m, [m]).yaw).toBeUndefined();
    expect(trackKey(b, [nav, b])).not.toBe(trackKey(m, [m]));
  });

  it("links a row borrowing from another row of the same Add", () => {
    const d = detectObjects({ id: "r", name: "f.csv", signals: ["nav.lat", "nav.lon", "nav.att.yaw", "gps.lat", "gps.lon"].map((n) => ({ id: `r/${n}`, name: n })) } as never);
    const [cn, cg] = d.candidates;
    const on = obj("n1"), og = obj("g1");
    linkAttitudes([{ c: cn, o: on }, { c: cg, o: og, from: cn.key }], d.candidates, undefined);
    expect(og.attitudeSource).toEqual({ object: "n1" });
    const plotted = obj("n0", { lat: "r/nav.lat" });
    const og2 = obj("g2");
    linkAttitudes([{ c: cg, o: og2, from: cn.key }], d.candidates, { objects: [plotted] } as never);
    expect(og2.attitudeSource).toEqual({ object: "n0" });       // the row already on the plot
  });

  it("looks by class: navigation dashed, receiver points", () => {
    expect([trackOfClass("truth"), trackOfClass("navigation"), trackOfClass("receiver"), trackOfClass(undefined)]).toEqual([undefined, "dash", "points", undefined]);
  });
});

describe("guessRoles (N5: one object's roles, never mixed)", () => {
  it("takes position and attitude from the same prefix", () => {
    const names = ["phys.lat", "phys.lon", "phys.alt", "phys.att.roll", "phys.att.pitch", "phys.att.yaw", "nav.lat", "nav.lon", "nav.att.yaw", "gps.lat", "gps.lon"];
    const g = guessRoles({ id: "q", name: "x.csv", signals: names.map((n) => ({ id: `q/${n}`, name: n })) } as never);
    expect(g).toEqual({ lat: "q/phys.lat", lon: "q/phys.lon", alt: "q/phys.alt", roll: "q/phys.att.roll", pitch: "q/phys.att.pitch", yaw: "q/phys.att.yaw" });
  });
});

/* ---- L3 / L4 (round of 2026-11-10): addable local positions, one "already on the map" rule ------- */

describe("objects from positions in metres (L3, L4)", () => {
  const run = (names: string[]) => ({ id: "r", name: "f.csv", signals: names.map((n) => ({ id: `r/${n}`, name: n })) }) as unknown as Parameters<typeof detectObjects>[0];
  const lane = ["XKF1[0].PN [m]", "XKF1[0].PE [m]", "XKF1[0].PD [m]", "XKF1[0].Roll [deg]", "XKF1[0].Pitch [deg]", "XKF1[0].Yaw [deg]"];
  const orgn = ["ORGN[0].Lat [deg]", "ORGN[0].Lng [deg]", "ORGN[0].Alt [m]"];
  // what the backend makes for an added lane: frame NED -> LLA (ref "signals"), then smoothed over 2 s
  const derived: SignalInfo[] = [
    ...["lat", "lon", "alt"].map((a, i) => ({ id: `derived/lla_Pos_ned.${a}`, name: `lla_Pos_ned.${a}`, op: "frame",
      sources: [...lane.slice(0, 3), ...orgn].map((n) => `r/${n}`), params: { qty: "position", src: "ned", dst: "lla", ref: "signals", axis: i } })),
    ...["lat", "lon", "alt"].map((a, i) => ({ id: `derived/smooth_2s.${a}`, name: `smooth_2s.${a}`, op: "vecsmooth",
      sources: ["lat", "lon", "alt"].map((x) => `derived/lla_Pos_ned.${x}`), params: { kind: "lla", window: 2, axis: i } })),
  ];
  it("a lane with its origin is addable; without one, or in cm, it is not", () => {
    expect(addable(detectObjects(run([...lane, ...orgn])).candidates[0])).toBe(true);
    expect(addable(detectObjects(run(lane)).candidates[0])).toBe(false);
    expect(addable(detectObjects(run(["s.ecef_x [cm]", "s.ecef_y [cm]", "s.ecef_z [cm]"])).candidates[0])).toBe(false);
  });
  it("walks the smoothing and the conversion back to the recorded signal (one walk for the form and the bar)", () => {
    const o = { lat: "derived/smooth_2s.lat", lon: "derived/smooth_2s.lon", alt: "derived/smooth_2s.alt" };
    const ch = objectSources(o, derived);
    expect([ch.smooth, ch.lat, ch.frame?.src, ch.frame?.sources[3]]).toEqual([2, "derived/lla_Pos_ned.lat", "ned", "r/ORGN[0].Lat [deg]"]);
    expect(firstSource(o, derived)).toBe("r/XKF1[0].PN [m]");
    expect(firstSource({ lat: "r/POS.Lat", lon: "r/POS.Lng", alt: null }, derived)).toBe("r/POS.Lat");
  });
  it("F8: a converted object is 'already on the map', so it is not offered again", () => {
    const c = detectObjects(run([...lane, ...orgn])).candidates[0];
    const plot = { objects: [obj("lane", { lat: "derived/smooth_2s.lat", lon: "derived/smooth_2s.lon" })] } as unknown as Plot;
    expect(isAdded(c, plot, derived)).toBe(true);
    expect(isAdded(c, plot, [])).toBe(false);                         // without the chain it cannot be known
    expect(isAdded(c, { objects: [] } as unknown as Plot, derived)).toBe(false);
  });
  it("Why? explains the origin, the lane and a wrong unit - in English and Hebrew", () => {
    const c = detectObjects(run([...lane, ...orgn])).candidates[0];
    const en = whyLines(c, "en");
    expect(en.some((l) => l.includes("ORGN[0]") && l.includes("EKF origin") && l.includes("above sea level"))).toBe(true);
    expect(en).toContain("EKF3 lane 0.");
    expect(whyLines(detectObjects(run(lane)).candidates[0], "en").some((l) => l.startsWith("No origin found"))).toBe(true);
    expect(whyLines(c, "he").some((l) => l.includes("ORGN[0]"))).toBe(true);
    const px4 = detectObjects(run(["vehicle_local_position.x", "vehicle_local_position.y", "vehicle_local_position.z",
      "vehicle_local_position.ref_lat", "vehicle_local_position.ref_lon", "vehicle_local_position.ref_alt"])).candidates[0];
    expect(whyLines(px4, "en").some((l) => l.includes("ref_lat / ref_lon / ref_alt") && l.includes("first value is used"))).toBe(true);
    expect(whyLines(detectObjects(run(["s.ecef_x [cm]", "s.ecef_y [cm]", "s.ecef_z [cm]"])).candidates[0], "en").some((l) => l.includes("in cm"))).toBe(true);
  });
});
