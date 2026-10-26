/* The time axis of a file - another column as its time, its unit (a scale), its offset - changed
   while working (owner's request, 2026-10-26). The file is read again in its place on the server
   (svcore/time_axis.py, store.set_time_axis); here: what the work on screen does with it - the
   column leaves the plots, positions (cursor, zoom, notes) follow the same rows where that is
   honest, linked files can take the same change, and one Undo puts everything back. */
import { api, type RunInfo, type TimeAxisResult } from "./api";
import { runJob } from "./files";
import { translate } from "./i18n";
import { actions, useApp } from "./store";
import { uid, type Plot, type Tab } from "./store/model";
import type { Range } from "./store/types";
import { DERIVED } from "./peers";

export interface AxisChange { column: string | null; scale: number; ownScale: number; offset: number }

/** Length of a time unit in seconds: the scale that puts a column in that unit into seconds. */
export const UNIT_SECONDS: Record<string, number> = { ns: 1e-9, us: 1e-6, ms: 1e-3, s: 1, min: 60, h: 3600 };

/** The ready conversions of the dialog: "the column is in X, show it in Y" (scale = X / Y). */
export const CONVERSIONS: { id: string; from: string; to: string }[] = [
  { id: "ms-s", from: "ms", to: "s" }, { id: "us-s", from: "us", to: "s" }, { id: "ns-s", from: "ns", to: "s" },
  { id: "min-s", from: "min", to: "s" }, { id: "h-s", from: "h", to: "s" },
  { id: "s-ms", from: "s", to: "ms" }, { id: "s-us", from: "s", to: "us" }, { id: "s-min", from: "s", to: "min" },
];
export const conversionScale = (id: string): number => {
  const c = CONVERSIONS.find((x) => x.id === id);
  return c ? UNIT_SECONDS[c.from] / UNIT_SECONDS[c.to] : 1;
};
/** The conversion a scale is (for showing the current state), or "" for any other number. */
export const conversionOf = (scale: number): string =>
  CONVERSIONS.find((c) => Math.abs(conversionScale(c.id) / scale - 1) < 1e-9)?.id ?? "";

/** Data files (not the derived-signals pseudo-file). */
const dataRuns = (runs: RunInfo[]) => runs.filter((r) => r.format !== DERIVED);

/** How many plot entries show this signal (as a line or as an X axis). */
export function plotUses(sig: string): number {
  let n = 0;
  for (const tab of useApp.getState().ws.tabs) for (const p of tab.plots) {
    n += p.signals.filter((s) => s.sig === sig).length + (p.xSignal === sig ? 1 : 0);
  }
  return n;
}

/** Other open files that could take the same change (Link plots / Link operations on): the ones
 *  that have a column of the same name (column change), or the same time column (unit change). */
export function linkedPeers(runId: string, change: AxisChange): RunInfo[] {
  const st = useApp.getState();
  if (!st.linkRuns && !st.linkEdits) return [];
  const me = st.runs.find((r) => r.id === runId);
  return dataRuns(st.runs).filter((r) => r.id !== runId && r.timeAxis && (change.column
    ? r.timeAxis.canColumn && r.signals.some((s) => s.name === change.column)
    : r.timeAxis.canScale && r.timeAxis.column === me?.timeAxis?.column));
}

/** Positions on the time axis kept by the page: cursor, zoom windows, notes. Only translated when
 *  this is the only data file open - with others, the positions belong to their axis too. */
function positions() {
  const st = useApp.getState();
  const list: number[] = [];
  const at = (v: number | null | undefined) => { list.push(v ?? NaN); return list.length - 1; };
  const cur = { t1: at(st.cursor.t1), t2: at(st.cursor.t2) };
  const ranges = Object.entries(st.ranges).map(([k, r]) => ({ k, i0: at(r ? r[0] : null), i1: at(r ? r[1] : null) }));
  const notes = (st.ws.notes ?? []).map((n) => ({ id: n.id, i: at(n.t), i2: n.t2 !== undefined ? at(n.t2) : -1 }));
  return { list, cur, ranges, notes };
}

async function changeOne(id: string, change: AxisChange, times: number[], label: string): Promise<TimeAxisResult | null> {
  return runJob<TimeAxisResult>("timeAxis", { id, ...change, times }, label);
}

