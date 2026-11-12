/* W10: ask before closing with unsaved changes. The work is unsaved while the workspace's revision differs
   from the one last saved to / opened from a session file (store/slices/workspace.ts). Autosave stays: this
   only asks whether to keep the work in a session file too.

   - In a browser tab: the browser's own "Leave site?" question (beforeunload - a page cannot word it).
   - In the app's window (pywebview): run.py asks the page before the window closes (`__svCloseRequest`); the
     page shows Save / Don't save / Cancel and closes the window itself through /api/window/close. */
import { useApp } from "./store";

export const isDirty = (s = useApp.getState()) => s.askBeforeClose && s.wsRev !== s.savedRev;

let allowClose = false;
/** what the window's close asks for; set by the dialog */
export const closeAsk = { open: false, listeners: new Set<() => void>() };

export function setCloseAsk(open: boolean): void {
  closeAsk.open = open;
  for (const f of closeAsk.listeners) f();
}

/** Close the app's window (the user chose) - nothing asks again. */
export async function closeNow(): Promise<void> {
  allowClose = true;
  try { await fetch("/api/window/close", { method: "POST" }); } catch { /* the browser tab: nothing to close */ }
}

export function installClosePrompt(): void {
  window.addEventListener("beforeunload", (e) => {
    if (allowClose || !isDirty()) return;
    e.preventDefault();
    e.returnValue = "";                                       // the old browsers' way to ask
  });
  // run.py: true = close now; false = the page asks first (and closes the window itself)
  (window as unknown as { __svCloseRequest: () => boolean }).__svCloseRequest = () => {
    if (allowClose || !isDirty()) return true;
    setCloseAsk(true);
    return false;
  };
  // the window keeps its own copy, so a close needs no round trip to the page while nothing is unsaved
  let last: boolean | null = null;
  useApp.subscribe((s) => {
    const d = isDirty(s);
    if (d === last) return;
    last = d;
    fetch("/api/window/dirty", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dirty: d }) }).catch(() => {});
  });
}
