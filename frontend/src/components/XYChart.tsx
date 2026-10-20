import { runsDataKey } from "../values";
import { useEffect, useRef, useState } from "react";
import uPlot from "uplot";
import { api } from "../api";
import { actions, shownSpan, signalName, useApp, type Plot } from "../store";
import { axisStyle, tickValues, dpr, indexSpan, orderedLinesIn, PLOT_THEME, useSize, wheelZoom } from "./chartUtil";

interface Props { plot: Plot; index: number; onLoading: (b: boolean) => void; emptyText: string }

/** X-Y plot: Y signals aligned onto the X signal's sample times; zoom on both axes. */
export default function XYChart({ plot, index, onLoading, emptyText }: Props) {
  const theme = useApp((s) => s.theme);
  const scale = useApp((s) => s.uiScale);
  const runs = useApp((s) => s.runs);
  const dataVersion = useApp((s) => s.dataVersion);
  const cursor = useApp((s) => s.cursor);
  const cvals = useApp((s) => s.cvals);
  const wrapRef = useRef<HTMLDivElement>(null);
  const uRef = useRef<uPlot | null>(null);
  const size = useSize(wrapRef);
  const [data, setData] = useState<{ id: string; x: Float64Array; y: Float32Array; t: Float64Array }[]>([]);
  const playMode = useApp((s) => s.playMode);
  const windowSec = useApp((s) => s.windowSec);
  const markRef = useRef({ cursor, cvals, playMode, windowSec });
  markRef.current = { cursor, cvals, playMode, windowSec };

  const ys = plot.signals.map((s) => s.sig);
  const yKey = ys.join("|");
  const runsKey = runsDataKey(runs);

  useEffect(() => {
    if (!plot.xSignal || !ys.length) { setData([]); return; }
    let cancelled = false;
    const h = window.setTimeout(async () => {
      onLoading(true);
      try {
        const r = await api.xy(plot.xSignal!, ys, plot.xyAlign ?? "linear", null, null);
        if (!cancelled) setData(r.filter((s) => !s.missing));
      } catch (e) {
        if (!cancelled) useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
      } finally { if (!cancelled) onLoading(false); }
    }, 60);
    return () => { cancelled = true; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plot.xSignal, yKey, plot.xyAlign, dataVersion, runsKey]);

  const styleKey = plot.signals.map((s) => `${s.sig}:${s.color}:${s.width}:${s.scale}:${s.offset}`).join("|");
  useEffect(() => {
    const host = wrapRef.current;
    uRef.current?.destroy();
    uRef.current = null;
    if (!host || !data.length || size.w < 50 || size.h < 50 || !plot.xSignal) return;
    const pt = PLOT_THEME[theme];
    const axis = axisStyle(theme);
    const rows = plot.signals.map((ps) => ({ ps, d: data.find((d) => d.id === ps.sig) })).filter((r) => r.d);
    if (!rows.length) return;      // data still belongs to the previous signals: wait for the new data
    const aligned = [null, ...rows.map(({ ps, d }) => {
      const y = Array.from(d!.y, (v) => (Number.isFinite(v) ? v * ps.scale + ps.offset : null));
      return [Array.from(d!.x), y];
    })] as unknown as uPlot.AlignedData;

    const drawMarks = (u: uPlot) => {
      const { cursor: c, cvals: cv } = markRef.current;
      if (!c.on || !plot.xSignal) return;
      const xv = cv[plot.xSignal]?.[0];
      if (xv === null || xv === undefined) return;
      const ctx = u.ctx;
      ctx.save();
      rows.forEach(({ ps }) => {
        const yv = cv[ps.sig]?.[0];
        if (yv === null || yv === undefined) return;
        const cx = u.valToPos(xv, "x", true), cy = u.valToPos(yv * ps.scale + ps.offset, "y", true);
        ctx.beginPath(); ctx.arc(cx, cy, 5 * dpr(), 0, Math.PI * 2);
        ctx.fillStyle = pt.amber; ctx.fill();
        ctx.lineWidth = 1.5 * dpr(); ctx.strokeStyle = pt.amberInk; ctx.stroke();
      });
      ctx.restore();
    };

    const opts = {
      mode: 2,
      width: size.w, height: size.h,
      padding: [8, 12, 0, 4],
      legend: { show: false },
      cursor: { drag: { x: true, y: true, uni: 20, setScale: true }, points: { show: false } },
      scales: {
        x: plot.xlim ? { time: false, auto: false, range: () => plot.xlim! } : { time: false, auto: true },
        y: plot.ylim ? { auto: false, range: () => plot.ylim! } : { auto: true },
      },
      axes: [
        { ...axis, size: 46, label: signalName(runs, plot.xSignal, false), labelSize: 14, labelGap: 2 },
        { ...axis, size: 56, values: tickValues },
      ],
      // the timeline's mode: only the points up to the time / in the last seconds
      series: [{}, ...rows.map(({ ps }) => ({ stroke: ps.color, width: ps.width, points: { show: false },
        paths: orderedLinesIn((si) => indexSpan(rows[si - 1]?.d?.t ?? [], shownSpan(markRef.current))) }))],
      hooks: { draw: [drawMarks] },
    } as unknown as uPlot.Options;
    const u = new uPlot(opts, aligned, host);
    uRef.current = u;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = u.over.getBoundingClientRect();
      const f = wheelZoom(e);                 // F27: in proportion to the step
      if (f === null) return;
      const xv = u.posToVal(e.clientX - r.left, "x"), yv = u.posToVal(e.clientY - r.top, "y");
      const sx = u.scales.x, sy = u.scales.y;
      u.batch(() => {
        u.setScale("x", { min: xv - (xv - sx.min!) * f, max: xv + (sx.max! - xv) * f });
        u.setScale("y", { min: yv - (yv - sy.min!) * f, max: yv + (sy.max! - yv) * f });
      });
    };
    u.over.addEventListener("wheel", onWheel, { passive: false });
    host.addEventListener("mousedown", () => actions.setActivePlot(index), true);
    return () => { u.destroy(); uRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, styleKey, theme, scale, size.w > 0 && size.h > 0, plot.xSignal, plot.xlim?.[0], plot.xlim?.[1], plot.ylim?.[0], plot.ylim?.[1]]);

  useEffect(() => { uRef.current?.setSize({ width: size.w, height: size.h }); }, [size]);
  useEffect(() => { uRef.current?.redraw(false); }, [cursor, cvals, playMode, windowSec]);

  return (
    <div className="plot-canvas" ref={wrapRef}>
      {(!plot.xSignal || !ys.length) && <div className="plot-empty">{emptyText}</div>}
    </div>
  );
}
