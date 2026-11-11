import { countRender } from "./perf";
import OverviewStrip from "./components/OverviewStrip";
import TabBand from "./components/TabBand";
import { evaluateAll } from "./conditions";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { lazyPreload, preloadAll } from "./lazyPreload";
import PanelResizer from "./components/PanelResizer";
import { usePanelWidth } from "./components/panelWidth";
import PreviewPlots from "./components/PreviewPlots";
import StartCard from "./components/StartCard";
import { mavlinkResume } from "./mavlink";
import Timeline from "./components/Timeline";
const SweepsScreen = lazyPreload(() => import("./components/sweeps/SweepsArea"));
const SweepsStatus = lazyPreload(() => import("./components/sweeps/SweepsStatus"));
const TemplateLibrary = lazyPreload(() => import("./components/TemplateLibrary"));
const ObjectDialog = lazyPreload(() => import("./components/ObjectDialog"));
const CompareObjectsDialog = lazyPreload(() => import("./components/CompareObjectsDialog"));
const CompareSimilarDialog = lazyPreload(() => import("./components/CompareSimilarDialog"));
const PlaceOnMapDialog = lazyPreload(() => import("./components/PlaceOnMapDialog"));
const TransformDialog = lazyPreload(() => import("./components/TransformDialog"));
const RetargetDialog = lazyPreload(() => import("./components/RetargetDialog"));
const SameWorkDialog = lazyPreload(() => import("./components/SameWorkDialog"));
const TimeAxisDialog = lazyPreload(() => import("./components/TimeAxisDialog"));
const StyleLinesDialog = lazyPreload(() => import("./components/StyleLinesDialog"));
const QualityDialog = lazyPreload(() => import("./components/QualityDialog"));
const RunsMatrix = lazyPreload(() => import("./components/RunsMatrix"));
import { api } from "./api";
import { handleNewFiles, stopLive } from "./live";
import { ensureLogs } from "./logs";
import { detectSameFlight } from "./sync";
import { actions, activeTab, rangeKey, recordingExtent, useApp } from "./store";
import { translate, useT } from "./i18n";
import { Icon } from "./icons";
import { applyState, currentState, explainCopy, openDropped, openPaths, openSession } from "./files";
import TopBar, { RecordingsBar } from "./components/TopBar";
import type { AreaId } from "./areas";
import StageBar from "./components/StageBar";
import DataPanel from "./components/DataPanel";
const AnalysisPanel = lazyPreload(() => import("./components/AnalysisPanel"));
const FleetArea = lazyPreload(() => import("./components/FleetPanel"));
const InvestigatePanel = lazyPreload(() => import("./components/InvestigatePanel"));
const ComparePanel = lazyPreload(() => import("./components/ComparePanel"));
const ReportPanel = lazyPreload(() => import("./components/ReportPanel"));
const LogPanel = lazyPreload(() => import("./components/LogPanel"));
const SyncDialog = lazyPreload(() => import("./components/SyncDialog"));
import Inspector from "./components/Inspector";
import StatusBar from "./components/StatusBar";
import CommandPalette from "./components/CommandPalette";
import FileBrowser from "./components/FileBrowser";
const ImportDialog = lazyPreload(() => import("./components/ImportDialog"));
import Toasts from "./components/Toasts";
import Jobs from "./components/Jobs";
const Help = lazyPreload(() => import("./components/Help"));
const GuideDialog = lazyPreload(() => import("./components/GuideDialog"));
const SettingsDialog = lazyPreload(() => import("./components/SettingsDialog"));
import { AxisDialog, ContextMenu, ModalFocus, PromptDialog } from "./components/Overlays";
import TabChoiceDialog from "./components/TabChoice";
import Welcome from "./components/Welcome";
import PlotGrid from "./components/PlotGrid";
import { RAIL, RAIL_W } from "./components/rail";
import { useShortcuts } from "./shortcuts";
const ReportPreview = lazyPreload(() => import("./components/ReportPreview"));
const CompareTable = lazyPreload(() => import("./components/CompareTable"));

/* resizable side panels: components/PanelResizer.tsx */
const MIN_STAGE = 380;

