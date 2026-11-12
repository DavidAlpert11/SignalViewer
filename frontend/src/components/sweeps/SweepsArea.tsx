/* The Sweeps area (areas.ts): a results table - one row per run, parameters and scenario columns
   first, outputs last - and the question asked of it.

   This file is layout only. The pieces, each its own file:
     StepNav                        the four steps (2026-11-01 redesign): data, columns, goal,
                                    results - each with its side panel and its middle (RawStep,
                                    RolesStep, GoalsStep, ResultsSide + ResultsCenter below)
     CenterTabs                     the results' views:
       PlotToolbar + ParallelPlot + SetsTable   the parameter sets / all runs as lines (+ AxisMenu)
       Desk         charts made from the columns   NextRunsView what to run next
       ReportStep   the report
     SetDetail                      one set on the right: why it fails, its runs, its recordings
   State: sweeps/state.ts. Styles: ./sweeps.css (its own file, to restyle the area alone). */
import { useEffect, useMemo, useRef, useState } from "react";
import PanelResizer from "../PanelResizer";
import { usePanelWidth } from "../panelWidth";
import { pickPath, useApp } from "../../store";
import { translate, useT, type TFn } from "../../i18n";
import { registerArea } from "../../areaCommands";
import Toasts from "../Toasts";
import { normCenter, normStep, STEPS } from "../../sweeps/model";
import { stepTitle } from "./StepNav";
import { useLeftHidden } from "../../sweeps/narrow";
import { Icon } from "../../icons";
import { sweepApi } from "../../sweeps/api";
import { recipeFiles, savedOf, useSweeps, useStudy, wireQuestion, type Study } from "../../sweeps/state";
import { emptyView, newGoal, materialize } from "../../sweeps/model";
import { notify, notifyError, say } from "../../sweeps/notify";
import { activeParams, colLabel, scaleOf, scopedColumns, scopeKey, showMask, shownAxes } from "../../sweeps/view";
import { keptMask } from "../../sweeps/filters";
import ReportDialog from "./ReportDialog";
import TemplatesDialog from "./TemplatesDialog";
import StepNav from "./StepNav";
import { RawCenter, RawSide, ZoomButtons } from "./RawStep";
import { NO_ZOOM } from "../../sweeps/zoom";
import { RolesCenter, RolesSide } from "./RolesStep";
import { templateSummary } from "../../sweeps/templates";
import { GoalsCenter, GoalsSide } from "./GoalsStep";
import ResultsSide from "./ResultsSide";
import { ReportCenter, ReportSide, exportPlot } from "./ReportStep";
import { confirmAsk, openMenu, prompt } from "../Overlays";
import type { SavedStudy } from "../../sweeps/state";
import AxisMenu from "./AxisMenu";
import CenterTabs from "./CenterTabs";
import SplitBar from "./SplitBar";
import Desk from "./Desk";
import NextRunsView from "./NextRunsView";
import ParallelPlot from "./ParallelPlot";
import PlotToolbar from "./PlotToolbar";
import SetDetail from "./SetDetail";
import SetsTable from "./SetsTable";
import StudyPanel, { openStudyDialog } from "./StudyPanel";
import { newStudy, openStudyFile, useStudyPanel } from "../../sweeps/studyStore";
import { onStudyRequest, takeStudy } from "../../sweeps/studyOpen";
import "./sweeps.css";

/** the middle (plot, tables) never narrower than this when a panel is dragged wider */
const MIN_MIDDLE = 380;
const LEFT_MIN = 220, LEFT_MAX = 320;
const TABLE_EXTS = [".csv", ".tsv", ".txt", ".parquet", ".pq", ".xlsx", ".xls"];
const STUDY_EXT = ".svsweep";

