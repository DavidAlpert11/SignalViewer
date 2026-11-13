/* W18: the demo's convergence chart - x = runs executed (log, so the full grid's count fits), y = the best
   (worst-drone) objective found so far; a dashed line at the full grid's optimum and a mark where the full
   grid would finish. SVG, theme colours only. */
import { fmtInt, useT } from "../../i18n";
import { useApp } from "../../store";
import type { DemoProgress, LoopProgress } from "../../sweeps/studyTypes";

const W = 420, H = 230, PAD = { l: 48, r: 16, t: 14, b: 36 };

/** p: the demo's progress (with the full grid's optimum and run count) or any loop's (without: no reference). */
export default function ConvergenceChart({ p }: { p: LoopProgress & Partial<Pick<DemoProgress, "optimum" | "full_grid">> }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const pts = p.points.filter((x) => x.best !== null) as { round: number; runs: number; best: number }[];
  const lastRuns = pts.length ? pts[pts.length - 1].runs : 100;
  const full = p.full_grid?.runs ?? null;
  const lx0 = Math.log10(Math.max(10, Math.min(pts[0]?.runs ?? 100, full ?? lastRuns) / 2)), lx1 = Math.log10((full ?? lastRuns) * 1.4);
  const ys = [...pts.map((x) => x.best), ...(p.optimum ? [p.optimum.score] : [])];
  const y0 = Math.min(...ys), y1 = Math.max(...ys), pad = (y1 - y0) * 0.1 || Math.abs(y0) * 0.05 || 1;
  const sx = (v: number) => PAD.l + (Math.log10(Math.max(v, 1)) - lx0) / (lx1 - lx0) * (W - PAD.l - PAD.r);
  const sy = (v: number) => H - PAD.b - (v - (y0 - pad)) / ((y1 + pad) - (y0 - pad)) * (H - PAD.t - PAD.b);
  const decades = [1, 2, 3, 4, 5, 6].map((e) => 10 ** e).filter((v) => Math.log10(v) >= lx0 && Math.log10(v) <= lx1);
  // the best so far is a step line: it holds until a round finds a better one
  const path = pts.map((x, i) => (i === 0 ? `M${sx(x.runs)} ${sy(x.best)}`
    : `L${sx(x.runs)} ${sy(pts[i - 1].best)} L${sx(x.runs)} ${sy(x.best)}`)).join(" ");
  return (
    <figure className="dm-chart" aria-label={t("dmChart")} data-points={pts.length}>
      <figcaption>{t("dmChart")}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img">
        {decades.map((v) => <g key={v}><line className="cp-grid" x1={sx(v)} x2={sx(v)} y1={PAD.t} y2={H - PAD.b} />
          <text className="cp-tick" x={sx(v)} y={H - PAD.b + 14} textAnchor="middle">{fmtInt(v, lang)}</text></g>)}
        <text className="cp-axis-name" x={(W + PAD.l) / 2} y={H - 4} textAnchor="middle">{t("dmRunsAxis")}</text>
        {p.optimum && <><line className="dm-opt" x1={PAD.l} x2={W - PAD.r} y1={sy(p.optimum.score)} y2={sy(p.optimum.score)}><title>{t("dmOptimum")}</title></line>
          <text className="cp-tick" x={PAD.l - 6} y={sy(p.optimum.score) + 3} textAnchor="end">{p.optimum.score.toFixed(3)}</text></>}
        {full !== null && <g className="dm-full"><line x1={sx(full)} x2={sx(full)} y1={PAD.t} y2={H - PAD.b} /><title>{t("dmFullGrid", { n: fmtInt(full, lang) })}</title>
          <text className="cp-tick" x={sx(full) - 4} y={PAD.t + 10} textAnchor="end">{t("dmFullGrid", { n: fmtInt(full, lang) })}</text></g>}
        {!p.optimum && pts.length > 0 && <text className="cp-tick" x={PAD.l - 6} y={sy(pts[pts.length - 1].best) + 3} textAnchor="end">{pts[pts.length - 1].best.toFixed(3)}</text>}
        {pts.length > 0 && <path className="dm-line" d={path} />}
        {pts.map((x) => <circle key={x.round} className="dm-pt" cx={sx(x.runs)} cy={sy(x.best)} r={3.5}>
          <title>{t("dmRound", { k: x.round })}: {fmtInt(x.runs, lang)} · {x.best.toFixed(4)}</title></circle>)}
      </svg>
    </figure>
  );
}
