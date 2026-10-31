/* A report of the study - and of how its answer was reached: the question, the process (filters,
   keep / exclude steps, merged tables, runs left out, the re-run list), the best parameter sets and
   the figures. Interactive HTML (the plot works in any browser, offline), Word, PDF, or the answer
   table as CSV. The server makes the numbers and figures (app/sweep_report.py); this dialog sends
   what only the page knows, in the user's language. */
import { useState } from "react";
import { pickPath, useApp } from "../../store";
import { useT, type TFn } from "../../i18n";
import { Icon } from "../../icons";
import { hasFilter, keptMask } from "../../sweeps/filters";
import { fmtValue, labelOf } from "../../sweeps/scales";
import { sweepApi } from "../../sweeps/api";
import { wireQuestion, type Study } from "../../sweeps/state";
import { colLabel, scopeKey, scopeMask, setColumns, shownAxes } from "../../sweeps/view";
import { useEscape } from "../Overlays";

type Format = "html" | "docx" | "pdf" | "csv";
const EXT: Record<Format, string> = { html: ".html", docx: ".docx", pdf: ".pdf", csv: ".csv" };

/** The question, as sentences. */
function questionLines(t: TFn, s: Study): string[] {
  const q = s.question;
  const out = [`${t("swRoleParam")}: ${s.columns.filter((c) => c.role === "param").map((c) => c.name).join(", ")}`];
  for (const h of s.columns.filter((c) => c.role === "hold"))
    out.push(`${t("swRoleHold")} - ${h.name}: ${(q.holdValues[h.name]?.length ? q.holdValues[h.name] : h.values ?? []).join(", ")}`);
  if (q.goal) out.push(`${t("swGoal")}: ${q.goal.direction === "max" ? t("swMaximize") : t("swMinimize")} ${q.goal.column} (${t("swWorst")})`);
  for (const c of q.conditions)
    out.push(`${c.column} ${c.op} ${c.value} - ${c.mode === "all" ? t("swInAll") : c.mode === "atLeast" ? `${t("swAtLeast")} ${c.k}`
      : `${t("swOnlyIn")} ${Object.entries(c.where ?? {}).map(([k, v]) => `${k} ${v.join(", ")}`).join("; ")}`}`);
  for (const o of q.objectives) out.push(`${t("swObjective")}: ${o.direction === "max" ? t("swMaximize") : t("swMinimize")} ${o.column} × ${o.weight}`);
  for (const d of q.derived) out.push(`ƒ ${d.name} = ${d.kind === "row" ? d.expr : `${d.op}(${d.column})`}`);
  out.push(`${t("swOutputsPerSet")} ${q.outputAgg}`);
  return out;
}

/** How the answer on screen was reached: tables merged, runs left out, filters, keep / exclude, re-run list. */
function processLines(t: TFn, s: Study): string[] {
  const v = s.view, out: string[] = [];
  if (s.sources.length > 1) out.push(t("swRepMerged", { list: s.sources.join(" + ") }));
  if (s.question.exclude.length) out.push(t("swLeftOutN", { n: s.question.exclude.length }));
  const cols = setColumns(s);
  if (v.scope.key === scopeKey(s))
    v.scope.steps.forEach((st, i) => out.push(t(st.kind === "keep" ? "swRepKept" : "swRepExcluded", { i: i + 1, n: st.sets.length })));
  for (const [name, f] of Object.entries(v.filters)) {
    if (!hasFilter(f)) continue;
    const c = cols.get(name);
    const what = f.kind === "ranges" ? f.ranges.map(([a, b]) => `${fmtValue(Math.min(a, b))} – ${fmtValue(Math.max(a, b))}`).join(" ∪ ")
      : f.values.map((x) => (c ? labelOf(c, x) : String(x))).join(", ");
    out.push(t("swRepFilter", { c: colLabel(t, s, name), what }));
  }
  if (v.rerun.length) out.push(t("swRepRerun", { n: v.rerun.length }));
  if (!out.length) out.push(t("swRepNothing"));
  return out;
}

