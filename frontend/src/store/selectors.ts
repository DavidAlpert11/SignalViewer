/* Reading the store: pure helpers over the workspace and the open files, and small helpers that
   put plots into a tab. No state of their own. */
import type { RunInfo } from "../api";
import { translate } from "../i18n";
import { dataRuns, runLabels } from "../names";
import { labelsOf } from "../values";
import { MAX_PLOTS, TRACE_COLORS, type Plot, type PlotSignal, type Tab, type Workspace } from "./model";
import { useApp } from "./state";
import type { CursorState, PickerRequest, PlayMode, Range } from "./types";

export const activeTab = (ws: Workspace) => ws.tabs.find((t) => t.id === ws.activeTab) ?? ws.tabs[0];
/** A plot emptied: its signals, X signal, map / 3D objects and what refers to them. */
export function emptyPlot(p: Plot) {
  p.signals = []; p.xSignal = null; p.objects = [];
  p.followObject = null; p.primaryObject = null; p.relatedObjects = []; p.ownTime = null;
}
/** A plot's references to objects it no longer has are dropped (follow, primary, related). */
export function forgetObjects(p: Plot) {
  const has = (id?: string | null) => !!id && (p.objects ?? []).some((o) => o.id === id);
  if (p.followObject && !has(p.followObject)) p.followObject = null;
  if (p.primaryObject && !has(p.primaryObject)) p.primaryObject = null;
  if (p.relatedObjects) p.relatedObjects = p.relatedObjects.filter(has);
}
export const findPlot = (ws: Workspace, id: string): Plot | undefined => {
  for (const t of ws.tabs) for (const p of t.plots) if (p.id === id) return p;
  return undefined;
};
/** A plot that shows something: signals, or objects on a map / in 3D. */
export const plotHasContent = (p: Plot) => p.signals.length > 0 || (p.objects?.length ?? 0) > 0;
export const tabHasContent = (t: Tab) => t.plots.some(plotHasContent);
export const rangeKey = (tab: Tab, plot: Plot) => (tab.linkX ? tab.id : plot.id);

/** The whole recording: earliest start to latest end of the open data files (time offsets included). */
export function recordingExtent(runs: RunInfo[]): Range | null {
  let lo = Infinity, hi = -Infinity;
  for (const r of runs) {
    if (r.format === "derived" || !Number.isFinite(r.start) || !Number.isFinite(r.end) || r.end <= r.start) continue;
    lo = Math.min(lo, r.start); hi = Math.max(hi, r.end);
  }
  return hi > lo ? [lo, hi] : null;
}

/** The part of time the plots show in the timeline's mode, or null for everything. */
export function shownSpan(s: { playMode: PlayMode; windowSec: number; cursor: CursorState }): Range | null {
  if (s.playMode === "cursor" || !s.cursor.on || s.cursor.t1 === null) return null;
  return s.playMode === "draw" ? [-Infinity, s.cursor.t1] : [s.cursor.t1 - Math.max(0.001, s.windowSec), s.cursor.t1];
}
export const yRangeKey = (tab: Tab, plot: Plot) => (tab.linkY ? `${tab.id}:y` : plot.id);

let _labelCache: { key: string; map: Map<string, string> } = { key: "", map: new Map() };
export function fileLabel(runs: RunInfo[], runId: string): string {
  const key = runs.map((r) => `${r.id}|${r.path}|${r.name}`).join(";");
  if (_labelCache.key !== key) _labelCache = { key, map: runLabels(runs) };
  return _labelCache.map.get(runId) ?? runs.find((r) => r.id === runId)?.name ?? runId;
}

/** Legend label: the file is named only when more than one DATA file is open
 *  (derived signals do not count), with as many parent folders as needed. */
export function signalName(runs: RunInfo[], sig: string, withFile = true): string {
  const [rid, ...rest] = sig.split("/");
  const name = rest.join("/");
  const run = runs.find((r) => r.id === rid);
  if (!run || run.format === "derived") return name;
  return withFile && dataRuns(runs).length > 1 ? `${name} · ${fileLabel(runs, rid)}` : name;
}

/** A signal as added to a plot. Text signals (states, flight modes) start as a state lane. */

/* ------------------------------------------------------------ file identity (T46) */
/** The colour and tag of the file a signal (or run id) belongs to; null for derived signals. */
export function fileMark(runs: RunInfo[], sigOrRun: string): { tag: string; color: string } | null {
  const rid = sigOrRun.split("/")[0];
  const r = runs.find((x) => x.id === rid);
  if (!r || r.format === "derived" || !r.color) return null;
  return { tag: r.tag ?? "", color: r.color };
}

