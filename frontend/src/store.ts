import { create } from "zustand";
import { api, type RunInfo } from "./api";
import { dataRuns, runLabels } from "./names";
import { translate } from "./i18n";
import { labelsOf } from "./values";
import type { LogInfo } from "./api";
import type { Lang } from "./i18n";

/* ----------------------------------------------------------------------------
   Workspace = everything the user arranges (tabs, plots, signal styling).
   Every change goes through `commit`, which records it for Undo / Redo.
   Signals are referenced by stable ids "<runId>/<name>", never by index.
---------------------------------------------------------------------------- */

export interface PlotSignal { sig: string; color: string; width: number; scale: number; offset: number; label?: string; state?: boolean; tOffset?: number;
  /** T13: pass / fail limits on the plotted value (null / absent = no limit on that side) */
  limits?: { lo?: number | null; hi?: number | null } }  // state: drawn as state markers only (no line)
export type PlotMode = "time" | "xy" | "fft" | "geo" | "spec" | "3d" | "env" | "xyz";   // env: Monte-Carlo envelope (T14); xyz: plain 3D (T17c)
export interface Plot {
  id: string; title: string; signals: PlotSignal[];
  mode?: PlotMode;                 // default "time"
  xSignal?: string | null;         // X-Y: signal on the horizontal axis (geo: longitude; the plot's signals are latitudes)
  xyAlign?: "linear" | "nearest";
  fftWindow?: "hanning" | "hamming" | "blackman" | "none";
  fftLog?: boolean;
  fftMethod?: "fft" | "welch";            // welch: averaged power spectral density (T16); absent = fft
  specN?: number;                  // spectrogram window (samples)
  specFmax?: number | null;        // spectrogram: highest frequency shown (null: all)
  caption?: string;                // shown under the plot in reports
  excludeFromReport?: boolean;
  xlim?: [number, number] | null;  // manual axis limits (V-07)
  ylim?: [number, number] | null;
  objects?: MapObject[];           // map: things that move (an aircraft, a ship...) - drawn at the timeline's time
  followObject?: string | null;    // map / 3D: keep this object in the middle (3D: the camera centred on it - it orbits and zooms towards it)
  primaryObject?: string | null;   // 3D: the object whose data the box shows and the relations start from (default: the first)
  relatedObjects?: string[];       // 3D: up to two more objects - a line to each, with distance, in the box: their distance, height difference, bearing
  showReadout?: boolean;           // 3D: the box with the primary object's current values (default shown)
  ownTime?: number | null;         // 3D: a time of its own (not the timeline's) - null / absent: the shared time
  showEvents?: boolean;            // 3D: the log's events as marks on the objects' tracks (default shown)
  xyzEqual?: boolean;              // XYZ (plain 3D, T17c): the same scale on all three axes (default true - right for positions)
  xyzFlipZ?: boolean;              // XYZ: Z drawn pointing down (NED "down", depth)
}
export type ObjectKind = "aircraft" | "missile" | "ship" | "uav" | "drone" | "vehicle";
/** Something that moves on the map: where it is (and how it points) comes from signals - which may
 *  be in different files - read at the timeline's time. */
export interface MapObject {
  id: string; name: string; kind: ObjectKind; color: string;
  lat: string; lon: string;                    // signal ids
  alt?: string | null; yaw?: string | null; pitch?: string | null; roll?: string | null;
  qw?: string | null; qx?: string | null; qy?: string | null; qz?: string | null;   // or the attitude as a quaternion (w, x, y, z)
  angleUnit?: "auto" | "deg" | "rad";
  altRef?: "msl" | "home" | "agl";             // the altitude signal: above sea level (default), above the take-off point, above the ground
  size?: number;                               // icon size, px (default 26)
  trail?: boolean;                             // draw its track (default true)
}
export interface Tab {
  id: string; name: string; rows: number; cols: number; plots: Plot[]; active: number; linkX: boolean;
  linkY?: boolean;                 // shared value axis across the tab's time plots
  sharedStates?: string[];         // state signals drawn as a lane at the bottom of EVERY time plot of the tab
  rowSizes?: number[]; colSizes?: number[];   // relative sizes (drag the gaps between plots)
}
export interface ReportMeta { title: string; intro: string; summary: string; lang: "en" | "he"; theme: "light" | "dark"; scope: "tab" | "all" }
/** A note at a moment of the recording ("vibration starts here"): shown on every time plot, saved
 *  with the session, listed in the report. */
export interface Note { id: string; t: number; text: string }
export interface Workspace { tabs: Tab[]; activeTab: string; report?: ReportMeta; notes?: Note[] }

export const TRACE_COLORS = [
  "#3D8BFD", "#2FBF9F", "#E5677A", "#9B7BFF", "#7CC35A",
  "#F07B3F", "#4FC3E8", "#D08CE8", "#B8A33A", "#FF8FB1",
];

export const MAX_PLOTS = 9;
let idCounter = 0;
export const uid = (p: string) => `${p}${Date.now().toString(36)}${(idCounter++).toString(36)}`;

const newPlot = (): Plot => ({ id: uid("p"), title: "", signals: [] });
const newTab = (_n: number): Tab => ({ id: uid("t"), name: "", rows: 1, cols: 1, plots: [newPlot()], active: 0, linkX: true });

function initialWorkspace(): Workspace {
  const t = newTab(1);
  return { tabs: [t], activeTab: t.id };
}

export type Range = [number, number] | null;
/** One step of zoom history: the x window before it, and the value-axis window if that changed too. */
export interface ZoomStep { x: Range; y?: { key: string; r: Range } }
export type ZoomMode = "x" | "y" | "xy";
export type NewFilesMode = "ask" | "auto" | "ignore";
export interface CursorState { on: boolean; dual: boolean; t1: number | null; t2: number | null; active?: 1 | 2 }
export interface Toast { id: string; kind: "info" | "error"; text: string; action?: { label: string; run: () => void }; ms?: number;
  /** its action undoes the LAST workspace change: valid only until the next change / undo / redo */
  undoesWs?: boolean }
