/* The results' views (2026-11-01, the owner's redesign - a clean set, nothing else): the parameter
   sets as lines, every run as lines, charts made from the columns, what to run next, the report. */
import { useT } from "../../i18n";
import { normCenter } from "../../sweeps/model";
import { useSweeps, type Study } from "../../sweeps/state";

export default function CenterTabs({ study }: { study: Study; studies?: number }) {
  const t = useT();
  const v = study.view;
  const st = useSweeps.getState();
  const c = normCenter(v.center);
  const tab = (key: string, on: boolean, label: string, go: () => void) => (
    <button key={key} role="tab" data-tab={key} aria-selected={on} className={on ? "on" : ""} onClick={go}>{label}</button>
  );
  return (
    <div className="sw-center-tabs" role="tablist">
      {tab("sets", c === "lines" && v.mode === "sets", t("swTabSets"), () => st.setView({ center: "lines", mode: "sets" }))}
      {tab("runs", c === "lines" && v.mode === "runs", t("swTabRuns"), () => st.setView({ center: "lines", mode: "runs" }))}
      {tab("charts", c === "charts", t("swCenterCharts"), () => st.setView({ center: "charts" }))}
      {tab("next", c === "next", v.rerun.length ? `${t("swCenterNext")} (${v.rerun.length})` : t("swCenterNext"), () => st.setView({ center: "next" }))}
      {tab("report", c === "report", t("swToolReport"), () => st.setView({ center: "report" }))}
    </div>
  );
}
