/* Step 6 - the report of the whole process, and the plot alone to play with. */
import { pickPath, useApp } from "../../store";
import { useT } from "../../i18n";
import { sweepApi } from "../../sweeps/api";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { colLabel, setColumns, shownAxes } from "../../sweeps/view";
import { ReportForm } from "./ReportDialog";
import { say } from "../../sweeps/notify";
import { journalLine, reportJournal } from "../../sweeps/journal";
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
      <Journal study={study} />
      {study.iterations.length > 1 && <div className="sw-hide-box sw-journal sw-iterations">
        <h3>{t("swRepIterations")}</h3>
        <ul>{study.iterations.map((it) => <li key={it.n}>{t("swRepIteration", { n: it.n, label: it.label, holding: it.holding, sets: it.sets, best: it.best === null ? "–" : fmtValue(it.best) })}</li>)}</ul>
      </div>}
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

/** The journal as the report will tell it (S20): the final story or everything; a line hidden by
 *  hand (× / ↺), and the line where the analysis starts (⤒) - before it nothing goes in. */
function Journal({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const all = !!study.view.journalAll, start = study.view.journalStart;
  const shown = reportJournal(study.log, !all, start);
  const lines = all ? study.log.filter((e) => e.kind !== "open") : shown;
  const inReport = new Set(shown);
  const startIdx = start ? study.log.findIndex((e) => e.at === start) : -1;
  return (
    <div className="sw-hide-box sw-journal">
      <h3>{t("swRepJournal")} <span className="hint">({t("swJournalInReport", { n: shown.length })})</span></h3>
      <div className="sw-seg" role="radiogroup" aria-label={t("swRepJournal")}>
        <button role="radio" aria-checked={!all} className={!all ? "on" : ""} onClick={() => st.setView({ journalAll: false })}>{t("swJournalFinal")}</button>
        <button role="radio" aria-checked={all} className={all ? "on" : ""} onClick={() => st.setView({ journalAll: true })}>{t("swJournalAll")}</button>
      </div>
      {start && <p className="hint">{t("swJournalStartsAt", { at: journalLine(t, study.log[startIdx] ?? study.log[0]).split(" · ")[0] })}{" "}
        <button className="linklike" onClick={() => st.setView({ journalStart: undefined })}>{t("swJournalFromFirst")}</button></p>}
      {lines.length === 0 ? <p className="hint">{t("swJournalEmpty")}</p> : (
        <ol className="sw-journal-lines">
          {[...lines].reverse().slice(0, 120).map((e) => {
            const before = startIdx >= 0 && study.log.indexOf(e) < startIdx;
            const out = e.hidden || before || (all && !inReport.has(e));
            return (
              <li key={e.at + e.kind} className={`${e.hidden ? "hidden" : ""}${out ? " out" : ""}`}>
                <span>{journalLine(t, e)}</span>
                <span className="sw-journal-acts">
                  <button className="iconbtn" title={t("swJournalStartHere")} aria-label={t("swJournalStartHere")} onClick={() => st.setView({ journalStart: e.at })}>⤒</button>
                  <button className="iconbtn" title={t(e.hidden ? "swJournalShow" : "swJournalHide")} aria-label={t(e.hidden ? "swJournalShow" : "swJournalHide")}
                    onClick={() => st.hideJournalLine(e.at, !e.hidden)}>{e.hidden ? "↺" : "×"}</button>
                </span>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
