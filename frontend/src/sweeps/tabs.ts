/* FT9 (owner, 2026-11-17): a filter remembers the tab it was made in (`view.filterTab`; missing: Parameter sets -
   older studies). A filter on a parameter, or on a column that is one value per set and the same in both tabs (#set,
   #holds, #group), is the same in both tabs. Any other filter made in Parameter sets keeps SETS by the sets' own values
   (an output's mean, the goal, a condition's margin, rank, score): in All runs every run of those sets is shown. One
   made in All runs keeps RUNS: in Parameter sets, the sets with at least one run that passes (the server's answer,
   `/api/sweep/select`, kept in the study as `runsTab`). Everything that reads the filters goes through here. */
import type { Col, Filter, View } from "./model";
import { hasFilter, keptMask } from "./filters";
import { activeParams } from "./view";
import { groupColumn } from "./groups";
import { wireQuestion, type Study } from "./state";
import { wireFilter, type RunSelection, type WireFilter } from "./selection";

export type Tab = "sets" | "runs";
export const tabOf = (v: View, column: string): Tab => v.filterTab?.[column] ?? "sets";

/** columns of All runs that are one value per set: the same in both tabs */
export const PER_SET = new Set(["#set", "#holds", "#group"]);

export interface FilterParts {
  /** the same in both tabs (parameters, per-set flags) */
  both: Record<string, Filter>;
  /** made in Parameter sets: they keep sets */
  sets: Record<string, Filter>;
  /** made in All runs: they keep runs */
  runs: Record<string, Filter>;
}

export function filterParts(s: Study): FilterParts {
  const params = new Set(activeParams(s));
  const out: FilterParts = { both: {}, sets: {}, runs: {} };
  for (const [c, f] of Object.entries(s.view.filters))
    out[params.has(c) || PER_SET.has(c) ? "both" : tabOf(s.view, c)][c] = f;
  return out;
}

/** The filters of the tab on screen (its axes' brushes): those made here and those the same in both tabs. */
export function ownFilters(s: Study): Record<string, Filter> {
  const p = filterParts(s);
  return { ...p.both, ...(s.view.mode === "runs" ? p.runs : p.sets) };
}

/** The filters made in the other tab that apply here (the chip above the plot). */
export function acrossFilters(s: Study): Record<string, Filter> {
  const p = filterParts(s), x = s.view.mode === "runs" ? p.sets : p.runs;
  return Object.fromEntries(Object.entries(x).filter(([, f]) => hasFilter(f)));
}

/** The sets' columns as the filters read them: the answer's, the groups' column, the set number. */
export function setFilterColumns(s: Study): Map<string, Col> {
  const a = s.answer;
  const cols = new Map((a?.sets ?? []).map((c) => [c.name, c]));
  if (!a) return cols;
  const n = a.sets[0]?.values.length ?? 0;
  if (s.view.groups?.length) cols.set("#group", groupColumn(a, s.view.groups));
  cols.set("#set", { name: "#set", kind: "num", values: Float32Array.from({ length: n }, (_, i) => i), group: "result" });
  return cols;
}

/** The filters made in All runs, as the server reads them (null: there are none) and the key of its answer. A text
 *  column's by its labels when the page has them, else by its codes (the server's own labels: the same). */
export function runsTabAsk(s: Study): { select: RunSelection; key: string } | null {
  const runs = Object.entries(filterParts(s).runs).filter(([, f]) => hasFilter(f));
  if (!runs.length || !s.answer) return null;
  const cols = new Map((s.answer.runs?.columns ?? []).map((c) => [c.name, c]));
  const filters: Record<string, WireFilter> = {};
  for (const [c, f] of runs) { const col = cols.get(c); filters[c] = col ? wireFilter(col, f) : f; }
  const select = { filters, sets: null }, question = wireQuestion(s);
  return { select, key: JSON.stringify([s.tableId, question, filters]) };
}

/** 1 for each set the filters keep, per set (exact: every set is on the page): those made in Parameter sets and those
 *  the same in both tabs (`both` false: without the parameters' - All runs filters its runs by them itself) and, when
 *  there are filters made in All runs, the server's sets with a run that passes them. `pending`: that answer is on its
 *  way (the mask then leaves them out of account). */
export function setKeep(s: Study, both = true): { mask: Uint8Array; pending: boolean } {
  const cols = setFilterColumns(s), n = s.answer?.sets[0]?.values.length ?? 0;
  const p = filterParts(s);
  const per = both ? p.both : Object.fromEntries(Object.entries(p.both).filter(([c]) => PER_SET.has(c)));
  const mask = keptMask(cols, { ...per, ...p.sets }, n);
  const ask = runsTabAsk(s);
  if (!ask) return { mask, pending: false };
  const got = s.runsTab;
  if (!got || got.key !== ask.key) return { mask, pending: true };
  const on = new Uint8Array(n);
  for (const i of got.sets) if (i < n) on[i] = 1;
  for (let i = 0; i < n; i++) mask[i] &= on[i];
  return { mask, pending: false };
}

/** 1 for each line of the tab on screen the filters keep: `cols` / `n` the mode's (scoped) columns, `index` the scoped
 *  rows' rows in the answer (sets) - the sets kept per set, and in All runs the runs' own filters. */
export function modeKeep(s: Study, cols: Map<string, Col>, n: number, index: Int32Array | null): Uint8Array {
  const runs = s.view.mode === "runs";
  const p = filterParts(s);
  const own = runs ? { ...Object.fromEntries(Object.entries(p.both).filter(([c]) => !PER_SET.has(c))), ...p.runs } : {};
  const m = keptMask(cols, own, n);
  const sk = setKeep(s, !runs).mask;
  const setOf = runs ? cols.get("#set")?.values : null;
  for (let r = 0; r < n; r++) if (m[r] && !sk[setOf ? setOf[r] : index ? index[r] : r]) m[r] = 0;
  return m;
}
