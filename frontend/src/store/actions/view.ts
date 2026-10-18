/* Looking at the data: zoom and its history, cursors, time, playback. UI state (not undoable). */
import { api } from "../../api";
import { revealInspector } from "../inspector";
import { activeTab, rangeKey, recordingExtent } from "../selectors";
import { useApp } from "../state";
import type { Range, ZoomMode, ZoomStep } from "../types";

let _pendingSteps = 0, _stepping = false;

export const viewActions = {
  setRange(key: string, r: Range, opts: { history?: boolean } = {}) {
    const st = useApp.getState();
    const cur = st.ranges[key] ?? null;
    if (cur === r || (cur && r && cur[0] === r[0] && cur[1] === r[1])) return;
    const hist = opts.history === false ? st.zoomHistory
      : { ...st.zoomHistory, [key]: [...(st.zoomHistory[key] ?? []).slice(-49), { x: cur }] };
    useApp.setState({ ranges: { ...st.ranges, [key]: r }, zoomHistory: hist });
  },
  /** Zoom one plot: x window (undefined = leave it) and value window (undefined = leave it,
   *  null = automatic again). One history step for both, so Backspace undoes the whole gesture. */
  setView(xKey: string, x: Range | undefined, yKey: string, y: Range | undefined, opts: { history?: boolean } = {}) {
    const st = useApp.getState();
    const curX = st.ranges[xKey] ?? null, curY = st.yRanges[yKey] ?? null;
    const same = (a: Range, b: Range) => a === b || (!!a && !!b && a[0] === b[0] && a[1] === b[1]);
    const xChange = x !== undefined && !same(curX, x), yChange = y !== undefined && !same(curY, y);
    if (!xChange && !yChange) return;
    const step: ZoomStep = { x: curX, ...(yChange ? { y: { key: yKey, r: curY } } : {}) };
    useApp.setState({
      ranges: xChange ? { ...st.ranges, [xKey]: x! } : st.ranges,
      yRanges: yChange ? { ...st.yRanges, [yKey]: y! } : st.yRanges,
      zoomHistory: opts.history === false ? st.zoomHistory : { ...st.zoomHistory, [xKey]: [...(st.zoomHistory[xKey] ?? []).slice(-49), step] },
    });
  },
  pushZoomStep(xKey: string, step: ZoomStep) {
    const st = useApp.getState();
    useApp.setState({ zoomHistory: { ...st.zoomHistory, [xKey]: [...(st.zoomHistory[xKey] ?? []).slice(-49), step] } });
  },
  setZoomMode(m: ZoomMode) { useApp.setState({ zoomMode: m }); },
  /** Both cursors on [a, b] and every plot of the tab zoomed to it (with some margin). */
  showSpan(a: number, b: number) {
    const st = useApp.getState();
    const tab = activeTab(st.ws);
    const pad = Math.max((b - a) * 0.5, 1);
    const ranges = { ...st.ranges };
    for (const p of tab.plots) ranges[rangeKey(tab, p)] = [a - pad, b + pad];
    useApp.setState({ ranges, cursor: { on: true, dual: b > a, t1: a, t2: b > a ? b : null, active: 1 } });
  },
  /** Put the cursor at time t (log event, parameter change...) and bring t into view in every
   *  plot of the tab that does not show it, keeping each plot's zoom width. */
  goToTime(t: number) {
    const st = useApp.getState();
    const tab = activeTab(st.ws);
    const ranges = { ...st.ranges };
    for (const p of tab.plots) {
      const key = rangeKey(tab, p);
      const r = ranges[key];
      if (r && (t < r[0] || t > r[1])) { const w = r[1] - r[0]; ranges[key] = [t - w / 2, t + w / 2]; }
    }
    useApp.setState({ ranges, cursor: { ...st.cursor, on: true, t1: t, active: 1 } });
  },
  cycleZoomMode() {
    const order: ZoomMode[] = ["x", "y", "xy"];
    const st = useApp.getState();
    useApp.setState({ zoomMode: order[(order.indexOf(st.zoomMode) + 1) % order.length] });
  },
  /** Play / pause. Starts from the beginning of the shown range in draw mode, or
   *  when the cursor already reached the end. */
  togglePlay() {
    const st = useApp.getState();
    if (st.playing) { useApp.setState({ playing: false }); return; }
    // over the whole recording (not just the visible window); from where the time is, or from the
    // start when it is at the end / outside
    const r = recordingExtent(st.runs);
    if (!r) return;
    let t1 = st.cursor.on && st.cursor.t1 !== null ? st.cursor.t1 : r[0];
    if (t1 >= r[1] - (r[1] - r[0]) * 0.001 || t1 < r[0]) t1 = r[0];
    useApp.setState({ cursor: { ...st.cursor, on: true, t1 }, playing: true });
    viewActions.followTime(t1);
  },
  /** Set the time (the cursor) - the timeline, its event marks, Home / End. */
  setTime(t: number) {
    const st = useApp.getState();
    useApp.setState({ cursor: { ...st.cursor, on: true, t1: t, active: 1 } });
  },
  /** Keep the time in view: a zoomed time plot of the active tab whose window no longer holds it
   *  moves to show it (near its left side, so what follows is visible). */
  followTime(t: number) {
    const st = useApp.getState();
    const tab = activeTab(st.ws);
    let ranges: Record<string, Range> | null = null;
    for (const p of tab.plots) {
      if ((p.mode ?? "time") !== "time" && p.mode !== "spec") continue;
      const k = rangeKey(tab, p);
      const r = st.ranges[k];
      if (!r || (t >= r[0] && t <= r[1])) continue;
      const w = r[1] - r[0];
      (ranges ??= { ...st.ranges })[k] = [t - w * 0.1, t + w * 0.9];
    }
    if (ranges) useApp.setState({ ranges });
  },
  /** Arrow keys: move the active cursor `n` recorded samples (n < 0: back) of the selected signal
   *  (else the first one of the active plot). The cursor lands exactly ON a sample, so the values
   *  read are the recorded ones, never interpolated. Only mouse placement interpolates.
   *  Presses that arrive while the server is answering are added up, so no step is lost. */
  stepCursor(n: number) {
    _pendingSteps += n;
    if (_stepping) return;
    _stepping = true;
    (async () => {
      try {
        while (_pendingSteps !== 0) {
          const k = _pendingSteps; _pendingSteps = 0;
          const st = useApp.getState();
          const c = st.cursor;
          const which: "t1" | "t2" = c.dual && c.active === 2 ? "t2" : "t1";
          const cur = c[which];
          if (!c.on || cur === null) return;
          const tb = activeTab(st.ws);
          const plot = tb.plots[tb.active];
          const sel = st.selected && plot && st.selected.plotId === plot.id ? plot.signals.find((x) => x.sig === st.selected!.sig) : undefined;
          const ps = sel ?? plot?.signals[0];
          let sigId = ps?.sig ?? null, off = ps?.tOffset ?? 0;
          if (plot && (plot.mode === "xy" || plot.mode === "geo") && plot.xSignal && !ps) sigId = plot.xSignal;
          if (!sigId) {                       // nothing plotted: fall back to a fixed fraction of the view
            const r = plot ? st.ranges[rangeKey(tb, plot)] : null;
            const run = st.runs.find((x) => x.format !== "derived");
            const span = r ? r[1] - r[0] : run ? run.end - run.start : 1;
            useApp.setState({ cursor: { ...c, [which]: cur + (span / 500) * k } });
            continue;
          }
          const r = await api.neighbor(sigId, cur - off, k);
          const now = useApp.getState().cursor;
          if (r.t !== null && now.on) useApp.setState({ cursor: { ...now, [which]: r.t + off } });
        }
      } catch (e) {
        useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
      } finally { _stepping = false; _pendingSteps = 0; }
    })();
  },
  zoomBack() {
    const st = useApp.getState();
    const tab = activeTab(st.ws);
    const plot = tab.plots[tab.active];
    if (!plot) return;
    const key = rangeKey(tab, plot);
    const h = st.zoomHistory[key] ?? [];
    if (!h.length) return;
    const step = h[h.length - 1];
    useApp.setState({
      ranges: { ...st.ranges, [key]: step.x },
      yRanges: step.y ? { ...st.yRanges, [step.y.key]: step.y.r } : st.yRanges,
      zoomHistory: { ...st.zoomHistory, [key]: h.slice(0, -1) },
    });
  },
  /** After a file was reloaded or replaced: a zoom window that no longer overlaps the data
   *  (the new file covers other times) would show an empty graph although the data changed.
   *  Such windows are dropped, so the graph shows the new data. */
  dropStaleRanges() {
    const st = useApp.getState();
    const data = st.runs.filter((r) => r.format !== "derived" && r.samples > 0);
    if (!data.length) return;
    const lo = Math.min(...data.map((r) => r.start)), hi = Math.max(...data.map((r) => r.end));
    const next = { ...st.ranges };
    let changed = false;
    for (const [k, r] of Object.entries(next)) {
      if (r && (r[1] < lo || r[0] > hi)) { delete next[k]; changed = true; }
    }
    if (changed) useApp.setState({ ranges: next });
  },
  resetZoom() {
    const st = useApp.getState();
    const tab = activeTab(st.ws);
    const next = { ...st.ranges };
    delete next[tab.id];
    tab.plots.forEach((p) => { delete next[p.id]; if (p.xlim) next[rangeKey(tab, p)] = p.xlim; });
    const ys = { ...st.yRanges };
    delete ys[`${tab.id}:y`];
    tab.plots.forEach((p) => { delete ys[p.id]; });
    useApp.setState({ ranges: next, yRanges: ys });
  },
  toggleCursor() {
    const st = useApp.getState();
    const c = st.cursor;
    if (!c.on && c.t1 === null) {
      // place the cursor in the middle of what is visible
      const tab = activeTab(st.ws);
      const plot = tab.plots[tab.active];
      const r = plot ? st.ranges[rangeKey(tab, plot)] : null;
      const run = st.runs.find((r) => r.format !== "derived");
      const mid = r ? (r[0] + r[1]) / 2 : run ? (run.start + run.end) / 2 : 0;
      useApp.setState({ cursor: { ...c, on: true, t1: mid } });
    } else useApp.setState({ cursor: { ...c, on: !c.on } });
    if (useApp.getState().cursor.on) revealInspector();
  },
  toggleDual() {
    const st = useApp.getState();
    const c = st.cursor;
    if (c.dual) { useApp.setState({ cursor: { ...c, dual: false } }); return; }
    // Both cursors must land inside what is SHOWN now. (Before, cursor 2 went 20 % after
    // cursor 1 or back to an old position, which after Play or a zoom is off-screen.)
    const tab = activeTab(st.ws);
    const plot = tab.plots[tab.active];
    const data = st.runs.filter((r) => r.format !== "derived");
    const shown = plot ? st.ranges[rangeKey(tab, plot)] ?? plot.xlim ?? null : null;
    const lo = shown ? shown[0] : data.length ? Math.min(...data.map((r) => r.start)) : 0;
    const hi = shown ? shown[1] : data.length ? Math.max(...data.map((r) => r.end)) : 1;
    const span = hi - lo || 1;
    const inside = (v: number | null) => v !== null && v >= lo && v <= hi;
    const t1 = inside(c.t1) ? c.t1! : lo + span * 0.4;
    let t2 = inside(c.t2) && c.t2 !== t1 ? c.t2! : t1 + span * 0.2;
    if (t2 > hi) t2 = t1 - span * 0.2;          // no room after cursor 1: put cursor 2 before it
    t2 = Math.min(hi, Math.max(lo, t2));
    useApp.setState({ cursor: { on: true, dual: true, t1, t2 } });
    revealInspector();
  },
};
