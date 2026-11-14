import { describe, expect, it } from "vitest";
import TUNING from "../../../examples/sweeps/drone_tuning.svsweep?raw";
import DEMO from "../../../examples/smart_sweep_demo/demo.svstudy.json";
import FIXTURE from "../../../tests/fixtures/drones/fixture.svstudy.json";
import type { Role as AreaRole } from "./api";
import type { Question } from "./model";
import { emptyQuestion, upgradeQuestion } from "./model";
import { areaRoles, goalToStudy, splitAnd, studyRoles, studyToGoal } from "./studyRoles";
import type { Study, StudyTable } from "./studyTypes";

const tuning = JSON.parse(TUNING) as { columns: { name: string; role: AreaRole }[]; question: Question };
const studies: [string, Study][] = [["demo", DEMO as unknown as Study], ["fixture", FIXTURE as unknown as Study]];
const flat = (c: string[] | undefined) => (c ?? []).flatMap(splitAnd);

describe("one vocabulary (C3)", () => {
  it("the single-table example's roles go to the study and back", () => {
    const area = Object.fromEntries(tuning.columns.map((c) => [c.name, c.role]));
    const st = studyRoles(area);
    expect(st.kp_roll).toBe("shared");
    expect(st.scenario_wind_mps).toBe("scenario");
    expect(st.roll_error_deg).toBe("output");
    expect(areaRoles(st, area)).toEqual(area);                       // id / recording kept through "ignore"
    expect(studyRoles(area, ["kp_roll"]).ki_roll).toBe("local");     // two systems: not shared = this system's own
  });

  for (const [name, s] of studies) {
    it(`${name}: the study's roles to the area's and back`, () => {
      for (const t of s.tables) {
        const area = areaRoles(t.roles ?? {});
        const shared = Object.entries(t.roles ?? {}).filter(([, r]) => r !== "local").map(([c]) => c);
        expect(studyRoles(area, shared)).toEqual(t.roles);
      }
    });
  }
});

describe("the Goal step writes the study (C3)", () => {
  it("the single-table example: its question as a study table and back", () => {
    const q = upgradeQuestion(tuning.question);
    const w = goalToStudy(q);
    expect(w.patch.constraints).toEqual(["roll_error_deg <= 5", "overshoot_pct <= 15", "kp_roll <= 0.25"]);
    expect(w.patch.objective).toEqual({ expr: "energy_wh", sense: "min" });
    expect(w.patch.aggregate).toBe("mean");                         // the goal shown per set as its mean
    expect(w.tableOnly).toEqual([]);
    const back = studyToGoal(w.patch, q).question;
    expect(back.conditions).toEqual(q.conditions);
    expect(back.goal).toEqual(q.goal);
    expect(goalToStudy(back).patch).toEqual(w.patch);
  });

  for (const [name, s] of studies) {
    it(`${name}: each table's goal to the Goal step and back`, () => {
      for (const t of s.tables) {
        const { question, unread } = studyToGoal(t);
        expect(unread).toEqual([]);
        expect(question.goal).toEqual({ column: t.objective!.expr, direction: t.objective!.sense });
        const w = goalToStudy(question);
        expect(w.tableOnly).toEqual([]);
        expect(flat(w.patch.constraints)).toEqual(flat(t.constraints));
        expect(w.patch.objective).toEqual(t.objective);
        expect(w.patch.aggregate).toBe(t.aggregate ?? "worst");
      }
    });
  }

  it("what the study cannot hold is the table's own, and survives a round trip", () => {
    const q = upgradeQuestion({
      ...emptyQuestion(),
      goals: [{ name: "1", combine: "and", optimize: [{ column: "err", direction: "min", weight: 1 }, { column: "energy", direction: "min", weight: 2 }],
        conditions: [
          { column: "err", op: "<", value: 3, mode: "all" },
          { column: "crash", op: "==", value: 0, mode: "atLeast", k: 2 },
          { column: "sat", op: "<", value: 0.9, mode: "all" },
          { column: "worst err", op: "<", value: 1, mode: "all" },
        ] }],
      derived: [{ name: "sat", kind: "row", expr: "motor / 100" }],
      outputAgg: "median", exclude: [3],
    });
    const w = goalToStudy(q);
    expect(w.patch.constraints).toEqual(["err < 3", "(motor / 100) < 0.9"]);
    expect(w.written).toEqual([0, 2]);
    expect(w.tableOnly).toEqual(["atLeast", "name", "aggregate", "objectives", "exclude"]);
    const back = studyToGoal({ ...w.patch, constraints: ["err < 2", ...w.patch.constraints!.slice(1)] }, q).question;
    expect(back.conditions.find((c) => c.mode === "atLeast")?.k).toBe(2);     // the table's own kept
    expect(back.conditions[0]).toEqual({ column: "err", op: "<", value: 2, mode: "all" });
    expect(back.objectives.map((o) => o.column)).toEqual(["err", "energy"]);
    expect(back.exclude).toEqual([3]);
  });

  it("the scenarios' kept values are the values not left out; an expression goal becomes a column", () => {
    const values = { wind: [0, 5, 10] };
    const q = upgradeQuestion({ ...emptyQuestion(), holdValues: { wind: [0, 5] } });
    const w = goalToStudy(q, values);
    expect(w.patch.drop).toEqual({ wind: [10] });
    const t: Pick<StudyTable, "constraints" | "objective" | "aggregate" | "drop"> = { drop: { wind: [5] }, objective: { expr: "a + 2 * b", sense: "max" }, constraints: ["3 > x and (y < 1 or z > 2)"] };
    const r = studyToGoal(t, undefined, values);
    expect(r.question.holdValues).toEqual({ wind: [0, 10] });
    expect(r.question.derived).toEqual([{ name: "objective", kind: "row", expr: "a + 2 * b" }]);
    expect(r.question.goal).toEqual({ column: "objective", direction: "max" });
    expect(r.question.conditions).toEqual([{ column: "x", op: "<", value: 3, mode: "all" }]);
    expect(r.unread).toEqual(["(y < 1 or z > 2)"]);
    expect(goalToStudy(r.question).patch.objective).toEqual({ expr: "a + 2 * b", sense: "max" });
  });
});
