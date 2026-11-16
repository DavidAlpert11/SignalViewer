import { describe, expect, test } from "vitest";
import { LOOK_FOV, lookDrag, lookFrom, lookZoom } from "./freeLook";

describe("the Cockpit's free look", () => {
  test("starts where the object points, wings level", () => {
    expect(lookFrom(370, 20)).toEqual({ hdg: 10, pitch: 20 });
    expect(lookFrom(-90, 120)).toEqual({ hdg: 270, pitch: 89 });
    expect(lookFrom(null, undefined)).toEqual({ hdg: 0, pitch: 0 });
    expect(lookFrom(NaN, NaN, 50)).toEqual({ hdg: 0, pitch: 0, fov: 50 });
  });
  test("a drag turns it - the scene moves with the mouse, one view-angle per view-height", () => {
    const l = { hdg: 90, pitch: 0 };
    expect(lookDrag(l, 100, 0, 700).hdg).toBeCloseTo(80);           // right: looks left (70° over 700 px)
    expect(lookDrag(l, -100, 0, 700).hdg).toBeCloseTo(100);
    expect(lookDrag(l, 0, 100, 700).pitch).toBeCloseTo(10);         // down: looks up
    expect(lookDrag({ hdg: 5, pitch: 0 }, 100, 0, 700).hdg).toBeCloseTo(355);   // across north
    expect(lookDrag(l, 0, 10_000, 700).pitch).toBe(89);             // never over the top
    expect(lookDrag({ hdg: 0, pitch: 0, fov: 35 }, 100, 0, 700).hdg).toBeCloseTo(355);   // zoomed in: finer
  });
  test("the wheel zooms the field of view, within bounds", () => {
    const l = { hdg: 0, pitch: 0 };
    expect(lookZoom(l, -100).fov!).toBeLessThan(LOOK_FOV);
    expect(lookZoom(l, 100).fov!).toBeGreaterThan(LOOK_FOV);
    expect(lookZoom(l, -100_000).fov).toBe(15);
    expect(lookZoom(l, 100_000).fov).toBe(100);
    expect(lookZoom(l, 100)).toMatchObject({ hdg: 0, pitch: 0 });
  });
});
