import { runsDataKey } from "../values";
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
  const [orderHz, setOrderHz] = useState<number | null>(null);    // T16b: the mean rotation rate, rev/s

  const ids = plot.signals.map((s) => s.sig);
  const idKey = ids.join("|");
  const region = cursor.on && cursor.dual && cursor.t1 !== null && cursor.t2 !== null ? [cursor.t1, cursor.t2] : null;
  const runsKey = runsDataKey(runs);

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

  // T16b: the rotation signal's mean over the same window as the spectrum
  const ord = plot.fftOrders;
  useEffect(() => {
    if (!ord?.sig) { setOrderHz(null); return; }
    let off = false;
    api.stats([ord.sig], region?.[0] ?? null, region?.[1] ?? null).then((r) => {
      const m = r.stats[ord.sig]?.mean;
      if (!off) setOrderHz(typeof m === "number" && Number.isFinite(m) && m > 0 ? (ord.unit === "rpm" ? m / 60 : m) : null);
    }).catch(() => { if (!off) setOrderHz(null); });
    return () => { off = true; };
  }, [ord?.sig, ord?.unit, region?.[0], region?.[1], dataVersion, runsKey]);

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
      plugins: orderHz ? [orderMarks(orderHz, ord?.blades ?? 0, axis.stroke as string)] : [],
    };
    const u = new uPlot(opts, aligned, host);
    uRef.current = u;
    host.addEventListener("mousedown", () => actions.setActivePlot(index), true);
    return () => { u.destroy(); uRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, styleKey, theme, scale, plot.fftLog, size.w > 0 && size.h > 0, plot.xlim?.[0], plot.xlim?.[1], plot.ylim?.[0], plot.ylim?.[1], orderHz, ord?.blades]);

  useEffect(() => { uRef.current?.setSize({ width: size.w, height: size.h }); }, [size]);
  // data-orders: the marked base frequency (Hz) - what the marks are drawn at, readable by tests / tools
  return <div className="plot-canvas" ref={wrapRef} data-orders={orderHz ? orderHz.toFixed(3) : undefined} />;
}

/** T16b: vertical marks at 1x, 2x, 3x the rotation rate f (rev/s) and, with blades, at the
 *  blade-pass frequency (blades x f) - where vibration from the motors / propellers shows. */
function orderMarks(f: number, blades: number, color: string): uPlot.Plugin {
  const marks = [1, 2, 3].map((k) => ({ hz: k * f, label: `${k}×`, dash: [4, 3] }));
  if (blades > 1 && ![1, 2, 3].includes(blades)) marks.push({ hz: blades * f, label: `BP ${blades}×`, dash: [1, 2] });
  else if (blades > 1) marks[blades - 1].label += ` BP`;
  return {
    hooks: {
      draw: [(u: uPlot) => {
        const ctx = u.ctx;
        const { top, height } = u.bbox;
        const pr = devicePixelRatio || 1;
        ctx.save();
        ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = pr;
        ctx.font = `${Math.round(11 * pr)}px system-ui, sans-serif`;
        ctx.textBaseline = "top";
        for (const m of marks) {
          const x = u.valToPos(m.hz, "x", true);
          if (!Number.isFinite(x) || x < u.bbox.left || x > u.bbox.left + u.bbox.width) continue;
          ctx.setLineDash(m.dash.map((d) => d * pr));
          ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + height); ctx.stroke();
          ctx.fillText(m.label, x + 3 * pr, top + 2 * pr);
        }
        ctx.restore();
      }],
    },
  };
}
