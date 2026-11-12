/* The workspace: everything the user arranges (tabs, plots, signal styling, notes). Every change goes
   through `commit`, which records it for Undo / Redo - the ONE way to change it (CLAUDE.md). */
import type { StoreApi } from "zustand";
import { clone, initialWorkspace, type Workspace } from "../model";
import type { Toast } from "../types";
import type { AppState } from "../state";

/** Toasts whose action undoes the LAST workspace change go away with the next change / undo / redo. */
const dropWsUndo = (ts: Toast[]) => (ts.some((t) => t.undoesWs) ? ts.filter((t) => !t.undoesWs) : ts);

/* W10: every workspace a commit makes gets the next revision number; undo / redo bring back the revision
   of the workspace they restore. `savedRev` is the revision last saved to (or opened from) a session file:
   the work is unsaved while they differ - and saved again when Undo returns to that very workspace. */
let lastRev = 0;
const revOf = new WeakMap<Workspace, number>();
const rev = (ws: Workspace) => revOf.get(ws) ?? 0;

export interface WorkspaceSlice {
  ws: Workspace;
  past: Workspace[];
  future: Workspace[];
  /** W10: the revision of `ws` and the one last saved / opened */
  wsRev: number;
  savedRev: number;
  commit: (fn: (ws: Workspace) => Workspace) => void;
  undo: () => void;
  redo: () => void;
  /** W10: the workspace as it is now is in a session file (saved, or just opened) */
  markSaved: () => void;
}

export const workspaceSlice = (set: StoreApi<AppState>["setState"], get: StoreApi<AppState>["getState"]): WorkspaceSlice => ({
  ws: initialWorkspace(),
  past: [],
  future: [],
  wsRev: 0,
  savedRev: 0,

  commit: (fn) => {
    const prev = get().ws;
    const next = fn(clone(prev));
    if (JSON.stringify(next) === JSON.stringify(prev)) return;
    revOf.set(prev, get().wsRev);
    revOf.set(next, ++lastRev);
    set({ ws: next, wsRev: lastRev, past: [...get().past.slice(-99), prev], future: [], toasts: dropWsUndo(get().toasts) });
  },
  undo: () => {
    const { past, ws, future } = get();
    if (!past.length) return;
    revOf.set(ws, get().wsRev);
    const back = past[past.length - 1];
    set({ ws: back, wsRev: rev(back), past: past.slice(0, -1), future: [ws, ...future], toasts: dropWsUndo(get().toasts) });
  },
  redo: () => {
    const { past, ws, future } = get();
    if (!future.length) return;
    revOf.set(ws, get().wsRev);
    set({ ws: future[0], wsRev: rev(future[0]), future: future.slice(1), past: [...past, ws], toasts: dropWsUndo(get().toasts) });
  },
  markSaved: () => set({ savedRev: get().wsRev }),
});
