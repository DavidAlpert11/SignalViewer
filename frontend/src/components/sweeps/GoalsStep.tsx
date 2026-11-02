/* Step 3 - the goal (2026-11-01, the owner's redesign): one table, a row per column - a limit on a
   column is a filter on it (at least / at most; an output in every scenario), and what to optimize.
   The rest (conditions in some scenarios, expressions, how an output shows per set, robustness,
   several goals) is under "More options".
   Before: conditions the outputs must meet in every scenario (all of them, or any one),
   and what to optimize. A study keeps several goals - Goal 1, Goal 2... - to try what happens when
   a limit moves: the table in the middle sets them side by side (how many sets hold, the best,
   how robust), and a click makes one the goal the results show. */
import { useEffect, useState } from "react";
import type { Condition } from "../../sweeps/model";
import { useT, type TFn } from "../../i18n";
import { sweepApi, type VariantResult } from "../../sweeps/api";
import { OUTPUT_AGGS, condText, type GoalVariant, type SetOp } from "../../sweeps/model";
import { fmtValue } from "../../sweeps/scales";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import ConditionRow from "./ConditionRow";
import RobustEditor from "./RobustEditor";
import BestSet from "./BestSet";
import { StepFoot } from "./StepNav";

export const goalName = (t: TFn, g: GoalVariant, i: number) => (g.name && Number.isNaN(Number(g.name)) ? g.name : t("swGoalN", { n: i + 1 }));

export const goalSummary = (t: TFn, g: GoalVariant) => {
  const conds = g.conditions.map(condText).join(g.combine === "or" ? ` ${t("swOr")} ` : ` ${t("swAnd")} `);
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
  const more = useSweeps((x) => x.goalMore);
  const setMore = (v: boolean) => useSweeps.setState({ goalMore: v });
  return (
    <div className="sw-side-step">
      <p className="sw-step-intro">{t("swGoalIntro2")}</p>
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
      {a && <div className="sw-answer sw-goal-count" aria-live="polite"><div className="sw-answer-n">{a.counts.holding.toLocaleString()} <span>{t("swOfSetsHold", { n: a.counts.sets.toLocaleString() })}</span></div></div>}
      {a && <BestSet study={study} />}
      <details className="sw-more" open={more} onToggle={(e) => setMore((e.target as HTMLDetailsElement).open)}>
      <summary>{t("swGoalMore")}</summary>
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
        <label className="sw-agg">{t("swOutputsPerSet")}
          <select value={q.outputAgg} onChange={(e) => st.setQuestion({ outputAgg: e.target.value as SetOp })}>{OUTPUT_AGGS.map((o) => <option key={o} value={o}>{o}</option>)}</select></label>
      </section>
      <RobustEditor study={study} />
      <button className="linklike sw-danger" onClick={() => st.removeGoal(q.active)}>{q.goals.length > 1 ? t("swGoalDelete") : t("swGoalClear")}</button>
      </details>
      <StepFoot study={study} next={t("swGoalSeeResults")} />
    </div>
  );
}

/** The goal as one table: a row per parameter and output - at least / at most (a filter on that
 *  column; an output in every scenario) and what to optimize. Conditions of other forms are kept
 *  and edited under "More options". With two goals or more, they are compared below. */
export function GoalsCenter({ study }: { study: Study }) {
  const t = useT();
  const q = study.question;
  return (
    <div className="sw-goals-center">
      <GoalTable study={study} />
      {q.goals.length > 1 && <><h3 className="sw-sub">{t("swGoalsCompare")}</h3><GoalsCompare study={study} /></>}
    </div>
  );
}

/** a condition the table shows: at least / at most, in every scenario, nothing else */
const simple = (c: Condition) => c.mode === "all" && !c.where && !c.in && (c.op === ">=" || c.op === "<=");

