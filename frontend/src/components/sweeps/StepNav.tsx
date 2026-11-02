/* The way through a study (2026-11-01, the owner's redesign): four steps, one after the other -
   the data (load, merge, see it as a table and as lines), the columns (what each one is), the goal
   (limits on columns, what to optimize), the results. Each says where it stands; any can be opened at
   any time. Running sets, the report and the other tools are in the results' Tools menu. */
import { useT, type TFn, type TKey } from "../../i18n";
import { normStep, STEPS, type Step } from "../../sweeps/model";
import { useSweeps, type Study } from "../../sweeps/state";
import { useLeftHidden, useNarrow } from "../../sweeps/narrow";

const TITLE: Record<Step, TKey> = { raw: "swStepData", clean: "swStepColumns", roles: "swStepColumns", goals: "swStepGoal", results: "swStepResults", report: "swStepResults", run: "swStepResults" };

/** One line under each step's name: what it holds now. */
function status(t: TFn, s: Study, step: Step): string {
  const sm = s.summary, a = s.answer, q = s.question;
  switch (step) {
    case "raw": return t("swStRaw", { rows: s.rows.toLocaleString(), cols: s.columns.length });
    case "roles": return t("swStRoles", { p: sm.params.length, h: sm.holds.length, o: sm.outputs.length });
    case "goals": return t("swStGoal", { c: q.conditions.length, o: (q.goals[q.active]?.optimize ?? []).length });
    default: return a ? t("swStResults", { n: a.counts.holding, of: a.counts.sets }) : "…";
  }
}

// Back / Next go through the steps in order
export const nextStep = (s: Step): Step | null => STEPS[STEPS.indexOf(normStep(s)) + 1] ?? null;
export const prevStep = (s: Step): Step | null => STEPS[STEPS.indexOf(normStep(s)) - 1] ?? null;

export default function StepNav({ study }: { study: Study }) {
  const t = useT();
  const cur = normStep(study.view.step);
  const narrow = useNarrow();
  const hidden = useLeftHidden();
  const toggle = () => (narrow ? useSweeps.setState({ narrowOpen: hidden }) : useSweeps.getState().setLeftHidden(!hidden));
  return (
    <nav className="sw-steps" aria-label={t("swSteps")}>
      <button className="iconbtn sw-panel-toggle" aria-pressed={!hidden} onClick={toggle}
        title={t(hidden ? "swShowPanel" : "swHidePanel")} aria-label={t(hidden ? "swShowPanel" : "swHidePanel")}>{hidden ? "›" : "‹"}</button>
      {STEPS.map((s, i) => (
        <button key={s} data-step={s} className={`sw-step-btn${s === cur ? " on" : ""}${STEPS.indexOf(cur) > i ? " done" : ""}`} aria-current={s === cur ? "step" : undefined}
          onClick={() => { useSweeps.getState().setView({ step: s }); useSweeps.setState({ narrowOpen: false }); }}>
          <span className="sw-step-n">{i + 1}</span>
          <span className="sw-step-txt"><b>{t(TITLE[s])}</b><span>{status(t, study, s)}</span></span>
        </button>
      ))}
    </nav>
  );
}

/** Back / Next at the foot of a step's side panel. */
export function StepFoot({ study, next }: { study: Study; next?: string }) {
  const t = useT();
  const st = useSweeps.getState();
  const p = prevStep(study.view.step), n = nextStep(study.view.step);
  return (
    <div className="sw-step-foot">
      {p && <button className="btn" onClick={() => st.setView({ step: p })}>← {t(TITLE[p])}</button>}
      {n && <button className="btn primary" onClick={() => st.setView({ step: n })}>{next ?? t(TITLE[n])} →</button>}
    </div>
  );
}

export const stepTitle = (t: TFn, s: Step) => t(TITLE[s]);
