import { useEffect, useRef, useState } from "react";
import uPlot from "uplot";
import { api } from "../api";
import { actions, useApp, type Plot } from "../store";
import { axisStyle, tickValues, useSize } from "./chartUtil";

interface Props { plot: Plot; index: number; onLoading: (b: boolean) => void; onPeaks: (p: Record<string, number>) => void }

/** Magnitude spectrum. Uses the region between the two cursors when they are on, else the whole signal. */
export default function FFTChart({ plot, index, onLoading, onPeaks }: Props) {
  const theme = useApp((s) => s.theme);
  const scale = useApp((s) => s.uiScale);
  const runs = useApp((s) => s.runs);
  const dataVersion = useApp((s) => s.dataVersion);
  const cursor = useApp((s) => s.cursor);
  const wrapRef = useRef<HTMLDivElement>(null);
  const uRef = useRef<uPlot | null>(null);
  const size = useSize(wrapRef);
  const [data, setData] = useState<{ id: string; x: Float64Array; y: Float32Array; peak: number }[]>([]);

  const ids = plot.signals.map((s) => s.sig);
  const idKey = ids.join("|");
  const region = cursor.on && cursor.dual && cursor.t1 !== null && cursor.t2 !== null ? [cursor.t1, cursor.t2] : null;
  const runsKey = runs.map((r) => `${r.id}:${r.timeOffset}:${r.samples}:${r.signals.length}`).join("|");

  useEffect(() => {
    if (!ids.length) { setData([]); onPeaks({}); return; }
    let cancelled = false;
    const h = window.setTimeout(async () => {
      onLoading(true);
      try {
        const r = (await api.fft(ids, plot.fftWindow ?? "hanning", region?.[0] ?? null, region?.[1] ?? null, 4000, plot.fftMethod ?? "fft")).filter((s) => !s.missing && s.n > 0);
        if (!cancelled) { setData(r); onPeaks(Object.fromEntries(r.map((s) => [s.id, s.peak]))); }
      } catch (e) {
        if (!cancelled) useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
      } finally { if (!cancelled) onLoading(false); }
    }, region ? 200 : 60);
    return () => { cancelled = true; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idKey, plot.fftWindow, plot.fftMethod, region?.[0], region?.[1], dataVersion, runsKey]);

  const styleKey = plot.signals.map((s) => `${s.sig}:${s.color}:${s.width}:${s.scale}`).join("|");
  useEffect(() => {
    const host = wrapRef.current;
    uRef.current?.destroy();
    uRef.current = null;
    if (!host || !data.length || size.w < 50 || size.h < 50) return;
    const axis = axisStyle(theme);
    const log = plot.fftLog ?? true;
    const rows = plot.signals.map((ps) => ({ ps, d: data.find((d) => d.id === ps.sig) })).filter((r) => r.d);
    if (!rows.length) return;      // data still belongs to the previous signals: wait for the new data
    const tables = rows.map(({ ps, d }) => {
      const y = Array.from(d!.y, (v) => {
        const m = v * Math.abs(ps.scale);
        return Number.isFinite(m) && (!log || m > 0) ? m : null;
      });
      return [Array.from(d!.x), y] as uPlot.AlignedData;
    });
    const aligned = tables.length === 1 ? tables[0] : uPlot.join(tables, tables.map(() => [1]));
    const opts: uPlot.Options = {
      width: size.w, height: size.h,
      padding: [8, 12, 0, 4],
      legend: { show: false },
      cursor: { y: false, points: { size: 6 }, drag: { x: true, y: false, setScale: true } },
      scales: {
        x: plot.xlim ? { time: false, auto: false, range: () => plot.xlim! } : { time: false },
        y: plot.ylim ? { auto: false, distr: log ? 3 : 1, range: () => plot.ylim! } : log ? { distr: 3 } : { auto: true },
      },
      axes: [{ ...axis, size: 46, label: "Hz", labelSize: 14, labelGap: 2 }, { ...axis, size: 60, values: tickValues }],
      series: [{}, ...rows.map(({ ps }) => ({ stroke: ps.color, width: ps.width, points: { show: false } }))],
    };
    const u = new uPlot(opts, aligned, host);
    uRef.current = u;
    host.addEventListener("mousedown", () => actions.setActivePlot(index), true);
    return () => { u.destroy(); uRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, styleKey, theme, scale, plot.fftLog, size.w > 0 && size.h > 0, plot.xlim?.[0], plot.xlim?.[1], plot.ylim?.[0], plot.ylim?.[1]]);

  useEffect(() => { uRef.current?.setSize({ width: size.w, height: size.h }); }, [size]);
  return <div className="plot-canvas" ref={wrapRef} />;
}
