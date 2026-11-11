/* Tabs and the plot grid: add / close / move tabs, layout, linked axes, sizes. Through commit. */
import { translate } from "../../i18n";
import { MAX_PLOTS, clone, newPlot, newTab, uid, type Plot, type Tab, type Workspace } from "../model";
import { activeTab, plotHasContent, rangeKey } from "../selectors";
import { useApp } from "../state";
import { viewActions } from "./view";

/** L10: a plot dragged by its handle carries its id under this type (also PLOT_MIME, its index, for N2's swap) */
export const PLOT_ID_MIME = "application/x-sv-plot-id";
/** L10: where a plot is (its tab and cell), or null. */
function findPlotIn(ws: Workspace, plotId: string): { tab: Tab; i: number } | null {
  for (const tab of ws.tabs) { const i = tab.plots.findIndex((p) => p.id === plotId); if (i >= 0) return { tab, i }; }
  return null;
}
const isEmpty = (p: Plot) => !plotHasContent(p) && !p.xSignal;
/** L10: the kind of content a plot holds, for merging: time / XY lines, or the objects of a map / 3D view. */
export const mergeKind = (p: Plot) => (p.mode === "geo" || p.mode === "3d" ? "objects" : p.mode === "xy" ? "xy" : (p.mode ?? "time") === "time" ? "time" : p.mode);
/** L10: the grid a full tab grows to for one more plot (a column while it is not wider than tall, else a
 *  row), within MAX_PLOTS; null when it cannot. */
function grown(tab: Tab): { rows: number; cols: number } | null {
  const r = Math.max(1, tab.rows), c = Math.max(1, tab.cols);
  if (c <= r && r * (c + 1) <= MAX_PLOTS) return { rows: r, cols: c + 1 };
  if ((r + 1) * c <= MAX_PLOTS) return { rows: r + 1, cols: c };
  if (r * (c + 1) <= MAX_PLOTS) return { rows: r, cols: c + 1 };
  return null;
}
/** L10: can `tab` take one more plot - an empty cell (`cell` first), or by growing? */
function hasRoom(tab: Tab, cell?: number): boolean {
  return (cell !== undefined && !!tab.plots[cell] && isEmpty(tab.plots[cell])) || tab.plots.some(isEmpty) || !!grown(tab);
}
/** L10: put `plot` into `tab` (`cell` when empty, else the first empty cell, else after growing the grid,
 *  every old plot keeping its row and column); returns its index. Assumes hasRoom. */
function placeIn(tab: Tab, plot: Plot, cell?: number): number {
  let k = cell !== undefined && tab.plots[cell] && isEmpty(tab.plots[cell]) ? cell : tab.plots.findIndex(isEmpty);
  if (k < 0) {
    const g = grown(tab)!;
    const old = tab.plots, c0 = Math.max(1, tab.cols);
    tab.plots = Array.from({ length: g.rows * g.cols }, (_, n) => {
      const row = Math.floor(n / g.cols), col = n % g.cols;
      return col < c0 ? old[row * c0 + col] ?? newPlot() : newPlot();
    });
    tab.rows = g.rows; tab.cols = g.cols; tab.rowSizes = undefined; tab.colSizes = undefined;
    k = tab.plots.findIndex((p, n) => isEmpty(p) && !old.includes(p) && n >= 0);
  }
  tab.plots[k] = plot;
  return k;
}
const toast = (key: "plotMoveFull" | "plotMergeKinds" | "plotMoveSame", vars: Record<string, string | number> = {}) => {
  const st = useApp.getState();
  st.toast({ kind: "info", text: translate(st.lang, key, vars) });
};

