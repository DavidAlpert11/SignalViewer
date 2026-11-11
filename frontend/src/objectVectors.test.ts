/* L12: the shared test vectors - names in, objects out - run here AND by pytest (backend/tests/test_objects_py.py)
   against svcore/objects.py, so the app's rules and Python's cannot drift. SV_WRITE_VECTORS=1 writes the
   expectations from these (the app's) rules into the file; pytest must then agree. */
import { describe, expect, it } from "vitest";
import { detectObjects, type Candidate } from "./objectDetect";
import DOC from "../../tests/data/object_detect_cases.json";

// node's fs / env only when writing the expectations (the app's tsconfig has no node types)
const env = (globalThis as unknown as { process?: { env: Record<string, string | undefined> } }).process?.env ?? {};
interface Case { name: string; names: string[]; expect?: unknown }

/** The canonical summary both languages compute (the same keys, the same order). */
export function summary(c: Candidate) {
  const picks = Object.fromEntries(Object.keys(c.picks).sort().map((r) => { const p = c.picks[r as keyof typeof c.picks]!; return [r, `${p.name}|${p.rule}`]; }));
  return {
    prefix: c.prefix, name: c.name, cls: c.cls, pos: c.pos, attitude: c.attitude, full: c.full, missing: c.missing, picks,
    origin: c.origin ? `${c.origin.via}|${c.origin.rule}${c.origin.moves ? "|moves" : ""}` : null,
    badUnit: c.badUnit ?? null, lane: c.lane ? `${c.lane.ekf}:${c.lane.n}` : null,
    nearMisses: c.nearMisses.map((m) => `${m.name}|${m.role}|${m.why}`),
  };
}
function run(names: string[]) {
  const d = detectObjects({ id: "r", name: "case.csv", signals: names.map((n) => ({ id: `r/${n}`, name: n })) } as never);
  return { candidates: d.candidates.map(summary), incomplete: d.incomplete.map((i) => i.prefix), nearMisses: d.nearMisses.map((m) => `${m.name}|${m.role}|${m.why}`) };
}

describe("shared object-detection vectors (L12)", () => {
  const doc = structuredClone(DOC) as { _about: string; cases: Case[] };
  if (env.SV_WRITE_VECTORS) {
    for (const c of doc.cases) c.expect = run(c.names);
    it("writes the expectations", async () => {
      const fs = await import(/* @vite-ignore */ ["node", "fs"].join(":")) as { writeFileSync: (p: URL, d: string) => void };
      fs.writeFileSync(new URL("../../tests/data/object_detect_cases.json", import.meta.url), JSON.stringify(doc, null, 1) + "\n");
    });
  }
  for (const c of doc.cases) it(c.name, () => expect(run(c.names)).toEqual(c.expect));
});
