/* T18 / F30: the user's settings and small remembered choices (panel widths, the file dialog's sort
   and folders, the Inspector, the MAVLink address...). Kept by the app in ~/.signalviewer/
   ui_settings.json: the browser's own storage is per address, and the app gets a new port at every
   start, so whatever was put there was forgotten at the next start.

   Read synchronously (getPref) from a copy loaded once before the UI starts (loadPrefs); writes go
   to that copy at once and to the app shortly after (one request for a burst of changes). */
import { api } from "./api";

let cache: Record<string, unknown> = {};
let pending: Record<string, unknown> = {};
let timer = 0;

export async function loadPrefs(): Promise<void> {
  try {
    cache = (await api.getSettings()).settings ?? {};
  } catch { cache = {}; }
  // the first start with this version: take what the browser still remembers (same port only)
  if (!cache.migrated) {
    const found: Record<string, unknown> = { migrated: true };
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith("sv3.") && !(k in cache)) found[k] = localStorage.getItem(k);
      }
    } catch { /* no storage */ }
    Object.assign(cache, found);
    pending = { ...pending, ...found };
    flushSoon();
  }
}

export function getPref(key: string): string | null {
  const v = cache[key];
  return v === undefined || v === null ? null : String(v);
}

export function getPrefValue<T>(key: string): T | undefined {
  return cache[key] as T | undefined;
}

export function setPref(key: string, value: unknown): void {
  if (cache[key] === value) return;
  if (value === null || value === undefined) delete cache[key]; else cache[key] = value;
  pending[key] = value ?? null;
  flushSoon();
}

function flushSoon() {
  window.clearTimeout(timer);
  timer = window.setTimeout(() => {
    const changes = pending;
    pending = {};
    api.putSettings(changes).catch(() => { pending = { ...changes, ...pending }; });
  }, 300);
}
