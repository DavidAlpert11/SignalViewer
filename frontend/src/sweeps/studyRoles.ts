/* C3: one vocabulary for a study (plan §4.4). The Sweeps area names a column's part by what it is on one
   table (param / hold / output / id / recording / ignore); the study file (svcore/study.py) by what it is
   across systems (shared / local / scenario / output / ignore). These map both ways, and the Goal step
   (a Question) writes a study table's `constraints` / `objective` / `aggregate` / `drop` - the one editor.
   What the study's engine cannot express (k of n combinations, robust to, several goals, weights...) stays
   the table's own and is listed as *this table only*. Pure functions: Vitest checks them on the examples. */
import type { Role as AreaRole } from "./api";
import type { Condition, Derived, Question } from "./model";
import { emptyQuestion, materialize, newGoal, OPS, upgradeQuestion } from "./model";
import type { Role as StudyRole, StudyTable } from "./studyTypes";

/** A column's study role from its area role. A parameter is *shared* unless the study has two systems or more
 *  and the column is not one of the shared ones (then it is this system's own: *local*). */
export function toStudyRole(r: AreaRole, opts: { shared?: boolean } = {}): StudyRole {
  if (r === "param") return opts.shared === false ? "local" : "shared";
  if (r === "hold") return "scenario";
  if (r === "output") return "output";
  return "ignore";
}

/** A column's area role from its study role; `was` keeps a finer area role the study has no word for (id,
 *  recording - both "ignore" in the study). */
export function toAreaRole(r: StudyRole, was?: AreaRole): AreaRole {
  if (r === "shared" || r === "local") return "param";
  if (r === "scenario") return "hold";
  if (r === "output") return "output";
  return was === "id" || was === "recording" ? was : "ignore";
}

export function studyRoles(area: Record<string, AreaRole>, shared?: string[]): Record<string, StudyRole> {
  const out: Record<string, StudyRole> = {};
  for (const [c, r] of Object.entries(area)) out[c] = toStudyRole(r, { shared: shared ? shared.includes(c) : true });
  return out;
}

export function areaRoles(study: Record<string, StudyRole>, was: Record<string, AreaRole> = {}): Record<string, AreaRole> {
  const out: Record<string, AreaRole> = { ...was };
  for (const [c, r] of Object.entries(study)) out[c] = toAreaRole(r, was[c]);
  return out;
}

// ------------------------------------------------------------------ the Goal step <-> the study table

/** What of a question the study cannot hold - shown as *this table only* in the Goal step. */
export type TableOnly = "atLeast" | "only" | "in" | "where" | "setColumn" | "name" | "or" | "objectives" | "rankBy"
  | "aggregate" | "robust" | "split" | "exclude" | "goals";

export interface GoalWrite {
  /** the study table's fields the question writes */
  patch: Pick<StudyTable, "constraints" | "objective" | "aggregate" | "drop">;
  /** what stayed the table's own (each kind once, in the order met) */
  tableOnly: TableOnly[];
  /** the active goal's conditions that were written (indices), the rest are this table's only */
  written: number[];
}

const IDENT = /^[A-Za-z_][A-Za-z0-9_]*$/;
const num = (v: number) => (Number.isInteger(v) ? String(v) : String(+v.toPrecision(12)));

function aggOf(q: Question, column: string): string {
  const a = q.outputAgg as unknown;
  if (a && typeof a === "object") return (a as Record<string, string>)[column] ?? "mean";
  return typeof a === "string" ? a : "mean";
}

/** The Goal step's question as the study table holds it. `values` are each scenario column's values (to
 *  write the kept ones as the ones left out). */
export function goalToStudy(question: Question, values: Record<string, (string | number)[]> = {}): GoalWrite {
  const q = materialize(question);
  const only: TableOnly[] = [];
  const say = (k: TableOnly) => { if (!only.includes(k)) only.push(k); };
  const rows = new Map<string, Derived>(q.derived.filter((d) => d.kind === "row").map((d) => [d.name, d]));
  const sets = new Set(q.derived.filter((d) => d.kind === "set").map((d) => d.name));
  // a column as the study's expressions read it (svcore/sweep/derived.py: names are identifiers); a per-set
  // column or a name that is not an identifier cannot be written
  const term = (c: string): string | null => {
    if (sets.has(c)) { say("setColumn"); return null; }
    const d = rows.get(c);
    if (d && d.kind === "row") return `(${d.expr})`;
    if (!IDENT.test(c)) { say("name"); return null; }
    return c;
  };
  const parts: string[] = [];
  const written: number[] = [];
  q.conditions.forEach((c, i) => {
    if (c.mode === "atLeast") return say("atLeast");
    if (c.mode === "only") return say("only");
    if (c.in) return say("in");
    if (c.where && Object.keys(c.where).length) return say("where");
    const t = term(c.column);
    if (t === null) return;
    parts.push(`${t} ${c.op} ${num(c.value)}`);
    written.push(i);
  });
  let constraints = parts;
  if (q.combine === "or" && q.conditions.length > 1) {
    // the study's constraints all hold together; "any of them" fits only when every one was written
    if (written.length === q.conditions.length) constraints = [parts.map((p) => `(${p})`).join(" or ")];
    else { say("or"); constraints = []; written.length = 0; }
  }
  let objective: StudyTable["objective"] = { expr: "", sense: "min" };
  let aggregate: StudyTable["aggregate"] = "worst";
  if (q.goal) {
    const t = term(q.goal.column);
    if (t !== null) {
      objective = { expr: t.startsWith("(") ? t.slice(1, -1) : t, sense: q.goal.direction };
      const a = aggOf(q, q.goal.column);
      const worst = q.goal.direction === "min" ? "max" : "min";
      if (a === "mean") aggregate = "mean";
      else if (a !== worst) say("aggregate");
    }
  }
  if (q.objectives.length >= 2) say("objectives");
  if (q.rankBy === "pareto") say("rankBy");
  if (q.robust && Object.keys(q.robust).length) say("robust");
  if (q.split) say("split");
  if (q.exclude.length) say("exclude");
  if (q.goals.length > 1) say("goals");
  const drop: Record<string, (string | number)[]> = {};
  for (const [c, kept] of Object.entries(q.holdValues)) {
    if (!kept?.length || !values[c]) continue;
    const out = values[c].filter((v) => !kept.some((k) => String(k) === String(v)));
    if (out.length) drop[c] = out;
  }
  return { patch: { constraints, objective, aggregate, drop }, tableOnly: only, written };
}

