/* ----------------------------------------------------------------------------
   Workspace = everything the user arranges (tabs, plots, signal styling).
   Every change goes through `commit`, which records it for Undo / Redo.
   Signals are referenced by stable ids "<runId>/<name>", never by index.
---------------------------------------------------------------------------- */

export interface PlotSignal { sig: string; color: string; width: number; scale: number; offset: number; label?: string; state?: boolean; tOffset?: number;
  /** T47: on the plot's second value axis (right); absent = the left axis */
  axis?: "right";
  /** T13: pass / fail limits on the plotted value (null / absent = no limit on that side) */
  limits?: { lo?: number | null; hi?: number | null } }  // state: drawn as state markers only (no line)
export type PlotMode = "time" | "xy" | "fft" | "geo" | "spec" | "3d" | "env" | "xyz" | "video" | "occ" | "step";   // step: 1.21 step response (PID Review)   // occ: a condition's stretches together (investigation step 3)   // env: Monte-Carlo envelope (T14); xyz: plain 3D (T17c); video: T15
export interface Plot {
  id: string; title: string; signals: PlotSignal[];
  mode?: PlotMode;                 // default "time"
  /** occ: whose stretches (a condition id), lined up at their start / end / peak, with this share of
   *  the longest one shown before and after */
  occ?: { cond: string; align: "start" | "end" | "peak"; pad: number };
  xSignal?: string | null;         // X-Y: signal on the horizontal axis (geo: longitude; the plot's signals are latitudes)
  xyAlign?: "linear" | "nearest";
  fftWindow?: "hanning" | "hamming" | "blackman" | "none";
  fftLog?: boolean;
  fftFilters?: boolean;            // 1.21: ArduPilot's gyro filters on the spectrum (notch lines, after-filter estimate)
  fftMethod?: "fft" | "welch";            // welch: averaged power spectral density (T16); absent = fft
  /** T16b: marks at 1x / 2x / 3x the mean rotation rate of this signal (and the blade-pass
   *  frequency with blades) over the spectrum's window; absent = no marks. */
  fftOrders?: { sig: string; unit: "rpm" | "hz"; blades?: number };
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
  /** T15 video mode: a local video file played with the timeline. data time = video time + offset (s). */
  video?: { path: string; offset: number };
  showEvents?: boolean;            // 3D: the log's events as marks on the objects' tracks (default shown)
  xyzEqual?: boolean;              // XYZ (plain 3D, T17c): the same scale on all three axes (default true - right for positions)
  xyzFlipZ?: boolean;              // XYZ: Z drawn pointing down (NED "down", depth)
  /** where the signal names (and their values) are: auto (above while they fit in two rows, else a
   *  column beside the plot), above, beside, hidden. Absent = auto. */
  legend?: "auto" | "top" | "side" | "off";
  legendW?: number;                // the side column's width, px (absent: 240)
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
  /** the track's colour (owner, 2026-11-03): the object's own (default), by a state signal (the
   *  flight mode: a colour per value, with a key) or by a value (altitude, speed: a colour scale) */
  trackColor?: "object" | "state" | "value";
  colorSig?: string | null;                    // the signal of "state" / "value"
}
export interface Tab {
  id: string; name: string; rows: number; cols: number; plots: Plot[]; active: number; linkX: boolean;
  linkY?: boolean;                 // shared value axis across the tab's time plots
  sharedStates?: string[];         // state signals drawn as a lane at the bottom of EVERY time plot of the tab
  rowSizes?: number[]; colSizes?: number[];   // relative sizes (drag the gaps between plots)
}
export interface ReportMeta { title: string; intro: string; summary: string; lang: "en" | "he"; theme: "light" | "dark"; scope: "tab" | "all"; investigation?: boolean }
/** A note at a moment of the recording ("vibration starts here"): shown on every time plot, saved
 *  with the session, listed in the report. */
/** A note at a moment, or over a time range (T23: t2 = its end). */
export interface Note { id: string; t: number; t2?: number; text: string;
  /** Investigation step 6: a note that is a finding (absent = a plain mark), and the view it was
   *  found in (tab, zoom, cursors) - a click brings that view back. */
  status?: FindingStatus; view?: SavedView }
