/* The Sweeps area (areas.ts): a results table - one row per run, parameters and scenario columns
   first, outputs last - and the question asked of it.

   This file is layout only. The pieces, each its own file:
     FlowNav                        the five steps of every study (PLAN 2026-11-16 §7a): data, columns,
                                    goal, results, next runs - for a table and a study file alike
     Navigator + SetupView          Data: the tables (layers of runs) and the problem's definition
     RawStep, RolesStep, GoalsStep  a table's steps, each with its side panel and its middle
     ResultsSide + CenterTabs       the results' views:
       PlotToolbar + ParallelPlot + SetsTable   the parameter sets / all runs as lines (+ AxisMenu)
       Desk         charts made from the columns   ReportStep   the report
       StudyPanel   the systems together (a study file of several)
     NextStep                       Next runs: the proposal (NextRunsView) and running it (RunPanel)
     SetDetail                      one set on the right: why it fails, its runs, its recordings
   State: sweeps/state.ts. Styles: ./sweeps.css (its own file, to restyle the area alone). */
import { openExample } from "../Welcome";
import { Words } from "../../i18n";
import { RECORDING_WORDS } from "../../sweeps/i18n";
import DemoGuide from "../DemoGuide";
import { useEffect, useMemo, useRef, useState } from "react";
import PanelResizer from "../PanelResizer";
import { usePanelWidth } from "../panelWidth";
import { pickPath, useApp } from "../../store";
import { translate, useT, type TFn } from "../../i18n";
import { registerArea } from "../../areaCommands";
import Toasts from "../Toasts";
import { normCenter, normStep } from "../../sweeps/model";
import { FLOW } from "../../sweeps/flow";
import FlowNav, { flowTitle, goFlow, useFlowStep } from "./FlowNav";
import { useLeftHidden } from "../../sweeps/narrow";
import { Icon } from "../../icons";
import { sweepApi } from "../../sweeps/api";
import { recipeFiles, savedOf, useCanRedo, useCanUndo, useSweeps, useStudy, wireQuestion, type Study } from "../../sweeps/state";
import { emptyView, newGoal, materialize } from "../../sweeps/model";
import { notify, notifyError, say } from "../../sweeps/notify";
import { activeParams, colLabel, reorderedAxes, scaleOf, scopedColumns, scopeKey, showMask, shownAxes } from "../../sweeps/view";
import { keptMask } from "../../sweeps/filters";
import { runSelection } from "../../sweeps/selection";
import ReportDialog from "./ReportDialog";
import { TABLE_EXTS, fileKind } from "../../sweeps/studyFile";
import TemplatesDialog from "./TemplatesDialog";
import { RawCenter, ZoomButtons } from "./RawStep";
import Navigator from "./Navigator";
import NextStep from "./NextStep";
import { NO_ZOOM } from "../../sweeps/zoom";
import { RolesCenter, RolesSide } from "./RolesStep";
import { templateSummary } from "../../sweeps/templates";
import { GoalsCenter, GoalsSide } from "./GoalsStep";
import ResultsSide from "./ResultsSide";
import { ReportCenter, ReportSide, exportPlot } from "./ReportStep";
import { confirmAsk, openMenu, prompt } from "../Overlays";
import type { SavedStudy } from "../../sweeps/state";
import AxisMenu from "./AxisMenu";
import CenterTabs, { TogetherTabs } from "./CenterTabs";
import SplitBar from "./SplitBar";
import Desk from "./Desk";
import ParallelPlot from "./ParallelPlot";
import PlotToolbar from "./PlotToolbar";
import SetDetail from "./SetDetail";
import SetsTable from "./SetsTable";
import StudyPanel, { saveStudyDialog, studyReportDialog } from "./StudyPanel";
import { HowItWorks } from "./DemoView";
import NewStudy from "./NewStudy";
import SetupView from "./SetupView";
import { chooseNewStudy, closePanel, startFromNothing, openStudyFile, redoStudy, refreshLoop, undoStudy, useStudyPanel } from "../../sweeps/studyStore";
import { onStudyRequest, requestStudy, takeStudy } from "../../sweeps/studyOpen";
import { onAreaExample, takeAreaExample } from "../../areaExample";
import { fromFolder } from "../../folderSummary";
import { api } from "../../api";
import "./sweeps.css";

