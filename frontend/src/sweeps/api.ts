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

export const sweepApi = {
  open: (path: string) => call<SweepOpened>("/api/sweep/open", { path }),
  summary: (id: string, roles: Record<string, Role>) => call<SweepSummary>("/api/sweep/summary", { id, roles }),
  example: () => call<{ path: string }>("/api/sweep/example"),
};
