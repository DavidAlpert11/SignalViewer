/* Decide (MF10): rank the sets the draft leaves on its objectives by a chosen method - weighted
   sum (the draft's own ranking), TOPSIS, Hurwicz (optimism α), Savage (least regret) - with weights
   from the sliders or from pairwise comparisons (eigenvector, consistency ratio), and a margin under
   which two sets are tied. Each row says why it is above the next: each objective's part of the
   difference. The maths is the server's (svcore/sweep/mcdm.py); the top sets can be kept as a group. */
import { useEffect, useMemo, useState } from "react";
import type { TFn } from "../../i18n";
import { sweepApi, type McdmResult } from "../../sweeps/api";
import { objectiveCol, type DecideSpec, type Draft, type Explored } from "../../sweeps/explore";
import { setIds } from "../../sweeps/groups";
import type { Answer, Col } from "../../sweeps/model";
import { notify } from "../../sweeps/notify";
import { fmtValue, labelOf } from "../../sweeps/scales";
import { useSweeps, type Study } from "../../sweeps/state";
import { activeParams } from "../../sweeps/view";

const METHODS: DecideSpec["method"][] = ["weighted", "topsis", "hurwicz", "savage"];
/** Saaty's scale, as offered in each cell: i over j */
const SCALE = [9, 7, 5, 3, 1, 1 / 3, 1 / 5, 1 / 7, 1 / 9];
const scaleLabel = (v: number) => (v >= 1 ? String(Math.round(v)) : `1/${Math.round(1 / v)}`);
const SHOW = 10;
/** more sets than this: the first ones by the draft's ranking are sent (the rest cannot be first) */
const MAX_SETS = 5000;

export const DEFAULT_DECIDE: DecideSpec = { method: "weighted", alpha: 0.5, margin: 0 };

