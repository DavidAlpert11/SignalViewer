import { useApp } from "./state";

/* Inspector: starts closed, opens by itself when there is something to show (a selected
   signal, the cursor). Once the user opens / closes it with its button, that choice is kept
   and the automatic opening stops. */
const INSPECTOR_KEY = "sv3.inspector";
export function inspectorPref(): "open" | "closed" | null {
  try { const v = localStorage.getItem(INSPECTOR_KEY); return v === "open" || v === "closed" ? v : null; }
  catch { return null; }
}
export function setInspectorByUser(open: boolean) {
  try { localStorage.setItem(INSPECTOR_KEY, open ? "open" : "closed"); } catch { /* private mode */ }
  useApp.setState({ inspectorOpen: open });
}
/** Open the Inspector for the cursor values - unless the user has closed it on purpose. */
export function revealInspector() {
  if (!useApp.getState().inspectorOpen && inspectorPref() !== "closed") useApp.setState({ inspectorOpen: true });
}
