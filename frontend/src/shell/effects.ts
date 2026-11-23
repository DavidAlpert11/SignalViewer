/* The app's background work, one hook each (moved out of App.tsx so that the App is only its layout):
   restore + autosave, the server ping, playback, live follow / polling, data pushed from Python, the
   files dropped on the window, the named conditions and the flight-log data. Each hook is mounted once,
   by App. */
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { evaluateAll } from "../conditions";
import { applyState, currentState, explainCopy, openDropped, openPaths, openSession } from "../files";
import { translate } from "../i18n";
import { handleNewFiles, stopLive } from "../live";
import { ensureLogs } from "../logs";
import { linkResume } from "../link";
import { mavlinkResume } from "../mavlink";
import { actions, activeTab, rangeKey, recordingExtent, useApp } from "../store";
import { detectSameFlight } from "../sync";

/** theme + language on <html> (plots stay left-to-right in Hebrew) */
export function useDocumentLook() {
  const theme = useApp((s) => s.theme);
  const lang = useApp((s) => s.lang);
  const uiScale = useApp((s) => s.uiScale);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "he" ? "rtl" : "ltr";
    document.documentElement.style.setProperty("--ui-scale", String(uiScale));
  }, [theme, lang, uiScale]);
}

/** a MAVLink link / a raw link still running after a reload */
export function useLinksResume() {
  useEffect(() => { mavlinkResume(); linkResume(); }, []);
}

/** named conditions: looked for again when they, the open files or their data change */
export function useConditions() {
  const condKey = useApp((s) => JSON.stringify((s.ws.conditions ?? []).map((c) => [c.id, c.text, c.exit, c.minDur, c.mergeGap, c.combine])));
  const condRuns = useApp((s) => s.runs.map((r) => r.id).join("|"));
  const condData = useApp((s) => s.dataVersion);
  useEffect(() => { void evaluateAll(); }, [condKey, condRuns, condData]);
}

/** tell the local server a tab is open (in browser mode it stops when none is) */
export function useServerPing() {
  useEffect(() => {
    const ping = () => { fetch("/api/ping", { method: "POST" }).catch(() => {}); };
    ping();
    const h = window.setInterval(ping, 5000);
    // the tab is going away: the server (browser mode) may stop soon. Without this it had to judge
    // by missing pings alone - and a tab in the background pings only about once a minute.
    const bye = () => { try { navigator.sendBeacon("/api/bye"); } catch { /* best effort */ } };
    window.addEventListener("pagehide", bye);
    // opened in the browser although the app has its own window: say why, once
    api.windowNote().then((n) => {
      if (!n.browserReason || sessionStorage.getItem("sv-window-note")) return;
      sessionStorage.setItem("sv-window-note", "1");
      const st = useApp.getState();
      st.toast({ kind: "info", text: translate(st.lang, "browserFallback", { reason: n.browserReason }), ms: 30000 });
    }).catch(() => {});
    return () => { window.clearInterval(h); window.removeEventListener("pagehide", bye); };
  }, []);
}

/** Restore the last workspace once, then autosave it (debounced). Returns whether the restore is done:
 *  files sent from outside wait for it (it would replace them). */
export function useRestoreAndAutosave(): React.MutableRefObject<boolean> {
  const restored = useRef(false);
  useEffect(() => {
    (async () => {
      try {
        const { state, damaged } = await api.getAutosave();
        if (damaged) useApp.getState().toast({ kind: "error", text: translate(useApp.getState().lang, "autosaveDamaged", { path: damaged }), ms: 15000 });
        if (state?.ws) await applyState(state);
        else useApp.setState({ runs: await api.listRuns() });
      } finally {
        restored.current = true;
      }
    })();
  }, []);
  const ws = useApp((s) => s.ws);
  const runs = useApp((s) => s.runs);
  const theme = useApp((s) => s.theme);
  const lang = useApp((s) => s.lang);
  const uiScale = useApp((s) => s.uiScale);
  const liveAutoStop = useApp((s) => s.liveAutoStop);
  const liveNewFiles = useApp((s) => s.liveNewFiles);
  const logMarkers = useApp((s) => s.logMarkers);
  const geoBase = useApp((s) => s.geoBase);
  const geoBorders = useApp((s) => s.geoBorders);
  useEffect(() => {
    if (!restored.current) return;
    const h = window.setTimeout(() => { api.putAutosave(currentState()).catch(() => {}); }, 800);
    return () => window.clearTimeout(h);
  }, [ws, runs, theme, lang, uiScale, liveAutoStop, liveNewFiles, logMarkers, geoBase, geoBorders]);
  return restored;
}