export default function DecidePanel({ t, study, a, cols, ex, draft, setDraft }: {
  t: TFn; study: Study; a: Answer; cols: Map<string, Col>; ex: Explored; draft: Draft; setDraft: (d: Draft) => void;
}) {
  const spec = draft.decide ?? DEFAULT_DECIDE;
  const objs = draft.objectives;
  const set = (p: Partial<DecideSpec>) => setDraft({ ...draft, decide: { ...spec, ...p } });
  const rows = useMemo(() => ex.ranked.slice(0, MAX_SETS), [ex]);
  const [res, setRes] = useState<McdmResult | null>(null);
  const [err, setErr] = useState("");
  const pairwise = spec.pairwise && spec.pairwise.length === objs.length ? spec.pairwise : null;
  const ask = JSON.stringify([rows.length, rows.slice(0, 50), objs.map((o) => [o.column, o.direction, o.weight]), spec.method, spec.alpha, spec.margin, pairwise]);
  useEffect(() => {
    if (objs.length < 2 || !rows.length) { setRes(null); return; }
    let live = true;
    const vals = rows.map((s) => objs.map((_, k) => { const v = cols.get(objectiveCol(k))?.values[s]; return v !== undefined && Number.isFinite(v) ? v : null; }));
    const timer = window.setTimeout(() => {
      sweepApi.mcdm(vals, objs.map((o) => o.direction), objs.map((o) => o.weight), spec.method, spec.alpha, spec.margin, pairwise)
        .then((r) => { if (live) { setRes(r); setErr(""); } }).catch((e) => live && setErr((e as Error).message));
    }, 150);
    return () => { live = false; window.clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ask]);

  if (objs.length < 2) return null;
  const params = activeParams(study);
  const show = (c: string, s: number) => { const col = cols.get(c); return col ? labelOf(col, col.values[s]) : "–"; };
  const top = res ? res.order.slice(0, SHOW) : [];
  const saveGroup = () => {
    if (!res) return;
    const n = Math.min(SHOW, res.order.length);
    const ids = setIds(a);
    const st = useSweeps.getState();
    const gs = study.view.groups ?? [];
    let color = 0;
    while (gs.some((g) => g.color === color)) color++;
    st.setView({ groups: [...gs, { id: `g${Date.now().toString(36)}m`, name: t("swDecideGroup", { n, m: t(`swDecide_${spec.method}`) }), color,
      source: "user", frozen: true, ids: res.order.slice(0, n).map((i) => ids[rows[i]]) }], colorBy: "#group" });
    notify(t("swDecideSaved", { n }));
  };
  const setCell = (i: number, j: number, v: number) => {
    const m = pairwise ? pairwise.map((r) => [...r]) : objs.map((_, a) => objs.map((__, b) => (a === b ? 1 : 1)));
    m[i][j] = v; m[j][i] = 1 / v;
    set({ pairwise: m });
  };
  return (
    <section className="sw-hide-box sw-decide" aria-label={t("swDecideTitle")}>
      <b>{t("swDecideTitle")}</b>
      <div className="sw-seg" role="radiogroup" aria-label={t("swDecideMethod")}>
        {METHODS.map((m) => (
          <button key={m} role="radio" aria-checked={spec.method === m} className={spec.method === m ? "on" : ""}
            title={t(`swDecideHint_${m}`)} onClick={() => set({ method: m })}>{t(`swDecide_${m}`)}</button>
        ))}
      </div>
      <p className="hint">{t(`swDecideHint_${spec.method}`)}</p>
      {spec.method === "hurwicz" && (
        <label className="sw-explore-line">{t("swDecideAlpha")}
          <input type="range" min={0} max={1} step={0.05} value={spec.alpha} aria-label={t("swDecideAlpha")} onChange={(e) => set({ alpha: Number(e.target.value) })} />
          <span className="mono">{spec.alpha.toFixed(2)}</span></label>
      )}
      <label className="sw-explore-line">{t("swDecideMargin")}
        <input type="range" min={0} max={0.2} step={0.01} value={spec.margin} aria-label={t("swDecideMargin")} onChange={(e) => set({ margin: Number(e.target.value) })} />
        <span className="mono">{Math.round(spec.margin * 100)}%</span></label>
      <label className="acheck">
        <input type="checkbox" checked={!!pairwise} onChange={(e) => set({ pairwise: e.target.checked ? objs.map(() => objs.map(() => 1)) : undefined })} />
        {t("swDecidePairwise")}</label>
      {pairwise && (
        <div className="sw-decide-pairs">
          <table>
            <thead><tr><th />{objs.map((o) => <th key={o.column} className="mono">{o.column}</th>)}</tr></thead>
            <tbody>{objs.map((o, i) => (
              <tr key={o.column}><th className="mono">{o.column}</th>
                {objs.map((_, j) => <td key={j}>{j <= i ? <span className="hint">{i === j ? "1" : scaleLabel(pairwise[i][j])}</span> : (
                  <select aria-label={t("swDecidePairOf", { a: o.column, b: objs[j].column })} value={scaleLabel(pairwise[i][j])}
                    onChange={(e) => setCell(i, j, SCALE.find((v) => scaleLabel(v) === e.target.value) ?? 1)}>
                    {SCALE.map((v) => <option key={v} value={scaleLabel(v)}>{scaleLabel(v)}</option>)}
                  </select>)}</td>)}
              </tr>))}</tbody>
          </table>
          <p className="hint">{t("swDecidePairHint")}</p>
          {res?.ahp && <p className={res.ahp.consistent ? "hint" : "sw-warn"} data-cr={res.ahp.cr.toFixed(3)}>
            {t(res.ahp.consistent ? "swDecideCrOk" : "swDecideCrBad", { cr: res.ahp.cr.toFixed(2) })}</p>}
        </div>
      )}
      {res && <p className="hint">{t("swDecideWeights")}: {objs.map((o, k) => `${o.column} ${Math.round(res.weights[k] * 100)}%`).join(" · ")}</p>}
      {err && <p className="sw-error">{err}</p>}
      {res && (
        <ol className="sw-decide-list">
          {top.map((i, pos) => {
            const s = rows[i];
            const why = res.why[pos];
            return (
              <li key={s} data-set={s}>
                <div className="sw-decide-row">
                  <span className="sw-decide-rank">{res.ranks[i]}</span>
                  <button className="linklike" onClick={() => useSweeps.getState().setView({ pinned: s })}>
                    {params.map((p) => `${p}=${show(p, s)}`).join(", ")}</button>
                  <span className="mono">{fmtValue(res.scores[i])}</span>
                </div>
                {why && pos < top.length - 1 && <div className="hint sw-decide-why">
                  {why.tie ? t("swDecideTie") : t("swDecideAbove")}{" "}
                  {why.parts.map((d, k) => ({ d, k })).filter((x) => Math.abs(x.d) > 1e-9).sort((x, y) => Math.abs(y.d) - Math.abs(x.d))
                    .map(({ d, k }) => <span key={k} className={d > 0 ? "sw-decide-plus" : "sw-decide-minus"}>{objs[k].column} {d > 0 ? "+" : "−"}{Math.abs(d * 100).toFixed(1)}</span>)}
                </div>}
              </li>
            );
          })}
        </ol>
      )}
      {res && res.order.length > 0 && <button className="btn outline" onClick={saveGroup}>{t("swDecideSave", { n: Math.min(SHOW, res.order.length) })}</button>}
    </section>
  );
}
