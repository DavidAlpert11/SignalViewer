import { useEffect, useRef, useState } from "react";
import uPlot from "uplot";
import { api } from "../api";
import { actions, signalName, useApp, type Plot } from "../store";
import { useT } from "../i18n";
import { axisStyle, tickValues, useSize } from "./chartUtil";

interface Props { plot: Plot; index: number; onLoading: (b: boolean) => void }
type Env = Awaited<ReturnType<typeof api.envelope>>;

/** T14: the plot's signals - many runs of one quantity (Monte-Carlo, repeated tests) - as an
 *  envelope: min…max (faint), the percentile band, and the median. Runs far from the others are
 *  named under the plot. Uses the region between the cursors when both are on. */
export default function EnvelopeChart({ plot, index, onLoading }: Props) {
  const t = useT();
  const theme = useApp((s) => s.theme);
  const scale = useApp((s) => s.uiScale);
  const runs = useApp((s) => s.runs);
  const dataVersion = useApp((s) => s.dataVersion);
  const cursor = useApp((s) => s.cursor);
  const wrapRef = useRef<HTMLDivElement>(null);
  const uRef = useRef<uPlot | null>(null);
  const size = useSize(wrapRef);
  const [env, setEnv] = useState<Env | null>(null);
  const region = cursor.on && cursor.dual && cursor.t1 !== null && cursor.t2 !== null ? [cursor.t1, cursor.t2] : null;
  const key = plot.signals.map((s) => `${s.sig}:${s.scale}:${s.offset}:${s.tOffset ?? 0}`).join("|");

  useEffect(() => {
    if (plot.signals.length < 2) { setEnv(null); return; }
    let cancelled = false;
    const h = window.setTimeout(async () => {
      onLoading(true);
      try {
        const r = await api.envelope(plot.signals.map((s) => ({ id: s.sig, scale: s.scale, offset: s.offset, tOffset: s.tOffset ?? 0 })),
          region?.[0] ?? null, region?.[1] ?? null, 2000);
        if (!cancelled) setEnv(r);
      } catch { if (!cancelled) setEnv(null); }
      finally { if (!cancelled) onLoading(false); }
    }, 120);
    return () => { cancelled = true; window.clearTimeout(h); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, region?.[0], region?.[1], dataVersion]);

  const color = plot.signals[0]?.color ?? "#3D8BFD";
  useEffect(() => {
    const host = wrapRef.current;
    uRef.current?.destroy();
    uRef.current = null;
    if (!host || !env || env.empty || size.w < 50 || size.h < 50) return;
    const axis = axisStyle(theme);
    const a = (k: "min" | "max" | "lo" | "hi" | "median") => Array.from(env[k]!, (v) => (Number.isFinite(v) ? v : null));
    // series: 1 min, 2 max, 3 lo, 4 hi, 5 median
    const data = [Array.from(env.t!), a("min"), a("max"), a("lo"), a("hi"), a("median")] as uPlot.AlignedData;
    const faint = { stroke: color + "55", width: 0.75, points: { show: false } };
    const opts: uPlot.Options = {
      width: size.w, height: size.h,
      padding: [8, 12, 0, 4],
      legend: { show: false },
      cursor: { y: false, drag: { x: true, y: false, setScale: true } },
      scales: { x: { time: false }, y: plot.ylim ? { auto: false, range: () => plot.ylim! } : { auto: true } },
      axes: [{ ...axis, size: 46 }, { ...axis, size: 60, values: tickValues }],
      series: [{}, { ...faint, label: "min" }, { ...faint, label: "max" },
        { ...faint, label: "lo" }, { ...faint, label: "hi" },
        { stroke: color, width: 2, points: { show: false }, label: "median" }],
      bands: [{ series: [2, 1], fill: color + "22" }, { series: [4, 3], fill: color + "55" }],
    };
    const u = new uPlot(opts, data, host);
    uRef.current = u;
    host.addEventListener("mousedown", () => actions.setActivePlot(index), true);
    return () => { u.destroy(); uRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [env, color, theme, scale, size.w > 0 && size.h > 0, plot.ylim?.[0], plot.ylim?.[1]]);
  useEffect(() => { uRef.current?.setSize({ width: size.w, height: size.h }); }, [size]);

  const outliers = env?.runs?.filter((r) => r.outlier) ?? [];
  return (
    <div className="plot-canvas env-wrap">
      <div className="env-canvas" ref={wrapRef} />
      <div className="env-caption">
        {plot.signals.length < 2 ? t("envNeedTwo")
          : env && !env.empty ? <>
              {t("envSummary", { n: env.n, p: env.pct ?? 5, q: 100 - (env.pct ?? 5) })}
              {outliers.length > 0 && <> · <b className="env-out">{t("envOutliers")}</b> {outliers.map((o) => signalName(runs, o.id)).join(", ")}</>}
            </> : env?.empty ? t("envNoOverlap") : null}
      </div>
    </div>
  );
}
