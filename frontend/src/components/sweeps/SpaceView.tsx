/* W14 / W15 / W18: the shared-parameter space - two shared parameters on the axes (the third, if any, as a
   slider: one of its values, or all of them projected). Tried values filled when they hold in every table,
   hollow when not, coloured by round (the demo); proposed values as diamonds with their reason; the best a
   ring, the full grid's optimum (the demo) a dashed ring. SVG, theme colours only. */
import { useMemo, useState } from "react";
import { useT } from "../../i18n";

export interface SpacePoint { values: Record<string, number | string>; feasible?: boolean; round?: number; proposed?: string }

const W = 360, H = 260, PAD = { l: 44, r: 12, t: 12, b: 34 };

function ticks(lo: number, hi: number, n = 5): number[] {
  if (!(hi > lo)) return [lo];
  const step = Math.pow(10, Math.floor(Math.log10((hi - lo) / n)));
  const k = [1, 2, 5, 10].find((m) => (hi - lo) / (step * m) <= n) ?? 10;
  const s = step * k, out: number[] = [];
  for (let v = Math.ceil(lo / s) * s; v <= hi + 1e-12; v += s) out.push(+v.toPrecision(10));
  return out;
}

export default function SpaceView({ axes, points, best, optimum, rounds }: {
  axes: string[]; points: SpacePoint[]; best?: Record<string, number | string> | null; optimum?: Record<string, number | string> | null; rounds?: number;
}) {
  const t = useT();
  const [xa, setXa] = useState(0);
  const [ya, setYa] = useState(Math.min(1, axes.length - 1));
  const za = axes.findIndex((_, i) => i !== xa && i !== ya);
  const zName = za >= 0 ? axes[za] : null;
  const zValues = useMemo(() => zName ? [...new Set(points.map((p) => Number(p.values[zName])))].filter(Number.isFinite).sort((a, b) => a - b) : [], [points, zName]);
  const [zi, setZi] = useState(-1);                       // -1: all values, projected
  const zv = zi >= 0 && zi < zValues.length ? zValues[zi] : null;
  const xn = axes[xa], yn = axes[ya];
  const num = (p: Record<string, number | string> | null | undefined, k: string) => Number(p?.[k]);
  const shown = points.filter((p) => zv === null || !zName || Math.abs(num(p.values, zName) - zv) < 1e-9);
  const all = [...points.map((p) => p.values), ...(optimum ? [optimum] : [])];
  const ext = (k: string) => { const v = all.map((p) => num(p, k)).filter(Number.isFinite); return v.length ? [Math.min(...v), Math.max(...v)] : [0, 1]; };
  const [x0, x1] = ext(xn), [y0, y1] = ext(yn);
  const sx = (v: number) => PAD.l + (x1 > x0 ? (v - x0) / (x1 - x0) : 0.5) * (W - PAD.l - PAD.r);
  const sy = (v: number) => H - PAD.b - (y1 > y0 ? (v - y0) / (y1 - y0) : 0.5) * (H - PAD.t - PAD.b);
  const maxRound = rounds ?? Math.max(1, ...points.map((p) => p.round ?? 1));
  const fill = (p: SpacePoint) => p.round ? `color-mix(in srgb, var(--info) ${Math.round(25 + 75 * (p.round / maxRound))}%, var(--muted))` : "var(--info)";
  const ring = (v: Record<string, number | string> | null | undefined, cls: string, label: string) =>
    v && (zv === null || !zName || Math.abs(num(v, zName) - zv) < 1e-9) && Number.isFinite(num(v, xn)) &&
    <circle className={cls} cx={sx(num(v, xn))} cy={sy(num(v, yn))} r={9}><title>{label}</title></circle>;
  return (
    <figure className="cp-space" aria-label={t("cpSpace")}>
      <div className="cp-space-axes">
        <label>x <select value={xa} onChange={(e) => setXa(+e.target.value)}>{axes.map((a, i) => <option key={a} value={i} disabled={i === ya}>{a}</option>)}</select></label>
        <label>y <select value={ya} onChange={(e) => setYa(+e.target.value)}>{axes.map((a, i) => <option key={a} value={i} disabled={i === xa}>{a}</option>)}</select></label>
        {zName && zValues.length > 1 && (
          <label className="cp-space-z">{zName} <input type="range" min={-1} max={zValues.length - 1} value={zi} onChange={(e) => setZi(+e.target.value)} aria-label={zName} />
            <bdi>{zv === null ? t("dmAll") : zv}</bdi></label>
        )}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="cp-space-svg" role="img">
        {ticks(x0, x1).map((v) => <g key={`x${v}`}><line className="cp-grid" x1={sx(v)} x2={sx(v)} y1={PAD.t} y2={H - PAD.b} /><text className="cp-tick" x={sx(v)} y={H - PAD.b + 14} textAnchor="middle">{v}</text></g>)}
        {ticks(y0, y1).map((v) => <g key={`y${v}`}><line className="cp-grid" x1={PAD.l} x2={W - PAD.r} y1={sy(v)} y2={sy(v)} /><text className="cp-tick" x={PAD.l - 6} y={sy(v) + 3} textAnchor="end">{v}</text></g>)}
        <text className="cp-axis-name" x={(W + PAD.l) / 2} y={H - 4} textAnchor="middle">{xn}</text>
        <text className="cp-axis-name" x={12} y={(H - PAD.b) / 2} textAnchor="middle" transform={`rotate(-90 12 ${(H - PAD.b) / 2})`}>{yn}</text>
        {shown.filter((p) => !p.proposed).map((p, i) => (
          <circle key={i} cx={sx(num(p.values, xn))} cy={sy(num(p.values, yn))} r={3.2} className={p.feasible ? "cp-pt ok" : "cp-pt no"}
            style={p.feasible ? { fill: fill(p), stroke: fill(p) } : { stroke: fill(p) }}>
            <title>{axes.map((a) => `${a} = ${p.values[a]}`).join(", ")}{p.round ? ` · ${t("dmRoundOf")} ${p.round}` : ""}</title></circle>
        ))}
        {shown.filter((p) => p.proposed).map((p, i) => {
          const x = sx(num(p.values, xn)), y = sy(num(p.values, yn));
          return <path key={`c${i}`} className="cp-cand" d={`M${x} ${y - 5}L${x + 5} ${y}L${x} ${y + 5}L${x - 5} ${y}Z`}>
            <title>{t("cpProposed")}: {t(`cpReason_${p.proposed}` as never)} · {axes.map((a) => `${a} = ${p.values[a]}`).join(", ")}</title></path>;
        })}
        {ring(optimum, "cp-opt", t("dmTrue"))}
        {ring(best, "cp-best", t("dmBest"))}
      </svg>
      <figcaption className="cp-space-legend">
        <span><i className="cp-dot ok" /> {t("dmFeasible")}</span><span><i className="cp-dot no" /> {t("dmTried")}</span>
        <span><i className="cp-dot best" /> {t("dmBest")}</span>{optimum && <span><i className="cp-dot opt" /> {t("dmTrue")}</span>}
        {points.some((p) => p.proposed) && <span><i className="cp-dot cand" /> {t("cpProposed")}</span>}
      </figcaption>
    </figure>
  );
}
