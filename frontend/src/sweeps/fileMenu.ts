/* The Sweeps area's file actions (CC1 / CC2): opening a table, a folder, a saved study; saving the study; and the
   top row's File ▾ built from them. Plain functions - the views that use them are SweepsArea and SweepsTools. */
import { pickPath, useApp, type MenuItem } from "../store";
import type { TFn } from "../i18n";
import { sweepApi } from "./api";
import { recipeFiles, savedOf, useSweeps, type SavedStudy } from "./state";
import { emptyView, materialize, newGoal } from "./model";
import { notify, say } from "./notify";
import { TABLE_EXTS, fileKind } from "./studyFile";
import { chooseNewStudy, closePanel, openStudyFile, refreshLoop, useStudyPanel } from "./studyStore";
import { fromFolder } from "../folderSummary";
import { confirmAsk, prompt } from "../components/Overlays";
import { saveStudyDialog, studyReportDialog } from "../components/sweeps/StudyPanel";

export const STUDY_EXT = ".svsweep";
const STUDY_FILE_EXT = ".svstudy.json";

export async function openTable(title: string) {
  const p = await pickPath({ mode: "open", title, exts: TABLE_EXTS });
  if (p) await useSweeps.getState().open(p);
}
export async function openFolder(title: string) {
  const p = await pickPath({ mode: "folder", title });
  if (p) await useSweeps.getState().open(p);
}
/** C10: one *Open a saved study* for either kind - a table's `.svsweep` or a study file (`.svstudy.json`). */
export async function openStudy(title: string): Promise<string> {
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

export async function saveStudy(t: TFn) {
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

/** CC1 / CC2 (owner, 2026-11-26: one way through Sweeps): the area's file actions are the top row's File ▾ - a new
 *  study, a table, a folder, a saved study; the study kept (save, template, report); reloading / following its file;
 *  Clear - and its undo / redo are the top row's (SweepsTools). No second toolbar row. */
export function sweepsFileItems(t: TFn): MenuItem[] {
  const st = useSweeps.getState();
  const studies = st.studies;
  const study = studies[st.active];
  const common = useStudyPanel.getState().open;
  const SEP: MenuItem = { label: "", sep: true, run: () => {} };
  // C10: one Open - a new study, a table, a folder, a saved study of either kind (.svsweep or .svstudy.json)
  const open: MenuItem[] = [
    { label: t("nsTitle") + "…", run: chooseNewStudy },
    { label: t("swOpenTable"), run: () => openTable(t("swOpenTable")) },
    { label: t("swOpenFolder"), run: () => openFolder(t("swOpenFolder")) },
    // FL1: a folder of recordings summed up, a row each
    { label: t("swFromFolder"), run: () => { void fromFolder(); } },
    { label: t("swOpenStudy"), run: () => say(openStudy(t("swOpenStudy")).then((m) => { if (m) throw new Error(m); })) },
  ];
  // what is kept of the study: the study itself, a template, a report (C10: with a study file open, its report)
  const studyReport: MenuItem = { label: t("srMenu"), run: () => { void studyReportDialog(t); } };
  const kept: MenuItem[] = !study ? (common ? [{ label: t("swSaveStudy"), run: () => saveStudy(t) }, studyReport] : []) : [
    { label: t("swSaveStudy"), run: () => saveStudy(t) },
    { label: t("swSaveTemplate"), run: async () => {
      const name = (await prompt(t("swSaveTemplate"), t("swTemplateName"), study.name.replace(/\.[^.]+$/, "")))?.trim();
      if (!name) return;
      if (st.templates.some((x) => x.name === name) && !(await confirmAsk(t("swTplReplace"), t("swTplReplaceAsk", { n: name })))) return;
      say(st.saveTemplate(name).then(() => t("swTemplateSaved", { n: name })));
    } },
    { label: t("swTemplatesMenu"), run: () => useSweeps.setState({ templatesOpen: true }) },
    common ? studyReport : { label: t("swReportMenu"), disabled: !study.answer, run: () => useSweeps.setState({ reportOpen: true }) },
  ];
  // the table's file: read again now, or follow it as it grows
  const file: MenuItem[] = study?.path ? [
    { label: t("swRefresh"), run: () => useSweeps.getState().reload() },
    { label: t("swFollow"), checked: !!study.view.follow, run: () => useSweeps.getState().setView({ follow: !study.view.follow }) },
  ] : [];
  /* Clear (owner, 2026-11-03: as in Recordings) - from the least to everything; each but the last is
     undone with Ctrl+Z, closing the studies with the notice's Undo (they are opened again) */
  const clear: MenuItem[] = [
    ...(study ? [
      { label: t("swClearCharts"), run: () => st.setView({ groups: [], activeGroup: undefined, desk: undefined, rerun: [], rerunSplit: [], filters: {}, filterTab: {}, pinned: null }) },
      { label: t("swClearGoal"), run: () => {
        st.setQuestion(materialize({ ...study.question, goals: [newGoal("1")], active: 0, robust: undefined, split: undefined }));
        st.setView({ ...emptyView(), step: "goals" });
        useSweeps.getState().evaluate();
      } },
      { label: t("swStartOver"), run: () => st.resetStudy() },
      SEP,
    ] : []),
    ...(common ? [{ label: t("cpClose"), run: closePanel }, SEP] : []),
    // SF1 (owner): everything = the study file too (asked first; the notice's one Undo opens it all again)
    { label: t("swClearAll", { n: studies.length + (common ? 1 : 0) }), danger: true, disabled: !studies.length && !common, run: async () => {
      if (!(await confirmAsk(t("swClearAllTitle"), t("swClearAllAsk"), t("swClearAllOk"), true))) return;
      const now = useSweeps.getState();
      // what can be opened again (read from files): put back by the notice's Undo
      const docs = now.studies.filter((x) => x.path || x.tables.some((tb) => recipeFiles(tb.recipe).length)).map(savedOf);
      const f = now.common.open ? now.common : null;
      for (let i = now.studies.length - 1; i >= 0; i--) useSweeps.getState().close(i);
      if (f) closePanel();
      useSweeps.setState({ part: "" });
      const n = now.studies.length + (f ? 1 : 0);
      useApp.getState().toast({ kind: "info", text: t("swClearedAll", { n }),
        action: docs.length || f ? { label: t("undo"), run: async () => {
          if (f) { useStudyPanel.setState({ ...f, past: [], future: [] }); void refreshLoop(); }
          for (const d of docs) await useSweeps.getState().open(d.path, d);
        } } : undefined });
    } },
  ];
  return [...open, ...(kept.length ? [SEP, ...kept] : []), ...(file.length ? [SEP, ...file] : []),
    ...(studies.length || common ? [SEP, { label: t("swClear"), run: () => {}, items: clear }] : [])];
}

