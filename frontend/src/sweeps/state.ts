/* The Sweeps area's own store - apart from the Recordings workspace (`useApp().ws`): nothing here
   goes into sessions, templates, undo or the Recordings autosave (areas.ts, step 3).

   A study = one open table: its columns (role and scale - guessed, then the user's), the question
   (must hold across, goal, conditions, new columns), how it is shown (the view) and the answer.
   Every change to the roles or the question asks the server again (debounced); a change to the
   view only redraws. */
import { create } from "zustand";
import { getPrefValue, setPref } from "../prefs";
import { sweepApi, type Role, type Scale, type SweepColumn, type SweepSummary, type WireQuestion } from "./api";
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
}

interface SweepsState {
  studies: Study[];
  active: number;
  busy: boolean;
  error: string;
  open: (path: string) => Promise<void>;
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
    outputAgg: Object.fromEntries(outputs.map((o) => [o, q.outputAgg])) };
}

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
  return {
    studies: [],
    active: 0,
    busy: false,
    error: "",

    open: async (path) => {
      set({ busy: true, error: "" });
      try {
        const r = await sweepApi.open(path);
        const mem = getPrefValue<Record<string, { role: Role; scale: Scale }>>(memoryKey(r.columns)) ?? {};
        const columns: StudyColumn[] = r.columns.map((c) => ({ ...c, guessRole: c.role, guessScale: c.scale,
          role: mem[c.name]?.role ?? c.role, scale: mem[c.name]?.scale ?? c.scale }));
        const study: Study = { tableId: r.id, path: r.path, name: r.name, rows: r.rows, seconds: r.seconds, columns,
          head: r.head, summary: r.summary, question: emptyQuestion(), view: emptyView(), answer: null, evaluating: false, evalError: "" };
        set((st) => ({ studies: [...st.studies, study], active: st.studies.length, busy: false }));
        if (Object.keys(mem).length) refreshSummary();
        get().evaluate();
      } catch (e) {
        set({ busy: false, error: (e as Error).message });
      }
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
