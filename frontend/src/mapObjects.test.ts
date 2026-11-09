import { describe, expect, it } from "vitest";
import { attitudeOf, derivedAttitude, guessRoles, trackKey, trackOfClass, trackRequest } from "./mapObjects";
import { linkAttitudes } from "./objectAdd";
import { detectObjects } from "./objectDetect";
import type { MapObject } from "./store";

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