const dropWsUndo = (ts: Toast[]) => (ts.some((t) => t.undoesWs) ? ts.filter((t) => !t.undoesWs) : ts);
export type PanelId = "data" | "analysis" | "compare" | "report" | "log";
export type LogMarkers = "off" | "important" | "all";
export type PlayMode = "cursor" | "draw" | "window";
export interface MenuItem { label: string; icon?: string; run: () => void; disabled?: boolean; danger?: boolean; sep?: boolean }
export interface PickerRequest {
  mode: "open" | "save" | "folder";     // folder: choose a folder (only folders are listed)
  title: string;
  exts?: string[];                 // e.g. [".svsession"]; default: data files
  defaultName?: string;
  resolve: (path: string | null) => void;
}

interface AppState {
  ws: Workspace;
  past: Workspace[];
  future: Workspace[];
  runs: RunInfo[];
  dataVersion: number;
  ranges: Record<string, Range>;      // key: tab id (linked) or plot id (unlinked)
  cursor: CursorState;
  theme: "light" | "dark";
  lang: Lang;
  panel: PanelId | null;
  inspectorOpen: boolean;
  inspectorScope: "active" | "all";
  selected: { plotId: string; sig: string } | null;
  multi: { plotId: string; sig: string }[];     // Ctrl+click several legend chips
  paletteOpen: boolean;
  browserOpen: boolean;
  picker: PickerRequest | null;
  importPaths: string[] | null;
  streaming: boolean;
  busy: number;
  toasts: Toast[];
  decimation: Record<string, { shown: number; total: number }>;
  cvals: Record<string, [number | null, number | null]>;   // raw values at cursor 1 / 2
  jobs: { id: string; label: string; progress: number; phase: string }[];
  menu: { x: number; y: number; items: MenuItem[] } | null;
  linkRuns: boolean;               // D-12: a signal clicked in one file is added from every file
  zoomHistory: Record<string, ZoomStep[]>;
  zoomMode: ZoomMode;              // what drag / wheel zoom: time only, values only, or both
  yRanges: Record<string, Range>;  // value-axis zoom; key: plot id, or "<tab id>:y" when the tab links Y
  liveAutoStop: number | null;     // live mode stops after this many seconds without new data (null: never)
  liveNewFiles: NewFilesMode;      // new files next to the open ones during live mode
  activity: Record<string, number>;   // live: seconds since each file last received data
  liveLastData: number;            // live: time (ms) new data last arrived, or live mode started
  liveStarting: boolean;
  liveIdle: number;
  logs: Record<string, LogInfo>;   // flight-log parameters / events per file (ArduPilot .bin), fetched on demand
  logMarkers: LogMarkers;          // log events drawn on time plots: none, warnings + errors, or all
  syncFor: string | null;          // the file whose time the sync dialog aligns
  templatesTarget: string | null;  // templates dialog opened for this file (its templates first)
  templatesNew: "tab" | "all" | "collection" | null;   // open the library on a new template (current / all tabs) or collection
  templatesSelect: string | null;  // open the library with this template selected (suggestions in the file panel)
  objectDialog: { plotId: string; objectId?: string } | null;   // adding / editing a map object
  placeDialog: string | null;      // T17c: putting an XYZ plot's tracks on a map / 3D plot (the XYZ plot's id)
  geoBase: "auto" | "osm" | "esri" | "light" | "dark" | "satellite" | "topo" | "offline";   // map layer                // live: seconds since new data last arrived (updated by each poll)           // live: refreshing every file before following them
  follow: number | null;           // live mode: show only the last N seconds
  playing: boolean;
  playSpeed: number;               // × real time (1 = the recording's own pace, time in seconds)
  /** What the plots show around the time (the cursor): everything + the cursor, from the start up
   *  to the time ("draw": the plot draws itself), or only the last `windowSec` seconds. */
  playMode: PlayMode;
  windowSec: number;
  timelineOpen: boolean;           // the timeline bar shown in full (or as a thin strip)
  preview: { plotId: string; label: string; x: Float64Array; y: Float32Array } | null;
  valuesOnPlot: boolean;
  yExtents: Record<string, [number, number]>;   // per plot, for linked value axes
  axisDialog: string | null;
  reportPreviewHtml: string | null;
  templatesOpen: boolean;
  transformTargets: string[] | null;     // signals whose change dialog is open
  listSel: string[];                      // signals selected in the file list (Ctrl / Shift + click, or from search)
  listAnchor: string | null;              // where a Shift + click range starts
  analysisSeed: string[] | null;          // signals handed to the Analysis panel from the file list
  retarget: { state: any; title: string; fromCurrent: boolean } | null;   // "open with new files"
  recent: import("./api").RecentItem[];
  hover: { plotId: string; t: number; vals: Record<string, number | null> } | null;
  compareTable: { rows: import("./api").CompareAllRow[]; baseline: string; fileCount: number; tol: boolean } | null;       // plot id whose axis limits are being edited
  promptDialog: { title: string; label: string; value: string; multiline?: boolean; resolve: (v: string | null) => void } | null;
  uiScale: 1 | 1.12 | 1.25;
  helpOpen: boolean;

  commit: (fn: (ws: Workspace) => Workspace) => void;
  undo: () => void;
  redo: () => void;
  set: (p: Partial<AppState>) => void;
  toast: (t: Omit<Toast, "id">) => void;
  dismiss: (id: string) => void;
}

const clone = <T,>(v: T): T => structuredClone(v);

/* Inspector: starts closed, opens by itself when there is something to show (a selected
   signal, the cursor). Once the user opens / closes it with its button, that choice is kept
   and the automatic opening stops. */
