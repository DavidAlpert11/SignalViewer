import { DATA_EXTS } from "./values";
import { isEmptyStart, offerStart } from "./smartStart";
import { api, type JobInfo, type LoadErrorInfo } from "./api";
import { actions, useApp } from "./store";
import { dictionaries, translate, type Lang, type TKey } from "./i18n";

/** Run a long operation as a background job: progress panel + cancel (N-04).
 *  Resolves with the job's result, or null when the user cancelled. Throws on errors. */
export async function runJob<T = any>(kind: string, body: unknown, label: string): Promise<T | null> {
  return followJob<T>(await api.startJob(kind, body, label), label);
}

/** Follow a job some endpoint started (progress in the jobs bar, like runJob). */
export async function followJob<T = any>(job: JobInfo, label: string): Promise<T | null> {
  const upd = (j: JobInfo) => useApp.setState({
    jobs: useApp.getState().jobs.filter((x) => x.id !== j.id).concat(j.state === "running" ? [{ id: j.id, label, progress: j.progress, phase: j.phase }] : []),
  });
  let j = job;
  upd(j);
  while (j.state === "running") {
    await new Promise((r) => setTimeout(r, 200));
    try { j = await api.job(job.id); } catch { continue; }
    upd(j);
  }
  if (j.state === "error") throw new Error(j.error || "Failed");
  return j.state === "done" ? (j.result as T) : null;
}

/** A background job the CALLER controls: quiet progress (no popup) and cancel().
 *  Cancelling stops the work on the server, not just the waiting in the UI. */
export function startJob<T = any>(kind: string, body: unknown, onProgress?: (p: number) => void) {
  let jobId: string | null = null;
  let cancelled = false;
  const result = (async (): Promise<T | null> => {
    const j0 = await api.startJob(kind, body, kind);
    jobId = j0.id;
    if (cancelled) { api.cancelJob(j0.id).catch(() => {}); return null; }
    let j = j0, wait = 60;
    while (j.state === "running") {
      await new Promise((r) => setTimeout(r, wait));
      wait = Math.min(200, wait * 2);           // quick jobs finish without a visible delay
      if (cancelled) return null;
      try { j = await api.job(j0.id); } catch { continue; }
      onProgress?.(j.progress);
    }
    if (j.state === "error") throw new Error(j.error || "Failed");
    return j.state === "done" ? (j.result as T) : null;
  })();
  return {
    result,
    cancel: () => { cancelled = true; if (jobId) api.cancelJob(jobId).catch(() => {}); },
  };
}

export async function cancelJob(id: string) {
  await api.cancelJob(id);
}

export const SUPPORTED_LABEL = DATA_EXTS.map((e) => e.slice(1).toUpperCase()).join(", ");

/** The reason a file could not be opened, in the UI language when the server gave a known code. */
export function loadErrorText(err: LoadErrorInfo, lang: Lang): string {
  const key = `err_${err.code}` as TKey;
  if (err.code && key in dictionaries.en) return translate(lang, key, err.params as Record<string, string | number> | undefined);
  return err.message;
}

/** Open files by path. Errors become actionable toasts. Nothing is plotted
 *  automatically: the user picks the signals. */
