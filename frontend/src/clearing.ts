import { api } from "./api";
import { actions, useApp, type MenuItem } from "./store";
import { activeTab } from "./store";
import { translate } from "./i18n";
import { clearEverything } from "./files";
import type { Workspace } from "./store/model";
import { homeRun } from "./peers";

/**
 * T63: one Clear button, five scopes, from the smallest to everything. All but the last keep the
 * files open and are undone with one click (the toast) or Ctrl+Z:
 *   this tab's plots · the other tabs · all tabs · all tabs + derived signals + in-place edits
 *   (only the data stays) · everything (files closed, asks first).
 */

const uid = (p: string) => `${p}${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

function freshTab() {
  return { id: uid("t"), name: "", rows: 1, cols: 1, plots: [{ id: uid("p"), title: "", signals: [] }], active: 0, linkX: true };
}

/** Views that pointed at plots that are gone: zoom, ranges, the selected plot. */
function forgetViews() {
  useApp.setState({ ranges: {}, yRanges: {}, zoomHistory: {}, selected: null, multi: [], preview: null, yExtents: {} });
}

function undoToast(text: string, undo?: () => Promise<void>) {
  const st = useApp.getState();
  st.toast({ kind: "info", text, undoesWs: true,
    action: { label: translate(st.lang, "undo"), run: undo ?? (async () => useApp.getState().undo()) } });
}

export function closeOtherTabs() {
  const st = useApp.getState();
  if (st.ws.tabs.length < 2) return;
  const n = st.ws.tabs.length - 1;
  st.commit((ws) => { ws.tabs = [activeTab(ws)]; return ws; });
  actions.dropStaleRanges();
  undoToast(translate(st.lang, "clearOtherTabsDone", { n }));
}

export function clearAllTabs() {
  const st = useApp.getState();
  st.commit((ws) => { const t = freshTab(); ws.tabs = [t]; ws.activeTab = t.id; return ws; });
  forgetViews();
  undoToast(translate(st.lang, "clearAllTabsDone"));
}

/** Everything made on the data - tabs, notes, derived signals, in-place edits - goes; the files
 *  stay open as they are. One Undo puts all of it back (formulas recomputed, edits re-applied). */
export async function clearWork() {
  const st = useApp.getState();
  const derived = st.runs.find((r) => r.format === "derived")?.signals ?? [];
  const items = derived.map((s) => ({ name: s.name, op: s.op!, sources: s.sources!, params: s.params }));
  const edited = st.runs.flatMap((r) => r.signals.filter((s) => s.transform).map((s) => s.id));
  const wsBefore: Workspace = structuredClone(st.ws);
  for (const s of derived) await api.deleteDerived(s.name).catch(() => {});
  let previous: Awaited<ReturnType<typeof api.setTransformSpecs>>["previous"] = {};
  if (edited.length) previous = (await api.setTransformSpecs(Object.fromEntries(edited.map((id) => [id, null])))).previous;
  st.commit((ws) => { const t = freshTab(); ws.tabs = [t]; ws.activeTab = t.id; ws.notes = []; return ws; });
  forgetViews();
  useApp.setState({ runs: await api.listRuns(), dataVersion: useApp.getState().dataVersion + 1 });
  undoToast(translate(st.lang, "clearWorkDone", { d: items.length, e: edited.length }), async () => {
    if (items.length) await api.restoreDerived(items);
    if (edited.length) await api.setTransformSpecs(previous);
    useApp.setState({ runs: await api.listRuns(), dataVersion: useApp.getState().dataVersion + 1 });
    useApp.getState().commit(() => structuredClone(wsBefore));
  });
}

/** The menu of the Clear button (and the same entries in Ctrl+K). */
export function clearMenuItems(): MenuItem[] {
  const st = useApp.getState();
  const t = (k: Parameters<typeof translate>[1], p?: Record<string, string | number>) => translate(st.lang, k, p);
  const tabs = st.ws.tabs.length;
  const derived = st.runs.find((r) => r.format === "derived")?.signals.length ?? 0;
  const edits = st.runs.reduce((n, r) => n + r.signals.filter((s) => s.transform).length, 0);
  const files = st.runs.filter((r) => r.format !== "derived").length;
  return [
    { label: t("clearThisTab"), run: actions.clearAllPlots },
    { label: t("clearOtherTabs", { n: Math.max(0, tabs - 1) }), run: closeOtherTabs, disabled: tabs < 2 },
    { label: t("clearAllTabs", { n: tabs }), run: clearAllTabs },
    { label: t("clearWork", { d: derived, e: edits }), run: () => { clearWork(); } },
    { label: "", run: () => {}, sep: true },
    { label: t("clearEverythingN", { f: files }), run: clearEverything, danger: true },
  ];
}

/* Q88: one file's work only, each part on its own - its signals out of every plot (signals made from
   it too), its edits (ƒ) undone, the signals made from it deleted (and whatever was made from those).
   The file stays open; one Undo puts all of it back. */
export interface FileParts { plots?: boolean; edits?: boolean; derived?: boolean }

/** what clearing `parts` of file `runId` would touch (for the menu's numbers and the work itself) */
export function fileWork(runId: string, parts: FileParts) {
  const st = useApp.getState();
  const all = st.runs.find((r) => r.format === "derived")?.signals ?? [];
  const doomed = new Set(parts.derived ? all.filter((d) => homeRun(st.runs, d.id) === runId).map((d) => d.id) : []);
  for (let grew = true; grew;) {
    grew = false;
    for (const d of all) if (!doomed.has(d.id) && d.sources?.some((x) => doomed.has(x))) { doomed.add(d.id); grew = true; }
  }
  const edited = parts.edits ? (st.runs.find((r) => r.id === runId)?.signals.filter((s) => s.transform).map((s) => s.id) ?? []) : [];
  const leaves = (id?: string | null) => !!id && (doomed.has(id) || (!!parts.plots && homeRun(st.runs, id) === runId));
  let plotted = 0;
  for (const t of st.ws.tabs) for (const p of t.plots) plotted += p.signals.filter((s) => leaves(s.sig)).length;
  return { doomed: all.filter((d) => doomed.has(d.id)), edited, leaves, plotted };
}

export async function clearFileWork(runId: string, parts: FileParts) {
  const st = useApp.getState();
  const name = st.runs.find((r) => r.id === runId)?.name ?? runId;
  const { doomed, edited, leaves, plotted } = fileWork(runId, parts);
  const items = doomed.map((s) => ({ name: s.name, op: s.op!, sources: s.sources!, params: s.params }));
  const wsBefore: Workspace = structuredClone(st.ws);
  if (plotted || parts.plots || doomed.length) st.commit((ws) => {
    for (const t of ws.tabs) {
      t.sharedStates = (t.sharedStates ?? []).filter((id) => !leaves(id));
      for (const p of t.plots) {
        p.signals = p.signals.filter((s) => !leaves(s.sig));
        if (leaves(p.xSignal)) p.xSignal = null;
        p.objects = (p.objects ?? []).filter((o) => !Object.values(o).some((v) => typeof v === "string" && leaves(v)));
      }
    }
    return ws;
  });
  for (const s of [...doomed].reverse()) await api.deleteDerived(s.name).catch(() => {});   // the last made first
  let previous: Awaited<ReturnType<typeof api.setTransformSpecs>>["previous"] = {};
  if (edited.length) previous = (await api.setTransformSpecs(Object.fromEntries(edited.map((id) => [id, null])))).previous;
  if (doomed.length || edited.length) useApp.setState({ runs: await api.listRuns(), dataVersion: useApp.getState().dataVersion + 1 });
  undoToast(translate(st.lang, "clearFileDone", { name, p: plotted, e: edited.length, d: doomed.length }), async () => {
    if (items.length) await api.restoreDerived(items);
    if (edited.length) await api.setTransformSpecs(previous);
    useApp.setState({ runs: await api.listRuns(), dataVersion: useApp.getState().dataVersion + 1 });
    useApp.getState().commit(() => structuredClone(wsBefore));
  });
}

/** The file menu's "Clear this file ▸" */
export function clearFileItem(runId: string): MenuItem {
  const st = useApp.getState();
  const t = (k: Parameters<typeof translate>[1], p?: Record<string, string | number>) => translate(st.lang, k, p);
  const p = fileWork(runId, { plots: true }).plotted;
  const e = fileWork(runId, { edits: true }).edited.length;
  const d = fileWork(runId, { derived: true }).doomed.length;
  return {
    label: t("clearFileMenu"), run: () => {},
    items: [
      { label: t("clearFilePlots", { n: p }), run: () => { void clearFileWork(runId, { plots: true }); }, disabled: !p },
      { label: t("clearFileEdits", { n: e }), run: () => { void clearFileWork(runId, { edits: true }); }, disabled: !e },
      { label: t("clearFileDerived", { n: d }), run: () => { void clearFileWork(runId, { derived: true }); }, disabled: !d },
      { label: "", run: () => {}, sep: true },
      { label: t("clearFileAll"), run: () => { void clearFileWork(runId, { plots: true, edits: true, derived: true }); }, disabled: !p && !e && !d },
    ],
  };
}
