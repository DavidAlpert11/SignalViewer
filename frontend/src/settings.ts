/* T18: the user's settings - theme, text size, language, how time is written, the Inspector, live
   mode's defaults. Kept with prefs.ts (in ~/.signalviewer), so they stay from one start to the next
   and a session file opened later does not change them. */
import { useApp } from "./store";
import { inspectorPref } from "./store/inspector";
import { getPrefValue, setPref } from "./prefs";

const KEYS = ["theme", "lang", "uiScale", "timeFormat", "liveAutoStop", "liveNewFiles"] as const;
type Key = (typeof KEYS)[number];

const VALID: Record<Key, (v: unknown) => boolean> = {
  theme: (v) => v === "light" || v === "dark",
  lang: (v) => v === "en" || v === "he",
  uiScale: (v) => v === 1 || v === 1.12 || v === 1.25,
  timeFormat: (v) => v === "seconds" || v === "clock",
  liveAutoStop: (v) => v === null || typeof v === "number",
  liveNewFiles: (v) => v === "ask" || v === "auto" || v === "ignore",
};

/** True when the user has chosen this setting (a session file then leaves it alone). */
export function hasSetting(key: Key): boolean {
  return getPrefValue(key) !== undefined;
}

/** After loadPrefs: the saved settings into the app, and every later change back into them. */
export function applySettings(): void {
  const set: Record<string, unknown> = {};
  for (const k of KEYS) {
    const v = getPrefValue(k);
    if (v !== undefined && VALID[k](v)) set[k] = v;
  }
  const insp = inspectorPref();
  if (insp) set.inspectorOpen = insp === "open";
  useApp.setState(set);
  useApp.subscribe((s, prev) => {
    for (const k of KEYS) if (s[k] !== prev[k]) setPref(k, s[k] as unknown);
  });
}
