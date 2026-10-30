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
import { emptyQuestion, emptyView, type Answer, type Condition, type Derived, type Filter, type Question, type View } from "./model";

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
}

/** A study as saved (.svsweep): which table, the columns' roles and scales, the question and the view. */
export interface SavedStudy {
  kind: "signalviewer-sweep"; version: 1;
  path: string;
  columns: { name: string; role: Role; scale: Scale }[];
  question: Question;
  view: Omit<View, "pinned">;
}

interface SweepsState {
  studies: Study[];
  active: number;
  busy: boolean;
  error: string;
  open: (path: string, saved?: SavedStudy) => Promise<void>;
  openRows: (name: string, columns: string[], rows: (string | number | null)[][]) => Promise<void>;
  saved: () => SavedStudy | null;
  // the file
  reload: () => Promise<void>;
  checkChanged: () => Promise<void>;
  // templates
  templates: SweepTemplate[];
  loadTemplates: () => Promise<void>;
  saveTemplate: (name: string) => Promise<void>;
  applyTemplate: (name: string) => void;
  deleteTemplate: (name: string) => Promise<void>;
  close: (i: number) => void;
  // columns
  setRole: (column: string, role: Role) => void;
  setScale: (column: string, scale: Scale) => void;
  resetRoles: () => void;
  // the question
  setQuestion: (patch: Partial<Question>) => void;
  setHoldValues: (column: string, values: (string | number)[]) => void;
  addCondition: (c: Condition) => void;
  updateCondition: (i: number, patch: Partial<Condition>) => void;
  removeCondition: (i: number) => void;
  addDerived: (d: Derived) => void;
  removeDerived: (i: number) => void;
  // the view
  setView: (patch: Partial<View>) => void;
  setFilter: (column: string, f: Filter | null) => void;
  moveAxis: (from: number, to: number) => void;
  toggleAxis: (column: string, on: boolean) => void;
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
  const roles = Object.fromEntries(s.columns.map((c) => [c.name, c.role])) as Record<string, Role>;
  const outputs = s.columns.filter((c) => c.role === "output").map((c) => c.name)
    .concat(s.question.derived.filter((d) => d.kind === "row").map((d) => d.name));
  const q = s.question;
  return { roles, holdValues: q.holdValues, goal: q.goal, conditions: q.conditions, derived: q.derived,
    outputAgg: Object.fromEntries(outputs.map((o) => [o, q.outputAgg])), objectives: q.objectives, exclude: q.exclude };
}

/** A template fits a table that has every column it gives a role to (other columns may be there too). */
export const fits = (t: SweepTemplate, cols: { name: string }[]) => {
  const have = new Set(cols.map((c) => c.name));
  const used = t.columns.filter((c) => c.role === "param" || c.role === "hold" || c.role === "output");
  return used.length > 0 && used.every((c) => have.has(c.name));
};

/** The axes a new answer starts with: the parameters, then the outputs - none that tell nothing. */
function defaultAxes(a: Answer): string[] {
  const keep = a.sets.filter((c) => (c.group === "param" || c.group === "output" || c.group === "derived") && !c.constant);
  // the parameters, then outputs up to 8 axes in all: more is unreadable (add any with + axis)
  const params = keep.filter((c) => c.group === "param").map((c) => c.name);
  const rest = keep.filter((c) => c.group !== "param").map((c) => c.name);
  return [...params, ...rest].slice(0, Math.max(8, params.length + 2));
}

let timer = 0;
let seq = 0;