/** the middle (plot, tables) never narrower than this when a panel is dragged wider */
const MIN_MIDDLE = 380;
const LEFT_MIN = 220, LEFT_MAX = 320;
const STUDY_EXT = ".svsweep", STUDY_FILE_EXT = ".svstudy.json";

async function openTable(title: string) {
  const p = await pickPath({ mode: "open", title, exts: TABLE_EXTS });
  if (p) await useSweeps.getState().open(p);
}
async function openFolder(title: string) {
  const p = await pickPath({ mode: "folder", title });
  if (p) await useSweeps.getState().open(p);
}
/** C10: one *Open a saved study* for either kind - a table's `.svsweep` or a study file (`.svstudy.json`). */
async function openStudy(title: string): Promise<string> {
  const p = await pickPath({ mode: "open", title, exts: [STUDY_EXT, STUDY_FILE_EXT, ".json"] });
  if (!p) return "";
  try {
    if (!p.endsWith(STUDY_EXT)) { await openStudyFile(p); return ""; }
    const doc = JSON.parse((await sweepApi.loadText(p)).text) as SavedStudy;
    if (doc.kind !== "signalviewer-sweep") return "not a study";
    // a study saved with its tables needs no `path` (its first table may be a merged one); tables named
    // relative to the file (a copied or shipped study) are found beside it, as the welcome card does
    const r = resolveIn(doc, p.replace(/[\\/][^\\/]*$/, ""));
    await useSweeps.getState().open(r.path, r);
    return "";
  } catch (e) { return (e as Error).message; }
}

/** A .svsweep that names its tables relative to itself (shipped with the examples, copied elsewhere): made absolute. */
function resolveIn(doc: SavedStudy, dir: string): SavedStudy {
  const abs = (p: string) => (!p || /^([a-zA-Z]:)?[\\/]/.test(p) ? p : `${dir}/${p}`);
  const fix = (r: unknown): unknown => (r && typeof r === "object"
    ? Object.fromEntries(Object.entries(r as Record<string, unknown>).map(([k, v]) => [k, k === "path" && typeof v === "string" ? abs(v) : Array.isArray(v) ? v.map(fix) : fix(v)]))
    : r);
  return { ...doc, path: abs(doc.path), tables: doc.tables?.map((x) => ({ ...x, recipe: fix(x.recipe) as typeof x.recipe })) };
}

/** Open a .svsweep (a table and its question) by its path - the welcome screen's sweep card. */
export async function openStudyPath(p: string): Promise<void> {
  const doc = JSON.parse((await sweepApi.loadText(p)).text) as SavedStudy;
  if (doc.kind !== "signalviewer-sweep") throw new Error("not a study");
  const r = resolveIn(doc, p.replace(/[\\/][^\\/]*$/, ""));
  await useSweeps.getState().open(r.path, r);
}

