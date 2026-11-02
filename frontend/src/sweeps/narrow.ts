/* The Sweeps area in a narrow window (owner, 2026-11-02): below NARROW_PX the steps' side panel
   folds into a panel over the middle, opened with its button (StepNav). */
import { useEffect, useState } from "react";
import { useSweeps } from "./state";

/** A window narrower than this: the side panel folds into a panel opened with its button. */
export const NARROW_PX = 900;
export function useNarrow(): boolean {
  const q = `(max-width: ${NARROW_PX - 1}px)`;
  const [narrow, setNarrow] = useState(() => window.matchMedia?.(q).matches ?? false);
  useEffect(() => {
    const m = window.matchMedia?.(q);
    if (!m) return;
    const on = () => setNarrow(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, [q]);
  return narrow;
}
/** the side panel is hidden now: by choice in a wide window, until opened in a narrow one */
export function useLeftHidden(): boolean {
  const narrow = useNarrow();
  const hidden = useSweeps((s) => s.leftHidden);
  const narrowOpen = useSweeps((s) => s.narrowOpen);
  return narrow ? !narrowOpen : hidden;
}

