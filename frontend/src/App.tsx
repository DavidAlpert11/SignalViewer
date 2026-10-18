import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { lazyPreload, preloadAll } from "./lazyPreload";
import PreviewPlots from "./components/PreviewPlots";
import StartCard from "./components/StartCard";
import { mavlinkResume } from "./mavlink";
import Timeline from "./components/Timeline";
const TemplateLibrary = lazyPreload(() => import("./components/TemplateLibrary"));
const ObjectDialog = lazyPreload(() => import("./components/ObjectDialog"));
const PlaceOnMapDialog = lazyPreload(() => import("./components/PlaceOnMapDialog"));
const TransformDialog = lazyPreload(() => import("./components/TransformDialog"));
const RetargetDialog = lazyPreload(() => import("./components/RetargetDialog"));
import { api } from "./api";
import { handleNewFiles, refreshAll, stopLive } from "./live";
import { ensureLogs } from "./logs";
import { detectSameFlight } from "./sync";
import { actions, activeTab, rangeKey, recordingExtent, useApp, type PanelId } from "./store";
import { translate, useT } from "./i18n";
import { Icon } from "./icons";
import { applyState, currentState, explainCopy, openDropped, openPaths, openSession, saveSession, startRetarget } from "./files";
import TopBar from "./components/TopBar";
import StageBar from "./components/StageBar";
import DataPanel from "./components/DataPanel";
const AnalysisPanel = lazyPreload(() => import("./components/AnalysisPanel"));
const ComparePanel = lazyPreload(() => import("./components/ComparePanel"));
const ReportPanel = lazyPreload(() => import("./components/ReportPanel"));
const LogPanel = lazyPreload(() => import("./components/LogPanel"));
const SyncDialog = lazyPreload(() => import("./components/SyncDialog"));
import Inspector from "./components/Inspector";
import PlotView from "./components/PlotView";
import StatusBar from "./components/StatusBar";
import CommandPalette from "./components/CommandPalette";
import FileBrowser from "./components/FileBrowser";
const ImportDialog = lazyPreload(() => import("./components/ImportDialog"));
import Toasts from "./components/Toasts";
import Jobs from "./components/Jobs";
const Help = lazyPreload(() => import("./components/Help"));
import { AxisDialog, ContextMenu, PromptDialog } from "./components/Overlays";
const ReportPreview = lazyPreload(() => import("./components/ReportPreview"));
const CompareTable = lazyPreload(() => import("./components/CompareTable"));

const RAIL: { id: PanelId; icon: keyof typeof Icon; key: "data" | "analysis" | "compare" | "report" | "flightLog" }[] = [
  { id: "data", icon: "Data", key: "data" },
  { id: "analysis", icon: "Analysis", key: "analysis" },
  { id: "compare", icon: "Compare", key: "compare" },
  { id: "report", icon: "Report", key: "report" },
  { id: "log", icon: "Log", key: "flightLog" },       // only while a file with a flight log is open
];

