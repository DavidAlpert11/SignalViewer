/* What the backend told us about the open files, and work in progress. Not saved. */
import type { LogInfo, RunInfo } from "../../api";

export interface DataSlice {
  runs: RunInfo[];
  dataVersion: number;
  busy: number;
  decimation: Record<string, { shown: number; total: number }>;
  cvals: Record<string, [number | null, number | null]>;   // raw values at cursor 1 / 2
  jobs: { id: string; label: string; progress: number; phase: string }[];
  logs: Record<string, LogInfo>;   // flight-log parameters / events per file (ArduPilot .bin), fetched on demand
  recent: import("../../api").RecentItem[];
}

export const dataSlice = (): DataSlice => ({
  runs: [],
  dataVersion: 0,
  busy: 0,
  decimation: {},
  cvals: {},
  jobs: [],
  logs: {},
  recent: [],
});