const INSPECTOR_KEY = "sv3.inspector";
function inspectorPref(): "open" | "closed" | null {
  try { const v = localStorage.getItem(INSPECTOR_KEY); return v === "open" || v === "closed" ? v : null; }
  catch { return null; }
}
export function setInspectorByUser(open: boolean) {
  try { localStorage.setItem(INSPECTOR_KEY, open ? "open" : "closed"); } catch { /* private mode */ }
  useApp.setState({ inspectorOpen: open });
}
/** Open the Inspector for the cursor values - unless the user has closed it on purpose. */
function revealInspector() {
  if (!useApp.getState().inspectorOpen && inspectorPref() !== "closed") useApp.setState({ inspectorOpen: true });
}

export const useApp = create<AppState>((set, get) => ({
  ws: initialWorkspace(),
  past: [],
  future: [],
  runs: [],
  dataVersion: 0,
  ranges: {},
  cursor: { on: false, dual: false, t1: null, t2: null },
  theme: window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark",
  lang: (navigator.language || "").startsWith("he") ? "he" : "en",
  panel: "data",
  inspectorOpen: inspectorPref() === "open",   // closed until there is something to show (T08)
  inspectorScope: "active",
  selected: null,
  multi: [],
  paletteOpen: false,
  browserOpen: false,
  picker: null,
  importPaths: null,
  streaming: false,
  busy: 0,
  toasts: [],
  decimation: {},
  cvals: {},
  jobs: [],
  menu: null,
  linkRuns: false,
  zoomHistory: {},
  zoomMode: "x",
  yRanges: {},
  liveAutoStop: 60,
  liveNewFiles: "ask",
  activity: {},
  liveLastData: 0,
  liveStarting: false,
  liveIdle: 0,
  logs: {},
  logMarkers: "important",
  syncFor: null,
  templatesTarget: null,
  templatesNew: null,
  templatesSelect: null,
  objectDialog: null,
  placeDialog: null,
  geoBase: "auto",
  follow: null,
  playing: false,
  playSpeed: 1,
  playMode: "cursor",
  windowSec: 10,
  timelineOpen: true,
  preview: null,
  valuesOnPlot: false,
  yExtents: {},
  axisDialog: null,
  reportPreviewHtml: null,
  compareTable: null,
  hover: null,
  templatesOpen: false,
  transformTargets: null,
  listSel: [],
  listAnchor: null,
  analysisSeed: null,
  retarget: null,
  recent: [],
  promptDialog: null,
  uiScale: 1,
  helpOpen: false,

  commit: (fn) => {
    const prev = get().ws;
    const next = fn(clone(prev));
    if (JSON.stringify(next) === JSON.stringify(prev)) return;
    set({ ws: next, past: [...get().past.slice(-99), prev], future: [], toasts: dropWsUndo(get().toasts) });
  },
  undo: () => {
    const { past, ws, future } = get();
    if (!past.length) return;
    set({ ws: past[past.length - 1], past: past.slice(0, -1), future: [ws, ...future], toasts: dropWsUndo(get().toasts) });
  },
  redo: () => {
    const { past, ws, future } = get();
    if (!future.length) return;
    set({ ws: future[0], future: future.slice(1), past: [...past, ws], toasts: dropWsUndo(get().toasts) });
  },
  set: (p) => set(p),
  toast: (t) => {
    const id = uid("m");
    // the same message again replaces the old one instead of stacking up
    set({ toasts: [...get().toasts.filter((x) => x.text !== t.text), { ...t, id }] });
    window.setTimeout(() => get().dismiss(id), t.ms ?? (t.kind === "error" ? 9000 : 4000));
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
}));

/* ------------------------------- selectors ------------------------------- */

export const activeTab = (ws: Workspace) => ws.tabs.find((t) => t.id === ws.activeTab) ?? ws.tabs[0];
/** A plot emptied: its signals, X signal, map / 3D objects and what refers to them. */
function emptyPlot(p: Plot) {
  p.signals = []; p.xSignal = null; p.objects = [];
  p.followObject = null; p.primaryObject = null; p.relatedObjects = []; p.ownTime = null;
}
/** A plot's references to objects it no longer has are dropped (follow, primary, related). */
function forgetObjects(p: Plot) {
  const has = (id?: string | null) => !!id && (p.objects ?? []).some((o) => o.id === id);
  if (p.followObject && !has(p.followObject)) p.followObject = null;
  if (p.primaryObject && !has(p.primaryObject)) p.primaryObject = null;
  if (p.relatedObjects) p.relatedObjects = p.relatedObjects.filter(has);
}
const findPlot = (ws: Workspace, id: string): Plot | undefined => {
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
export function newPlotSignal(sig: string, ws: Workspace): PlotSignal {
  const ps: PlotSignal = { sig, color: nextColor(ws), width: 1.5, scale: 1, offset: 0 };
  if (labelsOf(useApp.getState().runs, sig)) ps.state = true;
  return ps;
}

export function nextColor(ws: Workspace): string {
  const used = new Map<string, number>();
  ws.tabs.forEach((t) => t.plots.forEach((p) => p.signals.forEach((s) => used.set(s.color, (used.get(s.color) ?? 0) + 1))));
  let best = TRACE_COLORS[0], bestN = Infinity;
  for (const c of TRACE_COLORS) {
    const n = used.get(c) ?? 0;
    if (n < bestN) { best = c; bestN = n; }
  }
  return best;
}

/* -------------------------------- actions -------------------------------- */

export const actions = {
  addSignal(sig: string, plotId?: string) {
    const { commit } = useApp.getState();
    commit((ws) => {
      const tab = activeTab(ws);
      const plot = plotId ? tab.plots.find((p) => p.id === plotId) : tab.plots[tab.active];
      if (!plot || plot.signals.some((s) => s.sig === sig)) return ws;
      if ((plot.mode === "xy" || plot.mode === "geo") && !plot.xSignal) { plot.xSignal = sig; return ws; }
      plot.signals.push(newPlotSignal(sig, ws));
      if (plotId) tab.active = tab.plots.findIndex((p) => p.id === plotId);
      return ws;
    });
  },
  toggleSignal(sig: string) {
    const ws = useApp.getState().ws;
    const tab = activeTab(ws);
    const plot = tab.plots[tab.active];
    if (plot?.signals.some((s) => s.sig === sig)) actions.removeSignal(plot.id, sig);
    else actions.addSignal(sig);
  },
  addSignalToNewPlot(sig: string) {
    let full = false;
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      const p = newPlot();
      p.signals.push(newPlotSignal(sig, ws));
      const at = placePlot(tab, p);
      if (at < 0) { full = true; return ws; }
      tab.active = at;
      return ws;
    });
    if (full) tabFullMessage();
  },
  removeSignal(plotId: string, sig: string) {
    // with "link files" on, the same-named signals of the other files leave together
    const st0 = useApp.getState();
    const [rid, ...rest] = sig.split("/");
    const name = rest.join("/");
    const linked = st0.linkRuns && rid !== "derived";
    const dataIds = new Set(st0.runs.filter((r) => r.format !== "derived").map((r) => r.id));
    const goes = (x: string) => x === sig || (linked && dataIds.has(x.split("/")[0]) && x.slice(x.indexOf("/") + 1) === name);
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => { if (p.id === plotId) p.signals = p.signals.filter((s) => !goes(s.sig)); }));
      return ws;
    });
    const sel = useApp.getState().selected;
    if (sel && sel.plotId === plotId && sel.sig === sig) useApp.getState().set({ selected: null });
  },
  /** One undoable step for several signals (batch edit). */
  updateSignals(items: { plotId: string; sig: string }[], patch: Partial<PlotSignal>) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        p.signals = p.signals.map((s) => (items.some((i) => i.plotId === p.id && i.sig === s.sig) ? { ...s, ...patch } : s));
      }));
      return ws;
    });
  },
  removeSignals(items: { plotId: string; sig: string }[]) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => { p.signals = p.signals.filter((s) => !items.some((i) => i.plotId === p.id && i.sig === s.sig)); }));
      return ws;
    });
    useApp.setState({ multi: [], selected: null });
  },
  /** Map objects (Undo-able like everything in the workspace). */
  addObject(plotId: string, o: MapObject) {
    useApp.getState().commit((ws) => { const p = findPlot(ws, plotId); if (p) p.objects = [...(p.objects ?? []), o]; return ws; });
  },
  /** T17c: map objects in a new map / 3D plot of the active tab (false: the tab is full). */
  addObjectsToNewPlot(mode: "geo" | "3d", objs: MapObject[], title = ""): boolean {
    let full = false;
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      const at = placePlot(tab, { ...newPlot(), title, mode, objects: objs });
      if (at < 0) { full = true; return ws; }
      tab.active = at;
      return ws;
    });
    if (full) tabFullMessage();
    return !full;
  },
  updateObject(plotId: string, id: string, patch: Partial<MapObject>) {
    useApp.getState().commit((ws) => {
      const p = findPlot(ws, plotId);
      if (p?.objects) p.objects = p.objects.map((o) => (o.id === id ? { ...o, ...patch } : o));
      return ws;
    });
  },
  removeObject(plotId: string, id: string) {
    useApp.getState().commit((ws) => {
      const p = findPlot(ws, plotId);
      if (p?.objects) p.objects = p.objects.filter((o) => o.id !== id);
      if (p) forgetObjects(p);
      return ws;
    });
  },
  updatePlot(plotId: string, patch: Partial<Plot>) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => { if (p.id === plotId) Object.assign(p, patch); }));
      return ws;
    });
  },
  setPlotMode(plotId: string, mode: PlotMode) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        if (p.id !== plotId) return;
        p.mode = mode;
        if (mode === "geo" && !p.xSignal && p.signals.length >= 2) {
          // longitude = the signal named lon / lng / long (else the first one); the rest are latitudes
          const nameOf = (id: string) => id.slice(id.indexOf("/") + 1);
          const lon = p.signals.find((x) => /(^|[^a-z])(lon|lng|long)/i.test(nameOf(x.sig))) ?? p.signals[0];
          p.xSignal = lon.sig;
          p.signals = p.signals.filter((x) => x !== lon);
        } else if (mode === "xy" && !p.xSignal && p.signals.length >= 2) {
          // first signal becomes X, the rest stay as Y
          p.xSignal = p.signals[0].sig;
          p.signals = p.signals.slice(1);
        } else if (mode === "xyz" && p.xSignal) {
          // XYZ has no separate X: the plot's signals in threes are X, Y, Z - the X-Y / map X goes first
          if (!p.signals.some((x) => x.sig === p.xSignal)) p.signals.unshift(newPlotSignal(p.xSignal, ws));
          p.xSignal = null;
        }
      }));
      return ws;
    });
  },
  /** Map plot: choose the (first) latitude signal; further latitude tracks are added like any signal. */
  setGeoLat(plotId: string, sig: string) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        if (p.id !== plotId) return;
        if (p.signals.some((s) => s.sig === sig)) return;
        if (p.signals.length) p.signals[0] = { ...p.signals[0], sig };
        else p.signals.push(newPlotSignal(sig, ws));
      }));
      return ws;
    });
  },
  updateSignal(plotId: string, sig: string, patch: Partial<PlotSignal>) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        if (p.id === plotId) p.signals = p.signals.map((s) => (s.sig === sig ? { ...s, ...patch } : s));
      }));
      return ws;
    });
  },
  /** Any rows x cols with at most MAX_PLOTS plots. Shrinking removes the extra
   *  plots (their signals go with them); the toast offers Undo. */
  setLayout(rows: number, cols: number) {
    rows = Math.max(1, Math.min(MAX_PLOTS, Math.round(rows)));
    cols = Math.max(1, Math.min(MAX_PLOTS, Math.round(cols)));
    if (rows * cols > MAX_PLOTS) return;
    const st = useApp.getState();
    const before = activeTab(st.ws);
    const n = rows * cols;
    const dropped = before.plots.slice(n).filter((p) => p.signals.length || p.xSignal).length;
    st.commit((ws) => {
      const tab = activeTab(ws);
      tab.rows = rows; tab.cols = cols; tab.rowSizes = undefined; tab.colSizes = undefined;
      while (tab.plots.length < n) tab.plots.push(newPlot());
      tab.plots = tab.plots.slice(0, n);
      tab.active = Math.min(tab.active, n - 1);
      return ws;
    });
    if (dropped) {
      const L = useApp.getState().lang;
      useApp.getState().toast({ kind: "info", text: translate(L, "plotsRemoved", { n: dropped }),
        action: { label: translate(L, "undo"), run: () => useApp.getState().undo() }, undoesWs: true });
    }
  },
  setActivePlot(index: number) {
    const st = useApp.getState();
    const tab = activeTab(st.ws);
    if (index < 0 || index >= tab.plots.length || index === tab.active) return;
    // selection is not an undoable edit
    useApp.setState({ ws: { ...st.ws, tabs: st.ws.tabs.map((t) => (t.id === tab.id ? { ...t, active: index } : t)) } });
  },
  renamePlot(plotId: string, title: string) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => { if (p.id === plotId) p.title = title; }));
      return ws;
    });
  },
  addTab() {
    useApp.getState().commit((ws) => {
      const t = newTab(ws.tabs.length + 1);
      ws.tabs.push(t);
      ws.activeTab = t.id;
      return ws;
    });
  },
  duplicateTab(id: string) {
    useApp.getState().commit((ws) => {
      const src = ws.tabs.find((t) => t.id === id);
      if (!src) return ws;
      const copy: Tab = { ...clone(src), id: uid("t"), name: src.name ? `${src.name} (2)` : "" };
      copy.plots = copy.plots.map((p) => ({ ...p, id: uid("p") }));
      ws.tabs.splice(ws.tabs.indexOf(src) + 1, 0, copy);
      ws.activeTab = copy.id;
      return ws;
    });
  },
  closeTab(id: string) {
    useApp.getState().commit((ws) => {
      if (ws.tabs.length === 1) {
        const t = newTab(1);
        return { tabs: [t], activeTab: t.id };
      }
      const i = ws.tabs.findIndex((t) => t.id === id);
      ws.tabs.splice(i, 1);
      if (ws.activeTab === id) ws.activeTab = ws.tabs[Math.max(0, i - 1)].id;
      return ws;
    });
  },
  renameTab(id: string, name: string) {
    useApp.getState().commit((ws) => {
      const t = ws.tabs.find((x) => x.id === id);
      if (t) t.name = name;
      return ws;
    });
  },
  switchTab(id: string) {
    const st = useApp.getState();
    useApp.setState({ ws: { ...st.ws, activeTab: id }, selected: null });
  },
  toggleLinkX() {
    useApp.getState().commit((ws) => { const t = activeTab(ws); t.linkX = !t.linkX; return ws; });
  },
  /** D-12: with "link files" on, add the same-named signal from every open file. */
  addSignalLinked(sig: string, plotId?: string) {
    const st = useApp.getState();
    const [rid, ...rest] = sig.split("/");
    const name = rest.join("/");
    if (!st.linkRuns || rid === "derived") { actions.addSignal(sig, plotId); return; }
    const ids = st.runs.filter((r) => r.format !== "derived" && r.signals.some((x) => x.name === name)).map((r) => `${r.id}/${name}`);
    st.commit((ws) => {
      const tab = activeTab(ws);
      const plot = plotId ? tab.plots.find((p) => p.id === plotId) : tab.plots[tab.active];
      if (!plot) return ws;
      for (const id of ids) if (!plot.signals.some((x) => x.sig === id)) plot.signals.push(newPlotSignal(id, ws));
      return ws;
    });
  },
  duplicateToNewPlot(plotId: string, sig: string) {
    let full = false;
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      const src = tab.plots.find((p) => p.id === plotId)?.signals.find((s) => s.sig === sig);
      if (!src) return ws;
      const p = newPlot();
      p.signals.push({ ...src });
      const at = placePlot(tab, p);
      if (at < 0) { full = true; return ws; }
      tab.active = at;
      return ws;
    });
    if (full) tabFullMessage();
  },
  moveSignal(plotId: string, sig: string, dir: -1 | 1) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        if (p.id !== plotId) return;
        const i = p.signals.findIndex((s) => s.sig === sig), j = i + dir;
        if (i < 0 || j < 0 || j >= p.signals.length) return;
        [p.signals[i], p.signals[j]] = [p.signals[j], p.signals[i]];
      }));
      return ws;
    });
  },
  /** Drag a chip: reorder inside a plot (before `beforeSig`) or move / copy to another plot. */
  dropSignal(fromPlot: string, sig: string, toPlot: string, beforeSig: string | null, copy: boolean) {
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      const src = tab.plots.find((p) => p.id === fromPlot), dst = tab.plots.find((p) => p.id === toPlot);
      if (!src || !dst) return ws;
      const item = src.signals.find((s) => s.sig === sig);
      if (!item) return ws;
      if (!copy || src === dst) src.signals = src.signals.filter((s) => s.sig !== sig);
      if (src !== dst && dst.signals.some((s) => s.sig === sig)) return ws;
      const at = beforeSig ? dst.signals.findIndex((s) => s.sig === beforeSig) : -1;
      if (at >= 0) dst.signals.splice(at, 0, { ...item }); else dst.signals.push({ ...item });
      return ws;
    });
  },
  setAsX(plotId: string, sig: string) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        if (p.id !== plotId) return;
        p.mode = "xy"; p.xSignal = sig;
        p.signals = p.signals.filter((s) => s.sig !== sig);
      }));
      return ws;
    });
  },
  clearPlot(plotId: string) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => { if (p.id === plotId) emptyPlot(p); }));
      return ws;
    });
  },
  /** Empty the plots of this tab (files stay open). Undoable - the toast says so and offers it,
   *  which is what tells it apart from "Clear everything" in the TopBar. */
  clearAllPlots() {
    const st = useApp.getState();
    st.commit((ws) => { const t = activeTab(ws); t.plots.forEach(emptyPlot); return ws; });
    st.toast({ kind: "info", text: translate(st.lang, "plotsCleared"),
      action: { label: translate(st.lang, "undo"), run: () => useApp.getState().undo() }, undoesWs: true });
  },
  /** Take the 3D view away: its objects and 3D settings go, the plot is an empty time plot again (Undo brings it back). */
  remove3d(plotId: string) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => { if (p.id === plotId) { emptyPlot(p); p.mode = "time"; } }));
      return ws;
    });
  },
  closeOtherTabs(id: string) {
    useApp.getState().commit((ws) => ({ ...ws, tabs: ws.tabs.filter((t) => t.id === id), activeTab: id }));
  },
  moveTab(id: string, toIndex: number) {
    useApp.getState().commit((ws) => {
      const i = ws.tabs.findIndex((t) => t.id === id);
      if (i < 0) return ws;
      const [t] = ws.tabs.splice(i, 1);
      ws.tabs.splice(Math.max(0, Math.min(ws.tabs.length, toIndex)), 0, t);
      return ws;
    });
  },
  setAxisLimits(plotId: string, xlim: [number, number] | null, ylim: [number, number] | null, wholeTab: boolean) {
    const st = useApp.getState();
    st.commit((ws) => {
      const tab = activeTab(ws);
      tab.plots.forEach((p) => { if (p.id === plotId || wholeTab) { p.xlim = xlim; p.ylim = ylim; } });
      return ws;
    });
    const tab = activeTab(useApp.getState().ws);
    tab.plots.forEach((p) => { if (p.id === plotId || wholeTab) actions.setRange(rangeKey(tab, p), xlim); });
    const ys = { ...useApp.getState().yRanges };
    tab.plots.forEach((p) => { if (p.id === plotId || wholeTab) { delete ys[p.id]; delete ys[`${tab.id}:y`]; } });
    useApp.setState({ yRanges: ys });
  },
  toggleLinkY() {
    useApp.getState().commit((ws) => { const t = activeTab(ws); t.linkY = !t.linkY; return ws; });
  },
  setSizes(rowSizes: number[] | undefined, colSizes: number[] | undefined) {
    // live resizing is not an undoable step: write directly
    const st = useApp.getState();
    useApp.setState({ ws: { ...st.ws, tabs: st.ws.tabs.map((t) => (t.id === st.ws.activeTab ? { ...t, rowSizes, colSizes } : t)) } });
  },
  removeRunSignals(runId: string) { actions.removeSignalRefs((sig) => sig.startsWith(`${runId}/`)); },
  removeSignalRefs(match: (sig: string) => boolean) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        p.signals = p.signals.filter((s) => !match(s.sig));
        if (p.xSignal && match(p.xSignal)) p.xSignal = null;
        // an object without its position goes; a lost optional signal just goes from it
        if (p.objects) {
          p.objects = p.objects.filter((o) => !match(o.lat) && !match(o.lon)).map((o) => {
            const c = { ...o };
            for (const k of ["alt", "yaw", "pitch", "roll", "qw", "qx", "qy", "qz"] as const) if (c[k] && match(c[k]!)) c[k] = null;
            return c;
          });
          forgetObjects(p);
        }
      }));
      return ws;
    });
  },
  setRange(key: string, r: Range, opts: { history?: boolean } = {}) {
    const st = useApp.getState();
    const cur = st.ranges[key] ?? null;
    if (cur === r || (cur && r && cur[0] === r[0] && cur[1] === r[1])) return;
    const hist = opts.history === false ? st.zoomHistory
      : { ...st.zoomHistory, [key]: [...(st.zoomHistory[key] ?? []).slice(-49), { x: cur }] };
    useApp.setState({ ranges: { ...st.ranges, [key]: r }, zoomHistory: hist });
  },
  /** Zoom one plot: x window (undefined = leave it) and value window (undefined = leave it,
   *  null = automatic again). One history step for both, so Backspace undoes the whole gesture. */
  setView(xKey: string, x: Range | undefined, yKey: string, y: Range | undefined, opts: { history?: boolean } = {}) {
    const st = useApp.getState();
    const curX = st.ranges[xKey] ?? null, curY = st.yRanges[yKey] ?? null;
    const same = (a: Range, b: Range) => a === b || (!!a && !!b && a[0] === b[0] && a[1] === b[1]);
    const xChange = x !== undefined && !same(curX, x), yChange = y !== undefined && !same(curY, y);
    if (!xChange && !yChange) return;
    const step: ZoomStep = { x: curX, ...(yChange ? { y: { key: yKey, r: curY } } : {}) };
    useApp.setState({
      ranges: xChange ? { ...st.ranges, [xKey]: x! } : st.ranges,
      yRanges: yChange ? { ...st.yRanges, [yKey]: y! } : st.yRanges,
      zoomHistory: opts.history === false ? st.zoomHistory : { ...st.zoomHistory, [xKey]: [...(st.zoomHistory[xKey] ?? []).slice(-49), step] },
    });
  },
  pushZoomStep(xKey: string, step: ZoomStep) {
    const st = useApp.getState();
    useApp.setState({ zoomHistory: { ...st.zoomHistory, [xKey]: [...(st.zoomHistory[xKey] ?? []).slice(-49), step] } });
  },
  setZoomMode(m: ZoomMode) { useApp.setState({ zoomMode: m }); },
  async addNoteAtCursor() {
    const st = useApp.getState();
    if (!st.cursor.on || st.cursor.t1 === null) {
      st.toast({ kind: "info", text: translate(st.lang, "noteNeedsCursor") });
      return;
    }
    const at = st.cursor.active === 2 && st.cursor.t2 !== null ? st.cursor.t2 : st.cursor.t1;
    const { prompt } = await import("./components/Overlays");
    const text = await prompt(translate(st.lang, "noteAdd"), translate(st.lang, "noteAt", { t: at.toPrecision(7) }), "", true);
    if (!text || !text.trim()) return;
    st.commit((ws) => { ws.notes = [...(ws.notes ?? []), { id: uid("n"), t: at, text: text.trim() }]; return ws; });
  },
  async editNote(id: string) {
    const st = useApp.getState();
    const n = st.ws.notes?.find((x) => x.id === id);
    if (!n) return;
    const { prompt } = await import("./components/Overlays");
    const text = await prompt(translate(st.lang, "noteEdit"), translate(st.lang, "noteAt", { t: n.t.toPrecision(7) }), n.text, true);
    if (text === null) return;
    st.commit((ws) => { ws.notes = (ws.notes ?? []).map((x) => (x.id === id ? { ...x, text: text.trim() } : x)).filter((x) => x.text); return ws; });
  },
  removeNote(id: string) {
    useApp.getState().commit((ws) => { ws.notes = (ws.notes ?? []).filter((x) => x.id !== id); return ws; });
  },
  /** A state signal as a lane on every time plot of the active tab (or not any more). */
  toggleSharedState(sig: string) {
    useApp.getState().commit((ws) => {
      const tab = ws.tabs.find((t) => t.id === ws.activeTab);
      if (!tab) return ws;
      const cur = tab.sharedStates ?? [];
      tab.sharedStates = cur.includes(sig) ? cur.filter((x) => x !== sig) : [...cur, sig];
      return ws;
    });
  },
  /** Both cursors on [a, b] and every plot of the tab zoomed to it (with some margin). */
  showSpan(a: number, b: number) {
    const st = useApp.getState();
    const tab = activeTab(st.ws);
    const pad = Math.max((b - a) * 0.5, 1);
    const ranges = { ...st.ranges };
    for (const p of tab.plots) ranges[rangeKey(tab, p)] = [a - pad, b + pad];
    useApp.setState({ ranges, cursor: { on: true, dual: b > a, t1: a, t2: b > a ? b : null, active: 1 } });
  },
  /** A new tab with one plot of these signals (health check, log panel). */
  plotSignalsInNewTab(ids: string[], title: string) {
    const st = useApp.getState();
    st.commit((ws) => {
      const p: Plot = { id: uid("p"), title, signals: [] };
      ids.slice(0, 10).forEach((id, i) => p.signals.push({ ...newPlotSignal(id, ws), color: TRACE_COLORS[i % TRACE_COLORS.length] }));
      const tab: Tab = { id: uid("t"), name: title, rows: 1, cols: 1, plots: [p], active: 0, linkX: true };
      ws.tabs.push(tab);
      ws.activeTab = tab.id;
      return ws;
    });
  },
  /** Put the cursor at time t (log event, parameter change...) and bring t into view in every
   *  plot of the tab that does not show it, keeping each plot's zoom width. */
  goToTime(t: number) {
    const st = useApp.getState();
    const tab = activeTab(st.ws);
    const ranges = { ...st.ranges };
    for (const p of tab.plots) {
      const key = rangeKey(tab, p);
      const r = ranges[key];
      if (r && (t < r[0] || t > r[1])) { const w = r[1] - r[0]; ranges[key] = [t - w / 2, t + w / 2]; }
    }
    useApp.setState({ ranges, cursor: { ...st.cursor, on: true, t1: t, active: 1 } });
  },
  cycleZoomMode() {
    const order: ZoomMode[] = ["x", "y", "xy"];
    const st = useApp.getState();
    useApp.setState({ zoomMode: order[(order.indexOf(st.zoomMode) + 1) % order.length] });
  },
  /** Play / pause. Starts from the beginning of the shown range in draw mode, or
   *  when the cursor already reached the end. */
  togglePlay() {
    const st = useApp.getState();
    if (st.playing) { useApp.setState({ playing: false }); return; }
    // over the whole recording (not just the visible window); from where the time is, or from the
    // start when it is at the end / outside
    const r = recordingExtent(st.runs);
    if (!r) return;
    let t1 = st.cursor.on && st.cursor.t1 !== null ? st.cursor.t1 : r[0];
    if (t1 >= r[1] - (r[1] - r[0]) * 0.001 || t1 < r[0]) t1 = r[0];
    useApp.setState({ cursor: { ...st.cursor, on: true, t1 }, playing: true });
    actions.followTime(t1);
  },
  /** Set the time (the cursor) - the timeline, its event marks, Home / End. */
  setTime(t: number) {
    const st = useApp.getState();
    useApp.setState({ cursor: { ...st.cursor, on: true, t1: t, active: 1 } });
  },
  /** Keep the time in view: a zoomed time plot of the active tab whose window no longer holds it
   *  moves to show it (near its left side, so what follows is visible). */
  followTime(t: number) {
    const st = useApp.getState();
    const tab = activeTab(st.ws);
    let ranges: Record<string, Range> | null = null;
    for (const p of tab.plots) {
      if ((p.mode ?? "time") !== "time" && p.mode !== "spec") continue;
      const k = rangeKey(tab, p);
      const r = st.ranges[k];
      if (!r || (t >= r[0] && t <= r[1])) continue;
      const w = r[1] - r[0];
      (ranges ??= { ...st.ranges })[k] = [t - w * 0.1, t + w * 0.9];
    }
    if (ranges) useApp.setState({ ranges });
  },
  /** Arrow keys: move the active cursor `n` recorded samples (n < 0: back) of the selected signal
   *  (else the first one of the active plot). The cursor lands exactly ON a sample, so the values
   *  read are the recorded ones, never interpolated. Only mouse placement interpolates.
   *  Presses that arrive while the server is answering are added up, so no step is lost. */
  stepCursor(n: number) {
    _pendingSteps += n;
    if (_stepping) return;
    _stepping = true;
    (async () => {
      try {
        while (_pendingSteps !== 0) {
          const k = _pendingSteps; _pendingSteps = 0;
          const st = useApp.getState();
          const c = st.cursor;
          const which: "t1" | "t2" = c.dual && c.active === 2 ? "t2" : "t1";
          const cur = c[which];
          if (!c.on || cur === null) return;
          const tb = activeTab(st.ws);
          const plot = tb.plots[tb.active];
          const sel = st.selected && plot && st.selected.plotId === plot.id ? plot.signals.find((x) => x.sig === st.selected!.sig) : undefined;
          const ps = sel ?? plot?.signals[0];
          let sigId = ps?.sig ?? null, off = ps?.tOffset ?? 0;
          if (plot && (plot.mode === "xy" || plot.mode === "geo") && plot.xSignal && !ps) sigId = plot.xSignal;
          if (!sigId) {                       // nothing plotted: fall back to a fixed fraction of the view
            const r = plot ? st.ranges[rangeKey(tb, plot)] : null;
            const run = st.runs.find((x) => x.format !== "derived");
            const span = r ? r[1] - r[0] : run ? run.end - run.start : 1;
            useApp.setState({ cursor: { ...c, [which]: cur + (span / 500) * k } });
            continue;
          }
          const r = await api.neighbor(sigId, cur - off, k);
          const now = useApp.getState().cursor;
          if (r.t !== null && now.on) useApp.setState({ cursor: { ...now, [which]: r.t + off } });
        }
      } catch (e) {
        useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
      } finally { _stepping = false; _pendingSteps = 0; }
    })();
  },
  zoomBack() {
    const st = useApp.getState();
    const tab = activeTab(st.ws);
    const plot = tab.plots[tab.active];
    if (!plot) return;
    const key = rangeKey(tab, plot);
    const h = st.zoomHistory[key] ?? [];
    if (!h.length) return;
    const step = h[h.length - 1];
    useApp.setState({
      ranges: { ...st.ranges, [key]: step.x },
      yRanges: step.y ? { ...st.yRanges, [step.y.key]: step.y.r } : st.yRanges,
      zoomHistory: { ...st.zoomHistory, [key]: h.slice(0, -1) },
    });
  },
  /** After a file was reloaded or replaced: a zoom window that no longer overlaps the data
   *  (the new file covers other times) would show an empty graph although the data changed.
   *  Such windows are dropped, so the graph shows the new data. */
  dropStaleRanges() {
    const st = useApp.getState();
    const data = st.runs.filter((r) => r.format !== "derived" && r.samples > 0);
    if (!data.length) return;
    const lo = Math.min(...data.map((r) => r.start)), hi = Math.max(...data.map((r) => r.end));
    const next = { ...st.ranges };
    let changed = false;
    for (const [k, r] of Object.entries(next)) {
      if (r && (r[1] < lo || r[0] > hi)) { delete next[k]; changed = true; }
    }
    if (changed) useApp.setState({ ranges: next });
  },
  resetZoom() {
    const st = useApp.getState();
    const tab = activeTab(st.ws);
    const next = { ...st.ranges };
    delete next[tab.id];
    tab.plots.forEach((p) => { delete next[p.id]; if (p.xlim) next[rangeKey(tab, p)] = p.xlim; });
    const ys = { ...st.yRanges };
    delete ys[`${tab.id}:y`];
    tab.plots.forEach((p) => { delete ys[p.id]; });
    useApp.setState({ ranges: next, yRanges: ys });
  },
  toggleCursor() {
    const st = useApp.getState();
    const c = st.cursor;
    if (!c.on && c.t1 === null) {
      // place the cursor in the middle of what is visible
      const tab = activeTab(st.ws);
      const plot = tab.plots[tab.active];
      const r = plot ? st.ranges[rangeKey(tab, plot)] : null;
      const run = st.runs.find((r) => r.format !== "derived");
      const mid = r ? (r[0] + r[1]) / 2 : run ? (run.start + run.end) / 2 : 0;
      useApp.setState({ cursor: { ...c, on: true, t1: mid } });
    } else useApp.setState({ cursor: { ...c, on: !c.on } });
    if (useApp.getState().cursor.on) revealInspector();
  },
  toggleDual() {
    const st = useApp.getState();
    const c = st.cursor;
    if (c.dual) { useApp.setState({ cursor: { ...c, dual: false } }); return; }
    // Both cursors must land inside what is SHOWN now. (Before, cursor 2 went 20 % after
    // cursor 1 or back to an old position, which after Play or a zoom is off-screen.)
    const tab = activeTab(st.ws);
    const plot = tab.plots[tab.active];
    const data = st.runs.filter((r) => r.format !== "derived");
    const shown = plot ? st.ranges[rangeKey(tab, plot)] ?? plot.xlim ?? null : null;
    const lo = shown ? shown[0] : data.length ? Math.min(...data.map((r) => r.start)) : 0;
    const hi = shown ? shown[1] : data.length ? Math.max(...data.map((r) => r.end)) : 1;
    const span = hi - lo || 1;
    const inside = (v: number | null) => v !== null && v >= lo && v <= hi;
    const t1 = inside(c.t1) ? c.t1! : lo + span * 0.4;
    let t2 = inside(c.t2) && c.t2 !== t1 ? c.t2! : t1 + span * 0.2;
    if (t2 > hi) t2 = t1 - span * 0.2;          // no room after cursor 1: put cursor 2 before it
    t2 = Math.min(hi, Math.max(lo, t2));
    useApp.setState({ cursor: { on: true, dual: true, t1, t2 } });
    revealInspector();
  },
};

let _pendingSteps = 0, _stepping = false;

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
