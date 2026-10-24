/* Q87: "the same signal in another file" - one definition for everything that links files:
   - a data signal's peer is the signal with the same name in another open data file;
   - a derived signal's peer is a derived signal made by the same operation with the same parameters
     from the peers of its sources, all in one other file (derivative(Speed) of run_a <-> of run_b).
   Used by Link plots (add / remove in every file), Link operations (an edit or a new signal made on
   one file is made on the others) and Add a run with the same work. */
import { api, type RunInfo, type SignalInfo } from "./api";
import { translate } from "./i18n";
import { newPlotSignal, useApp, type PlotSignal, type Workspace } from "./store";

export const DERIVED = "derived";
const runOf = (id: string) => id.slice(0, id.indexOf("/"));
const nameOf = (id: string) => id.slice(id.indexOf("/") + 1);
export const dataRuns = (runs: RunInfo[]) => runs.filter((r) => r.format !== DERIVED);
const derivedRun = (runs: RunInfo[]) => runs.find((r) => r.format === DERIVED);
const sigOf = (runs: RunInfo[], id: string): SignalInfo | undefined => runs.find((r) => r.id === runOf(id))?.signals.find((s) => s.id === id);

/** Q91: the sources a derived signal KEEPS when it is made for another file - `params.pinned`, their
 *  indexes: {run_b.csv:Speed} in an expression of x, the baseline of a Compare difference. The other
 *  sources say which file the signal belongs to and are swapped for that file's. */
export const pinnedOf = (s?: SignalInfo): Set<number> =>
  new Set(Array.isArray(s?.params?.pinned) ? (s!.params!.pinned as unknown[]).filter((i): i is number => typeof i === "number") : []);

/** a derived signal's identity apart from its sources: the operation and its parameters (not the label) */
const opKey = (op?: string, params?: Record<string, unknown>) => {
  const { text: _text, ...rest } = params ?? {};
  return `${op}|${JSON.stringify(Object.keys(rest).sort().map((k) => [k, rest[k]]))}`;
};

/** The data file a signal comes from (a derived signal: the one file all its sources come from), or null. */
export function homeRun(runs: RunInfo[], id: string, depth = 0): string | null {
  if (runOf(id) !== DERIVED) return runOf(id);
  const s = sigOf(runs, id);
  if (!s?.sources?.length || depth > 20) return null;
  const pin = pinnedOf(s);
  const free = s.sources.filter((_x, i) => !pin.has(i));                 // the pinned ones say nothing
  if (!free.length) return null;
  const homes = new Set(free.map((x) => homeRun(runs, x, depth + 1)));
  return homes.size === 1 ? [...homes][0] : null;
}

/** The derived signal made by `op` / `params` from exactly `sources`, if there is one. */
export function findDerived(runs: RunInfo[], op: string, params: Record<string, unknown> | undefined, sources: string[]): string | null {
  const k = opKey(op, params);
  const hit = derivedRun(runs)?.signals.find((s) => opKey(s.op, s.params) === k
    && s.sources?.length === sources.length && s.sources.every((x, i) => x === sources[i]));
  return hit?.id ?? null;
}

/** `id` (of one file) in the file `to`: the same name, or the peer derived signal; null when there is none. */
export function mapTo(runs: RunInfo[], id: string, to: string, depth = 0): string | null {
  if (runOf(id) !== DERIVED) {
    const name = nameOf(id);
    return runs.find((r) => r.id === to)?.signals.some((s) => s.name === name) ? `${to}/${name}` : null;
  }
  const s = sigOf(runs, id);
  if (!s?.sources || !s.op || depth > 20) return null;
  const pin = pinnedOf(s);
  const src = s.sources.map((x, i) => (pin.has(i) ? x : mapTo(runs, x, to, depth + 1)));
  return src.every(Boolean) ? findDerived(runs, s.op, s.params, src as string[]) : null;
}

/** The same signal in every OTHER open data file that has it. */
export function peersOf(runs: RunInfo[], id: string): string[] {
  const home = homeRun(runs, id);
  if (!home) return [];
  return dataRuns(runs).filter((r) => r.id !== home).map((r) => mapTo(runs, id, r.id)).filter((x): x is string => !!x && x !== id);
}

/** Link operations: the signals to edit = these plus their peers (derived signals have no edits). */
export function withEditPeers(ids: string[]): string[] {
  const st = useApp.getState();
  if (!st.linkEdits) return ids;
  return Array.from(new Set(ids.flatMap((id) => (runOf(id) === DERIVED ? [id] : [id, ...peersOf(st.runs, id)]))));
}

