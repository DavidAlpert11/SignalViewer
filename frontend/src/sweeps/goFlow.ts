/* The flow's steps (flow.ts) acted on: where the area stands now, and a click on a step - apart from flow.ts so
   that stays pure (its unit test needs no store). */
import { flowGo, type FlowAt, type FlowStep } from "./flow";
import { useSweeps, type Part } from "./state";

/** Where the area stands now (the store read once - for clicks, not for rendering). */
export function flowAt(): FlowAt {
  const st = useSweeps.getState(), s = st.studies[st.active];
  return { part: st.part, table: s ? { step: s.view.step, center: s.view.center } : null, common: st.common.open, systems: st.common.study?.tables.length ?? 0 };
}

/** The steps the user asked for, counted: work that opens a table in the background (a round's first results) and
 *  then puts the screen back can see the user moved meanwhile, and keep where that click took it (a click is never undone). */
const asked = { n: 0, to: null as FlowStep | null, part: null as Part | null };
export const flowAsked = (): { n: number; to: FlowStep | null; part: Part | null } => ({ ...asked });

/** Go to a step (a no-op when it has nothing to show yet). */
export function goFlow(to: FlowStep): void {
  asked.n += 1;
  asked.to = to;
  const go = flowGo(flowAt(), to);
  asked.part = go ? go.part : null;
  if (!go) return;
  if (go.view && Object.keys(go.view).length) useSweeps.getState().setView(go.view);
  useSweeps.setState({ part: go.part, narrowOpen: false });
}
