import { describe, expect, it } from "vitest";
import { flatOnSharedAxis, rangeOf } from "./flatLine";

describe("flatOnSharedAxis", () => {
  it("a small signal beside a large one looks flat (12 A beside 3000 rpm)", () => {
    expect(flatOnSharedAxis([8, 16], [[2200, 3800]])).toBe("added");
  });
  it("a small movement far from zero is flat too (a bus voltage 22.8 - 24 V beside rpm)", () => {
    expect(flatOnSharedAxis([22.8, 24], [[2200, 3800]])).toBe("added");
  });
  it("a large signal added to small ones flattens them", () => {
    expect(flatOnSharedAxis([2200, 3800], [[8, 16], [0, 5]])).toBe("others");
  });
  it("signals of a like range share the axis (a setpoint and its response)", () => {
    expect(flatOnSharedAxis([3000, 3800], [[2200, 3800]])).toBeNull();
    expect(flatOnSharedAxis([-10, 20], [[-12, 22], [0, 360]])).toBeNull();
  });
  it("a constant is never the reason, and nothing is said without ranges", () => {
    expect(flatOnSharedAxis([5, 5], [[2200, 3800]])).toBeNull();
    expect(flatOnSharedAxis([2200, 3800], [[5, 5]])).toBeNull();
    expect(flatOnSharedAxis(null, [[0, 1]])).toBeNull();
    expect(flatOnSharedAxis([0, 1], [null])).toBeNull();
    expect(flatOnSharedAxis([0, 1], [])).toBeNull();
  });
  it("one of the lines there is already as large: the small ones were flat before", () => {
    expect(flatOnSharedAxis([2000, 4000], [[8, 16], [1000, 5000]])).toBeNull();
  });
});

describe("rangeOf", () => {
  it("takes the slices' extremes, skips missing ones, applies the line's scale and offset", () => {
    expect(rangeOf({ lo: [1, null, -2], hi: [3, null, 0] })).toEqual([-2, 3]);
    expect(rangeOf({ lo: [1, 2], hi: [3, 4] }, -2, 10)).toEqual([2, 8]);
    expect(rangeOf({ lo: [null], hi: [null] })).toBeNull();
    expect(rangeOf(null)).toBeNull();
  });
});