async function saveStudy(t: TFn) {
  const st = useSweeps.getState(), cp = useStudyPanel.getState();
  // C10: one Save - the study file when the study needs one (C5 `fileKind`); one table with a guessed Set up
  // (*I have results*) stays the table's own .svsweep; a study opened from its file is saved there
  const asStudy = !st.studies.length || !!cp.path?.toLowerCase().endsWith(STUDY_FILE_EXT) || fileKind(cp.study, st.studies.length) === "svstudy";
  if (cp.open && asStudy) { await saveStudyDialog(t); return; }
  const study = st.studies[st.active], doc = st.saved();
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
    if (!(e.ctrlKey || e.metaKey)) return false;
    const k = e.key.toLowerCase();
    const undo = k === "z" && !e.shiftKey, redo = k === "y" || (k === "z" && e.shiftKey);
    // one Undo for the area (C4): the newest step, in a table or in the study file
    if (!st.studies[st.active] && !useStudyPanel.getState().open) return false;
    if (undo) { st.undo(); return true; }
    if (redo) { st.redo(); return true; }
    return false;
  },
  commands: () => {
    const t = tNow, st = useSweeps.getState(), study = st.studies[st.active], g = t("areaSweeps");
    const common = useStudyPanel.getState().open;
    // C10: each command once - New study, the three ways to open (a saved study of either kind is one)
    const open = [
      { id: "sw-new-study", label: t("nsTitle"), group: g, icon: "open" as const, run: chooseNewStudy },
      { id: "sw-open-table", label: t("swOpenTable"), group: g, icon: "open" as const, run: () => { openTable(t("swOpenTable")); } },
      { id: "sw-open-folder", label: t("swOpenFolder"), group: g, icon: "open" as const, run: () => { openFolder(t("swOpenFolder")); } },
      { id: "sw-from-folder", label: t("swFromFolder"), group: g, icon: "open" as const, run: () => { void fromFolder(); } },
      { id: "sw-open-study", label: t("swOpenStudy"), group: g, icon: "open" as const, run: () => { openStudy(t("swOpenStudy")).then((m) => m && notify(m, "error")); } },
    ];
    if (!study && !common) return open;
    const both = [
      { id: "sw-undo", label: t("undo"), group: g, icon: "undo" as const, keys: "Ctrl Z", run: undoStudy },
      { id: "sw-redo", label: t("redo"), group: g, icon: "redo" as const, keys: "Ctrl Y", run: redoStudy },
      ...open,
      { id: "sw-save-study", label: t("swSaveStudy"), group: g, icon: "save" as const, run: () => { void saveStudy(t); } },
      ...(common ? [{ id: "sw-close-study", label: t("cpClose"), group: g, run: closePanel },
        { id: "sw-report", label: t("srMenu"), group: g, icon: "report" as const, run: () => { void studyReportDialog(t); } }] : []),
    ];
    if (!study) return both;
    return [
      ...both,
      ...(common ? [] : [{ id: "sw-report", label: t("swReportMenu"), group: g, icon: "report" as const, run: () => useSweeps.setState({ reportOpen: true }) }]),
      { id: "sw-templates", label: t("swTemplates"), group: g, run: () => useSweeps.setState({ templatesOpen: true }) },
      { id: "sw-start-over", label: t("swStartOver"), group: g, run: st.resetStudy },
      ...FLOW.map((s, i) => ({ id: `sw-step-${s}`, label: `${i + 1} ${flowTitle(t, s)}`, group: t("swSteps"), run: () => goFlow(s) })),
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
    // the demo opens on Next runs - its Next round and the chart converging (§7a)
    const take = () => { const r = takeStudy(); if (r) { if (r.demo) useSweeps.setState({ part: "run" }); void openStudyFile(r.path, r.demo); } };
    take();
    return onStudyRequest(take);
  }, []);
  // the welcome screen's sweep card: its table
  useEffect(() => {
    const take = () => { const p = takeAreaExample("sweeps"); if (p) void (p.endsWith(STUDY_EXT) ? openStudyPath(p) : useSweeps.getState().open(p)); };
    take();
    return onAreaExample(take);
  }, []);
  const common = useStudyPanel((s) => s.open);
  const part = useSweeps((s) => s.part);
  if (part === "new") return <><SweepsBar /><NewStudy /></>;
  if (!common && !study) return <><SweepsBar /><SweepsWelcome /></>;
  return <><SweepsBar /><StudyFlow /></>;
}

