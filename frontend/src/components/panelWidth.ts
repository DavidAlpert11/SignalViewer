/* A side panel's width, remembered in the settings (PanelResizer.tsx drags it). */
import { useEffect, useState } from "react";
import { getPref, setPref } from "../prefs";

export const MIN_PANEL = 200;

function loadWidth(key: string, def: number): number {
  const v = Number(getPref(`sv3.w.${key}`));
  return v >= MIN_PANEL && v <= 1400 ? v : def;
}

/** A panel's width, kept in the settings under `sv3.w.<key>` (the keys Recordings always used). */
export function usePanelWidth(key: string, def: number): [number, (w: number) => void] {
  const [w, setW] = useState(() => loadWidth(key, def));
  useEffect(() => { setPref(`sv3.w.${key}`, Math.round(w)); }, [key, w]);
  return [w, setW];
}
