/* The Sweeps area's calls (backend app/routes/sweep.py). */
import { call } from "../api";

export type Role = "param" | "hold" | "output" | "id" | "recording" | "ignore";
export type Scale = "linear" | "log" | "category" | "ordinal";
export const ROLES: Role[] = ["param", "hold", "output", "id", "recording", "ignore"];
export const SCALES: Scale[] = ["linear", "log", "category", "ordinal"];

export interface SweepColumn {
  name: string; kind: "number" | "text"; distinct: number; missing: number;
  constant: boolean; empty: boolean; min?: number; max?: number; integer?: boolean;
  values?: (number | string)[]; role: Role; scale: Scale;
}
export interface SweepSummary {
  rows: number; params: string[]; holds: string[]; outputs: string[];
  combos: number; sets: number; complete: number; missing: number; duplicates: number; failedRuns: number;
}
export interface SweepOpened {
  id: string; path: string; name: string; rows: number; columns: SweepColumn[];
  head: (number | string | null)[][]; summary: SweepSummary; seconds: number;
}

import type { WireCol } from "./decode";
import type { Condition, Derived, Objective, SetOp, Tolerance } from "./model";

/** What the server is asked: the roles of the columns and the question. */
export interface WireQuestion {
  roles: Record<string, Role>;
  combine: "and" | "or";
  holdValues: Record<string, (string | number)[]>;
  goal: { column: string; direction: "max" | "min" } | null;
  conditions: Condition[];
  derived: Derived[];
  outputAgg: Record<string, SetOp>;
  objectives: Objective[];
  exclude: number[];
  robust?: Record<string, Tolerance>;
}
export interface WireAnswer {
  counts: { sets: number; holding: number; complete: number; combos: number; rows: number };
  conditions: { label: string; column: string; met: number }[];
  sets: WireCol[];
  runs?: { columns: WireCol[]; sampled: boolean; total: number; n: number };
  seconds: number;
}
export interface SetDetail {
  params: Record<string, string | number | null>;
  columns: string[]; holds: string[];
  runs: (string | number | null)[][];
  why: { condition: number; column: string; broken: number; of: number; worst: number | null; noResult?: boolean;
    where: Record<string, string | number | null> | null }[];
  missingCombos: number;
  rows: number[];
  recordings: string[];
  /** each run's recording, in the order of `runs` (null: none) */
  recordingPerRun: (string | null)[];
}
/** A template: the roles, scales, question and view of a study, without its table - for the next
 *  table with the same columns. */
export interface SweepTemplate {
  name: string;
  /** when it was saved (local time, "YYYY-MM-DD HH:MM"; older templates have none) */
  saved?: string;
  columns: { name: string; role: Role; scale: Scale }[];
  question: unknown;
  view: unknown;
}
export interface VariantResult { holding?: number; sets?: number; error?: string; robust?: number | null; tolerance?: number | null;
  best?: { value: number; params: Record<string, string | number | null>; score?: number | null } | null; conditions?: { label: string; met: number }[] }
export interface Effects { params: { param: string; numeric: boolean; importance: number;
  levels: { value: number | string; mean: number | null; min: number | null; max: number | null; holding: number | null; sets: number }[] }[] }
export interface PairMap { x: string; y: string; xs: (number | string)[]; ys: (number | string)[]; share: (number | null)[][]; best: (number | null)[][]; count: number[][] }
export type SuggestKind = "edge" | "best" | "disagree" | "gaps" | "missing" | "robust";
export interface Suggestion { params: Record<string, number | string | null>; kind: SuggestKind; from: number; param?: string; distance?: number; set?: number }
export interface Suspect { row: number; set: number; column: string; value: number | null; expected: number | null; z: number;
  where: Record<string, string | number | null>; params: Record<string, string | number | null> }
export interface CompareResult { matched: number; onlyA: number; onlyB: number; nowHold: number; noLongerHold: number;
  rows: { params: Record<string, string | number | null>; holdsA: boolean; holdsB: boolean; goalA?: number | null; goalB?: number | null; delta?: number | null }[] }

