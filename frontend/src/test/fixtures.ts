// T1: small runs for the store's tests (the shape the backend lists them in)
import type { RunInfo, SignalInfo } from "../api";
import { initialWorkspace, useApp } from "../store";

export function sig(run: string, name: string, extra: Partial<SignalInfo> = {}): SignalInfo {
  return { id: `${run}/${name}`, name, samples: 100, ...extra } as SignalInfo;
}
export function run(id: string, names: string[], extra: Partial<RunInfo> = {}): RunInfo {
  return { id, name: `${id}.csv`, path: `/data/${id}.csv`, format: "csv", samples: 100, start: 0, end: 10, timeOffset: 0,
    importSettings: {}, signals: names.map((n) => sig(id, n)), ...extra } as RunInfo;
}
/** A fresh store: one empty tab, these runs, no history. */
export function reset(runs: RunInfo[] = []) {
  useApp.setState({ ws: initialWorkspace(), past: [], future: [], runs, toasts: [], linkRuns: false, quality: {}, compareTol: { default: {}, signals: {} } });
}