/** Make the change (and on the chosen linked files), then one toast with Undo. */
export async function applyTimeAxis(runId: string, change: AxisChange, peers: string[]) {
  const st = useApp.getState();
  const L = st.lang;
  const run = st.runs.find((r) => r.id === runId);
  if (!run) return;
  const wsBefore = structuredClone(st.ws);
  const rangesBefore = { ...st.ranges }, cursorBefore = { ...st.cursor };
  const single = dataRuns(st.runs).length === 1;
  const pos = single ? positions() : null;
  const label = translate(L, "timeAxisWorking", { name: run.name });
  const res = await changeOne(runId, change, pos?.list ?? [], label);
  if (!res) return;                                           // cancelled
  const done: { id: string; before: TimeAxisResult["before"] }[] = [{ id: runId, before: res.before }];
  const failed: string[] = [];
  for (const pid of peers) {
    const peer = st.runs.find((r) => r.id === pid);
    if (!peer?.timeAxis) continue;
    // a peer keeps its own offset unless its time column changes (then the old one means nothing)
    const pc: AxisChange = { ...change, offset: change.column ? 0 : peer.timeAxis.offset };
    try {
      const r = await changeOne(pid, pc, [], translate(L, "timeAxisWorking", { name: peer.name }));
      if (r) done.push({ id: pid, before: r.before });
    } catch { failed.push(peer.name); }
  }
  // the new time columns are not signals any more: out of the plots (Undo brings them back)
  if (change.column) {
    const gone = new Set([runId, ...done.map((d) => d.id)].map((id) => `${id}/${change.column}`));
    if ([...gone].some((g) => plotUses(g))) actions.removeSignalRefs((sig) => gone.has(sig));
  }
  // positions: the same rows on the new axis; a position with no honest place goes
  let lost = 0;
  if (pos) {
    const v = (i: number) => (i >= 0 ? res.times[i] ?? null : null);
    const cursor = { ...useApp.getState().cursor };
    for (const k of ["t1", "t2"] as const) {
      const was = cursorBefore[k];
      if (was === null) continue;
      cursor[k] = v(pos.cur[k]);
      if (cursor[k] === null) lost++;
    }
    if (cursor.t1 === null && cursor.t2 === null) cursor.on = false;
    const ranges: Record<string, Range> = {};
    for (const r of pos.ranges) {
      const a = v(r.i0), b = v(r.i1);
      if (a !== null && b !== null && b > a) ranges[r.k] = [a, b];
      else if (rangesBefore[r.k]) lost++;
    }
    useApp.setState({ cursor, ranges, zoomHistory: {} });
    let notesChanged = false;
    const notes = (wsBefore.notes ?? []).map((n, i) => {
      const p = pos.notes[i];
      const t = v(p.i), t2 = p.i2 >= 0 ? v(p.i2) : null;
      if (t === null) { lost++; return n; }                   // kept where it was: the user decides
      if (t !== n.t || (t2 !== null && t2 !== n.t2)) notesChanged = true;
      return { ...n, t, ...(t2 !== null ? { t2 } : {}) };
    });
    if (notesChanged) useApp.getState().commit((ws) => { ws.notes = notes; return ws; });
  }
  useApp.setState({ runs: await api.listRuns(), dataVersion: useApp.getState().dataVersion + 1 });
  if (!pos) actions.dropStaleRanges();
  const parts = [translate(L, "timeAxisDone", { name: run.name })];
  if (done.length > 1) parts.push(translate(L, "timeAxisDonePeers", { n: done.length - 1 }));
  if (lost) parts.push(translate(L, "timeAxisLostPositions", { n: lost }));
  if (failed.length) parts.push(translate(L, "timeAxisPeerFailed", { names: failed.join(", ") }));
  useApp.getState().toast({
    kind: failed.length ? "error" : "info", text: parts.join(" "), ms: 15000,
    action: { label: translate(L, "undo"), run: async () => {
      try {
        for (const d of done.slice().reverse()) {
          const peer = useApp.getState().runs.find((r) => r.id === d.id);
          await changeOne(d.id, { column: d.before.column, scale: d.before.scale, ownScale: d.before.ownScale, offset: d.before.offset }, [],
            translate(L, "timeAxisWorking", { name: peer?.name ?? "" }));
        }
        useApp.getState().commit(() => structuredClone(wsBefore));
        useApp.setState({ ranges: rangesBefore, cursor: cursorBefore, zoomHistory: {},
          runs: await api.listRuns(), dataVersion: useApp.getState().dataVersion + 1 });
      } catch (e) {
        useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
      }
    } },
  });
}

/** The alternative for a column that goes up and down: an X-Y plot with it on the X axis, in a
 *  new tab (nothing about the file changes). */
export function xyInstead(runId: string, column: string) {
  const st = useApp.getState();
  st.commit((ws) => {
    const p: Plot = { id: uid("p"), title: column, signals: [], mode: "xy", xSignal: `${runId}/${column}` };
    const tab: Tab = { id: uid("t"), name: column, rows: 1, cols: 1, plots: [p], active: 0, linkX: true };
    ws.tabs.push(tab);
    ws.activeTab = tab.id;
    return ws;
  });
  st.toast({ kind: "info", text: translate(st.lang, "timeAxisXyMade", { name: column }) });
}