/** A study open (a table, a study file, or both): the five steps and the step shown (PLAN 2026-11-16 §7a). */
function StudyFlow() {
  const t = useT();
  const study = useStudy();
  const step = useFlowStep();
  const part = useSweeps((s) => s.part);
  const common = useStudyPanel((s) => s.open);
  const demo = useStudyPanel((s) => s.demo);
  const [navW, setNavW] = usePanelWidth("swNav", 260);
  const box = useRef<HTMLDivElement>(null);
  const empty = <p className="empty-note sw-flow-empty">{t("flNeedsTableHint")}</p>;
  let body: React.ReactNode;
  if (step === "data") {
    // the problem: its tables (layers of runs) on the start side, the table's data or the definition in the middle
    const middle = common && demo && part === "about" ? <div className="cp-panel dm-panel dm-about"><HowItWorks /></div>
      : (common && part === "setup") || !study ? <SetupView /> : <StudyView study={study} />;
    body = (
      <div className="sw-ws" ref={box} style={{ gridTemplateColumns: `${navW}px minmax(0, 1fr)` }}>
        <Navigator />
        <PanelResizer label={t("resizePanel")} style={{ insetInlineStart: navW - 3 }} width={navW} setWidth={setNavW} grow={+1} def={260}
          max={() => Math.min(480, (box.current?.clientWidth ?? window.innerWidth) - MIN_MIDDLE)} />
        {middle}
      </div>
    );
  } else if (step === "next") body = <NextStep />;
  else if (step === "results" && (part === "together" || !study)) body = common ? <div className="sw-together"><TogetherTabs /><StudyPanel /></div> : empty;
  else body = study ? <StudyView study={study} /> : empty;
  return (
    <Words.Provider value={study?.recordings && !common ? RECORDING_WORDS : null}>
    <div className="sw-study-wrap sw-flow" data-flow={step}>
      <div className="notices sw-notices"><Toasts /></div>
      <FlowNav />
      {study?.recordings && <DemoGuide area="sweeps" />}
      {body}
    </div>
    </Words.Provider>
  );
}

