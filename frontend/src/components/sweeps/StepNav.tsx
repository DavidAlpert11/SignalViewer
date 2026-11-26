/* Back / Next at the foot of a table's step panels (the steps themselves: FlowNav, PLAN 2026-11-16 §7a - Data,
   Columns, Goal, Results, Next runs). */
import { useT } from "../../i18n";
import { flowStep, flowSteps } from "../../sweeps/flow";
import { isRecordings, useSweeps, type Study } from "../../sweeps/state";
import { flowTitle, goFlow } from "./FlowNav";

/** Back / Next at the foot of a step's side panel. */
export function StepFoot({ study, next }: { study: Study; next?: string }) {
  const t = useT();
  const FLOW = flowSteps(useSweeps(isRecordings));          // FR5: a table of recordings ends at Results
  const i = FLOW.indexOf(flowStep({ part: "table", table: { step: study.view.step, center: study.view.center }, common: false, systems: 0 }));
  const p = FLOW[i - 1], n = FLOW[i + 1];
  return (
    <div className="sw-step-foot">
      {p && <button className="btn" onClick={() => goFlow(p)}>← {flowTitle(t, p)}</button>}
      {n && <button className="btn primary" onClick={() => goFlow(n)} title={n === "next" && !study.recordings ? t("swResultsNextHint") : undefined}>{next ?? flowTitle(t, n)} →</button>}
    </div>
  );
}
