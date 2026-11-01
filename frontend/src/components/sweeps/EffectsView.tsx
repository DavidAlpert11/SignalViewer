/* Which parameter matters: for each parameter, the goal (worst case per set; else the share that
   holds) along its values - mean with the min..max band - and the share of sets that hold there;
   parameters in order of importance (the share of the spread their values explain). */
import { useEffect, useState } from "react";
import { useT } from "../../i18n";
import { sweepApi, type Effects } from "../../sweeps/api";
import { fmtValue } from "../../sweeps/scales";
import { wireQuestion, type Study } from "../../sweeps/state";
import { styleOf } from "../../sweeps/view";
import StyleMenu from "./StyleMenu";

export default function EffectsView({ study }: { study: Study }) {
  const t = useT();
  const [e, setE] = useState<Effects | null>(null);
  const [err, setErr] = useState("");
  const qk = JSON.stringify(wireQuestion(study));
  useEffect(() => {
    let live = true;
    sweepApi.effects(study.tableId, wireQuestion(study)).then((r) => live && setE(r)).catch((x) => live && setErr((x as Error).message));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [study.tableId, qk]);
  if (err) return <p className="sw-error">{err}</p>;
  if (!e) return <p className="hint">{t("swReading")}</p>;
  const what = study.question.goal ? t("swEffectsOfGoal", { c: study.question.goal.column }) : t("swEffectsOfHolding");
  const order = [...e.params].sort((a, b) => b.importance - a.importance);
  return (
    <div className="sw-effects">
      <div className="sw-row"><span className="hint">{what}</span><span className="sw-add-map" />
        <StyleMenu study={study} parts={["grid"]} /></div>
      <div className="sw-effects-grid">
        {order.map((p) => <EffectCard key={p.param} p={p} yTitle={study.question.goal ? study.question.goal.column : t("swRepItHolding")} style={styleOf(study)} />)}
      </div>
    </div>
  );
}

function EffectCard({ p, yTitle, style }: { p: Effects["params"][number]; yTitle: string; style: ReturnType<typeof styleOf> }) {
  const t = useT();
  // room for the y ticks and its title (the goal), the x ticks, the share holding and the x title
  const W = 280, H = 168, L = 58, R = 10, T = 10, B = 50;
  const vals = p.levels.flatMap((l) => [l.min, l.max, l.mean]).filter((v): v is number => v !== null);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const n = p.levels.length;
  const x = (i: number) => L + (n === 1 ? (W - L - R) / 2 : (i * (W - L - R)) / (n - 1));
  const y = (v: number) => T + (hi === lo ? (H - T - B) / 2 : (1 - (v - lo) / (hi - lo)) * (H - T - B));
  // the grid: lines at the ends and the middle of the goal's range, minor ones at the quarters, and
  // one up each parameter value
  const major = [0, 0.5, 1], minor = [0.25, 0.75];
  const gy = (f: number) => T + (1 - f) * (H - T - B);
  const pts = p.levels.map((l, i) => (l.mean === null ? null : `${x(i)},${y(l.mean)}`)).filter(Boolean).join(" ");
  const band = p.levels.every((l) => l.min !== null && l.max !== null)
    ? `${p.levels.map((l, i) => `${x(i)},${y(l.max!)}`).join(" ")} ${[...p.levels].reverse().map((l, i) => `${x(n - 1 - i)},${y(l.min!)}`).join(" ")}` : "";
  return (
    <div className="sw-effect">
      <div className="sw-effect-head"><b>{p.param}</b><span className="sw-imp" title={t("swImportanceHint")}>
        <span style={{ width: `${Math.round(p.importance * 100)}%` }} /></span><span className="hint">{Math.round(p.importance * 100)}%</span></div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("swEffectOf", { c: p.param })}>
        {style.grid && <g className="sw-grid">
          {major.map((f) => <line key={f} x1={L} x2={W - R} y1={gy(f)} y2={gy(f)} />)}
          {p.levels.map((_, i) => <line key={`v${i}`} x1={x(i)} x2={x(i)} y1={T} y2={H - B} />)}
          {style.minor && minor.map((f) => <line key={`m${f}`} x1={L} x2={W - R} y1={gy(f)} y2={gy(f)} className="minor" />)}
        </g>}
        <line x1={L} x2={L} y1={T} y2={H - B} className="sw-axis-line" /><line x1={L} x2={W - R} y1={H - B} y2={H - B} className="sw-axis-line" />
        {vals.length > 0 && <>
          {band && <polygon points={band} className="sw-band" />}
          <polyline points={pts} className="sw-mean" />
          {p.levels.map((l, i) => l.mean !== null && <circle key={i} cx={x(i)} cy={y(l.mean)} r={3} className="sw-dot" />)}
          <text x={L - 4} y={T + 4} className="sw-ax" textAnchor="end">{fmtValue(hi)}</text>
          {hi !== lo && <text x={L - 4} y={gy(0.5) + 3} className="sw-ax" textAnchor="end">{fmtValue((hi + lo) / 2)}</text>}
          <text x={L - 4} y={H - B} className="sw-ax" textAnchor="end">{fmtValue(lo)}</text>
        </>}
        {p.levels.map((l, i) => (
          <g key={i}>
            <text x={x(i)} y={H - B + 12} className="sw-ax" textAnchor="middle">{typeof l.value === "number" ? fmtValue(l.value) : String(l.value)}</text>
            <rect x={x(i) - 8} y={H - B + 17} width={16} height={6} className="sw-hold-bar-bg"><title>{t("swEffectHolding", { n: Math.round((l.holding ?? 0) * 100) })}</title></rect>
            <rect x={x(i) - 8} y={H - B + 17} width={16 * (l.holding ?? 0)} height={6} className="sw-hold-bar" />
          </g>
        ))}
        {/* the axes' titles (S18) */}
        <text x={(L + W - R) / 2} y={H - 4} className="sw-ax-title" textAnchor="middle">{p.param}</text>
        <text x={12} y={(T + H - B) / 2} className="sw-ax-title" textAnchor="middle" transform={`rotate(-90 12 ${(T + H - B) / 2})`}>{yTitle}</text>
      </svg>
    </div>
  );
}