export async function openPaths(paths: string[], settings?: Record<string, unknown>, opts: { copy?: boolean } = {}) {
  if (!paths.length) return;
  const st = useApp.getState();
  const lang = st.lang;
  // F19: a file that is already open is read again from the disk instead of being added a second
  // time without a word; "Open another copy" is one click away (the same log with another offset)
  if (!opts.copy) {
    const key = (p: string) => p.replace(/\\/g, "/").toLowerCase();
    const open = new Map(st.runs.filter((r) => r.format !== "derived" && r.path && !r.copy).map((r) => [key(r.path), r]));
    const again = paths.filter((p) => open.has(key(p)));
    if (again.length) {
      paths = paths.filter((p) => !open.has(key(p)));
      const names = again.map((p) => open.get(key(p))!.name).join(", ");
      try {
        for (const p of again) await api.reload(open.get(key(p))!.id);
        const s2 = useApp.getState();
        useApp.setState({ runs: await api.listRuns(), dataVersion: s2.dataVersion + 1 });
        actions.dropStaleRanges();
        s2.toast({ kind: "info", text: translate(lang, "alreadyOpen", { names }),
          action: { label: translate(lang, "openAnotherCopy"), run: () => { openPaths(again, settings, { copy: true }); } } });
      } catch (e) {
        useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
      }
      if (!paths.length) return;
    }
  }
  st.set({ busy: st.busy + 1 });
  const emptyStart = isEmptyStart();                    // T29: the first file(s) into an empty workspace
  try {
    const names = paths.map((p) => p.split(/[\\/]/).pop()).join(", ");
    const res = await runJob<{ opened: any[]; errors: LoadErrorInfo[] }>(
      "open", { paths, settings }, translate(lang, "openingFiles", { names }));
    if (!res) return;   // cancelled
    const runs = await api.listRuns();
    useApp.setState({ runs });
    const firstNew = res.opened.find((o) => o?.id)?.id;
    if (emptyStart && firstNew) offerStart(firstNew);          // in the background: never holds up the open
    refreshRecent();
    for (const err of res.errors) {
      const name = err.path.split(/[\\/]/).pop() || err.path;
      useApp.getState().toast({
        kind: "error",
        text: `${translate(lang, "loadFailed", { name })}: ${loadErrorText(err, lang)}`,
        // import options can help only a text file the loader misread - not a wrong type / empty / binary file
        action: /\.(mat|bin|tlog|ulg)$/i.test(err.path) || ["unsupported", "empty", "binaryText", "wrongExt", "notFound", "unreadable"].includes(err.code ?? "") ? undefined
          : { label: translate(lang, "importOptions"), run: () => useApp.setState({ importPaths: [err.path] }) },
      });
    }
    // D-04: tell what was skipped while reading
    for (const o of res.opened) {
      const rep = o.report || {};
      const parts: string[] = [];
      if (rep.skippedColumns?.length) parts.push(translate(lang, "skippedCols", { n: rep.skippedColumns.length }) + ` (${rep.skippedColumns.slice(0, 3).join(", ")}${rep.skippedColumns.length > 3 ? "…" : ""})`);
      if (rep.textColumns?.length) parts.push(translate(lang, "textColsRead", { n: rep.textColumns.length }) + ` (${rep.textColumns.slice(0, 3).join(", ")}${rep.textColumns.length > 3 ? "…" : ""})`);
      if (rep.tooManyTexts?.length) parts.push(translate(lang, "textColsTooMany", { n: rep.tooManyTexts.length }) + ` (${rep.tooManyTexts.slice(0, 3).join(", ")}${rep.tooManyTexts.length > 3 ? "…" : ""})`);
      if (rep.corruptBytes) parts.push(translate(lang, "corruptBytes", { n: rep.corruptBytes }));
      if (rep.cutOff) parts.push(translate(lang, "cutOff"));
      if (rep.damagedText) parts.push(translate(lang, "damagedText"));
      if (rep.damagedObjects) parts.push(translate(lang, "damagedObjects", { n: rep.damagedObjects }));
      if (rep.noTime) parts.push(translate(lang, "noTimeSamples"));
      if (rep.droppedRows) parts.push(translate(lang, "droppedRows", { n: rep.droppedRows }));
      if (rep.sorted) parts.push(translate(lang, "sortedRows"));
      if (rep.skipped?.length) parts.push(translate(lang, "skippedCols", { n: rep.skipped.length }));
      if (parts.length) useApp.getState().toast({ kind: "info", text: translate(lang, "loadedNote", { name: o.name, details: parts.join(" · ") }) });
      if (rep.rememberedSettings) useApp.getState().toast({
        kind: "info", text: translate(lang, "usedRemembered", { name: o.name }),
        action: { label: translate(lang, "forget"), run: () => { api.forgetImport(o.path).catch(() => {}); } },
      });
    }
  } catch (e) {
    useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
  } finally {
    useApp.setState({ busy: Math.max(0, useApp.getState().busy - 1) });
  }
}

export async function removeRun(id: string) {
  await api.remove(id);
  actions.removeRunSignals(id);
  useApp.setState({ runs: await api.listRuns() });
}

export async function reloadRun(id: string) {
  const run = useApp.getState().runs.find((r) => r.id === id);
  if (run?.copy) { explainCopy(id); return; }
  try {
    await api.reload(id);
    const st = useApp.getState();
    useApp.setState({ runs: await api.listRuns(), dataVersion: st.dataVersion + 1 });
    actions.dropStaleRanges();
    st.toast({ kind: "info", text: translate(st.lang, "reloaded", { name: run?.name ?? "" }) });
  } catch (e) {
    useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
  }
}

