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
}

/** A new column: a formula per run, or an operation over the runs of each parameter set. */
export type Derived =
  | { name: string; kind: "row"; expr: string }
  | { name: string; kind: "set"; op: SetOp; column: string; where?: Record<string, (string | number)[]> };

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
}

export interface Objective { column: string; direction: "max" | "min"; weight: number }

export const emptyQuestion = (): Question => ({ holdValues: {}, goal: null, conditions: [], derived: [], outputAgg: "mean", objectives: [], exclude: [] });

/** What the middle of the area shows. */
export type Center = "lines" | "effects" | "map" | "scatter" | "next" | "health" | "compare";
export const CENTERS: Center[] = ["lines", "effects", "map", "scatter", "next", "health", "compare"];

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
  /** read the table again by itself when its file changes */
  follow: boolean;
}

export const emptyView = (): View => ({ mode: "sets", axes: [], colorBy: "#holds", filters: {}, reversed: {}, scales: {},
  hideConstant: true, hideFlat: false, pinned: null, rerun: [], onlyMissing: false,
  center: "lines", mapX: null, mapY: null, scatterX: null, scatterY: null, left: "question", follow: false });

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
  conditions: { label: string; column: string; met: number }[];
  sets: Col[];
  runs?: { columns: Col[]; sampled: boolean; total: number; n: number };
  seconds: number;
}

export type { Role, Scale };
