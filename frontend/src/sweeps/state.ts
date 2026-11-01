/* The Sweeps area's own store - apart from the Recordings workspace (`useApp().ws`): nothing here
   goes into sessions, templates, undo or the Recordings autosave (areas.ts, step 3).

   A study = one open table: its columns (role and scale - guessed, then the user's), the question
   (must hold across, goal, conditions, new columns), how it is shown (the view) and the answer.
   Every change to the roles or the question asks the server again (debounced); a change to the
   view only redraws. */
import { create } from "zustand";
import { getPrefValue, setPref } from "../prefs";
import { sweepApi, type Role, type Scale, type SweepColumn, type SweepOpened, type SweepSummary, type SweepTemplate, type WireQuestion } from "./api";
import { decodeCol } from "./decode";
import { emptyQuestion, emptyView, materialize, newGoal, upgradeQuestion, type Answer, type Condition, type Derived, type Filter, type GoalVariant, type Iteration, type LogEntry, type LogKind, type Question, type Tolerance, type View } from "./model";
import { changes, entry, withEntry, withIteration } from "./journal";

export interface StudyColumn extends SweepColumn {
  guessRole: Role;
  guessScale: Scale;
}

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
}

/** What undo brings back: the columns' roles and scales (by name), the question, and the parts of
 *  the view that change what is shown. Not where one is (step, tab, open set, map axes, follow). */
const UNDO_VIEW = ["mode", "axes", "colorBy", "filters", "reversed", "scales", "hideConstant", "hideFlat", "rerun", "onlyMissing", "scope",
  "onlyHolding", "tableColumns", "tableSort", "maps", "scatters"] as const;
type UndoView = Pick<View, (typeof UNDO_VIEW)[number]>;
export interface Snap { roles: Record<string, { role: Role; scale: Scale }>; question: Question; view: UndoView }
export interface History { past: Snap[]; future: Snap[]; kind: string; at: number }
const emptyHistory = (): History => ({ past: [], future: [], kind: "", at: 0 });
const UNDO_DEPTH = 100;
/** how many axes taken off are offered back (S15) */
const AXES_OFF_KEPT = 8;
/** changes of one kind closer than this make one undo step (a drag on an axis, typing a limit) */
const UNDO_MERGE_MS = 1000;
/** an action that changes two parts (a goal and its axis, a new column and its axis) is one step */
const UNDO_SAME_ACTION_MS = 50;

const snapOf = (s: Study): Snap => ({
  roles: Object.fromEntries(s.columns.map((c) => [c.name, { role: c.role, scale: c.scale }])),
  question: s.question,
  view: Object.fromEntries(UNDO_VIEW.map((k) => [k, s.view[k]])) as UndoView,
});
/** Which undoable parts differ between two states of a study ("" when none): the parts are
 *  immutable, so a changed part is a new object. */
function changedKind(a: Study, b: Study): string {
  const out: string[] = [];
  if (a.columns !== b.columns && a.columns.some((c, i) => c.role !== b.columns[i]?.role || c.scale !== b.columns[i]?.scale)) out.push("roles");
  if (a.question !== b.question) out.push("q");
  for (const k of UNDO_VIEW) if (a.view[k] !== b.view[k]) out.push(k);
  return out.join(",");
}
/** A study with a snapshot put back. */
function applySnap(s: Study, snap: Snap): Study {
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
}

interface SweepsState {
  studies: Study[];
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
  setLeftHidden: (hidden: boolean) => void;
  /** opening the studies of the last run again (autosave) */
  restoring: boolean;
  /** open the studies the app had open when it last ran; what could not be opened, and why */
  reopenLast: () => Promise<{ name: string; why: string }[]>;
  openRows: (name: string, columns: string[], rows: (string | number | null)[][]) => Promise<void>;
  saved: () => SavedStudy | null;
  merge: (path: string, prefer: "new" | "old" | "both") => Promise<{ added: number; replaced: number }>;
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
  applyTemplate: (name: string) => void;
  deleteTemplate: (name: string) => Promise<void>;
  /** a template from a file (exported here or by a colleague); its name as kept */
  importTemplate: (path: string) => Promise<string>;
  close: (i: number) => void;
  // undo / redo of the active study
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
  /** a parameter's tolerance (null: not robust to it) */
  setRobust: (column: string, tol: Tolerance | null) => void;
  updateCondition: (i: number, patch: Partial<Condition>) => void;
  removeCondition: (i: number) => void;
  addDerived: (d: Derived) => void;
  removeDerived: (i: number) => void;
  // the view
  setView: (patch: Partial<View>) => void;
  setFilter: (column: string, f: Filter | null) => void;
  moveAxis: (from: number, to: number) => void;
  toggleAxis: (column: string, on: boolean) => void;
  /** the lines' axes, in order; those taken off are remembered to bring back (S15) */
  setAxes: (axes: string[]) => void;
  // the answer
  evaluate: () => void;
  exportRerun: (path: string) => Promise<{ path: string; rows: number }>;
}