/** A file dragged into a browser window was opened from a COPY: say so, and offer the original. */
export function explainCopy(id: string, more = 0) {
  const st = useApp.getState();
  const run = st.runs.find((r) => r.id === id);
  st.toast({
    kind: "info", text: translate(st.lang, "copyExplain", { name: run?.name ?? "" }) + (more > 1 ? " " + translate(st.lang, "copyExplainMore", { n: String(more) }) : ""),
    action: { label: translate(st.lang, "chooseOriginal"), run: async () => {
      const path = await pickPath({ mode: "open", title: translate(st.lang, "chooseOriginal"), exts: DATA_EXTS });
      if (!path) return;
      try {
        await api.replace(id, path);
        useApp.setState({ runs: await api.listRuns(), dataVersion: useApp.getState().dataVersion + 1 });
        actions.dropStaleRanges();
      } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
    } },
  });
}

/** Desktop window: pywebview gives the REAL paths of dropped files (see run.py), so they open
 *  from the original file and refresh / live mode follow edits to it. */
type DropWin = { __svOpenDroppedPaths?: (p: string[]) => void; __svDropHandledAt?: number; pywebview?: unknown };
(window as unknown as DropWin).__svOpenDroppedPaths = (paths: string[]) => {
  (window as unknown as DropWin).__svDropHandledAt = Date.now();
  if (paths.length) openPaths(paths);
};

/** Dropped files are opened from their ORIGINAL whenever possible - there is no advantage in a
 *  copy (refresh and live mode could not follow the original):
 *   1. desktop window: pywebview hands the real paths (run.py);
 *   2. otherwise the server finds the original by name + size + modified time (one exact match only);
 *   3. only what is still not found is uploaded as a copy (marked "copy" in the list). */
export async function openDropped(dropped: File[]) {
  // unsupported types are named to the user, never silently ignored
  const ok = (f: File) => DATA_EXTS.some((e) => f.name.toLowerCase().endsWith(e));
  const skipped = dropped.filter((f) => !ok(f)).map((f) => f.name);
  const files = dropped.filter(ok);
  if (skipped.length) {
    const st = useApp.getState();
    st.toast({ kind: "error", text: translate(st.lang, "droppedUnsupported", { names: skipped.join(", "), supported: SUPPORTED_LABEL }) });
  }
  if (!files.length) return;
  const w = window as unknown as DropWin;
  if (w.pywebview) {
    const t0 = Date.now();
    await new Promise((r) => setTimeout(r, 900));
    if ((w.__svDropHandledAt ?? 0) >= t0 - 100) return;      // opened from the real paths
  }
  let located: (string | null)[] = files.map(() => null);
  try {
    located = (await api.locate(files.map((f) => ({ name: f.name, size: f.size, mtime: f.lastModified / 1000 })))).paths;
  } catch { /* fall back to copies */ }
  const originals = located.filter((p): p is string => !!p);
  const rest = files.filter((_, i) => !located[i]);
  if (originals.length) await openPaths(originals);
  if (rest.length) {
    const { paths } = await api.upload(rest);
    await openPaths(paths);
    // tell the user WHY a copy was opened (the original was not found, or exists in two places)
    const copies = useApp.getState().runs.filter((r) => paths.includes(r.path));
    if (copies.length) explainCopy(copies[0].id, copies.length > 1 ? copies.length : 0);
  }
}

/* ------------------------------------------------------------------ sessions */

import { pickPath } from "./store";
import type { Workspace } from "./store";

/** Everything needed to rebuild the workspace: layout, files (paths + import
 *  settings, not data), derived signals as formulas, and UI preferences. */
export function currentState() {
  const st = useApp.getState();
  const drv = st.runs.find((r) => r.format === "derived");
  return {
    ws: st.ws,
    derived: (drv?.signals ?? []).map((s) => ({ name: s.name, op: s.op, sources: s.sources, params: s.params })),
    runs: st.runs.filter((r) => r.format !== "derived").map((r) => ({
      id: r.id, path: r.path, name: r.name, importSettings: r.importSettings, timeOffset: r.timeOffset,
    })),
    ui: { theme: st.theme, lang: st.lang, uiScale: st.uiScale, linkRuns: st.linkRuns, zoomMode: st.zoomMode,
      liveAutoStop: st.liveAutoStop, liveNewFiles: st.liveNewFiles, geoBase: st.geoBase,
      playMode: st.playMode, playSpeed: st.playSpeed, windowSec: st.windowSec, timelineOpen: st.timelineOpen },
    transforms: Object.fromEntries(st.runs.flatMap((r) => r.signals.filter((x) => x.transform).map((x) => [x.id, x.transform]))),
  };
}

