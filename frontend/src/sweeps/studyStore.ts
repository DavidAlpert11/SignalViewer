/* W14 / W15 / W17 / W18: the study file's part of the Sweeps area - the study being edited (Set up, Together),
   its answer, the next runs, the launcher, the loop, the demo. C4: it lives in the area's one store
   (`useSweeps().common`, state.ts) and its edits are steps of the area's one Undo; `useStudyPanel` is a view
   on it for the panels. The study is the file: editing changes the copy, Save writes the file; the backend
   is asked with the copy as it is now (unsaved edits included), relative paths read against the saved file's
   folder. */
import { emptyCommon, recipeFiles, registerSetupHistory, SETUP_KEY, useSweeps, type StudyPanelState } from "./state";
import { studyApi } from "./studyApi";
import { areaRoles, goalToStudy, studyToGoal } from "./studyRoles";
import { upgradeQuestion } from "./model";
import { newSetupStudy, setupFromResults } from "./setup";
import { notify, notifyError } from "./notify";
import { flowAsked } from "./goFlow";
import { useApp } from "../store";
import { translate } from "../i18n";
import type { DemoProgress, LauncherSubmitResult, NextRunsResult, Study, StudyReq, StudyTable } from "./studyTypes";

export type { StudyPanelState };

const get = (): StudyPanelState => useSweeps.getState().common;
const set = (p: Partial<StudyPanelState>) => useSweeps.setState((st) => ({ common: { ...st.common, ...p } }));
const EMPTY = emptyCommon();
const SETUP_DEPTH = 50;

/** The study file's state, read like a store of its own (a selector, `getState`, `setState`). */
export const useStudyPanel = Object.assign(
  <T = StudyPanelState>(sel?: (s: StudyPanelState) => T): T => useSweeps((st) => (sel ? sel(st.common) : (st.common as unknown as T))),
  { getState: get, setState: set },
);

/** What the backend is asked with: the panel's copy, read against the saved file's folder. */
export const reqOf = (s = get()): StudyReq => (s.study ? { study: s.study, study_path: s.path || undefined } : { study_path: s.path });

let seq = 0;
/** The ranked answer for the study as it is now (a second ask drops the first's answer). */
export async function evaluate(): Promise<void> {
  const s = get();
  if (!s.study || s.demo) return;
  const my = ++seq;
  set({ busy: true, error: "" });
  try {
    const r = await studyApi.common(reqOf());
    if (my === seq) set({ result: r, busy: false });
  } catch (e) { if (my === seq) set({ busy: false, error: (e as Error).message, result: null }); }
}

export async function openStudyFile(path: string, demo = false): Promise<void> {
  set({ ...EMPTY, open: true, demo, path, busy: true });
  try {
    const { path: p, study } = await studyApi.open(path);
    set({ path: p, study, saved: JSON.stringify(study), busy: false, seenAt: Date.now() / 1000 });
    if (demo) set({ demoProgress: await studyApi.demoProgress(p) });
    else { await evaluate(); await refreshLoop(); if (get().loopProgress?.running) pollLoop(); }
  } catch (e) { set({ busy: false, error: (e as Error).message }); }
}

/** *New study* (C6): the choice between *I have results* and *Start from nothing*. */
export function chooseNewStudy(): void { useSweeps.setState({ part: "new" }); }

/** *Start from nothing*: a study of one system, typed in Set up. */
export function startFromNothing(): void {
  set({ ...EMPTY, open: true, study: newSetupStudy(""), saved: "" });
  useSweeps.setState({ part: "setup" });
}

/** *I have results*: the table opens (its results at once) and the study's Set up is filled from its columns. */
export async function haveResults(path: string): Promise<void> {
  await useSweeps.getState().open(path);
  if (await setupFromOpenTable()) useSweeps.setState({ part: "table" });
}

/** C11: a file of one of the study's tables (a round's results) opened in the four steps reads as that table - its
 *  columns' roles (the study names them by their common name: `rename` undone) and its goal. Part of opening, not
 *  an edit (no Undo step); the answer follows. */