async function openTable(title: string) {
  const p = await pickPath({ mode: "open", title, exts: TABLE_EXTS });
  if (p) await useSweeps.getState().open(p);
}
async function openFolder(title: string) {
  const p = await pickPath({ mode: "folder", title });
  if (p) await useSweeps.getState().open(p);
}
async function openStudy(title: string): Promise<string> {
  const p = await pickPath({ mode: "open", title, exts: [STUDY_EXT] });
  if (!p) return "";
  try {
    const doc = JSON.parse((await sweepApi.loadText(p)).text) as SavedStudy;
    if (doc.kind !== "signalviewer-sweep") return "not a study";
    // a study saved with its tables needs no `path` (its first table may be a merged one)
    await useSweeps.getState().open(doc.path, doc);
    return "";
  } catch (e) { return (e as Error).message; }
}

async function saveStudy(t: TFn) {
  const st = useSweeps.getState(), study = st.studies[st.active], doc = st.saved();
  if (!study || !doc) return;
  if (!doc.path && !doc.tables?.length) { notify(t("swCannotSaveRows"), "error"); return; }
  const p = await pickPath({ mode: "save", title: t("swSaveStudy"), exts: [STUDY_EXT], defaultName: study.name.replace(/\.[^.]+$/, "") + STUDY_EXT });
  if (p) say(sweepApi.saveText(p, JSON.stringify(doc, null, 1)).then((r) => t("swSaved", { path: r.path })));
}

/* The area's keys and its commands in Ctrl+K (areaCommands.ts): registered when this code loads. */
const tNow: TFn = (k, v) => translate(useApp.getState().lang, k, v);
registerArea("sweeps", {
  onKey: (e) => {
    const st = useSweeps.getState();
    if (!(e.ctrlKey || e.metaKey) || !st.studies[st.active]) return false;
    const k = e.key.toLowerCase();
    if (k === "z" && !e.shiftKey) { st.undo(); return true; }
    if (k === "y" || (k === "z" && e.shiftKey)) { st.redo(); return true; }
    return false;
  },
  commands: () => {
    const t = tNow, st = useSweeps.getState(), study = st.studies[st.active], g = t("areaSweeps");
    const open = [
      { id: "sw-open-table", label: t("swOpenTable"), group: g, icon: "open" as const, run: () => { openTable(t("swOpenTable")); } },
      { id: "sw-open-folder", label: t("swOpenFolder"), group: g, icon: "open" as const, run: () => { openFolder(t("swOpenFolder")); } },
      { id: "sw-open-study", label: t("swOpenStudy"), group: g, icon: "open" as const, run: () => { openStudy(t("swOpenStudy")).then((m) => m && notify(m, "error")); } },
      { id: "cp-new", label: `${t("cpTitle")}: ${t("cpNew")}`, group: g, icon: "open" as const, run: newStudy },
      { id: "cp-open", label: `${t("cpTitle")}: ${t("cpOpen")}`, group: g, icon: "open" as const, run: () => { void openStudyDialog(tNow); } },
    ];
    if (!study) return open;
    return [
      { id: "sw-undo", label: t("undo"), group: g, icon: "undo" as const, keys: "Ctrl Z", run: st.undo },
      { id: "sw-redo", label: t("redo"), group: g, icon: "redo" as const, keys: "Ctrl Y", run: st.redo },
      ...open,
      { id: "sw-save-study", label: t("swSaveStudy"), group: g, icon: "save" as const, run: () => { saveStudy(t); } },
      { id: "sw-report", label: t("swReportMenu"), group: g, icon: "report" as const, run: () => useSweeps.setState({ reportOpen: true }) },
      { id: "sw-templates", label: t("swTemplates"), group: g, run: () => useSweeps.setState({ templatesOpen: true }) },
      { id: "sw-start-over", label: t("swStartOver"), group: g, run: st.resetStudy },
      ...STEPS.map((s, i) => ({ id: `sw-step-${s}`, label: `${i + 1} ${stepTitle(t, s)}`, group: t("swSteps"), run: () => st.setView({ step: s }) })),
    ];
  },
});

