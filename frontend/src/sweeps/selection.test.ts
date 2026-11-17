import { describe, expect, it } from "vitest";
import { describeRuns } from "./selection";
import type { Col } from "./model";

const num = (name: string, v: number[]): Col => ({ name, kind: "num", values: Float32Array.from(v), group: "run" });
const cat = (name: string, labels: string[], v: number[]): Col => ({ name, kind: "cat", values: Float32Array.from(v), labels, group: "run" });

describe("the brush of All runs, described for the server (1.29)", () => {
  const runs = new Map<string, Col>([
    ["out", num("out", [1, 2, 3])], ["terrain", cat("terrain", ["flat", "hill", "sea"], [0, 1, 2])],
    ["#set", num("#set", [0, 1, 2])], ["#holds", num("#holds", [1, 0, 1])],
  ]);
  const sets = new Map<string, Col>([["#holds", num("#holds", [1, 0, 1, 1])]]);

  it("sends a number column's filter as it is and a text column's by its labels, never codes", () => {
    const d = describeRuns(runs, { out: { kind: "ranges", ranges: [[1.5, 9]] }, terrain: { kind: "ranges", ranges: [[0.5, 2]] } }, sets, 4, null);
    expect(d).toEqual({ filters: { out: { kind: "ranges", ranges: [[1.5, 9]] }, terrain: { kind: "labels", labels: ["hill", "sea"] } }, sets: null });
  });

  it("decides per-set columns and the sets shown on the page, over every set", () => {
    const d = describeRuns(runs, { "#holds": { kind: "values", values: [1] }, nope: { kind: "values", values: [1] } }, sets, 4, Uint8Array.from([1, 1, 0, 1]));
    expect(d).toEqual({ filters: {}, sets: [0, 3] });
    expect(describeRuns(runs, { "#set": { kind: "ranges", ranges: [[2, 3]] } }, sets, 4, null).sets).toEqual([2, 3]);
  });
});
