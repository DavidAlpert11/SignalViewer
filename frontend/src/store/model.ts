/* ----------------------------------------------------------------------------
   Workspace = everything the user arranges (tabs, plots, signal styling).
   Every change goes through `commit`, which records it for Undo / Redo.
   Signals are referenced by stable ids "<runId>/<name>", never by index.
---------------------------------------------------------------------------- */

export interface PlotSignal { sig: string; color: string; width: number; scale: number; offset: number; label?: string; state?: boolean; tOffset?: number;
  /** T47: on the plot's second value axis (right); absent = the left axis */
  axis?: "right";
  /** T13: pass / fail limits on the plotted value (null / absent = no limit on that side) */
  limits?: { lo?: number | null; hi?: number | null };
  /** U4: dashed (true) or solid (false) by hand; absent = automatic (a setpoint beside its measured
   *  value is dashed and faded - desired.ts) */
  dash?: boolean }  // state: drawn as state markers only (no line)
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
  /** N6: how the 3D camera follows the followed object - on it (absent: it orbits and zooms towards it,
   *  as before), "chase" (behind and above it, along its heading) or "lookat" (from it towards the
   *  first related object) */
  camera?: "chase" | "lookat";
  /** N6: the 2D map's "up" - north (absent) or the heading of the followed object (else the primary, else
   *  the first): "track" */
  mapUp?: "track";
  /** N7: lines on the map between objects, with the range - the primary and the secondary (absent), the
   *  primary to every object, or none */
  relLines?: "all" | "off";
  /** N7: the relation box on the map folded (absent: open) */
  relFolded?: boolean;
  showReadout?: boolean;           // 3D: the box with the primary object's current values (default shown)
  ownTime?: number | null;         // 3D: a time of its own (not the timeline's) - null / absent: the shared time
  /** T15 video mode: a local video file played with the timeline. data time = video time + offset (s). */
  video?: { path: string; offset: number };
  showEvents?: boolean;            // 3D: the log's events as marks on the objects' tracks (default shown)
  /** U3: the tab's lanes drawn in this plot too, although the tab shows them once above its plots
   *  (absent / false: not here - the band above has them) */
  ownBand?: boolean;
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
  /** N5: the kind of source it was found as (truth / navigation / receiver / other) - sets its default
   *  look and, in N7, the default primary / secondary; absent = unknown (objects made before) */
  cls?: "truth" | "navigation" | "receiver" | "other";
  /** N5: how its track is drawn - a line (default), dashed (a navigation solution) or points (a receiver) */
  track?: "line" | "dash" | "points";
  /** N5 (owner's decision 3): where its attitude comes from - its own signals (default: absent = as
   *  before), its motion (course over ground, flight-path angle, roll unknown), or another object's */
  attitudeSource?: "own" | "motion" | { object: string };
  /** N5: below this ground speed (m/s) a heading from motion holds its last value (default 1) */
  minSpeed?: number;
  /** N7: its velocity north / east / down (m/s), found by its names - compared between objects */
  vel?: [string, string, string | null] | null;
}
export interface Tab {
  id: string; name: string; rows: number; cols: number; plots: Plot[]; active: number; linkX: boolean;
  linkY?: boolean;                 // shared value axis across the tab's time plots
  sharedStates?: string[];         // state signals drawn as a lane at the bottom of EVERY time plot of the tab
  rowSizes?: number[]; colSizes?: number[];   // relative sizes (drag the gaps between plots)
}
export interface ReportMeta { title: string; intro: string; summary: string; lang: "en" | "he"; theme: "light" | "dark"; scope: "tab" | "all"; investigation?: boolean;
  /** 26.U4: Compare's verdict (made by "Report…" in Compare) and whether the report includes it (default yes) */
  verdict?: ReportVerdict; includeVerdict?: boolean }
/** 26.U4: pass / fail per signal and file against a baseline, as a report section */
export interface ReportVerdict { id: string; title: string; summary: string[]; head: string[]; rows: string[][] }
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
  /** 26.A5: how a numeric signal is read between samples, by signal NAME (every file), as the user
   *  corrected it - "state" (held) or "value" (interpolated); absent = detected (readAs.ts). */
  readAs?: Record<string, "state" | "value">;
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

/* 26.U2: the first eight are Okabe & Ito's colours for colour-blind readers (blue, orange, bluish green,
   vermilion, sky blue, reddish purple, yellow, grey - told apart with any of the common colour vision
   deficiencies), the next twelve their darker / lighter companions. Drawn through chartUtil.ink(), which
   keeps each at 3:1 or more against the plot in either theme (yellow on white, grey on dark). */
export const TRACE_COLORS = [
  "#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7", "#F0E442", "#7F7F7F",
  "#004C7A", "#A86F00", "#00694C", "#9A4200", "#2A86C0", "#9A4F7E",
  "#B0A500", "#4D4D4D", "#3399CC", "#FFB733", "#33CC99", "#FF7A33",
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