/** The whole area: its bar (the app's second row) and what is under it (the third). */
export default function SweepsScreen() {
  const study = useStudy();
  // the studies open when the app last ran, opened again the first time the area is shown
  useEffect(() => {
    const lang = useApp.getState().lang;
    useSweeps.getState().reopenLast().then((failed) => {
      for (const f of failed) notify(f.why === "damaged" ? translate(lang, "swAutosaveDamaged", { path: f.name })
        : translate(lang, "swReopenFailed", { name: f.name, why: f.why }), "error", 15000);
    });
  }, []);
  // W14 / W18: a study asked for from outside the area (the welcome screen's cards)
  useEffect(() => {
    const take = () => { const r = takeStudy(); if (r) void openStudyFile(r.path, r.demo); };
    take();
    return onStudyRequest(take);
  }, []);
  const common = useStudyPanel((s) => s.open);
  return <><SweepsBar />{common ? <StudyPanel /> : study ? <StudyView study={study} /> : <SweepsWelcome />}</>;
}

function SweepsBar() {
  const t = useT();
  const studies = useSweeps((s) => s.studies);
  const active = useSweeps((s) => s.active);
  const study = studies[active];
  const below = (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    return { clientX: r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent;
  };
  // the ways in: one menu (they were four buttons, two with the same icon)
  const openMenuAt = (e: React.MouseEvent) => openMenu(below(e), [
    { label: t("swOpenTable"), run: () => openTable(t("swOpenTable")) },
    { label: t("swOpenFolder"), run: () => openFolder(t("swOpenFolder")) },
    { label: t("swOpenStudy"), run: () => say(openStudy(t("swOpenStudy")).then((m) => { if (m) throw new Error(m); })) },
    { label: "", sep: true, run: () => {} },
    // W14: one parameter set for several tables - its own study file (.svstudy.json)
    { label: t("cpOpenMenu"), run: () => {}, items: [
      { label: t("cpNew"), run: newStudy },
      { label: t("cpOpen"), run: () => openStudyDialog(t) },
    ] },
  ]);
  // what is kept of the study: the study itself, a template, a report
  const studyMenu = (e: React.MouseEvent) => {
    const st = useSweeps.getState();
    const SEP = { label: "", sep: true, run: () => {} };
    openMenu(below(e), [
      { label: t("swSaveStudy"), run: () => saveStudy(t) },
      { label: t("swStartOver"), run: () => st.resetStudy() },
      SEP,
      { label: t("swSaveTemplate"), run: async () => {
        const name = (await prompt(t("swSaveTemplate"), t("swTemplateName"), study.name.replace(/\.[^.]+$/, "")))?.trim();
        if (!name) return;
        if (st.templates.some((x) => x.name === name) && !(await confirmAsk(t("swTplReplace"), t("swTplReplaceAsk", { n: name })))) return;
        say(st.saveTemplate(name).then(() => t("swTemplateSaved", { n: name })));
      } },
      { label: t("swTemplatesMenu"), run: () => useSweeps.setState({ templatesOpen: true }) },

      SEP,
      { label: t("swReportMenu"), disabled: !study.answer, run: report },
    ]);
  };
  /* Clear (owner, 2026-11-03: as in Recordings) - from the least to everything; each but the last is
     undone with Ctrl+Z, closing the studies with the notice's Undo (they are opened again) */
  const clearMenu = (e: React.MouseEvent) => {
    const st = useSweeps.getState();
    const s = st.studies[st.active];
    openMenu(below(e), [
      ...(s ? [
        { label: t("swClearCharts"), run: () => st.setView({ groups: [], activeGroup: undefined, desk: undefined, rerun: [], rerunSplit: [], filters: {}, pinned: null }) },
        { label: t("swClearGoal"), run: () => {
          st.setQuestion(materialize({ ...s.question, goals: [newGoal("1")], active: 0, robust: undefined, split: undefined }));
          st.setView({ ...emptyView(), step: "goals" });
          useSweeps.getState().evaluate();
        } },
        { label: t("swStartOver"), run: () => st.resetStudy() },
        { label: "", sep: true, run: () => {} },
      ] : []),
      { label: t("swClearAll", { n: studies.length }), danger: true, disabled: !studies.length, run: async () => {
        if (!(await confirmAsk(t("swClearAllTitle"), t("swClearAllAsk"), t("swClearAllOk"), true))) return;
        const now = useSweeps.getState();
        // what can be opened again (read from files): put back by the notice's Undo
        const docs = now.studies.filter((x) => x.path || x.tables.some((tb) => recipeFiles(tb.recipe).length)).map(savedOf);
        for (let i = now.studies.length - 1; i >= 0; i--) useSweeps.getState().close(i);
        useApp.getState().toast({ kind: "info", text: t("swClearedAll", { n: now.studies.length }),
          action: docs.length ? { label: t("undo"), run: async () => { for (const d of docs) await useSweeps.getState().open(d.path, d); } } : undefined });
      } },
    ]);
  };
  useEffect(() => { useSweeps.getState().loadTemplates(); }, []);
  const reportOpen = useSweeps((s) => s.reportOpen);
  const templatesOpen = useSweeps((s) => s.templatesOpen);
  const report = () => useSweeps.setState({ reportOpen: true });
  return (
    <div className="areabar" role="toolbar" aria-label={t("areaSweeps")}>
      <nav className="tabs-wrap">
        <div className="tabs" role="tablist">
          {studies.map((s, i) => (
            <div key={s.tableId} role="tab" tabIndex={0} aria-selected={i === active} className={`tab${i === active ? " active" : ""}`}
              onClick={() => useSweeps.setState({ active: i })} onKeyDown={(e) => { if (e.key === "Enter") useSweeps.setState({ active: i }); }}>
              <span>{s.name}</span>
              <span className="x" role="button" aria-label={t("swCloseStudy")} title={t("swCloseStudy")}
                onClick={(e) => { e.stopPropagation(); useSweeps.getState().close(i); }}><Icon.X width={12} height={12} /></span>
            </div>
          ))}
        </div>
      </nav>
      {study && <>
        <button className="iconbtn" disabled={!study.history.past.length} onClick={() => useSweeps.getState().undo()} title={`${t("undo")} (Ctrl+Z)`} aria-label={t("undo")}><Icon.Undo /></button>
        <button className="iconbtn" disabled={!study.history.future.length} onClick={() => useSweeps.getState().redo()} title={`${t("redo")} (Ctrl+Y)`} aria-label={t("redo")}><Icon.Redo /></button>
      </>}
      <button className="btn outline" onClick={openMenuAt}><Icon.Open /> {t("swOpen")} ▾</button>
      {study && <button className="btn outline" onClick={studyMenu}>{t("swStudy")} ▾</button>}
      {studies.length > 0 && <button className="btn outline sw-clear-btn" onClick={clearMenu} title={t("swClearHint")}><Icon.Eraser /> {t("swClear")} ▾</button>}
      {study?.path && <button className="iconbtn" aria-label={t("swRefresh")} title={t("swRefresh")} onClick={() => useSweeps.getState().reload()}><Icon.Reload /></button>}
      {study?.path && <label className="acheck" title={t("swFollowHint")}><input type="checkbox" checked={study.view.follow} aria-label={t("swFollow")}
        onChange={(e) => useSweeps.getState().setView({ follow: e.target.checked })} /><span className="sw-wide">{t("swFollow")}</span></label>}
      <div className="spacer" />
      {reportOpen && study?.answer && <ReportDialog study={study} onClose={() => useSweeps.setState({ reportOpen: false })} />}
      {templatesOpen && study && <TemplatesDialog study={study} onClose={() => useSweeps.setState({ templatesOpen: false })} />}
    </div>
  );
}

/* a few rows of the example table, to show what a results table looks like */
const SAMPLE: { name: string; role: "hold" | "param" | "output" | "ignore" }[] = [
  { name: "scenario_wind_mps", role: "hold" }, { name: "kp_roll", role: "param" }, { name: "scenario_gusts", role: "hold" },
  { name: "filter_hz", role: "param" }, { name: "roll_error_deg", role: "output" }, { name: "overshoot_pct", role: "output" }, { name: "energy_wh", role: "output" },
];
const SAMPLE_ROWS = [
  ["0", "0.10", "none", "20", "1.81", "4.1", "26.3"],
  ["5", "0.20", "mild", "20", "2.62", "6.9", "30.4"],
  ["10", "0.20", "strong", "40", "4.75", "9.8", "35.2"],
  ["10", "0.30", "strong", "10", "3.10", "21.6", "38.0"],
];

function SweepsWelcome() {
  const t = useT();
  const busy = useSweeps((s) => s.busy);
  const error = useSweeps((s) => s.error);
  const restoring = useSweeps((s) => s.restoring);
  const example = async () => { const { path } = await sweepApi.example(); await useSweeps.getState().open(path); };
  // the example's second sweep - finer where the first looked good - as a second table, both
  // merged into a third one, and the steps after Data on it
  const merged = async () => {
    const { path, refine } = await sweepApi.example();
    await useSweeps.getState().open(path);
    const st = useSweeps.getState();
    await st.addTable(refine);
    const s = useSweeps.getState().studies[useSweeps.getState().active];
    await st.mergeTables(s.tables.map((x) => x.id), { names: s.tables.map((x) => x.name), how: "concat", keys: [], source: "_source", dedupe: false });
    st.useTable(useSweeps.getState().studies[useSweeps.getState().active].tables.length - 1);
    notify(t("swMergedNew", { n: 2 }));
  };
  return (
    <div className="sw-welcome">
      <div className="notices sw-notices"><Toasts /></div>
      <div className="welcome-card sw-welcome-card">
        <h1>{t("swWelcomeTitle")}</h1>
        <p className="tagline">{t("swWelcomeTagline")}</p>
        <div className="sw-sample" aria-label={t("swSampleTitle")}>
          <div className="sw-sample-head"><b>{t("swSampleTitle")}</b><span className="hint">{t("swSampleHint")}</span></div>
          <div className="sw-sample-wrap">
            <table className="sw-table">
              <thead><tr>{SAMPLE.map((c) => <th key={c.name} className={`sw-th-${c.role}`}>{c.name}</th>)}</tr></thead>
              <tbody>{SAMPLE_ROWS.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j} className={SAMPLE[j].role === "ignore" ? "sw-dim" : ""}>{v}</td>)}</tr>)}
                <tr><td colSpan={SAMPLE.length} className="hint">…</td></tr></tbody>
            </table>
          </div>
          <div className="sw-sample-legend">
            <span className="sw-th-param">■ {t("swRoleParam")}</span><span className="hint">{t("swWhatWeChoose")}</span>
            <span className="sw-th-hold">■ {t("swRoleHold")}</span><span className="hint">{t("swWhatWeDont")}</span>
            <span className="sw-th-output">■ {t("swRoleOutput")}</span><span className="hint">{t("swSampleOutputs")}</span>
          </div>
          <p className="hint">{t("swSampleNote")}</p>
        </div>
        <div className="sw-welcome-actions">
          <button className="btn primary" disabled={busy} onClick={() => openTable(t("swOpenTable"))}><Icon.Open /> {t("swOpenTable")}</button>
          <button className="btn outline" disabled={busy} onClick={() => openFolder(t("swOpenFolder"))}><Icon.Folder /> {t("swOpenFolder")}</button>
          <button className="btn outline" disabled={busy} onClick={() => openStudy(t("swOpenStudy")).then((m) => m && notify(m, "error"))}>{t("swOpenStudy")}</button>
          <button className="btn outline" disabled={busy} onClick={example}>{t("swTryExample")}</button>
          <button className="btn outline" disabled={busy} onClick={() => merged().catch(notifyError)}>{t("swTryMerged")}</button>
        </div>
        {busy && <p className="hint">{restoring ? t("swReopening") : t("swReading")}</p>}
        {error && <p className="sw-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}

function StudyView({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const step = normStep(study.view.step);
  // a study saved on an older step (clean, report, run) opens on its place in the four steps
  useEffect(() => {
    const old = study.view.step, center = normCenter(study.view.center);
    if (old === step && center === study.view.center) return;
    useSweeps.getState().setView({ step, center: old === "report" ? "report" : center });
  }, [study.view.step, study.view.center, step]);
  // follow the file: is it newer than what is on screen? (every few seconds, only this study)
  useEffect(() => {
    if (!study.path) return;
    const h = window.setInterval(() => useSweeps.getState().checkChanged(), 3000);
    return () => window.clearInterval(h);
  }, [study.tableId, study.path]);
  const side = step === "raw" ? <RawSide study={study} /> : step === "roles" ? <RolesSide study={study} />
    : step === "goals" ? <GoalsSide study={study} /> : <ResultsSide study={study} />;
  const noParams = !activeParams(study).length;
  // the side panels: widths dragged (and remembered) as in Recordings, the steps' panel can be hidden
  // the steps' panel: about 220 to 320 px (owner, 2026-11-02)
  const [leftW0, setLeftW] = usePanelWidth("swLeft", 280);
  const leftW = Math.max(LEFT_MIN, Math.min(LEFT_MAX, leftW0));
  const [detailW, setDetailW] = usePanelWidth("swDetail", 380);
  const leftHidden = useLeftHidden();
  const detail = step === "results" && study.view.pinned !== null && !!study.answer;
  const box = useRef<HTMLDivElement>(null);
  const room = (other: number) => () => (box.current?.clientWidth ?? window.innerWidth) - other - MIN_MIDDLE;
  const cols = [leftHidden ? "" : `${leftW}px`, "minmax(0, 1fr)", detail ? `${detailW}px` : ""].filter(Boolean).join(" ");
  return (
    <div className="sw-study-wrap">
      <div className="notices sw-notices"><Toasts /></div>
      <StepNav study={study} />
      <div className="sw-study" ref={box} style={{ gridTemplateColumns: cols }}>
        {!leftHidden && <aside className="side sw-left" aria-label={t("swSteps")}><div className="sw-left-body">{side}</div></aside>}
        {!leftHidden && <PanelResizer label={t("resizePanel")} style={{ insetInlineStart: leftW - 3 }} width={leftW} setWidth={setLeftW}
          grow={+1} def={280} max={() => Math.min(LEFT_MAX, room(detail ? detailW : 0)())} />}
        {detail && <PanelResizer label={t("resizePanel")} style={{ insetInlineEnd: detailW - 3 }} width={detailW} setWidth={setDetailW}
          grow={-1} def={380} max={room(leftHidden ? 0 : leftW)} />}
        <main className="sw-center">
          {study.changed && (
            <div className="sw-banner" role="status">{t("swFileChanged")}
              <button className="btn primary" onClick={() => st.reload()}>{t("swRefresh")}</button>
              <button className="btn outline" onClick={() => { st.setView({ follow: true }); st.reload(); }}>{t("swFollowFromNow")}</button></div>
          )}
          {study.offer && (
            <div className="sw-banner" role="status">{t("swTemplateFits", { n: study.offer })}
              <button className="btn primary" onClick={() => { const r = st.applyTemplate(study.offer!); if (r) notify(templateSummary(t, r), "info", 12000); }}>{t("swApply")}</button>
              <button className="iconbtn" aria-label={t("swDismiss")} onClick={() => useSweeps.setState((x) => ({ studies: x.studies.map((y) => (y.tableId === study.tableId ? { ...y, offer: null } : y)) }))}>×</button></div>
          )}
          {noParams && (step === "goals" || step === "results") && (
            <div className="sw-banner" role="status">{t("swChooseParams")}
              <button className="btn primary" onClick={() => st.setView({ step: "roles" })}>{t("swStepColumns")}</button></div>
          )}
          {step === "raw" && <RawCenter study={study} />}
          {step === "roles" && <RolesCenter study={study} />}
          {step === "goals" && <GoalsCenter study={study} />}
          {step === "results" && <ResultsCenter study={study} />}
        </main>
        {detail && <SetDetail study={study} set={study.view.pinned!} />}
      </div>
    </div>
  );
}

/** Step 5 in the middle: the lines (the parallel plot, filtered as in HiPlot) and the sets, and the
 *  other views of the same answer. */
function ResultsCenter({ study }: { study: Study }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const st = useSweeps.getState();
  const [menu, setMenu] = useState<{ name: string; at: DOMRect } | null>(null);
  const v = study.view;
  const { cols, n, index } = useMemo(() => scopedColumns(study), [study]);
  const axes = shownAxes(study);
  const scale = useMemo(() => (name: string) => scaleOf(study, name, cols.get(name)), [study, cols]);
  // the open set drawn thick: its line, or every run of it
  const setOfRow = (r: number) => (v.mode === "sets" ? (index ? index[r] : r) : (cols.get("#set")?.values[r] ?? -1));
  // the lines kept: the axes' filters and Show (all, those that hold, a group...) - as the table
  const showM = useMemo(() => showMask(study), [study]);
  const keep = useMemo(() => {
    const m = keptMask(cols, v.filters, n);
    if (showM) for (let i = 0; i < n; i++) if (m[i] && !showM[setOfRow(i)]) m[i] = 0;
    return m;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cols, v.filters, n, showM, index, v.mode]);
  const shown = useMemo(() => { let k = 0; for (let i = 0; i < n; i++) k += keep[i]; return k; }, [keep, n]);
  const highlight = useMemo(() => {
    if (v.pinned === null || !n) return null;
    const h = new Uint8Array(n);
    for (let i = 0; i < n; i++) if (setOfRow(i) === v.pinned) h[i] = 1;
    return h;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [v.pinned, v.mode, cols, n, index]);
  // what is selected now: the lines every filter keeps - as parameter sets, and as runs (table rows)
  const selection = () => {
    const m = keep;
    const sets = new Set<number>(), rows: number[] = [];
    const rowCol = cols.get("#row")?.values;
    for (let i = 0; i < n; i++) if (m[i]) { sets.add(setOfRow(i)); if (rowCol) rows.push(rowCol[i]); }
    return { sets: [...sets], rows };
  };
  const exportShown = async () => {
    const p = await pickPath({ mode: "save", title: t("swExportShown"), exts: [".csv"], defaultName: study.name.replace(/\.[^.]+$/, "") + "_selected.csv" });
    if (!p) return;
    const sel = selection();
    try {
      const r = await sweepApi.exportRows(study.tableId, wireQuestion(study), v.mode === "runs" ? { rows: sel.rows } : { sets: sel.sets }, p);
      notify(t("swExported", { n: r.rows, path: r.path }));
      useSweeps.getState().journal("export", { path: r.path, n: r.rows });
    } catch (e) { notifyError(e); }
  };
  const menuCol = menu ? cols.get(menu.name) : undefined;
  const zoomKey = `res:${study.tableId}`;
  const zoom = useSweeps((s) => s.zooms[zoomKey]) ?? NO_ZOOM;
  return (
    <>
      {study.question.split && study.columns.some((c) => c.name === study.question.split && c.role === "hold") && <SplitBar study={study} />}
      <CenterTabs study={study} studies={useSweeps.getState().studies.length} />
      {study.answer && v.center === "charts" && <Desk study={study} />}
      {study.answer && v.center === "next" && <NextRunsView study={study} />}
      {v.center === "report" && <div className="sw-report-tab"><ReportCenter study={study} /><ReportSide study={study} /></div>}
      {v.center === "lines" && v.mode === "runs" && study.answer && !study.answer.runs && (
        // owner, 2026-11-03: "All runs" once showed the sets (the runs were still on their way) - now it says so
        <p className="empty-note sw-runs-loading">{study.evalError || t("swRunsLoading")}</p>
      )}
      {v.center === "lines" && !(v.mode === "runs" && study.answer && !study.answer.runs) && (study.answer ? (
        <>
          <PlotToolbar study={study} shown={shown} total={n}
            onKeep={() => st.narrow("keep", selection().sets, scopeKey(study))}
            onExclude={() => st.narrow("exclude", selection().sets, scopeKey(study))}
            onExport={exportShown}
            onExportPlot={() => say(exportPlot(t, study, lang))} />
          <p className="hint sw-what-line">{v.mode === "sets" ? t("swPerSetHint") : t("swPerRunHint")}
            <ZoomButtons zoom={zoom} onZoom={(z) => useSweeps.getState().setZoom(zoomKey, z)} /></p>
          {v.mode === "runs" && study.answer.counts.rows === study.answer.counts.sets && <p className="hint">{t("swRunsSameAsSets")}</p>}
          {study.answer.runs?.sampled && v.mode === "runs" && <p className="hint">{t("swSampled", { n: study.answer.runs.n.toLocaleString(), of: study.answer.runs.total.toLocaleString() })}</p>}
          {axes.length ? (
            <ParallelPlot sliderLabel={(a, b, n) => t("swAxesOnScreen", { a, b, n })} cols={cols} n={n} axes={axes} scaleOf={scale} reversed={v.reversed} colorBy={v.colorBy && cols.has(v.colorBy) ? v.colorBy : null}
              filters={v.filters} keep={keep} highlight={highlight} labelOf={(a) => colLabel(t, study, a)} fit={!!v.fitAxes}
              zoom={zoom} onZoom={(z) => useSweeps.getState().setZoom(zoomKey, z)}
              onPick={(r) => st.setView({ pinned: setOfRow(r) })}
              onFilter={(name, f) => st.setFilter(name, f)} onAxisMenu={(name, at) => setMenu({ name, at })}
              onMoveAxis={(name, to) => { const from = v.axes.indexOf(name); const target = v.axes.indexOf(axes[to]); if (from >= 0 && target >= 0) st.moveAxis(from, target); }} />
          ) : <p className="empty-note">{t("swNoAxes")}</p>}
          <SetsTable study={study} />
        </>
      ) : <p className="empty-note">{study.evalError || t("swReading")}</p>)}
      {!study.answer && v.center !== "lines" && <p className="empty-note">{study.evalError || t("swReading")}</p>}
      {menu && menuCol && (
        <AxisMenu col={menuCol} label={colLabel(t, study, menu.name)} at={menu.at} scale={scale(menu.name)} reversed={!!v.reversed[menu.name]}
          filter={v.filters[menu.name]} colouring={v.colorBy === menu.name}
          onScale={(s) => st.setScale(menu.name, s)}
          onReverse={() => st.setView({ reversed: { ...v.reversed, [menu.name]: !v.reversed[menu.name] } })}
          onColour={() => st.setView({ colorBy: menu.name })}
          onHide={() => { st.toggleAxis(menu.name, false); setMenu(null); }}
          onFilter={(f) => st.setFilter(menu.name, f)} onClose={() => setMenu(null)} />
      )}
    </>
  );
}