export default function App() {
  countRender("App");
  useEffect(() => { preloadAll(); }, []);
  useEffect(() => { mavlinkResume(); }, []);
  // named conditions: looked for again when they, the open files or their data change
  const condKey = useApp((s) => JSON.stringify((s.ws.conditions ?? []).map((c) => [c.id, c.text, c.exit, c.minDur, c.mergeGap, c.combine])));
  const condRuns = useApp((s) => s.runs.map((r) => r.id).join("|"));
  const condData = useApp((s) => s.dataVersion);
  useEffect(() => { void evaluateAll(); }, [condKey, condRuns, condData]);           // a MAVLink link still running after a reload           // panels / dialogs: ready before their first open
  const t = useT();
  const theme = useApp((s) => s.theme);
  const lang = useApp((s) => s.lang);
  const uiScale = useApp((s) => s.uiScale);
  const importPaths = useApp((s) => s.importPaths);
  const helpOpen = useApp((s) => s.helpOpen);
  const guideOpen = useApp((s) => s.guideOpen);
  const settingsOpen = useApp((s) => s.settingsOpen);
  const previewHtml = useApp((s) => s.reportPreviewHtml);
  const compareTable = useApp((s) => !!s.compareTable);
  const templatesOpen = useApp((s) => s.templatesOpen);
  const objectDialog = useApp((s) => s.objectDialog);
  const compareDialog = useApp((s) => s.compareDialog);
  const similarDialog = useApp((s) => s.similarDialog);
  const placeDialog = useApp((s) => s.placeDialog);
  const transformOpen = useApp((s) => !!s.transformTargets);
  const retargetOpen = useApp((s) => !!s.retarget);
  const sameWorkOpen = useApp((s) => !!s.sameWorkFor);
  const timeAxisOpen = useApp((s) => !!s.timeAxisFor);
  const styleOpen = useApp((s) => !!s.styleDialog);
  const qualityOpen = useApp((s) => !!s.qualityFor);
  const matrixOpen = useApp((s) => s.matrixOpen);
  const panel = useApp((s) => s.panel);
  const inspectorOpen = useApp((s) => s.inspectorOpen);
  const area = useApp((s) => s.area);
  const runs = useApp((s) => s.runs);
  const ws = useApp((s) => s.ws);
  const streaming = useApp((s) => s.streaming);
  const zoomMode = useApp((s) => s.zoomMode);
  const logMarkers = useApp((s) => s.logMarkers);
  const syncFor = useApp((s) => s.syncFor);
  const geoBase = useApp((s) => s.geoBase);
  const geoBorders = useApp((s) => s.geoBorders);
  // null: no open file has a flight log (no Log button at all); else the number of logged errors
  const logErrors = useMemo(() => {
    const lr = runs.filter((r) => r.log);
    return lr.length ? lr.reduce((n, r) => n + (r.log?.errors ?? 0), 0) : null;
  }, [runs]);
  const liveAutoStop = useApp((s) => s.liveAutoStop);
  const liveNewFiles = useApp((s) => s.liveNewFiles);
  const [dropping, setDropping] = useState(false);
  const [sideW, setSideW] = usePanelWidth("side", 280);          // files / analysis / ... panel
  const [inspW, setInspW] = usePanelWidth("inspector", 320);     // inspector on the other side
  const restored = useRef(false);

  /* theme + language on <html> (plots stay left-to-right in Hebrew) */
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "he" ? "rtl" : "ltr";
    document.documentElement.style.setProperty("--ui-scale", String(uiScale));
  }, [theme, lang, uiScale]);

  /* tell the local server a tab is open (in browser mode it stops when none is) */
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

  /* restore the last workspace once */
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

  /* autosave (debounced) */
  useEffect(() => {
    if (!restored.current) return;
    const h = window.setTimeout(() => { api.putAutosave(currentState()).catch(() => {}); }, 800);
    return () => window.clearTimeout(h);
  }, [ws, runs, theme, lang, uiScale, zoomMode, liveAutoStop, liveNewFiles, logMarkers, geoBase, geoBorders]);
  // an autopilot log and a telemetry log of the same flight, not aligned: offer to align them
  useEffect(() => { if (runs.some((r) => r.format === "tlog")) detectSameFlight(); }, [runs]);
  // flight-log data: fetched only for files that have it, when the panel or the plot markers need it
  useEffect(() => {
    if (logErrors !== null && (panel === "log" || logMarkers !== "off")) ensureLogs();
    if (logErrors === null && panel === "log") useApp.setState({ panel: "data" });
  }, [runs, panel, logMarkers, logErrors]);


  /* playback (the timeline): the time runs through the whole recording at `playSpeed` × real time;
     a zoomed time plot follows it */
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

  /* live mode "follow": keep showing the last N seconds as data arrives */
  const follow = useApp((s) => s.follow);
  useEffect(() => {
    if (!streaming || !follow) return;
    const end = Math.max(...runs.filter((r) => r.format !== "derived").map((r) => r.end));
    if (!Number.isFinite(end)) return;
    const tb = activeTab(useApp.getState().ws);
    tb.plots.forEach((p) => actions.setRange(rangeKey(tb, p), [end - follow, end], { history: false }));
  }, [streaming, follow, runs]);

  /* T39: data sent from Python (signalviewer_push.show): refresh, and put a NEW run in the active plot.
     T54: files opened from outside (Open with, `SignalViewer file.bin`, a second start) come the same way */
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
  }, []);

  /* live streaming: poll for appended rows */
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

  useShortcuts();                       // A3: the keyboard (shortcuts.ts)

  /* drag & drop files from the OS anywhere in the window */
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

  const cols = [RAIL_W, panel ? sideW : 0, "1fr", inspectorOpen ? inspW : 0].map((c) => (typeof c === "number" ? `${c}px` : c)).join(" ");

  return (
    <div className="app">
      <TopBar />
      {/* the area on screen: its bar, then its body (areas.ts). A Record over AreaId, so a new area
          does not compile until it has a view here */}
      {({ recordings: <>
      <RecordingsBar />
      <div className="main" style={{ gridTemplateColumns: cols }}>
        {panel && <PanelResizer label={t("resizePanel")} style={{ insetInlineStart: RAIL_W + sideW - 3 }} width={sideW} setWidth={setSideW}
          grow={+1} def={280} max={() => window.innerWidth - RAIL_W - (inspectorOpen ? inspW : 0) - MIN_STAGE} />}
        {inspectorOpen && <PanelResizer label={t("resizePanel")} style={{ insetInlineEnd: inspW - 3 }} width={inspW} setWidth={setInspW}
          grow={-1} def={320} max={() => window.innerWidth - RAIL_W - (panel ? sideW : 0) - MIN_STAGE} />}
        <nav className="rail" aria-label="Panels">
          {RAIL.map((r) => {
            const I = Icon[r.icon];
            // U9: the Log tool stays in its place, disabled while no flight log is open (it used to vanish)
            const off = r.id === "log" && logErrors === null;
            return (
              <button key={r.id} className={`${panel === r.id ? "on" : ""}${r.id === "log" ? " rail-log" : ""}`} title={off ? t("railLogNone") : t(r.key)}
                aria-label={t(r.key)} aria-pressed={panel === r.id} disabled={off}
                onClick={() => useApp.setState({ panel: panel === r.id ? null : r.id })}><I /><span className="rail-label" aria-hidden="true">{t(r.short)}</span>
                {r.id === "log" && !!logErrors && <span className="rail-badge" aria-label={t("logErrorsN", { n: logErrors })} />}
              </button>
            );
          })}
          <span className="spacer" />
        </nav>
        <Suspense fallback={<aside className="side" />}>
          {panel === "data" ? <DataPanel /> : panel === "analysis" ? <AnalysisPanel /> : panel === "compare" ? <ComparePanel />
            : panel === "report" ? <ReportPanel /> : panel === "log" && logErrors !== null ? <LogPanel />
            : panel === "investigate" ? <InvestigatePanel /> : <div />}
        </Suspense>
        <main className="stage">
          <StageBar />
          {runs.length > 0 && <OverviewStrip />}
          {runs.length > 0 && <TabBand />}
          {!runs.length ? <div className="stage-body"><Welcome /></div> : (
            <PlotGrid />
          )}
          {runs.length > 0 && <PreviewPlots />}
          {/* one place for every notice - the start card and the messages - above the timeline,
              instead of a card over the plots and messages over the timeline's controls */}
          <div className="notices"><StartCard /><Toasts /></div>
          {runs.length > 0 && <Timeline />}
        </main>
        {inspectorOpen ? <Inspector /> : <div />}
      </div>
      </>,
      sweeps: <Suspense fallback={<><div className="areabar" /><div /></>}><SweepsScreen /></Suspense>,
      fleet: <Suspense fallback={<><div className="areabar" /><div /></>}><FleetArea /></Suspense>,
      } satisfies Record<AreaId, React.ReactNode>)[area]}
      {area === "sweeps" ? <Suspense fallback={<footer className="status" />}><SweepsStatus /></Suspense>
        : area === "recordings" ? <StatusBar /> : <footer className="status" />}
      <CursorValues />
      <CommandPalette />
      <FileBrowser />
      <Suspense fallback={null}>
        {importPaths && <ImportDialog />}
        {helpOpen && <Help />}
        {guideOpen && <GuideDialog />}
        {settingsOpen && <SettingsDialog />}
        {previewHtml && <ReportPreview />}
        {compareTable && <CompareTable />}
        {templatesOpen && <TemplateLibrary />}
        {objectDialog && <ObjectDialog key={`${objectDialog.plotId}/${objectDialog.objectId ?? "new"}`} />}
        {compareDialog && <CompareObjectsDialog key={compareDialog.plotId} />}
        {similarDialog && <CompareSimilarDialog key={`${similarDialog.runId}/${similarDialog.ids.join(",")}`} />}
        {placeDialog && <PlaceOnMapDialog key={placeDialog} />}
        {syncFor && <SyncDialog />}
        {transformOpen && <TransformDialog />}
        {retargetOpen && <RetargetDialog />}
        {sameWorkOpen && <SameWorkDialog />}
        {timeAxisOpen && <TimeAxisDialog />}
        {styleOpen && <StyleLinesDialog />}
        {qualityOpen && <QualityDialog />}
        {matrixOpen && <RunsMatrix />}
      </Suspense>
      <Jobs />
      <ContextMenu />
      <ModalFocus />
      <PromptDialog />
      <TabChoiceDialog />
      <AxisDialog />
      {dropping && <div className="drop-overlay"><div>{t("dropOverlay")}</div></div>}
    </div>
  );
}

