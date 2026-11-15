/* Back / Next at the foot of a table's step panels (the steps themselves: FlowNav, PLAN 2026-11-16 §7a - Data,
   Columns, Goal, Results, Next runs). */
import { useT, type TFn, type TKey } from "../../i18n";
import { type Step } from "../../sweeps/model";
import { FLOW, flowStep } from "../../sweeps/flow";
import type { Study } from "../../sweeps/state";
import { flowTitle, goFlow } from "./FlowNav";

const TITLE: Record<Step, TKey> = { raw: "swStepData", clean: "swStepColumns", roles: "swStepColumns", goals: "swStepGoal", results: "swStepResults", report: "swStepResults", run: "swStepResults" };

/** Back / Next at the foot of a step's side panel. */
export function StepFoot({ study, next }: { study: Study; next?: string }) {
  const t = useT();
  const i = FLOW.indexOf(flowStep({ part: "table", table: { step: study.view.step, center: study.view.center }, common: false, systems: 0 }));
  const p = FLOW[i - 1], n = FLOW[i + 1];
  return (
    <div className="sw-step-foot">
      {p && <button className="btn" onClick={() => goFlow(p)}>← {flowTitle(t, p)}</button>}
      {n && <button className="btn primary" onClick={() => goFlow(n)}>{next ?? flowTitle(t, n)} →</button>}
    </div>
  );
}

export const stepTitle = (t: TFn, s: Step) => t(TITLE[s]);
