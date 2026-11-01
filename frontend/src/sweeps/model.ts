/* The Sweeps area's data model: the question asked of a results table, how its columns are shown,
   and the decoded answer. Plain types only - state.ts keeps them, components draw them. */
import type { Role, Scale } from "./api";

export type Op = ">=" | "<=" | ">" | "<" | "==" | "!=";
export const OPS: Op[] = [">=", "<=", ">", "<", "==", "!="];
export type SetOp = "min" | "max" | "mean" | "median" | "p10" | "p90" | "std" | "spread" | "count" | "count_true";
export const SET_OPS: SetOp[] = ["min", "max", "mean", "median", "p10", "p90", "std", "spread", "count", "count_true"];
export const OUTPUT_AGGS: SetOp[] = ["mean", "min", "max", "median", "p10", "p90", "spread"];

/** A condition on an output (or a per-set column): met in every combination, in at least k, or in
 *  every combination of some must-hold-across values. */
export interface Condition {
  column: string; op: Op; value: number;
  mode: "all" | "atLeast" | "only";
  k?: number;
  where?: Record<string, (string | number)[]>;
  /** MF01: a parameter among these values (a categorical one's levels); op / value are then unused */
  in?: (string | number)[];
}

/** A condition in words: `p ∈ {a, b}` or `out <= 5`. */
export const condText = (c: Condition) => (c.in ? `${c.column} ∈ {${c.in.join(", ")}}` : `${c.column} ${c.op} ${c.value}`);

/** A new column: a formula per run, or an operation over the runs of each parameter set. */
export type Derived =
  | { name: string; kind: "row"; expr: string }
  | { name: string; kind: "set"; op: SetOp; column: string; where?: Record<string, (string | number)[]> };

/** A goal: conditions met together (and) or any of them (or), and what to optimize - the first ranks
 *  the sets, two or more also give the Pareto front and a weighted score. A study keeps several
 *  goals, to see what changes when one is changed ("what if the roll limit were 4?"). */
export interface GoalVariant {
  name: string;
  conditions: Condition[];
  combine: "and" | "or";
  optimize: Objective[];
}

export const newGoal = (name: string): GoalVariant => ({ name, conditions: [], combine: "and", optimize: [] });

export interface Question {
  /** kept values of each must-hold-across column (missing or empty: all) */
  holdValues: Record<string, (string | number)[]>;
  goal: { column: string; direction: "max" | "min" } | null;
  conditions: Condition[];
  derived: Derived[];
  /** how an output shows per parameter set */
  outputAgg: SetOp;
  /** several goals at once: the Pareto front and a weighted score (worst case of each) */
  objectives: Objective[];
  /** runs left out (rows of the table), e.g. suspicious ones */
  exclude: number[];
  /** the goals; `active` is the one answered - goal, conditions, objectives and combine above are its */
  goals: GoalVariant[];
  active: number;
  combine: "and" | "or";
  /** columns taken out in the cleaning step (constant, empty, or not wanted) */
  removed: string[];
  /** robust to these parameters (S06, optional): the sets within each one's tolerance must hold
   *  too, and the goal is their worst case - for every goal of the study */
  robust?: Record<string, Tolerance>;
}

/** How far a parameter may move: a percentage of its value, a value either way, or steps of the grid. */
export interface Tolerance { mode: "pct" | "abs" | "steps"; value: number }

export interface Objective { column: string; direction: "max" | "min"; weight: number }

export const emptyQuestion = (): Question => ({ holdValues: {}, goal: null, conditions: [], derived: [], outputAgg: "mean", objectives: [], exclude: [],
  goals: [newGoal("1")], active: 0, combine: "and", removed: [] });

/** The active goal's parts, where the rest of the code reads them. */
export function materialize(q: Question): Question {
  const g = q.goals[q.active] ?? q.goals[0];
  if (!g) return q;
  const opt = g.optimize;
  return { ...q, conditions: g.conditions, combine: g.combine,
    goal: opt[0] ? { column: opt[0].column, direction: opt[0].direction } : null,
    objectives: opt.length >= 2 ? opt : [] };
}

