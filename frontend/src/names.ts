import type { RunInfo } from "./api";

/**
 * File labels for the legend and the file list:
 *  - one data file  -> signal names only (no file name in the legend)
 *  - several files  -> "signal · file.csv"
 *  - same file name in different folders -> add parent folders, one at a time,
 *    until every label is different:  "A/test.csv", "B/test.csv", "x/A/test.csv"...
 * A name the user typed (rename) is kept as is.
 */
const parts = (p: string) => p.split(/[\\/]+/).filter(Boolean);
const base = (p: string) => parts(p).pop() ?? p;

export function uniqueLabels(paths: string[]): string[] {
  const split = paths.map(parts);
  const k = paths.map(() => 1);
  for (let guard = 0; guard < 64; guard++) {
    const labels = split.map((ps, i) => ps.slice(-k[i]).join("/"));
    let changed = false;
    labels.forEach((l, i) => {
      const clash = labels.some((m, j) => j !== i && m === l && paths[j] !== paths[i]);   // same path: numbered below
      if (clash && k[i] < split[i].length) { k[i]++; changed = true; }
    });
    if (!changed) break;
  }
  const labels = split.map((ps, i) => ps.slice(-k[i]).join("/"));
  // the very same file opened twice: number the copies
  const seen = new Map<string, number>();
  return labels.map((l) => { const n = (seen.get(l) ?? 0) + 1; seen.set(l, n); return n > 1 ? `${l} (${n})` : l; });
}

export function dataRuns(runs: RunInfo[]): RunInfo[] {
  return runs.filter((r) => r.format !== "derived");
}

/** Label of each open data file, by run id. */
export function runLabels(runs: RunInfo[]): Map<string, string> {
  const data = dataRuns(runs);
  const auto = uniqueLabels(data.map((r) => r.path));
  const m = new Map<string, string>();
  data.forEach((r, i) => m.set(r.id, r.name && r.name !== base(r.path) && !r.name.endsWith(base(r.path)) ? r.name : auto[i]));
  return m;
}
