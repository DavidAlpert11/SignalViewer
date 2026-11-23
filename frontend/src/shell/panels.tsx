/* The Recordings area's side panels: each one's view (a Record over PanelId - a new panel does not compile without
   one), the tool rail that opens them, and the ⤢ that moves a panel to the whole stage. Their order, widths and
   places are the table in components/rail.ts. */
import { useEffect, useRef, type ComponentType } from "react";
import { lazyPreload } from "../lazyPreload";
import DataPanel from "../components/DataPanel";
import { RAIL, canFill, isFull, setFull, showPlotsBeside } from "../components/rail";
import { Icon } from "../icons";
import { useT } from "../i18n";
import { activeTab, useApp, type PanelId } from "../store";

const AnalysisPanel = lazyPreload(() => import("../components/AnalysisPanel"));
const InvestigatePanel = lazyPreload(() => import("../components/InvestigatePanel"));
const MessagesPanel = lazyPreload(() => import("../components/MessagesPanel"));
const ComparePanel = lazyPreload(() => import("../components/ComparePanel"));
const ReportScreen = lazyPreload(() => import("../components/ReportScreen"));   // RE1: the report, in place of the plots
const LogPanel = lazyPreload(() => import("../components/LogPanel"));

export const PANEL_VIEW: Record<PanelId, ComponentType> = {
  data: DataPanel, analysis: AnalysisPanel, compare: ComparePanel, investigate: InvestigatePanel,
  messages: MessagesPanel, report: ReportScreen, log: LogPanel,
};

/** The panel on screen and where: null (none), "side" (beside the plots) or "stage" (in place of them). */
export function usePanelPlace(hasFiles: boolean): { panel: PanelId | null; place: "side" | "stage" | null } {
  const panel = useApp((s) => s.panel);
  // D7: Checks needs an open file
  const shown = panel === "log" && !hasFiles ? null : panel;
  const full = useApp((s) => !!shown && isFull(shown, s));
  return { panel: shown, place: shown ? (full ? "stage" : "side") : null };
}

/** A panel on the whole stage gives way to the plots when something it did needs them: the active tab or its plots
 *  changed, or the time cursor moved (a step through occurrences, a row of What changed). */
export function usePlotsComeBack() {
  const sig = useApp((s) => {
    const tb = activeTab(s.ws);
    return `${tb.id}|${tb.plots.map((p) => p.id + ":" + p.signals.map((x) => x.sig).join(",")).join(";")}|${s.cursor.on ? `${s.cursor.t1}|${s.cursor.t2}` : ""}`;
  });
  const first = useRef(true);
  useEffect(() => { if (first.current) first.current = false; else showPlotsBeside(); }, [sig]);
}

/** The ⤢ / ⤡ in a side panel's head (nothing for a panel that cannot take the stage). */
export function FillButton({ id }: { id: PanelId }) {
  const t = useT();
  const full = useApp((s) => isFull(id, s));
  if (!canFill(id)) return null;
  const I = full ? Icon.Collapse : Icon.Expand;
  return (
    <button className="iconbtn panel-fill" data-panel-fill={id} aria-pressed={full} title={t(full ? "panelBeside" : "panelFill")}
      aria-label={t(full ? "panelBeside" : "panelFill")} onClick={() => setFull(id, !full)}><I width={15} height={15} /></button>
  );
}

/** The tool rail: a button per panel; a second click closes it. */
export function Rail({ hasFiles, logErrors }: { hasFiles: boolean; logErrors: number | null }) {
  const t = useT();
  const panel = useApp((s) => s.panel);
  return (
    <nav className="rail" aria-label="Panels">
      {RAIL.map((r) => {
        const I = Icon[r.icon];
        // U9: the Log tool stays in its place, disabled while no file is open (it used to vanish)
        const off = r.id === "log" && !hasFiles;     // D7: Checks for any open file
        return (
          <button key={r.id} className={`${panel === r.id ? "on" : ""}${r.id === "log" ? " rail-log" : ""}`} title={off ? t("chkNone") : t(r.key)}
            data-tour={r.id === "compare" ? "compare" : undefined}
            aria-label={t(r.key)} aria-pressed={panel === r.id} disabled={off}
            onClick={() => useApp.setState({ panel: panel === r.id ? null : r.id })}><I /><span className="rail-label" aria-hidden="true">{t(r.short)}</span>
            {r.id === "log" && !!logErrors && <span className="rail-badge" aria-label={t("logErrorsN", { n: logErrors })} />}
          </button>
        );
      })}
      <span className="spacer" />
    </nav>
  );
}
