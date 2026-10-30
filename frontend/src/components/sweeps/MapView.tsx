/* Two parameters against each other: each cell, the share of sets there that hold (colour) and the
   best goal among them (number). Optional marks on top (the next-runs suggestions). */
import { useEffect, useState } from "react";
import { useT } from "../../i18n";
import { ramp } from "../../sweeps/colors";
import { sweepApi, type PairMap } from "../../sweeps/api";
import { fmtValue } from "../../sweeps/scales";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";

export interface Mark { x: number | string; y: number | string; kind: string }

export default function MapView({ study, marks }: { study: Study; marks?: Mark[] }) {
  const t = useT();
  const st = useSweeps.getState();
  const params = study.columns.filter((c) => c.role === "param").map((c) => c.name);
  const x = study.view.mapX && params.includes(study.view.mapX) ? study.view.mapX : params[0];
  const y = study.view.mapY && params.includes(study.view.mapY) && study.view.mapY !== x ? study.view.mapY : params.find((p) => p !== x);
  const [m, setM] = useState<PairMap | null>(null);
  const [err, setErr] = useState("");
  const qk = JSON.stringify(wireQuestion(study));
  useEffect(() => {
    if (!x || !y) return;
    let live = true;
    setErr("");
    sweepApi.map(study.tableId, wireQuestion(study), x, y).then((r) => live && setM(r)).catch((e) => live && setErr((e as Error).message));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [study.tableId, qk, x, y]);
  if (params.length < 2) return <p className="hint">{t("swMapNeedsTwo")}</p>;
  const pick = (
    <div className="sw-row">
      <label>{t("swMapX")} <select value={x} onChange={(e) => st.setView({ mapX: e.target.value })}>{params.map((p) => <option key={p}>{p}</option>)}</select></label>
      <label>{t("swMapY")} <select value={y} onChange={(e) => st.setView({ mapY: e.target.value })}>{params.filter((p) => p !== x).map((p) => <option key={p}>{p}</option>)}</select></label>
      <span className="hint">{t("swMapHint")}</span>
    </div>
  );
  if (err) return <>{pick}<p className="sw-error">{err}</p></>;
  if (!m) return <>{pick}<p className="hint">{t("swReading")}</p></>;
  const nx = m.xs.length, ny = m.ys.length;
  const L = 64, B = 40, T = 8, R = 8, cw = Math.max(26, Math.min(90, 700 / nx)), ch = Math.max(22, Math.min(60, 420 / ny));
  const W = L + nx * cw + R, H = T + ny * ch + B;
  // a mark between grid values sits between the cells
  const pos = (vals: (number | string)[], v: number | string) => {
    const i = vals.indexOf(v);
    if (i >= 0) return i;
    if (typeof v !== "number") return -1;
    const nums = vals as number[];
    for (let k = 0; k < nums.length - 1; k++) if (v > nums[k] && v < nums[k + 1]) return k + (v - nums[k]) / (nums[k + 1] - nums[k]);
    return v < nums[0] ? -0.4 : nums.length - 0.6;
  };
  return (
    <div className="sw-map">
      {pick}
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: W, maxWidth: "100%" }} role="img" aria-label={t("swMapAria", { x: m.x, y: m.y })}>
        {m.share.map((row, j) => row.map((s, i) => {
          const b = m.best[j][i];
          return (
            <g key={`${i}-${j}`}>
              <rect x={L + i * cw + 1} y={T + (ny - 1 - j) * ch + 1} width={cw - 2} height={ch - 2} rx={3}
                fill={s === null ? "transparent" : ramp(s)} className={s === null ? "sw-cell-empty" : ""}>
                <title>{`${m.x} ${m.xs[i]}, ${m.y} ${m.ys[j]}: ${s === null ? "–" : Math.round(s * 100) + "%"}${b !== null ? ` · ${fmtValue(b)}` : ""}`}</title>
              </rect>
              {b !== null && cw >= 40 && <text x={L + i * cw + cw / 2} y={T + (ny - 1 - j) * ch + ch / 2 + 4} textAnchor="middle" className="sw-cell-text">{fmtValue(b)}</text>}
            </g>
          );
        }))}
        {m.xs.map((v, i) => <text key={i} x={L + i * cw + cw / 2} y={H - B + 16} textAnchor="middle" className="sw-ax">{String(v)}</text>)}
        {m.ys.map((v, j) => <text key={j} x={L - 6} y={T + (ny - 1 - j) * ch + ch / 2 + 4} textAnchor="end" className="sw-ax">{String(v)}</text>)}
        <text x={L + (nx * cw) / 2} y={H - 4} textAnchor="middle" className="sw-ax-title">{m.x}</text>
        {(marks ?? []).map((mk, k) => {
          const i = pos(m.xs, mk.x), j = pos(m.ys, mk.y);
          if (i < -1 || j < -1) return null;
          return <text key={k} x={L + i * cw + cw / 2} y={T + (ny - 1 - j) * ch + ch / 2 + 5} textAnchor="middle" className={`sw-mark sw-mark-${mk.kind}`}>{MARK[mk.kind] ?? "•"}</text>;
        })}
      </svg>
      <div className="sw-row hint"><span className="sw-legend-ramp" /> {t("swMapLegend")}</div>
    </div>
  );
}

export const MARK: Record<string, string> = { edge: "◆", best: "★", disagree: "▲", gaps: "○", missing: "↻" };
