/* The Sweeps area's own store - apart from the Recordings workspace (`useApp().ws`): nothing here
   goes into sessions, templates, undo or the Recordings autosave (areas.ts, step 3). */
import { create } from "zustand";
import { sweepApi, type Role, type Scale, type SweepColumn, type SweepSummary } from "./api";

export interface Study {
  /** the table on the server (it may have been dropped: open the path again) */
  tableId: string;
  path: string; name: string; rows: number; seconds: number;
  columns: SweepColumn[];
  head: (number | string | null)[][];
  summary: SweepSummary;
}

interface SweepsState {
  studies: Study[];
  active: number;
  busy: boolean;
  error: string;
  open: (path: string) => Promise<void>;
  setRole: (column: string, role: Role) => Promise<void>;
  setScale: (column: string, scale: Scale) => void;
  close: (i: number) => void;
}

const rolesOf = (s: Study) => Object.fromEntries(s.columns.map((c) => [c.name, c.role])) as Record<string, Role>;

export const useSweeps = create<SweepsState>((set, get) => {
  const patchActive = (f: (s: Study) => Study) =>
    set((st) => ({ studies: st.studies.map((s, i) => (i === st.active ? f(s) : s)) }));
  return {
    studies: [],
    active: 0,
    busy: false,
    error: "",
    open: async (path) => {
      set({ busy: true, error: "" });
      try {
        const r = await sweepApi.open(path);
        const study: Study = { tableId: r.id, path: r.path, name: r.name, rows: r.rows, seconds: r.seconds,
          columns: r.columns, head: r.head, summary: r.summary };
        set((st) => ({ studies: [...st.studies, study], active: st.studies.length, busy: false }));
      } catch (e) {
        set({ busy: false, error: (e as Error).message });
      }
    },
    setRole: async (column, role) => {
      patchActive((s) => ({ ...s, columns: s.columns.map((c) => (c.name === column ? { ...c, role } : c)) }));
      const s = get().studies[get().active];
      try {
        const summary = await sweepApi.summary(s.tableId, rolesOf(s));
        patchActive((x) => (x.tableId === s.tableId ? { ...x, summary } : x));
      } catch (e) {
        set({ error: (e as Error).message });
      }
    },
    setScale: (column, scale) =>
      patchActive((s) => ({ ...s, columns: s.columns.map((c) => (c.name === column ? { ...c, scale } : c)) })),
    close: (i) => set((st) => ({ studies: st.studies.filter((_, j) => j !== i), active: Math.max(0, Math.min(st.active, st.studies.length - 2)) })),
  };
});
