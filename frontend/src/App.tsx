/* The app's frame: the top bar, the area on screen (Recordings: the rail, a panel, the stage, the Inspector;
   Sweeps), the status bar and what floats over them. The background work is in shell/effects.ts, the panels in
   shell/panels.tsx (their table: components/rail.ts), the dialogs in shell/Dialogs.tsx. */
import { countRender } from "./perf";
import { Suspense, useEffect } from "react";
import { lazyPreload, preloadAll } from "./lazyPreload";
import OverviewStrip from "./components/OverviewStrip";
import TabBand from "./components/TabBand";
import PanelResizer from "./components/PanelResizer";
import { usePanelWidth } from "./components/panelWidth";
import PreviewPlots from "./components/PreviewPlots";
import StartCard from "./components/StartCard";
import DemoGuide from "./components/DemoGuide";
import Timeline from "./components/Timeline";
import { useApp } from "./store";
import { useT } from "./i18n";
import TopBar, { RecordingsBar } from "./components/TopBar";
import type { AreaId } from "./areas";
import StageBar from "./components/StageBar";
import Inspector from "./components/Inspector";
import StatusBar from "./components/StatusBar";
import CommandPalette from "./components/CommandPalette";
import FileBrowser from "./components/FileBrowser";
import Toasts from "./components/Toasts";
import Jobs from "./components/Jobs";
import { AxisDialog, ContextMenu, ModalFocus, PromptDialog } from "./components/Overlays";
import UnsavedDialog from "./components/UnsavedDialog";
import Tour from "./components/Tour";
import TabChoiceDialog from "./components/TabChoice";
import Welcome from "./components/Welcome";
import PlotGrid from "./components/PlotGrid";
import { RAIL_W, pageOnScreen, panelDef } from "./components/rail";
import { useShortcuts } from "./shortcuts";
import { PANEL_VIEW, Rail, usePanelPlace, usePlotsComeBack } from "./shell/panels";
import Dialogs from "./shell/Dialogs";
import { PlaceContext } from "./shell/PanelFrame";
import CursorValues from "./shell/CursorValues";
import {
  useConditions, useDocumentLook, useFileDrop, useLinksResume, useLiveFollow, useLivePoll, useLogData, useLogErrors,
  usePlayback, usePushEvents, useRestoreAndAutosave, useServerPing, useStartGivesWay,
} from "./shell/effects";
const SweepsScreen = lazyPreload(() => import("./components/sweeps/SweepsArea"));
const SweepsStatus = lazyPreload(() => import("./components/sweeps/SweepsStatus"));

/* resizable side panels: components/PanelResizer.tsx */
const MIN_STAGE = 380;