/** The roles and scales the user gave a table with these column names, remembered for the next one. */
const memoryKey = (cols: SweepColumn[]) => {
  let h = 0;
  for (const ch of cols.map((c) => c.name).join("\u241f")) h = (Math.imul(h, 31) + ch.charCodeAt(0)) | 0;
  return `sv3.sweepColumns.${(h >>> 0).toString(36)}`;
};
const remember = (s: Study) =>
  setPref(memoryKey(s.columns), Object.fromEntries(s.columns.filter((c) => c.role !== c.guessRole || c.scale !== c.guessScale)
    .map((c) => [c.name, { role: c.role, scale: c.scale }])));

export function wireQuestion(s: Study): WireQuestion {
  const removed = new Set(s.question.removed);
  const roles = Object.fromEntries(s.columns.map((c) => [c.name, removed.has(c.name) ? "ignore" : c.role])) as Record<string, Role>;
  const outputs = s.columns.filter((c) => c.role === "output").map((c) => c.name)
    .concat(s.question.derived.filter((d) => d.kind === "row").map((d) => d.name));
  const q = s.question;
  return { roles, combine: q.combine, holdValues: q.holdValues, goal: q.goal, conditions: q.conditions, derived: q.derived,
    outputAgg: Object.fromEntries(outputs.map((o) => [o, q.outputAgg])), objectives: q.objectives, exclude: q.exclude,
    ...(q.robust && Object.keys(q.robust).length ? { robust: q.robust } : {}) };
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
  // the rank is always there, empty with nothing to optimize
  || (c.name === "#rank" && c.values.some((x) => Number.isFinite(x)))).map((c) => c.name);

function defaultAxes(a: Answer): string[] {
  const keep = a.sets.filter((c) => (c.group === "param" || c.group === "output" || c.group === "derived") && !c.constant);
  // the parameters, then outputs up to 8 axes in all: more is unreadable (add any with Columns),
  // then the optimization's
  const params = keep.filter((c) => c.group === "param").map((c) => c.name);
  const rest = keep.filter((c) => c.group !== "param").map((c) => c.name);
  return [...[...params, ...rest].slice(0, Math.max(8, params.length + 2)), ...optAxes(a)];
}

/** The axes with the optimization's columns that have just appeared (a goal or an objective just
 *  set) - not those the user took away while they were there. */
function withNewOptAxes(axes: string[], prev: Answer | null, a: Answer): string[] {
  if (!prev) return axes;
  const had = new Set(optAxes(prev));
  const add = optAxes(a).filter((n) => !had.has(n) && !axes.includes(n));
  return add.length ? [...axes, ...add] : axes;
}

/** A study as a .svsweep document (also what autosave keeps). */
export function savedOf(s: Study): SavedStudy {
  const { pinned: _p, ...view } = s.view;
  void _p;
  return { kind: "signalviewer-sweep", version: 1, path: s.path, columns: s.columns.map((c) => ({ name: c.name, role: c.role, scale: c.scale })),
    question: s.question, view, merged: s.merged, log: s.log, iterations: s.iterations };
}

let timer = 0;
let seq = 0;

