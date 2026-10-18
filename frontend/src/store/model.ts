/* ----------------------------------------------------------------------------
   Workspace = everything the user arranges (tabs, plots, signal styling).
   Every change goes through `commit`, which records it for Undo / Redo.
   Signals are referenced by stable ids "<runId>/<name>", never by index.
---------------------------------------------------------------------------- */

export interface PlotSignal { sig: string; color: string; width: number; scale: number; offset: number; label?: string; state?: boolean; tOffset?: number;
  /** T13: pass / fail limits on the plotted value (null / absent = no limit on that side) */
  limits?: { lo?: number | null; hi?: number | null } }  // state: drawn as state markers only (no line)
export type PlotMode = "time" | "xy" | "fft" | "geo" | "spec" | "3d" | "env" | "xyz" | "video";   // env: Monte-Carlo envelope (T14); xyz: plain 3D (T17c); video: T15
export interface Plot {
  id: string; title: string; signals: PlotSignal[];
  mode?: PlotMode;                 // default "time"
  xSignal?: string | null;         // X-Y: signal on the horizontal axis (geo: longitude; the plot's signals are latitudes)
  xyAlign?: "linear" | "nearest";
  fftWindow?: "hanning" | "hamming" | "blackman" | "none";
  fftLog?: boolean;
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
