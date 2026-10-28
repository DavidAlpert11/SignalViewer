import { useEffect, useRef, useState } from "react";
import uPlot from "uplot";
import { api } from "../api";
import { useApp, actions, signalName, type Plot } from "../store";
import { fmtNum, useT } from "../i18n";
import { axisStyle, tickValues, useSize } from "./chartUtil";

interface Props { plot: Plot; index: number; onLoading: (b: boolean) => void }
type Win = Awaited<ReturnType<typeof api.occWindows>>["items"];

/** Investigation step 3: every stretch of a condition drawn on top of each other, lined up at its
 *  start (or end, or peak), each signal's stretches thin and their mean bold. A pattern that comes
 *  after every stretch shows at once. */
export default function OccChart({ plot, index, onLoading }: Props) {
  const t = useT();
  const theme = useApp((s) => s.theme);
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const cond = useApp((s) => s.ws.conditions?.find((c) => c.id === plot.occ?.cond));
  const res = useApp((s) => (plot.occ ? s.condResults[plot.occ.cond] : undefined));
  const dataVersion = useApp((s) => s.dataVersion);
  const wrapRef = useRef<HTMLDivElement>(null);
  const size = useSize(wrapRef);
  const [win, setWin] = useState<Win | null>(null);
  const occ = plot.occ;
  const key = JSON.stringify([plot.signals.map((s) => s.sig), occ, res && Object.fromEntries(Object.entries(res).map(([k, v]) => [k, v.intervals]))]);

  useEffect(() => {
    if (!occ || !res) { setWin(null); return; }
    let gone = false;
    const items = plot.signals.map((s) => ({ sig: s.sig, intervals: res[s.sig.slice(0, s.sig.indexOf("/"))]?.intervals ?? [] }))
      .filter((x) => x.intervals.length);
    if (!items.length) { setWin([]); return; }
    onLoading(true);
    api.occWindows(items, occ.align, occ.pad).then((r) => { if (!gone) setWin(r.items); })
      .catch(() => { if (!gone) setWin(null); }).finally(() => { if (!gone) onLoading(false); });
    return () => { gone = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, dataVersion]);

  useEffect(() => {
    const host = wrapRef.current;
    if (!host || !win || !win.length || size.w < 50 || size.h < 50) return;
    const axis = axisStyle(theme);
    const grid = win[0].grid;
    const data: (number | null)[][] = [grid];
    const series: uPlot.Series[] = [{}];
    win.forEach((w) => {
      const color = plot.signals.find((s) => s.sig === w.sig)?.color ?? "#3D8BFD";
      // one grid for all: each item's grid is the same length; resample onto the first one's values
      const map = (ys: (number | null)[]) => (w.grid === grid ? ys : grid.map((g) => {
        const i = Math.round(((g - w.grid[0]) / (w.grid[w.grid.length - 1] - w.grid[0] || 1)) * (w.grid.length - 1));
        return i >= 0 && i < ys.length ? ys[i] : null;
      }));
      w.curves.forEach((c) => { data.push(map(c)); series.push({ stroke: color + "66", width: 1, points: { show: false } }); });
      data.push(map(w.mean)); series.push({ stroke: color, width: 2.5, points: { show: false } });
    });
    const u = new uPlot({
      width: size.w, height: size.h, padding: [8, 12, 0, 4], legend: { show: false },
      cursor: { y: false, drag: { x: false, y: false } },
      scales: { x: { time: false }, y: plot.ylim ? { auto: false, range: () => plot.ylim! } : { auto: true } },
      axes: [{ ...axis, size: 40 }, { ...axis, size: 60, values: tickValues }],
      hooks: { draw: [(uu) => {           // the moment they are lined up at
        const x = uu.valToPos(0, "x", true), { top, height } = uu.bbox;
        uu.ctx.save(); uu.ctx.strokeStyle = cond?.color ?? "#D4A72C"; uu.ctx.setLineDash([4, 4]); uu.ctx.lineWidth = 1.5;
        uu.ctx.beginPath(); uu.ctx.moveTo(x, top); uu.ctx.lineTo(x, top + height); uu.ctx.stroke(); uu.ctx.restore();
      }] },
      series,
    }, data as uPlot.AlignedData, host);
    const onDown = () => actions.setActivePlot(index);
    host.addEventListener("mousedown", onDown, true);
    return () => { host.removeEventListener("mousedown", onDown, true); u.destroy(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [win, theme, size.w, size.h, plot.ylim?.[0], plot.ylim?.[1], cond?.color]);

  const setAlign = (align: "start" | "end" | "peak") => useApp.getState().commit((ws) => {
    for (const tb of ws.tabs) for (const p of tb.plots) if (p.id === plot.id && p.occ) p.occ = { ...p.occ, align };
    return ws;
  });
  const n = win?.reduce((s, w) => s + w.curves.length, 0) ?? 0;
  return (
    <div className="plot-canvas env-wrap occ-wrap">
      <div className="env-canvas" ref={wrapRef} />
      <div className="env-caption occ-caption">
        {!cond ? t("occNoCond") : <>
          <b style={{ color: cond.color }}>{cond.name}</b> · {t(n === 1 ? "occSummaryOne" : "occSummary", { n })}
          {win?.some((w) => w.cut) ? ` · ${t("occCut")}` : ""}
          {" · "}{t("occAlign")}{" "}
          {(["start", "end", "peak"] as const).map((a) => (
            <button key={a} className={`linklike occ-align${occ?.align === a ? " on" : ""}`} aria-pressed={occ?.align === a} onClick={() => setAlign(a)}>
              {t(a === "start" ? "occStart" : a === "end" ? "occEnd" : "occPeak")}</button>
          ))}
          {plot.signals.length > 1 ? "" : plot.signals[0] ? ` · ${signalName(runs, plot.signals[0].sig)}` : ""}
          {" · "}{t("occTimeFrom", { s: fmtNum(0, lang, 1) })}
        </>}
      </div>
    </div>
  );
}