/** null: no open file has a flight log; else the number of logged errors */
export function useLogErrors(): number | null {
  return useApp((s) => {
    const lr = s.runs.filter((r) => r.log);
    return lr.length ? lr.reduce((n, r) => n + (r.log?.errors ?? 0), 0) : null;
  });
}

/** an autopilot log and a telemetry log of the same flight, not aligned: offer to align them; flight-log data
 *  fetched only for files that have it, when the panel or the plot markers need it */
export function useLogData(logErrors: number | null, hasFiles: boolean) {
  const runs = useApp((s) => s.runs);
  const panel = useApp((s) => s.panel);
  const logMarkers = useApp((s) => s.logMarkers);
  useEffect(() => { if (runs.some((r) => r.format === "tlog")) detectSameFlight(); }, [runs]);
  useEffect(() => {
    if (logErrors !== null && (panel === "log" || logMarkers !== "off")) ensureLogs();
    if (!hasFiles && panel === "log") useApp.setState({ panel: "data" });     // D7: Checks for any file
  }, [runs, panel, logMarkers, logErrors, hasFiles]);
}

/** a file opened (from the start page, Ctrl+O, a drop): the start page gives way to it */
export function useStartGivesWay() {
  const runIds = useApp((s) => s.runs.map((r) => r.id).join("|"));
  useEffect(() => { if (useApp.getState().startOpen) useApp.setState({ startOpen: false }); }, [runIds]);
}

/** playback (the timeline): the time runs through the whole recording at `playSpeed` × real time; a zoomed
 *  time plot follows it */
