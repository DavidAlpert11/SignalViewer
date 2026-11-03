/* Split by (owner's spec 2026-11-02): a condition studied value by value. The values shown, and
   each value's answer in short - how many sets hold, the best value and set, and which sets hold
   (their ids, for a group of each value). Shared by the results' bar, the groups and the report. */
import { sweepApi } from "./api";
import { decodeCol } from "./decode";
import { setIds } from "./groups";
import type { Answer } from "./model";
import { wireQuestion, type Study } from "./state";

export interface SplitRow { value: string | number | null; holding: number; sets: number; best: number | null; set: string; holds: string[] }

/** the values the split shows: those kept in its condition */
export function splitValues(s: Study): (string | number)[] {
  const c = s.columns.find((x) => x.name === s.question.split);
  if (!c) return [];
  const kept = s.question.holdValues[c.name] ?? [];
  return kept.length ? kept : c.values ?? [];
}

/** the split condition, when it is one of this study's conditions */
export const splitColumn = (s: Study): string | null =>
  s.question.split && s.columns.some((c) => c.name === s.question.split && c.role === "hold") ? s.question.split : null;

/** All together, then each value: the answer for it, in short */
export async function splitRows(s: Study): Promise<SplitRow[]> {
  return Promise.all([null, ...splitValues(s)].map(async (v): Promise<SplitRow> => {
    const w = await sweepApi.evaluate(s.tableId, wireQuestion({ ...s, view: { ...s.view, splitValue: v } }), false);
    const a: Answer = { counts: w.counts, conditions: w.conditions, seconds: w.seconds, sets: w.sets.map((c) => decodeCol(c)) };
    const rank = a.sets.find((c) => c.name === "#rank")?.values, goal = a.sets.find((c) => c.name === "#goal")?.values;
    const hold = a.sets.find((c) => c.name === "#holds")?.values;
    const ids = setIds(a);
    let at = -1, r0 = Infinity;
    if (rank) for (let i = 0; i < rank.length; i++) if (rank[i] < r0) { r0 = rank[i]; at = i; }
    return { value: v, holding: w.counts.holding, sets: w.counts.sets, best: at >= 0 && goal ? goal[at] : null,
      set: at >= 0 ? ids[at].replace(/\|/g, ", ") : "", holds: hold ? ids.filter((_, i) => hold[i] === 1) : [] };
  }));
}

/** a set is in the re-run list for what is shown now: All together, or this split value */
export function inRerun(s: Study, set: number): boolean {
  const sv = s.view.splitValue;
  if (sv === undefined || sv === null || !s.question.split || !s.answer) return s.view.rerun.includes(set);
  const id = setIds(s.answer)[set];
  return (s.view.rerunSplit ?? []).some((r) => r.id === id && r.value === sv);
}
/** every set in the re-run list: All together and for split values */
export const rerunCount = (s: Study) => s.view.rerun.length + (s.view.rerunSplit?.length ?? 0);
