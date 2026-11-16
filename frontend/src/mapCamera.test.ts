import { describe, expect, test } from "vitest";
import { isMapPlot, mapCamera } from "./mapObjects";

/* P4: one Map, drawn in 3D; a 1.25 session's 2D map opens From above, its 3D map as it was */
const obj = { id: "a", name: "a", kind: "aircraft" as const, color: "#000", lat: "r/x", lon: "r/y" };
describe("the Map and its camera", () => {
  test("what is the Map", () => {
    expect(isMapPlot({ mode: "3d" })).toBe(true);
    expect(isMapPlot({ mode: "geo", objects: [obj] })).toBe(true);
    expect(isMapPlot({ mode: "geo" })).toBe(false);              // a plain lon / lat X-Y
    expect(isMapPlot({ mode: "xyz" })).toBe(false);
  });
  test("saved values unchanged, read as the two cameras", () => {
    // Free unless an object is followed - whatever camera an older version saved with it
    expect(mapCamera({})).toBe("free");
    expect(mapCamera({ followObject: null })).toBe("free");
    expect(mapCamera({ followObject: "a" })).toBe("object");
    for (const camera of ["chase", "cockpit", "lookat", "top", undefined]) expect(mapCamera({ followObject: "a", camera } as { followObject: string })).toBe("object");
  });
});
