/* Explore (S21): a draft of a goal - its conditions (dragged as "what if"), limits on the parameters,
   and the objectives (direction, weight, an optional threshold) - all applied together to one list
   of parameter sets, none of it the study's goal until saved.

   Speed: a set's worst case for a condition or an objective does not depend on the limit it is
   compared with, so the server answers once per draft *structure* (which columns, which operators,
   which objectives) and every slider is applied here at once. Robustness is the exception (whether
   the neighbours hold depends on the values), so with robustness the values are part of the
   structure and the server is asked again, a moment after a drag. */
import { materialize, type Answer, type Col, type Condition, type Filter, type GoalVariant, type Objective, type Op } from "./model";
import type { Study } from "./state";

export interface DraftObjective extends Objective {
  /** "good enough": the sets whose worst case is past it are out (missing: none) */
  threshold?: number;
}
export interface Draft {
  conditions: Condition[];
  combine: "and" | "or";
  /** numeric parameters' allowed ranges (missing: the whole range) */
  limits: Record<string, [number, number]>;
  objectives: DraftObjective[];
}

export const draftOf = (g: GoalVariant): Draft => ({
  conditions: g.conditions.filter((c) => c.column).map((c) => ({ ...c })),
  combine: g.combine,
  limits: {},
  objectives: g.optimize.map((o) => ({ ...o })),
});

/** What the server must answer again for (the values only with robustness). */
export function structureKey(d: Draft, robust: boolean): string {
  return JSON.stringify([d.conditions.map((c) => [c.column, c.op, c.mode, c.k, c.where, robust ? c.value : 0]),
    d.combine, d.objectives.map((o) => [o.column, o.direction])]);
}

/** The answer's values come as Float32 (0.2 is 0.20000000298...): compared with what was typed or
 *  dragged (a double), equal means equal to Float32's precision - else a limit "<= 0.2" left out
 *  every set at 0.2 that the server, in doubles, keeps. */
const near = (a: number, b: number) => Math.abs(a - b) <= 1e-6 * Math.max(1, Math.abs(b));
const cmp = (op: Op, a: number, b: number) =>
  op === "<=" ? a <= b || near(a, b) : op === ">=" ? a >= b || near(a, b) : op === "<" ? a < b && !near(a, b)
    : op === ">" ? a > b && !near(a, b) : op === "==" ? near(a, b) : !near(a, b);

/** An objective's worst case per set: the goal's column for the first, #obj<k> for the others. */
export const objectiveCol = (k: number) => (k === 0 ? "#goal" : `#obj${k}`);

export interface Explored {
  n: number;
  /** after the conditions, after the limits too, after the thresholds too */
  funnel: [number, number, number, number];
  survivors: number[];
  /** each control: how many sets it alone takes out (they pass everything else) */
  alone: Record<string, number>;
  /** the survivors, best first */
  ranked: number[];
  /** the score of each ranked set (several objectives), else its first objective */
  value: Map<number, number>;
  /** the Pareto front of the survivors on the first two objectives */
  front: Set<number>;
}

/** Everything the draft says, on the answer to its structure. Controls are named c<i> (a
 *  condition), p:<name> (a parameter's limit), o<k> (an objective's threshold). */
