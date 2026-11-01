/* Step 6 - the report of the whole process, and the plot alone to play with. */
import { pickPath, useApp } from "../../store";
import { useT } from "../../i18n";
import { sweepApi } from "../../sweeps/api";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { colLabel, setColumns, shownAxes } from "../../sweeps/view";
import { ReportForm } from "./ReportDialog";
import { say } from "../../sweeps/notify";
import { journalLine } from "../../sweeps/journal";
import { fmtValue } from "../../sweeps/scales";
import { StepFoot } from "./StepNav";

/** The parallel plot alone, interactive (HTML): of every set, or `only` those (the table's, S14). */
export async function exportPlot(t: ReturnType<typeof useT>, study: Study, lang: string, only?: number[]): Promise<string> {
  const p = await pickPath({ mode: "save", title: t("swExportPlot"), exts: [".html"], defaultName: study.name.replace(/\.[^.]+$/, "") + (only ? "_sets_plot.html" : "_plot.html") });
  if (!p) return "";
  const cols = setColumns(study);
  const labels: Record<string, string> = Object.fromEntries([...cols.keys()].map((n) => [n, colLabel(t, study, n)]));
  Object.assign(labels, { "#shown": t("swShown", { n: "{n}", of: "{of}" }), "#clear": t("swRepClear"), "#hint": t("swRepHtmlHint"), "#colour": t("swColourByThis") });
  const r = await sweepApi.report(study.tableId, wireQuestion(study), { format: "plot", path: p, title: study.name, lang, labels, axes: shownAxes(study), ...(only ? { only } : {}) });
  useSweeps.getState().journal("export", { path: r.path });
  return t("swSaved", { path: r.path });
}

export function ReportSide({ study }: { study: Study }) {
  const t = useT();
  return (
    <div className="sw-side-step">
      <p className="sw-step-intro">{t("swReportIntro")}</p>
      {/* the journal so far (S08): what the report's process will tell, newest first */}
      <div className="sw-hide-box sw-journal">
        <h3>{t("swRepJournal")} <span className="hint">({study.log.length})</span></h3>
        <ol reversed>{[...study.log].reverse().slice(0, 60).map((e, i) => <li key={i}>{journalLine(t, e)}</li>)}</ol>
        {study.iterations.length > 1 && <>
          <h3>{t("swRepIterations")}</h3>
          <ul>{study.iterations.map((it) => <li key={it.n}>{t("swRepIteration", { n: it.n, label: it.label, holding: it.holding, sets: it.sets, best: it.best === null ? "–" : fmtValue(it.best) })}</li>)}</ul>
        </>}
      </div>
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