export function applyStudyTable(index: number, tableId: string): void {
  const spec = get().study?.tables.find((x) => x.id === tableId);
  const st = useSweeps.getState(), t = st.studies[index];
  if (!spec || !t) return;
  const back = Object.fromEntries(Object.entries(spec.rename ?? {}).map(([own, common]) => [common, own]));
  const named = Object.fromEntries([
    ...(get().study?.shared ?? []).map((x) => [x.name, "shared"] as const),
    ...Object.entries(spec.roles ?? {}),
  ].map(([c, r]) => [back[c] ?? c, r]));
  const was = Object.fromEntries(t.columns.map((c) => [c.name, c.role]));
  // SF1: Send runs names what varies and the scenarios, never the outputs - then every other number is an output
  const rest = Object.values(spec.roles ?? {}).includes("output") ? {}
    : Object.fromEntries(t.columns.filter((c) => !(c.name in named) && c.name !== "run_id" && c.kind === "number" && (c.role === "param" || c.role === "hold"))
      .map((c) => [c.name, "output"]));
  const roles = areaRoles({ ...rest, ...named } as Parameters<typeof areaRoles>[0], was);
  if (t.columns.some((c) => c.name === "run_id") && !("run_id" in named)) roles.run_id = "id";     // the launcher's run id: never a role of its own
  const values = Object.fromEntries(t.columns.filter((c) => c.values?.length).map((c) => [c.name, c.values!]));
  const { question } = studyToGoal(spec, t.question, values);
  asRead.set(t.tableId, { question: JSON.stringify(question), goal: { constraints: spec.constraints, objective: spec.objective, aggregate: spec.aggregate, drop: spec.drop } });
  useSweeps.setState({ studies: st.studies.map((x, i) => (i === index
    ? { ...x, columns: x.columns.map((c) => (roles[c.name] && roles[c.name] !== c.role ? { ...c, role: roles[c.name] } : c)), question, studyTable: tableId } : x)) });
  if (useSweeps.getState().active === index) useSweeps.getState().refreshSummary();     // Columns' counts follow the roles
  useSweeps.getState().evaluate();
}

/** A file of the study's tables (a round's results) shown in the Data step: the open table read from it, or opened
 *  now as that study table (its roles and goal, C11). The navigator's rounds and the first results (SF1). */
export async function showStudyFile(file: string, table?: string): Promise<void> {
  const st = useSweeps.getState();
  const i = st.studies.findIndex((s) => s.path === file || s.tables.some((tb) => recipeFiles(tb.recipe).includes(file)));
  if (i < 0) {
    await st.open(file);
    if (table) applyStudyTable(useSweeps.getState().active, table);
  }
  useSweeps.setState({ active: i < 0 ? useSweeps.getState().active : i, part: "table" });
  useSweeps.getState().setView({ step: "raw" });
}

/** SF1: round 1 sent from Send runs - when it finishes with no table open, its results come in as a regular table in
 *  Data (shown at once when the user is still on Send runs); the usual flow follows from there. */
async function firstResultsIn(): Promise<void> {
  if (useSweeps.getState().studies.length || get().loopProgress?.points.length !== 1) return;
  const r = await studyApi.tables(get().path);
  for (const ft of r.tables) for (const rd of ft.rounds) {
    const f = rd.files.find((x) => x.rows);
    if (!f) continue;
    const part = useSweeps.getState().part;
    const was = flowAsked().n;
    markSeen(rd.files.map((x) => x.mtime));                          // shown: not "new" in the navigator
    await showStudyFile(f.path, ft.id);
    const now = flowAsked();
    // a step clicked while it was read: where that click went stays (not put back to where the round started)
    const back = now.n !== was ? now.part ?? part : part;
    if (back !== "setup") useSweeps.setState({ part: back });      // elsewhere: listed in Data, not shown over it
    notify(translate(useApp.getState().lang, "suResultsIn", { n: ft.name || ft.id }));
    return;
  }
}

/** C11: a study table's file open in the four steps is that table - its goal changed there (an edit, or that edit's
 *  Undo / Redo) is written into the study file's table, so Together's ranking follows. No step of its own: the
 *  table's one step undoes both (C4's one order). What the study cannot hold stays the table's own (`goalToStudy`). */
