/* MF08: robust design - how the best sets' result spreads when their parameters move as the goal's
   tolerances say (*Robust to*, each with a distribution). On a model of the result (fast, virtual): each
   candidate's mean, σ, a percentile on the bad side and the probability of failure, and a plot of mean
   against σ. For real: the samples around one candidate as a group, run by the run step; once merged,
   any group's statistics. The maths: svcore/sweep/robust.py. */
import { useMemo, useState } from "react";
import { useT } from "../../i18n";
import { sweepApi, type RobustLimit, type RobustStats } from "../../sweeps/api";
import { idOfParams, maskOfKey } from "../../sweeps/groups";
import { labelOf, fmtValue } from "../../sweeps/scales";
import { notify, notifyError } from "../../sweeps/notify";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import NumField from "./NumField";

const CANDIDATES = 5;
type Centre = Record<string, string | number | null>;

export default function RobustSheet({ study }: { study: Study }) {
  const t = useT();
  const a = study.answer!;
  const q = study.question;
  const v = study.view;
  const tols = Object.keys(q.robust ?? {});
  const direction = q.goal?.direction ?? "max";
  const order = useMemo(() => a.sets.filter((c) => c.group === "param").map((c) => c.name), [a]);
  // the candidates: the best sets by rank
  const centres = useMemo((): Centre[] => {
    const rank = a.sets.find((c) => c.name === "#rank")?.values;
    if (!rank) return [];
    const idx = [...rank.keys()].filter((i) => Number.isFinite(rank[i])).sort((x, y) => rank[x] - rank[y]).slice(0, CANDIDATES);
    const ps = a.sets.filter((c) => c.group === "param");
    return idx.map((i) => Object.fromEntries(ps.map((c) => [c.name, c.kind === "cat" ? labelOf(c, c.values[i]) : c.values[i]])));
  }, [a]);
  const [n, setN] = useState(200);
  const [method, setMethod] = useState<"lhs" | "mc">("lhs");
  const [pct, setPct] = useState(95);
  const [limit, setLimit] = useState<RobustLimit | null>(null);
  const [rows, setRows] = useState<RobustStats[] | null>(null);
  // the candidates the rows were asked for (the answer may change - and the best sets with it - after)
  const [asked, setAsked] = useState<Centre[]>([]);
  const [busy, setBusy] = useState(false);
  const [group, setGroup] = useState(v.activeGroup ?? "all");
  const [gstats, setGstats] = useState<RobustStats | null>(null);

  if (!q.goal) return null;
  const onModel = async () => {
    setBusy(true);
    try {
      const wq = wireQuestion(study);
      const r = await sweepApi.surrogateTrain(study.tableId, wq, null, null);
      if (!r.best) throw new Error(t("swRobustNoModel"));
      const m = await sweepApi.robustModel(study.tableId, wq, r.key, r.best, centres, n, method, direction, pct, limit);
      setRows(m.rows); setAsked(centres);
    } catch (e) { notifyError(e); } finally { setBusy(false); }
  };
  const runAround = async (k: number) => {
    try {
      const r = await sweepApi.robustSample(study.tableId, wireQuestion(study), asked[k], n, method, 0);
      const gs = v.groups ?? [];
      let color = 0;
      while (gs.some((g) => g.color === color)) color++;
      const ids = [...new Set(r.sets.map((p) => idOfParams(p, order)))];
      useSweeps.getState().setView({ groups: [...gs, { id: `g${Date.now().toString(36)}r`, name: t("swRobustGroup", { k: k + 1 }), color, source: "doe", frozen: true, ids }] });
      notify(t("swRobustSaved", { n: ids.length }));
    } catch (e) { notifyError(e); }
  };
  const statsOf = async () => {
    const m = maskOfKey(a, v.groups ?? [], group, v.rerun);
    const sets = m ? [...m.keys()].filter((i) => m[i]) : [...Array(a.sets[0]?.values.length ?? 0).keys()];
    try { setGstats(await sweepApi.robustStats(study.tableId, wireQuestion(study), sets, direction, pct, limit)); } catch (e) { notifyError(e); }
  };
  const groups = [{ id: "all", name: t("swGrpAll") }, ...(v.groups ?? []).map((g) => ({ id: g.id, name: g.name }))];
  return (
    <section className="sw-robust-sheet" aria-label={t("swRobustTitle")}>
      <h3>{t("swRobustTitle")}</h3>
      <p className="hint">{t("swRobustSheetHint")}</p>
      {tols.length === 0 ? <p className="sw-warn">{t("swRobustNeedTol")} <button className="linklike" onClick={() => useSweeps.getState().setView({ step: "goals" })}>{t("swEditGoal")}</button></p> : <>
        <p className="hint">{tols.map((c) => { const x = q.robust![c]; return `${c} ±${x.value}${x.mode === "pct" ? "%" : x.mode === "steps" ? ` ${t("swTolSteps")}` : ""} (${t(`swDist_${x.dist ?? "uniform"}`)})`; }).join(" · ")}</p>
        <div className="sw-row sw-robust-opts">
          <label>{t("swRobustSamples")} <NumField value={n} lo={10} hi={20000} label={t("swRobustSamples")} onChange={(x) => setN(Math.max(10, Math.min(20000, Math.round(x))))} /></label>
          <label>{t("swRobustSampling")} <select aria-label={t("swRobustSampling")} value={method} onChange={(e) => setMethod(e.target.value as "lhs" | "mc")}>
            <option value="lhs">{t("swRobustLhs")}</option><option value="mc">{t("swRobustMc")}</option></select></label>
          <label>{t("swRobustPct")} <NumField value={pct} lo={50} hi={99.9} label={t("swRobustPct")} onChange={(x) => setPct(Math.max(50, Math.min(99.9, x)))} /></label>
          <label>{t("swRobustLimit", { c: q.goal.column })} <select aria-label={t("swRobustLimitOp")} value={limit?.op ?? ""}
            onChange={(e) => setLimit(e.target.value ? { op: e.target.value as RobustLimit["op"], value: limit?.value ?? 0 } : null)}>
            <option value="">–</option>{["<=", "<", ">=", ">"].map((o) => <option key={o} value={o}>{o}</option>)}</select>
            {limit && <NumField value={limit.value} lo={-1e12} hi={1e12} label={t("swRobustLimitValue")} onChange={(x) => setLimit({ ...limit, value: x })} />}</label>
        </div>
        {!centres.length && <p className="hint">{t("swRobustNoBest")}</p>}
        <button className="btn primary" disabled={busy || !centres.length} onClick={onModel}>{busy ? "…" : t("swRobustOnModel", { n: centres.length })}</button>
        {rows && <>
          <table className="sw-robust-table">
            <thead><tr><th>#</th><th>{t("swRoleParam")}</th><th>{t("swRobustNominal")}</th><th>{t("swRobustMean")}</th><th>σ</th><th>{t("swRobustPctCol", { p: pct })}</th>{limit && <th>{t("swRobustPFail")}</th>}<th /></tr></thead>
            <tbody>{rows.map((r, k) => (
              <tr key={k} data-k={k}>
                <td>{k + 1}</td>
                <td className="mono">{order.map((p) => `${p}=${typeof asked[k]?.[p] === "number" ? fmtValue(asked[k][p] as number) : asked[k]?.[p] ?? "–"}`).join(", ")}</td>
                <td>{fmtValue(r.nominal ?? NaN)}</td><td>{fmtValue(r.mean ?? NaN)}</td><td>{fmtValue(r.std ?? NaN)}</td><td>{fmtValue(r.pct ?? NaN)}</td>
                {limit && <td className={(r.pFail ?? 0) > 0 ? "sw-warn-txt" : ""}>{r.pFail === undefined || r.pFail === null ? "–" : `${(r.pFail * 100).toFixed(1)}%`}</td>}
                <td><button className="btn outline" onClick={() => runAround(k)}>{t("swRobustRunReal")}</button></td>
              </tr>))}</tbody>
          </table>
          <MeanSigma t={t} rows={rows} />
        </>}
        <div className="sw-row">
          <label>{t("swRobustGroupStats")} <select aria-label={t("swRobustGroupStats")} value={group} onChange={(e) => { setGroup(e.target.value); setGstats(null); }}>
            {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></label>
          <button className="btn outline" onClick={statsOf}>{t("swRobustCompute")}</button>
        </div>
        {gstats && <p className="sw-robust-gstats">{t("swRobustGroupLine", { n: gstats.valid, mean: fmtValue(gstats.mean ?? NaN), s: fmtValue(gstats.std ?? NaN), p: pct, v: fmtValue(gstats.pct ?? NaN) })}
          {gstats.pFail !== undefined && gstats.pFail !== null && ` · ${t("swRobustPFail")} ${(gstats.pFail * 100).toFixed(1)}%`}</p>}
      </>}
    </section>
  );
}

/** Mean against σ: the better mean to one side, the smaller spread down. */
function MeanSigma({ t, rows }: { t: ReturnType<typeof useT>; rows: RobustStats[] }) {
  const pts = rows.map((r, k) => ({ k, m: r.mean, s: r.std })).filter((p): p is { k: number; m: number; s: number } => p.m !== null && p.s !== null);
  if (pts.length < 1) return null;
  const W = 320, H = 180, L = 52, B = 30, T = 8, R = 12;
  const ext = (xs: number[]) => { const lo = Math.min(...xs), hi = Math.max(...xs); const pad = (hi - lo || Math.abs(hi) || 1) * 0.1; return [lo - pad, hi + pad]; };
  const [x0, x1] = ext(pts.map((p) => p.m)), [y0, y1] = ext(pts.map((p) => p.s));
  const px = (v: number) => L + ((v - x0) / (x1 - x0)) * (W - L - R), py = (v: number) => H - B - ((v - y0) / (y1 - y0)) * (H - B - T);
  return (
    <figure className="sw-robust-plot">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("swRobustPlot")}>
        <line x1={L} y1={H - B} x2={W - R} y2={H - B} className="sw-axis-line" /><line x1={L} y1={T} x2={L} y2={H - B} className="sw-axis-line" />
        <text x={(L + W - R) / 2} y={H - 4} textAnchor="middle" className="sw-ax">{t("swRobustMean")}</text>
        <text x={12} y={(T + H - B) / 2} textAnchor="middle" className="sw-ax" transform={`rotate(-90 12 ${(T + H - B) / 2})`}>σ</text>
        <text x={L} y={H - B + 12} className="sw-ax">{fmtValue(x0)}</text><text x={W - R} y={H - B + 12} textAnchor="end" className="sw-ax">{fmtValue(x1)}</text>
        {pts.map((p) => <g key={p.k}><circle cx={px(p.m)} cy={py(p.s)} r={4} className="kept" /><text x={px(p.m) + 6} y={py(p.s) - 4} className="sw-ax">{p.k + 1}</text></g>)}
      </svg>
    </figure>
  );
}