export const useSweeps = create<SweepsState>((set, get) => {
  /** Change the active study. A change to its roles, question or what is shown is one undo step
   *  (consecutive changes of the same kind within UNDO_MERGE_MS are one) and goes into the journal
   *  (`as`: the action's own line instead of what changed); `track: false` is for what the app does
   *  by itself (answers, summaries, a re-read file). */
  const patch = (f: (s: Study) => Study, track = true, as?: LogEntry) => set((st) => ({ studies: st.studies.map((s, i) => {
    if (i !== st.active) return s;
    let n = f(s);
    if (!track || n === s) return n;
    const kind = changedKind(s, n);
    if (!kind) return n;
    // the journal: this action as one line (`as`), or what changed
    n = { ...n, log: (as ? [as] : changes(s, n)).reduce(withEntry, n.log) };
    const h = s.history, now = Date.now();
    // one step: the same kind of change again soon, or a second change made by the same action
    const same = h.past.length > 0 && ((kind === h.kind && now - h.at < UNDO_MERGE_MS) || now - h.at < UNDO_SAME_ACTION_MS);
    const past = same ? h.past : [...h.past, snapOf(s)].slice(-UNDO_DEPTH);
    return { ...n, history: { past, future: [], kind, at: now } };
  }) }));
  const forget = (x: Study): Study => ({ ...x, history: emptyHistory() });
  const ask = () => { window.clearTimeout(timer); timer = window.setTimeout(() => get().evaluate(), 200); };
  const patchQ = (f: (q: Question) => Question) => { patch((s) => ({ ...s, question: f(s.question) })); ask(); };
  /** change the active goal; the question's goal, conditions and objectives follow it */
  const patchG = (f: (g: GoalVariant) => GoalVariant) => patchQ((q) => {
    const goals = q.goals.map((g, i) => (i === q.active ? f(g) : g));
    return materialize({ ...q, goals });
  });
  const patchV = (f: (v: View) => View, again = false) => { patch((s) => ({ ...s, view: f(s.view) })); if (again) ask(); };
  const refreshSummary = () => {
    const s = get().studies[get().active];
    if (!s) return;
    sweepApi.summary(s.tableId, wireQuestion(s).roles)
      .then((summary) => patch((x) => (x.tableId === s.tableId ? { ...x, summary } : x), false))
      .catch((e) => set({ error: (e as Error).message }));
  };
  /** a table the server opened, as a new study: the user's remembered roles, or a saved study's */
  const add = (r: SweepOpened, saved?: SavedStudy) => {
    const mem = getPrefValue<Record<string, { role: Role; scale: Scale }>>(memoryKey(r.columns)) ?? {};
    const from = saved ? Object.fromEntries(saved.columns.map((c) => [c.name, c])) : mem;
    const columns: StudyColumn[] = r.columns.map((c) => ({ ...c, guessRole: c.role, guessScale: c.scale,
      role: from[c.name]?.role ?? c.role, scale: from[c.name]?.scale ?? c.scale }));
    const study: Study = { tableId: r.id, path: r.path, name: r.name, rows: r.rows, seconds: r.seconds, columns,
      head: r.head, summary: r.summary,
      question: saved ? upgradeQuestion(saved.question) : emptyQuestion(),
      view: saved ? { ...emptyView(), ...saved.view, pinned: null } : emptyView(),
      answer: null, evaluating: false, evalError: "", changed: false, offer: null,
      sources: r.path ? [r.path.split(/[\\/]/).pop()!] : [r.name], merged: [], history: emptyHistory(),
      // a saved study goes on with its journal; a table opened now starts one
      // a saved study goes on with its journal; a table opened now starts an empty one (opening it
      // is not a step of the analysis: Where it comes from names the tables)
      log: saved?.log ?? [], iterations: saved?.iterations ?? [] };
    // the table always opens; with no parameter column yet, the columns come first - say which they are
    if (!columns.some((c) => c.role === "param")) study.view = { ...study.view, left: "columns" };
    if (!saved) study.offer = get().templates.find((t) => fits(t, columns))?.name ?? null;
    set((st) => ({ studies: [...st.studies, study], active: st.studies.length, busy: false }));
    if (Object.keys(from).length) refreshSummary();
    get().evaluate();
  };
  /** open a table as a new study (and merge what a saved study merged); throws what went wrong */
  const openOne = async (path: string, saved?: SavedStudy) => {
    if (!get().templates.length) await get().loadTemplates();
    const r = await sweepApi.open(path);
    add(r, saved);
    for (const m of saved?.merged ?? []) await get().merge(m.path, m.prefer);
  };
  return {
    studies: [],
    active: 0,
    busy: false,
    error: "",

    open: async (path, saved) => {
      set({ busy: true, error: "" });
      try { await openOne(path, saved); }
      catch (e) { set({ busy: false, error: (e as Error).message }); }
    },
    reportOpen: false,
    templatesOpen: false,
    leftHidden: getPrefValue<boolean>("sv3.swLeftHidden") === true,
    setLeftHidden: (hidden) => { setPref("sv3.swLeftHidden", hidden); set({ leftHidden: hidden }); },
    restoring: false,
    reopenLast: async () => {
      if (restoreStarted) return [];
      restoreStarted = true;
      const failed: { name: string; why: string }[] = [];
      set({ restoring: true, busy: true });
      try {
        const { state, damaged } = await sweepApi.autosave();
        if (damaged) failed.push({ name: damaged, why: "damaged" });
        const doc = state as AutosaveDoc | null;
        for (const s of doc?.studies ?? []) {
          try { await openOne(s.path, s); }
          catch (e) { failed.push({ name: s.path, why: (e as Error).message }); set({ busy: false }); }
        }
        if (doc && get().studies.length) set({ active: Math.max(0, Math.min(doc.active ?? 0, get().studies.length - 1)) });
      } catch { /* no autosave: start empty */ }
      // the studies opened again are not changes to undo
      set((st) => ({ restoring: false, busy: false, studies: st.studies.map((x) => ({ ...x, history: emptyHistory() })) }));
      restored = true;
      return failed;
    },
    openRows: async (name, columns, rows) => {
      set({ busy: true, error: "" });
      try { add(await sweepApi.openRows(name, columns, rows)); }
      catch (e) { set({ busy: false, error: (e as Error).message }); }
    },
    saved: () => { const s = get().studies[get().active]; return s ? savedOf(s) : null; },
    merge: async (path, prefer) => {
      const s = get().studies[get().active];
      const keys = s.columns.filter((c) => c.role === "param" || c.role === "hold").map((c) => c.name);
      const r = await sweepApi.merge(s.tableId, path, keys, prefer);
      const byName = new Map(s.columns.map((c) => [c.name, c]));
      const columns: StudyColumn[] = r.columns.map((c) => {
        const old = byName.get(c.name);
        return { ...c, guessRole: c.role, guessScale: c.scale, role: old?.role ?? c.role, scale: old?.scale ?? c.scale };
      });
      // the sets are numbered anew: what undo kept points at other sets
      patch((x) => (x.tableId !== s.tableId ? x : forget({ ...x, columns, rows: r.rows, head: r.head, sources: r.sources,
        merged: [...x.merged, { path, prefer }], view: { ...x.view, scope: { key: "", steps: [] }, pinned: null },
        log: withEntry(x.log, entry("merge", { name: path, added: r.added, replaced: r.replaced })) })), false);
      refreshSummary();
      get().evaluate();
      return { added: r.added, replaced: r.replaced };
    },
    unmerge: async (i) => {
      const s = get().studies[get().active];
      const m = s.merged[i - 1];
      if (!m) return;
      const r = await sweepApi.unmerge(s.tableId, m.path);
      const byName = new Map(s.columns.map((c) => [c.name, c]));
      const columns: StudyColumn[] = r.columns.map((c) => {
        const old = byName.get(c.name);
        return { ...c, guessRole: c.role, guessScale: c.scale, role: old?.role ?? c.role, scale: old?.scale ?? c.scale };
      });
      patch((x) => (x.tableId !== s.tableId ? x : forget({ ...x, columns, rows: r.rows, head: r.head, sources: r.sources,
        merged: x.merged.filter((_, j) => j !== i - 1), view: { ...x.view, scope: { key: "", steps: [] }, pinned: null },
        log: withEntry(x.log, entry("unmerge", { name: m.path })), iterations: x.iterations.filter((it) => it.n <= x.merged.length) })), false);
      refreshSummary();
      get().evaluate();
    },
    narrow: (kind, sets, key) => patchV((v) => ({ ...v, filters: {}, pinned: null,
      scope: { key, steps: [...(v.scope.key === key ? v.scope.steps : []), { kind, sets }] } })),
    journal: (kind, args) => patch((x) => ({ ...x, log: withEntry(x.log, entry(kind, args)) }), false),
    hideJournalLine: (at, hidden) => patch((x) => ({ ...x, log: x.log.map((e) => (e.at === at ? { ...e, hidden } : e)) }), false),
    resetStudy: () => {
      patch((s) => ({ ...s, question: emptyQuestion(), view: emptyView(), columns: s.columns.map((c) => ({ ...c, role: c.guessRole, scale: c.guessScale })) }), true, entry("reset"));
      refreshSummary();
      get().evaluate();
    },
    restore: (all) => patchV((v) => ({ ...v, scope: { ...v.scope, steps: all ? [] : v.scope.steps.slice(0, -1) } })),
    reload: async () => {
      const s = get().studies[get().active];
      if (!s) return;
      try {
        const r = await sweepApi.reload(s.tableId);
        // the roles stay the user's; new columns get their guess
        const byName = new Map(s.columns.map((c) => [c.name, c]));
        const columns: StudyColumn[] = r.columns.map((c) => {
          const old = byName.get(c.name);
          return { ...c, guessRole: c.role, guessScale: c.scale, role: old?.role ?? c.role, scale: old?.scale ?? c.scale };
        });
        patch((x) => (x.tableId !== s.tableId ? x : { ...x, columns, rows: r.rows, head: r.head, seconds: r.seconds, changed: false }), false);
        refreshSummary();
        get().evaluate();
      } catch (e) { set({ error: (e as Error).message }); }
    },
    checkChanged: async () => {
      const s = get().studies[get().active];
      if (!s || !s.path) return;
      try {
        const r = await sweepApi.changed(s.tableId);
        if (!r.changed) return;
        if (s.view.follow) await get().reload();
        else if (!s.changed) patch((x) => (x.tableId === s.tableId ? { ...x, changed: true } : x), false);
      } catch { /* the table was dropped on the server: nothing to follow */ }
    },

    templates: [],
    loadTemplates: async () => { try { set({ templates: (await sweepApi.templates()).templates }); } catch { /* none */ } },
    saveTemplate: async (name) => {
      const s = get().studies[get().active];
      if (!s) return;
      // what belongs to this table's runs stays out: the open set, filters, re-runs, keep / exclude
      // (by set number), next runs' answer; their choices (what to explore, the kinds) are kept
      const { pinned: _p, filters: _f, rerun: _r, scope: _s, next, ...rest } = s.view;
      void _p; void _f; void _r; void _s;
      const view = { ...rest, ...(next ? { next: { focus: next.focus, kinds: next.kinds, budget: next.budget } } : {}) };
      const r = await sweepApi.saveTemplate(name, { columns: s.columns.map((c) => ({ name: c.name, role: c.role, scale: c.scale })),
        question: { ...s.question, exclude: [] }, view });
      set({ templates: r.templates });
      patch((x) => ({ ...x, offer: null }), false);
    },
    applyTemplate: (name) => {
      const t = get().templates.find((x) => x.name === name);
      if (!t) return;
      const roles = new Map(t.columns.map((c) => [c.name, c]));
      patch((s) => {
        const columns = s.columns.map((c) => { const r = roles.get(c.name); return r ? { ...c, role: r.role, scale: r.scale } : c; });
        const have = new Set(columns.map((c) => c.name));
        const q = { ...upgradeQuestion(t.question as Partial<Question>), exclude: [] };
        // keep only what this table can answer: conditions and goals on columns it has (or new columns)
        const derived = new Set(q.derived.map((d) => d.name));
        const ok = (c: string) => have.has(c) || derived.has(c);
        const question: Question = materialize({ ...q,
          goals: q.goals.map((g) => ({ ...g, conditions: g.conditions.filter((c) => ok(c.column)), optimize: g.optimize.filter((o) => ok(o.column)) })),
          removed: q.removed.filter((c) => have.has(c)),
          holdValues: Object.fromEntries(Object.entries(q.holdValues).filter(([k]) => have.has(k))),
          robust: q.robust && Object.fromEntries(Object.entries(q.robust).filter(([k]) => have.has(k))) });
        const n = { ...s, columns, question, view: { ...emptyView(), ...(t.view as Partial<View>), pinned: null, filters: {}, rerun: [] }, offer: null };
        remember(n);
        return n;
      }, true, entry("template", { name }));
      refreshSummary();
      get().evaluate();
    },
    importTemplate: async (path) => {
      const r = await sweepApi.importTemplate(path);
      set({ templates: r.templates });
      return r.name;
    },
    deleteTemplate: async (name) => { set({ templates: (await sweepApi.deleteTemplate(name)).templates }); },

    undo: () => {
      const s = get().studies[get().active];
      const snap = s?.history.past[s.history.past.length - 1];
      if (!snap) return;
      patch((x) => { const n = applySnap(x, snap); remember(n);
        return { ...n, history: { past: x.history.past.slice(0, -1), future: [...x.history.future, snapOf(x)], kind: "", at: 0 } }; }, false);
      refreshSummary();
      get().evaluate();
    },
    redo: () => {
      const s = get().studies[get().active];
      const snap = s?.history.future[s.history.future.length - 1];
      if (!snap) return;
      patch((x) => { const n = applySnap(x, snap); remember(n);
        return { ...n, history: { past: [...x.history.past, snapOf(x)], future: x.history.future.slice(0, -1), kind: "", at: 0 } }; }, false);
      refreshSummary();
      get().evaluate();
    },

    close: (i) => set((st) => ({ studies: st.studies.filter((_, j) => j !== i), active: Math.max(0, Math.min(st.active, st.studies.length - 2)) })),

    setRole: (column, role) => {
      patch((s) => { const n = { ...s, columns: s.columns.map((c) => (c.name === column ? { ...c, role } : c)) }; remember(n); return n; });
      refreshSummary();
      ask();
    },
    setScale: (column, scale) => patch((s) => {
      if (!s.columns.some((c) => c.name === column)) return { ...s, view: { ...s.view, scales: { ...s.view.scales, [column]: scale } } };
      if (s.view.scales[column]) { const scales = { ...s.view.scales }; delete scales[column]; s = { ...s, view: { ...s.view, scales } }; }
      const n = { ...s, columns: s.columns.map((c) => (c.name === column ? { ...c, scale } : c)) };
      remember(n);
      return n;
    }),
    resetRoles: () => {
      patch((s) => { const n = { ...s, columns: s.columns.map((c) => ({ ...c, role: c.guessRole, scale: c.guessScale })) }; remember(n); return n; });
      refreshSummary();
      ask();
    },

    setQuestion: (p) => {
      patchQ((q) => {
        const n = { ...q, ...p };
        if (p.goal !== undefined || p.objectives !== undefined) {
          const g = n.goals[n.active];
          const optimize = p.objectives !== undefined && p.objectives.length ? p.objectives
            : n.goal ? [{ ...n.goal, weight: 1 }, ...g.optimize.slice(1)] : g.optimize.slice(1);
          n.goals = n.goals.map((x, i) => (i === n.active ? { ...x, optimize } : x));
        }
        return materialize(n);
      });
      if (p.goal) patchV((v) => (v.axes.includes("#goal") ? v : { ...v, axes: [...v.axes, "#goal"], colorBy: v.colorBy ?? "#holds" }));
    },
    setHoldValues: (column, values) => patchQ((q) => ({ ...q, holdValues: { ...q.holdValues, [column]: values } })),
    addCondition: (c) => patchG((g) => ({ ...g, conditions: [...g.conditions, c] })),
    updateCondition: (i, p) => patchG((g) => ({ ...g, conditions: g.conditions.map((c, j) => (j === i ? { ...c, ...p } : c)) })),
    removeCondition: (i) => patchG((g) => ({ ...g, conditions: g.conditions.filter((_, j) => j !== i) })),
    updateGoal: (p) => patchG((g) => ({ ...g, ...p })),
    addGoal: (copy) => patchQ((q) => {
      const g = copy ? { ...q.goals[q.active], conditions: q.goals[q.active].conditions.map((c) => ({ ...c })) } : newGoal("");
      const goals = [...q.goals, { ...g, name: `${q.goals.length + 1}` }];
      return materialize({ ...q, goals, active: goals.length - 1 });
    }),
    removeGoal: (i) => patchQ((q) => {
      if (q.goals.length < 2) return materialize({ ...q, goals: [newGoal("1")], active: 0 });
      const goals = q.goals.filter((_, j) => j !== i);
      return materialize({ ...q, goals, active: Math.min(q.active === i ? 0 : q.active > i ? q.active - 1 : q.active, goals.length - 1) });
    }),
    setActiveGoal: (i) => patchQ((q) => materialize({ ...q, active: i })),
    setRemoved: (columns) => patchQ((q) => ({ ...q, removed: columns })),
    setRobust: (column, tol) => patchQ((q) => {
      const robust = { ...(q.robust ?? {}) };
      if (tol) robust[column] = tol; else delete robust[column];
      return { ...q, robust };
    }),
    addDerived: (d) => { patchQ((q) => ({ ...q, derived: [...q.derived, d] })); patchV((v) => ({ ...v, axes: [...v.axes, d.name] })); },
    removeDerived: (i) => patchQ((q) => ({ ...q, derived: q.derived.filter((_, j) => j !== i) })),

    setView: (p) => patchV((v) => ({ ...v, ...p }), p.mode !== undefined),
    setFilter: (column, f) => patchV((v) => {
      const filters = { ...v.filters };
      if (f) filters[column] = f; else delete filters[column];
      return { ...v, filters };
    }),
    moveAxis: (from, to) => patchV((v) => {
      const axes = [...v.axes];
      const [a] = axes.splice(from, 1);
      axes.splice(Math.max(0, Math.min(axes.length, to)), 0, a);
      return { ...v, axes };
    }),
    toggleAxis: (column, on) => get().setAxes(on ? [...(get().studies[get().active]?.view.axes ?? []).filter((a) => a !== column), column]
      : (get().studies[get().active]?.view.axes ?? []).filter((a) => a !== column)),
    setAxes: (axes) => patchV((v) => {
      const off = v.axes.filter((a) => !axes.includes(a));
      return { ...v, axes, axesOff: [...off, ...(v.axesOff ?? []).filter((a) => !axes.includes(a) && !off.includes(a))].slice(0, AXES_OFF_KEPT) };
    }),

    evaluate: () => {
      const s = get().studies[get().active];
      if (!s) return;
      const my = ++seq;
      patch((x) => ({ ...x, evaluating: true }), false);
      sweepApi.evaluate(s.tableId, wireQuestion(s), s.view.mode === "runs").then((w) => {
        if (my !== seq) return;
        const answer: Answer = { counts: w.counts, conditions: w.conditions, seconds: w.seconds,
          sets: w.sets.map((c) => decodeCol(c)),
          runs: w.runs && { ...w.runs, columns: w.runs.columns.map((c) => decodeCol(c, "run")) } };
        // the iteration (the tables merged so far) with this answer: how many hold, the best goal
        const rank = answer.sets.find((c) => c.name === "#rank")?.values, goalCol = answer.sets.find((c) => c.name === "#goal")?.values;
        let best: number | null = null;
        if (rank && goalCol) { let r0 = Infinity; for (let i = 0; i < rank.length; i++) if (rank[i] < r0) { r0 = rank[i]; best = goalCol[i]; } }
        patch((x) => (x.tableId !== s.tableId ? x : { ...x, answer, evaluating: false, evalError: "",
          iterations: withIteration(x.iterations, x, answer.counts.holding, answer.counts.sets, best),
          view: x.view.axes.length ? { ...x.view, axes: withNewOptAxes(x.view.axes, x.answer, answer) } : { ...x.view, axes: defaultAxes(answer) } }), false);
      }).catch((e) => {
        if (my !== seq) return;
        patch((x) => ({ ...x, evaluating: false, evalError: (e as Error).message }), false);
      });
    },
    exportRerun: (path) => {
      const s = get().studies[get().active];
      return sweepApi.exportRerun(s.tableId, wireQuestion(s), s.view.rerun, s.view.onlyMissing, path);
    },
  };
});

/* ------------------------------------------------------------------ autosave
   The open studies, as .svsweep documents, a moment after each change - only once the last ones
   were opened again (reopenLast), so an empty start never overwrites them. A table that was not read
   from a file (rows pasted from Recordings) cannot be opened again and is left out. */
interface AutosaveDoc { version: 1; active: number; studies: SavedStudy[] }
let restoreStarted = false;
let restored = false;
let lastSaved = "";
let saveTimer = 0;
useSweeps.subscribe((st, prev) => {
  if (!restored || (st.studies === prev.studies && st.active === prev.active)) return;
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
    const now = useSweeps.getState();
    const kept = now.studies.filter((s) => s.path);
    const doc: AutosaveDoc = { version: 1, active: Math.max(0, kept.indexOf(now.studies[now.active])), studies: kept.map(savedOf) };
    const text = JSON.stringify(doc);
    if (text === lastSaved) return;
    lastSaved = text;
    sweepApi.autosaveSave(doc).catch(() => { lastSaved = ""; });
  }, 800);
});

/** The active study (or undefined), for components. */
export const useStudy = () => useSweeps((s) => s.studies[s.active]);