export function usePlayback() {
  const playing = useApp((s) => s.playing);
  useEffect(() => {
    if (!playing) return;
    let raf = 0, last = performance.now();
    const step = (now: number) => {
      const st = useApp.getState();
      const r = recordingExtent(st.runs);
      if (!r || !st.cursor.on || st.cursor.t1 === null) { useApp.setState({ playing: false }); return; }
      const t = st.cursor.t1 + st.playSpeed * ((now - last) / 1000);
      last = now;
      if (t >= r[1]) { useApp.setState({ cursor: { ...st.cursor, t1: r[1] }, playing: false }); actions.followTime(r[1]); return; }
      const tt = Math.max(t, r[0]);
      useApp.setState({ cursor: { ...st.cursor, t1: tt } });
      actions.followTime(tt);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing]);
}

/** live mode "follow": keep showing the last N seconds as data arrives */
export function useLiveFollow() {
  const streaming = useApp((s) => s.streaming);
  const follow = useApp((s) => s.follow);
  const runs = useApp((s) => s.runs);
  useEffect(() => {
    if (!streaming || !follow) return;
    const end = Math.max(...runs.filter((r) => r.format !== "derived").map((r) => r.end));
    if (!Number.isFinite(end)) return;
    const tb = activeTab(useApp.getState().ws);
    tb.plots.forEach((p) => actions.setRange(rangeKey(tb, p), [end - follow, end], { history: false }));
  }, [streaming, follow, runs]);
}

/** T39: data sent from Python (signalviewer_push.show): refresh, and put a NEW run in the active plot.
 *  T54: files opened from outside (Open with, `SignalViewer file.bin`, a second start) come the same way */
export function usePushEvents(restored: React.MutableRefObject<boolean>) {
  useEffect(() => {
    let since = 0;
    // the first ask: data sent while the page loaded counts, older data (before a reload) is not
    // plotted again. One ask at a time: a late answer (the server busy with a big file) overtaken
    // by the next one handled the same events twice.
    let first = true;
    let asking = false;
    const h = window.setInterval(async () => {
      if (asking) return;
      asking = true;
      try {
        // files to open are taken once the last work is restored (it would replace them); the server
        // hands each out once, so a reload does not open them again
        const r = await api.pushEvents(since, restored.current);
        const fresh = r.events.filter((e) => e.kind === "open" || !first || e.age < 10);
        first = false;
        since = r.seq;
        const opens = fresh.filter((e) => e.kind === "open");
        for (const e of opens) {
          const paths = e.paths ?? [];
          const sessions = paths.filter((p) => /\.svsession$/i.test(p));
          for (const p of sessions) await openSession(p);
          const files = paths.filter((p) => !sessions.includes(p));
          if (files.length) await openPaths(files);
        }
        const pushed = r.events.filter((e) => e.kind !== "open");
        if (!pushed.length) return;
        const runs = await api.listRuns();
        const st = useApp.getState();
        useApp.setState({ runs, dataVersion: st.dataVersion + 1 });
        for (const e of fresh) {
          if (e.kind === "open" || !e.new) continue;
          const run = runs.find((x) => x.id === e.run);
          if (!run) continue;
          if (e.plot) run.signals.slice(0, 8).forEach((s) => actions.addSignal(s.id));
          st.toast({ kind: "info", text: translate(st.lang, "pushReceived", { name: e.name ?? "", n: run.signals.length }) });
        }
      } catch { /* server busy; next tick */ } finally { asking = false; }
    }, 1000);
    return () => window.clearInterval(h);
  }, [restored]);
}

/** live streaming: poll for appended rows */
export function useLivePoll() {
  const streaming = useApp((s) => s.streaming);
  useEffect(() => {
    if (!streaming) return;
    const st0 = useApp.getState();
    // files opened from a dragged-in COPY cannot follow the original: say so right away
    st0.runs.filter((r) => r.copy).forEach((r) => explainCopy(r.id));
    const reported = new Map<string, string>();
    let polling = false;               // a poll still running (a big file read again) is not overtaken
    const h = window.setInterval(async () => {
      if (polling) return;
      polling = true;
      try {
        const r = await api.poll();
        if (!useApp.getState().streaming) return;
        // a file still being written (read when it settles) is activity too: live mode is not idle
        if (r.writing?.length) useApp.setState({ liveLastData: Date.now() });
        if (r.changed.length && r.runs) {
          const st = useApp.getState();
          const before = st.runs;
          useApp.setState({ runs: r.runs, dataVersion: st.dataVersion + 1, liveLastData: Date.now() });
          actions.pinTimeToEnd(before);        // a time at the end stays at the newest data
        }
        useApp.setState({ activity: r.activity ?? {}, liveIdle: (Date.now() - useApp.getState().liveLastData) / 1000 });
        if (r.newFiles?.length) handleNewFiles(r.newFiles);
        // stop by itself after the chosen time without new data in any file
        const st = useApp.getState();
        if (st.liveAutoStop && Date.now() - st.liveLastData > st.liveAutoStop * 1000) { stopLive("idle"); return; }
        // a file that cannot be read now (e.g. locked while another program saves it): tell once
        for (const [rid, msg] of Object.entries(r.errors ?? {})) {
          if (reported.get(rid) === msg) continue;
          reported.set(rid, msg);
          const st = useApp.getState();
          st.toast({ kind: "error", text: translate(st.lang, "liveReadError", { name: st.runs.find((x) => x.id === rid)?.name ?? rid, msg }) });
        }
        for (const rid of Array.from(reported.keys())) if (!(r.errors ?? {})[rid]) reported.delete(rid);
      } catch { /* server busy; next tick */ } finally { polling = false; }
    }, 1000);
    return () => window.clearInterval(h);
  }, [streaming]);
}

/** drag & drop files from the OS anywhere in the window; true while files are dragged over it */
export function useFileDrop(): boolean {
  const [dropping, setDropping] = useState(false);
  useEffect(() => {
    let depth = 0;
    const isFiles = (e: DragEvent) => !!e.dataTransfer?.types.includes("Files");
    const enter = (e: DragEvent) => { if (isFiles(e)) { depth++; setDropping(true); } };
    const leave = (e: DragEvent) => { if (isFiles(e) && --depth <= 0) { depth = 0; setDropping(false); } };
    const over = (e: DragEvent) => { if (isFiles(e)) e.preventDefault(); };
    const drop = (e: DragEvent) => {
      if (!isFiles(e)) return;
      e.preventDefault(); depth = 0; setDropping(false);
      const files = Array.from(e.dataTransfer!.files);
      // pywebview / Electron expose a real path: open in place instead of copying
      const withPath = files.map((f) => (f as File & { path?: string }).path).filter(Boolean) as string[];
      if (withPath.length === files.length) openPaths(withPath); else openDropped(files);
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter); window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", over); window.removeEventListener("drop", drop);
    };
  }, []);
  return dropping;
}
