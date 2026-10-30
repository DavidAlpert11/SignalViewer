/* Which parameter matters: for each parameter, the goal (worst case per set; else the share that
   holds) along its values - mean with the min..max band - and the share of sets that hold there;
   parameters in order of importance (the share of the spread their values explain). */
import { useEffect, useState } from "react";
import { useT } from "../../i18n";
import { sweepApi, type Effects } from "../../sweeps/api";
import { fmtValue } from "../../sweeps/scales";
import { wireQuestion, type Study } from "../../sweeps/state";

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
      <p className="hint">{what}</p>
      <div className="sw-effects-grid">
        {order.map((p) => <EffectCard key={p.param} p={p} />)}
      </div>
    </div>
  );
}

function EffectCard({ p }: { p: Effects["params"][number] }) {
  const t = useT();
  const W = 260, H = 130, L = 40, R = 10, T = 10, B = 26;
  const vals = p.levels.flatMap((l) => [l.min, l.max, l.mean]).filter((v): v is number => v !== null);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const n = p.levels.length;
  const x = (i: number) => L + (n === 1 ? (W - L - R) / 2 : (i * (W - L - R)) / (n - 1));
  const y = (v: number) => T + (hi === lo ? (H - T - B) / 2 : (1 - (v - lo) / (hi - lo)) * (H - T - B));
  const pts = p.levels.map((l, i) => (l.mean === null ? null : `${x(i)},${y(l.mean)}`)).filter(Boolean).join(" ");
  const band = p.levels.every((l) => l.min !== null && l.max !== null)
    ? `${p.levels.map((l, i) => `${x(i)},${y(l.max!)}`).join(" ")} ${[...p.levels].reverse().map((l, i) => `${x(n - 1 - i)},${y(l.min!)}`).join(" ")}` : "";
  return (
    <div className="sw-effect">
      <div className="sw-effect-head"><b>{p.param}</b><span className="sw-imp" title={t("swImportanceHint")}>
        <span style={{ width: `${Math.round(p.importance * 100)}%` }} /></span><span className="hint">{Math.round(p.importance * 100)}%</span></div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("swEffectOf", { c: p.param })}>
        {vals.length > 0 && <>
          {band && <polygon points={band} className="sw-band" />}
          <polyline points={pts} className="sw-mean" />
          {p.levels.map((l, i) => l.mean !== null && <circle key={i} cx={x(i)} cy={y(l.mean)} r={3} className="sw-dot" />)}
          <text x={L - 4} y={T + 4} className="sw-ax" textAnchor="end">{fmtValue(hi)}</text>
          <text x={L - 4} y={H - B} className="sw-ax" textAnchor="end">{fmtValue(lo)}</text>
        </>}
        {p.levels.map((l, i) => (
          <g key={i}>
            <rect x={x(i) - 8} y={H - 12} width={16} height={8} className="sw-hold-bar-bg" />
            <rect x={x(i) - 8} y={H - 12} width={16 * (l.holding ?? 0)} height={8} className="sw-hold-bar" />
            <text x={x(i)} y={H - 15} className="sw-ax" textAnchor="middle">{typeof l.value === "number" ? fmtValue(l.value) : String(l.value)}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}
