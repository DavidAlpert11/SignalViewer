/* What the brush of All runs selects, as a description the server resolves on the whole table (1.29).
   The runs drawn are a sample above the cap, so nothing that turns the brush into a result - Keep,
   Exclude, a group saved from it, Export shown - may collect sets or rows from them. Per set, the page
   is exact (the answer has every set): Show, the keep / exclude steps, hidden groups and the filters on
   per-set columns become the list of sets; the filters on the runs' own columns go to the server
   (svcore/sweep/select.py), a text column's by its labels. */
import type { Col, Filter } from "./model";
import { hasFilter, keeps, keptMask } from "./filters";
import { sweepApi } from "./api";
import { groupColumn } from "./groups";
import { modeColumns, scaleOf, scopeMask, shownAxes, showMask } from "./view";
import { FLAG_COLS } from "./colors";
import { useSweeps, wireQuestion, type Study } from "./state";
import { filterParts, PER_SET, setFilterColumns } from "./tabs";

export type WireFilter = Filter | { kind: "labels"; labels: string[] };
export interface RunSelection { filters: Record<string, WireFilter>; sets: number[] | null }

/** A filter as the server reads it: a text column's by the labels it keeps (its codes are the page's own). */
export const wireFilter = (c: Col, f: Filter): WireFilter =>
  c.kind === "cat" ? { kind: "labels", labels: (c.labels ?? []).filter((_, i) => keeps(f, i)) } : f;

/** The filters on columns the lines have, as the server reads them (the Data step). */
export function wireFilters(cols: Map<string, Col>, filters: Record<string, Filter>): Record<string, WireFilter> {
  const out: Record<string, WireFilter> = {};
  for (const [name, f] of Object.entries(filters)) { const c = cols.get(name); if (c) out[name] = wireFilter(c, f); }
  return out;
}

/** The description from the runs' columns, the filters on them, the sets' columns and the sets shown (null: every
 *  one). A filter on a per-set column becomes the list of sets; one on a column the page does not have as a run
 *  column (Parameter sets without the runs) goes by the sets' column, else as it is (the server reads a text
 *  column's codes by its own labels; a column it does not have is ignored, as on the page). */
export function describeRuns(runCols: Map<string, Col>, filters: Record<string, Filter>, setCols: Map<string, Col>,
  nSets: number, shown: Uint8Array | null): RunSelection {
  const out: Record<string, WireFilter> = {};
  let m: Uint8Array | null = shown ? Uint8Array.from(shown) : null;
  for (const [name, f] of Object.entries(filters)) {
    if (PER_SET.has(name)) {
      const v = name === "#set" ? null : setCols.get(name)?.values;
      if (name !== "#set" && !v) continue;
      m ??= new Uint8Array(nSets).fill(1);
      for (let i = 0; i < nSets; i++) if (m[i] && !keeps(f, v ? v[i] : i)) m[i] = 0;
      continue;
    }
    const c = runCols.get(name) ?? setCols.get(name);
    out[name] = c ? wireFilter(c, f) : f;
  }
  if (!m) return { filters: out, sets: null };
  const sets: number[] = [];
  for (let i = 0; i < nSets; i++) if (m[i]) sets.push(i);
  return { filters: out, sets };
}

/** What the filters select on the whole table, by the tab each was made in (FT9, sweeps/tabs.ts): those made in
 *  Parameter sets as the sets they keep (exact on the page), those made in All runs and the parameters' as run
 *  filters; `shown`: the sets the view shows (null: every one). */
export function describeStudy(s: Study, shown: Uint8Array | null): RunSelection {
  const a = s.answer, n = a?.sets[0]?.values.length ?? 0;
  const p = filterParts(s), setCols = setFilterColumns(s);
  let m = shown;
  if (Object.keys(p.sets).length) {
    const k = keptMask(setCols, p.sets, n);
    m = m ? m.map((x, i) => x & k[i]) : k;
  }
  const runCols = s.view.mode === "runs" ? modeColumns(s).cols : new Map((a?.runs?.columns ?? []).map((c) => [c.name, c]));
  return describeRuns(runCols, { ...p.both, ...p.runs }, setCols, n, m);
}

/** The study's brush, described: its filters, and the sets Show and the keep / exclude steps leave on screen. */
export function runSelection(s: Study): RunSelection {
  const a = s.answer;
  const n = a?.sets[0]?.values.length ?? 0;
  const scope = scopeMask(s), show = showMask(s);
  let shown: Uint8Array | null = null;
  if (scope || show) {
    shown = new Uint8Array(n);
    for (let i = 0; i < n; i++) shown[i] = (!scope || scope[i]) && (!show || show[i] === 1) ? 1 : 0;
  }
  return describeStudy(s, shown);
}

/** Save the brush as a group. In All runs a brush on a run's own column (a scenario, an output per run) is
 *  not a rule over the sets: the group is the sets the server finds with such runs, frozen. */
export async function saveBrushGroup(s: Study, frozen: boolean, name: string): Promise<void> {
  const st = useSweeps.getState();
  // a filter made in All runs is not a rule over the sets (FT9: whichever tab is on screen)
  const perRun = Object.values(filterParts(s).runs).some(hasFilter);
  if (!perRun || !s.answer) { st.saveGroup(frozen, name); return; }
  const r = await sweepApi.select(s.tableId, wireQuestion(s), runSelection(s));
  const n = s.answer.sets[0]?.values.length ?? 0, m = new Uint8Array(n);
  for (const i of r.sets) if (i < n) m[i] = 1;
  st.addFrozenGroup(name, m);
  st.setView({ filters: {}, filterTab: {} });
}

/** The colouring of the lines as the server counts it per series in a density picture (1.29): a run's own text
 *  column by its labels; a per-set flag (holds, Pareto) or the groups as one code per set; none for a number (the
 *  density is then one colour; the lines drawn one by one keep their colours). */
export function colourSpec(s: Study): { column?: string; sets?: number[]; n: number } | undefined {
  const a = s.answer, by = s.view.colorBy;
  if (!a || !by) return undefined;
  const run = a.runs?.columns.find((c) => c.name === by);
  if (run && run.kind === "cat" && !by.startsWith("#")) return { column: by, n: (run.labels?.length ?? 0) + 1 };
  const set = by === "#group" && s.view.groups?.length ? groupColumn(a, s.view.groups) : a.sets.find((c) => c.name === by);
  if (!set) return undefined;
  if (FLAG_COLS.has(by)) return { sets: Array.from(set.values, (v) => (v === 1 ? 1 : 0)), n: 2 };
  if (set.kind === "cat") {
    const n = set.labels?.length ?? 0;
    return { sets: Array.from(set.values, (v) => (Number.isFinite(v) ? v : n)), n: n + 1 };
  }
  return undefined;
}

/** The plot's axes and their scales, as the server cuts them into cells for a density picture. */
export function axesSpec(s: Study): { column: string; scale: string }[] {
  const { cols } = modeColumns(s);
  return shownAxes(s).map((a) => ({ column: a, scale: scaleOf(s, a, cols.get(a)) }));
}
