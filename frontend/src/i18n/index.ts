import { useApp } from "../store";
import { swEn, swHe } from "../sweeps/i18n";
import * as templates from "./templates";
import * as flightlog from "./flightlog";
import * as investigate from "./investigate";
import * as compare from "./compare";
import * as mapsAnd3d from "./mapsAnd3d";
import * as files from "./files";
import * as liveAndFleet from "./liveAndFleet";
import * as app from "./app";
import * as signals from "./signals";
import * as plots from "./plots";
import * as common from "./common";
// the welcome / first minute, and Sweeps -> Common parameters (merged from the 2026-11-13 round's lane modules)
import * as welcome from "./welcome";
import * as study from "./study";

export type Lang = "en" | "he";

/* A2: the texts live by area in i18n/*.ts (each with en and he); here they are merged - the Sweeps
   area's own (sweeps/i18n.ts) first, as before. */
const en = { ...swEn, ...templates.en, ...flightlog.en, ...investigate.en, ...compare.en, ...mapsAnd3d.en, ...files.en, ...liveAndFleet.en, ...app.en, ...signals.en, ...plots.en, ...common.en,
  ...welcome.en, ...study.en };
const he: typeof en = { ...swHe, ...templates.he, ...flightlog.he, ...investigate.he, ...compare.he, ...mapsAnd3d.he, ...files.he, ...liveAndFleet.he, ...app.he, ...signals.he, ...plots.he, ...common.he,
  ...welcome.he, ...study.he };

export const dictionaries = { en, he };
export type TKey = keyof typeof en;

export function translate(lang: Lang, key: TKey, vars?: Record<string, string | number>): string {
  let s = dictionaries[lang][key] ?? dictionaries.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
  return s;
}

/** What useT() returns: a key (and its {vars}) to text in the current language. */
export type TFn = (key: TKey, vars?: Record<string, string | number>) => string;

export function useT(): TFn {
  const lang = useApp((s) => s.lang);
  return (key: TKey, vars?: Record<string, string | number>) => translate(lang, key, vars);
}

export function fmtNum(v: number | null | undefined, lang: Lang, digits = 5): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  const a = Math.abs(v);
  if (a !== 0 && (a >= 1e6 || a < 1e-3)) return v.toExponential(3);
  return v.toLocaleString(lang === "he" ? "he-IL" : "en-US", { maximumSignificantDigits: digits });
}

export function fmtInt(v: number, lang: Lang): string {
  return v.toLocaleString(lang === "he" ? "he-IL" : "en-US");
}
