/* The Sweeps area's store, its parts before the store itself (UX5.5: split out of sweeps/state.ts as they were): the
   study file's state, a study's types (columns, tables, the saved form), Undo's snapshots and the pure helpers the store
   uses. sweeps/state.ts re-exports all of it - import from there. */
import type { Group } from "./groups";
import { getPrefValue, setPref } from "../prefs";
import type { MergeSpec, Role, Scale, SweepColumn, SweepOpened, SweepSummary, SweepTemplate, TableRecipe, WireQuestion } from "./api";
import { axesSpec, colourSpec, runSelection, type RunSelection } from "./selection";
import { useApp } from "../store";
import type { Answer, Condition, Derived, Filter, GoalVariant, Iteration, LogEntry, LogKind, Question, Tolerance, View } from "./model";
import type { CommonResult, DemoProgress, LauncherStatusResult, LauncherSubmitResult, LoopProgress, NextRunsResult, Study as StudyFile } from "./studyTypes";

/** The study file's part of the area (C4: one store) - Set up / Together / the loop / the demo, edited as the
 *  `.svstudy.json` it is saved to (studyStore.ts holds its actions). Its edits share the area's one Undo. */
export interface StudyPanelState {
  open: boolean;
  demo: boolean;
  path: string;
  study: StudyFile | null;
  saved: string;                      // the study as last saved / opened (JSON) - unsaved while different
  past: StudyFile[];
  future: StudyFile[];
  result: CommonResult | null;
  next: NextRunsResult | null;
  submit: LauncherSubmitResult | null;
  status: LauncherStatusResult | null;
  demoProgress: DemoProgress | null;
  loopProgress: LoopProgress | null;
  pinned: number | null;              // the ranked row opened
  busy: boolean;
  error: string;
  /** C6 *I have results*: what the backend guessed from the table (the values seen, for Set up) */
  guess?: import("./setup").FromTable | null;
  /** UI only: a round's file written after this (seconds) is marked *new* - set when the study opens or is first
   *  saved, raised when a round is opened (the loop rewrites the study file each round, so its own time cannot say) */
  seenAt?: number | null;
}
export const emptyCommon = (): StudyPanelState => ({ open: false, demo: false, path: "", study: null, saved: "", past: [], future: [], result: null,
  next: null, submit: null, status: null, demoProgress: null, loopProgress: null, pinned: null, busy: false, error: "", guess: null, seenAt: null });

/** What the middle of the area shows (C6; UI only, not undone): the *New study* choice, the study's problem
 *  definition, a table in its steps, Together (the study of several systems), the Next runs step (run - PLAN
 *  2026-11-16 §7a, flow.ts); "" = as before (the table, or the panel). */
export type Part = "" | "new" | "setup" | "table" | "together" | "about" | "run";   // about: a demo study's explanation (C9)

/** One Undo for the whole area (C4): which part each step was made in, oldest first - `"setup"` (the study
 *  file) or `"t:" + tableId` (a table's question, roles, view). Undo takes the newest and undoes it there. */
export const SETUP_KEY = "setup";
export const tableKey = (s: { tableId: string }) => "t:" + s.tableId;
export const ORDER_DEPTH = 200;
/** The study file's own steps (studyStore.ts registers them: they ask the backend again). */
export const setupHistory = { undo: (): boolean => false, redo: (): boolean => false };
export function registerSetupHistory(h: typeof setupHistory): void { Object.assign(setupHistory, h); }

export interface StudyColumn extends SweepColumn {
  guessRole: Role;
  guessScale: Scale;
}

/** A table of the study (the Data step, owner 2026-11-02): read from a file, or tables merged into
 *  a new one. Each stays apart; the steps after Data work on one of them (`Study.use`). */
export interface StudyTable {
  id: string;
  name: string;
  /** how it was made, to make it again when a saved study opens ({} for rows handed over) */
  recipe: TableRecipe | Record<string, never>;
  /** what the server said when it opened: the columns, the first rows, the shape */
  opened: SweepOpened;
  /** made by merging tables of the study */
  merged: boolean;
}

/** The files a table is read from (a merged table: its parts'), in order. */
export const recipeFiles = (r: StudyTable["recipe"]): string[] =>
  "merge" in r ? r.merge.parts.flatMap(recipeFiles) : "path" in r && r.path ? [r.path, ...(r.merged ?? []).map((m) => m.path)] : [];
