/* Live mode (growing files, MAVLink): its settings and status. UI state, never saved. */
import type { MavStatus } from "../../api";
import type { NewFilesMode } from "../types";

export interface LiveSlice {
  streaming: boolean;
  liveAutoStop: number | null;     // live mode stops after this many seconds without new data (null: never)
  liveNewFiles: NewFilesMode;      // new files next to the open ones during live mode
  activity: Record<string, number>;   // live: seconds since each file last received data
  liveLastData: number;            // live: time (ms) new data last arrived, or live mode started
  liveStarting: boolean;           // live: refreshing every file before following them
  liveIdle: number;                 // live: seconds since new data last arrived (updated by each poll)
  mavlink: MavStatus | null;       // T12: the live MAVLink link (UI state, never saved)
  liveMenuOpen: boolean;           // the Live popover (also opened from Ctrl+K)
}

export const liveSlice = (): LiveSlice => ({
  streaming: false,
  liveAutoStop: 60,
  liveNewFiles: "ask",
  activity: {},
  liveLastData: 0,
  liveStarting: false,
  liveIdle: 0,
  mavlink: null,
  liveMenuOpen: false,
});