export default function App() {
  countRender("App");
  useEffect(() => { preloadAll(); }, []);          // panels / dialogs: ready before their first open
  const t = useT();
  const area = useApp((s) => s.area);
  const runs = useApp((s) => s.runs);
  const startOpen = useApp((s) => s.startOpen);
  // UX5.1: the Inspector is the plots' properties - not beside a page that is in their place
  const inspectorOpen = useApp((s) => s.inspectorOpen && !pageOnScreen(s));
  const hasFiles = runs.some((r) => r.format !== "derived");      // D7: Checks for any open file
  const logErrors = useLogErrors();

  useDocumentLook();
  useLinksResume();
  useConditions();
  useServerPing();
  const restored = useRestoreAndAutosave();
  useStartGivesWay();
  useLogData(logErrors, hasFiles);
  usePlayback();
  useLiveFollow();
  usePushEvents(restored);
  useLivePoll();
  useShortcuts();                       // A3: the keyboard (shortcuts.ts)
  usePlotsComeBack();
  const dropping = useFileDrop();

  const { panel, place } = usePanelPlace(hasFiles);
  // every panel keeps its own remembered width (rail.ts); the hooks are called for all, in a fixed order
  const [sideW0, setSideW0] = usePanelWidth("side", 280);
  const [invW, setInvW] = usePanelWidth("investigate", 380);
  const [msgW, setMsgW] = usePanelWidth("messages", 520);
  const [inspW, setInspW] = usePanelWidth("inspector", 320);     // inspector on the other side
  const widths: Record<string, [number, (w: number) => void]> = { side: [sideW0, setSideW0], investigate: [invW, setInvW], messages: [msgW, setMsgW] };
  const [wKey, wDef] = panel ? panelDef(panel).width : ["side", 280] as [string, number];
  const [sideW, setSideW] = widths[wKey] ?? widths.side;
  const side = place === "side";
  const cols = [RAIL_W, side ? sideW : 0, "1fr", inspectorOpen ? inspW : 0].map((c) => (typeof c === "number" ? `${c}px` : c)).join(" ");
  const View = panel ? PANEL_VIEW[panel] : null;

  return (
    <div className="app">
      <TopBar />
      {/* the area on screen: its bar, then its body (areas.ts). A Record over AreaId, so a new area
          does not compile until it has a view here */}
      {({ recordings: <>
      <RecordingsBar />
      <div className="main" style={{ gridTemplateColumns: cols }}>
        {side && <PanelResizer label={t("resizePanel")} style={{ insetInlineStart: RAIL_W + sideW - 3 }} width={sideW} setWidth={setSideW}
          grow={+1} def={wDef} max={() => window.innerWidth - RAIL_W - (inspectorOpen ? inspW : 0) - MIN_STAGE} />}
        {inspectorOpen && <PanelResizer label={t("resizePanel")} style={{ insetInlineEnd: inspW - 3 }} width={inspW} setWidth={setInspW}
          grow={-1} def={320} max={() => window.innerWidth - RAIL_W - (side ? sideW : 0) - MIN_STAGE} />}
        <Rail hasFiles={hasFiles} logErrors={logErrors} />
        {/* the panel, in ONE place in the tree whether beside the plots or on the whole stage (its grid column moves):
            moving it does not remount it, so what it had open stays open */}
        {View ? (
          <div className={place === "stage" ? `stage stage-panel stage-${panel}` : "panel-slot"} role={place === "stage" ? "main" : undefined}
            style={{ gridColumn: place === "stage" ? 3 : 2, gridRow: 1 }}>
            <PlaceContext.Provider value={place ?? "side"}>
              <Suspense fallback={place === "stage" ? <div className="rd" /> : <aside className="side" />}><View /></Suspense>
            </PlaceContext.Provider>
            {/* the Report (RE1), or a workspace on the whole stage (rail.ts isFull): the notices over it */}
            {place === "stage" && <div className="notices"><Toasts /></div>}
          </div>
        ) : <div style={{ gridColumn: 2, gridRow: 1 }} />}
        {place === "stage" ? null : <main className="stage" style={{ gridColumn: 3, gridRow: 1 }}>
          <StageBar />
          {runs.length > 0 && <DemoGuide />}
          {runs.length > 0 && <OverviewStrip />}
          {runs.length > 0 && <TabBand />}
          {!runs.length || startOpen ? <div className="stage-body"><Welcome /></div> : (
            <PlotGrid />
          )}
          {runs.length > 0 && <PreviewPlots />}
          {/* one place for every notice - the start card and the messages - above the timeline,
              instead of a card over the plots and messages over the timeline's controls */}
          <div className="notices"><StartCard /><Toasts /></div>
          {runs.length > 0 && <Timeline />}
        </main>}
        {inspectorOpen ? <div className="panel-slot" style={{ gridColumn: 4, gridRow: 1 }}><Inspector /></div> : <div style={{ gridColumn: 4, gridRow: 1 }} />}
      </div>
      </>,
      sweeps: <Suspense fallback={<div />}><SweepsScreen /></Suspense>,
      } satisfies Record<AreaId, React.ReactNode>)[area]}
      {area === "sweeps" ? <Suspense fallback={<footer className="status" />}><SweepsStatus /></Suspense>
        : <StatusBar />}
      <CursorValues />
      <CommandPalette />
      <FileBrowser />
      <Dialogs />
      <Jobs />
      <ContextMenu />
      <ModalFocus />
      <PromptDialog />
      <UnsavedDialog />
      <Tour />
      <TabChoiceDialog />
      <AxisDialog />
      {dropping && <div className="drop-overlay"><div>{t("dropOverlay")}</div></div>}
    </div>
  );
}
