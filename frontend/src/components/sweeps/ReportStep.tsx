/* Step 6 - the report of the whole process, and the plot alone to play with. */
import { pickPath, useApp } from "../../store";
import { useT } from "../../i18n";
import { sweepApi } from "../../sweeps/api";
import { wireQuestion, type Study } from "../../sweeps/state";
import { colLabel, setColumns, shownAxes } from "../../sweeps/view";
import { ReportForm } from "./ReportDialog";
import { say } from "../../sweeps/notify";
import { StepFoot } from "./StepNav";

export async function exportPlot(t: ReturnType<typeof useT>, study: Study, lang: string): Promise<string> {
  const p = await pickPath({ mode: "save", title: t("swExportPlot"), exts: [".html"], defaultName: study.name.replace(/\.[^.]+$/, "") + "_plot.html" });
  if (!p) return "";
  const cols = setColumns(study);
  const labels: Record<string, string> = Object.fromEntries([...cols.keys()].map((n) => [n, colLabel(t, study, n)]));
  Object.assign(labels, { "#shown": t("swShown", { n: "{n}", of: "{of}" }), "#clear": t("swRepClear"), "#hint": t("swRepHtmlHint"), "#colour": t("swColourByThis") });
  const r = await sweepApi.report(study.tableId, wireQuestion(study), { format: "plot", path: p, title: study.name, lang, labels, axes: shownAxes(study) });
  return t("swSaved", { path: r.path });
}

export function ReportSide({ study }: { study: Study }) {
  const t = useT();
  return (
    <div className="sw-side-step">
      <p className="sw-step-intro">{t("swReportIntro")}</p>
      <StepFoot study={study} />
    </div>
  );
}

export function ReportCenter({ study }: { study: Study }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  if (!study.answer) return <p className="hint">{study.evalError || t("swReading")}</p>;
  return (
    <div className="sw-report-page">
      <h2>{t("swReport")}</h2>
      <ReportForm study={study} />
      <div className="sw-hide-box">
        <b>{t("swExportPlot")}</b>
        <span className="hint">{t("swExportPlotHint")}</span>
        <div className="sw-row"><button className="btn outline" onClick={() => say(exportPlot(t, study, lang))}>{t("swExportPlot")}</button></div>
      </div>
    </div>
  );
}
