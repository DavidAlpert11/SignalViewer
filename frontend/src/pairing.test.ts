// T1: pairing.ts - signals given to plots, colours that stand apart
import { describe, expect, test } from "vitest";
import { contrastColor, distinctParts, pairWithPlots, targetPlots } from "./pairing";
import type { Plot } from "./store";

const plot = (title: string, sigs: string[] = []): Plot => ({ id: title, title, signals: sigs.map((sig) => ({ sig, color: "#000000", width: 1.5, scale: 1, offset: 0 })) });

describe("pairing", () => {
  test("contrastColor: an unused colour of the palette first", () => {
    expect(contrastColor(["#111111", "#222222", "#333333"], ["#111111"])).not.toBe("#111111");
  });
  test("distinctParts: the part of each name that tells them apart", () => {
    const d = distinctParts(["ATT.Roll", "ATT.Pitch", "ATT.Yaw"]);
    expect(new Set(d).size).toBe(3);
  });
  test("pairWithPlots: as many signals as plots - one each, in order", () => {
    const plots = [plot("a", ["r/x"]), plot("b", ["r/y"])];
    const p = pairWithPlots(["r/x2", "r/y2"], plots, 0);
    expect(p.pairs.map((x) => x.plot).sort()).toEqual(targetPlots(plots).slice(0, 2).sort());
    expect(p.extra).toEqual([]);
  });
});
