import { runsDataKey } from "../values";
import { useEffect, useRef, useState } from "react";
import uPlot from "uplot";
import { api, type StepSeries } from "../api";
import { fmtNum, useT } from "../i18n";
import { actions, signalName, TRACE_COLORS, useApp, type Plot } from "../store";
import { axisStyle, ink, tickValues, useSize } from "./chartUtil";

interface Props { plot: Plot; index: number; onLoading: (b: boolean) => void }

/** 1.21: a control loop's step response from flight data (as ArduPilot's PID Review): the plot's
 *  signals in pairs - the setpoint, then what was measured (RATE.RDes, RATE.R) - over the region
 *  between the two cursors when they are on, else the whole recording. */
export default function StepChart({ plot, index, onLoading }: Props) {
  const theme = useApp((s) => s.theme);
  const scale = useApp((s) => s.uiScale);
  const runs = useApp((s) => s.runs);
  const dataVersion = useApp((s) => s.dataVersion);
  const cursor = useApp((s) => s.cursor);
  const lang = useApp((s) => s.lang);
  const t = useT();
  const wrapRef = useRef<HTMLDivElement>(null);
  const uRef = useRef<uPlot | null>(null);
  const size = useSize(wrapRef);
  const [data, setData] = useState<StepSeries[]>([]);
  const sigs = plot.signals;
  const pairs: [string, string][] = [];
  for (let i = 0; i + 1 < sigs.length; i += 2) pairs.push([sigs[i].sig, sigs[i + 1].sig]);
  const key = pairs.map((p) => p.join(">")).join("|");
  const region = cursor.on && cursor.dual && cursor.t1 !== null && cursor.t2 !== null ? [cursor.t1, cursor.t2] : null;
  const runsKey = runsDataKey(runs);

  useEffect(() => {
    if (!pairs.length) { setData([]); return; }
    let off = false;
    const h = window.setTimeout(async () => {
      onLoading(true);
      try {
        const r = await api.stepResp(pairs, region?.[0] ?? null, region?.[1] ?? null);
        if (!off) setData(r);
      } catch (e) {
        if (!off) useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
      } finally { if (!off) onLoading(false); }
    }, region ? 250 : 60);
    return () => { off = true; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, region?.[0], region?.[1], dataVersion, runsKey]);

  const styleKey = sigs.map((s) => `${s.sig}:${s.color}:${s.width}`).join("|");
  const ok = data.filter((d) => d.t && d.step);
  useEffect(() => {
    const host = wrapRef.current;
    uRef.current?.destroy();
    uRef.current = null;
    if (!host || !ok.length || size.w < 50 || size.h < 50) return;
    const axis = axisStyle(theme);
    const tables = ok.map((d) => [Array.from(d.t!), Array.from(d.step!)] as uPlot.AlignedData);
    const aligned = tables.length === 1 ? tables[0] : uPlot.join(tables, tables.map(() => [1]));
    const colorOf = (id: string) => ink(sigs.find((s) => s.sig === id)?.color ?? TRACE_COLORS[0], theme);
    const widthOf = (id: string) => sigs.find((s) => s.sig === id)?.width ?? 1.5;
    const opts: uPlot.Options = {
      width: size.w, height: size.h, padding: [8, 12, 0, 4], legend: { show: false },
      cursor: { y: false, points: { size: 6 }, drag: { x: true, y: false, setScale: true } },
      scales: { x: { time: false }, y: { auto: true, range: (_u, lo, hi) => [Math.min(0, lo), Math.max(1.2, hi * 1.05)] } },
      axes: [{ ...axis, size: 46, label: "s", labelSize: 14, labelGap: 2 }, { ...axis, size: 60, values: tickValues }],
      series: [{}, ...ok.map((d) => ({ stroke: colorOf(d.pair[1]), width: widthOf(d.pair[1]) + 0.5, points: { show: false } }))],
      plugins: [unityLine(axis.stroke as string)],
    };
    const u = new uPlot(opts, aligned, host);
    uRef.current = u;
    host.addEventListener("mousedown", () => actions.setActivePlot(index), true);
    return () => { u.destroy(); uRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, styleKey, theme, scale, size.w > 0 && size.h > 0]);
  useEffect(() => { uRef.current?.setSize({ width: size.w, height: size.h }); }, [size]);

  const ms = (s?: number | null) => (typeof s === "number" ? `${fmtNum(s * 1000, lang, 3)} ms` : "–");
  const notes = data.map((d) => {
    const name = data.length > 1 ? signalName(runs, d.pair[1], false) + ": " : "";
    if (d.error === "rate") return t("stepRate", { name, hz: fmtNum(d.rate ?? 0, lang, 3) });
    if (d.error) return t("stepNone", { name });
    return t("stepSay", { name, rise: ms(d.rise), over: fmtNum(d.overshoot ?? 0, lang, 2), settle: ms(d.settle), n: d.windows ?? 0 });
  });
  return <>
    <div className="plot-canvas" ref={wrapRef} data-step={ok.map((d) => (d.rise ?? 0).toFixed(4)).join(",") || undefined} />
    {pairs.length === 0 && sigs.length > 0 && <div className="plot-empty">{t("stepNeedsPairs")}</div>}
    {notes.length > 0 && <div className="fft-filters-note step-note" title={t("stepHint")}>{notes.join(" · ")}</div>}
  </>;
}

/** the setpoint's size (1): a step response ends near it when the loop follows */
function unityLine(color: string): uPlot.Plugin {
  return {
    hooks: {
      draw: [(u: uPlot) => {
        const y = u.valToPos(1, "y", true);
        if (!Number.isFinite(y)) return;
        const ctx = u.ctx, pr = devicePixelRatio || 1;
        ctx.save(); ctx.strokeStyle = color; ctx.globalAlpha = 0.6; ctx.lineWidth = pr; ctx.setLineDash([2 * pr, 3 * pr]);
        ctx.beginPath(); ctx.moveTo(u.bbox.left, y); ctx.lineTo(u.bbox.left + u.bbox.width, y); ctx.stroke(); ctx.restore();
      }],
    },
  };
}
