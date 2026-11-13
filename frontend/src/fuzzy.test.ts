import { describe, expect, it } from "vitest";
import { tieredSort } from "./fuzzy";

describe("tieredSort (the command palette)", () => {
  const items = ["Open a template or collection…", "ATT.Roll", "ATT.DesRoll", "Speed"];
  it("keeps only the exact matches when there are any", () => {
    expect(tieredSort(items, (x) => x, "roll")).toEqual(["ATT.Roll", "ATT.DesRoll"]);
  });
  it("falls back to approximate matches", () => {
    expect(tieredSort(items, (x) => x, "spd")).toEqual(["Speed"]);
    expect(tieredSort(items, (x) => x, "sepeed")).toEqual(["Speed"]);
  });
  it("an empty query lists everything in order", () => {
    expect(tieredSort(items, (x) => x, " ")).toEqual(items);
  });
});
