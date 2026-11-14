import { describe, expect, it } from "vitest";
import { fileKind } from "./studyFile";
import { autoTemplate, newSetupStudy, params, parseValues, readiness, removeParam, scenarios, setGoal, setOutputs, setParam, setRun,
  setScenario, setupFromResults, splitCommand, type FromTable } from "./setup";

/** The walkthrough's study from nothing (plan §4.7, 4): two parameters, one scenario column, an output, the command. */
function fromNothing() {
  let s = newSetupStudy("Roll tuning");
  s = setParam(s, "", { name: "a", min: 0, max: 2, step: 0.1, scale: "linear", values: [], count: 3 });
  s = setParam(s, "", { name: "b", min: 1, max: 3, step: 0.5, scale: "log", values: [], count: 2 });
  s = setScenario(s, "", { name: "wind", values: parseValues("0, 5") });
  s = setOutputs(s, ["err"]);
  s = setGoal(s, "err", "min", []);
  return setRun(s, { where: "pc", command: 'python "my sim.py" {{params_file}}' });
}

describe("Set up (C6)", () => {
  it("writes what varies, the scenarios and how to run into the study's own blocks", () => {
    const s = fromNothing();
    expect(s.shared).toEqual([{ name: "a" }, { name: "b" }]);
    expect(s.search?.params.a).toMatchObject({ min: 0, max: 2, step: 0.1, log: false });
    expect(s.search?.params.b.log).toBe(true);
    expect(s.start).toEqual({ grid: { a: 3, b: 2 }, scenarios: { T1: { wind: [0, 5] } } });
    expect(s.tables[0].roles).toEqual({ wind: "scenario", err: "output" });
    expect(s.tables[0].objective).toEqual({ expr: "err", sense: "min" });
    expect(s.launcher?.submit).toEqual(["python", "my sim.py", "{{params_file}}"]);
    expect(s.launcher?.local_workers).toBe(2);
    expect(JSON.parse(autoTemplate(s).replace(/\{\{(\w+)\}\}/g, (_, n) => (n === "run_id" || n === "table" || n === "study_dir" ? n : "1")))).toEqual(
      { run_id: "run_id", table: "table", a: 1, b: 1, wind: 1, out: "study_dir/results/table/run_id.csv" });
    expect(fileKind(s, 1)).toBe("svstudy");
  });

  it("says what round 1 will run and what is missing", () => {
    const empty = readiness(newSetupStudy());
    expect(empty.missing).toEqual(["params", "output", "goal", "command"]);
    const r = readiness(fromNothing());
    expect(r.missing).toEqual([]);
    expect(r.counts).toEqual([3, 2]);
    expect([r.sets, r.combos, r.runs]).toEqual([6, 2, 12]);
    expect(r.full).toEqual([21, 5]);
    expect(r.fullRuns).toBe(21 * 5 * 2);
    const noRange = setParam(fromNothing(), "a", { name: "a", min: 2, max: 1, step: null, scale: "linear", values: [], count: 3 });
    expect(readiness(noRange).missing).toEqual(["range"]);
    expect(readiness(noRange).full).toBeNull();
  });

  it("renames and removes a parameter and a scenario everywhere it is written", () => {
    let s = fromNothing();
    s = setParam(s, "a", { ...params(s)[0], name: "kp" });
    expect(s.shared?.map((p) => p.name)).toEqual(["kp", "b"]);
    expect(Object.keys(s.search!.params)).toEqual(["b", "kp"]);
    expect(s.start?.grid).toEqual({ b: 2, kp: 3 });
    expect(s.launcher?.params_template).toContain('"kp": {{kp}}');
    s = removeParam(s, "b");
    expect(params(s).map((p) => p.name)).toEqual(["kp"]);
    s = setScenario(s, "wind", { name: "gusts", values: ["none", "strong"] });
    expect(scenarios(s)).toEqual([{ name: "gusts", values: ["none", "strong"] }]);
    expect(s.tables[0].roles).toEqual({ gusts: "scenario", err: "output" });
    expect(s.launcher?.params_template).toContain('"gusts": "{{gusts}}"');
    const values = setParam(s, "kp", { name: "kp", min: null, max: null, step: null, scale: "values", values: [1, 2, 4], count: 9 });
    expect(params(values)[0]).toMatchObject({ scale: "values", values: [1, 2, 4], count: 3 });
  });

  it("a template of the user's own is left alone; a farm launcher runs a round at once", () => {
    let s = fromNothing();
    s.launcher = { ...s.launcher, params_template: "<run kp='{{a}}'/>", template_auto: false };
    s = setParam(s, "", { name: "c", min: 0, max: 1, step: 0.5, scale: "linear", values: [], count: 2 });
    expect(s.launcher?.params_template).toBe("<run kp='{{a}}'/>");
    s = setRun(s, { where: "farm", command: "submit.bat {{round_dir}} {{params_files}}" });
    expect(s.launcher).toMatchObject({ local_workers: null, submit_mode: "round" });
    expect(splitCommand("a 'b c' \"d\"")).toEqual(["a", "b c", "d"]);
  });

  it("I have results: the set-up from the table's columns, still a .svsweep", () => {
    const g: FromTable = { rows: 270, params: [{ name: "kp_roll", kind: "number", distinct: 5, values: [0.1, 0.2], min: 0.1, max: 0.5 }],
      scenarios: [{ name: "wind", kind: "number", distinct: 3, values: [0, 5, 10] }], outputs: ["err"], other: ["run_id"],
      shared: [{ name: "kp_roll" }], search: { params: { kp_roll: { min: 0.1, max: 0.5, integer: false, log: false } } },
      roles: { kp_roll: "shared", wind: "scenario", err: "output", run_id: "ignore" } };
    const s = setupFromResults(g, "/x/t.csv", "t", { constraints: ["err < 3"], objective: { expr: "err", sense: "min" }, aggregate: "worst" });
    expect(params(s)).toEqual([{ name: "kp_roll", min: 0.1, max: 0.5, step: null, scale: "linear", values: [], count: 4 }]);
    expect(s.tables[0]).toMatchObject({ paths: ["/x/t.csv"], constraints: ["err < 3"], roles: { wind: "scenario" } });
    expect(fileKind(s, 1)).toBe("svsweep");
    expect(readiness(s).missing).toEqual(["command"]);
  });
});