/** Re-open the files of a saved state (keeping their ids), recreate derived
 *  signals from formulas, and drop references to anything that is missing. */
export async function applyState(state: any, opts: { announce?: boolean } = {}) {
  if (!state?.ws) return;
  const st = useApp.getState();
  st.set({ busy: st.busy + 1 });
  try {
    if (state.ui?.theme) useApp.setState({ theme: state.ui.theme });
    if (state.ui?.lang) useApp.setState({ lang: state.ui.lang });
    if ([1, 1.12, 1.25].includes(state.ui?.uiScale)) useApp.setState({ uiScale: state.ui.uiScale });
    if (typeof state.ui?.linkRuns === "boolean") useApp.setState({ linkRuns: state.ui.linkRuns });
    if (["x", "y", "xy"].includes(state.ui?.zoomMode)) useApp.setState({ zoomMode: state.ui.zoomMode });
    // the timeline (sessions saved before it have none of these: the defaults stay)
    if (["cursor", "draw", "window"].includes(state.ui?.playMode)) useApp.setState({ playMode: state.ui.playMode });
    if (typeof state.ui?.playSpeed === "number" && state.ui.playSpeed > 0 && state.ui.playSpeed <= 1000) useApp.setState({ playSpeed: state.ui.playSpeed });
    if (typeof state.ui?.windowSec === "number" && state.ui.windowSec > 0) useApp.setState({ windowSec: state.ui.windowSec });
    if (typeof state.ui?.timelineOpen === "boolean") useApp.setState({ timelineOpen: state.ui.timelineOpen });
    if (state.ui && "liveAutoStop" in state.ui && (state.ui.liveAutoStop === null || typeof state.ui.liveAutoStop === "number")) useApp.setState({ liveAutoStop: state.ui.liveAutoStop });
    if (["ask", "auto", "ignore"].includes(state.ui?.liveNewFiles)) useApp.setState({ liveNewFiles: state.ui.liveNewFiles });
    if (["auto", "osm", "esri", "light", "dark", "satellite", "topo", "offline"].includes(state.ui?.geoBase)) useApp.setState({ geoBase: state.ui.geoBase });
    const res = state.runs?.length ? await api.restore(state.runs) : { restored: [], missing: [] };
    const keep = new Set<string>(res.restored.map((r) => r.id));
    // changes made on signals themselves (before derived signals, which may use them)
    if (state.transforms && Object.keys(state.transforms).length) {
      const specs = Object.fromEntries(Object.entries(state.transforms).filter(([id]) => keep.has(id.split("/")[0])));
      if (Object.keys(specs).length) await api.setTransformSpecs(specs as never).catch(() => {});
    }
    let derivedFailed = 0;
    if (state.derived?.length) {
      const d = await api.restoreDerived(state.derived);
      derivedFailed = d.failed.length;
      keep.add("derived");
    }
    const ws: Workspace = structuredClone(state.ws);   // the original stays intact for "Locate…"
    for (const tb of ws.tabs) for (const p of tb.plots) {
      p.signals = p.signals.filter((s) => keep.has(s.sig.split("/")[0]));
      if (p.xSignal && !keep.has(p.xSignal.split("/")[0])) p.xSignal = null;
    }
    if (!ws.tabs.length) return;
    useApp.setState({ ws, past: [], future: [], runs: await api.listRuns(), ranges: {}, yRanges: {}, selected: null,
      dataVersion: useApp.getState().dataVersion + 1 });
    const L = useApp.getState().lang;
    if (opts.announce !== false && res.restored.length) useApp.getState().toast({ kind: "info", text: translate(L, "restored") });
    if (res.missing.length) useApp.getState().toast({
      kind: "error", text: translate(L, "missingFiles", { n: res.missing.length }),
      // E-02: point to the files' new location; the saved layout is then applied again
      action: { label: translate(L, "locateFile"), run: async () => {
        const runs = (state.runs as any[]).map((r) => ({ ...r }));
        for (const m of res.missing as any[]) {
          const name = String(m.path || "").split(/[\\/]/).pop() || m.name;
          const p = await pickPath({ mode: "open", title: translate(L, "locateTitle", { name }), exts: DATA_EXTS });
          if (!p) continue;
          const r = runs.find((x) => x.id === m.id);
          if (r) r.path = p;
        }
        await applyState({ ...state, runs }, { announce: true });
      } },
    });
    if (derivedFailed) useApp.getState().toast({ kind: "error", text: translate(L, "derivedFailed", { n: derivedFailed }) });
    if (state.skippedDerived) useApp.getState().toast({ kind: "info", text: translate(L, "v2DerivedSkipped", { n: state.skippedDerived }) });
  } finally {
    useApp.setState({ busy: Math.max(0, useApp.getState().busy - 1) });
  }
}