function GoalTable({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const q = study.question;
  const g = q.goals[q.active];
  const a = study.answer;
  const removed = new Set(q.removed);
  const params = study.columns.filter((c) => c.role === "param" && c.kind === "number" && !removed.has(c.name));
  const outputs = [...study.columns.filter((c) => c.role === "output" && c.kind === "number" && !removed.has(c.name)),
    ...q.derived.map((d) => ({ name: d.name, min: undefined as number | undefined, max: undefined as number | undefined }))];
  const others = g.conditions.filter((c) => !simple(c)).length;
  const idx = (col: string, op: ">=" | "<=") => g.conditions.findIndex((c) => simple(c) && c.column === col && c.op === op);
  const setLimit = (col: string, op: ">=" | "<=", text: string) => {
    const i = idx(col, op);
    const v = Number(text.trim().replace(/,/g, ""));
    if (!text.trim()) { if (i >= 0) st.removeCondition(i); return; }
    if (!Number.isFinite(v)) return;
    if (i >= 0) st.updateCondition(i, { value: v }); else st.addCondition({ column: col, op, value: v, mode: "all" });
  };
  const opt = (col: string) => g.optimize.find((o) => o.column === col);
  const setOpt = (col: string, dir: "" | "min" | "max") => {
    const rest = g.optimize.filter((o) => o.column !== col);
    st.updateGoal({ optimize: dir ? [...g.optimize.map((o) => (o.column === col ? { ...o, direction: dir } : o)), ...(opt(col) ? [] : [{ column: col, direction: dir, weight: 1 }])] : rest });
  };
  const met = (col: string, op: ">=" | "<=") => { const i = idx(col, op); return i >= 0 ? a?.conditions[i]?.met : undefined; };
  const Limit = ({ col, op }: { col: string; op: ">=" | "<=" }) => {
    const i = idx(col, op);
    const m = met(col, op);
    return (
      <span className="sw-limit">
        <input key={`${col}${op}${i >= 0 ? g.conditions[i].value : ""}`} className="sw-limit-in mono" inputMode="decimal"
          aria-label={t(op === ">=" ? "swAtLeastOf" : "swAtMostOf", { c: col })} placeholder="–"
          defaultValue={i >= 0 ? String(g.conditions[i].value) : ""}
          onBlur={(e) => setLimit(col, op, e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); if (e.key === "Escape") { (e.target as HTMLInputElement).value = i >= 0 ? String(g.conditions[i].value) : ""; (e.target as HTMLInputElement).blur(); } }} />
        {m !== undefined && <span className="hint sw-limit-met" title={t("swLimitMetHint")}>{t("swLimitMet", { n: m })}</span>}
      </span>
    );
  };
  const row = (c: { name: string; min?: number; max?: number }, out: boolean) => {
    const o = opt(c.name);
    return (
      <tr key={c.name} data-col={c.name} className={(idx(c.name, ">=") >= 0 || idx(c.name, "<=") >= 0 || o) ? "sw-goal-on" : ""}>
        <td className="sw-col-name">{c.name}</td>
        <td className="hint">{c.min !== undefined && c.max !== undefined ? `${fmtValue(c.min)} – ${fmtValue(c.max)}` : ""}</td>
        <td><Limit col={c.name} op=">=" /></td>
        <td><Limit col={c.name} op="<=" /></td>
        <td>{out && (
          <select aria-label={t("swOptimizeOf", { c: c.name })} value={o?.direction ?? ""} onChange={(e) => setOpt(c.name, e.target.value as "" | "min" | "max")}>
            <option value="">–</option><option value="min">{t("swMinimize")}</option><option value="max">{t("swMaximize")}</option>
          </select>)}</td>
        <td>{out && o && g.optimize.length > 1 && (
          <input type="number" min={0} step={0.5} aria-label={t("swWeightOf", { c: c.name })} defaultValue={o.weight} key={`w${q.active}:${c.name}:${o.weight}`} style={{ width: 56 }}
            onBlur={(e) => st.updateGoal({ optimize: g.optimize.map((x) => (x.column === c.name ? { ...x, weight: Math.max(0, Number(e.target.value) || 0) } : x)) })} />)}</td>
      </tr>
    );
  };
  return (
    <>
      <p className="hint">{t("swGoalTableHint")}</p>
      <div className="sw-table-wrap">
        <table className="sw-table sw-goal-table">
          <thead><tr><th>{t("swColumn")}</th><th>{t("swRange")}</th><th>{t("swLimitMin")}</th><th>{t("swLimitMax")}</th><th>{t("swGoalOptimize")}</th><th>{g.optimize.length > 1 ? t("swWeight") : ""}</th></tr></thead>
          <tbody>
            {outputs.length > 0 && <tr className="sw-goal-group"><td colSpan={6}>{t("swGoalOutputs")}</td></tr>}
            {outputs.map((c) => row(c, true))}
            {params.length > 0 && <tr className="sw-goal-group"><td colSpan={6}>{t("swGoalParams")}</td></tr>}
            {params.map((c) => row(c, false))}
          </tbody>
        </table>
      </div>
      {others > 0 && <p className="hint">{t("swGoalOthers", { n: others })}</p>}
      <p className="hint sw-optimize-now" aria-live="polite">{optimizeNow(t, g, a)}</p>
      <div className="sw-row">
        <button className="btn primary" onClick={() => st.setView({ step: "results" })}>{t("swGoalSeeResults")} →</button>
      </div>
    </>
  );
}

/** The goals side by side. */
function GoalsCompare({ study }: { study: Study }) {
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
    </div>
  );
}