/** A question saved before goals had variants: its goal and conditions become goal 1. */
export function upgradeQuestion(q: Partial<Question>): Question {
  const base = { ...emptyQuestion(), ...q };
  if (!q.goals?.length) {
    const optimize: Objective[] = q.objectives?.length ? q.objectives : q.goal ? [{ ...q.goal, weight: 1 }] : [];
    base.goals = [{ name: "1", conditions: q.conditions ?? [], combine: q.combine ?? "and", optimize }];
    base.active = 0;
  }
  return materialize(base);
}

/** The steps of the work, in order. */
export type Step = "raw" | "clean" | "roles" | "goals" | "results" | "report";
export const STEPS: Step[] = ["raw", "clean", "roles", "goals", "results", "report"];

/** What the middle of the area shows. */
/** A line of the study's journal (S08): when, what kind of step, its details (rendered in the
 *  report's language). */
export type LogKind = "open" | "merge" | "unmerge" | "template" | "reset" | "roles" | "clean" | "scenarios" | "derived"
  | "goalAdd" | "goalRemove" | "goal" | "robust" | "excludeRuns" | "keep" | "exclude" | "scopeBack" | "suggest" | "export" | "report";
export interface LogEntry { at: string; kind: LogKind; args: Record<string, string | number>;
  /** left out of the report by hand (S20) */
  hidden?: boolean }
/** An iteration: the study after each table merged in (1: the first table) - its latest answer. */
export interface Iteration { n: number; label: string; at: string; sets: number; holding: number; best: number | null }

/** Next runs' choices and their last answer (S06), kept with the study and in the report. */
export interface NextRuns {
  /** the parameters to explore (missing: all) */
  focus?: string[];
  kinds?: string[];
  budget?: number;
  result?: { suggestions: { params: Record<string, number | string | null>; kind: string; from: number; param?: string }[];
    available: Record<string, number>; at: string; focus: string[] | null;
    /** how many of each kind went into the suggestions, and the budget asked (S16) */
    taken?: Record<string, number>; budget?: number;
    /** the question it answered: when the question changes, it is out of date */
    key?: string };
  /** the run list written last */
  exported?: string;
}

export type Center = "lines" | "explore" | "charts" | "effects" | "map" | "scatter" | "next" | "health" | "compare";
export const CENTERS: Center[] = ["lines", "explore", "charts", "effects", "map", "scatter", "next", "health", "compare"];

/** MF02: a pane of the chart desktop and what it shows. */
export type PaneKind = "lines" | "scatter" | "bubble" | "histogram" | "box" | "matrix" | "map" | "history" | "pareto" | "compare" | "broken";
export interface DeskPane { kind: PaneKind; x?: string; y?: string; size?: string; columns?: string[]; corr?: "pearson" | "spearman";
  /** only this group's sets (an automatic group, "marked" or a user group's id; missing: all) */
  group?: string }

/** A range filter on an axis keeps a value inside any of its ranges; a category filter keeps the
 *  listed values (codes into the column's labels). */
export type Filter = { kind: "ranges"; ranges: [number, number][] } | { kind: "values"; values: number[] };