export default function ReportDialog({ study, onClose, onNote }: { study: Study; onClose: () => void; onNote: (msg: string) => void }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const [format, setFormat] = useState<Format>("html");
  const [title, setTitle] = useState(study.name.replace(/\.[^.]+$/, ""));
  const [notes, setNotes] = useState("");
  const [top, setTop] = useState(25);
  const [inc, setInc] = useState({ question: true, process: true, plot: true, effects: true, map: true, table: true });
  useEscape(onClose);
  const a = study.answer!;
  const make = async () => {
    onClose();                         // the file dialog takes its place; the result shows in the area's bar
    const p = await pickPath({ mode: "save", title: t("swReport"), exts: [EXT[format]], defaultName: title + EXT[format] });
    if (!p) return;
    const cols = setColumns(study);
    const labels: Record<string, string> = Object.fromEntries([...cols.keys()].map((n) => [n, colLabel(t, study, n)]));
    Object.assign(labels, { "#answer": t("swRepAnswer"), "#best": t("swBestSets"), "#plot": t("swCenterLines"), "#effectsTitle": t("swCenterEffects"),
      "#mapTitle": t("swCenterMap"), "#what": "", "#value": "", "#shown": t("swShown", { n: "{n}", of: "{of}" }), "#clear": t("swRepClear"),
      "#hint": t("swRepHtmlHint"), "#colour": t("swColourByThis") });
    // the sets on screen: after the filters and the keep / exclude steps
    const n = a.sets[0]?.values.length ?? 0, kept = keptMask(cols, study.view.filters, n), scope = scopeMask(study);
    const shown: number[] = [];
    for (let i = 0; i < n; i++) if (kept[i] && (!scope || scope[i])) shown.push(i);
    const table = ["#rank", ...a.sets.filter((c) => c.group === "param").map((c) => c.name), ...(cols.has("#goal") ? ["#goal"] : []),
      ...a.sets.filter((c) => c.group === "condition" && c.part === "margin").map((c) => c.name),
      ...["#score", "#neighbours", "#tolerance"].filter((x) => cols.has(x)), "#holds"];
    const sections = [
      ...(inc.question ? [{ title: t("swQuestion"), items: questionLines(t, study) }] : []),
      ...(inc.process ? [{ title: t("swRepProcess"), items: processLines(t, study) }] : []),
    ];
    const params = study.columns.filter((c) => c.role === "param").map((c) => c.name);
    onNote(t("swRepMaking"));
    try {
      const r = await sweepApi.report(study.tableId, wireQuestion(study), {
        format, path: p, title, notes, lang, subtitle: study.sources.join(" + "), sections, labels,
        summary: [[t("swRuns"), a.counts.rows], [t("swSets"), a.counts.sets], [t("swCombos"), a.counts.combos],
          [t("swRepHolding"), `${a.counts.holding} / ${a.counts.sets}`], [t("swMissing"), a.counts.sets - a.counts.complete],
          [t("swRepShownNow"), shown.length]],
        columns: table, axes: shownAxes(study), shown: shown.length < n ? shown : null, top,
        include: { plot: inc.plot, effects: inc.effects, map: inc.map, table: inc.table },
        mapX: study.view.mapX ?? params[0] ?? null, mapY: study.view.mapY ?? params.find((x) => x !== (study.view.mapX ?? params[0])) ?? null });
      onNote(t("swSaved", { path: r.path }));
    } catch (e) { onNote((e as Error).message); }
  };
  const box = (k: keyof typeof inc, label: string) => (
    <label className="acheck"><input type="checkbox" checked={inc[k]} disabled={format === "csv"} onChange={(e) => setInc({ ...inc, [k]: e.target.checked })} />{label}</label>
  );
  const FORMATS: { f: Format; label: string; hint: string }[] = [
    { f: "html", label: t("swRepHtml"), hint: t("swRepHtmlDesc") },
    { f: "docx", label: t("swRepWord"), hint: t("swRepFigures") },
    { f: "pdf", label: "PDF", hint: t("swRepFigures") },
    { f: "csv", label: t("swRepCsv"), hint: t("swRepCsvDesc") },
  ];
  return (
    <div className="scrim" onMouseDown={onClose}>
      <div className="dialog sw-report" role="dialog" aria-label={t("swReport")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("swReport")}</h2>
          <button className="iconbtn" onClick={onClose} aria-label={t("close")}><Icon.X /></button></div>
        <div className="dialog-body sw-report-body">
          <div className="sw-report-formats" role="radiogroup" aria-label={t("swRepFormat")}>
            {FORMATS.map(({ f, label, hint }) => (
              <label key={f} className={`sw-report-format${format === f ? " on" : ""}`}>
                <input type="radio" name="fmt" checked={format === f} onChange={() => setFormat(f)} />
                <span><b>{label}</b><br /><span className="hint">{hint}</span></span>
              </label>
            ))}
          </div>
          <label className="sw-field">{t("swRepTitle")}<input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
          <label className="sw-field">{t("swRepNotes")}<textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder={t("swRepNotesHint")} /></label>
          <div className="sw-report-inc">
            {box("question", t("swQuestion"))}{box("process", t("swRepProcess"))}{box("plot", t("swCenterLines"))}
            {box("effects", t("swCenterEffects"))}{box("map", t("swCenterMap"))}{box("table", t("swBestSets"))}
            <label className="acheck">{t("swRepTop")}<input type="number" min={1} max={1000} value={top} onChange={(e) => setTop(Math.max(1, Number(e.target.value) || 25))} style={{ width: 64 }} /></label>
          </div>
          <div className="sw-report-preview">
            <b>{t("swRepProcess")}</b>
            <ul>{processLines(t, study).map((x, i) => <li key={i}>{x}</li>)}</ul>
          </div>
        </div>
        <div className="dialog-foot">
          <button className="btn" onClick={onClose}>{t("cancel")}</button>
          <button className="btn primary" onClick={make}>{t("swRepMake")}</button>
        </div>
      </div>
    </div>
  );
}
