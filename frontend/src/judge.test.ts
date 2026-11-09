// T1: judge.ts - the baseline proposed, the verdict per file (26.U4)
import { expect, test } from "vitest";
import type { CompareAllRow } from "./api";
import { proposeBaseline, setGolden, verdicts } from "./judge";

const r = (id: string, name: string) => ({ id, name, path: `/d/${name}` });

test("a golden run, else a name that says reference, else the first", () => {
  expect(proposeBaseline([r("1", "run_a.csv"), r("2", "run_b.csv")])).toBe("1");
  expect(proposeBaseline([r("1", "today.csv"), r("2", "golden_run.csv")])).toBe("2");
  expect(proposeBaseline([r("1", "flight3.bin"), r("2", "ref.bin")])).toBe("2");
  expect(proposeBaseline([r("1", "prefix.csv"), r("2", "b.csv")])).toBe("1");          // "ref" inside a word is not it
  setGolden("/d/run_b.csv", true);
  expect(proposeBaseline([r("1", "golden.csv"), r("2", "run_b.csv")])).toBe("2");
  setGolden("/d/run_b.csv", false);
});

test("per file: the signals judged, those outside - worst first; unjudged are not counted", () => {
  const rows = [
    { name: "A", diffs: [{ run: "x", pass: false, outsidePct: 2 }, { run: "y", pass: true }] },
    { name: "B", diffs: [{ run: "x", pass: false, outsidePct: 9 }, { run: "y", pass: true }] },
    { name: "C", diffs: [{ run: "x", pass: null }, { run: "y", pass: null }] },
  ] as unknown as CompareAllRow[];
  const v = verdicts(rows, "base", ["base", "x", "y"]);
  expect(v.map((f) => [f.run, f.judged, f.failed.map((x) => x.name)])).toEqual([["x", 2, ["B", "A"]], ["y", 2, []]]);
});
