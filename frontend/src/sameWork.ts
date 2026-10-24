/* Q87 / Q88: "Copy the work to another file" - give a file (open already, or opened now) what was
   done on one open file, each part on its own: its edits (ƒ), the signals made from it (derived, in
   order, derived of derived included) and its place in the plots - on the same plots (to compare)
   or in a copy of each tab. Repeatable for more files. "Replace the input files" SWAPS files. */
import { api, type RunInfo } from "./api";
import { openPaths } from "./files";
import { copyDerived, DERIVED, findDerived, homeRun, mapTo, newSignalLike, peerName, pinnedOf } from "./peers";
import { fitLayout, MAX_PLOTS, uid, useApp, type Plot, type Tab } from "./store";

export type SameWorkMode = "none" | "overlay" | "beside" | "tabs";
/** what to copy: each part on its own (Q88) */
export interface CopyParts { edits: boolean; derived: boolean; plots: SameWorkMode;
  /** Q91: signals of `from` and another file whose intent is not recorded (crossFileOf), to make
   *  for the target anyway - `from`'s sources swapped, the others kept */
  cross?: string[] }
/** the file that gets the work: one already open, or a file to open */
export type CopyTarget = { run: string } | { path: string };
export interface SameWorkResult { to: string; edits: number; derived: number; plots: number; tabs: number; besideFull: number; missing: string[] }

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

