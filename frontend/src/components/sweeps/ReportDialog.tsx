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
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { activeColumns, activeParams, colLabel, showKey, mapAxes, mapList, mapSpec, scopeKey, scopeMask, setColumns, shownAxes, tableColumns, tableRows } from "../../sweeps/view";
import { useEscape } from "../Overlays";
import { goalName } from "./GoalsStep";
import { KINDS } from "../../sweeps/next";
import { journalLine, reportJournal } from "../../sweeps/journal";
import { notify, notifyError } from "../../sweeps/notify";
import type { MapSpec } from "../../sweeps/model";
import { deskOf } from "./Desk";

type Format = "html" | "docx" | "pdf" | "csv";
const EXT: Record<Format, string> = { html: ".html", docx: ".docx", pdf: ".pdf", csv: ".csv" };

/** The question, as sentences. */
function questionLines(t: TFn, s: Study): string[] {
  const q = s.question;
  const out = [`${t("swRoleParam")}: ${activeParams(s).join(", ")}`];
  const holds = new Set(activeColumns(s, "hold"));
  for (const h of s.columns.filter((c) => holds.has(c.name)))
    out.push(`${t("swRoleHold")} - ${h.name}: ${(q.holdValues[h.name]?.length ? q.holdValues[h.name] : h.values ?? []).join(", ")}`);
  if (q.removed.length) out.push(t("swRepRemoved", { list: q.removed.join(", ") }));
  q.goals.forEach((g, i) => {
    const where = (c: (typeof g.conditions)[number]) => (c.mode === "all" ? t("swInAll") : c.mode === "atLeast" ? `${t("swAtLeast")} ${c.k}`
      : `${t("swOnlyIn")} ${Object.entries(c.where ?? {}).map(([k, v]) => `${k} ${v.join(", ")}`).join("; ")}`);
    const conds = g.conditions.map((c) => `${c.column} ${c.op} ${c.value} (${where(c)})`).join(g.combine === "or" ? ` ${t("swOr")} ` : ` ${t("swAnd")} `);
    const opt = g.optimize.map((o) => `${o.direction === "max" ? t("swMaximize") : t("swMinimize")} ${o.column}`).join(", ");
    out.push(`${goalName(t, g, i)}${i === q.active ? ` (${t("swRepShownGoal")})` : ""}: ${[conds, opt].filter(Boolean).join(" - ") || t("swGoalEmpty")}`);
  });
  const robust = Object.entries(q.robust ?? {});
  if (robust.length) out.push(t("swRepRobust", { list: robust.map(([c, tol]) => `${c} ± ${tol.value}${tol.mode === "pct" ? "%" : tol.mode === "steps" ? ` ${t("swTolSteps")}` : ""}`).join(", ") }));
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
  const k = showKey(v);
  if (k !== "all") out.push(t("swRepShown", { what: k === "holds" ? t("swShowHoldsWord") : k === "fail" ? t("swShowFailWord") : (v.groups ?? []).find((g) => g.id === k)?.name ?? k }));
  if (v.tableSort && setColumns(s).has(v.tableSort.column))
    out.push(t(v.tableSort.desc ? "swRepSortedDesc" : "swRepSorted", { c: colLabel(t, s, v.tableSort.column) }));
  if (v.rerun.length) out.push(t("swRepRerun", { n: v.rerun.length }));
  const nx = v.next?.result;
  if (nx) {
    const by = Object.entries(nx.suggestions.reduce<Record<string, number>>((m, x) => ({ ...m, [x.kind]: (m[x.kind] ?? 0) + 1 }), {}))
      .map(([k, n]) => `${t(KINDS.find((x) => x.k === k)?.title ?? "swNextGaps")} ${n}`).join(", ");
    out.push(t("swRepNext", { n: nx.suggestions.length, by }) + (nx.focus ? ` - ${t("swExploredOnly", { list: nx.focus.join(", ") })}` : ""));
  }
  if (v.next?.exported) out.push(t("swRepNextExported", { path: v.next.exported }));
  if (!out.length) out.push(t("swRepNothing"));
  return out;
}