const baseName = (p: string) => p.replace(/[\\/]+$/, "").split(/[\\/]/).pop() ?? p;

export interface Study {
  /** the table on the server (it may have been dropped: open the path again) */
  tableId: string;
  path: string; name: string; rows: number; seconds: number;
  columns: StudyColumn[];
  head: (number | string | null)[][];
  summary: SweepSummary;
  question: Question;
  view: View;
  answer: Answer | null;
  evaluating: boolean;
  evalError: string;
  /** the file changed on disk since it was read (and the study does not follow it) */
  changed: boolean;
  /** C11: the study file's table this file was opened as (its goal edited here is that table's) - not saved */
  studyTable?: string;
  /** FR5: rows handed over by the recordings side (a folder summed up, the Runs matrix): a row is a recording,
   *  not a run of a sweep - no runs to send, no next runs, "recordings" not "sets". Not saved (neither are the rows). */
  recordings?: boolean;
  /** a template whose columns this table has, offered when it opened */
  offer: string | null;
  /** the tables merged into this one, in order (their file names) */
  sources: string[];
  /** what was merged in, to merge it again when a saved study opens */
  merged: { path: string; prefer: "new" | "old" | "both" }[];
  /** undo / redo of this study (never saved) */
  history: History;
  /** what was done, in order (S08): the report's process */
  log: LogEntry[];
  /** the study after each table merged in: sets, holding, best (S08) */
  iterations: Iteration[];
  /** the tables of the study, each apart (the Data step); `tableId` above is tables[use]'s */
  tables: StudyTable[];
  use: number;
  /** the table in the Data step's middle, and those ticked to merge (ids) - not undone, not saved */
  shown: number;
  picked: string[];
  /** columns to check after a template was applied (new to it: their role is a guess) - UI only */
  toCheck?: string[];
  /** new columns already seen in the Goal step's table (the others say "new") - UI only */
  goalSeen?: string[];
  /** FT9: the sets with a run that passes the filters made in All runs, as the server found them for `key`
   *  (sweeps/tabs.ts runsTabAsk) - not saved */
  runsTab?: { key: string; sets: number[]; runs: number };
}

/** What applying a template did (its summary to the user). */
export interface TemplateResult {
  matched: number; of: number; newColumns: string[];
  /** new columns of the template not made, and the column each one misses */
  skippedFormulas: { name: string; missing: string }[];
  /** goal limits / objectives on columns this table lacks */
  skippedLimits: number;
  /** the Split by condition, not a condition of this table */
  splitSkipped?: string;
}

const FORMULA_WORDS = new Set(["abs", "sqrt", "exp", "log", "log10", "sin", "cos", "tan", "atan2", "sign", "floor", "ceil", "round",
  "min", "max", "clip", "where", "isnan", "col", "pi", "e", "nan", "inf", "and", "or", "not"]);
/** The columns a formula reads (names and col("...")), as far as a quick look can tell. */
export function formulaColumns(expr: string): string[] {
  const out = new Set<string>();
  for (const m of expr.matchAll(/col\(\s*"([^"]*)"\s*\)|col\(\s*'([^']*)'\s*\)|"[^"]*"|'[^']*'|([A-Za-z_][A-Za-z0-9_]*)/g)) {
    const name = m[1] ?? m[2] ?? m[3];
    if (name !== undefined && !(m[3] !== undefined && FORMULA_WORDS.has(name))) out.add(name);
  }
  return [...out];
}

/** What undo brings back: the columns' roles and scales (by name), the question, and the parts of
 *  the view that change what is shown. Not where one is (step, tab, open set, map axes, follow). */
const UNDO_VIEW = ["mode", "axes", "colorBy", "filters", "filterTab", "reversed", "scales", "hideConstant", "hideFlat", "rerun", "rerunSplit", "onlyMissing", "scope",
  "onlyHolding", "show", "tableColumns", "tableSort", "maps", "scatters", "groups", "desk"] as const;