/** One condition read back from a constraint: `column op number` (also with the sides swapped). */
function parseCondition(part: string): Condition | null {
  const p = part.trim().replace(/^\((.*)\)$/, "$1").trim();
  const name = String.raw`([A-Za-z_][A-Za-z0-9_]*)`;
  const n = String.raw`(-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)`;
  const op = String.raw`(>=|<=|==|!=|>|<)`;
  let m = new RegExp(`^${name}\\s*${op}\\s*${n}$`).exec(p);
  if (m) return { column: m[1], op: m[2] as Condition["op"], value: +m[3], mode: "all" };
  m = new RegExp(`^${n}\\s*${op}\\s*${name}$`).exec(p);
  if (m) {
    const flip: Record<string, Condition["op"]> = { ">=": "<=", "<=": ">=", ">": "<", "<": ">", "==": "==", "!=": "!=" };
    return { column: m[3], op: flip[m[2]], value: +m[1], mode: "all" };
  }
  return null;
}

/** A constraint split at its top-level `and` (as the engine reports each part). */
export function splitAnd(expr: string): string[] {
  const out: string[] = [];
  let depth = 0, start = 0;
  for (let i = 0; i < expr.length; i++) {
    const ch = expr[i];
    if (ch === "(") depth++;
    else if (ch === ")") depth--;
    else if (depth === 0 && expr.startsWith(" and ", i)) {
      out.push(expr.slice(start, i).trim());
      start = i + 5;
      i += 4;
    }
  }
  out.push(expr.slice(start).trim());
  return out.filter(Boolean);
}

export interface GoalRead {
  question: Question;
  /** constraints the Goal step cannot show as conditions (kept in the study as they are) */
  unread: string[];
}

/** A study table's goal as the Goal step shows it. `base` keeps the table's own parts (this table only);
 *  `values`: each scenario column's values (to turn the ones left out into the kept ones). */
export function studyToGoal(t: Pick<StudyTable, "constraints" | "objective" | "aggregate" | "drop">, base?: Question,
  values: Record<string, (string | number)[]> = {}): GoalRead {
  const q = base ? upgradeQuestion(structuredClone(base)) : emptyQuestion();
  const unread: string[] = [];
  const conditions: Condition[] = [];
  for (const c of t.constraints ?? []) {
    for (const part of splitAnd(c)) {
      const cond = parseCondition(part);
      if (cond && OPS.includes(cond.op)) conditions.push(cond);
      else unread.push(part);
    }
  }
  const expr = (t.objective?.expr ?? "").trim();
  const sense = t.objective?.sense ?? "min";
  let derived = q.derived;
  let goalCol = "";
  if (expr) {
    if (IDENT.test(expr)) goalCol = expr;
    else {
      goalCol = "objective";
      derived = [...derived.filter((d) => d.name !== goalCol), { name: goalCol, kind: "row", expr }];
    }
  }
  const g = q.goals[q.active] ?? newGoal("1");
  // the table's own parts of the goal stay (k of n, among values, where ...); the written ones are replaced
  const own = g.conditions.filter((c) => c.mode !== "all" || c.in || (c.where && Object.keys(c.where).length));
  const optimize = goalCol ? [{ column: goalCol, direction: sense, weight: 1 }, ...g.optimize.slice(1)] : g.optimize.slice(1);
  const goals = q.goals.slice();
  goals[q.active] = { ...g, conditions: [...conditions, ...own], combine: "and", optimize };
  let outputAgg = q.outputAgg as unknown;
  if (goalCol) {
    const agg = t.aggregate === "mean" ? "mean" : sense === "min" ? "max" : "min";
    outputAgg = outputAgg && typeof outputAgg === "object" ? { ...(outputAgg as object), [goalCol]: agg } : agg;
  }
  const holdValues = { ...q.holdValues };
  for (const [c, out] of Object.entries(t.drop ?? {})) {
    if (!values[c]) continue;
    holdValues[c] = values[c].filter((v) => !out.some((o) => String(o) === String(v)));
  }
  for (const c of Object.keys(holdValues)) if (!(c in (t.drop ?? {})) && values[c]) delete holdValues[c];
  const question = materialize({ ...q, goals, derived, holdValues, outputAgg: outputAgg as Question["outputAgg"] });
  return { question, unread };
}