/** Give `target` the chosen parts of the work of `from`. Null when the file could not be opened. */
export async function copyWork(from: string, target: CopyTarget, parts: CopyParts): Promise<SameWorkResult | null> {
  const st0 = useApp.getState();
  const fromRun = st0.runs.find((r) => r.id === from);
  if (!fromRun) return null;
  let to: string | undefined;
  if ("run" in target) to = target.run;
  else {
    const before = new Set(st0.runs.map((r) => r.id));
    await openPaths([target.path], fromRun.importSettings as Record<string, unknown> | undefined);
    const now = useApp.getState().runs;
    to = now.find((r) => !before.has(r.id) && r.format !== DERIVED)?.id
      ?? now.find((r) => r.format !== DERIVED && r.path && samePath(r.path, target.path))?.id;
  }
  let runs: RunInfo[] = useApp.getState().runs;
  if (!to || to === from || !runs.some((r) => r.id === to)) return null;
  const missing = new Set<string>();

  // 1. the edits (ƒ): each signal of `from` that has one -> the same signal of `to`
  const specs: Record<string, NonNullable<RunInfo["signals"][number]["transform"]>> = {};
  if (parts.edits) for (const s of fromRun.signals) {
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
  if (parts.derived) for (const d of originals) {
    if (mapTo(useApp.getState().runs, d.id, to)) { made.set(d.id, mapTo(useApp.getState().runs, d.id, to)!); continue; }
    try {
      const c = await copyDerived(d.id, to, made);
      if (c) derived++; else missing.add(d.name);
    } catch { missing.add(d.name); }
  }

  // 2b. (Q91) the chosen signals of `from` and another file: `from`'s sources swapped, the others
  //     kept - and recorded as kept (pinned), so from now on they belong to one file like any other
  if (parts.cross?.length) for (const id of parts.cross) {
    const now = useApp.getState().runs;
    const d = now.find((r) => r.format === DERIVED)?.signals.find((x) => x.id === id);
    if (!d?.sources || !d.op || made.has(id)) continue;
    const pin = pinnedOf(d);
    const src: string[] = [], keep: number[] = [];
    let ok = true;
    for (const [i, x] of d.sources.entries()) {
      if (pin.has(i) || homeRun(now, x) !== from) { src.push(x); keep.push(i); continue; }
      const m = x.startsWith(`${DERIVED}/`) ? await copyDerived(x, to, made) : mapTo(now, x, to);
      if (!m) { ok = false; break; }
      src.push(m);
    }
    if (!ok) { missing.add(d.name); continue; }
    const params = { ...(d.params ?? {}), pinned: keep };
    const have = findDerived(useApp.getState().runs, d.op, params, src);
    if (have) { made.set(id, have); continue; }
    try {
      const r = await api.createDerived(d.op, src, params, peerName(useApp.getState().runs, d.name, from, to));
      useApp.setState({ runs: r.runs });
      made.set(id, r.id); derived++;
    } catch { missing.add(d.name); }
  }

  // 3. the plots: a signal of `from` -> its counterpart in `to` (undefined: not from that file)
  runs = useApp.getState().runs;
  // undefined: not from `from` (stays as it is) · null: `to` has no such signal (reported) ·
  // "": a signal made from `from` that was not copied and has no copy already (left out quietly)
  const counterpart = (id: string): string | null | undefined => {
    if (made.has(id)) return made.get(id)!;                              // incl. the chosen cross-file ones
    if (homeRun(runs, id) !== from) return undefined;
    const c = made.get(id) ?? mapTo(runs, id, to!);
    return c === null && !parts.derived && id.startsWith(`${DERIVED}/`) ? "" : c;
  };
  let plots = 0, tabs = 0, besideFull = 0;
  const toName = runs.find((r) => r.id === to)?.name ?? to;
  if (parts.plots !== "none") useApp.getState().commit((ws) => {
    if (parts.plots === "overlay") {
      for (const t of ws.tabs) for (const p of t.plots) {
        let added = false;
        for (const s of [...p.signals]) {
          const c = counterpart(s.sig);
          if (c === undefined || c === "") continue;
          if (c === null) { missing.add(nameOf(s.sig)); continue; }
          if (!p.signals.some((x) => x.sig === c)) { p.signals.push(newSignalLike(s, c, ws)); added = true; }
        }
        if (added) plots++;
      }
      return ws;
    }
    const usesPlot = (p: Plot) => p.signals.some((s) => counterpart(s.sig) !== undefined) || (!!p.xSignal && counterpart(p.xSignal) !== undefined);
    /** a copy of plot `p` for `to`: its signals of `from` swapped (others stay), new id */
    const copyPlot = (p: Plot): Plot => {
      const c: Plot = structuredClone(p);
      c.id = uid("p");
      c.signals = c.signals.flatMap((s) => { const n = swap(s.sig); return n ? [{ ...s, sig: n }] : []; });
      if (c.xSignal) c.xSignal = swap(c.xSignal);
      for (const o of c.objects ?? []) for (const [k2, v] of Object.entries(o))
        if (typeof v === "string" && v.includes("/") && counterpart(v) !== undefined) (o as unknown as Record<string, unknown>)[k2] = counterpart(v) || undefined;
      return c;
    };
    const copyTab = (t: Tab, k: number): Tab => {
      const c: Tab = structuredClone(t);
      c.id = uid("t");
      c.name = `${t.name || `${k + 1}`} · ${toName}`;
      c.sharedStates = (c.sharedStates ?? []).map((id) => swap(id)).filter((x): x is string => !!x);
      c.plots = t.plots.map(copyPlot);
      plots += c.plots.filter((p) => p.signals.length || p.xSignal || p.objects?.length).length;
      return c;
    };
    const copies: Tab[] = [];
    ws.tabs.forEach((t, k) => {
      if (!t.plots.some(usesPlot)) return;
      if (parts.plots === "beside") {
        // each plot that shows `from` gets its copy right after it, in the same tab
        const n = t.plots.filter(usesPlot).length;
        if (t.plots.length + n <= MAX_PLOTS) {
          const activeId = t.plots[t.active]?.id;
          const allOfThem = n === t.plots.length;
          t.plots = t.plots.flatMap((p) => (usesPlot(p) ? [p, copyPlot(p)] : [p]));
          t.active = Math.max(0, t.plots.findIndex((p) => p.id === activeId));
          t.rowSizes = undefined; t.colSizes = undefined;
          if (allOfThem && t.cols === 1) { t.cols = 2; t.rows = Math.ceil(t.plots.length / 2); }   // each one and its copy side by side
          else fitLayout(t);
          plots += n;
          return;
        }
        besideFull++;                           // no room for the copies in this tab: a copy of the tab
      }
      copies.push(copyTab(t, k));
    });
    tabs = copies.length;
    if (copies.length) { ws.tabs.push(...copies); if (parts.plots === "tabs") ws.activeTab = copies[0].id; }
    return ws;
  });

  /** in a copied tab: a signal of `from` becomes its counterpart (gone when `to` has none); others stay */
  function swap(id: string): string | null {
    const c = counterpart(id);
    if (c === undefined) return id;
    if (c === null) missing.add(nameOf(id));
    return c || null;
  }
  return { to, edits: Object.keys(specs).length, derived, plots, tabs, besideFull, missing: [...missing] };
}