type UndoView = Pick<View, (typeof UNDO_VIEW)[number]>;
export interface Snap { roles: Record<string, { role: Role; scale: Scale }>; question: Question; view: UndoView }
export interface History { past: Snap[]; future: Snap[]; kind: string; at: number }
export const emptyHistory = (): History => ({ past: [], future: [], kind: "", at: 0 });
export const UNDO_DEPTH = 100;
/** how many axes taken off are offered back (S15) */
export const AXES_OFF_KEPT = 8;
/** changes of one kind closer than this make one undo step (a drag on an axis, typing a limit) */
export const UNDO_MERGE_MS = 1000;
/** an action that changes two parts (a goal and its axis, a new column and its axis) is one step */
export const UNDO_SAME_ACTION_MS = 50;

export const snapOf = (s: Study): Snap => ({
  roles: Object.fromEntries(s.columns.map((c) => [c.name, { role: c.role, scale: c.scale }])),
  question: s.question,
  view: Object.fromEntries(UNDO_VIEW.map((k) => [k, s.view[k]])) as UndoView,
});
/** Which undoable parts differ between two states of a study ("" when none): the parts are
 *  immutable, so a changed part is a new object. */
export function changedKind(a: Study, b: Study): string {
  const out: string[] = [];
  if (a.columns !== b.columns && a.columns.some((c, i) => c.role !== b.columns[i]?.role || c.scale !== b.columns[i]?.scale)) out.push("roles");
  if (a.question !== b.question) out.push("q");
  for (const k of UNDO_VIEW) if (a.view[k] !== b.view[k]) out.push(k);
  return out.join(",");
}
/** A study with a snapshot put back. */
export function applySnap(s: Study, snap: Snap): Study {
  return { ...s, columns: s.columns.map((c) => (snap.roles[c.name] ? { ...c, ...snap.roles[c.name] } : c)),
    question: snap.question, view: { ...s.view, ...snap.view } };
}

/** A study as saved (.svsweep): which table, the columns' roles and scales, the question and the view. */
export interface SavedStudy {
  kind: "signalviewer-sweep"; version: 1;
  path: string;
  columns: { name: string; role: Role; scale: Scale }[];
  question: Question;
  view: Omit<View, "pinned">;
  merged?: { path: string; prefer: "new" | "old" | "both" }[];
  log?: LogEntry[];
  iterations?: Iteration[];
  /** every table of the study (2026-11-02; older studies: `path` and `merged`), and the one the
   *  steps after Data work on */
  tables?: { name: string; recipe: TableRecipe }[];
  use?: number;
}

