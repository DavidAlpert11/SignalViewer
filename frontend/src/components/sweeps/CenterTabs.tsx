/* The results' views (2026-11-01, the owner's redesign - a clean set, nothing else): the parameter sets as lines,
   every run as lines, charts made from the columns, the report - and, in a study of several systems, the systems
   together (PLAN 2026-11-16 §7a: a view of Results; it was the navigator's *Together*). What to run next is the
   fifth step (FlowNav). */
import { useT } from "../../i18n";
import { normCenter } from "../../sweeps/model";
import { useSweeps, type Study } from "../../sweeps/state";

/** The study file's systems together - a tab of Results when it has two or more (not the demo: its page is one). */
function useTogether(): boolean {
  return useSweeps((s) => s.common.open && !s.common.demo && (s.common.study?.tables.length ?? 0) >= 2);
}

export default function CenterTabs({ study }: { study: Study; studies?: number }) {
  const t = useT();
  const v = study.view;
  const st = useSweeps.getState();
  const c = normCenter(v.center);
  const together = useTogether();
  const tab = (key: string, on: boolean, label: string, go: () => void) => (
    <button key={key} role="tab" data-tab={key} aria-selected={on} className={on ? "on" : ""} onClick={go}>{label}</button>
  );
  // how many lines each one draws, in its name: the two tabs are told apart before they are opened
  const k = study.answer?.counts;
  const n = (x: number | undefined) => (x === undefined ? "" : ` · ${x.toLocaleString()}`);
  return (
    <div className="sw-center-tabs" role="tablist">
      {tab("sets", c === "lines" && v.mode === "sets", t("swTabSets") + n(k?.sets), () => st.setView({ center: "lines", mode: "sets" }))}
      {tab("runs", c === "lines" && v.mode === "runs", t("swTabRuns") + n(k?.rows), () => st.setView({ center: "lines", mode: "runs" }))}
      {tab("charts", c === "charts", t("swCenterCharts"), () => st.setView({ center: "charts" }))}
      {tab("report", c === "report", t("swToolReport"), () => st.setView({ center: "report" }))}
      {together && tab("together", false, t("flTogether"), () => useSweeps.setState({ part: "together" }))}
    </div>
  );
}

/** Above the systems together: back to the open table's views. */
export function TogetherTabs() {
  const t = useT();
  const study = useSweeps((s) => s.studies[s.active]);
  if (!study) return null;
  const back = () => useSweeps.setState({ part: "table" });
  return (
    <div className="sw-center-tabs sw-together-tabs" role="tablist">
      <button role="tab" data-tab="sets" aria-selected={false} onClick={back}>{t("flThisTable", { n: study.name })}</button>
      <button role="tab" data-tab="together" aria-selected className="on">{t("flTogether")}</button>
    </div>
  );
}