export type FindingStatus = "open" | "explained" | "fault" | "rejected";
/** What was on screen: the active tab, its plots' zoom windows and the cursors. */
export interface SavedView { tab: string; ranges: Record<string, [number, number]>; t1: number | null; t2: number | null }
/** One step of the investigation, recorded as it happens (Investigate panel; the report's "analysis steps"). */
/** kind: what the step was (the list groups by it); older sessions have none */
export type StepKind = "condition" | "changed" | "lag" | "differ" | "overlay" | "finding" | "error";
export interface JournalStep { id: string; at: number; text: string; view?: SavedView; include: boolean; kind?: StepKind }
/** U1: the rest of a template's tabs - its id, the files its slots were given, the tab names left. */
export interface MoreTabs { tpl: string; name: string; builtin?: boolean; bind: Record<string, string>; tabs: string[] }
export interface Workspace { tabs: Tab[]; activeTab: string; report?: ReportMeta; notes?: Note[];
  /** State lanes on every time plot of every tab (signal ids), beside each tab's own sharedStates. */
  globalStates?: string[];
  /** "Always as a state", by signal NAME (every open file): true = a lane wherever it is added,
   *  false = a line even when it has texts; absent = automatic (signals with texts are lanes). */
  stateNames?: Record<string, boolean>;
  /** Investigation step 2: named conditions (where an expression holds), in the session. */
  conditions?: Condition[];
  /** The rows of the overview strip, in order (absent: the run's phase signal alone). */
  overviewRows?: StripRow[];
  /** Groups of signals the user made and named in the signal list (owner, 2026-11-03); "/" in a
   *  name nests it ("Nav/IMU" is inside "Nav"). Signals of any open file and made signals. */
  sigGroups?: SigGroupDef[];
  /** U1: tabs of a template that were not opened with it, offered by "+N more from <template>"
   *  beside the tab bar's + (optional: older sessions have none). */
  moreTabs?: MoreTabs[];
}
export interface SigGroupDef { name: string; sigs: string[] }
/** A row of the overview strip: a state signal by NAME (every file), or a named condition. */
export type StripRow = { kind: "state"; name: string } | { kind: "cond"; id: string };
/** A named condition: the stretches of each open file where `text` holds (svcore/conditions.py), or
 *  two or more conditions combined. Kept in the session; results are not (computed again). */
export interface Condition {
  id: string; name: string; color: string; visible: boolean;
  text: string;                    // {Speed} > 12 and Mode == "AUTO"
  exit?: string;                   // hysteresis: a stretch lasts until this holds
  minDur?: number;                 // s: shorter stretches are left out
  mergeGap?: number;               // s: closer stretches are joined
  combine?: { op: "and" | "or"; ids: string[] };   // instead of text: these conditions together
}

export const TRACE_COLORS = [
  "#3D8BFD", "#2FBF9F", "#E5677A", "#9B7BFF", "#7CC35A",
  "#F07B3F", "#4FC3E8", "#D08CE8", "#B8A33A", "#FF8FB1",
  // ten more (an investigation shows 20-40 signals at once: ten colours repeated every tenth line)
  "#2563EB", "#D97706", "#059669", "#DC2626", "#7C3AED",
  "#0891B2", "#DB2777", "#65A30D", "#A0522D", "#6B7280",
];

/** A deep copy (the workspace is plain data). */
export const clone = <T,>(v: T): T => structuredClone(v);

export const MAX_PLOTS = 9;
let idCounter = 0;
export const uid = (p: string) => `${p}${Date.now().toString(36)}${(idCounter++).toString(36)}`;

export const newPlot = (): Plot => ({ id: uid("p"), title: "", signals: [] });
export const newTab = (_n: number): Tab => ({ id: uid("t"), name: "", rows: 1, cols: 1, plots: [newPlot()], active: 0, linkX: true });

export function initialWorkspace(): Workspace {
  const t = newTab(1);
  return { tabs: [t], activeTab: t.id };
}