export const useSweeps = create<SweepsState>((set, get) => {
  const patch = (f: (s: Study) => Study) => set((st) => ({ studies: st.studies.map((s, i) => (i === st.active ? f(s) : s)) }));
  const ask = () => { window.clearTimeout(timer); timer = window.setTimeout(() => get().evaluate(), 200); };
  const patchQ = (f: (q: Question) => Question) => { patch((s) => ({ ...s, question: f(s.question) })); ask(); };
  const patchV = (f: (v: View) => View, again = false) => { patch((s) => ({ ...s, view: f(s.view) })); if (again) ask(); };
  const refreshSummary = () => {
    const s = get().studies[get().active];
    if (!s) return;
    sweepApi.summary(s.tableId, wireQuestion(s).roles)
      .then((summary) => patch((x) => (x.tableId === s.tableId ? { ...x, summary } : x)))
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
      question: saved ? { ...emptyQuestion(), ...saved.question } : emptyQuestion(),
      view: saved ? { ...emptyView(), ...saved.view, pinned: null } : emptyView(),
      answer: null, evaluating: false, evalError: "", changed: false, offer: null };
    // the table always opens; with no parameter column yet, the columns come first - say which they are
    if (!columns.some((c) => c.role === "param")) study.view = { ...study.view, left: "columns" };
    if (!saved) study.offer = get().templates.find((t) => fits(t, columns))?.name ?? null;
    set((st) => ({ studies: [...st.studies, study], active: st.studies.length, busy: false }));
    if (Object.keys(from).length) refreshSummary();
    get().evaluate();
  };
  return {
    studies: [],
    active: 0,
    busy: false,
    error: "",

    open: async (path, saved) => {
      set({ busy: true, error: "" });
      if (!get().templates.length) await get().loadTemplates();
      try {
        const r = await sweepApi.open(path);
        add(r, saved);
      } catch (e) {
        set({ busy: false, error: (e as Error).message });
      }
    },
    openRows: async (name, columns, rows) => {
      set({ busy: true, error: "" });
      try { add(await sweepApi.openRows(name, columns, rows)); }
      catch (e) { set({ busy: false, error: (e as Error).message }); }
    },
    saved: () => {
      const s = get().studies[get().active];
      if (!s) return null;
      const { pinned: _p, ...view } = s.view;
      void _p;
      return { kind: "signalviewer-sweep", version: 1, path: s.path, columns: s.columns.map((c) => ({ name: c.name, role: c.role, scale: c.scale })),
        question: s.question, view };
    },
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
        patch((x) => (x.tableId !== s.tableId ? x : { ...x, columns, rows: r.rows, head: r.head, seconds: r.seconds, changed: false }));
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
        else if (!s.changed) patch((x) => (x.tableId === s.tableId ? { ...x, changed: true } : x));
      } catch { /* the table was dropped on the server: nothing to follow */ }
    },

    templates: [],
    loadTemplates: async () => { try { set({ templates: (await sweepApi.templates()).templates }); } catch { /* none */ } },
    saveTemplate: async (name) => {
      const s = get().studies[get().active];
      if (!s) return;
      const { pinned: _p, filters: _f, rerun: _r, ...view } = s.view;
      void _p; void _f; void _r;
      const r = await sweepApi.saveTemplate(name, { columns: s.columns.map((c) => ({ name: c.name, role: c.role, scale: c.scale })),
        question: { ...s.question, exclude: [] }, view });
      set({ templates: r.templates });
      patch((x) => ({ ...x, offer: null }));
    },
    applyTemplate: (name) => {
      const t = get().templates.find((x) => x.name === name);
      if (!t) return;
      const roles = new Map(t.columns.map((c) => [c.name, c]));
      patch((s) => {
        const columns = s.columns.map((c) => { const r = roles.get(c.name); return r ? { ...c, role: r.role, scale: r.scale } : c; });
        const have = new Set(columns.map((c) => c.name));
        const q = { ...emptyQuestion(), ...(t.question as Partial<Question>), exclude: [] };
        // keep only what this table can answer: conditions and goals on columns it has (or new columns)
        const derived = new Set(q.derived.map((d) => d.name));
        const ok = (c: string) => have.has(c) || derived.has(c);
        const question: Question = { ...q, conditions: q.conditions.filter((c) => ok(c.column)),
          goal: q.goal && ok(q.goal.column) ? q.goal : null, objectives: q.objectives.filter((o) => ok(o.column)),
          holdValues: Object.fromEntries(Object.entries(q.holdValues).filter(([k]) => have.has(k))) };
        const n = { ...s, columns, question, view: { ...emptyView(), ...(t.view as Partial<View>), pinned: null, filters: {}, rerun: [] }, offer: null };
        remember(n);
        return n;
      });
      refreshSummary();
      get().evaluate();
    },
    deleteTemplate: async (name) => { set({ templates: (await sweepApi.deleteTemplate(name)).templates }); },

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
      patchQ((q) => ({ ...q, ...p }));
      if (p.goal) patchV((v) => (v.axes.includes("#goal") ? v : { ...v, axes: [...v.axes, "#goal"], colorBy: v.colorBy ?? "#holds" }));
    },
    setHoldValues: (column, values) => patchQ((q) => ({ ...q, holdValues: { ...q.holdValues, [column]: values } })),
    addCondition: (c) => patchQ((q) => ({ ...q, conditions: [...q.conditions, c] })),
    updateCondition: (i, p) => patchQ((q) => ({ ...q, conditions: q.conditions.map((c, j) => (j === i ? { ...c, ...p } : c)) })),
    removeCondition: (i) => patchQ((q) => ({ ...q, conditions: q.conditions.filter((_, j) => j !== i) })),
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
    toggleAxis: (column, on) => patchV((v) => ({ ...v, axes: on ? (v.axes.includes(column) ? v.axes : [...v.axes, column]) : v.axes.filter((a) => a !== column) })),

    evaluate: () => {
      const s = get().studies[get().active];
      if (!s) return;
      const my = ++seq;
      patch((x) => ({ ...x, evaluating: true }));
      sweepApi.evaluate(s.tableId, wireQuestion(s), s.view.mode === "runs").then((w) => {
        if (my !== seq) return;
        const answer: Answer = { counts: w.counts, conditions: w.conditions, seconds: w.seconds,
          sets: w.sets.map((c) => decodeCol(c)),
          runs: w.runs && { ...w.runs, columns: w.runs.columns.map((c) => decodeCol(c, "run")) } };
        patch((x) => (x.tableId !== s.tableId ? x : { ...x, answer, evaluating: false, evalError: "",
          view: x.view.axes.length ? x.view : { ...x.view, axes: defaultAxes(answer) } }));
      }).catch((e) => {
        if (my !== seq) return;
        patch((x) => ({ ...x, evaluating: false, evalError: (e as Error).message }));
      });
    },
    exportRerun: (path) => {
      const s = get().studies[get().active];
      return sweepApi.exportRerun(s.tableId, wireQuestion(s), s.view.rerun, s.view.onlyMissing, path);
    },
  };
});

/** The active study (or undefined), for components. */
export const useStudy = () => useSweeps((s) => s.studies[s.active]);