function SweepsBar() {
  const canUndo = useCanUndo(), canRedo = useCanRedo();
  const t = useT();
  const studies = useSweeps((s) => s.studies);
  const active = useSweeps((s) => s.active);
  const study = studies[active];
  const common = useStudyPanel((s) => s.open);
  const below = (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    return { clientX: r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent;
  };
  // the ways in: one menu (they were four buttons, two with the same icon)
  // C10: one Open ▾ - a new study, a table, a folder, a saved study of either kind (.svsweep or .svstudy.json)
  const openMenuAt = (e: React.MouseEvent) => openMenu(below(e), [
    { label: t("nsTitle") + "…", run: chooseNewStudy },
    { label: "", sep: true, run: () => {} },
    { label: t("swOpenTable"), run: () => openTable(t("swOpenTable")) },
    { label: t("swOpenFolder"), run: () => openFolder(t("swOpenFolder")) },
    // FL1: a folder of recordings summed up, a row each (W16: the ways to open a folder are here, not on the welcome)
    { label: t("swFromFolder"), run: () => { void fromFolder(); } },
    { label: t("swOpenStudy"), run: () => say(openStudy(t("swOpenStudy")).then((m) => { if (m) throw new Error(m); })) },
  ]);
  // what is kept of the study: the study itself, a template, a report
  const studyMenu = (e: React.MouseEvent) => {
    const st = useSweeps.getState();
    const SEP = { label: "", sep: true, run: () => {} };
    // C10: with a study file open its report is the study's (a table's own report stays in its Results)
    const studyReport = { label: t("srMenu"), run: () => { void studyReportDialog(t); } };
    if (!study) { openMenu(below(e), [{ label: t("swSaveStudy"), run: () => saveStudy(t) }, SEP, studyReport]); return; }
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
      common ? studyReport : { label: t("swReportMenu"), disabled: !study.answer, run: report },
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
      ...(useStudyPanel.getState().open ? [{ label: t("cpClose"), run: closePanel }, { label: "", sep: true, run: () => {} }] : []),
      // SF1 (owner): everything = the study file too (asked first; the notice's one Undo opens it all again)
      { label: t("swClearAll", { n: studies.length + (common ? 1 : 0) }), danger: true, disabled: !studies.length && !common, run: async () => {
        if (!(await confirmAsk(t("swClearAllTitle"), t("swClearAllAsk"), t("swClearAllOk"), true))) return;
        const now = useSweeps.getState();
        // what can be opened again (read from files): put back by the notice's Undo
        const docs = now.studies.filter((x) => x.path || x.tables.some((tb) => recipeFiles(tb.recipe).length)).map(savedOf);
        const file = now.common.open ? now.common : null;
        for (let i = now.studies.length - 1; i >= 0; i--) useSweeps.getState().close(i);
        if (file) closePanel();
        useSweeps.setState({ part: "" });
        const n = now.studies.length + (file ? 1 : 0);
        useApp.getState().toast({ kind: "info", text: t("swClearedAll", { n }),
          action: docs.length || file ? { label: t("undo"), run: async () => {
            if (file) { useStudyPanel.setState({ ...file, past: [], future: [] }); void refreshLoop(); }
            for (const d of docs) await useSweeps.getState().open(d.path, d);
          } } : undefined });
      } },
    ]);
  };
  useEffect(() => { useSweeps.getState().loadTemplates(); }, []);
  const reportOpen = useSweeps((s) => s.reportOpen);
  const templatesOpen = useSweeps((s) => s.templatesOpen);
  const report = () => useSweeps.setState({ reportOpen: true });
  return (
    <div className="areabar" role="toolbar" aria-label={t("areaSweeps")}>
      {(study || common) && <>
        <button className="iconbtn" disabled={!canUndo} onClick={() => useSweeps.getState().undo()} title={`${t("undo")} (Ctrl+Z)`} aria-label={t("undo")}><Icon.Undo /></button>
        <button className="iconbtn" disabled={!canRedo} onClick={() => useSweeps.getState().redo()} title={`${t("redo")} (Ctrl+Y)`} aria-label={t("redo")}><Icon.Redo /></button>
      </>}
      <button className="btn outline" onClick={openMenuAt}><Icon.Open /> {t("swOpen")} ▾</button>
      {(study || common) && <button className="btn outline" onClick={studyMenu}>{t("swStudy")} ▾</button>}
      {(studies.length > 0 || common) && <button className="btn outline sw-clear-btn" onClick={clearMenu} title={t("swClearHint")}><Icon.Eraser /> {t("swClear")} ▾</button>}
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
  // the two example studies (the welcome screen's cards): the three drones, the smart-sweep demo
  const [demoPath, setDemoPath] = useState("");
  const [gainsPath, setGainsPath] = useState("");
  const [folderEx, setFolderEx] = useState<Parameters<typeof openExample>[0] | null>(null);
  useEffect(() => {
    api.examples().then((xs) => {
      setFolderEx(xs.find((e) => e.id === "folderOfFlights") ?? null);
      const last = (id: string) => { const x = xs.find((e) => e.id === id); return x ? x.paths[x.paths.length - 1] : ""; };
      setDemoPath(last("smartSweepDemo")); setGainsPath(last("commonGains"));
    }).catch(() => {});
  }, []);
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
        {/* FR6 (owner, 2026-11-16): three equal starts - results in hand, nothing yet, a folder of recordings - each one
            click, its examples under it. Saved studies and folders of tables stay in Open ▾ (W16). */}
        <div className="sw-ways sw-starts">
          <div className="sw-way" data-start="have">
            <button className="btn primary sw-start" disabled={busy} onClick={() => openTable(t("nsHaveTitle"))}><Icon.Open /> {t("nsHave")}</button>
            <p className="hint">{t("swStartHaveHint")}</p>
            <div className="sw-welcome-actions">
              <button className="btn outline sm" disabled={busy} onClick={example}>{t("swTryExample")}</button>
              <button className="btn outline sm" disabled={busy} onClick={() => merged().catch(notifyError)}>{t("swTryMerged")}</button>
              {gainsPath && <button className="btn outline sm sw-try-gains" onClick={() => requestStudy(gainsPath)}>{t("swTryGains")}</button>}
            </div>
          </div>
          <div className="sw-way" data-start="nothing">
            <button className="btn primary sw-start sw-start-nothing" disabled={busy} onClick={startFromNothing}>{t("nsNothing")}</button>
            <p className="hint">{t("swStartNothingHint")}</p>
            <div className="sw-welcome-actions">
              {demoPath && <button className="btn outline sm sw-try-demo" onClick={() => requestStudy(demoPath, true)}>{t("swTryDemo")}</button>}
            </div>
          </div>
          <div className="sw-way" data-start="folder">
            <button className="btn primary sw-start" disabled={busy} onClick={() => { void fromFolder(); }}>{t("swStartFolder")}</button>
            <p className="hint">{t("swStartFolderHint")}</p>
            <div className="sw-welcome-actions">
              {folderEx && <button className="btn outline sm sw-try-folder" onClick={() => openExample(folderEx)}>{t("swTryFolder")}</button>}
            </div>
          </div>
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
  // the Data step has no side panel (C7): its tables are the navigator's
  const side = step === "raw" ? null : step === "roles" ? <RolesSide study={study} />
    : step === "goals" ? <GoalsSide study={study} /> : <ResultsSide study={study} />;
  const noParams = !activeParams(study).length;
  // the side panels: widths dragged (and remembered) as in Recordings, the steps' panel can be hidden
  // the steps' panel: about 220 to 320 px (owner, 2026-11-02)
  const [leftW0, setLeftW] = usePanelWidth("swLeft", 280);
  const leftW = Math.max(LEFT_MIN, Math.min(LEFT_MAX, leftW0));
  const [detailW, setDetailW] = usePanelWidth("swDetail", 380);
  const leftHidden = useLeftHidden() || !side;
  const detail = step === "results" && study.view.pinned !== null && !!study.answer;
  const box = useRef<HTMLDivElement>(null);
  const room = (other: number) => () => (box.current?.clientWidth ?? window.innerWidth) - other - MIN_MIDDLE;
  const cols = [leftHidden ? "" : `${leftW}px`, "minmax(0, 1fr)", detail ? `${detailW}px` : ""].filter(Boolean).join(" ");
  return (
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
  // what is selected now. Parameter sets: the lines every filter keeps (every set is drawn). All runs: the
  // runs drawn are a sample above the cap, so the server resolves the brush on the whole table (1.29)
  const shownSets = () => {
    const sets = new Set<number>();
    for (let i = 0; i < n; i++) if (keep[i]) sets.add(setOfRow(i));
    return [...sets];
  };
  const narrow = async (kind: "keep" | "exclude") => {
    const key = scopeKey(study);
    try {
      const sets = v.mode === "runs" ? (await sweepApi.select(study.tableId, wireQuestion(study), runSelection(study))).sets : shownSets();
      st.narrow(kind, sets, key);
    } catch (e) { notifyError(e); }
  };
  const exportShown = async () => {
    const p = await pickPath({ mode: "save", title: t("swExportShown"), exts: [".csv"], defaultName: study.name.replace(/\.[^.]+$/, "") + "_selected.csv" });
    if (!p) return;
    try {
      const r = await sweepApi.exportRows(study.tableId, wireQuestion(study), v.mode === "runs" ? { select: runSelection(study) } : { sets: shownSets() }, p);
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
      {v.center === "report" && <div className="sw-report-tab"><ReportCenter study={study} /><ReportSide study={study} /></div>}
      {v.center === "lines" && v.mode === "runs" && study.answer && !study.answer.runs && (
        // owner, 2026-11-03: "All runs" once showed the sets (the runs were still on their way) - now it says so
        <p className="empty-note sw-runs-loading">{study.evalError || t("swRunsLoading")}</p>
      )}
      {v.center === "lines" && !(v.mode === "runs" && study.answer && !study.answer.runs) && (study.answer ? (
        <>
          <PlotToolbar study={study} shown={shown} total={n}
            onKeep={() => void narrow("keep")}
            onExclude={() => void narrow("exclude")}
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
              onMoveAxis={(name, to) => st.setAxes(reorderedAxes(study, name, to))} />
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