/** The maps and point plots of the report: those on screen - the Charts' panes (a points or bubble
 *  pane is a point plot), then next runs' maps; the same pair once. */
function reportFigures(study: Study): { maps: MapSpec[]; scatters: { x: string; y: string }[] } {
  const setCols = new Set(study.answer?.sets.map((c) => c.name) ?? []);
  const desk = deskOf(study), panes = desk.panes.filter((p) => p.inReport !== false);
  const scatters = panes.filter((p) => (p.kind === "scatter" || p.kind === "bubble") && setCols.has(p.x ?? "") && setCols.has(p.y ?? ""))
    .map((p) => ({ x: p.x!, y: p.y! }));
  const seen = new Set<string>(), maps: MapSpec[] = [];
  for (const m of [...panes.filter((p) => p.kind === "map").map((p) => mapSpec(study, p)), ...mapList(study)]) {
    const k = [m.x, m.y].sort().join("|");
    if (m.x && m.y && !seen.has(k)) { seen.add(k); maps.push(m); }
  }
  return { maps, scatters };
}

/** The report's choices and the button that makes it - in the Report step, and in the dialog. */
export function ReportForm({ study, onBefore }: { study: Study; onBefore?: () => void }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const [format, setFormat] = useState<Format>("html");
  const [title, setTitle] = useState(study.name.replace(/\.[^.]+$/, ""));
  const [notes, setNotes] = useState("");
  const [top, setTop] = useState(25);
  const [inc, setInc] = useState({ question: true, process: true, journal: true, plot: true, map: true, points: true, table: true, provenance: true });
  const a = study.answer!;
  const figs = reportFigures(study);
  const make = async () => {
    onBefore?.();                      // the dialog closes: the file dialog takes its place
    const p = await pickPath({ mode: "save", title: t("swReport"), exts: [EXT[format]], defaultName: title + EXT[format] });
    if (!p) return;
    const cols = setColumns(study);
    const labels: Record<string, string> = Object.fromEntries([...cols.keys()].map((n) => [n, colLabel(t, study, n)]));
    Object.assign(labels, { "#answer": t("swRepAnswer"), "#best": t("swBestSets"), "#plot": t("swCenterLines"),
      "#mapTitle": t("swCenterMap"), "#mapAt": t("swMapAt"),
      "#mapShareKey": t("swMapByShare"), "#mapGoalKey": study.question.goal ? t("swMapByGoal", { c: study.question.goal.column }) : "", "#what": "", "#value": "", "#shown": t("swShown", { n: "{n}", of: "{of}" }), "#clear": t("swRepClear"),
      "#hint": t("swRepHtmlHint"), "#colour": t("swColourByThis"), "#provenance": t("swRepProvenance"),
      "#itTitle": t("swRepIterations"), "#itHolding": t("swRepItHolding"), "#itBest": t("swRepItBest"),
      "#pointsTitle": t("swCenterScatter"), "#holdsKey": t("swHolds"), "#others": t("swOthers") });
    const setCols = new Set(a.sets.map((c) => c.name));
    // the sets on screen: after the filters and the keep / exclude steps
    const n = a.sets[0]?.values.length ?? 0, kept = keptMask(cols, study.view.filters, n), scope = scopeMask(study);
    const shown: number[] = [];
    for (let i = 0; i < n; i++) if (kept[i] && (!scope || scope[i])) shown.push(i);
    // the table as on screen (S04): its columns, its sets in its order (only those that hold, sorted)
    const table = ["#rank", ...tableColumns(study), "#holds"];
    const journal = reportJournal(study.log, !study.view.journalAll, study.view.journalStart);
    const sections = [
      ...(inc.question ? [{ title: t("swQuestion"), items: questionLines(t, study) }] : []),
      ...(inc.process ? [{ title: t("swRepProcess"), items: processLines(t, study) }] : []),
      ...(inc.process && study.iterations.length > 1 ? [{ title: t("swRepIterations"), items: study.iterations.map((it) =>
        t("swRepIteration", { n: it.n, label: it.label, holding: it.holding, sets: it.sets, best: it.best === null ? "–" : fmtValue(it.best) })) }] : []),
      // the journal as chosen in the Report step: the final story or everything, hidden lines out (S20)
      ...(inc.journal && journal.length ? [{ title: t("swRepJournal"), items: journal.map((e) => journalLine(t, e)) }] : []),
    ];
    const map = mapAxes(study);
    notify(t("swRepMaking"));
    try {
      const r = await sweepApi.report(study.tableId, wireQuestion(study), {
        format, path: p, title, notes, lang, subtitle: study.sources.join(" + "), sections, labels,
        summary: [[t("swRuns"), a.counts.rows], [t("swSets"), a.counts.sets], [t("swCombos"), a.counts.combos],
          [t("swRepHolding"), `${a.counts.holding} / ${a.counts.sets}`], [t("swMissing"), a.counts.sets - a.counts.complete],
          [t("swRepShownNow"), shown.length]],
        columns: table, rows: tableRows(study), axes: shownAxes(study), shown: shown.length < n ? shown : null, top,
        include: { plot: inc.plot, map: inc.map && figs.maps.length > 0, points: inc.points && figs.scatters.length > 0, table: inc.table, provenance: inc.provenance, iterations: inc.process },
        scatters: figs.scatters, style: study.view.style ?? null, colorBy: study.view.colorBy && setCols.has(study.view.colorBy) ? study.view.colorBy : null,
        iterations: study.iterations.length > 1 ? study.iterations : null,
        mapX: map.x ?? null, mapY: map.y ?? null, maps: figs.maps });
      notify(t("swSaved", { path: r.path }));
      useSweeps.getState().journal("report", { path: r.path });
    } catch (e) { notifyError(e); }
  };
  // a map / point plot box counts what is on screen; none there: nothing to include
  const box = (k: keyof typeof inc, label: string, n?: number) => (
    <label className="acheck"><input type="checkbox" checked={inc[k] && n !== 0} disabled={format === "csv" || n === 0}
      onChange={(e) => setInc({ ...inc, [k]: e.target.checked })} />{n === undefined ? label : `${label} (${n})`}</label>
  );
  const FORMATS: { f: Format; label: string; hint: string }[] = [
    { f: "html", label: t("swRepHtml"), hint: t("swRepHtmlDesc") },
    { f: "docx", label: t("swRepWord"), hint: t("swRepFigures") },
    { f: "pdf", label: "PDF", hint: t("swRepFigures") },
    { f: "csv", label: t("swRepCsv"), hint: t("swRepCsvDesc") },
  ];
  return (
    <div className="sw-report-body">
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
        {box("question", t("swQuestion"))}{box("process", t("swRepProcess"))}{box("journal", t("swRepJournal"))}{box("plot", t("swCenterLines"))}
        {box("map", t("swCenterMap"), figs.maps.length)}{box("points", t("swCenterScatter"), figs.scatters.length)}{box("table", t("swBestSets"))}{box("provenance", t("swRepProvenance"))}
        <label className="acheck">{t("swRepTop")}<input type="number" min={1} max={1000} value={top} onChange={(e) => setTop(Math.max(1, Number(e.target.value) || 25))} style={{ width: 64 }} /></label>
      </div>
      <div className="sw-report-preview">
        <b>{t("swRepProcess")}</b>
        <ul>{processLines(t, study).map((x, i) => <li key={i}>{x}</li>)}</ul>
      </div>
      <div className="sw-row"><button className="btn primary" onClick={make}>{t("swRepMake")}</button></div>
    </div>
  );
}

export default function ReportDialog({ study, onClose }: { study: Study; onClose: () => void }) {
  const t = useT();
  useEscape(onClose);
  return (
    <div className="scrim" onMouseDown={onClose}>
      <div className="dialog sw-report" role="dialog" aria-label={t("swReport")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("swReport")}</h2>
          <button className="iconbtn" onClick={onClose} aria-label={t("close")}><Icon.X /></button></div>
        <div className="dialog-body"><ReportForm study={study} onBefore={onClose} /></div>
      </div>
    </div>
  );
}