export async function saveSession() {
  const L = useApp.getState().lang;
  const path = await pickPath({ mode: "save", title: translate(L, "saveSession"), exts: [".svsession"], defaultName: "session.svsession" });
  if (!path) return;
  try {
    const r = await api.saveSession(path, currentState());
    useApp.getState().toast({ kind: "info", text: translate(L, "savedTo", { path: r.path }) });
  } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
}

export async function openSession() {
  const L = useApp.getState().lang;
  const path = await pickPath({ mode: "open", title: translate(L, "openSession"), exts: [".svsession", ".json"] });
  if (!path) return;
  try {
    const r = await api.loadSession(path);
    await applyState(r.state, { announce: false });
    useApp.getState().toast({ kind: "info", text: translate(L, r.converted ? "sessionConverted" : "sessionOpened") });
  } catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
}


/** Start over: close every file, delete derived signals, one empty tab. Files on disk are untouched. */
export async function clearEverything() {
  const st = useApp.getState();
  const { confirmAsk } = await import("./components/Overlays");
  if (!(await confirmAsk(translate(st.lang, "clearEverything"), translate(st.lang, "clearEverythingAsk")))) return;
  for (const r of st.runs) {
    if (r.format === "derived") { for (const s of r.signals) await api.deleteDerived(s.name).catch(() => {}); }
    else await api.remove(r.id).catch(() => {});
  }
  const tabId = `t${Date.now().toString(36)}`;
  useApp.setState({
    ws: { tabs: [{ id: tabId, name: "", rows: 1, cols: 1, plots: [{ id: `p${Date.now().toString(36)}`, title: "", signals: [] }], active: 0, linkX: true }], activeTab: tabId },
    past: [], future: [], runs: await api.listRuns(), ranges: {}, yRanges: {}, zoomHistory: {}, selected: null, multi: [], preview: null,
    cursor: { on: false, dual: false, t1: null, t2: null }, playing: false, cvals: {}, yExtents: {},
  });
  useApp.getState().toast({ kind: "info", text: translate(st.lang, "cleared") });
}


/** Same work, new runs: the current workspace, or a saved session, re-opened with new input files. */
export async function startRetarget(sessionPath?: string) {
  const st = useApp.getState();
  if (!sessionPath) {
    if (!st.runs.some((r) => r.format !== "derived")) return;
    useApp.setState({ retarget: { state: currentState(), title: "", fromCurrent: true } });
    return;
  }
  try {
    const r = await api.loadSession(sessionPath);
    useApp.setState({ retarget: { state: r.state, title: sessionPath.split(/[\\/]/).pop() || "", fromCurrent: false } });
  } catch (e) { st.toast({ kind: "error", text: String((e as Error).message) }); }
}

export async function pickSessionForRetarget() {
  const st = useApp.getState();
  const path = await pickPath({ mode: "open", title: translate(st.lang, "retargetPickSession"), exts: [".svsession", ".json"] });
  if (path) await startRetarget(path);
}

/* ------------------------------------------------------------------ recent files */

/** Reload the recent list from the server (after files were opened, or when a dialog opens). */
export async function refreshRecent() {
  try { useApp.setState({ recent: (await api.recent()).items }); } catch { /* keep what we have */ }
}

/** Recent data files that are not open now (newest first). Missing ones are kept, marked exists=false. */
export function recentToOpen(limit = 8) {
  const st = useApp.getState();
  const open = new Set(st.runs.map((r) => r.path.toLowerCase()));
  return st.recent.filter((x) => x.kind === "file" && !open.has(x.path.toLowerCase())).slice(0, limit);
}