export interface SweepsState {
  studies: Study[];
  /** the study file's part (Set up, Together, the loop) - C4 */
  common: StudyPanelState;
  /** what the middle shows (C6) */
  part: Part;
  /** the one Undo's order of steps, and Redo's (see SETUP_KEY) */
  undoOrder: string[];
  redoOrder: string[];
  active: number;
  busy: boolean;
  error: string;
  open: (path: string, saved?: SavedStudy) => Promise<void>;
  /** the report dialog is open (the Study menu, Ctrl+K) */
  reportOpen: boolean;
  /** the templates dialog is open */
  templatesOpen: boolean;
  /** the steps' side panel is hidden (more room for the plot); remembered */
  leftHidden: boolean;
  /** the goal's "More options" open (for this session) */
  goalMore: boolean;
  setLeftHidden: (hidden: boolean) => void;
  /** a narrow window: the side panel opened over the middle (it starts folded) */
  narrowOpen: boolean;
  /** opening the studies of the last run again (autosave) */
  restoring: boolean;
  /** open the studies the app had open when it last ran; what could not be opened, and why */
  reopenLast: () => Promise<{ name: string; why: string }[]>;
  openRows: (name: string, columns: string[], rows: (string | number | null)[][]) => Promise<void>;
  saved: () => SavedStudy | null;
  merge: (path: string, prefer: "new" | "old" | "both") => Promise<{ added: number; replaced: number }>;
  /** the Data step: another table into the study, apart (not merged) */
  addTable: (path: string) => Promise<void>;
  /** the ticked tables merged into a new one (the tables merged stay) */
  mergeTables: (ids: string[], spec: MergeSpec) => Promise<void>;
  /** a table out of the study (the last one closes the study) */
  closeTable: (i: number) => void;
  /** the table the steps after Data work on */
  useTable: (i: number) => void;
  setShown: (i: number) => void;
  setPicked: (ids: string[]) => void;
  /** new columns touched in the Goal step's table: no longer "new" */
  seeInGoal: (names: string[]) => void;
  /** Split by: the condition whose values are studied apart (null: none), and the value shown */
  setSplit: (column: string | null) => void;
  setSplitValue: (v: string | number | null) => void;
  /** several columns' limits and what to optimize at once (the Goal step's bar) */
  setLimits: (cols: string[], p: { atLeast?: number | null; atMost?: number | null; optimize?: "" | "min" | "max" }, outputs: string[]) => void;
  /** the Data step: Table or Parallel plot - the same for every table (UI only) */
  dataTab: "table" | "plot";
  /** each table's parallel plot as it was left (axes, filters, colour, zoom): kept across the tabs */
  rawViews: Record<string, RawView>;
  /** FR5: a table's Data view asked to sort by a column and tick the rows with a value (a demo's button shows its
   *  answer so); taken once by the table (UI only) */
  rawAsk: { table: string; sort: { c: string; desc: boolean }; tick?: { col: string; value: string } } | null;
  setRawView: (id: string, v: RawView) => void;
  /** each parallel plot's zoom (a Data table's by its id, the results' as "res:" + id): UI only */
  zooms: Record<string, { k: number; x: number; y: number }>;
  setZoom: (key: string, z: { k: number; x: number; y: number }) => void;
  /** take the i-th merged table out again (1: the first one merged in) */
  unmerge: (i: number) => Promise<void>;
  narrow: (kind: "keep" | "exclude", sets: number[], key: string) => void;
  restore: (all: boolean) => void;
  /** the same table, the study from the start: no goals, nothing removed, the guessed roles */
  resetStudy: () => void;
  /** a step that leaves the study - a file written, a report, suggestions - into its journal */
  journal: (kind: LogKind, args?: Record<string, string | number>) => void;
  /** a journal line (by its time) out of the report, or back in */
  hideJournalLine: (at: string, hidden: boolean) => void;
  // the file
  reload: () => Promise<void>;
  checkChanged: () => Promise<void>;
  // templates
  templates: SweepTemplate[];
  loadTemplates: () => Promise<void>;
  saveTemplate: (name: string) => Promise<void>;
  applyTemplate: (name: string) => TemplateResult | null;
  deleteTemplate: (name: string) => Promise<void>;
  /** a template from a file (exported here or by a colleague); its name as kept */
  importTemplate: (path: string) => Promise<string>;
  close: (i: number) => void;
  // undo / redo: the newest step of the area, wherever it was made (a table's or the study file's)
  undo: () => void;
  redo: () => void;
  // columns
  setRole: (column: string, role: Role) => void;
  setScale: (column: string, scale: Scale) => void;
  resetRoles: () => void;
  // the question
  setQuestion: (patch: Partial<Question>) => void;
  setHoldValues: (column: string, values: (string | number)[]) => void;
  addCondition: (c: Condition) => void;
  updateGoal: (patch: Partial<GoalVariant>) => void;
  addGoal: (copy: boolean) => void;
  removeGoal: (i: number) => void;
  setActiveGoal: (i: number) => void;
  setRemoved: (columns: string[]) => void;
  /** S2: the table's own edits (display names, units, the runs kept, values fixed) - one Undo each */
  editTable: (patch: Partial<Pick<Question, "labels" | "units" | "rowFilter" | "cells">>) => void;
  /** a parameter's tolerance (null: not robust to it) */
  setRobust: (column: string, tol: Tolerance | null) => void;
  updateCondition: (i: number, patch: Partial<Condition>) => void;
  removeCondition: (i: number) => void;
  addDerived: (d: Derived) => void;
  removeDerived: (i: number) => void;
  /** a new column changed (its name, formula or operation) */
  replaceDerived: (i: number, d: Derived) => void;
  // the view
  setView: (patch: Partial<View>) => void;
  /** MF00: the brush (the axes' filters) as a new group - a live rule, or frozen ids */
  saveGroup: (frozen: boolean, name: string) => void;
  /** a group from a mask (∪ ∩ ∖ of two groups, the marked sets): frozen ids */
  addFrozenGroup: (name: string, mask: Uint8Array, source?: Group["source"]) => void;
  /** a group of these sets (their ids), frozen - one per value of a split condition */
  addIdsGroup: (name: string, ids: string[]) => void;
  /** a set to run again: as All together, or - a split value shown - for that value only */
  toggleRerun: (set: number) => void;
  editGroup: (id: string, patch: Partial<Pick<Group, "name" | "hidden" | "frozen">>) => void;
  removeGroup: (id: string) => void;
  setFilter: (column: string, f: Filter | null) => void;
  moveAxis: (from: number, to: number) => void;
  toggleAxis: (column: string, on: boolean) => void;
  /** the lines' axes, in order; those taken off are remembered to bring back (S15) */
  setAxes: (axes: string[]) => void;
  // the answer
  evaluate: () => void;
  /** All runs above the cap (1.29): the runs drawn again for the brush now (a sample of those it keeps) */
  refreshRuns: () => void;
  /** FT9: ask the server which sets have a run that passes the filters made in All runs (when there are some) */
  refreshRunsTab: () => void;
  /** the active table's summary (its parameters / scenarios / outputs) asked again - after its roles were set from outside */
  refreshSummary: () => void;
  exportRerun: (path: string) => Promise<{ path: string; rows: number }>;
}

