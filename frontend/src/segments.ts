import type { Plot } from "./store";
import { placePlot, rangeKey, tabFullMessage, TRACE_COLORS, uid, useApp } from "./store";

/** T10b: one segment (a value + occurrence of a state signal) found in each run. */
export interface SegWindow { run: string; t0?: number; t1?: number; missing?: "signal" | "segment"; count?: number }
export interface SegmentChoice { title: string; windows: Record<string, [number, number]> }

/**
 * Show a signal of several runs over the same segment, side by side: each run's line is moved by
 * the existing per-signal time offset (tOffset = -segment start), so every run starts at 0. They
 * go to a tab of their own (named after the segment), because the other tabs show the runs on
 * their own clock and a linked time axis cannot show both. newPlot: add a plot instead of
 * replacing the tab's active one (flip through signals in one plot, like the compare list does).
 */
export function showSegmentPlot(name: string, runs: string[], seg: SegmentChoice, newPlot: boolean, colorOf?: (rid: string) => string,
  sigs?: Record<string, string>) {
  const ids = runs.filter((r) => seg.windows[r]);
  if (!ids.length) return;
  const dur = Math.max(...ids.map((r) => seg.windows[r][1] - seg.windows[r][0]));
  let full = false, tabId = "", plotKey = "";
  useApp.getState().commit((ws) => {
    let tab = ws.tabs.find((t) => t.name === seg.title);
    if (!tab) {
      tab = { id: uid("t"), name: seg.title, rows: 1, cols: 1, plots: [{ id: uid("p"), title: "", signals: [] }], active: 0, linkX: true };
      ws.tabs.push(tab);
      newPlot = false;
    }
    ws.activeTab = tab.id;
    const signals = ids.map((rid, i) => ({ sig: `${rid}/${sigs?.[rid] ?? name}`, color: colorOf?.(rid) ?? TRACE_COLORS[i % TRACE_COLORS.length],
      width: 1.5, scale: 1, offset: 0, tOffset: -seg.windows[rid][0] }));
    let plot: Plot | undefined;
    if (newPlot) {
      plot = { id: uid("p"), title: name, signals };
      const at = placePlot(tab, plot);
      if (at < 0) { full = true; return ws; }
      tab.active = at;
      plot = tab.plots[at];
    } else {
      plot = tab.plots[tab.active] ?? tab.plots[0];
      plot.signals = signals; plot.title = name;
    }
    tabId = tab.id; plotKey = rangeKey(tab, plot);
    return ws;
  });
  if (full) { tabFullMessage(); return; }
  if (tabId) useApp.setState({ ranges: { ...useApp.getState().ranges, [plotKey]: [0, dur] } });
}
