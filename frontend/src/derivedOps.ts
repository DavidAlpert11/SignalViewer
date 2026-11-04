/* Signals made in Create signals, managed where they are listed (owner, 2026-11-03: a made signal
   could be removed only in the Create panel). One place for both the signal list and the panel:
   delete (with what was made from it, asked first; one Undo puts all of it back), rename (the
   plots and the signals made from it follow), and a formula's text changed in place. */
import { api, type RunInfo } from "./api";
import { useApp } from "./store";
import { translate } from "./i18n";
import { confirmAsk, prompt } from "./components/Overlays";
import { resolveFormula } from "./formulaRefs";
import type { Workspace } from "./store/model";

type Sig = RunInfo["signals"][number];
const tr = (k: Parameters<typeof translate>[1], v?: Record<string, string | number>) => translate(useApp.getState().lang, k, v);
const madeSignals = (): Sig[] => useApp.getState().runs.find((r) => r.format === "derived")?.signals ?? [];
const refresh = async (runs?: RunInfo[]) =>
  useApp.setState({ runs: runs ?? await api.listRuns(), dataVersion: useApp.getState().dataVersion + 1 });

/** The chosen made signals and every one made from them (in the order they were made). */
export function withDependents(ids: string[]): Sig[] {
  const all = madeSignals();
  const doomed = new Set(ids.filter((id) => id.startsWith("derived/")));
  for (let grew = true; grew;) {
    grew = false;
    for (const d of all) if (!doomed.has(d.id) && d.sources?.some((x) => doomed.has(x))) { doomed.add(d.id); grew = true; }
  }
  return all.filter((d) => doomed.has(d.id));
}

/** Every reference to a signal in the workspace, wherever it is kept (plots, X, objects, lanes,
 *  groups...): a walk over the plain data, so a new place that keeps signal ids needs nothing here. */
function mapRefs(ws: Workspace, f: (id: string) => string | null): Workspace {
  const walk = (v: unknown): unknown => {
    if (typeof v === "string") return v.startsWith("derived/") ? f(v) ?? v : v;
    if (Array.isArray(v)) return v.map(walk);
    if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, walk(x)]));
    return v;
  };
  return walk(ws) as Workspace;
}

export async function deleteMadeSignals(ids: string[]) {
  const st = useApp.getState();
  const doomed = withDependents(ids);
  if (!doomed.length) return;
  const extra = doomed.filter((d) => !ids.includes(d.id));
  if (extra.length && !(await confirmAsk(tr("dsDeleteTitle"),
    tr("dsDeleteAlso", { n: extra.length, names: extra.slice(0, 6).map((d) => d.name).join(", ") + (extra.length > 6 ? "…" : "") }),
    tr("dsDeleteN", { n: doomed.length }), true))) return;
  const gone = new Set(doomed.map((d) => d.id));
  const items = doomed.map((s) => ({ name: s.name, op: s.op!, sources: s.sources!, params: s.params }));
  const wsBefore: Workspace = structuredClone(st.ws);
  st.commit((ws) => {
    for (const t of ws.tabs) {
      t.sharedStates = (t.sharedStates ?? []).filter((id) => !gone.has(id));
      for (const p of t.plots) {
        p.signals = p.signals.filter((s) => !gone.has(s.sig));
        if (p.xSignal && gone.has(p.xSignal)) p.xSignal = null;
        p.objects = (p.objects ?? []).filter((o) => !gone.has(o.lat) && !gone.has(o.lon));
      }
    }
    ws.globalStates = (ws.globalStates ?? []).filter((id) => !gone.has(id));
    ws.sigGroups = (ws.sigGroups ?? []).map((g) => ({ ...g, sigs: g.sigs.filter((id) => !gone.has(id)) }));
    return ws;
  });
  for (const s of [...doomed].reverse()) await api.deleteDerived(s.name).catch(() => {});   // the last made first
  useApp.setState({ listSel: useApp.getState().listSel.filter((id) => !gone.has(id)) });
  await refresh();
  st.toast({ kind: "info", undoesWs: true,
    text: doomed.length === 1 ? tr("dsDeletedOne", { name: doomed[0].name }) : tr("dsDeletedN", { n: doomed.length }),
    action: { label: tr("undo"), run: async () => {
      await api.restoreDerived(items);
      await refresh();
      useApp.getState().commit(() => structuredClone(wsBefore));
    } } });
}

export async function renameMadeSignal(id: string) {
  const s = madeSignals().find((x) => x.id === id);
  if (!s) return;
  const v = await prompt(tr("dsRename"), tr("dsRenameLabel"), s.name);
  if (v === null || !v.trim() || v.trim() === s.name) return;
  try {
    const r = await api.renameDerived(s.name, v.trim());
    const st = useApp.getState();
    st.commit((ws) => mapRefs(ws, (x) => (x === id ? r.id : null)));
    useApp.setState({ listSel: st.listSel.map((x) => (x === id ? r.id : x)) });
    await refresh(r.runs);
  } catch (e) { useApp.getState().toast({ kind: "error", text: (e as Error).message }); }
}

/** A formula's text changed in place: the same name, so every plot keeps it. Only for formulas
 *  (Create signals' other operations have their own fields: made again there). */
export async function editMadeFormula(id: string) {
  const s = madeSignals().find((x) => x.id === id);
  const text = typeof s?.params?.text === "string" ? s.params.text : null;
  if (!s || s.op !== "expr" || text === null) return;
  const v = await prompt(tr("dsEditFormula"), s.name, text);
  if (v === null || !v.trim() || v.trim() === text) return;
  const st = useApp.getState();
  const res = resolveFormula(v.trim(), st.runs.map((r) => (r.format === "derived" ? { ...r, signals: r.signals.filter((x) => x.id !== id) } : r)),
    (k, p) => translate(st.lang, k as never, p));
  if (res.error) { st.toast({ kind: "error", text: res.error }); return; }
  const r = await api.restoreDerived([{ name: s.name, op: "expr", sources: res.sources,
    params: { ...s.params, expr: res.expr, text: v.trim(), ...(res.pinned ? { pinned: res.pinned } : {}) } }]);
  if (r.failed.length) st.toast({ kind: "error", text: r.failed[0].message });
  await refresh(r.runs);
}

export const isMadeFormula = (s: Sig) => s.op === "expr" && typeof s.params?.text === "string";
