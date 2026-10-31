/* The way through a study, one step after the other - the results as they came, clean the
   columns, say which are the scenarios and which the parameters, set the goal(s), look at the
   results, report. Each step says where it stands; any step can be opened at any time. */
import { useT, type TFn, type TKey } from "../../i18n";
import { STEPS, type Step } from "../../sweeps/model";
import { useSweeps, type Study } from "../../sweeps/state";

const TITLE: Record<Step, TKey> = { raw: "swStepRaw", clean: "swStepClean", roles: "swStepRoles", goals: "swStepGoals", results: "swStepResults", report: "swStepReport" };

/** One line under each step's name: what it holds now. */
function status(t: TFn, s: Study, step: Step): string {
  const sm = s.summary, a = s.answer, q = s.question;
  switch (step) {
    case "raw": return t("swStRaw", { rows: s.rows.toLocaleString(), cols: s.columns.length });
    case "clean": return t("swStClean", { n: q.removed.length });
    case "roles": return t("swStRoles", { p: sm.params.length, h: sm.holds.length, o: sm.outputs.length });
    case "goals": return t("swStGoals", { n: q.goals.length, c: q.conditions.length });
    case "results": return a ? t("swStResults", { n: a.counts.holding, of: a.counts.sets }) : "…";
    default: return t("swStReport");
  }
}

export const nextStep = (s: Step): Step | null => STEPS[STEPS.indexOf(s) + 1] ?? null;
export const prevStep = (s: Step): Step | null => STEPS[STEPS.indexOf(s) - 1] ?? null;

export default function StepNav({ study }: { study: Study }) {
  const t = useT();
  const cur = study.view.step;
  return (
    <nav className="sw-steps" aria-label={t("swSteps")}>
      {STEPS.map((s, i) => (
        <button key={s} className={`sw-step-btn${s === cur ? " on" : ""}${STEPS.indexOf(cur) > i ? " done" : ""}`} aria-current={s === cur ? "step" : undefined}
          onClick={() => useSweeps.getState().setView({ step: s })}>
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
