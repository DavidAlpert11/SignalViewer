/* Q87: "Add a run with the same work" - open another file and give it everything done on one open
   file: its edits (ƒ), the signals made from it (derived, in order, derived of derived included) and
   its place in the plots - on the same plots (to compare) or in a copy of each tab. Repeatable: a
   third and a fourth run the same way. "Replace the input files" stays the way to SWAP files. */
import { api, type RunInfo } from "./api";
import { openPaths } from "./files";
import { copyDerived, DERIVED, homeRun, mapTo, newSignalLike } from "./peers";
import { uid, useApp, type Tab } from "./store";

export type SameWorkMode = "overlay" | "tabs";
export interface SameWorkResult { to: string; edits: number; derived: number; plots: number; tabs: number; missing: string[] }

const nameOf = (id: string) => id.slice(id.indexOf("/") + 1);
const samePath = (a: string, b: string) => a.replace(/\\/g, "/").toLowerCase() === b.replace(/\\/g, "/").toLowerCase();

/** Every signal of file `from` the work uses (plots, X axes, states, map objects, edits, formulas) -
 *  data names, for the check of a new file before it is opened. */
export function usedNames(from: string): string[] {
  const st = useApp.getState();
  const out = new Set<string>();
  const add = (id?: string | null) => {
    if (!id) return;
    if (id.startsWith(`${DERIVED}/`)) {
      const d = st.runs.find((r) => r.format === DERIVED)?.signals.find((s) => s.id === id);
      (d?.sources ?? []).forEach(add);
    } else if (id.startsWith(`${from}/`)) out.add(nameOf(id));
  };
  for (const t of st.ws.tabs) {
    (t.sharedStates ?? []).forEach(add);
    for (const p of t.plots) {
      p.signals.forEach((s) => add(s.sig)); add(p.xSignal);
      (p.objects ?? []).forEach((o) => Object.values(o).forEach((v) => { if (typeof v === "string" && v.includes("/")) add(v); }));
    }
  }
  st.runs.find((r) => r.id === from)?.signals.forEach((s) => { if (s.transform) out.add(s.name); });
  return [...out];
}

/** Open `path` and give it the work of `from`. Null when the file could not be opened. */
export async function addRunLike(from: string, path: string, mode: SameWorkMode): Promise<SameWorkResult | null> {
  const st0 = useApp.getState();
  const fromRun = st0.runs.find((r) => r.id === from);
  if (!fromRun) return null;
  const before = new Set(st0.runs.map((r) => r.id));
  await openPaths([path], fromRun.importSettings as Record<string, unknown> | undefined);
  let runs: RunInfo[] = useApp.getState().runs;
  const to = runs.find((r) => !before.has(r.id) && r.format !== DERIVED)?.id
    ?? runs.find((r) => r.format !== DERIVED && r.path && samePath(r.path, path))?.id;
  if (!to || to === from) return null;
  const missing = new Set<string>();

  // 1. the edits (ƒ): each signal of `from` that has one -> the same signal of `to`
  const specs: Record<string, NonNullable<RunInfo["signals"][number]["transform"]>> = {};
  for (const s of fromRun.signals) {
    if (!s.transform) continue;
    const m = mapTo(runs, s.id, to);
    if (m) specs[m] = s.transform; else missing.add(s.name);
  }
  if (Object.keys(specs).length) {
    const r = await api.setTransformSpecs(specs);
    useApp.setState({ runs: r.runs, dataVersion: useApp.getState().dataVersion + 1 });
  }

  // 2. the signals made from it, in the order they were made (so derived-of-derived find their sources)
  runs = useApp.getState().runs;
  const made = new Map<string, string>();
  const originals = (runs.find((r) => r.format === DERIVED)?.signals ?? []).filter((d) => homeRun(runs, d.id) === from);
  let derived = 0;
  for (const d of originals) {
    if (mapTo(useApp.getState().runs, d.id, to)) { made.set(d.id, mapTo(useApp.getState().runs, d.id, to)!); continue; }
    try {
      const c = await copyDerived(d.id, to, made);
      if (c) derived++; else missing.add(d.name);
    } catch { missing.add(d.name); }
  }

  // 3. the plots: a signal of `from` -> its counterpart in `to` (undefined: not from that file)
  runs = useApp.getState().runs;
  const counterpart = (id: string): string | null | undefined =>
    homeRun(runs, id) !== from ? undefined : made.get(id) ?? mapTo(runs, id, to);
  let plots = 0, tabs = 0;
  const toName = runs.find((r) => r.id === to)?.name ?? to;
  useApp.getState().commit((ws) => {
    if (mode === "overlay") {
      for (const t of ws.tabs) for (const p of t.plots) {
        let added = false;
        for (const s of [...p.signals]) {
          const c = counterpart(s.sig);
          if (c === undefined) continue;
          if (c === null) { missing.add(nameOf(s.sig)); continue; }
          if (!p.signals.some((x) => x.sig === c)) { p.signals.push(newSignalLike(s, c, ws)); added = true; }
        }
        if (added) plots++;
      }
      return ws;
    }
    const copies: Tab[] = [];
    ws.tabs.forEach((t, k) => {
      const uses = t.plots.some((p) => p.signals.some((s) => counterpart(s.sig) !== undefined) || (p.xSignal && counterpart(p.xSignal) !== undefined));
      if (!uses) return;
      const c: Tab = structuredClone(t);
      c.id = uid("t");
      c.name = `${t.name || `${k + 1}`} · ${toName}`;
      c.sharedStates = (c.sharedStates ?? []).map((id) => swap(id)).filter((x): x is string => !!x);
      for (const p of c.plots) {
        p.id = uid("p");
        p.signals = p.signals.flatMap((s) => { const n = swap(s.sig); return n ? [{ ...s, sig: n }] : []; });
        if (p.xSignal) p.xSignal = swap(p.xSignal);
        for (const o of p.objects ?? []) for (const [k2, v] of Object.entries(o))
          if (typeof v === "string" && v.includes("/") && counterpart(v) !== undefined) (o as unknown as Record<string, unknown>)[k2] = counterpart(v) ?? undefined;
        if (p.signals.length || p.xSignal || p.objects?.length) plots++;
      }
      copies.push(c);
    });
    tabs = copies.length;
    if (copies.length) { ws.tabs.push(...copies); ws.activeTab = copies[0].id; }
    return ws;
  });

  /** in a copied tab: a signal of `from` becomes its counterpart (gone when `to` has none); others stay */
  function swap(id: string): string | null {
    const c = counterpart(id);
    if (c === undefined) return id;
    if (c === null) missing.add(nameOf(id));
    return c;
  }
  return { to, edits: Object.keys(specs).length, derived, plots, tabs, missing: [...missing] };
}
