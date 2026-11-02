/* Step 5's side: which goal is answered (switch between them here too), the answer, what is
   filtered now, and the runs left out. */
import { useT } from "../../i18n";
import { hasFilter } from "../../sweeps/filters";
import { useSweeps, type Study } from "../../sweeps/state";
import { colLabel, scopeKey } from "../../sweeps/view";
import { goalName, goalSummary } from "./GoalsStep";
import { StepFoot } from "./StepNav";
import BestSet from "./BestSet";
import GroupsPanel from "./GroupsPanel";

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
      {a && <GroupsPanel study={study} />}
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
