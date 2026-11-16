/* PLAN_2026-11-16 §7a: one way through every study - 1 Data · 2 Columns · 3 Goal · 4 Results · 5 Next runs.
   A table's own steps (its saved `view.step` / `view.center`) and the study file's parts (`part`: its problem
   definition, the demo's About, the systems together, the runs) are two ways of saying where the user is; this
   file reads one step out of both and says what a click on a step changes. UI only: nothing here is saved. */
import { normCenter, normStep, type Center, type Step, type View } from "./model";
import type { Part } from "./state";

export type FlowStep = "data" | "columns" | "goal" | "results" | "next";
export const FLOW: FlowStep[] = ["data", "columns", "goal", "results", "next"];
/** FR5: a table of recordings has no runs to send or propose: its steps stop at Results (the goal step is its limits). */
export const flowSteps = (recordings: boolean): FlowStep[] => (recordings ? FLOW.filter((s) => s !== "next") : FLOW);

/** Where the area stands: the part shown, the active table's step (null: no table open), the study file. */
export interface FlowAt {
  part: Part;
  table: { step: Step; center: Center } | null;
  common: boolean;                 // a study file is open
  systems: number;                 // its tables (systems): two or more are a view of Results together
}

export function flowStep(a: FlowAt): FlowStep {
  if (a.part === "run") return "next";               // a study file with no table open
  if (a.part === "setup" || a.part === "about") return "data";
  if (a.part === "together") return "results";
  if (a.table) {
    const s = normStep(a.table.step);
    if (s === "raw") return "data";
    if (s === "roles") return "columns";
    if (s === "goals") return "goal";
    return normCenter(a.table.center) === "next" ? "next" : "results";
  }
  return a.common && a.systems > 1 ? "results" : "data";
}

/** What a click on a step changes (the part shown, the active table's view), or null: not open yet (no table). */
export function flowGo(a: FlowAt, to: FlowStep): { part: Part; view?: Partial<View> } | null {
  const off = a.table && normCenter(a.table.center) === "next" ? { center: "lines" as Center } : {};
  switch (to) {
    case "data": return a.table ? { part: "table", view: { step: "raw" } } : a.common ? { part: "setup" } : null;
    case "columns": return a.table ? { part: "table", view: { step: "roles" } } : null;
    case "goal": return a.table ? { part: "table", view: { step: "goals" } } : null;
    case "results": return a.table ? { part: "table", view: { step: "results", ...off } } : a.common && a.systems > 1 ? { part: "together" } : null;
    // a table keeps its place in its own view (saved with it: it opens again on Next runs)
    case "next": return a.table ? { part: "table", view: { step: "results", center: "next" } } : a.common ? { part: "run" } : null;
  }
}
