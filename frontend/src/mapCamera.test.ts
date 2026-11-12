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
  test("saved values unchanged, read as the four cameras", () => {
    expect(mapCamera({ mode: "geo" })).toBe("top");               // a 2D-era map
    expect(mapCamera({ mode: "geo", followObject: "a" })).toBe("top");
    expect(mapCamera({ mode: "geo", camera: "free" })).toBe("free");
    expect(mapCamera({ mode: "3d" })).toBe("free");
    expect(mapCamera({ mode: "3d", followObject: "a" })).toBe("centre");
    expect(mapCamera({ mode: "3d", followObject: "a", camera: "chase" })).toBe("chase");
    expect(mapCamera({ mode: "3d", camera: "top" })).toBe("top");
  });
});