export const sweepApi = {
  open: (path: string) => call<SweepOpened>("/api/sweep/open", { path }),
  summary: (id: string, roles: Record<string, Role>) => call<SweepSummary>("/api/sweep/summary", { id, roles }),
  example: () => call<{ path: string; refine: string }>("/api/sweep/example"),
  variants: (id: string, question: WireQuestion, variants: { goal: unknown; conditions: unknown; combine: string; objectives: unknown }[]) =>
    call<{ variants: VariantResult[] }>("/api/sweep/variants", { id, question, variants }),
  rows: (id: string, offset: number, limit: number, sort?: string, desc?: boolean) =>
    call<{ total: number; offset: number; columns: string[]; rows: (string | number | null)[][]; index: number[] }>(
      `/api/sweep/rows?id=${encodeURIComponent(id)}&offset=${offset}&limit=${limit}${sort ? `&sort=${encodeURIComponent(sort)}&desc=${!!desc}` : ""}`),
  raw: (id: string) => call<{ columns: WireCol[]; n: number; total: number; sampled: boolean }>("/api/sweep/raw", { id, question: {} }),
  evaluate: (id: string, question: WireQuestion, runs: boolean) =>
    call<WireAnswer>("/api/sweep/evaluate", { id, question, runs }),
  set: (id: string, question: WireQuestion, set: number) => call<SetDetail>("/api/sweep/set", { id, question, set }),
  openRows: (name: string, columns: string[], rows: (string | number | null)[][]) => call<SweepOpened>("/api/sweep/open-rows", { name, columns, rows }),
  effects: (id: string, question: WireQuestion) => call<Effects>("/api/sweep/effects", { id, question }),
  map: (id: string, question: WireQuestion, x: string, y: string, rest: "all" | "best" = "all") =>
    call<PairMap & { rest: "all" | "best"; fixed: Record<string, string | number | null> | null; goal: boolean; direction: "max" | "min"; bestAt: [number, number] | null }>("/api/sweep/map", { id, question, x, y, rest }),
  suggest: (id: string, question: WireQuestion, kinds: SuggestKind[], budget: number, focus: string[] | null) =>
    call<{ suggestions: Suggestion[]; available: Record<string, number> }>("/api/sweep/suggest", { id, question, kinds, budget, focus }),
  suggestExport: (id: string, question: WireQuestion, params: Suggestion["params"][], path: string) =>
    call<{ path: string; rows: number }>("/api/sweep/suggest/export", { id, question, params, path }),
  suspects: (id: string, question: WireQuestion) => call<{ suspects: Suspect[] }>("/api/sweep/suspects", { id, question }),
  compare: (a: { id: string; question: WireQuestion }, b: { id: string; question: WireQuestion }) => call<CompareResult>("/api/sweep/compare", { a, b }),
  merge: (id: string, path: string, keys: string[], prefer: "new" | "old" | "both") =>
    call<SweepOpened & { added: number; replaced: number; sources: string[] }>("/api/sweep/merge", { id, path, keys, prefer }),
  unmerge: (id: string, path: string) => call<SweepOpened & { sources: string[] }>("/api/sweep/unmerge", { id, path }),
  exportSets: (id: string, question: WireQuestion, sets: number[], columns: string[], labels: Record<string, string>, path: string) =>
    call<{ path: string; rows: number }>("/api/sweep/export-sets", { id, question, sets, columns, labels, path }),
  exportRows: (id: string, question: WireQuestion, sel: { sets?: number[]; rows?: number[] }, path: string) =>
    call<{ path: string; rows: number }>("/api/sweep/export-rows", { id, question, ...sel, path }),
  reload: (id: string) => call<SweepOpened>("/api/sweep/reload", { path: id }),
  changed: (id: string) => call<{ changed: boolean; missing?: boolean }>(`/api/sweep/changed?id=${encodeURIComponent(id)}`),
  templates: () => call<{ templates: SweepTemplate[]; folder: string }>("/api/sweep/templates"),
  saveTemplate: (name: string, template: Omit<SweepTemplate, "name">) => call<{ templates: SweepTemplate[] }>("/api/sweep/templates/save", { name, template }),
  exportTemplate: (name: string, path: string) => call<{ path: string }>("/api/sweep/templates/export", { name, path }),
  importTemplate: (path: string) => call<{ templates: SweepTemplate[]; name: string }>("/api/sweep/templates/import", { path }),
  deleteTemplate: (name: string) => call<{ templates: SweepTemplate[] }>("/api/sweep/templates/delete", { name }),
  report: (id: string, question: WireQuestion, body: Record<string, unknown>) =>
    call<{ path: string; size: number }>("/api/sweep/report", { id, question, ...body }),
  saveText: (path: string, text: string) => call<{ path: string }>("/api/sweep/save-text", { path, text }),
  loadText: (path: string) => call<{ path: string; text: string }>("/api/sweep/load-text", { path }),
  autosave: () => call<{ state: unknown; damaged?: string }>("/api/sweep/autosave"),
  autosaveSave: (state: unknown) => call<{ ok: boolean }>("/api/sweep/autosave", state),
  exportRerun: (id: string, question: WireQuestion, sets: number[], onlyMissing: boolean, path: string) =>
    call<{ path: string; rows: number }>("/api/sweep/export", { id, question, sets, onlyMissing, path }),
};
