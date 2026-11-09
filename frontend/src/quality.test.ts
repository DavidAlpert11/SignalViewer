// T1: the data-quality summary in words (26.U7)
import { expect, test } from "vitest";
import { kindsText, signalLines } from "./quality";
import type { RunQuality, SignalQuality } from "./api";

test("a signal's problems, one line each", () => {
  const s = { name: "B", n: 100, rate: 100, missing: 4, missingPct: 4, allMissing: false, gaps: 1, gapTime: 2, firstGap: 3,
    duplicates: 0, backwards: 0, rateChanges: [{ t: 5, from: 100, to: 10 }], issues: ["missing", "gaps", "rateChanges"] } as SignalQuality;
  const lines = signalLines(s, "en");
  expect(lines).toHaveLength(3);
  expect(lines[2]).toBe("At 5 s the rate changes from 100 to 10 Hz");
});
test("a file's summary names the kinds found and how many signals", () => {
  const q = { count: { missing: 1, gaps: 2, duplicates: 0, backwards: 0, rateChanges: 0 } } as unknown as RunQuality;
  expect(kindsText(q, "en")).toBe("missing values (1), gaps (2)");
});
