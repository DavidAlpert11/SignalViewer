import { useEffect, useRef, useState } from "react";
import uPlot from "uplot";
import { api } from "../api";
import { actions, rangeKey, signalName, useApp, type Plot, type Range, type Tab } from "../store";
import { useT } from "../i18n";
import { axisStyle, reportGutter, tickValues, useGutter, useSize } from "./chartUtil";

interface Props { tab: Tab; plot: Plot; index: number; onLoading: (b: boolean) => void }
type Env = Awaited<ReturnType<typeof api.envelope>>;

/** T14: the plot's signals - many runs of one quantity (Monte-Carlo, repeated tests) - as an
 *  envelope: min…max (faint), the percentile band, and the median. Runs far from the others are
 *  named under the plot. Uses the region between the cursors when both are on.
 *  T14c: its time window is the tab's (linked with the time plots): drag zooms them all, double-click
 *  shows everything, Backspace / R work as for the time plots. */
export default function EnvelopeChart({ tab, plot, index, onLoading }: Props) {
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
  const key = rangeKey(tab, plot);
  const range = useApp((s) => s.ranges[key] ?? null);
  const rangeRef = useRef<Range>(range);
  rangeRef.current = range;
  // F24: the room left / right of the plot area is the column's, so the time axes line up
  const gutter = useGutter(tab, plot.id);
  useEffect(() => { reportGutter(plot.id, 64, 12); }, [plot.id]);
  const region = cursor.on && cursor.dual && cursor.t1 !== null && cursor.t2 !== null ? [cursor.t1, cursor.t2] : null;
  const sigKey = plot.signals.map((s) => `${s.sig}:${s.scale}:${s.offset}:${s.tOffset ?? 0}`).join("|");

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
  }, [sigKey, region?.[0], region?.[1], dataVersion]);

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
      padding: [8, Math.max(12, gutter[1]), 0, 4],
      legend: { show: false },
      cursor: { y: false, drag: { x: true, y: false, setScale: false } },
      scales: {
        x: { time: false, auto: () => !rangeRef.current,
          range: (_u, mn, mx): uPlot.Range.MinMax => (rangeRef.current ? [rangeRef.current[0], rangeRef.current[1]] : [mn, mx]) },
        y: plot.ylim ? { auto: false, range: () => plot.ylim! } : { auto: true },
      },
      axes: [{ ...axis, size: 46 }, { ...axis, size: Math.max(60, gutter[0] - 4), values: tickValues }],
      hooks: {
        // a dragged time window zooms every linked plot of the tab (one zoom-history step)
        setSelect: [(u) => {
          const { left, width } = u.select;
          u.setSelect({ left: 0, top: 0, width: 0, height: 0 }, false);
          if (width < 3) return;
          actions.setRange(key, [u.posToVal(left, "x"), u.posToVal(left + width, "x")]);
        }],
      },
      series: [{}, { ...faint, label: "min" }, { ...faint, label: "max" },
        { ...faint, label: "lo" }, { ...faint, label: "hi" },
        { stroke: color, width: 2, points: { show: false }, label: "median" }],
      bands: [{ series: [2, 1], fill: color + "22" }, { series: [4, 3], fill: color + "55" }],
    };
    const u = new uPlot(opts, data, host);
    uRef.current = u;
    const onDown = () => actions.setActivePlot(index);
    const onDbl = () => actions.setRange(key, null);
    const onCtx = (e: MouseEvent) => {           // the moment under a right-click, for the plot's menu
      const r = u.over.getBoundingClientRect();
      (e as MouseEvent & { svTime?: number }).svTime = u.posToVal(e.clientX - r.left, "x");
    };
    u.over.addEventListener("contextmenu", onCtx);
    host.addEventListener("mousedown", onDown, true);
    host.addEventListener("dblclick", onDbl);
    return () => { host.removeEventListener("mousedown", onDown, true); host.removeEventListener("dblclick", onDbl); u.destroy(); uRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [env, color, theme, scale, size.w > 0 && size.h > 0, plot.ylim?.[0], plot.ylim?.[1], key, gutter[0], gutter[1]]);
  // the tab's time window changed (a zoom here or in a linked plot): move the axis, no rebuild
  useEffect(() => {
    const u = uRef.current;
    if (!u) return;
    const t = u.data[0] as number[];
    if (range) u.setScale("x", { min: range[0], max: range[1] });
    else if (t.length) u.setScale("x", { min: t[0], max: t[t.length - 1] });
  }, [range?.[0], range?.[1]]);
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