function Welcome() {
  const t = useT();
  const items = useApp((s) => s.recent);
  useEffect(() => { api.recent().then((r) => useApp.setState({ recent: r.items })).catch(() => {}); }, []);
  // T09: ready examples (a drone flight; three car runs to compare) - a first look in one click
  const [examples, setExamples] = useState<{ id: "flight" | "car"; paths: string[] }[]>([]);
  useEffect(() => { api.examples().then(setExamples).catch(() => setExamples([])); }, []);
  const files = items.filter((x) => x.kind === "file").slice(0, 6);
  const sessions = items.filter((x) => x.kind === "session").slice(0, 4);
  const openRecent = async (x: (typeof items)[number]) => {
    if (!x.exists) return;
    if (x.kind === "file") openPaths([x.path]);
    else {
      try { const r = await api.loadSession(x.path); await applyState(r.state, { announce: true }); }
      catch (e) { useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); }
    }
  };
  const forget = async (path: string) => useApp.setState({ recent: (await api.forgetRecent(path)).items });
  const list = (title: string, xs: typeof items, icon: React.ReactNode) => xs.length > 0 && (
    <div className="recent-col">
      <h3>{title}</h3>
      {xs.map((x) => (
        <div key={x.path} className={`recent-row${x.exists ? "" : " gone"}`}>
          <button className="recent-open" disabled={!x.exists} onClick={() => openRecent(x)} title={x.path}>
            {icon}<span className="recent-name">{x.name}</span><span className="recent-folder">{x.exists ? x.folder : t("notFound")}</span>
          </button>
          {x.kind === "session" && x.exists && (
            <button className="iconbtn sm" onClick={() => startRetarget(x.path)} aria-label={t("withNewFiles")} title={t("withNewFiles")}><Icon.Replace /></button>
          )}
          <button className="iconbtn sm" onClick={() => forget(x.path)} aria-label={t("forget")} title={t("forget")}><Icon.X /></button>
        </div>
      ))}
    </div>
  );
  return (
    <div className="welcome">
      <div className="welcome-card">
        <svg className="trace" viewBox="0 0 220 64" aria-hidden="true">
          <path d="M0 40 C 18 40, 22 14, 40 14 S 62 54, 80 54 S 102 22, 120 22 S 142 46, 160 46 S 190 30, 220 30"
            fill="none" stroke="var(--muted)" strokeWidth="2" strokeLinecap="round" />
          <line x1="132" y1="2" x2="132" y2="62" stroke="var(--amber)" strokeWidth="1.6" />
          <rect x="133" y="2" width="34" height="13" fill="var(--amber)" />
        </svg>
        <h1>{t("dropTitle")}</h1>
        <p>{t("dropHint")}</p>
        <button className="btn primary" style={{ height: 36, paddingInline: 16 }} onClick={() => useApp.setState({ browserOpen: true })}>
          <Icon.Folder /> {t("openFiles")}
        </button>
        {examples.length > 0 && (
          <p className="examples-line">{t("tryExample")}{" "}
            {examples.map((ex, i) => (
              <span key={ex.id}>{i > 0 && " · "}
                <button className="linkbtn" onClick={() => openPaths(ex.paths)}>{t(ex.id === "flight" ? "exampleFlight" : "exampleCar")}</button>
              </span>
            ))}
          </p>
        )}
        {(files.length > 0 || sessions.length > 0) && (
          <div className="recent">
            {list(t("recentFiles"), files, <Icon.File />)}
            {list(t("recentSessions"), sessions, <Icon.Open />)}
          </div>
        )}
      </div>
    </div>
  );
}

