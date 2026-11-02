/* The study's journal (S08): what was done, in order, for the report - the process, not only where
   it ended. Changes to the study are read off the difference between two states of it (patch in
   state.ts), so no action has to remember to write; what leaves the study (a file written, a report,
   suggestions) is written by the action. Consecutive changes of one kind to one thing (typing a
   limit, dragging...) are one line. Undo is not a change of its own. Words are rendered in the
   report's language (ReportDialog), from the kind and its arguments. */
import type { TFn, TKey } from "../i18n";
import type { Iteration, LogEntry, LogKind } from "./model";
import type { Study } from "./state";
import type { GoalVariant } from "./model";

/** changes of one kind to one thing closer than this are one line */
const MERGE_MS = 120_000;
/** the journal keeps this many lines (the oldest go) */
const MAX = 400;

export const entry = (kind: LogKind, args: Record<string, string | number> = {}): LogEntry => ({ at: new Date().toISOString(), kind, args });

/** The journal with one line more - or the last line replaced, when it is the same kind of change to
 *  the same thing a moment ago. */
export function withEntry(log: LogEntry[], e: LogEntry): LogEntry[] {
  const last = log[log.length - 1];
  if (last && last.kind === e.kind && (last.args.key ?? "") === (e.args.key ?? "") && Date.parse(e.at) - Date.parse(last.at) < MERGE_MS)
    return [...log.slice(0, -1), { ...e, at: last.at, args: e.args }];
  return [...log, e].slice(-MAX);
}

/** A goal in a line: its conditions and what it optimizes, in symbols (no language). */
export function goalText(g: GoalVariant): string {
  const conds = g.conditions.filter((c) => c.column).map((c) => `${c.column} ${c.op} ${c.value}`).join(g.combine === "or" ? " | " : " & ");
  const opt = g.optimize.map((o) => `${o.direction === "max" ? "↑" : "↓"}${o.column}${g.optimize.length > 1 ? `×${o.weight}` : ""}`).join(", ");
  return [conds, opt].filter(Boolean).join(" · ");
}

/** What changed between two states of a study, as journal lines. */
export function changes(a: Study, b: Study): LogEntry[] {
  const out: LogEntry[] = [];
  if (a.columns !== b.columns) {
    const was = new Map(a.columns.map((c) => [c.name, c.role]));
    const moved = b.columns.filter((c) => was.has(c.name) && was.get(c.name) !== c.role).map((c) => `${c.name}: ${was.get(c.name)} → ${c.role}`);
    if (moved.length) out.push(entry("roles", { key: "roles", list: moved.join(", ") }));
  }
  const qa = a.question, qb = b.question;
  if (qa !== qb) {
    if (qa.removed !== qb.removed) out.push(entry("clean", { key: "clean", n: qb.removed.length, list: qb.removed.join(", ") }));
    if (qa.holdValues !== qb.holdValues) out.push(entry("scenarios", { key: "scenarios" }));
    if (qa.derived !== qb.derived) out.push(entry("derived", { key: "derived", list: qb.derived.map((d) => (d.kind === "row" ? `${d.name} = ${d.expr}` : `${d.name} = ${d.op}(${d.column})`)).join(", ") || "-" }));
    // a goal by its name and its number (a goal with no name of its own is "Goal n" in the report's language)
    if (qa.goals.length < qb.goals.length) out.push(entry("goalAdd", { name: qb.goals[qb.goals.length - 1]?.name ?? "", goal: qb.goals.length }));
    else if (qa.goals.length > qb.goals.length) {
      const i = qa.goals.findIndex((g) => !qb.goals.includes(g));
      out.push(entry("goalRemove", { name: qa.goals[i]?.name ?? "", goal: i + 1 }));
    } else if (qa.goals !== qb.goals) {
      const g = qb.goals[qb.active];
      if (g) out.push(entry("goal", { key: `goal:${qb.active}`, name: g.name, goal: qb.active + 1, text: goalText(g) || "-" }));
    }
    if (qa.robust !== qb.robust) {
      const list = Object.entries(qb.robust ?? {}).map(([c, t]) => `${c} ± ${t.value}${t.mode === "pct" ? "%" : t.mode === "steps" ? " steps" : ""}`).join(", ");
      out.push(entry("robust", { key: "robust", list: list || "-" }));
    }
    if (qa.exclude !== qb.exclude) out.push(entry("excludeRuns", { key: "excludeRuns", n: qb.exclude.length }));
  }
  const sa = a.view.scope.steps, sb = b.view.scope.steps;
  if (sa !== sb) {
    if (sb.length > sa.length) { const st = sb[sb.length - 1]; out.push(entry(st.kind === "keep" ? "keep" : "exclude", { n: st.sets.length })); }
    else out.push(entry("scopeBack", { key: "scopeBack", n: sb.length }));
  }
  return out;
}

/** The iterations with the latest answer in: each table merged in starts one (1: the first table). */
export function withIteration(its: Iteration[], s: Study, holding: number, sets: number, best: number | null): Iteration[] {
  const n = Math.max(1, s.sources.length);
  const label = s.sources[n - 1] ?? s.sources[s.sources.length - 1] ?? String(n);
  const cur: Iteration = { n, label, at: new Date().toISOString(), sets, holding, best };
  const kept = its.filter((x) => x.n < n);
  return [...kept, cur];
}