const asRead = new Map<string, { question: string; goal: Partial<StudyTable> }>();   // by the area's tableId
function followTableGoals(st: ReturnType<typeof useSweeps.getState>, prev: ReturnType<typeof useSweeps.getState>): void {
  const study = st.common.study;
  if (!study || st.studies === prev.studies) return;
  let tables = study.tables;
  for (const t of st.studies) {
    const was = prev.studies.find((x) => x.tableId === t.tableId);
    if (!t.studyTable || !was || was.studyTable !== t.studyTable || was.question === t.question) continue;   // just opened: as read
    const values = Object.fromEntries(t.columns.filter((c) => c.values?.length).map((c) => [c.name, c.values!]));
    const read = asRead.get(t.tableId);
    // back to the goal as it was read (an Undo): the study table's own words again, not a rewrite of them
    const patch = read && read.question === JSON.stringify(t.question) ? read.goal
      : Object.fromEntries(Object.entries(goalToStudy(t.question, values).patch).filter(([, v]) => v !== undefined));
    tables = tables.map((x) => (x.id === t.studyTable ? { ...x, ...patch } : x));
  }
  if (tables === study.tables || JSON.stringify(tables) === JSON.stringify(study.tables)) return;
  set({ study: { ...study, tables } });
  void evaluate();
}
useSweeps.subscribe(followTableGoals);

/** The study's Set up filled from the table on screen (I have results; the navigator's Set up for a table opened
 *  on its own, C7). False when no table is open. */
export async function setupFromOpenTable(): Promise<boolean> {
  const st = useSweeps.getState(), t = st.studies[st.active];
  if (!t) return false;
  const roles = Object.fromEntries(t.columns.map((c) => [c.name, c.role]));
  const guess = await studyApi.fromTable(t.tableId, roles);
  const { patch } = goalToStudy(upgradeQuestion(t.question));
  const name = t.name.replace(/\.[^.]+$/, "");
  set({ ...EMPTY, open: true, study: setupFromResults(guess, t.path, name, patch), saved: "", guess });
  return true;
}

/** One edit of the study: a step of the area's one Undo; the answer asked again. */
export function editStudy(f: (s: Study) => Study): void {
  const s = get();
  if (!s.study) return;
  const next = f(structuredClone(s.study));
  if (JSON.stringify(next) === JSON.stringify(s.study)) return;
  const study = s.study;
  useSweeps.setState((st) => ({ common: { ...st.common, study: next, past: [...st.common.past.slice(-(SETUP_DEPTH - 1)), study], future: [] },
    undoOrder: [...st.undoOrder, SETUP_KEY], redoOrder: [] }));
  void evaluate();
}
/** The study file's own step back / again - the area's Undo / Redo call them in their order (state.ts). */
function undoSetup(): boolean {
  const s = get();
  if (!s.past.length || !s.study) return false;
  set({ study: s.past[s.past.length - 1], past: s.past.slice(0, -1), future: [s.study, ...s.future] });
  void evaluate();
  return true;
}
function redoSetup(): boolean {
  const s = get();
  if (!s.future.length || !s.study) return false;
  set({ study: s.future[0], future: s.future.slice(1), past: [...s.past, s.study] });
  void evaluate();
  return true;
}
registerSetupHistory({ undo: undoSetup, redo: redoSetup });
/** The area's one Undo / Redo (kept by these names for the panels and the palette). */
export const undoStudy = (): void => useSweeps.getState().undo();
export const redoStudy = (): void => useSweeps.getState().redo();

export async function saveStudyAs(path: string): Promise<string> {
  const s = get();
  if (!s.study) return "";
  const r = await studyApi.save(path, s.study);
  set({ path: r.path, saved: JSON.stringify(s.study), seenAt: s.seenAt ?? Date.now() / 1000 });
  return r.path;
}

/** A round's files opened: what they hold is seen - only rounds written later stay *new*. */
export function markSeen(mtimes: (number | null)[]): void {
  const m = Math.max(get().seenAt ?? 0, ...mtimes.map((x) => x ?? 0));
  if (m > 0) set({ seenAt: m });
}

