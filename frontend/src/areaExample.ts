/* Review (owner, 2026-11-13: a clear demo for everything): the welcome screen's cards for the Sweeps single
   table and the Fleet open their area on its example. The area takes the request when it shows (it is lazy:
   it may not be mounted yet) - the same hand-over as sweeps/studyOpen.ts. */
import { useApp } from "./store";

type Req = { area: "sweeps" | "fleet"; path: string };
let pending: Req | null = null;
const listeners = new Set<() => void>();

export function requestAreaExample(area: Req["area"], path: string): void {
  pending = { area, path };
  useApp.setState({ area });
  for (const f of listeners) f();
}

/** The example asked of this area, once. */
export function takeAreaExample(area: Req["area"]): string | null {
  if (!pending || pending.area !== area) return null;
  const p = pending.path;
  pending = null;
  return p;
}

export function onAreaExample(f: () => void): () => void {
  listeners.add(f);
  return () => { listeners.delete(f); };
}
