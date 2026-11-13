/* W14 / W15 / W17 / W18: the Common parameters panel's state - the study being edited (with its own Undo /
   Redo, like a Sweeps study), its answer, the next runs, the launcher, the demo. The study is the file:
   editing changes the panel's copy, Save writes the file; the panel asks the backend with the copy as it is
   now (unsaved edits included), relative paths read against the saved file's folder. */
import { create } from "zustand";
import { studyApi } from "./studyApi";
import type { CommonResult, DemoProgress, LoopProgress, LauncherStatusResult, LauncherSubmitResult, NextRunsResult, Study, StudyReq } from "./studyTypes";

export interface StudyPanelState {
  open: boolean;
  demo: boolean;
  path: string;
  study: Study | null;
  saved: string;                      // the study as last saved / opened (JSON) - unsaved while different
  past: Study[];
  future: Study[];
  result: CommonResult | null;
  next: NextRunsResult | null;
  submit: LauncherSubmitResult | null;
  status: LauncherStatusResult | null;
  demoProgress: DemoProgress | null;
  loopProgress: LoopProgress | null;
  pinned: number | null;              // the ranked row opened
  busy: boolean;
  error: string;
}

const EMPTY: StudyPanelState = { open: false, demo: false, path: "", study: null, saved: "", past: [], future: [], result: null, next: null,
  submit: null, status: null, demoProgress: null, loopProgress: null, pinned: null, busy: false, error: "" };

export const useStudyPanel = create<StudyPanelState>(() => ({ ...EMPTY }));
const set = useStudyPanel.setState;
const get = useStudyPanel.getState;

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
    set({ path: p, study, saved: JSON.stringify(study), busy: false });
    if (demo) set({ demoProgress: await studyApi.demoProgress(p) });
    else { await evaluate(); await refreshLoop(); if (get().loopProgress?.running) pollLoop(); }
  } catch (e) { set({ busy: false, error: (e as Error).message }); }
}

export function newStudy(): void {
  const study: Study = { version: 1, name: "", tables: [], shared: [], combine: { mode: "auto" }, search: { params: {} }, next: { batch: 20 } };
  set({ ...EMPTY, open: true, study, saved: "" });
}

/** One edit of the study: recorded for Undo; the answer asked again. */
export function editStudy(f: (s: Study) => Study): void {
  const s = get();
  if (!s.study) return;
  const next = f(structuredClone(s.study));
  if (JSON.stringify(next) === JSON.stringify(s.study)) return;
  set({ study: next, past: [...s.past.slice(-49), s.study], future: [] });
  void evaluate();
}
export function undoStudy(): void {
  const s = get();
  if (!s.past.length || !s.study) return;
  set({ study: s.past[s.past.length - 1], past: s.past.slice(0, -1), future: [s.study, ...s.future] });
  void evaluate();
}
export function redoStudy(): void {
  const s = get();
  if (!s.future.length || !s.study) return;
  set({ study: s.future[0], future: s.future.slice(1), past: [...s.past, s.study] });
  void evaluate();
}

export async function saveStudyAs(path: string): Promise<string> {
  const s = get();
  if (!s.study) return "";
  const r = await studyApi.save(path, s.study);
  set({ path: r.path, saved: JSON.stringify(s.study) });
  return r.path;
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
