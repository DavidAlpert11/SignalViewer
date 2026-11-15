import { describe, expect, it } from "vitest";
import { flowGo, flowStep, type FlowAt } from "./flow";
import type { Step } from "./model";

const table = (step: Step) => ({ step, center: "lines" as const });
const at = (p: Partial<FlowAt>): FlowAt => ({ part: "table", table: null, common: false, systems: 0, ...p });

describe("one way through a study (PLAN 2026-11-16 §7a)", () => {
  it("reads one step from a table's view and from the study file's part", () => {
    expect(flowStep(at({ table: table("raw") }))).toBe("data");
    expect(flowStep(at({ table: table("clean") }))).toBe("columns");          // an old study's step
    expect(flowStep(at({ table: table("goals") }))).toBe("goal");
    expect(flowStep(at({ table: table("report") }))).toBe("results");
    expect(flowStep(at({ table: { step: "results", center: "next" } }))).toBe("next");   // saved on the old Next runs tab
    expect(flowStep(at({ part: "setup", table: table("results") }))).toBe("data");
    expect(flowStep(at({ part: "run", table: table("results") }))).toBe("next");
    expect(flowStep(at({ part: "", common: true, systems: 3 }))).toBe("results");
    expect(flowStep(at({ part: "", common: true, systems: 1 }))).toBe("data");     // started from nothing
  });

  it("opens only the steps there is something for", () => {
    const fileOnly = at({ part: "setup", common: true, systems: 1 });
    expect(flowGo(fileOnly, "columns")).toBeNull();
    expect(flowGo(fileOnly, "results")).toBeNull();
    expect(flowGo(fileOnly, "next")).toEqual({ part: "run" });
    expect(flowGo(at({ part: "", common: true, systems: 2 }), "results")).toEqual({ part: "together" });
    expect(flowGo(at({ table: table("results") }), "data")).toEqual({ part: "table", view: { step: "raw" } });
  });

  it("keeps a table's Next runs in its own view (saved with it), and leaves it for the results", () => {
    const t = at({ table: table("goals") });
    expect(flowGo(t, "next")).toEqual({ part: "table", view: { step: "results", center: "next" } });
    const next = at({ table: { step: "results", center: "next" } });
    expect(flowGo(next, "results")).toEqual({ part: "table", view: { step: "results", center: "lines" } });
  });
});