/** A table's parallel plot in the Data step, as the user left it. */
/** FR5: the active table is a table of recordings, and no study file is open (a study's tables are runs). */
export const isRecordings = (s: { studies: Study[]; active: number; common: { open: boolean } }): boolean =>
  !!s.studies[s.active]?.recordings && !s.common.open;

export interface RawView {
  axes: string[]; filters: Record<string, Filter>; colorBy: string | null;
  scales: Record<string, Scale>; reversed: Record<string, boolean>;
  /** the run picked (a line clicked): marked in the Table too */
  picked?: number | null;
}

/** The roles and scales the user gave a table with these column names, remembered for the next one. */
export const memoryKey = (cols: SweepColumn[]) => {
  let h = 0;
  for (const ch of cols.map((c) => c.name).join("\u241f")) h = (Math.imul(h, 31) + ch.charCodeAt(0)) | 0;
  return `sv3.sweepColumns.${(h >>> 0).toString(36)}`;
};
export const remember = (s: Study) =>
  setPref(memoryKey(s.columns), Object.fromEntries(s.columns.filter((c) => c.role !== c.guessRole || c.scale !== c.guessScale)
    .map((c) => [c.name, { role: c.role, scale: c.scale }])));

export function wireQuestion(s: Study): WireQuestion {
  const removed = new Set(s.question.removed);
  const roles = Object.fromEntries(s.columns.map((c) => [c.name, removed.has(c.name) ? "ignore" : c.role])) as Record<string, Role>;
  const outputs = s.columns.filter((c) => c.role === "output").map((c) => c.name)
    .concat(s.question.derived.filter((d) => d.kind === "row").map((d) => d.name));
  const q = s.question;
  // Split by: one value of the split condition - the question for the runs with that value
  const sv = s.view.splitValue;
  const split = q.split && roles[q.split] === "hold" && sv !== undefined && sv !== null ? q.split : null;
  const holdValues = split ? { ...q.holdValues, [split]: [sv as string | number] } : q.holdValues;
  return { roles, combine: q.combine, holdValues, goal: q.goal, conditions: q.conditions, derived: q.derived,
    outputAgg: Object.fromEntries(outputs.map((o) => [o, q.outputAgg])), objectives: q.objectives, exclude: q.exclude,
    ...(q.robust && Object.keys(q.robust).length ? { robust: q.robust } : {}),
    ...(q.cells?.length ? { cells: q.cells } : {}), ...(q.rowFilter?.trim() ? { rowFilter: q.rowFilter.trim() } : {}),
    ...(q.objectives.length >= 2 && q.rankBy === "pareto" ? { rankBy: "pareto" as const } : {}) };
}

/** A template fits a table that has every column it gives a role to (other columns may be there too). */
export const fits = (t: SweepTemplate, cols: { name: string }[]) => {
  const have = new Set(cols.map((c) => c.name));
  const used = t.columns.filter((c) => c.role === "param" || c.role === "hold" || c.role === "output");
  return used.length > 0 && used.every((c) => have.has(c.name));
};

/** The axes a new answer starts with: the parameters, then the outputs - none that tell nothing. */
/** The optimization's axes (S19): the goal, the rank, the other objectives and the score - drag on
 *  them in the lines to keep the best and see their parameters. */
