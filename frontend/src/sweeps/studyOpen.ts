/* W14 / W18: a study file to open in the Sweeps area's *Common parameters* panel, asked from outside the
   area (the welcome screen's cards, a file opened from outside). The panel takes it when it shows. */
import { useApp } from "../store";

let pending: { path: string; demo: boolean } | null = null;
const listeners = new Set<() => void>();

/** Open this .svstudy.json in Sweeps → Common parameters (demo: the smart-sweep demo's view). */
export function requestStudy(path: string, demo = false): void {
  pending = { path, demo };
  useApp.setState({ area: "sweeps" });
  for (const f of listeners) f();
}

/** The study asked for, once (the panel calls it when it mounts and when told). */
export function takeStudy(): { path: string; demo: boolean } | null {
  const p = pending;
  pending = null;
  return p;
}

export function onStudyRequest(f: () => void): () => void {
  listeners.add(f);
  return () => { listeners.delete(f); };
}
