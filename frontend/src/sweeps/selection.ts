/* What the brush of All runs selects, as a description the server resolves on the whole table (1.29).
   The runs drawn are a sample above the cap, so nothing that turns the brush into a result - Keep,
   Exclude, a group saved from it, Export shown - may collect sets or rows from them. Per set, the page
   is exact (the answer has every set): Show, the keep / exclude steps, hidden groups and the filters on
   per-set columns become the list of sets; the filters on the runs' own columns go to the server
   (svcore/sweep/select.py), a text column's by its labels. */
import type { Col, Filter } from "./model";
import { hasFilter, keeps } from "./filters";
import { sweepApi } from "./api";
import { groupColumn } from "./groups";
import { activeParams, modeColumns, scaleOf, scopeMask, shownAxes, showMask } from "./view";
import { FLAG_COLS } from "./colors";
import { useSweeps, wireQuestion, type Study } from "./state";

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

/** columns of All runs that are one value per set: decided here, over the sets */
const PER_SET = new Set(["#set", "#holds", "#group"]);

/** The description from the runs' columns (what the axes may filter), the sets' columns and the sets
 *  shown (null: every one). Filters on a column the runs do not have are ignored, as on the page. */
export function describeRuns(runCols: Map<string, Col>, filters: Record<string, Filter>, setCols: Map<string, Col>,
  nSets: number, shown: Uint8Array | null): RunSelection {
  const out: Record<string, WireFilter> = {};
  let m: Uint8Array | null = shown ? Uint8Array.from(shown) : null;
  for (const [name, f] of Object.entries(filters)) {
    const c = runCols.get(name);
    if (!c) continue;
    if (PER_SET.has(name)) {
      m ??= new Uint8Array(nSets).fill(1);
      const v = name === "#set" ? null : setCols.get(name)?.values;
      for (let i = 0; i < nSets; i++) if (m[i] && !keeps(f, v ? v[i] : i)) m[i] = 0;
    } else out[name] = wireFilter(c, f);
  }
  if (!m) return { filters: out, sets: null };
  const sets: number[] = [];
  for (let i = 0; i < nSets; i++) if (m[i]) sets.push(i);
  return { filters: out, sets };
}

/** The study's brush in All runs, described: its filters, and the sets Show and the keep / exclude steps
 *  leave on screen. */
export function runSelection(s: Study): RunSelection {
  const a = s.answer;
  const n = a?.sets[0]?.values.length ?? 0;
  const { cols } = modeColumns(s);
  const setCols = new Map((a?.sets ?? []).map((c) => [c.name, c]));
  if (a && s.view.groups?.length) setCols.set("#group", groupColumn(a, s.view.groups));
  const scope = scopeMask(s), show = showMask(s);
  let shown: Uint8Array | null = null;
  if (scope || show) {
    shown = new Uint8Array(n);
    for (let i = 0; i < n; i++) shown[i] = (!scope || scope[i]) && (!show || show[i] === 1) ? 1 : 0;
  }
  return describeRuns(cols, s.view.filters, setCols, n, shown);
}

/** Save the brush as a group. In All runs a brush on a run's own column (a scenario, an output per run) is
 *  not a rule over the sets: the group is the sets the server finds with such runs, frozen. */
export async function saveBrushGroup(s: Study, frozen: boolean, name: string): Promise<void> {
  const st = useSweeps.getState();
  const params = new Set(activeParams(s));
  const perRun = s.view.mode === "runs" && !!s.answer?.runs
    && Object.entries(s.view.filters).some(([c, f]) => hasFilter(f) && !params.has(c));
  if (!perRun || !s.answer) { st.saveGroup(frozen, name); return; }
  const r = await sweepApi.select(s.tableId, wireQuestion(s), runSelection(s));
  const n = s.answer.sets[0]?.values.length ?? 0, m = new Uint8Array(n);
  for (const i of r.sets) if (i < n) m[i] = 1;
  st.addFrozenGroup(name, m);
  st.setView({ filters: {} });
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