export interface View {
  /** a line per parameter set, or per run */
  mode: "sets" | "runs";
  /** the axes shown, in order */
  axes: string[];
  colorBy: string | null;
  filters: Record<string, Filter>;
  reversed: Record<string, boolean>;
  /** a scale for a column that is not a table column (a goal, a condition's worst case...) */
  scales: Record<string, Scale>;
  hideConstant: boolean;
  hideFlat: boolean;
  /** the parameter set open on the right */
  pinned: number | null;
  /** parameter sets to run again */
  rerun: number[];
  onlyMissing: boolean;
  center: Center;
  /** the map's and the scatter's axes */
  mapX: string | null; mapY: string | null;
  scatterX: string | null; scatterY: string | null;
  /** the left side: the question, or the columns */
  left: "question" | "columns";
  /** the step on screen */
  step: Step;
  /** read the table again by itself when its file changes */
  follow: boolean;
  /** HiPlot's keep / exclude: steps that narrow what is shown to some parameter sets; Restore
   *  clears them. Valid for the question they were made with (`key`): the sets are its sets. */
  scope: { key: string; steps: { kind: "keep" | "exclude"; sets: number[] }[] };
  /** the parallel plot fits the width of the screen (every axis squeezed in) instead of scrolling
   *  sideways when its axes need more room (optional: older studies scroll) */
  fitAxes?: boolean;
  /** the table of sets: only the sets that hold (the export and the report's table follow it) */
  onlyHolding?: boolean;
  /** the table's columns, in order (missing: the parameters, the goal and the conditions) */
  tableColumns?: string[];
  /** the table sorted by a column (missing: best first) */
  tableSort?: { column: string; desc: boolean } | null;
  /** the maps on screen, each two parameters and the rest: every value or a slice at the best set
   *  (missing: one map, of mapX / mapY) */
  maps?: MapSpec[];
  /** the point plots on screen (missing: one, of scatterX / scatterY) */
  scatters?: { x: string; y: string }[];
  /** next runs' choices and answer */
  next?: NextRuns;
  /** the report's journal: the final story (default) or everything (S20) */
  journalAll?: boolean;
  /** the journal line where the analysis starts (its time); before it is out of the report */
  journalStart?: string;
  /** Explore's draft of a goal and the goal it started from (S21): not the goal until saved */
  explore?: { draft: import("./explore").Draft; from: number };
  /** how the plots look (S12) */
  style?: PlotStyle;
  /** axes taken off the lines lately, newest first (S15: one click brings one back) */
  axesOff?: string[];
  /** the chart desktop (MF02; missing: two panes from the study's columns) */
  desk?: { layout: 1 | 2 | 4; panes: DeskPane[] };
  /** Explore's controls as sliders or as one table of the problem (MF01; missing: sliders) */
  exploreAs?: "sliders" | "table";
  /** the user's groups of sets (MF00; optional: an old study has the automatic groups only) */
  groups?: import("./groups").Group[];
  /** the group the tools read (an automatic group's name or a user group's id; missing: all) */
  activeGroup?: string;
}

/** How the maps, point plots and *Which parameter matters* look (S12), for the study and its report. */
export interface PlotStyle {
  cmap?: "viridis" | "plasma" | "cividis" | "turbo" | "greys";
  /** a point's size, px */
  size?: number;
  /** a point's opacity, 0.1..1 (missing: less when there are many) */
  opacity?: number;
  grid?: boolean;
  minor?: boolean;
  /** the best goal written on a map's cells */
  numbers?: boolean;
}

export interface MapSpec { x: string; y: string; rest?: "all" | "best";
  /** the cells' colour: the share of sets that hold, or the best goal (missing: the goal when the
   *  goal has no conditions, else the share) */
  color?: "share" | "goal" }

export const emptyView = (): View => ({ mode: "sets", axes: [], colorBy: "#holds", filters: {}, reversed: {}, scales: {},
  hideConstant: true, hideFlat: false, pinned: null, rerun: [], onlyMissing: false,
  center: "lines", mapX: null, mapY: null, scatterX: null, scatterY: null, left: "question", step: "raw", follow: false, scope: { key: "", steps: [] } });

/** A decoded column of the answer. Text is codes into `labels`. */
export interface Col {
  name: string;
  kind: "num" | "cat";
  values: Float32Array;
  labels?: string[];
  group: "param" | "hold" | "output" | "derived" | "condition" | "goal" | "result" | "run";
  agg?: string;
  label?: string;
  part?: "worst" | "margin" | "passed";
  condition?: number;
  constant?: boolean;
  flat?: boolean;
}

export interface Answer {
  counts: { sets: number; holding: number; complete: number; combos: number; rows: number };
  conditions: { label: string; column: string; met: number; needed?: number }[];
  sets: Col[];
  runs?: { columns: Col[]; sampled: boolean; total: number; n: number };
  seconds: number;
}

export type { Role, Scale };
