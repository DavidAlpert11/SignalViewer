import { describe, expect, it } from "vitest";
import { pagePlot } from "./plotSpec";
import type { Plot } from "./store";

const obj = { id: "o1", name: "POS", kind: "aircraft" as const, color: "#e5677a", lat: "r/POS.Lat", lon: "r/POS.Lng" };
const plot = (mode: Plot["mode"], extra: Partial<Plot> = {}): Plot => ({ id: "p", title: "", signals: [], mode, ...extra });
const line = [{ sig: "r/POS.Alt", color: "#fff", width: 1.5 }] as Plot["signals"];

describe("pagePlot (1.26: one rule for reports, the replay and the report panel)", () => {
  it("a map with objects is in - in 2D and in 3D (1.25 left the 3D view out without a word)", () => {
    expect(pagePlot(plot("geo", { objects: [obj] })).include).toBe(true);
    expect(pagePlot(plot("3d", { objects: [obj] })).include).toBe(true);
  });
  it("lines are in; an empty plot is out as 'nothing to draw'", () => {
    expect(pagePlot(plot("time", { signals: line })).include).toBe(true);
    expect(pagePlot(plot(undefined, { signals: line })).include).toBe(true);
    expect(pagePlot(plot("time"))).toEqual({ include: false, why: "pageWhyEmpty" });
    expect(pagePlot(plot("3d"))).toEqual({ include: false, why: "pageWhyEmpty" });
  });
  it("what a page cannot hold says why", () => {
    expect(pagePlot(plot("video", { signals: line }))).toEqual({ include: false, why: "pageWhyVideo" });
    expect(pagePlot(plot("occ", { signals: line }))).toEqual({ include: false, why: "pageWhyOcc" });
  });
});
