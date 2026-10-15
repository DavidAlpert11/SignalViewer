import { useEffect, useRef } from "react";
import uPlot from "uplot";
import { useApp, type PreviewLine } from "../store";
import { axisStyle, PLOT_THEME, PREVIEW_DASH, tickValues, useSize } from "./chartUtil";

/** One small chart per preview line, stacked (Create signals > Preview > Separate charts): the
 *  three axes of a frame conversion often differ by orders of magnitude (lat / lon vs alt, N / E vs
 *  D), so on one shared value axis two of them look flat. UI-only, nothing is kept. */
export default function PreviewCharts({ lines }: { lines: PreviewLine[] }) {
  return (
    <div className="pv-charts">
      {lines.map((l, k) => <MiniChart key={`${k}:${l.label}`} line={l} k={k} />)}
    </div>
  );
}

const H = 110;

function MiniChart({ line, k }: { line: PreviewLine; k: number }) {
  const theme = useApp((s) => s.theme);
  const scale = useApp((s) => s.uiScale);
  const wrapRef = useRef<HTMLDivElement>(null);
  const size = useSize(wrapRef);
  const uRef = useRef<uPlot | null>(null);

  useEffect(() => {
    const host = wrapRef.current;
    uRef.current?.destroy();
    uRef.current = null;
    if (!host || size.w < 60 || !line.x.length) return;
    const axis = axisStyle(theme);
    const data = [Array.from(line.x), Array.from(line.y, (v) => (Number.isFinite(v) ? v : null))] as uPlot.AlignedData;
    const u = new uPlot({
      width: size.w, height: H,
      padding: [6, 8, 0, 2],
      legend: { show: false },
      cursor: { y: false, drag: { x: false, y: false }, sync: { key: "sv-preview" } },   // the charts point at the same time
      scales: { x: { time: false }, y: { auto: true } },
      axes: [{ ...axis, size: 26 }, { ...axis, size: 52, values: tickValues }],
      series: [{}, { stroke: PLOT_THEME[theme].axis, width: 1.5, dash: PREVIEW_DASH[k % PREVIEW_DASH.length], points: { show: false }, spanGaps: false, label: line.label }],
    }, data, host);
    uRef.current = u;
    return () => { u.destroy(); uRef.current = null; };
  }, [line, k, theme, scale, size.w > 0]);
  useEffect(() => { uRef.current?.setSize({ width: size.w, height: H }); }, [size.w]);

  return (
    <figure className="pv-chart">
      <figcaption>{line.label}</figcaption>
      <div ref={wrapRef} className="pv-canvas" style={{ height: H }} />
    </figure>
  );
}
