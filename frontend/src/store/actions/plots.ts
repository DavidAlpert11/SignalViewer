/* Signals and objects in plots: add, remove, move, style, plot modes. Workspace changes, through commit. */
import { translate } from "../../i18n";
import { MAX_PLOTS, TRACE_COLORS, newPlot, uid, type MapObject, type Plot, type PlotMode, type PlotSignal, type Tab } from "../model";
import { activeTab, colorByFile, emptyPlot, findPlot, fitLayout, forgetObjects, newPlotSignal, placePlot, tabFullMessage } from "../selectors";
import { useApp } from "../state";

/** T46 (owner): a signal joining the same-named signal of ANOTHER file in a plot is a comparison -
 *  that group is coloured by file, so "which line is which file" is the colour. */
function sameNameByFile(plot: Plot, sig: string) {
  const name = sig.slice(sig.indexOf("/") + 1), rid = sig.split("/")[0];
  if (plot.signals.some((s) => s.sig !== sig && s.sig.slice(s.sig.indexOf("/") + 1) === name && s.sig.split("/")[0] !== rid))
    colorByFile(plot, useApp.getState().runs);
}

export const plotActions = {
  addSignal(sig: string, plotId?: string) {
    const { commit } = useApp.getState();
    commit((ws) => {
      const tab = activeTab(ws);
      const plot = plotId ? tab.plots.find((p) => p.id === plotId) : tab.plots[tab.active];
      if (!plot || plot.signals.some((s) => s.sig === sig)) return ws;
      if ((plot.mode === "xy" || plot.mode === "geo") && !plot.xSignal) { plot.xSignal = sig; return ws; }
      plot.signals.push(newPlotSignal(sig, ws));
      sameNameByFile(plot, sig);
      if (plotId) tab.active = tab.plots.findIndex((p) => p.id === plotId);
      return ws;
    });
  },
  /** T20: split a plot - a new plot with this signal right after it (to its right or below it),
   *  the grid growing a column or a row when it is full. moveFrom: a legend chip moved out of
   *  that plot (not copied). One undo step. */
  splitPlot(plotId: string, sig: string, side: "right" | "bottom", moveFrom?: string) {
    let full = false;
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      const i = tab.plots.findIndex((p) => p.id === plotId);
      if (i < 0) return ws;
      if (tab.plots.length >= MAX_PLOTS) { full = true; return ws; }
      const src = moveFrom ? tab.plots.find((p) => p.id === moveFrom)?.signals.find((x) => x.sig === sig) : undefined;
      const np: Plot = { id: uid("p"), title: "", signals: [src ? { ...src } : newPlotSignal(sig, ws)] };
      if (moveFrom) { const from = tab.plots.find((p) => p.id === moveFrom); if (from) from.signals = from.signals.filter((x) => x.sig !== sig); }
      tab.plots.splice(i + 1, 0, np);
      const n = tab.plots.length;
      if (n > tab.rows * tab.cols) {
        if (side === "right") { tab.cols += 1; tab.rows = Math.max(1, Math.ceil(n / tab.cols)); }
        else { tab.rows += 1; tab.cols = Math.max(1, Math.ceil(n / tab.rows)); }
        if (tab.rows * tab.cols > MAX_PLOTS) fitLayout(tab);
        tab.rowSizes = undefined; tab.colSizes = undefined;     // sizes were for the old grid
      }
      tab.active = i + 1;
      return ws;
    });
    if (full) tabFullMessage();
  },
  /** Several signals into the active plot (or plotId) as ONE undo step (a nested group). */
  addSignals(ids: string[], plotId?: string) {
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      const plot = plotId ? tab.plots.find((p) => p.id === plotId) : tab.plots[tab.active];
      if (!plot) return ws;
      for (const id of ids) if (!plot.signals.some((s) => s.sig === id)) { plot.signals.push(newPlotSignal(id, ws)); sameNameByFile(plot, id); }
      return ws;
    });
  },
  /** Each signal in a plot of its own (empty plots are used first), as one undo step. */
  addSignalsToNewPlots(ids: string[]) {
    let full = false;
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      for (const id of ids) {
        const p = newPlot();
        p.signals.push(newPlotSignal(id, ws));
        const at = placePlot(tab, p);
        if (at < 0) { full = true; break; }
        tab.active = at;
      }
      return ws;
    });
    if (full) tabFullMessage();
  },
  toggleSignal(sig: string) {
    const ws = useApp.getState().ws;
    const tab = activeTab(ws);
    const plot = tab.plots[tab.active];
    if (plot?.signals.some((s) => s.sig === sig)) plotActions.removeSignal(plot.id, sig);
    else plotActions.addSignal(sig);
  },
  addSignalToNewPlot(sig: string) {
    let full = false;
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      const p = newPlot();
      p.signals.push(newPlotSignal(sig, ws));
      const at = placePlot(tab, p);
      if (at < 0) { full = true; return ws; }
      tab.active = at;
      return ws;
    });
    if (full) tabFullMessage();
  },
  /** T46: every file signal of the plot in its file's colour (shades for several from one file). */
  colorPlotByFile(plotId: string) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => { if (p.id === plotId) colorByFile(p, useApp.getState().runs, true); }));
      return ws;
    });
  },
  removeSignal(plotId: string, sig: string) {
    // with "link files" on, the same-named signals of the other files leave together
    const st0 = useApp.getState();
    const [rid, ...rest] = sig.split("/");
    const name = rest.join("/");
    const linked = st0.linkRuns && rid !== "derived";
    const dataIds = new Set(st0.runs.filter((r) => r.format !== "derived").map((r) => r.id));
    const goes = (x: string) => x === sig || (linked && dataIds.has(x.split("/")[0]) && x.slice(x.indexOf("/") + 1) === name);
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => { if (p.id === plotId) p.signals = p.signals.filter((s) => !goes(s.sig)); }));
      return ws;
    });
    const sel = useApp.getState().selected;
    if (sel && sel.plotId === plotId && sel.sig === sig) useApp.getState().set({ selected: null });
  },
  /** One undoable step for several signals (batch edit). */
  updateSignals(items: { plotId: string; sig: string }[], patch: Partial<PlotSignal>) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        p.signals = p.signals.map((s) => (items.some((i) => i.plotId === p.id && i.sig === s.sig) ? { ...s, ...patch } : s));
      }));
      return ws;
    });
  },
  removeSignals(items: { plotId: string; sig: string }[]) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => { p.signals = p.signals.filter((s) => !items.some((i) => i.plotId === p.id && i.sig === s.sig)); }));
      return ws;
    });
    useApp.setState({ multi: [], selected: null });
  },
  /** Map objects (Undo-able like everything in the workspace). */
  addObject(plotId: string, o: MapObject) {
    useApp.getState().commit((ws) => { const p = findPlot(ws, plotId); if (p) p.objects = [...(p.objects ?? []), o]; return ws; });
  },
  /** T17c: map objects in a new map / 3D plot of the active tab (false: the tab is full). */
  addObjectsToNewPlot(mode: "geo" | "3d", objs: MapObject[], title = ""): boolean {
    let full = false;
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      const at = placePlot(tab, { ...newPlot(), title, mode, objects: objs });
      if (at < 0) { full = true; return ws; }
      tab.active = at;
      return ws;
    });
    if (full) tabFullMessage();
    return !full;
  },
  updateObject(plotId: string, id: string, patch: Partial<MapObject>) {
    useApp.getState().commit((ws) => {
      const p = findPlot(ws, plotId);
      if (p?.objects) p.objects = p.objects.map((o) => (o.id === id ? { ...o, ...patch } : o));
      return ws;
    });
  },
  removeObject(plotId: string, id: string) {
    useApp.getState().commit((ws) => {
      const p = findPlot(ws, plotId);
      if (p?.objects) p.objects = p.objects.filter((o) => o.id !== id);
      if (p) forgetObjects(p);
      return ws;
    });
  },
  updatePlot(plotId: string, patch: Partial<Plot>) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => { if (p.id === plotId) Object.assign(p, patch); }));
      return ws;
    });
  },
  /** T15: the video a video-mode plot plays (a new file keeps the plot's offset). */
  setVideo(plotId: string, path: string) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        if (p.id === plotId) p.video = { path, offset: p.video?.offset ?? 0 };
      }));
      return ws;
    });
  },
  /** T15: data time = video time + offset. */
  setVideoOffset(plotId: string, offset: number) {
    if (!Number.isFinite(offset)) return;
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        if (p.id === plotId && p.video) p.video = { ...p.video, offset: Math.round(offset * 1000) / 1000 };
      }));
      return ws;
    });
  },
  setPlotMode(plotId: string, mode: PlotMode) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        if (p.id !== plotId) return;
        p.mode = mode;
        if (mode === "geo" && !p.xSignal && p.signals.length >= 2) {
          // longitude = the signal named lon / lng / long (else the first one); the rest are latitudes
          const nameOf = (id: string) => id.slice(id.indexOf("/") + 1);
          const lon = p.signals.find((x) => /(^|[^a-z])(lon|lng|long)/i.test(nameOf(x.sig))) ?? p.signals[0];
          p.xSignal = lon.sig;
          p.signals = p.signals.filter((x) => x !== lon);
        } else if (mode === "xy" && !p.xSignal && p.signals.length >= 2) {
          // first signal becomes X, the rest stay as Y
          p.xSignal = p.signals[0].sig;
          p.signals = p.signals.slice(1);
        } else if (mode === "xyz" && p.xSignal) {
          // XYZ has no separate X: the plot's signals in threes are X, Y, Z - the X-Y / map X goes first
          if (!p.signals.some((x) => x.sig === p.xSignal)) p.signals.unshift(newPlotSignal(p.xSignal, ws));
          p.xSignal = null;
        }
      }));
      return ws;
    });
  },
  /** Map plot: choose the (first) latitude signal; further latitude tracks are added like any signal. */
  setGeoLat(plotId: string, sig: string) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        if (p.id !== plotId) return;
        if (p.signals.some((s) => s.sig === sig)) return;
        if (p.signals.length) p.signals[0] = { ...p.signals[0], sig };
        else p.signals.push(newPlotSignal(sig, ws));
      }));
      return ws;
    });
  },
  updateSignal(plotId: string, sig: string, patch: Partial<PlotSignal>) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        if (p.id === plotId) p.signals = p.signals.map((s) => (s.sig === sig ? { ...s, ...patch } : s));
      }));
      return ws;
    });
  },
  /** D-12: with "link files" on, add the same-named signal from every open file. */
  addSignalLinked(sig: string, plotId?: string) {
    const st = useApp.getState();
    const [rid, ...rest] = sig.split("/");
    const name = rest.join("/");
    if (!st.linkRuns || rid === "derived") { plotActions.addSignal(sig, plotId); return; }
    const ids = st.runs.filter((r) => r.format !== "derived" && r.signals.some((x) => x.name === name)).map((r) => `${r.id}/${name}`);
    st.commit((ws) => {
      const tab = activeTab(ws);
      const plot = plotId ? tab.plots.find((p) => p.id === plotId) : tab.plots[tab.active];
      if (!plot) return ws;
      for (const id of ids) if (!plot.signals.some((x) => x.sig === id)) plot.signals.push(newPlotSignal(id, ws));
      return ws;
    });
  },
  duplicateToNewPlot(plotId: string, sig: string) {
    let full = false;
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      const src = tab.plots.find((p) => p.id === plotId)?.signals.find((s) => s.sig === sig);
      if (!src) return ws;
      const p = newPlot();
      p.signals.push({ ...src });
      const at = placePlot(tab, p);
      if (at < 0) { full = true; return ws; }
      tab.active = at;
      return ws;
    });
    if (full) tabFullMessage();
  },
  moveSignal(plotId: string, sig: string, dir: -1 | 1) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        if (p.id !== plotId) return;
        const i = p.signals.findIndex((s) => s.sig === sig), j = i + dir;
        if (i < 0 || j < 0 || j >= p.signals.length) return;
        [p.signals[i], p.signals[j]] = [p.signals[j], p.signals[i]];
      }));
      return ws;
    });
  },
  /** Drag a chip: reorder inside a plot (before `beforeSig`) or move / copy to another plot. */
  dropSignal(fromPlot: string, sig: string, toPlot: string, beforeSig: string | null, copy: boolean) {
    useApp.getState().commit((ws) => {
      const tab = activeTab(ws);
      const src = tab.plots.find((p) => p.id === fromPlot), dst = tab.plots.find((p) => p.id === toPlot);
      if (!src || !dst) return ws;
      const item = src.signals.find((s) => s.sig === sig);
      if (!item) return ws;
      if (!copy || src === dst) src.signals = src.signals.filter((s) => s.sig !== sig);
      if (src !== dst && dst.signals.some((s) => s.sig === sig)) return ws;
      const at = beforeSig ? dst.signals.findIndex((s) => s.sig === beforeSig) : -1;
      if (at >= 0) dst.signals.splice(at, 0, { ...item }); else dst.signals.push({ ...item });
      return ws;
    });
  },
  setAsX(plotId: string, sig: string) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        if (p.id !== plotId) return;
        p.mode = "xy"; p.xSignal = sig;
        p.signals = p.signals.filter((s) => s.sig !== sig);
      }));
      return ws;
    });
  },
  clearPlot(plotId: string) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => { if (p.id === plotId) emptyPlot(p); }));
      return ws;
    });
  },
  /** Empty the plots of this tab (files stay open). Undoable - the toast says so and offers it,
   *  which is what tells it apart from "Clear everything" in the TopBar. */
  clearAllPlots() {
    const st = useApp.getState();
    st.commit((ws) => { const t = activeTab(ws); t.plots.forEach(emptyPlot); return ws; });
    st.toast({ kind: "info", text: translate(st.lang, "plotsCleared"),
      action: { label: translate(st.lang, "undo"), run: () => useApp.getState().undo() }, undoesWs: true });
  },
  /** Take the 3D view away: its objects and 3D settings go, the plot is an empty time plot again (Undo brings it back). */
  remove3d(plotId: string) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => { if (p.id === plotId) { emptyPlot(p); p.mode = "time"; } }));
      return ws;
    });
  },
  removeRunSignals(runId: string) { plotActions.removeSignalRefs((sig) => sig.startsWith(`${runId}/`)); },
  removeSignalRefs(match: (sig: string) => boolean) {
    useApp.getState().commit((ws) => {
      ws.tabs.forEach((t) => t.plots.forEach((p) => {
        p.signals = p.signals.filter((s) => !match(s.sig));
        if (p.xSignal && match(p.xSignal)) p.xSignal = null;
        // an object without its position goes; a lost optional signal just goes from it
        if (p.objects) {
          p.objects = p.objects.filter((o) => !match(o.lat) && !match(o.lon)).map((o) => {
            const c = { ...o };
            for (const k of ["alt", "yaw", "pitch", "roll", "qw", "qx", "qy", "qz"] as const) if (c[k] && match(c[k]!)) c[k] = null;
            return c;
          });
          forgetObjects(p);
        }
      }));
      return ws;
    });
  },
  /** A state signal as a lane on every time plot of the active tab (or not any more). */
  toggleSharedState(sig: string) {
    useApp.getState().commit((ws) => {
      const tab = ws.tabs.find((t) => t.id === ws.activeTab);
      if (!tab) return ws;
      const cur = tab.sharedStates ?? [];
      tab.sharedStates = cur.includes(sig) ? cur.filter((x) => x !== sig) : [...cur, sig];
      return ws;
    });
  },
  /** A new tab with one plot of these signals (health check, log panel). */
  plotSignalsInNewTab(ids: string[], title: string) {
    const st = useApp.getState();
    st.commit((ws) => {
      const p: Plot = { id: uid("p"), title, signals: [] };
      ids.slice(0, 10).forEach((id, i) => p.signals.push({ ...newPlotSignal(id, ws), color: TRACE_COLORS[i % TRACE_COLORS.length] }));
      const tab: Tab = { id: uid("t"), name: title, rows: 1, cols: 1, plots: [p], active: 0, linkX: true };
      ws.tabs.push(tab);
      ws.activeTab = tab.id;
      return ws;
    });
  },
};