/* The values at the cursor, fetched as it moves (N6: its own component - the App, and so every panel
   under it, re-rendered on every frame of playback while this lived in it). */
function CursorValues() {
  const tab = useApp((s) => activeTab(s.ws));
  const cursor = useApp((s) => s.cursor);
  const dataVersion = useApp((s) => s.dataVersion);
  /* cursor values: full-resolution interpolation on the server.
     A signal with its own time offset is read at (cursor time - offset). */
  const sigOffsets = new Map<string, number>();
  tab.plots.forEach((p) => {
    p.signals.forEach((s) => { if (!sigOffsets.has(s.sig)) sigOffsets.set(s.sig, s.tOffset ?? 0); });
    if ((p.mode === "xy" || p.mode === "geo") && p.xSignal && !sigOffsets.has(p.xSignal)) sigOffsets.set(p.xSignal, 0);
  });
  const sigKey = Array.from(sigOffsets, ([k, o]) => `${k}@${o}`).join("|");
  /* One request at a time; when it returns and the cursor has moved meanwhile, one more for where it
     is NOW. (A debounce never fired while dragging - every step took longer than it - so each step
     sent a request and each answer redrew the plot: 154 requests for one drag.) The values follow
     the drag and playback instead of appearing only when the cursor stops. */
  const cvReq = useRef({ busy: false, again: false, want: "" });
  const cvWant = cursor.on && cursor.t1 !== null && sigKey ? `${cursor.t1}|${cursor.dual ? cursor.t2 : ""}|${sigKey}|${dataVersion}` : "";
  useEffect(() => {
    const R = cvReq.current;
    R.want = cvWant;
    if (!cvWant) return;
    const fetchNow = async () => {
      if (R.busy) { R.again = true; return; }
      R.busy = true;
      const c = useApp.getState().cursor;
      const key = R.want;
      const entries = key.split("|").slice(2, -1).join("|").split("|").map((e) => { const i = e.lastIndexOf("@"); return [e.slice(0, i), Number(e.slice(i + 1))] as [string, number]; });
      const groups = new Map<number, string[]>();
      entries.forEach(([sig, off]) => groups.set(off, [...(groups.get(off) ?? []), sig]));
      try {
        if (c.on && c.t1 !== null) {
          const out: Record<string, [number | null, number | null]> = {};
          await Promise.all(Array.from(groups, async ([off, sigs]) => {
            const a = await api.cursor(sigs, c.t1! - off);
            const b = c.dual && c.t2 !== null ? await api.cursor(sigs, c.t2 - off) : null;
            for (const sg of sigs) out[sg] = [a.values[sg] ?? null, b ? b.values[sg] ?? null : null];
          }));
          if (R.want) useApp.setState({ cvals: out });
        }
      } catch { /* the next move asks again */ }
      R.busy = false;
      if (R.again || (R.want && R.want !== key)) { R.again = false; if (R.want) fetchNow(); }
    };
    fetchNow();
  }, [cvWant]);
  return null;
}
