import type { RunInfo } from "./api";
import { fmtNum, type Lang } from "./i18n";
import { withUnit } from "./units";

/** File types the app opens (file dialogs, "choose the original", "locate"...). */
export const DATA_EXTS = [".csv", ".txt", ".tsv", ".dat", ".mat", ".bin", ".tlog", ".ulg", ".mcap", ".h5", ".hdf5", ".parquet", ".pq", ".asc", ".log"];
/** F34: the part of the run list that says "the data changed" - for the effects that fetch data.
 *  The versions come from the server: a reload or a live update of a file, a derived signal
 *  replaced under the same name, a Python operation whose code changed. */
export function runsDataKey(runs: RunInfo[]): string {
  return runs.map((r) => `${r.id}:${r.timeOffset}:${r.samples}:${r.signals.length}:${r.version ?? ""}`
    + (r.format === "derived" ? `:${r.signals.map((s) => s.version ?? "").join(",")}` : "")).join("|");
}

/** T60: the extensions of the user's own readers join the list (it is read wherever it is used). */
export function addDataExts(exts: string[]) {
  for (const e of exts) if (!DATA_EXTS.includes(e.toLowerCase())) DATA_EXTS.push(e.toLowerCase());
}
/** Flight-log formats: their own time per message, a Log panel, health checks. */
export const LOG_FORMATS = new Set(["bin", "tlog", "ulg"]);

/* ------------------------------------------------------------------ text values
   A signal with text values (a CSV column such as "IDLE" / "ARMED", an ArduPilot flight mode)
   holds integer codes; its `labels` map turns them back into text everywhere a value is shown. */

const cache = new WeakMap<RunInfo[], Map<string, Record<string, string> | undefined>>();

export function labelsOf(runs: RunInfo[], sig: string): Record<string, string> | undefined {
  let m = cache.get(runs);
  if (!m) { m = new Map(); cache.set(runs, m); }
  if (m.has(sig)) return m.get(sig);
  const rid = sig.slice(0, sig.indexOf("/"));
  const info = runs.find((r) => r.id === rid)?.signals.find((x) => x.id === sig);
  const l = info?.labels && Object.keys(info.labels).length ? info.labels : undefined;
  m.set(sig, l);
  return l;
}

/** The text of a code (unknown code: the number itself). */
export function labelText(labels: Record<string, string> | undefined, v: number | null | undefined): string | null {
  if (v === null || v === undefined || !Number.isFinite(v)) return null;
  if (labels && Number.isInteger(v) && labels[String(v)] !== undefined) return labels[String(v)];
  return null;
}

/** A value as shown to the user: its text for text signals, else the number with its unit. */
export function fmtValue(runs: RunInfo[], sig: string, v: number, lang: Lang, unit?: string | null, digits?: number): string {
  const txt = labelText(labelsOf(runs, sig), v);
  if (txt !== null) return txt;
  return withUnit(fmtNum(v, lang, digits), unit ?? null);
}

/* ------------------------------------------------------------------ state colours
   Distinct, calm colours that keep white or dark text readable; the same code always gets the
   same colour (in every plot and in the legend). */
const STATE_LIGHT = ["#4C78A8", "#F58518", "#54A24B", "#B279A2", "#E45756", "#72B7B2",
  "#9D755D", "#EECA3B", "#FF9DA6", "#79706E", "#2E86AB", "#A0CBE8"];
const STATE_DARK = ["#5B8FD0", "#F59A3D", "#62B85A", "#C08CC0", "#EA6B6A", "#7FCAC4",
  "#B08A70", "#E6C547", "#FFA8B2", "#9A918E", "#3E9CC4", "#A9D1EE"];

export function stateColor(code: number, theme: "light" | "dark"): string {
  const pal = theme === "dark" ? STATE_DARK : STATE_LIGHT;
  const i = ((Math.round(code) % pal.length) + pal.length) % pal.length;
  return pal[i];
}

/** Black or white text on a colour (WCAG contrast). */
export function inkOn(hex: string): string {
  const n = parseInt(hex.slice(1), 16);
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((c) => { const s = c / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; });
  const L = 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
  return (L + 0.05) / 0.05 > 1.05 / (L + 0.05) ? "#111418" : "#ffffff";
}