/** Plot grid; drag the gaps between plots to resize rows and columns (V-02). */
function PlotGrid() {
  const tab = useApp((s) => activeTab(s.ws));
  const ref = useRef<HTMLDivElement>(null);
  const rows = tab.rowSizes && tab.rowSizes.length === tab.rows ? tab.rowSizes : Array(tab.rows).fill(1);
  const cols = tab.colSizes && tab.colSizes.length === tab.cols ? tab.colSizes : Array(tab.cols).fill(1);
  const startDrag = (axis: "row" | "col", i: number) => (e: React.MouseEvent) => {
    e.preventDefault();
    const el = ref.current;
    if (!el) return;
    const sizes = (axis === "row" ? rows : cols).slice();
    const total = sizes.reduce((a, b) => a + b, 0);
    const px = axis === "row" ? el.clientHeight : el.clientWidth;
    const rtl = document.documentElement.dir === "rtl" && axis === "col";
    const start = axis === "row" ? e.clientY : e.clientX;
    const a0 = sizes[i], b0 = sizes[i + 1];
    const move = (ev: MouseEvent) => {
      let d = ((axis === "row" ? ev.clientY : ev.clientX) - start) / px * total;
      if (rtl) d = -d;
      const min = total * 0.08;
      const a = Math.max(min, Math.min(a0 + b0 - min, a0 + d));
      sizes[i] = a; sizes[i + 1] = a0 + b0 - a;
      if (axis === "row") actions.setSizes(sizes.slice(), tab.colSizes); else actions.setSizes(tab.rowSizes, sizes.slice());
    };
    const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
    window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
  };
  const frac = (arr: number[]) => arr.map((v) => `minmax(0, ${v}fr)`).join(" ");
  const sum = (arr: number[], n: number) => arr.slice(0, n).reduce((a, b) => a + b, 0) / arr.reduce((a, b) => a + b, 0);
  return (
    <div className="grid" ref={ref} style={{ gridTemplateRows: frac(rows), gridTemplateColumns: frac(cols) }}>
      {tab.plots.map((p, i) => <PlotView key={p.id} tab={tab} plot={p} index={i} active={i === tab.active} />)}
      {rows.slice(0, -1).map((_, i) => (
        <div key={`r${i}`} className="gutter-h" style={{ top: `calc(${sum(rows, i + 1) * 100}% - 4px)` }} onMouseDown={startDrag("row", i)}
          onDoubleClick={() => actions.setSizes(undefined, tab.colSizes)} role="separator" aria-orientation="horizontal" />
      ))}
      {cols.slice(0, -1).map((_, i) => (
        <div key={`c${i}`} className="gutter-v" style={{ insetInlineStart: `calc(${sum(cols, i + 1) * 100}% - 4px)` }} onMouseDown={startDrag("col", i)}
          onDoubleClick={() => actions.setSizes(tab.rowSizes, undefined)} role="separator" aria-orientation="vertical" />
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- resizable side panels */
const MIN_PANEL = 200, MIN_STAGE = 380;
function loadWidth(key: string, def: number): number {
  try { const v = Number(localStorage.getItem(`sv3.w.${key}`)); return v >= MIN_PANEL && v <= 1400 ? v : def; } catch { return def; }
}
function saveWidth(key: string, w: number) { try { localStorage.setItem(`sv3.w.${key}`, String(Math.round(w))); } catch { /* private mode */ } }

/** A draggable divider next to a side panel (mouse, touch or arrow keys; double-click = default width).
 *  `grow` is +1 when moving the pointer toward the plots makes the panel wider (the panel is on the
 *  start side), -1 for the panel on the end side. RTL (Hebrew) mirrors the pointer direction. */
function PanelResizer({ label, style, width, setWidth, grow, def, other }: {
  label: string; style: React.CSSProperties; width: number; setWidth: (w: number) => void; grow: 1 | -1; def: number; other: number;
}) {
  const clamp = (w: number) => Math.max(MIN_PANEL, Math.min(w, window.innerWidth - 48 - other - MIN_STAGE));
  const onDown = (e: React.PointerEvent) => {
    e.preventDefault();
    const x0 = e.clientX, w0 = width, rtl = document.documentElement.dir === "rtl" ? -1 : 1;
    const move = (ev: PointerEvent) => setWidth(clamp(w0 + grow * rtl * (ev.clientX - x0)));
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); document.body.classList.remove("resizing"); };
    document.body.classList.add("resizing");
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  const onKey = (e: React.KeyboardEvent) => {
    const rtl = document.documentElement.dir === "rtl" ? -1 : 1;
    const step = e.shiftKey ? 64 : 16;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault(); e.stopPropagation();
      setWidth(clamp(width + grow * rtl * (e.key === "ArrowRight" ? step : -step)));
    }
  };
  return <div className="resizer" role="separator" aria-orientation="vertical" aria-label={label} title={label} tabIndex={0}
    style={style} onPointerDown={onDown} onKeyDown={onKey} onDoubleClick={() => setWidth(clamp(def))} />;
}

export default function App() {
  useEffect(() => { preloadAll(); }, []);
  useEffect(() => { mavlinkResume(); }, []);           // a MAVLink link still running after a reload           // panels / dialogs: ready before their first open
  const t = useT();
  const theme = useApp((s) => s.theme);
  const lang = useApp((s) => s.lang);
  const uiScale = useApp((s) => s.uiScale);
  const importPaths = useApp((s) => s.importPaths);
  const helpOpen = useApp((s) => s.helpOpen);
  const previewHtml = useApp((s) => s.reportPreviewHtml);
  const compareTable = useApp((s) => !!s.compareTable);
  const templatesOpen = useApp((s) => s.templatesOpen);
  const objectDialog = useApp((s) => s.objectDialog);
  const placeDialog = useApp((s) => s.placeDialog);
  const transformOpen = useApp((s) => !!s.transformTargets);
  const retargetOpen = useApp((s) => !!s.retarget);
  const panel = useApp((s) => s.panel);
  const inspectorOpen = useApp((s) => s.inspectorOpen);
  const runs = useApp((s) => s.runs);
  const ws = useApp((s) => s.ws);
  const cursor = useApp((s) => s.cursor);
  const streaming = useApp((s) => s.streaming);
  const dataVersion = useApp((s) => s.dataVersion);
  const zoomMode = useApp((s) => s.zoomMode);
  const logMarkers = useApp((s) => s.logMarkers);
  const syncFor = useApp((s) => s.syncFor);
  const geoBase = useApp((s) => s.geoBase);
  // null: no open file has a flight log (no Log button at all); else the number of logged errors
  const logErrors = useMemo(() => {
    const lr = runs.filter((r) => r.log);
    return lr.length ? lr.reduce((n, r) => n + (r.log?.errors ?? 0), 0) : null;
  }, [runs]);
  const liveAutoStop = useApp((s) => s.liveAutoStop);
  const liveNewFiles = useApp((s) => s.liveNewFiles);
  const [dropping, setDropping] = useState(false);
  const [sideW, setSideW] = useState(() => loadWidth("side", 280));          // files / analysis / ... panel
  const [inspW, setInspW] = useState(() => loadWidth("inspector", 320));     // inspector on the other side
  useEffect(() => saveWidth("side", sideW), [sideW]);
  useEffect(() => saveWidth("inspector", inspW), [inspW]);
  const restored = useRef(false);
  const tab = activeTab(ws);

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
    return () => window.clearInterval(h);
  }, []);

  /* restore the last workspace once */
  useEffect(() => {
    (async () => {
      try {
        const { state } = await api.getAutosave();
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
  }, [ws, runs, theme, lang, uiScale, zoomMode, liveAutoStop, liveNewFiles, logMarkers, geoBase]);
  // an autopilot log and a telemetry log of the same flight, not aligned: offer to align them
  useEffect(() => { if (runs.some((r) => r.format === "tlog")) detectSameFlight(); }, [runs]);
  // flight-log data: fetched only for files that have it, when the panel or the plot markers need it
  useEffect(() => {
    if (logErrors !== null && (panel === "log" || logMarkers !== "off")) ensureLogs();
    if (logErrors === null && panel === "log") useApp.setState({ panel: "data" });
  }, [runs, panel, logMarkers, logErrors]);

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

  /* T39: data sent from Python (signalviewer_push.show): refresh, and put a NEW run in the active plot */
  useEffect(() => {
    let since = 0;
    let first = true;                     // the first ask: data sent while the page loaded counts,
    const h = window.setInterval(async () => {   // older data (before a reload) is not plotted again
      try {
        const r = await api.pushEvents(since);
        const fresh = r.events.filter((e) => !first || e.age < 10);
        first = false;
        since = r.seq;
        if (!r.events.length) return;
        const runs = await api.listRuns();
        const st = useApp.getState();
        useApp.setState({ runs, dataVersion: st.dataVersion + 1 });
        for (const e of fresh) {
          if (!e.new) continue;
          const run = runs.find((x) => x.id === e.run);
          if (!run) continue;
          if (e.plot) run.signals.slice(0, 8).forEach((s) => actions.addSignal(s.id));
          st.toast({ kind: "info", text: translate(st.lang, "pushReceived", { name: e.name, n: run.signals.length }) });
        }
      } catch { /* server busy; next tick */ }
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
    const h = window.setInterval(async () => {
      try {
        const r = await api.poll();
        if (!useApp.getState().streaming) return;
        if (r.changed.length && r.runs) {
          const st = useApp.getState();
          useApp.setState({ runs: r.runs, dataVersion: st.dataVersion + 1, liveLastData: Date.now() });
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
      } catch { /* server busy; next tick */ }
    }, 1000);
    return () => window.clearInterval(h);
  }, [streaming]);

  /* keyboard shortcuts */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const st = useApp.getState();
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.target instanceof HTMLTextAreaElement;
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "k") { e.preventDefault(); useApp.setState({ paletteOpen: true }); return; }
      if (mod && e.key.toLowerCase() === "o" && e.shiftKey) { e.preventDefault(); openSession(); return; }
      if (mod && e.key.toLowerCase() === "o") { e.preventDefault(); useApp.setState({ browserOpen: true }); return; }
      if (mod && e.key.toLowerCase() === "s") { e.preventDefault(); saveSession(); return; }
      const SCALES = [1, 1.12, 1.25] as const;
      if (mod && (e.key === "=" || e.key === "+")) { e.preventDefault(); const i = SCALES.indexOf(st.uiScale); useApp.setState({ uiScale: SCALES[Math.min(2, i + 1)] }); return; }
      if (mod && e.key === "-") { e.preventDefault(); const i = SCALES.indexOf(st.uiScale); useApp.setState({ uiScale: SCALES[Math.max(0, i - 1)] }); return; }
      if (mod && e.key === "0") { e.preventDefault(); useApp.setState({ uiScale: 1 }); return; }
      if (e.key === "F5" || (mod && e.key.toLowerCase() === "r")) { e.preventDefault(); refreshAll(); return; }   // not a page reload
      if (typing || st.paletteOpen || st.browserOpen || st.picker || st.importPaths || st.helpOpen) return;
      if (e.key === "?") { useApp.setState({ helpOpen: true }); return; }
      if (mod && e.key.toLowerCase() === "z" && !e.shiftKey) { e.preventDefault(); st.undo(); return; }
      if (mod && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) { e.preventDefault(); st.redo(); return; }
      if (mod) return;
      if (e.key === " ") { e.preventDefault(); actions.toggleCursor(); }
      else if (e.key.toLowerCase() === "d") actions.toggleDual();
      else if (e.key.toLowerCase() === "r") actions.resetZoom();
      else if (e.key.toLowerCase() === "z") actions.cycleZoomMode();
      else if (e.key.toLowerCase() === "n") { e.preventDefault(); actions.addNoteAtCursor(); }
      else if (e.key === "Backspace" || (e.altKey && e.key === "ArrowLeft")) { e.preventDefault(); actions.zoomBack(); }
      else if (e.key === "Home" || e.key === "End") {          // the timeline: start / end of the recording
        const r = recordingExtent(st.runs);
        if (r) { e.preventDefault(); const tt = e.key === "Home" ? r[0] : r[1]; actions.setTime(tt); actions.followTime(tt); }
      }
      else if (e.key.toLowerCase() === "p") actions.togglePlay();
      else if (/^[1-9]$/.test(e.key)) actions.setActivePlot(Number(e.key) - 1);
      else if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && st.cursor.on && st.cursor.t1 !== null) {
        // jump from recorded value to recorded value (no interpolation); Shift = 10 samples
        e.preventDefault();
        actions.stepCursor((e.key === "ArrowRight" ? 1 : -1) * (e.shiftKey ? 10 : 1));
      } else if (e.key === "Delete" && st.selected) actions.removeSignal(st.selected.plotId, st.selected.sig);
      else if (e.key === "Escape") useApp.setState({ selected: null });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

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

  const cols = [48, panel ? sideW : 0, "1fr", inspectorOpen ? inspW : 0].map((c) => (typeof c === "number" ? `${c}px` : c)).join(" ");

  return (
    <div className="app">
      <TopBar />
      <div className="main" style={{ gridTemplateColumns: cols }}>
        {panel && <PanelResizer label={t("resizePanel")} style={{ insetInlineStart: 48 + sideW - 3 }} width={sideW} setWidth={setSideW}
          grow={+1} def={280} other={inspectorOpen ? inspW : 0} />}
        {inspectorOpen && <PanelResizer label={t("resizePanel")} style={{ insetInlineEnd: inspW - 3 }} width={inspW} setWidth={setInspW}
          grow={-1} def={320} other={panel ? sideW : 0} />}
        <nav className="rail" aria-label="Panels">
          {RAIL.filter((r) => r.id !== "log" || logErrors !== null).map((r) => {
            const I = Icon[r.icon];
            return (
              <button key={r.id} className={`${panel === r.id ? "on" : ""}${r.id === "log" ? " rail-log" : ""}`} title={t(r.key)} aria-label={t(r.key)} aria-pressed={panel === r.id}
                onClick={() => useApp.setState({ panel: panel === r.id ? null : r.id })}><I />
                {r.id === "log" && !!logErrors && <span className="rail-badge" aria-label={t("logErrorsN", { n: logErrors })} />}
              </button>
            );
          })}
          <span className="spacer" />
        </nav>
        <Suspense fallback={<aside className="side" />}>
          {panel === "data" ? <DataPanel /> : panel === "analysis" ? <AnalysisPanel /> : panel === "compare" ? <ComparePanel />
            : panel === "report" ? <ReportPanel /> : panel === "log" && logErrors !== null ? <LogPanel /> : <div />}
        </Suspense>
        <main className="stage">
          <StageBar />
          {!runs.length ? <div className="stage-body"><Welcome /></div> : (
            <PlotGrid />
          )}
          {runs.length > 0 && <PreviewPlots />}
          <StartCard />
          {runs.length > 0 && <Timeline />}
        </main>
        {inspectorOpen ? <Inspector /> : <div />}
      </div>
      <StatusBar />
      <CommandPalette />
      <FileBrowser />
      <Suspense fallback={null}>
        {importPaths && <ImportDialog />}
        {helpOpen && <Help />}
        {previewHtml && <ReportPreview />}
        {compareTable && <CompareTable />}
        {templatesOpen && <TemplateLibrary />}
        {objectDialog && <ObjectDialog key={`${objectDialog.plotId}/${objectDialog.objectId ?? "new"}`} />}
        {placeDialog && <PlaceOnMapDialog key={placeDialog} />}
        {syncFor && <SyncDialog />}
        {transformOpen && <TransformDialog />}
        {retargetOpen && <RetargetDialog />}
      </Suspense>
      <Toasts />
      <Jobs />
      <ContextMenu />
      <PromptDialog />
      <AxisDialog />
      {dropping && <div className="drop-overlay"><div>{t("dropOverlay")}</div></div>}
    </div>
  );
}
