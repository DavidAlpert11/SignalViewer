/* The workspace: everything the user arranges (tabs, plots, signal styling, notes). Every change goes
   through `commit`, which records it for Undo / Redo - the ONE way to change it (CLAUDE.md). */
import type { StoreApi } from "zustand";
import { clone, initialWorkspace, type Workspace } from "../model";
import type { Toast } from "../types";
import type { AppState } from "../state";

/** Toasts whose action undoes the LAST workspace change go away with the next change / undo / redo. */
const dropWsUndo = (ts: Toast[]) => (ts.some((t) => t.undoesWs) ? ts.filter((t) => !t.undoesWs) : ts);

export interface WorkspaceSlice {
  ws: Workspace;
  past: Workspace[];
  future: Workspace[];
  commit: (fn: (ws: Workspace) => Workspace) => void;
  undo: () => void;
  redo: () => void;
}

export const workspaceSlice = (set: StoreApi<AppState>["setState"], get: StoreApi<AppState>["getState"]): WorkspaceSlice => ({
  ws: initialWorkspace(),
  past: [],
  future: [],

  commit: (fn) => {
    const prev = get().ws;
    const next = fn(clone(prev));
    if (JSON.stringify(next) === JSON.stringify(prev)) return;
    set({ ws: next, past: [...get().past.slice(-99), prev], future: [], toasts: dropWsUndo(get().toasts) });
  },
  undo: () => {
    const { past, ws, future } = get();
    if (!past.length) return;
    set({ ws: past[past.length - 1], past: past.slice(0, -1), future: [ws, ...future], toasts: dropWsUndo(get().toasts) });
  },
  redo: () => {
    const { past, ws, future } = get();
    if (!future.length) return;
    set({ ws: future[0], future: future.slice(1), past: [...past, ws], toasts: dropWsUndo(get().toasts) });
  },
});