export const layoutActions = {
  /** L10: a plot to another tab (`"new"`: a new tab named after it) - the same plot, so its axes, cursors,
   *  objects, pair and map state go with it; one Undo. The source cell is left empty (the grid does not
   *  reflow); the target tab and the plot become active. `copy` (Ctrl while dropping): a copy goes instead.
   *  Returns false when it cannot (the target full, the same tab) - with a toast that says why. */
  movePlotToTab(plotId: string, tabId: string | "new", cell?: number, copy = false): boolean {
    const st = useApp.getState();
    const at = findPlotIn(st.ws, plotId);
    if (!at) return false;
    if (tabId === at.tab.id && !copy) { toast("plotMoveSame"); return false; }
    const target = tabId === "new" ? null : st.ws.tabs.find((t) => t.id === tabId);
    if (tabId !== "new" && !target) return false;
    if (target && !hasRoom(target, cell)) { toast("plotMoveFull", { tab: target.name || translate(st.lang, "tab"), n: MAX_PLOTS }); return false; }
    st.commit((ws) => {
      const src = findPlotIn(ws, plotId)!;
      const plot = src.tab.plots[src.i];
      const moved: Plot = copy ? { ...clone(plot), id: uid("p") } : plot;
      if (!copy) src.tab.plots[src.i] = newPlot();
      let tab: Tab;
      if (tabId === "new") {
        tab = { ...newTab(ws.tabs.length + 1), name: plot.title || translate(useApp.getState().lang, "plotMovedTab") };
        tab.plots = [moved];
        ws.tabs.push(tab);
        tab.active = 0;
      } else {
        tab = ws.tabs.find((t) => t.id === tabId)!;
        tab.active = placeIn(tab, moved, cell);
      }
      ws.activeTab = tab.id;
      return ws;
    });
    return true;
  },
  /** L10: a plot's lines join another plot (time into time, XY into XY, a map's / 3D view's objects into a
   *  map / 3D view); a line or object already there is not added twice; styles and axes kept. The source
   *  is emptied (its cell stays), or kept for *Copy into*. One Undo; false (with the reason) otherwise. */
  mergePlotInto(plotId: string, targetPlotId: string, keepSource = false): boolean {
    const st = useApp.getState();
    const a = findPlotIn(st.ws, plotId), b = findPlotIn(st.ws, targetPlotId);
    if (!a || !b || plotId === targetPlotId) return false;
    const P = a.tab.plots[a.i], T = b.tab.plots[b.i];
    if (mergeKind(P) !== mergeKind(T)) { toast("plotMergeKinds", { a: String(mergeKind(P)), b: String(mergeKind(T)) }); return false; }
    st.commit((ws) => {
      const src = findPlotIn(ws, plotId)!, dst = findPlotIn(ws, targetPlotId)!;
      const p = src.tab.plots[src.i], q = dst.tab.plots[dst.i];
      for (const s of p.signals) if (!q.signals.some((x) => x.sig === s.sig && !!x.state === !!s.state)) q.signals.push(clone(s));
      if (p.objects?.length) {
        q.objects ??= [];
        for (const o of p.objects) if (!q.objects.some((x) => x.lat === o.lat && x.lon === o.lon)) q.objects.push({ ...clone(o), id: q.objects.some((x) => x.id === o.id) ? uid("o") : o.id });
      }
      if (!keepSource) src.tab.plots[src.i] = newPlot();
      ws.activeTab = dst.tab.id; dst.tab.active = dst.i;
      return ws;
    });
    return true;
  },
  /** N2: two plots of the active tab change places (one Undo). The cells keep their sizes; the active
   *  plot stays the one that moved; everything keyed by plot id (axes, cursors, map / 3D) moves with it. */
  swapPlots(i: number, j: number) {
    const tab0 = activeTab(useApp.getState().ws);
    if (i === j || i < 0 || j < 0 || i >= tab0.plots.length || j >= tab0.plots.length) return;
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      [tab.plots[i], tab.plots[j]] = [tab.plots[j], tab.plots[i]];
      tab.active = tab.active === i ? j : tab.active === j ? i : tab.active;
      return ws;
    });
  },
  /** N2: the active plot swapped with its neighbour in the grid (false: there is none that way). */
  moveActivePlot(dir: "left" | "right" | "up" | "down"): boolean {
    const tab = activeTab(useApp.getState().ws);
    const i = tab.active, c = Math.max(1, tab.cols), r = Math.floor(i / c), col = i % c;
    const rtl = document.documentElement.dir === "rtl";   // left / right as seen on the screen
    const d = dir === "left" ? (rtl ? 1 : -1) : dir === "right" ? (rtl ? -1 : 1) : 0;
    const j = d ? (col + d >= 0 && col + d < c ? i + d : -1) : dir === "up" ? (r > 0 ? i - c : -1) : i + c;
    if (j < 0 || j >= tab.plots.length) return false;
    layoutActions.swapPlots(i, j);
    return true;
  },
  /** Any rows x cols with at most MAX_PLOTS plots. Shrinking removes the extra
   *  plots (their signals go with them); the toast offers Undo. */
  setLayout(rows: number, cols: number) {
    rows = Math.max(1, Math.min(MAX_PLOTS, Math.round(rows)));
    cols = Math.max(1, Math.min(MAX_PLOTS, Math.round(cols)));
    if (rows * cols > MAX_PLOTS) return;
    const st = useApp.getState();
    const before = activeTab(st.ws);
    const n = rows * cols;
    const dropped = before.plots.slice(n).filter((p) => p.signals.length || p.xSignal).length;
    st.commit((ws) => {
      const tab = activeTab(ws);
      tab.rows = rows; tab.cols = cols; tab.rowSizes = undefined; tab.colSizes = undefined;
      while (tab.plots.length < n) tab.plots.push(newPlot());
      tab.plots = tab.plots.slice(0, n);
      tab.active = Math.min(tab.active, n - 1);
      return ws;
    });
    if (dropped) {
      const L = useApp.getState().lang;
      useApp.getState().toast({ kind: "info", text: translate(L, "plotsRemoved", { n: dropped }),
        action: { label: translate(L, "undo"), run: () => useApp.getState().undo() }, undoesWs: true });
    }
  },
  setActivePlot(index: number) {
    const st = useApp.getState();
    const tab = activeTab(st.ws);
    if (index < 0 || index >= tab.plots.length || index === tab.active) return;
    // selection is not an undoable edit
    useApp.setState({ ws: { ...st.ws, tabs: st.ws.tabs.map((t) => (t.id === tab.id ? { ...t, active: index } : t)) } });
  },
  renamePlot(plotId: string, title: string) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => { if (p.id === plotId) p.title = title; }));
      return ws;
    });
  },
  addTab() {
    useApp.getState().commit((ws) => {
      const t = newTab(ws.tabs.length + 1);
      ws.tabs.push(t);
      ws.activeTab = t.id;
      return ws;
    });
  },
  duplicateTab(id: string) {
    useApp.getState().commit((ws) => {
      const src = ws.tabs.find((t) => t.id === id);
      if (!src) return ws;
      const copy: Tab = { ...clone(src), id: uid("t"), name: src.name ? `${src.name} (2)` : "" };
      copy.plots = copy.plots.map((p) => ({ ...p, id: uid("p") }));
      ws.tabs.splice(ws.tabs.indexOf(src) + 1, 0, copy);
      ws.activeTab = copy.id;
      return ws;
    });
  },
  closeTab(id: string) {
    useApp.getState().commit((ws) => {
      if (ws.tabs.length === 1) {
        const t = newTab(1);
        return { tabs: [t], activeTab: t.id };
      }
      const i = ws.tabs.findIndex((t) => t.id === id);
      ws.tabs.splice(i, 1);
      if (ws.activeTab === id) ws.activeTab = ws.tabs[Math.max(0, i - 1)].id;
      return ws;
    });
  },
  renameTab(id: string, name: string) {
    useApp.getState().commit((ws) => {
      const t = ws.tabs.find((x) => x.id === id);
      if (t) t.name = name;
      return ws;
    });
  },
  /** The next / previous tab, wrapping around (Ctrl+PageDown / Ctrl+PageUp, F22). */
  cycleTab(dir: 1 | -1) {
    const { ws } = useApp.getState();
    const i = ws.tabs.findIndex((t) => t.id === ws.activeTab);
    const next = ws.tabs[(i + dir + ws.tabs.length) % ws.tabs.length];
    if (next && next.id !== ws.activeTab) layoutActions.switchTab(next.id);
  },
  switchTab(id: string) {
    const st = useApp.getState();
    useApp.setState({ ws: { ...st.ws, activeTab: id }, selected: null });
  },
  toggleLinkX() {
    useApp.getState().commit((ws) => { const t = activeTab(ws); t.linkX = !t.linkX; return ws; });
  },
  closeOtherTabs(id: string) {
    useApp.getState().commit((ws) => ({ ...ws, tabs: ws.tabs.filter((t) => t.id === id), activeTab: id }));
  },
  moveTab(id: string, toIndex: number) {
    useApp.getState().commit((ws) => {
      const i = ws.tabs.findIndex((t) => t.id === id);
      if (i < 0) return ws;
      const [t] = ws.tabs.splice(i, 1);
      ws.tabs.splice(Math.max(0, Math.min(ws.tabs.length, toIndex)), 0, t);
      return ws;
    });
  },
  setAxisLimits(plotId: string, xlim: [number, number] | null, ylim: [number, number] | null, wholeTab: boolean) {
    const st = useApp.getState();
    st.commit((ws) => {
      const tab = activeTab(ws);
      tab.plots.forEach((p) => { if (p.id === plotId || wholeTab) { p.xlim = xlim; p.ylim = ylim; } });
      return ws;
    });
    const tab = activeTab(useApp.getState().ws);
    tab.plots.forEach((p) => { if (p.id === plotId || wholeTab) viewActions.setRange(rangeKey(tab, p), xlim); });
    const ys = { ...useApp.getState().yRanges };
    tab.plots.forEach((p) => { if (p.id === plotId || wholeTab) { delete ys[p.id]; delete ys[`${tab.id}:y`]; } });
    useApp.setState({ yRanges: ys });
  },
  toggleLinkY() {
    useApp.getState().commit((ws) => { const t = activeTab(ws); t.linkY = !t.linkY; return ws; });
  },
  setSizes(rowSizes: number[] | undefined, colSizes: number[] | undefined) {
    // live resizing is not an undoable step: write directly
    const st = useApp.getState();
    useApp.setState({ ws: { ...st.ws, tabs: st.ws.tabs.map((t) => (t.id === st.ws.activeTab ? { ...t, rowSizes, colSizes } : t)) } });
  },
};
