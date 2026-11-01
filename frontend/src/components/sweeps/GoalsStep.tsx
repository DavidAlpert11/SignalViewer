/* Step 4 - the goal: conditions the outputs must meet in every scenario (all of them, or any one),
   and what to optimize. A study keeps several goals - Goal 1, Goal 2... - to try what happens when
   a limit moves: the table in the middle sets them side by side (how many sets hold, the best,
   how robust), and a click makes one the goal the results show. */
import { useEffect, useState } from "react";
import { useT, type TFn } from "../../i18n";
import { sweepApi, type VariantResult } from "../../sweeps/api";
import { OUTPUT_AGGS, type GoalVariant, type SetOp } from "../../sweeps/model";
import { fmtValue } from "../../sweeps/scales";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import ConditionRow from "./ConditionRow";
import RobustEditor from "./RobustEditor";
import { StepFoot } from "./StepNav";

export const goalName = (t: TFn, g: GoalVariant, i: number) => (g.name && Number.isNaN(Number(g.name)) ? g.name : t("swGoalN", { n: i + 1 }));

export const goalSummary = (t: TFn, g: GoalVariant) => {
  const conds = g.conditions.map((c) => `${c.column} ${c.op} ${c.value}`).join(g.combine === "or" ? ` ${t("swOr")} ` : ` ${t("swAnd")} `);
  const opt = g.optimize.map((o) => `${o.direction === "max" ? "↑" : "↓"} ${o.column}`).join(", ");
  return [conds, opt].filter(Boolean).join(" · ") || t("swGoalEmpty");
};

/** What the optimization does now, in a sentence: by what the sets that hold are ranked. */
function optimizeNow(t: TFn, g: GoalVariant, a: Study["answer"]): string {
  const n = (a?.counts.holding ?? 0).toLocaleString();
  // robust to some parameters: only the sets that hold robustly are ranked
  const rh = a?.sets.find((c) => c.name === "#robustHolds")?.values;
  let r = 0;
  if (rh) for (let i = 0; i < rh.length; i++) r += rh[i] === 1 ? 1 : 0;
  const robust = rh ? ` ${t("swOptimizeRobust", { n: r.toLocaleString() })}` : "";
  return optimizeLine(t, g, a, n) + (g.optimize.length ? robust : "");
}

function optimizeLine(t: TFn, g: GoalVariant, a: Study["answer"], n: string): string {
  if (!g.optimize.length) return t("swOptimizeNone");
  if (g.optimize.length === 1) {
    const o = g.optimize[0];
    return t("swOptimizeNow1", { n, c: o.column, dir: t(o.direction === "max" ? "swLargest" : "swSmallest") });
  }
  const pareto = a?.sets.find((c) => c.name === "#pareto")?.values;
  let p = 0;
  if (pareto) for (let i = 0; i < pareto.length; i++) p += pareto[i] === 1 ? 1 : 0;
  const list = g.optimize.map((o) => `${o.direction === "max" ? "↑" : "↓"}${o.column} ×${o.weight}`).join(", ");
  return t("swOptimizeNowN", { n, list, p });
}

