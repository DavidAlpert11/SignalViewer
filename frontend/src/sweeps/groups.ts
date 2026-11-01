/* Groups of parameter sets (MF00): the unit every Sweeps tool reads and writes. A group is a rule
   (the same filters as the axes - live, it follows new results) or frozen ids (a set's id is its
   parameter values, so it survives a merge or a re-sort). Automatic groups are computed from the
   answer and never saved; the user's live in `view.groups` (optional: an old study opens with the
   automatic ones only). Mirrors backend/svcore/sweep/groups.py. Pure functions. */
import type { Answer, Col, Filter } from "./model";
import { keptMask } from "./filters";

export type GroupSource = "auto" | "user" | "doe" | "virtual" | "cluster" | "rerun";
export type AutoGroup = "all" | "holds" | "pareto" | "fails" | "error" | "suggested";
export const AUTO_GROUPS: AutoGroup[] = ["all", "holds", "pareto", "fails", "error", "suggested"];

export interface Group {
  id: string;
  name: string;
  /** a slot of the category palette (colors.ts), so both themes stay readable */
  color: number;
  source: Exclude<GroupSource, "auto">;
  /** live: the axes' filters when it was saved */
  rule?: Record<string, Filter>;
  /** frozen: the sets' ids */
  ids?: string[];
  frozen: boolean;
  /** hidden in every plot (the eye) */
  hidden?: boolean;
}

/** A set's status in the table (MF00). */
export type SetStatus = "holds" | "fails" | "error" | "virtual";

const fmt = (v: number, c: Col): string => {
  if (!Number.isFinite(v)) return "";
  if (c.kind === "cat") return c.labels?.[v] ?? "";
  return String(Number.isInteger(v) ? v : +v.toPrecision(7));
};

/** The id of every set in the answer: `p=2|k=0.1`, the parameters in the answer's order. */
export function setIds(a: Answer): string[] {
  const ps = a.sets.filter((c) => c.group === "param");
  const n = a.sets[0]?.values.length ?? 0;
  const out: string[] = new Array(n);
  for (let i = 0; i < n; i++) out[i] = ps.map((c) => `${c.name}=${fmt(c.values[i], c)}`).join("|");
  return out;
}

const flag = (a: Answer, name: string, dflt: boolean): Uint8Array => {
  const n = a.sets[0]?.values.length ?? 0;
  const c = a.sets.find((x) => x.name === name);
  const m = new Uint8Array(n);
  for (let i = 0; i < n; i++) m[i] = c ? (c.values[i] > 0.5 ? 1 : 0) : dflt ? 1 : 0;
  return m;
};

/** The automatic groups' masks: error = an output missing, fails = complete and not holding. */
export function autoMasks(a: Answer, suggested: string[] = [], ids = setIds(a)): Record<AutoGroup, Uint8Array> {
  const n = ids.length;
  const holds = flag(a, "#holds", false), complete = flag(a, "#complete", true);
  const error = new Uint8Array(n), fails = new Uint8Array(n);
  for (let i = 0; i < n; i++) { error[i] = complete[i] ? 0 : 1; fails[i] = complete[i] && !holds[i] ? 1 : 0; }
  return { all: new Uint8Array(n).fill(1), holds, pareto: flag(a, "#pareto", false), fails, error, suggested: idsMask(ids, suggested) };
}

export function idsMask(ids: string[], members: string[]): Uint8Array {
  const want = new Set(members);
  return Uint8Array.from(ids, (x) => (want.has(x) ? 1 : 0));
}

/** The sets of a user group in the current answer. */
export function groupMask(g: Group, a: Answer, ids = setIds(a)): Uint8Array {
  if (g.frozen) return idsMask(ids, g.ids ?? []);
  return keptMask(new Map(a.sets.map((c) => [c.name, c])), g.rule ?? {}, ids.length);
}

export type GroupOp = "union" | "intersect" | "minus";
export function combine(op: GroupOp, x: Uint8Array, y: Uint8Array): Uint8Array {
  return x.map((v, i) => (op === "union" ? v | y[i] : op === "intersect" ? v & y[i] : v & (1 - y[i])));
}

export const freeze = (m: Uint8Array, ids: string[]): string[] => ids.filter((_, i) => m[i]);
export const count = (m: Uint8Array): number => m.reduce((s, v) => s + v, 0);

/** The brush (the axes' filters) as a group: live by default, frozen ids with Shift. */
export function fromBrush(filters: Record<string, Filter>, a: Answer, name: string, taken: Group[], frozen: boolean): Group {
  const id = `g${Date.now().toString(36)}${taken.length}`;
  const used = new Set(taken.map((g) => g.color));
  let color = 0;
  while (used.has(color)) color++;
  if (frozen) {
    const ids = setIds(a);
    return { id, name, color, source: "user", frozen: true, ids: freeze(groupMask({ id, name, color, source: "user", frozen: false, rule: filters }, a, ids), ids) };
  }
  return { id, name, color, source: "user", frozen: false, rule: structuredClone(filters) };
}

/** Each set's status: error (an output missing), fails, holds - virtual sets come from a surrogate. */
export function statuses(a: Answer, virtual: string[] = [], ids = setIds(a)): SetStatus[] {
  const m = autoMasks(a, [], ids), v = new Set(virtual);
  return ids.map((x, i) => (v.has(x) ? "virtual" : m.error[i] ? "error" : m.fails[i] ? "fails" : "holds"));
}

/** Which conditions a set fails, and in how many of its combinations: "fails in k of n". */
export function failedConditions(a: Answer, set: number): { condition: number; label: string; passed: number }[] {
  const out: { condition: number; label: string; passed: number }[] = [];
  for (const c of a.sets) {
    if (c.part !== "passed" || c.condition == null) continue;
    const met = a.sets.find((x) => x.condition === c.condition && x.part === "margin");
    if (met && met.values[set] < 0) out.push({ condition: c.condition, label: c.label ?? c.name, passed: c.values[set] });
  }
  return out;
}

/** Saved groups as they come from a file: drop what cannot be used (never fail to open a study). */
export function upgradeGroups(gs: unknown): Group[] {
  if (!Array.isArray(gs)) return [];
  return gs.filter((g): g is Group => !!g && typeof g === "object" && typeof (g as Group).id === "string"
    && (((g as Group).frozen && Array.isArray((g as Group).ids)) || (!(g as Group).frozen && typeof (g as Group).rule === "object")));
}