/** How many more signals a linked edit of `ids` reaches (for the dialogs' note). */
export const linkedExtra = (ids: string[]) => withEditPeers(ids).length - new Set(ids).size;

/** The name of a derived signal's copy for another file: "name (run_b)" - the file's tag replaces
 *  the original's when the name already ends with it. */
export function peerName(runs: RunInfo[], name: string, from: string | null, to: string): string {
  const fromName = runs.find((r) => r.id === from)?.name;
  const base = fromName && name.endsWith(` (${fromName})`) ? name.slice(0, -fromName.length - 3) : name;
  return `${base} (${runs.find((r) => r.id === to)?.name ?? to})`;
}

/** Make the derived signal `id` again in file `to` (its derived sources first), unless it exists.
 *  `made` maps an original derived id to its copy (filled as it goes). Returns the copy, or null when
 *  `to` lacks a source. */
export async function copyDerived(id: string, to: string, made: Map<string, string> = new Map(), depth = 0): Promise<string | null> {
  if (runOf(id) !== DERIVED) return mapTo(useApp.getState().runs, id, to);
  if (made.has(id)) return made.get(id)!;
  const runs = useApp.getState().runs;
  const s = sigOf(runs, id);
  if (!s?.sources || !s.op || depth > 20) return null;
  const src: string[] = [];
  const pin = pinnedOf(s);
  for (const [i, x] of s.sources.entries()) {
    if (pin.has(i)) { src.push(x); continue; }                            // kept: that file's, whatever the copy
    const m = runOf(x) === DERIVED ? await copyDerived(x, to, made, depth + 1) : mapTo(useApp.getState().runs, x, to);
    if (!m) return null;
    src.push(m);
  }
  const now = useApp.getState().runs;
  const have = findDerived(now, s.op, s.params, src);
  if (have) { made.set(id, have); return have; }
  const r = await api.createDerived(s.op, src, s.params ?? {}, peerName(now, s.name, homeRun(now, id), to));
  useApp.setState({ runs: r.runs });
  made.set(id, r.id);
  return r.id;
}

/** Link operations: a new derived signal `id` is made for every other file too. With Link plots
 *  the copies join every plot the original is in. Returns how many were made; `announce: false`
 *  leaves the message to the caller (one for a whole batch - see announceLinked). */
export async function linkNewDerived(id: string, announce = true): Promise<number> {
  const st = useApp.getState();
  if (!st.linkEdits) return 0;
  const home = homeRun(st.runs, id);
  if (!home) return 0;
  const made: string[] = [];
  try {
    for (const r of dataRuns(st.runs)) {
      if (r.id === home || mapTo(useApp.getState().runs, id, r.id)) continue;      // it exists already
      const c = await copyDerived(id, r.id);
      if (c) made.push(c);
    }
  } catch (e) {
    useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
  }
  if (made.length && useApp.getState().linkRuns) addBeside(id, made);
  if (announce) announceLinked(made.length);
  return made.length;
}

export function announceLinked(n: number) {
  if (n) useApp.getState().toast({ kind: "info", text: translate(useApp.getState().lang, "linkedMade", { n }) });
}

/** Put `ids` into every plot that shows `beside` (one undo step). */
export function addBeside(beside: string, ids: string[]) {
  const st = useApp.getState();
  const inSome = st.ws.tabs.some((t) => t.plots.some((p) => p.signals.some((s) => s.sig === beside)));
  if (!inSome) return;
  st.commit((ws) => {
    for (const t of ws.tabs) for (const p of t.plots) {
      if (!p.signals.some((s) => s.sig === beside)) continue;
      for (const id of ids) if (!p.signals.some((s) => s.sig === id)) p.signals.push(newSignalLike(p.signals.find((s) => s.sig === beside)!, id, ws));
    }
    return ws;
  });
}

// the copy keeps how the original is drawn (width, axis, state lane...) but gets its own colour
export function newSignalLike(src: PlotSignal, id: string, ws: Workspace): PlotSignal {
  const fresh = newPlotSignal(id, ws);
  return { ...src, sig: id, color: fresh.color, label: undefined };
}

/** Q91: signals made from `from` together with another file whose intent is not recorded (made
 *  before 1.13, or a formula whose names fell in two files): no file of their own, but a source -
 *  not pinned - of `from`. Copy the work asks about each of them. */
export function crossFileOf(runs: RunInfo[], from: string): SignalInfo[] {
  return (derivedRun(runs)?.signals ?? []).filter((d) => {
    if (homeRun(runs, d.id) !== null || !d.sources) return false;
    const pin = pinnedOf(d);
    return d.sources.some((x, i) => !pin.has(i) && homeRun(runs, x) === from);
  });
}