export function explore(a: Answer, d: Draft, robust: boolean): Explored {
  const cols = new Map<string, Col>(a.sets.map((c) => [c.name, c]));
  const n = a.sets[0]?.values.length ?? 0;
  const complete = cols.get("#complete")?.values;
  const robustHolds = robust ? cols.get("#robustHolds")?.values : undefined;
  const conds = d.conditions.map((c, i) => ({ id: `c${i}`, worst: cols.get(`#c${i}.worst`)?.values, c }));
  const limits = Object.entries(d.limits).map(([p, [lo, hi]]) => ({ id: `p:${p}`, v: cols.get(p)?.values, lo, hi }));
  const thresholds = d.objectives.map((o, k) => ({ id: `o${k}`, v: cols.get(objectiveCol(k))?.values, o })).filter((x) => x.o.threshold !== undefined && x.v);
  const condPass = (s: number, skip?: string) => {
    if (complete && complete[s] !== 1) return false;
    if (robustHolds && robustHolds[s] !== 1) return false;
    const live = conds.filter((x) => x.id !== skip && x.worst);
    if (!live.length) return true;
    const ok = (x: (typeof conds)[number]) => Number.isFinite(x.worst![s]) && cmp(x.c.op, x.worst![s], x.c.value);
    return d.combine === "or" ? live.some(ok) : live.every(ok);
  };
  const limitPass = (s: number, skip?: string) => limits.every((x) => x.id === skip || !x.v || (cmp(">=", x.v[s], x.lo) && cmp("<=", x.v[s], x.hi)));
  const thresholdPass = (s: number, skip?: string) => thresholds.every((x) => x.id === skip ||
    (Number.isFinite(x.v![s]) && cmp(x.o.direction === "min" ? "<=" : ">=", x.v![s], x.o.threshold!)));
  const funnel: [number, number, number, number] = [n, 0, 0, 0];
  const survivors: number[] = [];
  for (let s = 0; s < n; s++) {
    if (!condPass(s)) continue;
    funnel[1]++;
    if (!limitPass(s)) continue;
    funnel[2]++;
    if (!thresholdPass(s)) continue;
    funnel[3]++;
    survivors.push(s);
  }
  const alone: Record<string, number> = {};
  for (const id of [...conds.map((x) => x.id), ...limits.map((x) => x.id), ...thresholds.map((x) => x.id)]) {
    let k = 0;
    for (let s = 0; s < n; s++) if (condPass(s, id) && limitPass(s, id) && thresholdPass(s, id)) k++;
    alone[id] = k - survivors.length;
  }
  // ranking: one objective by its worst case; several by a weighted score of each one's place
  // among the survivors (1 = the best of them on every objective), as the server's score
  const objs = d.objectives.map((o, k) => ({ o, v: cols.get(objectiveCol(k))?.values })).filter((x) => x.v);
  const value = new Map<number, number>();
  if (objs.length === 1) {
    const { o, v } = objs[0];
    for (const s of survivors) value.set(s, Number.isFinite(v![s]) ? (o.direction === "max" ? v![s] : -v![s]) : -Infinity);
  } else if (objs.length > 1) {
    const wsum = objs.reduce((t, x) => t + Math.max(0, x.o.weight), 0) || 1;
    const norm = objs.map(({ o, v }) => {
      let lo = Infinity, hi = -Infinity;
      for (const s of survivors) if (Number.isFinite(v![s])) { lo = Math.min(lo, v![s]); hi = Math.max(hi, v![s]); }
      return (s: number) => (!Number.isFinite(v![s]) ? 0 : hi === lo ? 1 : o.direction === "max" ? (v![s] - lo) / (hi - lo) : (hi - v![s]) / (hi - lo));
    });
    for (const s of survivors) value.set(s, objs.reduce((t, x, k) => t + Math.max(0, x.o.weight) * norm[k](s), 0) / wsum);
  }
  const ranked = objs.length ? [...survivors].sort((x, y) => (value.get(y)! - value.get(x)!) || x - y) : [...survivors];
  if (objs.length === 1) for (const s of survivors) value.set(s, objs[0].v![s]);       // shown as the value itself
  // the Pareto front on the first two objectives (better = smaller when minimizing)
  const front = new Set<number>();
  if (objs.length >= 2) {
    const g = (k: number, s: number) => (objs[k].o.direction === "max" ? -objs[k].v![s] : objs[k].v![s]);
    for (const s of survivors) {
      if (!Number.isFinite(g(0, s)) || !Number.isFinite(g(1, s))) continue;
      const beaten = survivors.some((t) => t !== s && g(0, t) <= g(0, s) && g(1, t) <= g(1, s) && (g(0, t) < g(0, s) || g(1, t) < g(1, s)));
      if (!beaten) front.add(s);
    }
  }
  return { n, funnel, survivors, alone, ranked, value, front };
}

/** The draft as a goal: its conditions, each limit narrower than the parameter's range and each
 *  threshold as conditions too (worst case, every combination), its objectives. With "or" a limit
 *  or a threshold cannot be said (it would be one more alternative), so the caller refuses. */
export function goalOfDraft(d: Draft, name: string, ranges: Record<string, [number, number]>): GoalVariant {
  const extra: Condition[] = [];
  for (const [p, [lo, hi]] of Object.entries(d.limits)) {
    const [min, max] = ranges[p] ?? [-Infinity, Infinity];
    if (lo > min + 1e-12) extra.push({ column: p, op: ">=", value: lo, mode: "all" });
    if (hi < max - 1e-12) extra.push({ column: p, op: "<=", value: hi, mode: "all" });
  }
  for (const o of d.objectives) if (o.threshold !== undefined)
    extra.push({ column: o.column, op: o.direction === "min" ? "<=" : ">=", value: o.threshold, mode: "all" });
  return { name, combine: d.combine, conditions: [...d.conditions.map((c) => ({ ...c })), ...extra],
    optimize: d.objectives.map(({ column, direction, weight }) => ({ column, direction, weight })) };
}

/** Whether a draft adds what an "or" goal cannot say. */
export const needsAnd = (d: Draft, ranges: Record<string, [number, number]>) =>
  d.combine === "or" && goalOfDraft({ ...d, conditions: [] }, "", ranges).conditions.length > 0;