/** Tags are shown only when they tell files apart: two or more data files open. */
export const showFileTags = (runs: RunInfo[]) => dataRuns(runs).length > 1;

/** A shade of a colour: k = 0 the colour, then darker / lighter in turn - several signals of one
 *  file in a plot coloured by file stay apart. */
export function shade(hex: string, k: number): string {
  if (!k) return hex;
  const n = parseInt(hex.slice(1), 16), step = 0.24 * Math.ceil(k / 2), to = k % 2 ? 0 : 255;
  const ch = (v: number) => Math.round(v + (to - v) * Math.min(0.75, step)).toString(16).padStart(2, "0");
  return `#${ch(n >> 16)}${ch((n >> 8) & 255)}${ch(n & 255)}`.toUpperCase();
}

/** T46: colour signals by their file - all of the plot's file signals (`all`), or only the groups
 *  where the same signal name comes from two or more files (a comparison). Several names from one
 *  file get shades of its colour. Mutates the plot (call inside commit). */
export function colorByFile(plot: Plot, runs: RunInfo[], all = false) {
  const nameOf = (s: string) => s.slice(s.indexOf("/") + 1);
  const files = new Map<string, Set<string>>();
  plot.signals.forEach((s) => { if (fileMark(runs, s.sig)) files.set(nameOf(s.sig), (files.get(nameOf(s.sig)) ?? new Set()).add(s.sig.split("/")[0])); });
  const chosen = plot.signals.filter((s) => fileMark(runs, s.sig) && (all || (files.get(nameOf(s.sig))?.size ?? 0) >= 2));
  const names = [...new Set(chosen.map((s) => nameOf(s.sig)))];      // the same shade for a name in every file
  chosen.forEach((s) => { s.color = shade(fileMark(runs, s.sig)!.color, names.indexOf(nameOf(s.sig))); });
  return chosen.length;
}

export function newPlotSignal(sig: string, ws: Workspace): PlotSignal {
  const ps: PlotSignal = { sig, color: nextColor(ws), width: 1.5, scale: 1, offset: 0 };
  if (labelsOf(useApp.getState().runs, sig)) ps.state = true;
  return ps;
}

export function nextColor(ws: Workspace): string {
  return colorAllocator(ws)();
}

/** Colours for several signals made in one go, before they are in the workspace (F13: a template's
 *  plots are built first and added after - nextColor alone saw the same counts every time and gave
 *  every signal the same colour). Each call returns the least used colour, counting what it gave. */
export function colorAllocator(ws: Workspace): () => string {
  const used = new Map<string, number>();
  ws.tabs.forEach((t) => t.plots.forEach((p) => p.signals.forEach((s) => used.set(s.color, (used.get(s.color) ?? 0) + 1))));
  return () => {
    let best = TRACE_COLORS[0], bestN = Infinity;
    for (const c of TRACE_COLORS) {
      const n = used.get(c) ?? 0;
      if (n < bestN) { best = c; bestN = n; }
    }
    used.set(best, bestN + 1);
    return best;
  };
}

/** Put a new plot in the tab: reuse an empty one, else add one (up to MAX_PLOTS).
 *  Returns the index, or -1 when the tab is full (the caller shows a message). */
export function placePlot(tab: Tab, p: Plot): number {
  const empty = tab.plots.findIndex((x) => x.signals.length === 0 && !x.xSignal && !x.objects?.length);   // a map with only objects is in use
  if (empty >= 0) { tab.plots[empty] = { ...p, id: tab.plots[empty].id }; return empty; }
  if (tab.plots.length >= MAX_PLOTS) return -1;
  tab.plots.push(p); fitLayout(tab);
  return tab.plots.length - 1;
}

export function tabFullMessage() {
  const L = useApp.getState().lang;
  useApp.getState().toast({ kind: "error", text: translate(L, "tabFull", { n: MAX_PLOTS }) });
}

export function fitLayout(tab: Tab) {
  if (tab.plots.length > MAX_PLOTS) tab.plots = tab.plots.slice(0, MAX_PLOTS);
  const n = tab.plots.length;
  if (n <= tab.rows * tab.cols) return;
  if (tab.cols === 1 && n <= 4) { tab.rows = n; return; }
  tab.cols = Math.max(tab.cols, Math.ceil(Math.sqrt(n)));
  tab.rows = Math.ceil(n / tab.cols);
}

/** Ask the user for a file path with the built-in browser (open or save). */
export function pickPath(req: Omit<PickerRequest, "resolve">): Promise<string | null> {
  return new Promise((resolve) => useApp.setState({ picker: { ...req, resolve } }));
}
