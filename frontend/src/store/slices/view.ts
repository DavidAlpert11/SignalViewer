/* How the data is looked at: time and value windows, cursors, playback, map layer. Not undoable. */
import type { CursorState, LogMarkers, PlayMode, PreviewLine, Range, ZoomMode, ZoomStep } from "../types";

export interface ViewSlice {
  ranges: Record<string, Range>;      // key: tab id (linked) or plot id (unlinked)
  cursor: CursorState;
  zoomHistory: Record<string, ZoomStep[]>;
  zoomMode: ZoomMode;              // what drag / wheel zoom: time only, values only, or both
  yRanges: Record<string, Range>;  // value-axis zoom; key: plot id, or "<tab id>:y" when the tab links Y
  yExtents: Record<string, [number, number]>;   // per plot, for linked value axes
  hover: { plotId: string; t: number; vals: Record<string, number | null> } | null;
  /** U6: the time under the pointer over a time plot, also while the cursors are on (hover is
   *  then empty: the legend shows the cursor's values) - the map / 3D draw a ghost there. UI only. */
  pointer: { plotId: string; t: number } | null;
  /** the legend entry under the pointer: its line is drawn on top, the plot's others faint */
  legendFocus: { plotId: string; sig: string } | null;
  /** Dashed lines in one plot, computed but not kept (Create signals > Preview). Several for an
   *  operation with several outputs (the three axes of a frame conversion). */
  preview: { plotId: string; lines: PreviewLine[]; separate?: boolean } | null;   // separate: a plot per line under the grid
  valuesOnPlot: boolean;
  follow: number | null;           // live mode: show only the last N seconds
  playing: boolean;
  playSpeed: number;               // × real time (1 = the recording's own pace, time in seconds)
  /** What the plots show around the time (the cursor): everything + the cursor, from the start up
   *  to the time ("draw": the plot draws itself), or only the last `windowSec` seconds. */
  playMode: PlayMode;
  windowSec: number;
  timelineOpen: boolean;           // the timeline bar shown in full (or as a thin strip)
  logMarkers: LogMarkers;          // log events drawn on time plots: none, warnings + errors, or all
  geoBase: "auto" | "osm" | "esri" | "light" | "dark" | "satellite" | "topo" | "offline";   // map layer
  geoBorders: boolean;            // country borders and names over the offline map and the satellite photos
  linkRuns: boolean;               // D-12: a signal clicked in one file is added from every file
  linkEdits: boolean;              // Q87: an edit or a new signal made on one file is made on the others
}

export const viewSlice = (): ViewSlice => ({
  ranges: {},
  cursor: { on: false, dual: false, t1: null, t2: null },
  zoomHistory: {},
  zoomMode: "x",
  yRanges: {},
  yExtents: {},
  hover: null,
  pointer: null,
  legendFocus: null,
  preview: null,
  valuesOnPlot: false,
  follow: null,
  playing: false,
  playSpeed: 1,
  playMode: "cursor",
  windowSec: 10,
  timelineOpen: true,
  logMarkers: "important",
  geoBase: "auto",
  geoBorders: true,
  linkRuns: false,
  linkEdits: false,
});