/** How the draft differs from the goal, in words' keys and counts. */
export function draftChanges(d: Draft, g: GoalVariant, ranges: Record<string, [number, number]>): number {
  const asGoal = goalOfDraft(d, g.name, ranges);
  let k = 0;
  const key = (c: Condition) => JSON.stringify([c.column, c.op, c.value, c.mode, c.k, c.where]);
  const a = new Set(g.conditions.filter((c) => c.column).map(key)), b = new Set(asGoal.conditions.map(key));
  for (const x of a) if (!b.has(x)) k++;
  for (const x of b) if (!a.has(x)) k++;
  const ok = (o: Objective) => JSON.stringify([o.column, o.direction, o.weight]);
  const oa = new Set(g.optimize.map(ok)), ob = new Set(asGoal.optimize.map(ok));
  for (const x of oa) if (!ob.has(x)) k++;
  for (const x of ob) if (!oa.has(x)) k++;
  return k;
}

/** A parameter's range in the draft: its limit, or the whole range (= no limit). */
export const limitOf = (d: Draft, p: string, ranges: Record<string, [number, number]>): [number, number] =>
  d.limits[p] ?? ranges[p];

/** Whether a limit narrows its parameter at all (the slider's two ends at the range's: no limit). */
export const isLimited = (lim: [number, number] | undefined, range: [number, number] | undefined) =>
  !!lim && !!range && ((lim[0] > range[0] && !near(lim[0], range[0])) || (lim[1] < range[1] && !near(lim[1], range[1])));

/** The limits with a parameter's new range: one back at the whole range is no limit any more. */
export function withLimit(d: Draft, p: string, lim: [number, number], ranges: Record<string, [number, number]>): Draft {
  const limits = { ...d.limits };
  if (isLimited(lim, ranges[p])) limits[p] = lim;
  else delete limits[p];
  return { ...d, limits };
}

/** S23: an objective's threshold is "off" at the slider's far end - the end that keeps everything
 *  (the largest value when minimizing, the smallest when maximizing). */
export const thresholdOffEnd = (direction: "max" | "min", lo: number, hi: number) => (direction === "min" ? hi : lo);
export const thresholdOf = (direction: "max" | "min", v: number, lo: number, hi: number) =>
  near(v, thresholdOffEnd(direction, lo, hi)) ? undefined : v;

/** The lines' axes in Explore: the parameters, the objectives, the rank, the conditions' worst cases. */
export function exploreAxes(a: Answer, d: Draft, params: string[]): string[] {
  const have = new Set(a.sets.map((c) => c.name));
  return [...params, ...d.objectives.map((_, k) => objectiveCol(k)), ...(d.objectives.length ? ["#rank"] : []),
    ...d.conditions.map((_, i) => `#c${i}.worst`)].filter((c) => have.has(c));
}

/** The draft's limits as the plot's filter marks (drawn only: Explore's own mask decides what is left). */
export const limitMarks = (d: Draft): Record<string, Filter> =>
  Object.fromEntries(Object.entries(d.limits).map(([p, r]) => [p, { kind: "ranges", ranges: [r] } as Filter]));

/** S23: the study as Explore's draft makes it - for the existing plot, table and exports to draw
 *  instead of the goal's view, without a copy of them. The answer is the draft structure's, with
 *  #holds = the sets left, #rank = their order (and the score and Pareto front of what is left);
 *  the question is the draft saved as a goal (so an export's own columns say what Explore said);
 *  the view keeps the table's choices but none of the goal's filters or keep / exclude steps.
 *  Nothing here is stored: leaving Explore shows the goal's own view again. */
export function draftStudy(s: Study, d: Draft, a: Answer, ex: Explored, ranges: Record<string, [number, number]>, axes: string[]): Study {
  const n = ex.n;
  const holds = new Float32Array(n), rank = new Float32Array(n).fill(NaN);
  for (const i of ex.survivors) holds[i] = 1;
  if (d.objectives.length) ex.ranked.forEach((i, r) => { rank[i] = r + 1; });
  const several = d.objectives.length > 1;
  const swap = (c: Col): Col => {
    if (c.name === "#holds") return { ...c, values: holds };
    if (c.name === "#rank") return { ...c, values: rank };
    if (several && c.name === "#score") { const v = new Float32Array(n).fill(NaN); for (const i of ex.survivors) v[i] = ex.value.get(i) ?? NaN; return { ...c, values: v }; }
    if (several && c.name === "#pareto") { const v = new Float32Array(n); for (const i of ex.front) v[i] = 1; return { ...c, values: v }; }
    return c;
  };
  // an "or" goal cannot say limits or thresholds: its export says the conditions only (the rows are still what is left)
  const saved = needsAnd(d, ranges) ? { ...d, limits: {}, objectives: d.objectives.map(({ column, direction, weight }) => ({ column, direction, weight })) } : d;
  const goal = goalOfDraft(saved, s.question.goals[s.question.active]?.name ?? "", ranges);
  return { ...s,
    answer: { ...a, sets: a.sets.map(swap), counts: { ...a.counts, holding: ex.survivors.length } },
    question: materialize({ ...s.question, goals: [goal], active: 0 }),
    view: { ...s.view, mode: "sets", axes, filters: {}, onlyHolding: true, scope: { key: "", steps: [] } } };
}