export function GoalsSide({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const q = study.question;
  const g = q.goals[q.active];
  const removed = new Set(q.removed);
  const outputs = [...study.columns.filter((c) => c.role === "output" && !removed.has(c.name)).map((c) => c.name), ...q.derived.map((d) => d.name)];
  const a = study.answer;
  return (
    <div className="sw-side-step">
      <p className="sw-step-intro">{t("swGoalsIntro")}</p>
      <div className="sw-goal-tabs" role="tablist">
        {q.goals.map((x, i) => (
          <span key={i} className={`sw-goal-tab${i === q.active ? " on" : ""}`}>
            <button role="tab" aria-selected={i === q.active} onClick={() => st.setActiveGoal(i)}>{goalName(t, x, i)}</button>
            <button className="sw-tag-x" aria-label={t("swGoalDeleteN", { n: goalName(t, x, i) })} title={t("swGoalDeleteN", { n: goalName(t, x, i) })}
              onClick={() => st.removeGoal(i)}>×</button>
          </span>
        ))}
        <button className="linklike" onClick={() => st.addGoal(true)} title={t("swGoalCopyHint")}>{t("swGoalCopy")}</button>
        <button className="linklike" onClick={() => st.addGoal(false)}>{t("swGoalNew")}</button>
      </div>
      <label className="sw-field">{t("swGoalName")}
        <input value={g.name && Number.isNaN(Number(g.name)) ? g.name : ""} placeholder={goalName(t, g, q.active)} onChange={(e) => st.updateGoal({ name: e.target.value })} />
      </label>
      <section className="sw-goal-part">
        <h3>{t("swGoalMust")}</h3>
        {g.conditions.map((c, i) => (
          <div key={i}>
            {i > 0 && (
              <div className="sw-seg sw-andor" role="radiogroup" aria-label={t("swCombine")}>
                <button className={g.combine === "and" ? "on" : ""} onClick={() => st.updateGoal({ combine: "and" })}>{t("swAnd")}</button>
                <button className={g.combine === "or" ? "on" : ""} onClick={() => st.updateGoal({ combine: "or" })}>{t("swOr")}</button>
              </div>
            )}
            <ConditionRow study={study} i={i} c={c} outputs={outputs} met={a?.conditions[i]?.met} />
          </div>
        ))}
        <button className="btn outline sw-add-btn" disabled={!outputs.length}
          onClick={() => st.addCondition({ column: outputs[0], op: "<=", value: 0, mode: "all" })}>{t("swAddCondition")}</button>
      </section>
      <section className="sw-goal-part">
        <h3>{t("swGoalOptimize")}</h3>
        <span className="hint">{t("swGoalOptimizeHint")}</span>
        {g.optimize.map((o, i) => (
          <div key={i} className="sw-cond-line">
            <select aria-label={t("swObjective")} value={o.column} onChange={(e) => st.updateGoal({ optimize: g.optimize.map((x, j) => (j === i ? { ...x, column: e.target.value } : x)) })}>
              {outputs.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select aria-label={t("swDirection")} value={o.direction} onChange={(e) => st.updateGoal({ optimize: g.optimize.map((x, j) => (j === i ? { ...x, direction: e.target.value as "max" | "min" } : x)) })}>
              <option value="max">{t("swMaximize")}</option><option value="min">{t("swMinimize")}</option>
            </select>
            {g.optimize.length > 1 && <input type="number" min={0} step={0.5} aria-label={t("swWeight")} title={t("swWeight")} defaultValue={o.weight} style={{ width: 56 }}
              key={`w${q.active}:${i}:${o.weight}`}
              onBlur={(e) => st.updateGoal({ optimize: g.optimize.map((x, j) => (j === i ? { ...x, weight: Math.max(0, Number(e.target.value) || 0) } : x)) })} />}
            <button className="iconbtn" aria-label={t("swRemove")} onClick={() => st.updateGoal({ optimize: g.optimize.filter((_, j) => j !== i) })}>×</button>
          </div>
        ))}
        <button className="btn outline sw-add-btn" disabled={!outputs.length}
          onClick={() => st.updateGoal({ optimize: [...g.optimize, { column: outputs.find((o) => !g.optimize.some((x) => x.column === o)) ?? outputs[0], direction: "max", weight: 1 }] })}>{t("swAddObjective")}</button>
        <p className="hint sw-optimize-now" aria-live="polite">{optimizeNow(t, g, a)}</p>
        <label className="sw-agg">{t("swOutputsPerSet")}
          <select value={q.outputAgg} onChange={(e) => st.setQuestion({ outputAgg: e.target.value as SetOp })}>{OUTPUT_AGGS.map((o) => <option key={o} value={o}>{o}</option>)}</select></label>
      </section>
      <RobustEditor study={study} />
      <button className="linklike sw-danger" onClick={() => st.removeGoal(q.active)}>{q.goals.length > 1 ? t("swGoalDelete") : t("swGoalClear")}</button>
      <StepFoot study={study} next={t("swGoalSeeResults")} />
    </div>
  );
}

/** The goals side by side. */
export function GoalsCenter({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const q = study.question;
  const [res, setRes] = useState<VariantResult[] | null>(null);
  const [err, setErr] = useState("");
  const key = JSON.stringify([wireQuestion(study).roles, q.holdValues, q.derived, q.exclude, q.removed, q.goals]);
  useEffect(() => {
    let live = true;
    const t0 = window.setTimeout(() => {
      const vs = q.goals.map((g) => ({ goal: g.optimize[0] ? { column: g.optimize[0].column, direction: g.optimize[0].direction } : null,
        conditions: g.conditions, combine: g.combine, objectives: g.optimize.length >= 2 ? g.optimize : [] }));
      sweepApi.variants(study.tableId, wireQuestion(study), vs).then((r) => { if (live) { setRes(r.variants); setErr(""); } }).catch((e) => live && setErr((e as Error).message));
    }, 250);
    return () => { live = false; window.clearTimeout(t0); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [study.tableId, key]);
  return (
    <div className="sw-goals-center">
      <p className="hint">{t("swGoalsCompareHint")}</p>
      {err && <p className="sw-error">{err}</p>}
      <div className="sw-table-wrap">
        <table className="sw-table sw-variants">
          <thead><tr><th>{t("swGoal")}</th><th>{t("swGoalWhat")}</th><th className="num">{t("swRepHolding")}</th><th className="num">{t("swBestValue")}</th>
            <th>{t("swBestSet")}</th><th className="num" title={t("swNeighboursHint")}>{t("swRobust")}</th><th className="num" title={t("swToleranceHint")}>{t("swToleranceCol")}</th><th /></tr></thead>
          <tbody>{q.goals.map((g, i) => {
            const r = res?.[i];
            return (
              <tr key={i} className={i === q.active ? "pinned" : ""} onClick={() => st.setActiveGoal(i)}>
                <td><b>{goalName(t, g, i)}</b></td>
                <td className="sw-wrap">{goalSummary(t, g)}</td>
                <td className="num">{r?.error ? <span className="sw-error">{r.error}</span> : r ? `${r.holding} / ${r.sets}` : "…"}</td>
                <td className="num">{r?.best ? fmtValue(r.best.value) : "–"}{r?.best?.score != null && <span className="hint"> · {t("swScoreCol")} {fmtValue(r.best.score)}</span>}</td>
                <td className="hint">{r?.best ? Object.values(r.best.params).join(" · ") : ""}</td>
                <td className="num">{r?.robust != null ? `${Math.round(r.robust * 100)}%` : "–"}</td>
                <td className="num">{r?.tolerance != null ? r.tolerance : "–"}</td>
                <td onClick={(e) => e.stopPropagation()}><button className="iconbtn" aria-label={t("swGoalDeleteN", { n: goalName(t, g, i) })}
                  title={t("swGoalDeleteN", { n: goalName(t, g, i) })} onClick={() => st.removeGoal(i)}>×</button></td>
              </tr>
            );
          })}</tbody>
        </table>
      </div>
      <div className="sw-row">
        <button className="btn outline" onClick={() => st.addGoal(true)}>{t("swGoalCopy")}</button>
        <button className="btn primary" onClick={() => st.setView({ step: "results" })}>{t("swGoalSeeResults")} →</button>
      </div>
    </div>
  );
}
