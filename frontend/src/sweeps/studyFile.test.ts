import { describe, expect, it } from "vitest";
import TUNING from "../../../examples/sweeps/drone_tuning.svsweep?raw";
import TUNING_127 from "../../../tests/fixtures/sweeps/v1_27/drone_tuning.svsweep?raw";
import DEMO from "../../../examples/smart_sweep_demo/demo.svstudy.json";
import DEMO_127 from "../../../tests/fixtures/sweeps/v1_27/demo.svstudy.json";
import FIXTURE from "../../../tests/fixtures/drones/fixture.svstudy.json";
import FIXTURE_127 from "../../../tests/fixtures/sweeps/v1_27/fixture.svstudy.json";
import type { SavedStudy } from "./state";
import { fileKind, fromStudyFile, hasSetup, kindOfPath, toStudyFile } from "./studyFile";
import type { Study } from "./studyTypes";

const sweeps: [string, SavedStudy][] = [["drone_tuning", JSON.parse(TUNING)], ["drone_tuning 1.27", JSON.parse(TUNING_127)]];
const studies: [string, Study][] = [["demo", DEMO as unknown as Study], ["demo 1.27", DEMO_127 as unknown as Study],
  ["fixture", FIXTURE as unknown as Study], ["fixture 1.27", FIXTURE_127 as unknown as Study]];
const viaJson = <T>(x: T): T => JSON.parse(JSON.stringify(x));

describe("one study file (C5)", () => {
  for (const [name, doc] of sweeps) {
    it(`${name}: one table without Set up stays a .svsweep; as a study it round-trips`, () => {
      expect(fileKind(null, 1)).toBe("svsweep");
      const file = viaJson(toStudyFile(null, [doc]));
      expect(file.tables).toHaveLength(1);
      expect(file.tables[0].paths).toEqual(["drone_tuning.csv"]);
      expect(file.tables[0].objective).toEqual({ expr: "energy_wh", sense: "min" });
      expect(file.tables[0].roles?.kp_roll).toBe("shared");
      expect(hasSetup(file)).toBe(false);                               // still one table without Set up
      const back = fromStudyFile(file);
      expect(back.docs).toEqual([doc]);                                  // the area's table exactly as it was
      expect(viaJson(toStudyFile(back.setup, back.docs))).toEqual(file);
    });
  }

  for (const [name, s] of studies) {
    it(`${name}: a study file opens and saves back unchanged`, () => {
      expect(fileKind(s, 0)).toBe("svstudy");
      const back = fromStudyFile(s);
      expect(back.docs).toEqual([]);
      expect(viaJson(toStudyFile(back.setup, back.docs))).toEqual(viaJson(s));
    });
  }

  it("a study with its tables as shown keeps both; the place last shown comes back", () => {
    const doc = sweeps[0][1];
    const file = viaJson(toStudyFile(DEMO as unknown as Study, [doc, doc], 1, { part: "table", table: 1 }));
    expect(file.tables.map((t) => t.id)).toEqual(["A", "B", "C"]);          // the study's own tables are not replaced
    expect(file.workspace?.sweeps).toHaveLength(2);
    const back = fromStudyFile(file);
    expect(back.active).toBe(1);
    expect(back.place).toEqual({ part: "table", table: 1 });
    expect(back.setup.workspace).toBeUndefined();
  });

  it("what makes Save offer a study file", () => {
    const one: Study = { version: 1, tables: [{ id: "T1", paths: ["a.csv"] }] };
    expect(fileKind(one, 1)).toBe("svsweep");
    expect(fileKind({ ...one, launcher: { submit: ["python", "sim.py"] } }, 1)).toBe("svstudy");
    expect(fileKind({ ...one, start: { grid: 3 } }, 1)).toBe("svstudy");
    expect(fileKind(one, 2)).toBe("svstudy");
    expect(kindOfPath("C:/x/A.SVSTUDY.json")).toBe("svstudy");
    expect(kindOfPath("/x/a.svsweep")).toBe("svsweep");
  });
});
