import { describe, expect, it } from "vitest";
import { isSimilarityTab, shownTabName } from "./store/selectors";
import type { Tab } from "./store/model";

const tab = (x: Partial<Tab>): Tab => ({ id: "t", name: "", rows: 1, cols: 1, plots: [], active: 0, linkX: true, ...x });

// review 2026-11-25 round 2: Compare's Similarity tab is found again after a restart and named in today's language
describe("the Similarity tab", () => {
  it("is found by its mark, or by its default name in either language", () => {
    expect(isSimilarityTab(tab({ kind: "similarity", name: "Mine" }))).toBe(true);
    expect(isSimilarityTab(tab({ name: "Similarity" }))).toBe(true);
    expect(isSimilarityTab(tab({ name: "דמיון" }))).toBe(true);
    expect(isSimilarityTab(tab({ name: "Compare 1" }))).toBe(false);
  });
  it("shows its default name in the language of the moment, a name the user gave as it is", () => {
    expect(shownTabName(tab({ kind: "similarity", name: "Similarity" }), 3, "he")).toBe("דמיון");
    expect(shownTabName(tab({ kind: "similarity", name: "Mine" }), 3, "he")).toBe("Mine");
    expect(shownTabName(tab({ name: "" }), 1, "en")).toBe("Tab 2");
  });
});
