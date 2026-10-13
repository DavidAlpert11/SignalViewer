import { rangeKey, signalName, useApp, type Plot, type Tab } from "./store";

/** What the server needs to draw / export one plot (reports, images, CSV). */
export function plotSpec(tab: Tab, plot: Plot, index: number, plotLabel: string) {
  const st = useApp.getState();
  const runs = st.runs;
  const range = st.ranges[rangeKey(tab, plot)] ?? null;
  return {
    title: plot.title || plotLabel.replace("{n}", String(index + 1)),
    caption: plot.caption || "",
    mode: plot.mode === "geo" ? "xy" : (plot.mode ?? "time"),   // reports / images draw a map as lon-lat X-Y
    xSignal: plot.xSignal ?? null,
    xLabel: plot.xSignal ? signalName(runs, plot.xSignal, false) : "",
    xyAlign: plot.xyAlign ?? "linear",
    fftWindow: plot.fftWindow ?? "hanning",
    fftMethod: plot.fftMethod ?? "fft",
    fftLog: plot.fftLog ?? true,
    range,
    signals: plot.signals.map((s) => ({
      id: s.sig, label: s.label || signalName(runs, s.sig), color: s.color, width: s.width,
      scale: s.scale, offset: s.offset, state: !!s.state, tOffset: s.tOffset ?? 0, limits: s.limits ?? null,
    })),
  };
}

/** Time range for exporting data: between the cursors, else what is shown, else everything. */
export function exportRange(tab: Tab, plot: Plot): [number, number] | null {
  const st = useApp.getState();
  const c = st.cursor;
  if (c.on && c.dual && c.t1 !== null && c.t2 !== null) return [Math.min(c.t1, c.t2), Math.max(c.t1, c.t2)];
  return st.ranges[rangeKey(tab, plot)] ?? null;
}
