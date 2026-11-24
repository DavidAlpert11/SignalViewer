/* The tool rail (A3: moved out of App.tsx): the side panels, in order - their button, their width and where they
   are shown. One table: a new panel is one row here and one view in shell/panels.tsx (a Record over PanelId, so
   it does not compile without one). */
import type { Icon } from "../icons";
import type { AppState, PanelId } from "../store";
import type { TKey } from "../i18n";
import { getPref, setPref } from "../prefs";
import { useApp } from "../store";

/** the tool rail's width: an icon with its short name under it (the names made Investigate findable) */
export const RAIL_W = 64;

/** Where a panel is shown (owner, 2026-11-23: one coherent app). The tools that act on the plots (Files, Create,
 *  Compare, Checks) sit beside them (Checks may take the stage with its ⤢ - a long list read); the workspaces read and worked in are pages on the whole stage, all in one frame
 *  (shell/PanelFrame.tsx): the Report always, Investigate and Messages by their rule - and beside the plots with the ⤡
 *  in their head (remembered), or for a moment when what they did needs the plots. */
export interface PanelDef {
  id: PanelId; icon: keyof typeof Icon; key: "data" | "analysis" | "compare" | "report" | "chkTitle" | "investigate" | "msgPanel"; short: TKey;
  /** its remembered width beside the plots (panelWidth.ts key, default px) */
  width: [string, number];
  place: "side" | "stage";
  /** a side panel that may take the whole stage: whether it opens that way until the user chooses with its ⤢ - always,
   *  or while it has something to read (a function of the state) */
  full?: boolean | ((s: FullState) => boolean);
}

/** what decides whether a panel is on the whole stage */
type FullState = Pick<AppState, "panelFull" | "whatChanged">;

export const RAIL: PanelDef[] = [
  { id: "data", icon: "Data", key: "data", short: "railData", width: ["side", 280], place: "side" },
  { id: "analysis", icon: "Analysis", key: "analysis", short: "railAnalysis", width: ["side", 280], place: "side" },
  { id: "compare", icon: "Compare", key: "compare", short: "railCompare", width: ["side", 280], place: "side" },
  // investigation step 2: named conditions. Wider (review 2026-11-13: What changed at 280 px read as a column of
  // wrapped words); owner, 2026-11-23: room like the Report's - What changed is read on the whole stage, the cursors
  // are placed with the panel beside the plots
  { id: "investigate", icon: "Search", key: "investigate", short: "railInvestigate", width: ["investigate", 380], place: "side", full: (s) => !!s.whatChanged },
  // MSG3: byte streams, links, structures. MSG9: the bytes, the values and the structure form side by side
  { id: "messages", icon: "Messages", key: "msgPanel", short: "railMessages", width: ["messages", 520], place: "side", full: true },
  { id: "report", icon: "Report", key: "report", short: "railReport", width: ["side", 280], place: "stage" },   // RE1: in place of the plots
  { id: "log", icon: "Log", key: "chkTitle", short: "railChecks", width: ["side", 280], place: "side",
    // D7: Checks for any open file. UX5.2: beside the plots by default (a finding or an event is a click to its time),
    // a page with the ⤢ to read a long list - the file and its sections in the index column, the section beside it
    full: false },
];

export const panelDef = (id: PanelId): PanelDef => RAIL.find((r) => r.id === id)!;

/** Can this panel take the whole stage (the ⤢ in its head)? */
export const canFill = (id: PanelId): boolean => panelDef(id).place === "side" && panelDef(id).full !== undefined;

/** Is the panel on the whole stage now: always for a stage panel; else the choice this session (the plots came back
 *  beside it), else the one the user made with its ⤢ (remembered), else its default. */
export function isFull(id: PanelId, s: FullState): boolean {
  const d = panelDef(id);
  if (d.place === "stage") return true;
  if (d.full === undefined) return false;
  if (s.panelFull[id] !== undefined) return s.panelFull[id]!;
  const p = getPref(`sv3.full.${id}`);
  return p !== null ? p === "true" : typeof d.full === "function" ? d.full(s) : d.full;
}

/** Is a page on the whole stage in place of the plots now (the Recordings area, an open panel that fills it)? The
 *  Inspector is the plots' properties (their cursor values, statistics, notes): it is not shown beside a page
 *  (UX5.1) and comes back with the plots. Checks needs an open file, as usePanelPlace says. */
export function pageOnScreen(s: FullState & Pick<AppState, "panel" | "area" | "runs">): boolean {
  if (s.area !== "recordings" || !s.panel) return false;
  if (s.panel === "log" && !s.runs.length) return false;
  return isFull(s.panel, s);
}

/** Something new to read in a panel (What changed opened): the plots that came back beside it are forgotten - where it
 *  goes is again the user's ⤢ choice, else its rule. */
export function forgetPlotsBeside(id: PanelId) {
  const st = useApp.getState();
  if (st.panelFull[id] !== undefined) {
    const rest = { ...st.panelFull };
    delete rest[id];
    useApp.setState({ panelFull: rest });
  }
}

/** The ⤢ / ⤡ in a panel's head: the user's choice, remembered for the next time. */
export function setFull(id: PanelId, on: boolean) {
  setPref(`sv3.full.${id}`, on);
  useApp.setState({ panelFull: { ...useApp.getState().panelFull, [id]: on } });
}

/** Something a panel did needs the plots (a new tab, the cursor moved): a panel on the whole stage moves beside them
 *  - for now only, its remembered choice stays. */
export function showPlotsBeside() {
  const st = useApp.getState();
  if (st.panel && canFill(st.panel) && isFull(st.panel, st)) useApp.setState({ panelFull: { ...st.panelFull, [st.panel]: false } });
}
