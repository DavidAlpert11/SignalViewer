/* Step 5's side: which goal is answered (switch between them here too), the answer, what is
   filtered now, and the runs left out. */
import { useT } from "../../i18n";
import { hasFilter } from "../../sweeps/filters";
import { useSweeps, type Study } from "../../sweeps/state";
import { colLabel, scopeKey, setColumns } from "../../sweeps/view";
import { labelOf } from "../../sweeps/scales";
import { goalName, goalSummary } from "./GoalsStep";
import { StepFoot } from "./StepNav";

export default function ResultsSide({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const q = study.question, v = study.view, a = study.answer;
  const filters = Object.entries(v.filters).filter(([, f]) => hasFilter(f));
  const steps = v.scope.key === scopeKey(study) ? v.scope.steps : [];
  return (
    <div className="sw-side-step">
      <label className="sw-field">{t("swGoal")}
        <select value={q.active} onChange={(e) => st.setActiveGoal(Number(e.target.value))}>
          {q.goals.map((g, i) => <option key={i} value={i}>{goalName(t, g, i)}</option>)}
        </select>
      </label>
      <p className="hint">{goalSummary(t, q.goals[q.active])} <button className="linklike" onClick={() => st.setView({ step: "goals" })}>{t("swEditGoal")}</button></p>
      <div className="sw-answer" aria-live="polite">
        {study.evalError ? <p className="sw-error">{study.evalError}</p> : a ? (
          <>
            <div className="sw-answer-n">{a.counts.holding.toLocaleString()} <span>{t("swOfSetsHold", { n: a.counts.sets.toLocaleString() })}</span></div>
            <div className="hint">{t("swCombosEach", { n: a.counts.combos })}</div>
            {a.counts.complete < a.counts.sets && <div className="hint">{t("swIncomplete", { n: (a.counts.sets - a.counts.complete).toLocaleString() })}</div>}
            {a.conditions.map((c, i) => <div key={i} className="hint">{c.label}: {t("swMetBy", { n: c.met })}</div>)}
          </>
        ) : <p className="hint">{t("swReading")}</p>}
      </div>
      {a && <BestSet study={study} />}
      <div className="sw-hide-box">
        <b>{t("swNowShown")}</b>
        {filters.length === 0 && steps.length === 0 && <span className="hint">{t("swRepNothing")}</span>}
        {filters.map(([name]) => (
          <div key={name} className="sw-row"><span>{colLabel(t, study, name)}</span>
            <button className="iconbtn" aria-label={t("swClearFilter")} onClick={() => st.setFilter(name, null)}>×</button></div>
        ))}
        {steps.map((s, i) => <span key={i} className="hint">{t(s.kind === "keep" ? "swRepKept" : "swRepExcluded", { i: i + 1, n: s.sets.length })}</span>)}
        {q.exclude.length > 0 && <span className="hint">{t("swLeftOutN", { n: q.exclude.length })} <button className="linklike" onClick={() => st.setQuestion({ exclude: [] })}>{t("swKeepAll")}</button></span>}
      </div>
      <p className="hint">{t("swResultsNextHint")}</p>
      <StepFoot study={study} />
    </div>
  );
}

/** The best set (S10): where the optimization shows - the set ranked first, its parameters and its
 *  goal (its score with several objectives, its worst case within the tolerance when robust). */
function BestSet({ study }: { study: Study }) {
  const t = useT();
  const cols = setColumns(study);
  const rank = cols.get("#rank")?.values;
  if (!rank || !study.question.goal) return null;
  let best = -1;
  for (let i = 0; i < rank.length; i++) if (Number.isFinite(rank[i]) && (best < 0 || rank[i] < rank[best])) best = i;
  if (best < 0) return <div className="sw-hide-box sw-best"><b>★ {t("swBestSetTitle")}</b><span className="hint">{t("swNoBestSet")}</span></div>;
  const show = (name: string) => { const c = cols.get(name); return c ? labelOf(c, c.values[best]) : "–"; };
  const params = study.answer!.sets.filter((c) => c.group === "param").map((c) => c.name);
  const extra = ["#robustGoal", "#score"].filter((n) => cols.has(n));
  return (
    <div className="sw-hide-box sw-best">
      <b>★ {t("swBestSetTitle")}</b>
      <div className="sw-best-goal"><span>{colLabel(t, study, "#goal")}</span><b>{show("#goal")}</b></div>
      {extra.map((n) => <div key={n} className="sw-best-goal"><span>{colLabel(t, study, n)}</span><b>{show(n)}</b></div>)}
      <div className="sw-best-params">{params.map((p) => <span key={p}>{p} = <b>{show(p)}</b></span>)}</div>
      <button className="btn outline" onClick={() => useSweeps.getState().setView({ pinned: best })}>{t("swOpenBestSet")}</button>
    </div>
  );
}
