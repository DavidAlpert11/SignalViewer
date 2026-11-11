import { describe, expect, it } from "vitest";
import { envelopePath, panSpan, pullEdge, shownWindow } from "./timelineView";

describe("envelopePath", () => {
  it("maps time across 0..1000 and values top (high) to bottom (low)", () => {
    const d = envelopePath([0, 5, 10], [0, 10, 5], 0, 10);
    expect(d).toBe("M0.0 92.0L500.0 8.0L1000.0 50.0");
  });
  it("breaks at missing values, draws a constant in the middle, nothing for an empty line", () => {
    expect(envelopePath([0, 1, 2, 3], [1, NaN, 2, 3], 0, 3)).toMatch(/^M0\.0 92\.0M666\.7 50\.0L1000\.0 8\.0$/);
    expect(envelopePath([0, 1], [4, 4], 0, 1)).toBe("M0.0 50.0L1000.0 50.0");
    expect(envelopePath([0, 1], [NaN, NaN], 0, 1)).toBe("");
  });
});

describe("the window on the timeline", () => {
  it("moves keeping its width, inside the recording", () => {
    expect(panSpan([10, 20], 5, [0, 100])).toEqual([15, 25]);
    expect(panSpan([10, 20], -50, [0, 100])).toEqual([0, 10]);
    expect(panSpan([10, 20], 500, [0, 100])).toEqual([90, 100]);
  });
  it("an edge pulled zooms, never past the other edge", () => {
    expect(pullEdge([10, 20], 0, 4, [0, 100], 1)).toEqual([4, 20]);
    expect(pullEdge([10, 20], 1, 15, [0, 100], 1)).toEqual([10, 15]);
    expect(pullEdge([10, 20], 0, 30, [0, 100], 1)).toEqual([19, 20]);
    expect(pullEdge([10, 20], 1, 300, [0, 100], 1)).toEqual([10, 100]);
  });
  it("is drawn only when the plots show part of the recording", () => {
    expect(shownWindow(null, [0, 100])).toBeNull();
    expect(shownWindow([0, 99], [0, 100])).toBeNull();
    expect(shownWindow([-10, 30], [0, 100])).toEqual([0, 30]);
    expect(shownWindow([200, 300], [0, 100])).toBeNull();
  });
});
