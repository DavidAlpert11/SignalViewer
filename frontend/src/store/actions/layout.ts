/* Tabs and the plot grid: add / close / move tabs, layout, linked axes, sizes. Through commit. */
import { translate } from "../../i18n";
import { MAX_PLOTS, clone, newPlot, newTab, uid, type Tab } from "../model";
import { activeTab, rangeKey } from "../selectors";
import { useApp } from "../state";
import { viewActions } from "./view";

export const layoutActions = {
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
