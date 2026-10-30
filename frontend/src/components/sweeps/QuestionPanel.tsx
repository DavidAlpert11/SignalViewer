/* The question, on the left: 1 what we choose, 2 what it must hold across (and which values),
   3 the goal and the conditions, and new columns. The answer's count under it. */
import { useT } from "../../i18n";
import { OUTPUT_AGGS, type SetOp } from "../../sweeps/model";
import { useSweeps, type Study } from "../../sweeps/state";
import ConditionRow from "./ConditionRow";
import DerivedEditor from "./DerivedEditor";

export default function QuestionPanel({ study, onColumns }: { study: Study; onColumns: () => void }) {
  const t = useT();
  const st = useSweeps.getState();
  const q = study.question;
  const params = study.columns.filter((c) => c.role === "param");
  const holds = study.columns.filter((c) => c.role === "hold");
  const outputs = [...study.columns.filter((c) => c.role === "output").map((c) => c.name),
    ...q.derived.map((d) => d.name)];
  const a = study.answer;
  return (
    <div className="sw-question">
      <section>
        <h3><span className="sw-step">1</span>{t("swRoleParam")}<span className="hint"> · {t("swWhatWeChoose")}</span></h3>
        <div className="sw-tags">{params.map((c) => <span key={c.name} className="sw-tag">{c.name}</span>)}
          <button className="linklike" onClick={onColumns}>{t("swEditColumns")}</button></div>
        {!params.length && <p className="sw-warn">{t("swNoParams")}</p>}
      </section>
      <section>
        <h3><span className="sw-step">2</span>{t("swRoleHold")}<span className="hint"> · {t("swWhatWeDont")}</span></h3>
        {holds.map((c) => {
          const all = c.values ?? [];
          const kept = q.holdValues[c.name]?.length ? q.holdValues[c.name] : all;
          return (
            <div key={c.name} className="sw-hold">
              <div className="sw-hold-name">{c.name}</div>
              {all.length ? (
                <div className="sw-hold-values">
                  {all.map((v) => {
                    const on = kept.includes(v);
                    return <button key={String(v)} className={`sw-pill${on ? " on" : ""}`} aria-pressed={on}
                      onClick={() => {
                        const next = on ? kept.filter((x) => x !== v) : [...kept, v];
                        if (next.length) st.setHoldValues(c.name, next.length === all.length ? [] : next);
                      }}>{String(v)}</button>;
                  })}
                </div>
              ) : <span className="hint">{t("swDistinct", { n: c.distinct })}</span>}
            </div>
          );
        })}
        {!holds.length && <p className="hint">{t("swNoHolds")}</p>}
        {a && <p className="hint">{t("swCombosEach", { n: a.counts.combos })}</p>}
      </section>
      <section>
        <h3><span className="sw-step">3</span>{t("swGoalAndConditions")}</h3>
        <div className="sw-goal">
          <select aria-label={t("swGoal")} value={q.goal?.column ?? ""} onChange={(e) => st.setQuestion({ goal: e.target.value ? { column: e.target.value, direction: q.goal?.direction ?? "max" } : null })}>
            <option value="">{t("swNoGoal")}</option>
            {outputs.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
          {q.goal && (
            <div className="sw-seg">
              <button className={q.goal.direction === "max" ? "on" : ""} onClick={() => st.setQuestion({ goal: { ...q.goal!, direction: "max" } })}>{t("swMaximize")}</button>
              <button className={q.goal.direction === "min" ? "on" : ""} onClick={() => st.setQuestion({ goal: { ...q.goal!, direction: "min" } })}>{t("swMinimize")}</button>
            </div>
          )}
        </div>
        {q.goal && <p className="hint">{t(q.goal.direction === "max" ? "swGoalHintMax" : "swGoalHintMin")}</p>}
        {q.conditions.map((c, i) => <ConditionRow key={i} study={study} i={i} c={c} outputs={outputs} met={a?.conditions[i]?.met} />)}
        <button className="btn outline sw-add-btn" disabled={!outputs.length}
          onClick={() => st.addCondition({ column: outputs[0], op: "<=", value: 0, mode: "all" })}>{t("swAddCondition")}</button>
      </section>
      <section>
        <h3>{t("swNewColumns")}</h3>
        {q.derived.map((d, i) => (
          <div key={i} className="sw-derived">
            <b>ƒ {d.name}</b>
            <span className="hint">{d.kind === "row" ? d.expr : `${d.op}(${d.column})${d.where ? " · " + Object.entries(d.where).map(([k, v]) => `${k} ∈ {${v.join(", ")}}`).join(" · ") : ""}`}</span>
            <button className="iconbtn" aria-label={t("swRemove")} onClick={() => st.removeDerived(i)}>×</button>
          </div>
        ))}
        <DerivedEditor study={study} />
      </section>
      <section>
        <label className="sw-agg">{t("swOutputsPerSet")}
          <select value={q.outputAgg} onChange={(e) => st.setQuestion({ outputAgg: e.target.value as SetOp })}>
            {OUTPUT_AGGS.map((o) => <option key={o} value={o}>{o}</option>)}
          </select></label>
      </section>
      <div className="sw-answer" aria-live="polite">
        {study.evalError ? <p className="sw-error">{study.evalError}</p> : a ? (
          <>
            <div className="sw-answer-n">{a.counts.holding.toLocaleString()} <span>{t("swOfSetsHold", { n: a.counts.sets.toLocaleString() })}</span></div>
            {a.counts.complete < a.counts.sets && <div className="hint">{t("swIncomplete", { n: (a.counts.sets - a.counts.complete).toLocaleString() })}</div>}
          </>
        ) : <p className="hint">{t("swReading")}</p>}
      </div>
    </div>
  );
}
