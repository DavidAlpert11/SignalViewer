/* The Sweeps area's calls (backend app/routes/sweep.py). */
import { call } from "../api";

export type Role = "param" | "hold" | "output" | "id" | "ignore";
export type Scale = "linear" | "log" | "category" | "ordinal";
export const ROLES: Role[] = ["param", "hold", "output", "id", "ignore"];
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
import type { Condition, Derived, SetOp } from "./model";

/** What the server is asked: the roles of the columns and the question. */
export interface WireQuestion {
  roles: Record<string, Role>;
  holdValues: Record<string, (string | number)[]>;
  goal: { column: string; direction: "max" | "min" } | null;
  conditions: Condition[];
  derived: Derived[];
  outputAgg: Record<string, SetOp>;
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
}

export const sweepApi = {
  open: (path: string) => call<SweepOpened>("/api/sweep/open", { path }),
  summary: (id: string, roles: Record<string, Role>) => call<SweepSummary>("/api/sweep/summary", { id, roles }),
  example: () => call<{ path: string }>("/api/sweep/example"),
  evaluate: (id: string, question: WireQuestion, runs: boolean) =>
    call<WireAnswer>("/api/sweep/evaluate", { id, question, runs }),
  set: (id: string, question: WireQuestion, set: number) => call<SetDetail>("/api/sweep/set", { id, question, set }),
  exportRerun: (id: string, question: WireQuestion, sets: number[], onlyMissing: boolean, path: string) =>
    call<{ path: string; rows: number }>("/api/sweep/export", { id, question, sets, onlyMissing, path }),
};