export const isUnsaved = (s = get()) => !!s.study && JSON.stringify(s.study) !== s.saved;

/** W15: the next runs (written into the round's folder and the study's history - the study must be saved). */
export async function suggestNext(): Promise<NextRunsResult> {
  const r = await studyApi.nextRuns({ ...reqOf(), write: true });
  // the history the backend wrote is the study now (opened again, so a later Save keeps it)
  const { study } = await studyApi.open(get().path);
  set({ next: r, study, saved: JSON.stringify(study), past: [], future: [] });
  return r;
}

/** W17: the exact command (nothing run), then - confirmed - the round sent; the runs' states polled. */
export async function launcherCommand(): Promise<LauncherSubmitResult> {
  const r = await studyApi.submit(get().path, false);
  set({ submit: r });
  return r;
}
export async function sendToLauncher(): Promise<void> {
  const r = await studyApi.submit(get().path, true);
  set({ submit: r });
  await pollStatus();
}
let polling = 0;
export async function pollStatus(): Promise<void> {
  window.clearTimeout(polling);
  try {
    const st = await studyApi.status(get().path);
    set({ status: st });
    if (!st.finished && !st.timed_out) polling = window.setTimeout(() => { void pollStatus(); }, 1500);
    else void evaluate();
  } catch (e) { set({ error: (e as Error).message }); }
}

/** W18: the demo's buttons; its progress polled while it runs. */
let demoPoll = 0;
export async function demoAction(action: "next" | "run" | "reset" | "stop"): Promise<void> {
  set({ error: "" });
  try {
    set({ demoProgress: await studyApi.demoStep(get().path, action) });
    if (action !== "reset") pollDemo();
  } catch (e) { set({ error: (e as Error).message }); }
}
function pollDemo(): void {
  window.clearTimeout(demoPoll);
  demoPoll = window.setTimeout(async () => {
    try {
      const p: DemoProgress = await studyApi.demoProgress(get().path);
      set({ demoProgress: p });
      if (p.running) pollDemo();
    } catch (e) { set({ error: (e as Error).message }); }
  }, 400);
}

/** The loop (any study with a launcher command): Next round / Run until converged / Stop / Reset, polled while
 *  it runs; the answer and the study (its history) follow each finished round. */
let loopPoll = 0;
export async function loopAction(action: "next" | "run" | "stop" | "reset"): Promise<void> {
  set({ error: "" });
  try {
    if ((action === "next" || action === "run") && (isUnsaved() || !get().path)) throw new Error("save");
    set({ loopProgress: await studyApi.loop(get().path, action) });
    if (action !== "reset") pollLoop();
  } catch (e) { if ((e as Error).message !== "save") set({ error: (e as Error).message }); else throw e; }
}
export async function refreshLoop(): Promise<void> {
  if (!get().path || get().demo) return;
  try { set({ loopProgress: await studyApi.loopProgress(get().path) }); } catch { /* a study never run: nothing to show */ }
}
function pollLoop(): void {
  window.clearTimeout(loopPoll);
  loopPoll = window.setTimeout(async () => {
    try {
      const before = get().loopProgress?.points.length ?? 0;
      const p = await studyApi.loopProgress(get().path);
      set({ loopProgress: p });
      if (p.points.length !== before) {                     // a round finished: its results are in the ranking now
        const { study } = await studyApi.open(get().path);
        set({ study, saved: JSON.stringify(study) });
        void evaluate();
        void firstResultsIn().catch(notifyError);
      }
      if (p.running) pollLoop();
      else if (p.error) set({ error: p.error });
    } catch (e) { set({ error: (e as Error).message }); }
  }, 600);
}

export function closePanel(): void {
  window.clearTimeout(loopPoll);
  window.clearTimeout(polling);
  window.clearTimeout(demoPoll);
  set({ ...EMPTY });
}

// W14: what the e2e tests wait on
(window as unknown as { __svStudy: unknown }).__svStudy = { state: () => get() };