const optAxes = (a: Answer) => a.sets.filter((c) => c.name === "#goal" || c.name === "#score" || /^#obj\d+$/.test(c.name)
  // FT9: whether a set holds, an axis of its own (✓ / ✗) when the goal has conditions
  || (c.name === "#holds" && a.conditions.length > 0)
  // the rank is always there, empty with nothing to optimize
  || (c.name === "#rank" && c.values.some((x) => Number.isFinite(x)))).map((c) => c.name);

export function defaultAxes(a: Answer): string[] {
  const keep = a.sets.filter((c) => (c.group === "param" || c.group === "output" || c.group === "derived") && !c.constant);
  // the parameters, then outputs up to 8 axes in all: more is unreadable (add any with Columns),
  // then the optimization's
  const params = keep.filter((c) => c.group === "param").map((c) => c.name);
  const rest = keep.filter((c) => c.group !== "param").map((c) => c.name);
  return [...[...params, ...rest].slice(0, Math.max(8, params.length + 2)), ...optAxes(a)];
}

/** The axes with the optimization's columns that have just appeared (a goal or an objective just
 *  set) - not those the user took away while they were there. */
export function withNewOptAxes(axes: string[], prev: Answer | null, a: Answer): string[] {
  if (!prev) return axes;
  const had = new Set(optAxes(prev));
  const add = optAxes(a).filter((n) => !had.has(n) && !axes.includes(n));
  return add.length ? [...axes, ...add] : axes;
}

/** A study as a .svsweep document (also what autosave keeps). */
export function savedOf(s: Study): SavedStudy {
  const { pinned: _p, ...view } = s.view;
  void _p;
  // the tables that can be made again (rows handed over cannot)
  const kept = s.tables.filter((x) => recipeFiles(x.recipe).length);
  const use = Math.max(0, kept.indexOf(s.tables[s.use]));
  return { kind: "signalviewer-sweep", version: 1, path: s.path, columns: s.columns.map((c) => ({ name: c.name, role: c.role, scale: c.scale })),
    question: s.question, view, merged: s.merged, log: s.log, iterations: s.iterations,
    tables: kept.map((x) => ({ name: x.name, recipe: x.recipe as TableRecipe })), use };
}

/** A study working on another of its tables: the same question; the roles of columns it had kept
 *  (by name - `from`, else the study's), the others guessed; the sets are numbered anew. */
export function onTable(s: Study, i: number, from?: Record<string, { role: Role; scale: Scale }>): Study {
  const tb = s.tables[i], r = tb.opened;
  const by = from ?? Object.fromEntries(s.columns.map((c) => [c.name, { role: c.role, scale: c.scale }]));
  const mem = getPrefValue<Record<string, { role: Role; scale: Scale }>>(memoryKey(r.columns)) ?? {};
  const columns: StudyColumn[] = r.columns.map((c) => ({ ...c, guessRole: c.role, guessScale: c.scale,
    role: by[c.name]?.role ?? mem[c.name]?.role ?? c.role, scale: by[c.name]?.scale ?? mem[c.name]?.scale ?? c.scale }));
  const files = recipeFiles(tb.recipe).map(baseName);
  return { ...s, tableId: tb.id, use: i, rows: r.rows, head: r.head, summary: r.summary, seconds: r.seconds, columns,
    sources: files.length ? files : [tb.name], answer: null, changed: false,
    view: { ...s.view, scope: { key: "", steps: [] }, pinned: null }, history: emptyHistory() };
}

/** What All runs asks to draw: the Settings cap, the brush (sweeps/selection.ts), the open set; `key` says
 *  which brush a sample was taken for. */
export function drawOf(s: Study): DrawSpec {
  const { sweepLines: cap, sweepOver: over } = useApp.getState();
  const select = runSelection(s), pinned = s.view.pinned ?? null, axes = axesSpec(s), colour = colourSpec(s);
  return { cap, select, pinned, over, axes, colour, key: JSON.stringify([cap, over, select, pinned, axes, colour ?? null]) };
}
export interface DrawSpec {
  cap: number; select: RunSelection; pinned: number | null; over: "density" | "sample";
  axes: { column: string; scale: string }[]; colour?: { column?: string; sets?: number[]; n: number }; key: string;
}