const KEY: Record<LogKind, TKey> = {
  open: "swLogOpen", merge: "swLogMerge", unmerge: "swLogUnmerge", template: "swLogTemplate", reset: "swLogReset",
  roles: "swLogRoles", clean: "swLogClean", scenarios: "swLogScenarios", derived: "swLogDerived", goalAdd: "swLogGoalAdd",
  goalRemove: "swLogGoalRemove", goal: "swLogGoal", robust: "swLogRobust", excludeRuns: "swLogExcludeRuns", keep: "swLogKeep",
  exclude: "swLogExclude", scopeBack: "swLogScopeBack", suggest: "swLogSuggest", export: "swLogExport", report: "swLogReport",
};
const two = (n: number) => String(n).padStart(2, "0");

/** A journal line as read: its local time and what was done. */
export function journalLine(t: TFn, e: LogEntry): string {
  const d = new Date(e.at);
  const when = `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())} ${two(d.getHours())}:${two(d.getMinutes())}`;
  const args = { ...e.args };
  if (args.goal !== undefined) {                               // as the goals' tabs name it (goalName)
    const n = String(args.name ?? "");
    args.name = n && Number.isNaN(Number(n)) ? n : t("swGoalN", { n: args.goal });
  }
  return `${when} · ${t(KEY[e.kind], args)}`;
}

/* ------------------------------------------------------------------ the report's journal (S20)
   The final story: what the study ended up as, in the order it was done - each thing's last
   change (most lines hold the whole state then: a goal's text, the columns out, the tolerances),
   the roles as their net change, keep / exclude as the steps still standing, nothing before the
   last "start over" or the line marked "the analysis starts here". Files opened are not lines
   (Where it comes from names them). Lines hidden by hand are out in both views. */

/** The journal from where the analysis starts: after `start` (an entry's time), and after the
 *  last start over. */
function fromStart(log: LogEntry[], start?: string): LogEntry[] {
  let i = 0;
  log.forEach((e, k) => { if (e.kind === "reset") i = k; });
  if (start) { const k = log.findIndex((e) => e.at === start); if (k > i) i = k; }
  return log.slice(i);
}

/** The lines the report shows: everything (but what was hidden and the files opened), or the
 *  final story. */
export function reportJournal(log: LogEntry[], final: boolean, start?: string): LogEntry[] {
  const kept = fromStart(log, start).filter((e) => e.kind !== "open");
  if (!final) return kept.filter((e) => !e.hidden);
  // the last of each thing is found among every line - a hidden one too: hiding the last version of
  // a goal leaves the goal out, it does not bring back its version before
  // keep / exclude: the steps still standing after the ones undone
  const steps: LogEntry[] = [];
  for (const e of kept) {
    if (e.kind === "keep" || e.kind === "exclude") steps.push(e);
    else if (e.kind === "scopeBack") steps.length = Math.min(steps.length, Number(e.args.n) || 0);
  }
  // roles: each column's net change (a column set back to its role is no change)
  const roles = new Map<string, [string, string]>();
  let rolesAt: LogEntry | undefined;
  for (const e of kept.filter((x) => x.kind === "roles")) {
    rolesAt = e;
    for (const part of String(e.args.list).split(", ")) {
      const m = part.match(/^(.*): (\S+) → (\S+)$/);
      if (!m) continue;
      const was = roles.get(m[1]);
      roles.set(m[1], [was ? was[0] : m[2], m[3]]);
    }
  }
  const netRoles = [...roles].filter(([, [a, b]]) => a !== b).map(([c, [a, b]]) => `${c}: ${a} → ${b}`);
  // a goal deleted later: its lines go too
  const gone = new Set(kept.filter((e) => e.kind === "goalRemove").map((e) => String(e.args.name || e.args.goal)));
  const lastOf = new Map<string, LogEntry>();
  for (const e of kept) if (e.args.key !== undefined) lastOf.set(String(e.args.key), e);
  const out: LogEntry[] = [];
  for (const e of kept) {
    if (e.kind === "keep" || e.kind === "exclude") { if (steps.includes(e)) out.push(e); continue; }
    if (e.kind === "scopeBack" || e.kind === "goalAdd" || e.kind === "goalRemove") continue;
    if (e.kind === "roles") { if (e === rolesAt && netRoles.length) out.push({ ...e, args: { ...e.args, list: netRoles.join(", ") } }); continue; }
    if (e.kind === "goal" && gone.has(String(e.args.name || e.args.goal))) continue;
    if (e.args.key !== undefined && lastOf.get(String(e.args.key)) !== e) continue;
    // a thing that ended up as nothing (no tolerance, no column out, no run left out) is no step
    if (e.args.list === "-" || ((e.kind === "clean" || e.kind === "excludeRuns") && Number(e.args.n) === 0)) continue;
    out.push(e);
  }
  return out.filter((e) => !e.hidden);
}
